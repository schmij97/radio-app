#!/usr/bin/env python3
# main.py - Password-protected SiriusXM App for Render deployment with Database Storage

import sys
import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import requests
import time
import uuid
import json
import urllib.parse
import threading
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from functools import wraps
import traceback

# Try to import PostgreSQL library, fallback gracefully if not available
try:
    import psycopg
    POSTGRESQL_AVAILABLE = True
    print("✅ PostgreSQL library loaded successfully")
except ImportError:
    POSTGRESQL_AVAILABLE = False
    print("❌ PostgreSQL library not available, using SQLite fallback")

# Configure Flask app
app = Flask(__name__)

# IMPORTANT: Change these before deploying!
app.config['SECRET_KEY'] = 'unique-key'

# User credentials
USERS = {
    'DaveHall': {'password': 'schmij', 'role': 'admin'},
    'ShelbyHank': {'password': 'schmij', 'role': 'operator'}
}

# Session settings
SESSION_TIMEOUT = 3600  # 1 hour in seconds

# File storage (Render will handle this)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RADIO_IDS_FILE = os.path.join(BASE_DIR, 'radio_ids.json')  # Keep for migration purposes
DATABASE_FILE = os.path.join(BASE_DIR, 'radio_data.db')

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL')  # Render provides this automatically

# Global variables for status tracking
activation_status = {"progress": 0, "status": "Ready", "completed": False, "success": False}

def login_required(f):
    """Decorator to require login for protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        
        # Check session timeout
        if time.time() - session.get('login_time', 0) > SESSION_TIMEOUT:
            session.clear()
            flash('Session expired. Please log in again.', 'warning')
            return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    """Home page - redirect based on login status"""
    if session.get('authenticated'):
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in USERS and USERS[username]['password'] == password:
            session['authenticated'] = True
            session['user'] = username
            session['role'] = USERS[username]['role']
            session['login_time'] = time.time()
            flash('Successfully logged in!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Database Functions with PostgreSQL/SQLite support

@contextmanager
def get_db_connection():
    """Context manager for SQLite database connections"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
    finally:
        conn.close()

def get_default_radios():
    """Get the default radio list"""
    return [
        ("🆕 Custom Entry", "CUSTOM"),
        ("Acura", "5XVVWA06"),
        ("Truck", "Q2EV928P"),
        ("Jaguar", "BTGBM48Y"),
        ("Trev's car", "055515329200"),
        ("Trev's Yukon", "6M2K32RP"),
        ("Bob's truck", "H8NWC389"),
        ("Bob's traverse", "8RCEM20P"),
        ("Rogers truck", "KUGVK086"),
        ("Windys yukon", "9092Z24W"),
        ("Stef's car", "ZJHA8101"),
        ("JT", "073617581556"),
        ("Faddy's truck", "568CC38K"),
        ("Faddys dads truck", "053139310355"),
        ("Julie McFadden", "03MTAD4X"),
        ("Frank's dodge", "76N1BACG"),
        ("Wenzels oldie", "Y75T528N"),
        ("Wenzel desk top", "UJGZ2QWW"),
        ("Chris Anderson", "057220240031"),
        ("Craig King Ranch", "032768368075"),
        ("Dave Hall", "YDMJLEWU"),
        ("Terras SUV", "HL3MB30"),
        ("Stacey truck", "4UPA5D0A"),
        ("Kitchen radio", "044528325001"),
        ("Hanks radio", "039475329911"),
        ("Shelby's radio", "031458220386"),
        ("Adam", "87BZ62HD"),
        ("McFadden Audi", "067145879367"),
        ("Gord TRAVERSE", "0KGNV3HT"),
        ("Gord Truck", "041592909611"),
        ("Gords Truck #2", "00180002"),
        ("Tbag", "MWBKU3M2"),
        ("Tbag Daughter", "067177368177"),
        ("Steranko", "081690989621"),
        ("Micah", "0KT19AWL"),
        ("Kaden", "L5E5A4WK"),
        ("Braley", "ZNYMKEMQ"),
        ("Listy #1", "CNJ1T3WZ"),
        ("Carmen truck", "THGUDA05"),
        ("Carmen Van", "079315292567"),
        ("Kurt Baker", "ZX81P2R6"),
        ("Deuchsher", "XMUPRE4G"),
        ("Dustin M #1", "H55EU0R5"),
        ("Dustin M #2", "AC0KG0CE"),
        ("Brent", "0PBPB3R3"),
        ("Baba's", "GXABAE0Z"),
        ("Jeanie's Acura MDX", "GMGRPEMG"),
        ("Listy #2", "A6E9QEH6"),
        ("Chris Okoloise", "LD6E02H4")
    ]

