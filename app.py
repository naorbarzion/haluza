from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
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
                'full_name': 'הנהלת מוסדות אסף',
                'role': 'admin'
            },
            {
                'username': 'admin2',
                'password': generate_password_hash('1234'),
                'full_name': 'הנהלת מוסדות שירי',
                'role': 'admin'
            }
        ]
        
        # הוספת משתמשי מנהל
        result = db.users.insert_many(admin_users)
        logger.info(f"Added {len(result.inserted_ids)} admin users")
        
        # משתמשי נהגים
        drivers = [
            {'username': 'moriel', 'password': generate_password_hash('3278'), 'full_name': 'חלוצית 4 - מוריאל', 'role': 'driver'},
            {'username': 'doron', 'password': generate_password_hash('4521'), 'full_name': 'תלמוד תורה - דורון ותקין', 'role': 'driver'},
            {'username': 'haravneria', 'password': generate_password_hash('8394'), 'full_name': 'תלמוד תורה - הרב נריה', 'role': 'driver'},
            {'username': 'israel', 'password': generate_password_hash('6710'), 'full_name': 'תיכונית - ישראל רובינשטיין', 'role': 'driver'},
            {'username': 'elad', 'password': generate_password_hash('5924'), 'full_name': 'תיכונית - אלעד בסטיקר', 'role': 'driver'},
            {'username': 'haravasaf', 'password': generate_password_hash('3187'), 'full_name': 'תיכונית - הרב אסף נאומבורג', 'role': 'driver'},
            {'username': 'natanel', 'password': generate_password_hash('4209'), 'full_name': 'חלוצי דרור - נתנאל שכטר', 'role': 'driver'},
            {'username': 'anat', 'password': generate_password_hash('7536'), 'full_name': 'אולפנא - ענת', 'role': 'driver'},
            {'username': 'yosef', 'password': generate_password_hash('9841'), 'full_name': 'אולפנא - יוסף', 'role': 'driver'},
            {'username': 'haravyossi', 'password': generate_password_hash('2648'), 'full_name': 'ישיבה קטנה - הרב יוסי וייסברג', 'role': 'driver'},
            {'username': 'barak', 'password': generate_password_hash('8307'), 'full_name': 'ישיבה גבוהה - ברק שיטרית', 'role': 'driver'},
            {'username': 'shimon', 'password': generate_password_hash('6752'), 'full_name': 'מטבח - שמעון ג\'רבי', 'role': 'driver'},
            {'username': 'orly', 'password': generate_password_hash('9435'), 'full_name': 'בית ספר לבנות - אורלי', 'role': 'driver'},
            {'username': 'tamiravichai', 'password': generate_password_hash('5076'), 'full_name': 'תחזוקה - תמיר או אביחי', 'role': 'driver'}
        ]
        
        # הוספת משתמשי נהגים
        result = db.users.insert_many(drivers)
        logger.info(f"Added {len(result.inserted_ids)} driver users")
        
        # יצירת נסיעה לדוגמה
        example_driver = db.users.find_one({'username': 'moriel'})
        if example_driver:
            example_trip = {
                'user_id': example_driver['_id'],
                'vehicle': 'car1',
                'start_time': datetime.utcnow().isoformat(),
                'end_time': (datetime.utcnow() + timedelta(hours=2)).isoformat(),
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
            'start_time': data['start_time'],
            'end_time': data['end_time'],
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
            'start_time': trip['start_time'],
            'end_time': trip['end_time'],
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
    if session.get('role') != 'driver':
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
        
    try:
        # מיון לפי סטטוס (pending ראשון) ואז לפי תאריך
        pipeline = [
            {
                '$match': {
                    'user_id': ObjectId(session['user_id'])
                }
            },
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
                    'start_time': -1
                }
            }
        ]
        
        trips = list(db.trips.aggregate(pipeline))
        
        # המרת ObjectId למחרוזת
        for trip in trips:
            trip['_id'] = str(trip['_id'])
            trip['user_id'] = str(trip['user_id'])
            if 'admin_id' in trip:
                trip['admin_id'] = str(trip['admin_id'])
            # הסרת שדה עזר
            trip.pop('statusOrder', None)
            # המרת תאריכים למחרוזות
            if 'created_at' in trip and isinstance(trip['created_at'], datetime):
                trip['created_at'] = trip['created_at'].isoformat()
            if 'start_time' in trip and isinstance(trip['start_time'], datetime):
                trip['start_time'] = trip['start_time'].isoformat()
            if 'end_time' in trip and isinstance(trip['end_time'], datetime):
                trip['end_time'] = trip['end_time'].isoformat()
        
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
            query['start_time'] = {'$gte': data['date_from']}
        
        if data.get('date_to'):
            if 'start_time' in query:
                query['start_time']['$lte'] = data['date_to']
            else:
                query['start_time'] = {'$lte': data['date_to']}
        
        if data.get('driver_id'):
            query['user_id'] = ObjectId(data['driver_id'])
        
        if data.get('status'):
            query['status'] = data['status']
        
        trips = list(db.trips.find(query).sort('start_time', -1))
        
        # המרת ObjectId ל-string
        for trip in trips:
            trip['_id'] = str(trip['_id'])
            trip['user_id'] = str(trip['user_id'])
            if 'admin_id' in trip:
                trip['admin_id'] = str(trip['admin_id'])
            # הוספת שם הנהג
            driver = db.users.find_one({'_id': ObjectId(trip['user_id'])})
            trip['driver_name'] = driver['full_name'] if driver else 'לא ידוע'
            # המרת תאריכים למחרוזות
            if 'created_at' in trip and isinstance(trip['created_at'], datetime):
                trip['created_at'] = trip['created_at'].isoformat()
        
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
            query['start_time'] = {'$gte': data['date_from']}
        
        if data.get('date_to'):
            if 'start_time' in query:
                query['start_time']['$lte'] = data['date_to']
            else:
                query['start_time'] = {'$lte': data['date_to']}
        
        if data.get('driver_id'):
            query['user_id'] = ObjectId(data['driver_id'])
        
        if data.get('status'):
            query['status'] = data['status']
        
        trips = list(db.trips.find(query).sort('start_time', -1))
        
        # הכנת הנתונים לאקסל
        excel_data = []
        for trip in trips:
            driver = db.users.find_one({'_id': trip['user_id']})
            excel_data.append({
                'תאריך ושעת התחלה': trip['start_time'],
                'תאריך ושעת סיום': trip['end_time'],
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
            'car1': 'יונדאי איוניק - 53836402',
            'car2': 'טויוטה סיטי - 15093804',
            'car3': 'מרצדס בנץ - 19826603'
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
                    'start_time': -1
                }
            }
        ]
        
        trips = list(db.trips.aggregate(pipeline))
        
        # המרת ObjectId למחרוזת והוספת שם הנהג
        for trip in trips:
            trip['_id'] = str(trip['_id'])
            trip['user_id'] = str(trip['user_id'])
            if 'admin_id' in trip:
                trip['admin_id'] = str(trip['admin_id'])
            driver = db.users.find_one({'_id': ObjectId(trip['user_id'])})
            trip['driver_name'] = driver['full_name'] if driver else 'לא ידוע'
            # הסרת שדה עזר
            trip.pop('statusOrder', None)
            # המרת תאריכים למחרוזות
            if 'created_at' in trip and isinstance(trip['created_at'], datetime):
                trip['created_at'] = trip['created_at'].isoformat()
            if 'start_time' in trip and isinstance(trip['start_time'], datetime):
                trip['start_time'] = trip['start_time'].isoformat()
            if 'end_time' in trip and isinstance(trip['end_time'], datetime):
                trip['end_time'] = trip['end_time'].isoformat()
        
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
        trip_id = data.get('trip_id')
        if not trip_id:
            return jsonify({"status": "error", "message": "לא התקבל מזהה נסיעה"}), 400
            
        # בדיקת תקינות התאריכים החדשים
        if not data.get('new_start_time') or not data.get('new_end_time'):
            return jsonify({"status": "error", "message": "לא התקבלו תאריכי התחלה וסיום חדשים"}), 400
        
        # עדכון הנסיעה
        result = db.trips.update_one(
            {'_id': ObjectId(trip_id)},
            {
                '$set': {
                    'start_time': data['new_start_time'],
                    'end_time': data['new_end_time'],
                    'updated_at': datetime.utcnow(),
                    'updated_by': ObjectId(session['user_id'])
                }
            }
        )
        
        if result.modified_count == 0:
            return jsonify({"status": "error", "message": "הנסיעה לא נמצאה או לא עודכנה"}), 404
        
        # שליפת הנסיעה המעודכנת
        trip = db.trips.find_one({'_id': ObjectId(trip_id)})
        if not trip:
            return jsonify({"status": "error", "message": "הנסיעה לא נמצאה"}), 404
            
        # הכנת אובייקט התגובה
        response_trip = {
            '_id': str(trip['_id']),
            'user_id': str(trip['user_id']),
            'vehicle': trip['vehicle'],
            'start_time': trip['start_time'],
            'end_time': trip['end_time'],
            'purpose': trip['purpose'],
            'destination': trip['destination'],
            'status': trip['status']
        }
        
        if 'created_at' in trip:
            response_trip['created_at'] = trip['created_at'].isoformat()
        if 'updated_at' in trip:
            response_trip['updated_at'] = trip['updated_at'].isoformat()
            
        # הוספת שם הנהג
        driver = db.users.find_one({'_id': trip['user_id']})
        response_trip['driver_name'] = driver['full_name'] if driver else 'לא ידוע'
        
        logger.info(f"Successfully rescheduled trip {trip_id}")
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

