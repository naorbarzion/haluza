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

def get_greeting(hour):
    if 5 <= hour < 12:
        return "בוקר טוב"
    elif 12 <= hour < 18:
        return "צהריים טובים"
    elif 18 <= hour < 22:
        return "ערב טוב"
    else:
        return "לילה טוב"

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

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/driver/dashboard')
@login_required
def driver_dashboard():
    if session.get('role') != 'driver':
        return redirect(url_for('index'))
    current_hour = datetime.now().hour
    greeting = get_greeting(current_hour)
    return render_template('driver_dashboard.html', 
                         greeting=greeting,
                         full_name=session.get('full_name'))

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html', 
                         full_name=session.get('full_name'))

@app.route('/admin/reports')
@login_required
@admin_required
def reports():
    return render_template('reports.html', 
                         full_name=session.get('full_name'))

@app.route('/admin/get_drivers')
@login_required
@admin_required
def get_drivers():
    try:
        drivers = list(db.users.find({'role': 'driver'}, {'_id': 1, 'full_name': 1}).sort('full_name', 1))
        
        # המרת ObjectId ל-string
        for driver in drivers:
            driver['id'] = str(driver['_id'])
            del driver['_id']
        
        return jsonify(drivers)
        
    except Exception as e:
        logger.error(f"Error getting drivers: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/admin/search_trips', methods=['POST'])
@login_required
@admin_required
def search_trips():
    try:
        data = request.json
        query = {}
        
        if data.get('date_from'):
            query['date_time'] = {'$gte': data['date_from']}
        
        if data.get('date_to'):
            if 'date_time' in query:
                query['date_time']['$lte'] = data['date_to']
            else:
                query['date_time'] = {'$lte': data['date_to']}
        
        if data.get('driver_id'):
            query['user_id'] = ObjectId(data['driver_id'])
        
        if data.get('status'):
            query['status'] = data['status']
        
        trips = list(db.trips.find(query).sort('date_time', -1))
        
        # המרת ObjectId ל-string
        for trip in trips:
            trip['_id'] = str(trip['_id'])
            trip['user_id'] = str(trip['user_id'])
            # הוספת שם הנהג
            driver = db.users.find_one({'_id': ObjectId(trip['user_id'])})
            trip['driver_name'] = driver['full_name'] if driver else 'לא ידוע'
        
        return jsonify(trips)
        
    except Exception as e:
        logger.error(f"Error searching trips: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/admin/update_trip_status', methods=['POST'])
@login_required
@admin_required
def update_trip_status():
    try:
        data = request.json
        
        update_data = {
            'status': data['status']
        }
        if data.get('rejection_reason'):
            update_data['rejection_reason'] = data['rejection_reason']
        
        result = db.trips.update_one(
            {'_id': ObjectId(data['trip_id'])},
            {'$set': update_data}
        )
        
        if result.modified_count == 0:
            return jsonify({"status": "error", "message": "הנסיעה לא נמצאה"}), 404
        
        updated_trip = db.trips.find_one({'_id': ObjectId(data['trip_id'])})
        driver = db.users.find_one({'_id': updated_trip['user_id']})
        
        updated_trip['_id'] = str(updated_trip['_id'])
        updated_trip['user_id'] = str(updated_trip['user_id'])
        updated_trip['driver_name'] = driver['full_name'] if driver else 'לא ידוע'
        
        return jsonify({
            "status": "success",
            "trip": updated_trip
        })
        
    except Exception as e:
        logger.error(f"Error in update_trip_status: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/admin/export_trips', methods=['POST'])
@login_required
@admin_required
def export_trips():
    try:
        data = request.json
        query = {}
        
        if data.get('date_from'):
            query['date_time'] = {'$gte': data['date_from']}
        
        if data.get('date_to'):
            if 'date_time' in query:
                query['date_time']['$lte'] = data['date_to']
            else:
                query['date_time'] = {'$lte': data['date_to']}
        
        if data.get('driver_id'):
            query['user_id'] = ObjectId(data['driver_id'])
        
        if data.get('status'):
            query['status'] = data['status']
        
        trips = list(db.trips.find(query).sort('date_time', -1))
        
        # הכנת הנתונים לאקסל
        excel_data = []
        for trip in trips:
            driver = db.users.find_one({'_id': trip['user_id']})
            excel_data.append({
                'תאריך ושעה': trip['date_time'],
                'שם הנהג': driver['full_name'] if driver else 'לא ידוע',
                'רכב': trip['vehicle'],
                'מטרת נסיעה': trip['purpose'],
                'יעד': trip.get('destination', ''),
                'סטטוס': trip['status'],
                'תאריך יצירה': trip['created_at']
            })
        
        df = pd.DataFrame(excel_data)
        
        # מיפוי ערכים
        status_map = {
            'pending': 'ממתין לאישור',
            'approved': 'מאושר',
            'rejected': 'נדחה'
        }
        df['סטטוס'] = df['סטטוס'].map(status_map)
        
        vehicle_map = {
            'car1': 'טויוטה קורולה - 12-345-67',
            'car2': 'יונדאי i35 - 23-456-78',
            'car3': 'סקודה אוקטביה - 34-567-89'
        }
        df['רכב'] = df['רכב'].map(vehicle_map)
        
        # יצירת קובץ אקסל
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='דוח נסיעות')
            worksheet = writer.sheets['דוח נסיעות']
            
            for idx, col in enumerate(df.columns):
                max_length = max(df[col].astype(str).apply(len).max(), len(col)) + 2
                worksheet.set_column(idx, idx, max_length)
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'דוח_נסיעות_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
        )
        
    except Exception as e:
        logger.error(f"Error exporting trips: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False)  # שינוי ל-False בסביבת ייצור