def init_database_safe():
    """Initialize database with safe PostgreSQL/SQLite handling"""
    try:
        if DATABASE_URL and POSTGRESQL_AVAILABLE:
            # PostgreSQL setup
            print("🔧 Setting up PostgreSQL database...")
            with psycopg.connect(DATABASE_URL) as conn:
                with conn.cursor() as cursor:
                    # Create table with PostgreSQL syntax
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS radio_ids (
                            id SERIAL PRIMARY KEY,
                            name TEXT NOT NULL,
                            radio_id TEXT UNIQUE NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            is_default BOOLEAN DEFAULT FALSE
                        )
                    ''')
                    
                    # Check if we need to populate default data
                    cursor.execute('SELECT COUNT(*) FROM radio_ids')
                    count = cursor.fetchone()[0]
                    
                    if count == 0:
                        # Insert default radios
                        default_radios = get_default_radios()
                        
                        for name, radio_id in default_radios:
                            is_default = radio_id != "CUSTOM"
                            cursor.execute('''
                                INSERT INTO radio_ids (name, radio_id, is_default) 
                                VALUES (%s, %s, %s)
                                ON CONFLICT (radio_id) DO NOTHING
                            ''', (name, radio_id, is_default))
                        
                        conn.commit()
                        print(f"✅ PostgreSQL initialized with {len(default_radios)} default radio IDs")
                    else:
                        print(f"📊 PostgreSQL already has {count} radio IDs")
        else:
            # Fallback to SQLite
            print("🔧 Setting up SQLite database...")
            init_database_sqlite()
            
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        print("🔄 Using SQLite fallback")
        init_database_sqlite()

def init_database_sqlite():
    """Initialize SQLite database"""
    with get_db_connection() as conn:
        # Create the radio_ids table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS radio_ids (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                radio_id TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_default BOOLEAN DEFAULT 0
            )
        ''')
        
        # Check if we need to populate default data
        cursor = conn.execute('SELECT COUNT(*) FROM radio_ids')
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Insert all your default radio IDs
            default_radios = get_default_radios()
            
            # Insert default radios with is_default=1
            for name, radio_id in default_radios:
                conn.execute('''
                    INSERT OR IGNORE INTO radio_ids (name, radio_id, is_default) 
                    VALUES (?, ?, ?)
                ''', (name, radio_id, 1 if radio_id != "CUSTOM" else 0))
            
            conn.commit()
            print(f"✅ SQLite initialized with {len(default_radios)} default radio IDs")