@app.route('/admin/add_trip', methods=['POST'])
@login_required
@admin_required
def admin_add_trip():
    try:
        data = request.json
        logger.info(f"Admin adding trip with data: {data}")
        
        # בדיקת תקינות הנתונים
        required_fields = ['driver_id', 'vehicle', 'start_time', 'end_time', 'purpose', 'destination']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    "status": "error",
                    "message": f"שדה חובה חסר: {field}"
                }), 400

        # המרת מזהה הנהג ל-ObjectId
        try:
            driver_id = ObjectId(data['driver_id'])
        except Exception as e:
            logger.error(f"Invalid driver_id format: {e}")
            return jsonify({"status": "error", "message": "מזהה נהג לא תקין"}), 400

        # בדיקה שהנהג קיים
        driver = db.users.find_one({'_id': driver_id, 'role': 'driver'})
        if not driver:
            return jsonify({"status": "error", "message": "הנהג לא נמצא"}), 404

        # יצירת הנסיעה
        trip = {
            'user_id': driver_id,
            'vehicle': data['vehicle'],
            'start_time': data['start_time'],
            'end_time': data['end_time'],
            'purpose': data['purpose'],
            'destination': data['destination'],
            'status': 'approved',  # נסיעות שהאדמין מוסיף מאושרות אוטומטית
            'created_at': datetime.utcnow(),
            'added_by_admin': True,  # סימון שהנסיעה נוספה על ידי אדמין
            'admin_id': ObjectId(session['user_id'])  # שמירת מזהה האדמין שהוסיף
        }

        result = db.trips.insert_one(trip)
        
        # הכנת אובייקט התגובה
        response_trip = {
            '_id': str(result.inserted_id),
            'user_id': str(trip['user_id']),
            'vehicle': trip['vehicle'],
            'start_time': trip['start_time'],
            'end_time': trip['end_time'],
            'purpose': trip['purpose'],
            'destination': trip['destination'],
            'status': trip['status'],
            'created_at': trip['created_at'].isoformat(),
            'driver_name': driver['full_name']
        }
        
        logger.info(f"Successfully added trip for driver {driver['full_name']}")
        return jsonify({
            "status": "success",
            "message": "הנסיעה נוספה בהצלחה",
            "trip": response_trip
        })
        
    except Exception as e:
        logger.error(f"Error in admin_add_trip: {str(e)}")
        return jsonify({
            "status": "error", 
            "message": f"שגיאה בהוספת הנסיעה: {str(e)}"
        }), 500

