from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import sqlite3
from functools import wraps
import os
import pandas as pd
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # יש להחליף במפתח אמיתי בפרודקשן

def init_db():
    # יצירת תיקיית database אם היא לא קיימת
    os.makedirs('database', exist_ok=True)
    
    conn = sqlite3.connect('database/trips.db')
    c = conn.cursor()
    
def init_db():
    # יצירת תיקיית database אם היא לא קיימת
    os.makedirs('database', exist_ok=True)
    
    conn = sqlite3.connect('database/trips.db')
    c = conn.cursor()
    
    # טבלת משתמשים
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    
    # טבלת נסיעות
    c.execute('''
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            vehicle TEXT NOT NULL,
            date_time DATETIME NOT NULL,
            purpose TEXT NOT NULL,
            destination TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            rejection_reason TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # משתמשי מנהל
    admin_users = [
        ('admin', 'admin', 'מנהל ראשי', 'admin'),      # admin/admin
        ('admin2', '1234', 'מנהל משנה', 'admin')       # admin2/1234
    ]
    
    for username, password, full_name, role in admin_users:
        try:
            c.execute('''
                INSERT OR IGNORE INTO users (username, password, full_name, role)
                VALUES (?, ?, ?, ?)
            ''', (username, generate_password_hash(password), full_name, role))
        except sqlite3.IntegrityError:
            print(f"User {username} already exists")
    
    # משתמשי נהגים
    drivers = [
        ('driver1', 'משה כהן'),
        ('driver2', 'יוסי לוי'),
        ('driver3', 'דוד כהן'),
        ('driver4', 'יעקב אברהם'),
        ('driver5', 'דניאל דוד'),
        ('driver6', 'אברהם יצחק'),
        ('driver7', 'יצחק משה'),
        ('driver8', 'שמואל שלום'),
        ('driver9', 'אהרון הכהן'),
        ('driver10', 'מאיר דוד'),
        ('driver11', 'חיים כהן'),
        ('driver12', 'יונתן לוי'),
        ('driver13', 'אליהו הנביא'),
        ('driver14', 'שלמה המלך'),
        ('driver15', 'דן הגיבור'),
        ('driver16', 'גד החוזה')
    ]
    
    for username, full_name in drivers:
        try:
            c.execute('''
                INSERT OR IGNORE INTO users (username, password, full_name, role)
                VALUES (?, ?, ?, ?)
            ''', (username, generate_password_hash('1234'), full_name, 'driver'))
        except sqlite3.IntegrityError:
            print(f"User {username} already exists")

    conn.commit()
    conn.close()

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

def get_greeting(hour):
    if 5 <= hour < 12:
        return "בוקר טוב"
    elif 12 <= hour < 18:
        return "צהריים טובים"
    elif 18 <= hour < 22:
        return "ערב טוב"
    else:
        return "לילה טוב"

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('driver_dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('database/trips.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['full_name'] = user[3]
            session['role'] = user[4]
            
            if user[4] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('driver_dashboard'))
        
        return render_template('login.html', error='שם משתמש או סיסמה שגויים')
    
    return render_template('login.html')

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

# ניתובי דוחות
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
        conn = sqlite3.connect('database/trips.db')
        c = conn.cursor()
        
        c.execute('''
            SELECT id, full_name 
            FROM users 
            WHERE role = 'driver'
            ORDER BY full_name
        ''')
        
        drivers = [{'id': row[0], 'full_name': row[1]} for row in c.fetchall()]
        conn.close()
        return jsonify(drivers)
        
    except Exception as e:
        print(f"Error getting drivers: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/admin/search_trips', methods=['POST'])
@login_required
@admin_required
def search_trips():
    try:
        data = request.json
        conn = sqlite3.connect('database/trips.db')
        c = conn.cursor()
        
        query = '''
            SELECT 
                t.id,
                t.user_id,
                t.vehicle,
                t.date_time,
                t.purpose,
                t.destination,
                t.status,
                t.created_at,
                u.full_name as driver_name
            FROM trips t
            JOIN users u ON t.user_id = u.id
            WHERE 1=1
        '''
        params = []

        if data.get('date_from'):
            query += ' AND DATE(t.date_time) >= DATE(?)'
            params.append(data['date_from'])
        
        if data.get('date_to'):
            query += ' AND DATE(t.date_time) <= DATE(?)'
            params.append(data['date_to'])
        
        if data.get('driver_id'):
            query += ' AND t.user_id = ?'
            params.append(data['driver_id'])
        
        if data.get('status'):
            query += ' AND t.status = ?'
            params.append(data['status'])
        
        query += ' ORDER BY t.date_time DESC'
        
        c.execute(query, params)
        
        trips = [{
            'id': row[0],
            'user_id': row[1],
            'vehicle': row[2],
            'date_time': row[3],
            'purpose': row[4],
            'destination': row[5],
            'status': row[6],
            'created_at': row[7],
            'driver_name': row[8]
        } for row in c.fetchall()]
        
        conn.close()
        return jsonify(trips)
        
    except Exception as e:
        print(f"Error searching trips: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/admin/export_trips', methods=['POST'])
@login_required
@admin_required
def export_trips():
    try:
        data = request.json
        conn = sqlite3.connect('database/trips.db')
        
        query = '''
            SELECT 
                t.date_time as 'תאריך ושעה',
                u.full_name as 'שם הנהג',
                t.vehicle as 'רכב',
                t.purpose as 'מטרת נסיעה',
                t.destination as 'יעד',
                t.status as 'סטטוס',
                t.created_at as 'תאריך יצירה'
            FROM trips t
            JOIN users u ON t.user_id = u.id
            WHERE 1=1
        '''
        params = []

        if data.get('date_from'):
            query += ' AND DATE(t.date_time) >= DATE(?)'
            params.append(data['date_from'])
        
        if data.get('date_to'):
            query += ' AND DATE(t.date_time) <= DATE(?)'
            params.append(data['date_to'])
        
        if data.get('driver_id'):
            query += ' AND t.user_id = ?'
            params.append(data['driver_id'])
        
        if data.get('status'):
            query += ' AND t.status = ?'
            params.append(data['status'])
        
        query += ' ORDER BY t.date_time DESC'
        
        df = pd.read_sql_query(query, conn, params=params)
        
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
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='דוח נסיעות')
            worksheet = writer.sheets['דוח נסיעות']
            
            for idx, col in enumerate(df.columns):
                max_length = max(df[col].astype(str).apply(len).max(), len(col)) + 2
                worksheet.set_column(idx, idx, max_length)
        
        output.seek(0)
        conn.close()
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'דוח_נסיעות_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
        )
        
    except Exception as e:
        print(f"Error exporting trips: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/driver/submit_trip', methods=['POST'])
@login_required
def submit_trip():
    if session.get('role') != 'driver':
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
        
    try:
        data = request.form
        conn = sqlite3.connect('database/trips.db')
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO trips (user_id, vehicle, date_time, purpose, destination, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        ''', (
            session['user_id'],
            data['vehicle'],
            data['date_time'],
            data['purpose'],
            data['destination']
        ))
        
        trip_id = c.lastrowid
        conn.commit()
        
        c.execute('''
            SELECT 
                t.id,
                t.user_id,
                t.vehicle,
                t.date_time,
                t.purpose,
                t.status,
                t.rejection_reason,
                t.created_at,
                u.full_name
            FROM trips t
            JOIN users u ON t.user_id = u.id
            WHERE t.id = ?
        ''', (trip_id,))
        
        new_trip = c.fetchone()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "הנסיעה נוספה בהצלחה",
            "trip": {
                "id": new_trip[0],
                "user_id": new_trip[1],
                "vehicle": new_trip[2],
                "date_time": new_trip[3],
                "purpose": new_trip[4],
                "status": new_trip[5],
                "rejection_reason": new_trip[6],
                "created_at": new_trip[7],
                "driver_name": new_trip[8]
            }
        })
        
    except Exception as e:
        print(f"Error in submit_trip: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/admin/get_trips')
@login_required
@admin_required
def admin_get_trips():
    try:
        conn = sqlite3.connect('database/trips.db')
        c = conn.cursor()
        
        c.execute('''
            SELECT 
                t.id,
                t.user_id,
                t.vehicle,
                t.date_time,
                t.purpose,
                t.status,
                t.rejection_reason,
                t.created_at,
                u.full_name
            FROM trips t
            JOIN users u ON t.user_id = u.id
            ORDER BY 
                CASE t.status 
                    WHEN 'pending' THEN 1 
                    WHEN 'approved' THEN 2
                    ELSE 3 
                END,
                t.date_time DESC
        ''')
        
        trips = [{
            'id': row[0],
            'user_id': row[1],
            'vehicle': row[2],
            'date_time': row[3],
            'purpose': row[4],
            'status': row[5],
            'rejection_reason': row[6],
            'created_at': row[7],
            'driver_name': row[8]
        } for row in c.fetchall()]
        
        conn.close()
        return jsonify(trips)
        
    except Exception as e:
        print(f"Error in admin_get_trips: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/driver/get_trips')
@login_required
def driver_get_trips():
    try:
        conn = sqlite3.connect('database/trips.db')
        c = conn.cursor()
        
        c.execute('''
            SELECT 
                t.id,
                t.user_id,
                t.vehicle,
                t.date_time,
                t.purpose,
                t.status,
                t.rejection_reason,
                t.created_at,
                u.full_name
            FROM trips t
            JOIN users u ON t.user_id = u.id
            WHERE t.user_id = ?
            ORDER BY t.created_at DESC
        ''', (session['user_id'],))
        
        trips = [{
            'id': row[0],
            'user_id': row[1],
            'vehicle': row[2],
            'date_time': row[3],
            'purpose': row[4],
            'status': row[5],
            'rejection_reason': row[6],
            'created_at': row[7],
            'driver_name': row[8]
        } for row in c.fetchall()]
        
        conn.close()
        return jsonify(trips)
        
    except Exception as e:
        print(f"Error in driver_get_trips: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/admin/update_trip_status', methods=['POST'])
@login_required
@admin_required
def update_trip_status():
    try:
        data = request.json
        conn = sqlite3.connect('database/trips.db')
        c = conn.cursor()
        
        c.execute('''
            UPDATE trips 
            SET status = ?, 
                rejection_reason = ?
            WHERE id = ?
        ''', (
            data['status'],
            data.get('rejection_reason'),
            data['trip_id']
        ))
        
        conn.commit()
        
        c.execute('''
            SELECT 
                t.id,
                t.user_id,
                t.vehicle,
                t.date_time,
                t.purpose,
                t.status,
                t.rejection_reason,
                t.created_at,
                u.full_name
            FROM trips t
            JOIN users u ON t.user_id = u.id
            WHERE t.id = ?
        ''', (data['trip_id'],))
        
        updated_trip = c.fetchone()
        conn.close()
        
        return jsonify({
            "status": "success",
            "trip": {
                "id": updated_trip[0],
                "user_id": updated_trip[1],
                "vehicle": updated_trip[2],
                "date_time": updated_trip[3],
                "purpose": updated_trip[4],
                "status": updated_trip[5],
                "rejection_reason": updated_trip[6],
                "created_at": updated_trip[7],
                "driver_name": updated_trip[8]
            }
        })
        
    except Exception as e:
        print(f"Error in update_trip_status: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/admin/reschedule_trip', methods=['POST'])
@login_required
@admin_required
def reschedule_trip():
   try:
       data = request.json
       conn = sqlite3.connect('database/trips.db')
       c = conn.cursor()
       
       c.execute('''
           UPDATE trips 
           SET date_time = ?
           WHERE id = ?
       ''', (
           data['new_date_time'],
           data['trip_id']
       ))
       
       conn.commit()
       
       c.execute('''
           SELECT 
               t.id,
               t.user_id,
               t.vehicle,
               t.date_time,
               t.purpose,
               t.status,
               t.rejection_reason,
               t.created_at,
               u.full_name
           FROM trips t
           JOIN users u ON t.user_id = u.id
           WHERE t.id = ?
       ''', (data['trip_id'],))
       
       updated_trip = c.fetchone()
       conn.close()
       
       return jsonify({
           "status": "success",
           "trip": {
               "id": updated_trip[0],
               "user_id": updated_trip[1],
               "vehicle": updated_trip[2],
               "date_time": updated_trip[3],
               "purpose": updated_trip[4],
               "status": updated_trip[5],
               "rejection_reason": updated_trip[6],
               "created_at": updated_trip[7],
               "driver_name": updated_trip[8]
           }
       })
       
   except Exception as e:
       print(f"Error in reschedule_trip: {str(e)}")
       return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True)