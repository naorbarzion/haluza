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
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def create_default_users():
    try:
        # מחיקת כל הקולקציות הקיימות
        db.users.drop()
        db.trips.drop()
        
        # יצירת אינדקסים
        db.users.create_index('username', unique=True)
        db.trips.create_index([('user_id', 1), ('created_at', -1)])
        db.trips.create_index([('status', 1), ('date_time', -1)])
        
        # משתמשי מנהל
        admin_users = [
            {
                'username': 'admin',
                'password': generate_password_hash('admin'),
                'full_name': 'מנהל ראשי',
                'role': 'admin'
            },
            {
                'username': 'admin2',
                'password': generate_password_hash('1234'),
                'full_name': 'מנהל משנה',
                'role': 'admin'
            }
        ]
        
        # הוספת משתמשי מנהל
        result = db.users.insert_many(admin_users)
        logger.info(f"Added {len(result.inserted_ids)} admin users")
        
        # משתמשי נהגים
        drivers = [
            {'username': 'driver1', 'password': generate_password_hash('1234'), 'full_name': 'משה כהן', 'role': 'driver'},
            {'username': 'driver2', 'password': generate_password_hash('1234'), 'full_name': 'יוסי לוי', 'role': 'driver'},
            {'username': 'driver3', 'password': generate_password_hash('1234'), 'full_name': 'דוד כהן', 'role': 'driver'},
            {'username': 'driver4', 'password': generate_password_hash('1234'), 'full_name': 'יעקב אברהם', 'role': 'driver'},
            {'username': 'driver5', 'password': generate_password_hash('1234'), 'full_name': 'דניאל דוד', 'role': 'driver'},
            {'username': 'driver6', 'password': generate_password_hash('1234'), 'full_name': 'אברהם יצחק', 'role': 'driver'},
            {'username': 'driver7', 'password': generate_password_hash('1234'), 'full_name': 'יצחק משה', 'role': 'driver'},
            {'username': 'driver8', 'password': generate_password_hash('1234'), 'full_name': 'שמואל שלום', 'role': 'driver'},
            {'username': 'driver9', 'password': generate_password_hash('1234'), 'full_name': 'אהרון הכהן', 'role': 'driver'},
            {'username': 'driver10', 'password': generate_password_hash('1234'), 'full_name': 'מאיר דוד', 'role': 'driver'},
            {'username': 'driver11', 'password': generate_password_hash('1234'), 'full_name': 'חיים כהן', 'role': 'driver'},
            {'username': 'driver12', 'password': generate_password_hash('1234'), 'full_name': 'יונתן לוי', 'role': 'driver'},
            {'username': 'driver13', 'password': generate_password_hash('1234'), 'full_name': 'אליהו הנביא', 'role': 'driver'},
            {'username': 'driver14', 'password': generate_password_hash('1234'), 'full_name': 'שלמה המלך', 'role': 'driver'},
            {'username': 'driver15', 'password': generate_password_hash('1234'), 'full_name': 'דן הגיבור', 'role': 'driver'},
            {'username': 'driver16', 'password': generate_password_hash('1234'), 'full_name': 'גד החוזה', 'role': 'driver'}
        ]
        
        # הוספת משתמשי נהגים
        result = db.users.insert_many(drivers)
        logger.info(f"Added {len(result.inserted_ids)} driver users")
        
        # יצירת נסיעה לדוגמה
        example_driver = db.users.find_one({'username': 'driver1'})
        if example_driver:
            example_trip = {
                'user_id': example_driver['_id'],
                'vehicle': 'car1',
                'date_time': datetime.utcnow().isoformat(),
                'purpose': 'נסיעת דוגמה',
                'destination': 'תל אביב',
                'status': 'pending',
                'created_at': datetime.utcnow()
            }
            db.trips.insert_one(example_trip)
            logger.info("Added example trip")
        
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
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # אם המשתמש כבר מחובר, נפנה אותו לדף המתאים
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('driver_dashboard'))

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
            'rejection_reason': None,
            'created_at': datetime.utcnow()
        }
        
        result = db.trips.insert_one(trip)
        
        # המרת ObjectId למחרוזת לפני החזרה
        trip_response = {
            '_id': str(result.inserted_id),
            'user_id': str(trip['user_id']),
            'vehicle': trip['vehicle'],
            'date_time': trip['date_time'],
            'purpose': trip['purpose'],
            'destination': trip['destination'],
            'status': trip['status'],
            'rejection_reason': trip['rejection_reason'],
            'created_at': trip['created_at'].isoformat()
        }
        
        logger.info(f"New trip submitted: {trip_response}")
        
        return jsonify({
            "status": "success",
            "message": "הנסיעה נוספה בהצלחה",
            "trip": trip_response
        })
        
    except Exception as e:
        logger.error(f"Error in submit_trip: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/driver/get_trips')
@login_required
def driver_get_trips():
    try:
        # שליפת כל הנסיעות של הנהג
        trips = list(db.trips.find(
            {'user_id': ObjectId(session['user_id'])}
        ).sort('created_at', -1))
        
        # המרת ObjectId למחרוזת
        for trip in trips:
            trip['_id'] = str(trip['_id'])
            trip['user_id'] = str(trip['user_id'])
            # המרת תאריכים למחרוזות
            if 'created_at' in trip and isinstance(trip['created_at'], datetime):
                trip['created_at'] = trip['created_at'].isoformat()
        
        logger.info(f"Retrieved {len(trips)} trips for driver {session['user_id']}")
        return jsonify(trips)
        
    except Exception as e:
        logger.error(f"Error in driver_get_trips: {str(e)}")
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
        logger.info(f"Updating trip status with data: {data}")
        
        # בדיקה שכל השדות הנדרשים קיימים
        if not data:
            logger.error("No JSON data received")
            return jsonify({"status": "error", "message": "לא התקבלו נתונים"}), 400
        
        # קבלת מזהה הנסיעה מהבקשה
        trip_id = data.get('_id') or data.get('trip_id')
        if not trip_id:
            logger.error("Missing trip ID in request")
            return jsonify({"status": "error", "message": "חסר מזהה נסיעה"}), 400
            
        if not data.get('status'):
            logger.error("Missing status in request")
            return jsonify({"status": "error", "message": "חסר סטטוס"}), 400
        
        # הכנת נתוני העדכון
        update_data = {
            'status': data['status']
        }
        
        # הוספת סיבת דחייה אם קיימת
        if data.get('rejection_reason'):
            update_data['rejection_reason'] = data['rejection_reason']
        elif data['status'] == 'rejected' and not data.get('rejection_reason'):
            logger.error("Missing rejection reason for rejected status")
            return jsonify({"status": "error", "message": "חסרה סיבת דחייה"}), 400
        
        try:
            if isinstance(trip_id, str):
                trip_id = ObjectId(trip_id)
        except Exception as e:
            logger.error(f"Invalid trip_id format: {e}")
            return jsonify({"status": "error", "message": "מזהה נסיעה לא תקין"}), 400
        
        # עדכון הנסיעה
        result = db.trips.update_one(
            {'_id': trip_id},
            {'$set': update_data}
        )
        
        if result.modified_count == 0:
            logger.error(f"Trip {trip_id} not found")
            return jsonify({"status": "error", "message": "הנסיעה לא נמצאה"}), 404
        
        # שליפת הנסיעה המעודכנת
        updated_trip = db.trips.find_one({'_id': trip_id})
        if not updated_trip:
            logger.error(f"Could not fetch updated trip {trip_id}")
            return jsonify({"status": "error", "message": "שגיאה בשליפת הנסיעה המעודכנת"}), 500
            
        # שליפת פרטי הנהג
        driver = db.users.find_one({'_id': updated_trip['user_id']})
        
        # הכנת אובייקט התגובה
        response_trip = {
            '_id': str(updated_trip['_id']),
            'user_id': str(updated_trip['user_id']),
            'vehicle': updated_trip['vehicle'],
            'date_time': updated_trip['date_time'],
            'purpose': updated_trip['purpose'],
            'destination': updated_trip.get('destination', ''),
            'status': updated_trip['status'],
            'rejection_reason': updated_trip.get('rejection_reason', ''),
            'created_at': updated_trip.get('created_at', '').isoformat() if updated_trip.get('created_at') else '',
            'driver_name': driver['full_name'] if driver else 'לא ידוע'
        }
        
        logger.info(f"Successfully updated trip {trip_id} to status {data['status']}")
        return jsonify({
            "status": "success",
            "message": "סטטוס הנסיעה עודכן בהצלחה",
            "trip": response_trip
        })
        
    except Exception as e:
        logger.error(f"Error in update_trip_status: {str(e)}")
        return jsonify({
            "status": "error", 
            "message": f"שגיאה בעדכון סטטוס הנסיעה: {str(e)}"
        }), 500

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

@app.route('/admin/get_trips')
@login_required
@admin_required
def admin_get_trips():
    try:
        # מיון לפי סטטוס (pending ראשון) ואז לפי תאריך
        pipeline = [
            {
                '$addFields': {
                    'statusOrder': {
                        '$switch': {
                            'branches': [
                                {'case': {'$eq': ['$status', 'pending']}, 'then': 1},
                                {'case': {'$eq': ['$status', 'approved']}, 'then': 2},
                                {'case': {'$eq': ['$status', 'rejected']}, 'then': 3}
                            ],
                            'default': 4
                        }
                    }
                }
            },
            {
                '$sort': {
                    'statusOrder': 1,
                    'date_time': -1
                }
            }
        ]
        
        trips = list(db.trips.aggregate(pipeline))
        
        # המרת ObjectId למחרוזת והוספת שם הנהג
        for trip in trips:
            trip['_id'] = str(trip['_id'])
            trip['user_id'] = str(trip['user_id'])
            driver = db.users.find_one({'_id': ObjectId(trip['user_id'])})
            trip['driver_name'] = driver['full_name'] if driver else 'לא ידוע'
            # הסרת שדה עזר
            trip.pop('statusOrder', None)
            # המרת תאריכים למחרוזות
            if 'created_at' in trip and isinstance(trip['created_at'], datetime):
                trip['created_at'] = trip['created_at'].isoformat()
        
        logger.info(f"Retrieved {len(trips)} trips")
        return jsonify(trips)
        
    except Exception as e:
        logger.error(f"Error in admin_get_trips: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/admin/reschedule_trip', methods=['POST'])
@login_required
@admin_required
def reschedule_trip():
    try:
        data = request.json
        logger.info(f"Rescheduling trip with data: {data}")
        
        # בדיקה שכל השדות הנדרשים קיימים
        if not data:
            logger.error("No JSON data received")
            return jsonify({"status": "error", "message": "לא התקבלו נתונים"}), 400
        
        # קבלת מזהה הנסיעה מהבקשה
        trip_id = data.get('_id') or data.get('trip_id')
        if not trip_id:
            logger.error("Missing trip ID in request")
            return jsonify({"status": "error", "message": "חסר מזהה נסיעה"}), 400
            
        if not data.get('new_date_time'):
            logger.error("Missing new_date_time in request")
            return jsonify({"status": "error", "message": "חסר מועד חדש"}), 400
        
        try:
            if isinstance(trip_id, str):
                trip_id = ObjectId(trip_id)
        except Exception as e:
            logger.error(f"Invalid trip_id format: {e}")
            return jsonify({"status": "error", "message": "מזהה נסיעה לא תקין"}), 400
        
        # עדכון הנסיעה
        result = db.trips.update_one(
            {'_id': trip_id},
            {'$set': {'date_time': data['new_date_time']}}
        )
        
        if result.modified_count == 0:
            logger.error(f"Trip {trip_id} not found")
            return jsonify({"status": "error", "message": "הנסיעה לא נמצאה"}), 404
        
        # שליפת הנסיעה המעודכנת
        updated_trip = db.trips.find_one({'_id': trip_id})
        if not updated_trip:
            logger.error(f"Could not fetch updated trip {trip_id}")
            return jsonify({"status": "error", "message": "שגיאה בשליפת הנסיעה המעודכנת"}), 500
            
        # שליפת פרטי הנהג
        driver = db.users.find_one({'_id': updated_trip['user_id']})
        
        # הכנת אובייקט התגובה
        response_trip = {
            '_id': str(updated_trip['_id']),
            'user_id': str(updated_trip['user_id']),
            'vehicle': updated_trip['vehicle'],
            'date_time': updated_trip['date_time'],
            'purpose': updated_trip['purpose'],
            'destination': updated_trip.get('destination', ''),
            'status': updated_trip['status'],
            'rejection_reason': updated_trip.get('rejection_reason', ''),
            'created_at': updated_trip.get('created_at', '').isoformat() if updated_trip.get('created_at') else '',
            'driver_name': driver['full_name'] if driver else 'לא ידוע'
        }
        
        logger.info(f"Successfully rescheduled trip {trip_id} to {data['new_date_time']}")
        return jsonify({
            "status": "success",
            "message": "מועד הנסיעה עודכן בהצלחה",
            "trip": response_trip
        })
        
    except Exception as e:
        logger.error(f"Error in reschedule_trip: {str(e)}")
        return jsonify({
            "status": "error", 
            "message": f"שגיאה בעדכון מועד הנסיעה: {str(e)}"
        }), 500

if __name__ == '__main__':
    app.run(debug=False)  # שינוי ל-False בסביבת ייצור