def load_radio_ids():
    """Load radio IDs with safe PostgreSQL/SQLite handling"""
    try:
        if DATABASE_URL and POSTGRESQL_AVAILABLE:
            # PostgreSQL query
            with psycopg.connect(DATABASE_URL) as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        SELECT name, radio_id 
                        FROM radio_ids 
                        ORDER BY 
                            CASE WHEN radio_id = 'CUSTOM' THEN 0 ELSE 1 END,
                            name
                    ''')
                    
                    radios = cursor.fetchall()
                    print(f"📊 Loaded {len(radios)} radios from PostgreSQL")
                    return radios
                    
        else:
            # Fallback to SQLite
            return load_radio_ids_sqlite()
            
    except Exception as e:
        print(f"❌ PostgreSQL load error: {e}")
        print("🔄 Using SQLite fallback")
        return load_radio_ids_sqlite()

def load_radio_ids_sqlite():
    """SQLite version of load_radio_ids"""
    try:
        with get_db_connection() as conn:
            cursor = conn.execute('''
                SELECT name, radio_id 
                FROM radio_ids 
                ORDER BY 
                    CASE WHEN radio_id = 'CUSTOM' THEN 0 ELSE 1 END,
                    name
            ''')
            radios = cursor.fetchall()
            return [(row['name'], row['radio_id']) for row in radios]
    except Exception as e:
        print(f"❌ SQLite load error: {e}")
        # Return defaults if everything fails
        return get_default_radios()

def add_radio_to_db(name, radio_id):
    """Add radio with enhanced debugging"""
    print(f"🔍 DEBUG: Starting add_radio_to_db for {name} - {radio_id}")
    print(f"🔍 DEBUG: DATABASE_URL present: {DATABASE_URL is not None}")
    print(f"🔍 DEBUG: POSTGRESQL_AVAILABLE: {POSTGRESQL_AVAILABLE}")
    
    try:
        if DATABASE_URL and POSTGRESQL_AVAILABLE:
            print(f"🔍 DEBUG: Attempting PostgreSQL insert...")
            # PostgreSQL insert
            with psycopg.connect(DATABASE_URL) as conn:
                print(f"🔍 DEBUG: PostgreSQL connection established")
                with conn.cursor() as cursor:
                    print(f"🔍 DEBUG: Checking for duplicates...")
                    # Check for duplicates
                    cursor.execute('SELECT name FROM radio_ids WHERE radio_id = %s', (radio_id,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        print(f"🔍 DEBUG: Duplicate found: {existing[0]}")
                        raise ValueError(f"Radio ID '{radio_id}' already exists for '{existing[0]}'")
                    
                    print(f"🔍 DEBUG: No duplicates, inserting new radio...")
                    # Insert new radio
                    cursor.execute('''
                        INSERT INTO radio_ids (name, radio_id, is_default) 
                        VALUES (%s, %s, %s)
                    ''', (name, radio_id, False))
                    
                    print(f"🔍 DEBUG: Insert executed, committing...")
                    conn.commit()
                    
                    # Verify the insert worked
                    cursor.execute('SELECT name FROM radio_ids WHERE radio_id = %s', (radio_id,))
                    verify = cursor.fetchone()
                    
                    if verify:
                        print(f"✅ Successfully added to PostgreSQL: {name} - {radio_id}")
                        print(f"✅ Verification: Found {verify[0]} in database")
                    else:
                        print(f"❌ Insert failed - radio not found after commit")
                        
                    return True
                    
        else:
            print(f"🔍 DEBUG: Falling back to SQLite...")
            # Fallback to SQLite
            return add_radio_to_db_sqlite(name, radio_id)
            
    except Exception as e:
        print(f"❌ PostgreSQL add error: {e}")
        print(f"❌ Error type: {type(e)}")
        print(f"❌ Full traceback: {traceback.format_exc()}")
        print("🔄 Using SQLite fallback")
        return add_radio_to_db_sqlite(name, radio_id)

def add_radio_to_db_sqlite(name, radio_id):
    """SQLite version of add_radio_to_db"""
    print(f"🔍 DEBUG SQLite: Adding {name} - {radio_id}")
    with get_db_connection() as conn:
        # Check if radio_id already exists
        cursor = conn.execute('SELECT name FROM radio_ids WHERE radio_id = ?', (radio_id,))
        existing = cursor.fetchone()
        
        if existing:
            raise ValueError(f"Radio ID '{radio_id}' already exists for '{existing['name']}'")
        
        # Insert new radio
        conn.execute('''
            INSERT INTO radio_ids (name, radio_id, is_default) 
            VALUES (?, ?, 0)
        ''', (name, radio_id))
        conn.commit()
        print(f"✅ Added to SQLite: {name} - {radio_id}")

def delete_radio_from_db(radio_id):
    """Delete radio with safe PostgreSQL/SQLite handling"""
    if radio_id == "CUSTOM":
        raise ValueError("Cannot delete the Custom Entry")
    
    try:
        if DATABASE_URL and POSTGRESQL_AVAILABLE:
            # PostgreSQL delete
            with psycopg.connect(DATABASE_URL) as conn:
                with conn.cursor() as cursor:
                    # Check if exists
                    cursor.execute('SELECT name FROM radio_ids WHERE radio_id = %s', (radio_id,))
                    existing = cursor.fetchone()
                    
                    if not existing:
                        raise ValueError(f"Radio ID '{radio_id}' not found")
                    
                    # Delete radio
                    cursor.execute('DELETE FROM radio_ids WHERE radio_id = %s', (radio_id,))
                    conn.commit()
                    
                    print(f"🗑️ Deleted from PostgreSQL: {existing[0]} - {radio_id}")
                    return True
                    
        else:
            # Fallback to SQLite
            return delete_radio_from_db_sqlite(radio_id)
            
    except Exception as e:
        print(f"❌ PostgreSQL delete error: {e}")
        print("🔄 Using SQLite fallback")
        return delete_radio_from_db_sqlite(radio_id)

def delete_radio_from_db_sqlite(radio_id):
    """SQLite version of delete_radio_from_db"""
    with get_db_connection() as conn:
        # Check if exists
        cursor = conn.execute('SELECT name FROM radio_ids WHERE radio_id = ?', (radio_id,))
        existing = cursor.fetchone()
        
        if not existing:
            raise ValueError(f"Radio ID '{radio_id}' not found")
        
        # Delete radio
        conn.execute('DELETE FROM radio_ids WHERE radio_id = ?', (radio_id,))
        conn.commit()
        print(f"🗑️ Deleted from SQLite: {existing['name']} - {radio_id}")

def get_radio_stats():
    """Get radio statistics with safe PostgreSQL/SQLite handling"""
    try:
        if DATABASE_URL and POSTGRESQL_AVAILABLE:
            with psycopg.connect(DATABASE_URL) as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        SELECT 
                            COUNT(*) as total,
                            SUM(CASE WHEN is_default = true THEN 1 ELSE 0 END) as default_count,
                            SUM(CASE WHEN is_default = false AND radio_id != 'CUSTOM' THEN 1 ELSE 0 END) as user_added
                        FROM radio_ids
                    ''')
                    result = cursor.fetchone()
                    return {
                        'total': result[0],
                        'default_count': result[1] or 0,
                        'user_added': result[2] or 0
                    }
        else:
            return get_radio_stats_sqlite()
    except Exception as e:
        print(f"❌ PostgreSQL stats error: {e}")
        return get_radio_stats_sqlite()