@app.route('/admin/reject_trip', methods=['POST'])
@login_required
@admin_required
def reject_trip():
    try:
        data = request.json
        trip_id = data.get('trip_id')
        rejection_reason = data.get('rejection_reason')
        
        if not trip_id:
            return jsonify({"status": "error", "message": "לא התקבל מזהה נסיעה"}), 400
            
        if not rejection_reason:
            return jsonify({"status": "error", "message": "חובה לציין סיבת דחייה"}), 400
        
        # עדכון הנסיעה
        result = db.trips.update_one(
            {'_id': ObjectId(trip_id)},
            {
                '$set': {
                    'status': 'rejected',
                    'rejection_reason': rejection_reason,
                    'updated_at': datetime.utcnow(),
                    'updated_by': ObjectId(session['user_id'])
                }
            }
        )
        
        if result.modified_count == 0:
            return jsonify({"status": "error", "message": "הנסיעה לא נמצאה או לא עודכנה"}), 404
        
        # שליפת הנסיעה המעודכנת
        trip = db.trips.find_one({'_id': ObjectId(trip_id)})
        if not trip:
            return jsonify({"status": "error", "message": "הנסיעה לא נמצאה"}), 404
            
        # הכנת אובייקט התגובה
        response_trip = {
            '_id': str(trip['_id']),
            'user_id': str(trip['user_id']),
            'vehicle': trip['vehicle'],
            'start_time': trip['start_time'],
            'end_time': trip['end_time'],
            'purpose': trip['purpose'],
            'destination': trip['destination'],
            'status': trip['status'],
            'rejection_reason': trip['rejection_reason']
        }
        
        if 'created_at' in trip:
            response_trip['created_at'] = trip['created_at'].isoformat()
        if 'updated_at' in trip:
            response_trip['updated_at'] = trip['updated_at'].isoformat()
            
        # הוספת שם הנהג
        driver = db.users.find_one({'_id': trip['user_id']})
        response_trip['driver_name'] = driver['full_name'] if driver else 'לא ידוע'
        
        logger.info(f"Successfully rejected trip {trip_id}")
        return jsonify({
            "status": "success",
            "message": "הנסיעה נדחתה בהצלחה",
            "trip": response_trip
        })
        
    except Exception as e:
        logger.error(f"Error in reject_trip: {str(e)}")
        return jsonify({
            "status": "error", 
            "message": f"שגיאה בדחיית הנסיעה: {str(e)}"
        }), 500

