from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import os
import pandas as pd
from io import BytesIO
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import logging
from dotenv import load_dotenv
from bson import ObjectId

# הגדרת logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# טעינת משתני הסביבה
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key_here')

# התחברות ל-MongoDB עם טיפול שגיאות
try:
    MONGODB_URI = os.getenv('MONGODB_URI')
    if not MONGODB_URI:
        raise ValueError("MONGODB_URI is not set in environment variables")
    
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    # בדיקת חיבור
    client.admin.command('ping')
    logger.info("Successfully connected to MongoDB")
    
    db = client.tracer_db
except (ConnectionFailure, ServerSelectionTimeoutError) as e:
    logger.error(f"Could not connect to MongoDB: {e}")
    raise
except Exception as e:
    logger.error(f"An error occurred while connecting to MongoDB: {e}")
    raise

# הוספת הדקורטורים החסרים
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def create_default_users():
    try:
        # מחיקת כל המשתמשים הקיימים
        db.users.delete_many({})
        
        # משתמשי מנהל
        admin_users = [
            {'username': 'admin', 'password': generate_password_hash('admin'), 'full_name': 'מנהל ראשי', 'role': 'admin'},
            {'username': 'admin2', 'password': generate_password_hash('1234'), 'full_name': 'מנהל משנה', 'role': 'admin'}
        ]
        
        db.users.insert_many(admin_users)
        logger.info("Added admin users")
        
        # משתמשי נהגים
        drivers = [
            {'username': 'driver1', 'password': generate_password_hash('1234'), 'full_name': 'משה כהן', 'role': 'driver'},
            {'username': 'driver2', 'password': generate_password_hash('1234'), 'full_name': 'יוסי לוי', 'role': 'driver'}
        ]
        
        db.users.insert_many(drivers)
        logger.info("Added driver users")
        
        return True
    except Exception as e:
        logger.error(f"Error creating default users: {e}")
        return False

@app.route('/init-db')
def init_database():
    try:
        if create_default_users():
            return jsonify({"status": "success", "message": "משתמשים נוצרו בהצלחה"})
        else:
            return jsonify({"status": "error", "message": "שגיאה ביצירת משתמשים"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('driver_dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            
            user = db.users.find_one({'username': username})
            logger.info(f"Login attempt for user: {username}")
            
            if user and check_password_hash(user['password'], password):
                session['user_id'] = str(user['_id'])
                session['username'] = user['username']
                session['full_name'] = user['full_name']
                session['role'] = user['role']
                logger.info(f"Successful login for user: {username}")
                
                if user['role'] == 'admin':
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('driver_dashboard'))
            
            logger.warning(f"Failed login attempt for user: {username}")
            return render_template('login.html', error='שם משתמש או סיסמה שגויים')
        
        return render_template('login.html')
    except Exception as e:
        logger.error(f"Error in login route: {e}")
        return render_template('login.html', error='אירעה שגיאה במערכת, אנא נסה שוב מאוחר יותר')

@app.route('/driver/submit_trip', methods=['POST'])
@login_required
def submit_trip():
    if session.get('role') != 'driver':
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
        
    try:
        data = request.form
        trip = {
            'user_id': ObjectId(session['user_id']),
            'vehicle': data['vehicle'],
            'date_time': data['date_time'],
            'purpose': data['purpose'],
            'destination': data['destination'],
            'status': 'pending',
            'created_at': datetime.utcnow()
        }
        
        result = db.trips.insert_one(trip)
        trip['_id'] = str(result.inserted_id)
        
        return jsonify({
            "status": "success",
            "message": "הנסיעה נוספה בהצלחה",
            "trip": trip
        })
        
    except Exception as e:
        print(f"Error in submit_trip: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/driver/get_trips')
@login_required
def driver_get_trips():
    try:
        trips = list(db.trips.find({'user_id': ObjectId(session['user_id'])}).sort('created_at', -1))
        
        # המרת ObjectId ל-string
        for trip in trips:
            trip['_id'] = str(trip['_id'])
            trip['user_id'] = str(trip['user_id'])
        
        return jsonify(trips)
        
    except Exception as e:
        print(f"Error in driver_get_trips: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ... המשך הקוד עם התאמות דומות לכל הפונקציות ...

if __name__ == '__main__':
    app.run(debug=False)  # שינוי ל-False בסביבת ייצור