def get_radio_stats_sqlite():
    """SQLite version of get_radio_stats"""
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN is_default = 1 THEN 1 ELSE 0 END) as default_count,
                SUM(CASE WHEN is_default = 0 AND radio_id != 'CUSTOM' THEN 1 ELSE 0 END) as user_added
            FROM radio_ids
        ''')
        result = cursor.fetchone()
        return {
            'total': result[0],
            'default_count': result[1] or 0,
            'user_added': result[2] or 0
        }

def initialize_app():
    """Initialize app with safe database handling"""
    print("🚀 Initializing database...")
    try:
        init_database_safe()
        
        # Get stats
        stats = get_radio_stats()
        db_type = "PostgreSQL" if (DATABASE_URL and POSTGRESQL_AVAILABLE) else "SQLite"
        
        print(f"📊 {db_type} Database Stats:")
        print(f"   Total: {stats['total']}")
        print(f"   Default: {stats['default_count']}")
        print(f"   User Added: {stats['user_added']}")
        
    except Exception as e:
        print(f"❌ App initialization error: {e}")

# Flask Routes

@app.route('/dashboard')
@login_required
def dashboard():
    """Main page - no dealer selection, Montgomery AL hardcoded"""
    radios = load_radio_ids()
    user_info = {
        'username': session.get('user'),
        'role': session.get('role')
    }
    return render_template('index.html', radios=radios, user=user_info)

@app.route('/api/radios')
@login_required
def get_radios():
    """Get current radio list"""
    radios = load_radio_ids()
    return jsonify([{"name": name, "radio_id": radio_id} for name, radio_id in radios])

@app.route('/api/radios/add', methods=['POST'])
@login_required
def add_radio():
    """Add a new radio ID - Admin only"""
    # Check if user is admin
    if session.get('role') != 'admin':
        return jsonify({"error": "Administrator access required"}), 403
    
    data = request.json
    name = data.get('name', '').strip()
    radio_id = data.get('radio_id', '').strip().upper()
    
    print(f"🔍 API DEBUG: Received add request for {name} - {radio_id}")
    
    if not name or not radio_id:
        return jsonify({"error": "Name and Radio ID are required"}), 400
    
    try:
        print(f"🔍 API DEBUG: Calling add_radio_to_db...")
        result = add_radio_to_db(name, radio_id)
        print(f"🔍 API DEBUG: add_radio_to_db returned: {result}")
        
        # Verify it was actually added
        radios = load_radio_ids()
        found = any(rid == radio_id for _, rid in radios)
        print(f"🔍 API DEBUG: Radio found in load_radio_ids: {found}")
        
        return jsonify({
            "message": f"Added {name} - {radio_id}", 
            "success": True,
            "verified": found
        })
    except ValueError as e:
        print(f"❌ API DEBUG: ValueError: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(f"❌ API DEBUG: Exception: {e}")
        print(f"❌ API DEBUG: Full traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500

@app.route('/api/radios/delete', methods=['POST'])
@login_required
def delete_radio():
    """Delete a radio ID - Admin only"""
    # Check if user is admin
    if session.get('role') != 'admin':
        return jsonify({"error": "Administrator access required"}), 403
    
    data = request.json
    radio_id = data.get('radio_id', '').strip().upper()
    
    if not radio_id:
        return jsonify({"error": "Radio ID is required"}), 400
    
    try:
        delete_radio_from_db(radio_id)
        return jsonify({"message": f"Deleted radio ID {radio_id}", "success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

@app.route('/api/radios/stats')
@login_required
def get_radio_statistics():
    """Get radio database statistics"""
    try:
        stats = get_radio_stats()
        return jsonify({
            "total_radios": stats['total'],
            "default_radios": stats['default_count'], 
            "user_added_radios": stats['user_added'],
            "success": True
        })
    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

@app.route('/api/debug/database')
@login_required
def debug_database():
    """Debug route to check database state"""
    try:
        # Check database type
        db_type = "PostgreSQL" if (DATABASE_URL and POSTGRESQL_AVAILABLE) else "SQLite"
        
        # Get database stats
        stats = get_radio_stats()
        
        # Get recent radios
        radios = load_radio_ids()
        recent_radios = radios[:10]  # First 10 radios
        
        file_info = {
            "database_type": db_type,
            "database_url_present": DATABASE_URL is not None,
            "postgresql_available": POSTGRESQL_AVAILABLE,
            "current_working_directory": os.getcwd(),
            "base_dir": BASE_DIR
        }
        
        if db_type == "SQLite":
            db_exists = os.path.exists(DATABASE_FILE)
            file_info.update({
                "database_file_path": DATABASE_FILE,
                "database_exists": db_exists
            })
            
            if db_exists:
                stat_info = os.stat(DATABASE_FILE)
                file_info.update({
                    "file_size_bytes": stat_info.st_size,
                    "file_modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat()
                })
        
        return jsonify({
            "success": True,
            "file_info": file_info,
            "total_radios": stats['total'],
            "default_radios": stats['default_count'],
            "user_added_radios": stats['user_added'],
            "recent_radios": [{"name": name, "radio_id": radio_id} for name, radio_id in recent_radios]
        })
        
    except Exception as e:
        return jsonify({"error": f"Database debug error: {str(e)}"}), 500

@app.route('/api/debug/test-connection')
@login_required
def test_db_connection():
    """Test database connection"""
    try:
        if DATABASE_URL and POSTGRESQL_AVAILABLE:
            with psycopg.connect(DATABASE_URL) as conn:
                with conn.cursor() as cursor:
                    cursor.execute('SELECT version()')
                    version = cursor.fetchone()[0]
                    
                    cursor.execute('SELECT COUNT(*) FROM radio_ids')
                    count = cursor.fetchone()[0]
                    
                    return jsonify({
                        "success": True,
                        "database": "PostgreSQL",
                        "version": version,
                        "radio_count": count
                    })
        else:
            return jsonify({
                "success": False,
                "error": "PostgreSQL not available",
                "database_url_present": DATABASE_URL is not None,
                "postgresql_available": POSTGRESQL_AVAILABLE
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "error_type": str(type(e))
        })

@app.route('/activate', methods=['POST'])
@login_required
def activate():
    data = request.json
    radio_id = data.get('radio_id')
    
    if not radio_id:
        return jsonify({"error": "Missing radio ID"}), 400
    
    # Reset status
    global activation_status
    activation_status = {"progress": 0, "status": "Starting activation...", "completed": False, "success": False}
    
    # Start activation in background thread (Montgomery, AL hardcoded)
    thread = threading.Thread(target=run_activation, args=(radio_id,))
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "Activation started"})

@app.route('/status')
@login_required
def get_status():
    return jsonify(activation_status)

def update_status(message):
    global activation_status
    activation_status["status"] = f"{activation_status['status']}\n[{datetime.now().strftime('%H:%M:%S')}] {message}"

def update_progress(value):
    global activation_status
    activation_status["progress"] = value

def run_activation(radio_id):
    global activation_status
    try:
        activator = SiriusXMActivator()
        success = activator.activate_radio(radio_id, update_status, update_progress)
        
        activation_status["completed"] = True
        activation_status["success"] = success
        activation_status["progress"] = 9
        
        if success:
            activation_status["status"] += f"\n🎉 Radio {radio_id} activated successfully!"
        else:
            activation_status["status"] += f"\n❌ Radio {radio_id} activation failed"
            
    except Exception as e:
        activation_status["completed"] = True
        activation_status["success"] = False
        activation_status["status"] += f"\n❌ Error: {str(e)}"

# SiriusXM Activator class - FIXED VERSION matching working code
class SiriusXMActivator:
    def __init__(self):
        self.session = requests.Session()
        self.radio_id_input = None
        self.uuid4 = str(uuid.uuid4())
        self.auth_token = ""
        self.seq = ""
        self.deviceModel = "iPhone 14 Pro"
        self.deviceiOSVersion = "17.0"
        self.appVer = "3.1.0"
        self.userAgent = "SiriusXM%20Dealer/3.1.0 CFNetwork/1568.200.51 Darwin/24.1.0"
    
    def get_reporting_params(self, svc_id):
        """Generate reporting params string - FIXED to match working code"""
        params = {
            "os": self.deviceiOSVersion,
            "dm": self.deviceModel,
            "did": self.uuid4,
            "ua": "iPhone",
            "aid": "DealerApp",
            "aname": "SiriusXM Dealer",
            "chnl": "mobile",
            "plat": "ios",
            "aver": self.appVer,
            "atype": "native",
            "stype": "b2c",
            "kuid": "",
            "mfaid": "df7be3dc-e278-436c-b2f8-4cfde321df0a",
            "mfbaseid": "efb9acb6-daea-4f2f-aeb3-b17832bdd47b",
            "mfaname": "DealerApp",
            "sdkversion": "9.5.36",
            "sdktype": "js",
            "fid": "frmRadioRefresh",
            "sessiontype": "I",
            "clientUUID": "1742536405634-41a8-0de0-125c",
            "rsid": "1742536405654-b954-784f-38d2",
            "svcid": svc_id
        }
        
        # Use json.dumps like the working code
        params_str = json.dumps(params, separators=(',', ':'))
        
        # Encode it properly
        return urllib.parse.quote(params_str, safe='$:,')
    
    def activate_radio(self, radio_id, status_callback, progress_callback):
        self.radio_id_input = radio_id.upper()
        status_callback(f"🔄 Starting activation for: {self.radio_id_input}")
        
        steps = [
            ("🔐 Login", self.login),
            ("📱 Version Control", self.versionControl),
            ("⚙️ Get Properties", self.getProperties),
            ("🔄 Device Refresh 1", self.update_1),
            ("📊 CRM Info", self.getCRM),
            ("🛡️ Blocklist Check", self.blocklist),
            ("👤 Create Account", self.createAccount),
            ("✅ Device Refresh 2", self.update_2)
        ]
        
        for i, (step_name, step_func) in enumerate(steps):
            status_callback(f"Step {i+1}/8: {step_name}")
            progress_callback(i + 1)
            
            try:
                result = step_func()
                if result is not None or step_func == self.blocklist or step_func == self.createAccount or step_func == self.update_2:
                    status_callback(f"✅ {step_name}: Complete")
                else:
                    status_callback(f"❌ {step_name}: Failed")
                    return False
            except Exception as e:
                status_callback(f"❌ {step_name}: Error - {str(e)[:100]}")
                return False
            
            time.sleep(1)
        
        status_callback("🎉 Activation completed!")
        return True

    def login(self):
        try:
            params = {
                "os": self.deviceiOSVersion,
                "dm": self.deviceModel,
                "did": self.uuid4,
                "ua": "iPhone",
                "aid": "DealerApp",
                "aname": "SiriusXM Dealer",
                "chnl": "mobile",
                "plat": "ios",
                "aver": self.appVer,
                "atype": "native",
                "stype": "b2c",
                "kuid": "",
                "mfaid": "df7be3dc-e278-436c-b2f8-4cfde321df0a",
                "mfbaseid": "efb9acb6-daea-4f2f-aeb3-b17832bdd47b",
                "mfaname": "DealerApp",
                "sdkversion": "9.5.36",
                "sdktype": "js",
                "sessiontype": "I",
                "clientUUID": "1742536405634-41a8-0de0-125c",
                "rsid": "1742536405654-b954-784f-38d2",
                "svcid": "login_$anonymousProvider"
            }
            params_str = json.dumps(params, separators=(',', ':'))
            
            response = self.session.post(
                url="https://dealerapp.siriusxm.com/authService/100000002/login",
                headers={
                    "X-Voltmx-Platform-Type": "ios",
                    "Accept": "application/json",
                    "X-Voltmx-App-Secret": "c086fca8646a72cf391f8ae9f15e5331",
                    "Accept-Language": "en-us",
                    "X-Voltmx-SDK-Type": "js",
                    "Accept-Encoding": "br, gzip, deflate",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": self.userAgent,
                    "X-Voltmx-SDK-Version": "9.5.36",
                    "X-Voltmx-App-Key": "67cfe0220c41a54cb4e768723ad56b41",
                    "X-Voltmx-ReportingParams": urllib.parse.quote(params_str, safe='$:,'),
                },
            )
            self.auth_token = response.json().get('claims_token').get('value')
            return self.auth_token
        except Exception as e:
            print(f'Login failed: {e}')
            return None

    def versionControl(self):
        try:
            params = {
                "os": self.deviceiOSVersion,
                "dm": self.deviceModel,
                "did": self.uuid4,
                "ua": "iPhone",
                "aid": "DealerApp",
                "aname": "SiriusXM Dealer",
                "chnl": "mobile",
                "plat": "ios",
                "aver": self.appVer,
                "atype": "native",
                "stype": "b2c",
                "kuid": "",
                "mfaid": "df7be3dc-e278-436c-b2f8-4cfde321df0a",
                "mfbaseid": "efb9acb6-daea-4f2f-aeb3-b17832bdd47b",
                "mfaname": "DealerApp",
                "sdkversion": "9.5.36",
                "sdktype": "js",
                "fid": "frmHome",
                "sessiontype": "I",
                "clientUUID": "1742536405634-41a8-0de0-125c",
                "rsid": "1742536405654-b954-784f-38d2",
                "svcid": "VersionControl"
            }
            params_str = json.dumps(params, separators=(',', ':'))
            
            response = self.session.post(
                url="https://dealerapp.siriusxm.com/services/DealerAppService7/VersionControl",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Accept-Language": "en-us",
                    "Accept-Encoding": "br, gzip, deflate",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": self.userAgent,
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": urllib.parse.quote(params_str, safe='$:,'),
                },
                data={
                    "deviceCategory": "iPhone",
                    "appver": self.appVer,
                    "deviceLocale": "en_US",
                    "deviceModel": self.deviceModel,
                    "deviceVersion": self.deviceiOSVersion,
                    "deviceType": "",
                },
            )
            return True
        except Exception as e:
            print(f'versionControl failed: {e}')
            return None

    def getProperties(self):
        try:
            params = {
                "os": self.deviceiOSVersion,
                "dm": self.deviceModel,
                "did": self.uuid4,
                "ua": "iPhone",
                "aid": "DealerApp",
                "aname": "SiriusXM Dealer",
                "chnl": "mobile",
                "plat": "ios",
                "aver": self.appVer,
                "atype": "native",
                "stype": "b2c",
                "kuid": "",
                "mfaid": "df7be3dc-e278-436c-b2f8-4cfde321df0a",
                "mfbaseid": "efb9acb6-daea-4f2f-aeb3-b17832bdd47b",
                "mfaname": "DealerApp",
                "sdkversion": "9.5.36",
                "sdktype": "js",
                "fid": "frmHome",
                "sessiontype": "I",
                "clientUUID": "1742536405634-41a8-0de0-125c",
                "rsid": "1742536405654-b954-784f-38d2",
                "svcid": "getProperties"
            }
            params_str = json.dumps(params, separators=(',', ':'))
            
            response = self.session.post(
                url="https://dealerapp.siriusxm.com/services/DealerAppService7/getProperties",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Accept-Language": "en-us",
                    "Accept-Encoding": "br, gzip, deflate",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": self.userAgent,
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": urllib.parse.quote(params_str, safe='$:,'),
                },
            )
            return True
        except Exception as e:
            print(f'getProperties failed: {e}')
            return None

    def update_1(self):
        try:
            params = {
                "os": self.deviceiOSVersion,
                "dm": self.deviceModel,
                "did": self.uuid4,
                "ua": "iPhone",
                "aid": "DealerApp",
                "aname": "SiriusXM Dealer",
                "chnl": "mobile",
                "plat": "ios",
                "aver": self.appVer,
                "atype": "native",
                "stype": "b2c",
                "kuid": "",
                "mfaid": "df7be3dc-e278-436c-b2f8-4cfde321df0a",
                "mfbaseid": "efb9acb6-daea-4f2f-aeb3-b17832bdd47b",
                "mfaname": "DealerApp",
                "sdkversion": "9.5.36",
                "sdktype": "js",
                "fid": "frmRadioRefresh",
                "sessiontype": "I",
                "clientUUID": "1742536405634-41a8-0de0-125c",
                "rsid": "1742536405654-b954-784f-38d2",
                "svcid": "updateDeviceSATRefreshWithPriority"
            }
            params_str = json.dumps(params, separators=(',', ':'))
            
            print(f'🔍 DEBUG update_1: Radio ID = {self.radio_id_input}')
            print(f'🔍 DEBUG update_1: Auth Token = {self.auth_token[:50]}...')
            
            response = self.session.post(
                url="https://dealerapp.siriusxm.com/services/USUpdateDeviceSATRefresh/updateDeviceSATRefreshWithPriority",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Accept-Language": "en-us",
                    "Accept-Encoding": "br, gzip, deflate",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": self.userAgent,
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": urllib.parse.quote(params_str, safe='$:,'),
                },
                data={
                    "deviceId": self.radio_id_input,
                    "appVersion": self.appVer,
                    "deviceID": self.uuid4,
                    "provisionPriority": "2",
                    "provisionType": "activate",
                },
            )
            
            print(f'🔍 DEBUG update_1: Status Code = {response.status_code}')
            print(f'🔍 DEBUG update_1: Response = {response.content}')
            
            if response.status_code != 200:
                print(f'❌ update_1: HTTP error {response.status_code}')
                return None
            
            response_json = response.json()
            print(f'🔍 DEBUG update_1: JSON = {response_json}')
            
            self.seq = response_json.get('seqValue')
            
            if not self.seq:
                print(f'❌ update_1: No seqValue in response')
                return None
                
            print(f'✅ update_1: Got seqValue = {self.seq}')
            return self.seq
            
        except Exception as e:
            print(f'❌ update_1 failed with exception: {e}')
            print(f'❌ Full traceback: {traceback.format_exc()}')
            return None

    def getCRM(self):
        try:
            params = {
                "os": self.deviceiOSVersion,
                "dm": self.deviceModel,
                "did": self.uuid4,
                "ua": "iPhone",
                "aid": "DealerApp",
                "aname": "SiriusXM Dealer",
                "chnl": "mobile",
                "plat": "ios",
                "aver": self.appVer,
                "atype": "native",
                "stype": "b2c",
                "kuid": "",
                "mfaid": "df7be3dc-e278-436c-b2f8-4cfde321df0a",
                "mfbaseid": "efb9acb6-daea-4f2f-aeb3-b17832bdd47b",
                "mfaname": "DealerApp",
                "sdkversion": "9.5.36",
                "sdktype": "js",
                "fid": "frmRadioRefresh",
                "sessiontype": "I",
                "clientUUID": "1742536405634-41a8-0de0-125c",
                "rsid": "1742536405654-b954-784f-38d2",
                "svcid": "GetCRMAccountPlanInformation"
            }
            params_str = json.dumps(params, separators=(',', ':'))
            
            response = self.session.post(
                url="https://dealerapp.siriusxm.com/services/DemoConsumptionRules/GetCRMAccountPlanInformation",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Accept-Language": "en-us",
                    "Accept-Encoding": "br, gzip, deflate",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": self.userAgent,
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": urllib.parse.quote(params_str, safe='$:,'),
                },
                data={
                    "seqVal": self.seq,
                    "deviceId": self.radio_id_input,
                },
            )
            print(f'getCRM Response: {response.content}')
            return True
        except Exception as e:
            print(f'getCRM failed: {e}')
            return None

    def blocklist(self):
        try:
            params = {
                "os": self.deviceiOSVersion,
                "dm": self.deviceModel,
                "did": self.uuid4,
                "ua": "iPhone",
                "aid": "DealerApp",
                "aname": "SiriusXM Dealer",
                "chnl": "mobile",
                "plat": "ios",
                "aver": self.appVer,
                "atype": "native",
                "stype": "b2c",
                "kuid": "",
                "mfaid": "df7be3dc-e278-436c-b2f8-4cfde321df0a",
                "mfbaseid": "efb9acb6-daea-4f2f-aeb3-b17832bdd47b",
                "mfaname": "DealerApp",
                "sdkversion": "9.5.36",
                "sdktype": "js",
                "fid": "frmRadioRefresh",
                "sessiontype": "I",
                "clientUUID": "1742536405634-41a8-0de0-125c",
                "rsid": "1742536405654-b954-784f-38d2",
                "svcid": "BlockListDevice"
            }
            params_str = json.dumps(params, separators=(',', ':'))
            
            response = self.session.post(
                url="https://dealerapp.siriusxm.com/services/USBlockListDevice/BlockListDevice",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Accept-Language": "en-us",
                    "Accept-Encoding": "br, gzip, deflate",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": self.userAgent,
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": urllib.parse.quote(params_str, safe='$:,'),
                },
                data={
                    "deviceId": self.uuid4,
                },
            )
            print(f'blocklist Response: {response.content}')
            return True
        except Exception as e:
            print(f'blocklist failed: {e}')
            return None

    def createAccount(self):
        try:
            params = {
                "os": self.deviceiOSVersion,
                "dm": self.deviceModel,
                "did": self.uuid4,
                "ua": "iPhone",
                "aid": "DealerApp",
                "aname": "SiriusXM Dealer",
                "chnl": "mobile",
                "plat": "ios",
                "aver": self.appVer,
                "atype": "native",
                "stype": "b2c",
                "kuid": "",
                "mfaid": "df7be3dc-e278-436c-b2f8-4cfde321df0a",
                "mfbaseid": "efb9acb6-daea-4f2f-aeb3-b17832bdd47b",
                "mfaname": "DealerApp",
                "sdkversion": "9.5.36",
                "sdktype": "js",
                "fid": "frmRadioRefresh",
                "sessiontype": "I",
                "clientUUID": "1742536405634-41a8-0de0-125c",
                "rsid": "1742536405654-b954-784f-38d2",
                "svcid": "CreateAccount"
            }
            params_str = json.dumps(params, separators=(',', ':'))
            
            response = self.session.post(
                url="https://dealerapp.siriusxm.com/services/DealerAppService3/CreateAccount",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Accept-Language": "en-us",
                    "Accept-Encoding": "br, gzip, deflate",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": self.userAgent,
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": urllib.parse.quote(params_str, safe='$:,'),
                },
                data={
                    "seqVal": self.seq,
                    "deviceId": self.radio_id_input,
                    "oracleCXFailed": "1",
                    "appVersion": self.appVer,
                },
            )
            print(f'createAccount Response: {response.content}')
            return True
        except Exception as e:
            print(f'createAccount failed: {e}')
            return None

    def update_2(self):
        try:
            params = {
                "os": self.deviceiOSVersion,
                "dm": self.deviceModel,
                "did": self.uuid4,
                "ua": "iPhone",
                "aid": "DealerApp",
                "aname": "SiriusXM Dealer",
                "chnl": "mobile",
                "plat": "ios",
                "aver": self.appVer,
                "atype": "native",
                "stype": "b2c",
                "kuid": "",
                "mfaid": "df7be3dc-e278-436c-b2f8-4cfde321df0a",
                "mfbaseid": "efb9acb6-daea-4f2f-aeb3-b17832bdd47b",
                "mfaname": "DealerApp",
                "sdkversion": "9.5.36",
                "sdktype": "js",
                "fid": "frmRadioRefresh",
                "sessiontype": "I",
                "clientUUID": "1742536405634-41a8-0de0-125c",
                "rsid": "1742536405654-b954-784f-38d2",
                "svcid": "updateDeviceSATRefreshWithPriority"
            }
            params_str = json.dumps(params, separators=(',', ':'))
            
            response = self.session.post(
                url="https://dealerapp.siriusxm.com/services/USUpdateDeviceRefreshForCC/updateDeviceSATRefreshWithPriority",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Accept-Language": "en-us",
                    "Accept-Encoding": "br, gzip, deflate",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": self.userAgent,
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": urllib.parse.quote(params_str, safe='$:,'),
                },
                data={
                    "deviceId": self.radio_id_input,
                    "provisionPriority": "2",
                    "appVersion": self.appVer,
                    "device_Type": urllib.parse.quote("iPhone " + self.deviceModel, safe='$:,'),
                    "deviceID": self.uuid4,
                    "os_Version": urllib.parse.quote("iPhone " + self.deviceiOSVersion, safe='$:,'),
                    "provisionType": "activate",
                },
            )
            print(f'update_2 Response: {response.content}')
            return True
        except Exception as e:
            print(f'update_2 failed: {e}')
            return None

# Render deployment configuration
if __name__ == '__main__':
    # Initialize database before starting the app
    initialize_app()
    
    import os
    port = int(os.environ.get('PORT', 5000))
    
    print("🚀 Starting SiriusXM Activator on Render...")
    print(f"🌐 Port: {port}")
    print("🔗 Will be available at: https://app.renslip.com")
    print("")
    print("⚠️  UPDATED USER SYSTEM:")
    print("👑 DaveHall / schmij (Administrator)")
    print("⚙️ ShelbyHank / schmij (Operator)")
    print("🔑 CHANGE SECRET KEY before sharing!")
    print("")
    print("✅ Ready for production deployment!")
    
    # Render production configuration
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