@app.route('/admin/approve_trip', methods=['POST'])
@login_required
@admin_required
def approve_trip():
    try:
        data = request.json
        trip_id = data.get('trip_id')
        
        if not trip_id:
            return jsonify({"status": "error", "message": "לא התקבל מזהה נסיעה"}), 400
        
        # עדכון הנסיעה
        result = db.trips.update_one(
            {'_id': ObjectId(trip_id)},
            {
                '$set': {
                    'status': 'approved',
                    'updated_at': datetime.utcnow(),
                    'updated_by': ObjectId(session['user_id'])
                }
            }
        )
        
        if result.modified_count == 0:
            return jsonify({"status": "error", "message": "הנסיעה לא נמצאה או לא עודכנה"}), 404
        
        # שליפת הנסיעה המעודכנת
        trip = db.trips.find_one({'_id': ObjectId(trip_id)})
        if not trip:
            return jsonify({"status": "error", "message": "הנסיעה לא נמצאה"}), 404
            
        # הכנת אובייקט התגובה
        response_trip = {
            '_id': str(trip['_id']),
            'user_id': str(trip['user_id']),
            'vehicle': trip['vehicle'],
            'start_time': trip['start_time'],
            'end_time': trip['end_time'],
            'purpose': trip['purpose'],
            'destination': trip['destination'],
            'status': trip['status']
        }
        
        if 'created_at' in trip:
            response_trip['created_at'] = trip['created_at'].isoformat()
        if 'updated_at' in trip:
            response_trip['updated_at'] = trip['updated_at'].isoformat()
            
        # הוספת שם הנהג
        driver = db.users.find_one({'_id': trip['user_id']})
        response_trip['driver_name'] = driver['full_name'] if driver else 'לא ידוע'
        
        logger.info(f"Successfully approved trip {trip_id}")
        return jsonify({
            "status": "success",
            "message": "הנסיעה אושרה בהצלחה",
            "trip": response_trip
        })
        
    except Exception as e:
        logger.error(f"Error in approve_trip: {str(e)}")
        return jsonify({
            "status": "error", 
            "message": f"שגיאה באישור הנסיעה: {str(e)}"
        }), 500

if __name__ == '__main__':
    app.run(debug=False)  # שינוי ל-False בסביבת ייצור
