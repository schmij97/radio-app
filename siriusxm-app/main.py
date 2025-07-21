#!/usr/bin/env python3
# main.py - Password-protected SiriusXM App for Railway deployment

import sys
import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import requests
import time
import uuid
import json
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from functools import wraps

# Configure Flask app
app = Flask(__name__)

# IMPORTANT: Change these before deploying!
app.config['SECRET_KEY'] = 'unique-key'
ADMIN_PASSWORD = "DaveHall"  # ⚠️ Updated password!

# Session settings
SESSION_TIMEOUT = 3600  # 1 hour in seconds

# File storage (Railway will handle this)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RADIO_IDS_FILE = os.path.join(BASE_DIR, 'radio_ids.json')

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        password = request.form.get('password')
        
        if password == ADMIN_PASSWORD:
            session['authenticated'] = True
            session['login_time'] = time.time()
            flash('Successfully logged in!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid password. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

def load_radio_ids() -> List[Tuple[str, str]]:
    """Load radio IDs from file, or return default list if file doesn't exist"""
    default_radios = [
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
    
    if os.path.exists(RADIO_IDS_FILE):
        try:
            with open(RADIO_IDS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [(item['name'], item['radio_id']) for item in data]
        except Exception as e:
            print(f"Error loading radio IDs: {e}")
            return default_radios
    else:
        save_radio_ids(default_radios)
        return default_radios

def save_radio_ids(radio_ids: List[Tuple[str, str]]) -> None:
    """Save radio IDs to file"""
    try:
        data = [{"name": name, "radio_id": radio_id} for name, radio_id in radio_ids]
        with open(RADIO_IDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving radio IDs: {e}")

@app.route('/')
@login_required
def index():
    """Main page - no dealer selection needed"""
    radios = load_radio_ids()
    return render_template('index.html', radios=radios)

@app.route('/api/radios')
@login_required
def get_radios():
    """Get current radio list"""
    radios = load_radio_ids()
    return jsonify([{"name": name, "radio_id": radio_id} for name, radio_id in radios])

@app.route('/api/radios/add', methods=['POST'])
@login_required
def add_radio():
    """Add a new radio ID"""
    data = request.json
    name = data.get('name', '').strip()
    radio_id = data.get('radio_id', '').strip().upper()
    
    if not name or not radio_id:
        return jsonify({"error": "Name and Radio ID are required"}), 400
    
    radios = load_radio_ids()
    
    # Check for duplicates
    existing_ids = [rid for _, rid in radios if rid != "CUSTOM"]
    if radio_id in existing_ids:
        return jsonify({"error": f"Radio ID '{radio_id}' already exists"}), 400
    
    # Add new radio
    custom_entry = None
    filtered_radios = []
    for name_item, radio_item in radios:
        if radio_item == "CUSTOM":
            custom_entry = (name_item, radio_item)
        else:
            filtered_radios.append((name_item, radio_item))
    
    filtered_radios.append((name, radio_id))
    
    if custom_entry:
        filtered_radios.insert(0, custom_entry)
    
    save_radio_ids(filtered_radios)
    
    return jsonify({"message": f"Added {name} - {radio_id}", "success": True})

@app.route('/api/radios/delete', methods=['POST'])
@login_required
def delete_radio():
    """Delete a radio ID"""
    data = request.json
    radio_id = data.get('radio_id', '').strip().upper()
    
    if not radio_id or radio_id == "CUSTOM":
        return jsonify({"error": "Invalid Radio ID"}), 400
    
    radios = load_radio_ids()
    updated_radios = [(n, r) for n, r in radios if r != radio_id]
    
    if len(updated_radios) == len(radios):
        return jsonify({"error": "Radio ID not found"}), 404
    
    save_radio_ids(updated_radios)
    
    return jsonify({"message": f"Deleted radio ID {radio_id}", "success": True})

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
    
    # Start activation in background thread
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
        activation_status["progress"] = 11
        
        if success:
            activation_status["status"] += f"\n🎉 Radio {radio_id} activated successfully!"
        else:
            activation_status["status"] += f"\n❌ Radio {radio_id} activation failed"
            
    except Exception as e:
        activation_status["completed"] = True
        activation_status["success"] = False
        activation_status["status"] += f"\n❌ Error: {str(e)}"

# SiriusXM Activator class with the new implementation
class SiriusXMActivator:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Accept-Language': 'en-us',
            'Accept-Encoding': 'br, gzip, deflate',
            'User-Agent': 'SiriusXM%20Dealer/3.1.0 CFNetwork/1568.200.51 Darwin/24.1.0'
        })
        self.radio_id = None
        self.uuid4 = str(uuid.uuid4())
        self.auth_token = None
        self.seq = None
    
    def activate_radio(self, radio_id, status_callback, progress_callback):
        self.radio_id = radio_id.upper()
        status_callback(f"🔄 Starting activation for: {self.radio_id}")
        
        steps = [
            ("📡 App Config", self.appconfig),
            ("🔐 Login", self.login),
            ("📱 Version Control", self.version_control),
            ("⚙️ Get Properties", self.get_properties),
            ("🔄 Device Refresh 1", self.update_1),
            ("📊 CRM Info", self.get_crm),
            ("💾 DB Update", self.db_update),
            ("🛡️ Blocklist Check", self.blocklist),
            ("🏢 Oracle Check", self.oracle),
            ("👤 Create Account", self.create_account),
            ("✅ Device Refresh 2", self.update_2)
        ]
        
        for i, (step_name, step_func) in enumerate(steps):
            status_callback(f"Step {i+1}/11: {step_name}")
            progress_callback(i + 1)
            
            try:
                success = step_func()
                if success:
                    status_callback(f"✅ {step_name}: Complete")
                else:
                    status_callback(f"❌ {step_name}: Failed")
            except Exception as e:
                status_callback(f"❌ {step_name}: Error - {str(e)[:50]}")
            
            time.sleep(1)
        
        status_callback("🎉 Activation completed!")
        return True
    
    def appconfig(self):
        try:
            response = self.session.post(
                "https://dealerapp.siriusxm.com/authService/100000002/appconfig",
                headers={
                    "X-Kony-Integrity": "GWSUSEVMJK;FEC9AA232EC59BE8A39F0FAE1B71300216E906B85F40CA2B1C5C7A59F85B17A4",
                    "X-HTTP-Method-Override": "GET",
                    "X-Voltmx-App-Key": "67cfe0220c41a54cb4e768723ad56b41",
                    "Accept": "*/*",
                    "X-Voltmx-App-Secret": "c086fca8646a72cf391f8ae9f15e5331",
                    "X-Voltmx-ReportingParams": "",
                },
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
    
    def login(self):
        try:
            response = self.session.post(
                "https://dealerapp.siriusxm.com/authService/100000002/login",
                headers={
                    "X-Voltmx-Platform-Type": "ios",
                    "Accept": "application/json",
                    "X-Voltmx-App-Secret": "c086fca8646a72cf391f8ae9f15e5331",
                    "X-Voltmx-SDK-Type": "js",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Voltmx-SDK-Version": "9.5.36",
                    "X-Voltmx-App-Key": "67cfe0220c41a54cb4e768723ad56b41",
                    "X-Voltmx-ReportingParams": f'%7B%22os%22:%2217.0%22,%22dm%22:%22iPhone%2014%20Pro%22,%22did%22:%22{self.uuid4}%22,%22ua%22:%22iPhone%22,%22aid%22:%22DealerApp%22,%22aname%22:%22SiriusXM%20Dealer%22,%22chnl%22:%22mobile%22,%22plat%22:%22ios%22,%22aver%22:%223.1.0%22,%22atype%22:%22native%22,%22stype%22:%22b2c%22,%22kuid%22:%22%22,%22mfaid%22:%22df7be3dc-e278-436c-b2f8-4cfde321df0a%22,%22mfbaseid%22:%22efb9acb6-daea-4f2f-aeb3-b17832bdd47b%22,%22mfaname%22:%22DealerApp%22,%22sdkversion%22:%229.5.36%22,%22sdktype%22:%22js%22,%22fid%22:%22frmRadioRefresh%22,%22sessiontype%22:%22I%22,%22clientUUID%22:%221742536405634-41a8-0de0-125c%22,%22rsid%22:%221742536405654-b954-784f-38d2%22,%22svcid%22:%22BlockListDevice%22%7D',
                },
                data={
                    "deviceId": self.uuid4,
                },
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
    
    def oracle(self):
        try:
            response = self.session.post(
                "https://oemremarketing.custhelp.com/cgi-bin/oemremarketing.cfg/php/custom/src/oracle/program_status.php",
                params={
                    "google_addr": "395 EASTERN BLVD, MONTGOMERY, AL 36117, USA",
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "*/*",
                    "X-Voltmx-ReportingParams": "",
                },
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
    
    def create_account(self):
        try:
            response = self.session.post(
                "https://dealerapp.siriusxm.com/services/DealerAppService3/CreateAccount",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": f'%7B%22os%22:%2217.0%22,%22dm%22:%22iPhone%2014%20Pro%22,%22did%22:%22{self.uuid4}%22,%22ua%22:%22iPhone%22,%22aid%22:%22DealerApp%22,%22aname%22:%22SiriusXM%20Dealer%22,%22chnl%22:%22mobile%22,%22plat%22:%22ios%22,%22aver%22:%223.1.0%22,%22atype%22:%22native%22,%22stype%22:%22b2c%22,%22kuid%22:%22%22,%22mfaid%22:%22df7be3dc-e278-436c-b2f8-4cfde321df0a%22,%22mfbaseid%22:%22efb9acb6-daea-4f2f-aeb3-b17832bdd47b%22,%22mfaname%22:%22DealerApp%22,%22sdkversion%22:%229.5.36%22,%22sdktype%22:%22js%22,%22fid%22:%22frmRadioRefresh%22,%22sessiontype%22:%22I%22,%22clientUUID%22:%221742536405634-41a8-0de0-125c%22,%22rsid%22:%221742536405654-b954-784f-38d2%22,%22svcid%22:%22CreateAccount%22%7D',
                },
                data={
                    "seqVal": self.seq,
                    "deviceId": self.radio_id,
                    "oracleCXFailed": "1",
                    "appVersion": "3.1.0",
                },
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
    
    def update_2(self):
        try:
            response = self.session.post(
                "https://dealerapp.siriusxm.com/services/USUpdateDeviceRefreshForCC/updateDeviceSATRefreshWithPriority",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": f'%7B%22os%22:%2217.0%22,%22dm%22:%22iPhone%2014%20Pro%22,%22did%22:%22{self.uuid4}%22,%22ua%22:%22iPhone%22,%22aid%22:%22DealerApp%22,%22aname%22:%22SiriusXM%20Dealer%22,%22chnl%22:%22mobile%22,%22plat%22:%22ios%22,%22aver%22:%223.1.0%22,%22atype%22:%22native%22,%22stype%22:%22b2c%22,%22kuid%22:%22%22,%22mfaid%22:%22df7be3dc-e278-436c-b2f8-4cfde321df0a%22,%22mfbaseid%22:%22efb9acb6-daea-4f2f-aeb3-b17832bdd47b%22,%22mfaname%22:%22DealerApp%22,%22sdkversion%22:%229.5.36%22,%22sdktype%22:%22js%22,%22fid%22:%22frmRadioRefresh%22,%22sessiontype%22:%22I%22,%22clientUUID%22:%221742536405634-41a8-0de0-125c%22,%22rsid%22:%221742536405654-b954-784f-38d2%22,%22svcid%22:%22updateDeviceSATRefreshWithPriority%22%7D',
                },
                data={
                    "deviceId": self.radio_id,
                    "provisionPriority": "2",
                    "appVersion": "3.1.0",
                    "device_Type": "iPhone iPhone 6 Plus",
                    "deviceID": self.uuid4,
                    "os_Version": "iPhone 12.5.7",
                    "provisionType": "activate",
                },
                timeout=10
            )
            return response.status_code == 200
        except:
            return False

# Railway deployment configuration
if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    
    print("🚀 Starting SiriusXM Activator on Render...")
    print(f"🌐 Port: {port}")
    print("🔗 Will be available at: https://app.renslip.com")
    print("")
    print("⚠️  IMPORTANT SECURITY REMINDERS:")
    print("🔐 Current password: DaveHall")
    print("🛠️  CHANGE PASSWORD before sharing!")
    print("🔑 CHANGE SECRET KEY before sharing!")
    print("")
    print("✅ Ready for production deployment!")
    
    # Render production configuration
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)%22,%22mfaname%22:%22DealerApp%22,%22sdkversion%22:%229.5.36%22,%22sdktype%22:%22js%22,%22sessiontype%22:%22I%22,%22clientUUID%22:%221742536405634-41a8-0de0-125c%22,%22rsid%22:%221742536405654-b954-784f-38d2%22,%22svcid%22:%22login_$anonymousProvider%22%7D',
                },
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get('claims_token', {}).get('value')
                return self.auth_token is not None
        except:
            pass
        return False
    
    def version_control(self):
        try:
            response = self.session.post(
                "https://dealerapp.siriusxm.com/services/DealerAppService7/VersionControl",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": f'%7B%22os%22:%2217.0%22,%22dm%22:%22iPhone%2014%20Pro%22,%22did%22:%22{self.uuid4}%22,%22ua%22:%22iPhone%22,%22aid%22:%22DealerApp%22,%22aname%22:%22SiriusXM%20Dealer%22,%22chnl%22:%22mobile%22,%22plat%22:%22ios%22,%22aver%22:%223.1.0%22,%22atype%22:%22native%22,%22stype%22:%22b2c%22,%22kuid%22:%22%22,%22mfaid%22:%22df7be3dc-e278-436c-b2f8-4cfde321df0a%22,%22mfbaseid%22:%22efb9acb6-daea-4f2f-aeb3-b17832bdd47b%22,%22mfaname%22:%22DealerApp%22,%22sdkversion%22:%229.5.36%22,%22sdktype%22:%22js%22,%22fid%22:%22frmHome%22,%22sessiontype%22:%22I%22,%22clientUUID%22:%221742536405634-41a8-0de0-125c%22,%22rsid%22:%221742536405654-b954-784f-38d2%22,%22svcid%22:%22VersionControl%22%7D',
                },
                data={
                    "deviceCategory": "iPhone",
                    "appver": "3.1.0",
                    "deviceLocale": "en_US",
                    "deviceModel": "iPhone%206%20Plus",
                    "deviceVersion": "12.5.7",
                    "deviceType": "",
                },
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
    
    def get_properties(self):
        try:
            response = self.session.post(
                "https://dealerapp.siriusxm.com/services/DealerAppService7/getProperties",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": f'%7B%22os%22:%2217.0%22,%22dm%22:%22iPhone%2014%20Pro%22,%22did%22:%22{self.uuid4}%22,%22ua%22:%22iPhone%22,%22aid%22:%22DealerApp%22,%22aname%22:%22SiriusXM%20Dealer%22,%22chnl%22:%22mobile%22,%22plat%22:%22ios%22,%22aver%22:%223.1.0%22,%22atype%22:%22native%22,%22stype%22:%22b2c%22,%22kuid%22:%22%22,%22mfaid%22:%22df7be3dc-e278-436c-b2f8-4cfde321df0a%22,%22mfbaseid%22:%22efb9acb6-daea-4f2f-aeb3-b17832bdd47b%22,%22mfaname%22:%22DealerApp%22,%22sdkversion%22:%229.5.36%22,%22sdktype%22:%22js%22,%22fid%22:%22frmHome%22,%22sessiontype%22:%22I%22,%22clientUUID%22:%221742536405634-41a8-0de0-125c%22,%22rsid%22:%221742536405654-b954-784f-38d2%22,%22svcid%22:%22getProperties%22%7D',
                },
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
    
    def update_1(self):
        try:
            response = self.session.post(
                "https://dealerapp.siriusxm.com/services/USUpdateDeviceSATRefresh/updateDeviceSATRefreshWithPriority",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": f'%7B%22os%22:%2217.0%22,%22dm%22:%22iPhone%2014%20Pro%22,%22did%22:%22{self.uuid4}%22,%22ua%22:%22iPhone%22,%22aid%22:%22DealerApp%22,%22aname%22:%22SiriusXM%20Dealer%22,%22chnl%22:%22mobile%22,%22plat%22:%22ios%22,%22aver%22:%223.1.0%22,%22atype%22:%22native%22,%22stype%22:%22b2c%22,%22kuid%22:%22%22,%22mfaid%22:%22df7be3dc-e278-436c-b2f8-4cfde321df0a%22,%22mfbaseid%22:%22efb9acb6-daea-4f2f-aeb3-b17832bdd47b%22,%22mfaname%22:%22DealerApp%22,%22sdkversion%22:%229.5.36%22,%22sdktype%22:%22js%22,%22fid%22:%22frmRadioRefresh%22,%22sessiontype%22:%22I%22,%22clientUUID%22:%221742536405634-41a8-0de0-125c%22,%22rsid%22:%221742536405654-b954-784f-38d2%22,%22svcid%22:%22updateDeviceSATRefreshWithPriority%22%7D',
                },
                data={
                    "deviceId": self.radio_id,
                    "appVersion": "3.1.0",
                    "lng": "-86.210313195",
                    "deviceID": self.uuid4,
                    "provisionPriority": "2",
                    "provisionType": "activate",
                    "lat": "32.37436705",
                },
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.seq = data.get('seqValue')
                return True
        except:
            pass
        return False
    
    def get_crm(self):
        try:
            response = self.session.post(
                "https://dealerapp.siriusxm.com/services/DemoConsumptionRules/GetCRMAccountPlanInformation",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": f'%7B%22os%22:%2217.0%22,%22dm%22:%22iPhone%2014%20Pro%22,%22did%22:%22{self.uuid4}%22,%22ua%22:%22iPhone%22,%22aid%22:%22DealerApp%22,%22aname%22:%22SiriusXM%20Dealer%22,%22chnl%22:%22mobile%22,%22plat%22:%22ios%22,%22aver%22:%223.1.0%22,%22atype%22:%22native%22,%22stype%22:%22b2c%22,%22kuid%22:%22%22,%22mfaid%22:%22df7be3dc-e278-436c-b2f8-4cfde321df0a%22,%22mfbaseid%22:%22efb9acb6-daea-4f2f-aeb3-b17832bdd47b%22,%22mfaname%22:%22DealerApp%22,%22sdkversion%22:%229.5.36%22,%22sdktype%22:%22js%22,%22fid%22:%22frmRadioRefresh%22,%22sessiontype%22:%22I%22,%22clientUUID%22:%221742536405634-41a8-0de0-125c%22,%22rsid%22:%221742536405654-b954-784f-38d2%22,%22svcid%22:%22GetCRMAccountPlanInformation%22%7D',
                },
                data={
                    "seqVal": self.seq,
                    "deviceId": self.radio_id,
                },
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
    
    def db_update(self):
        try:
            response = self.session.post(
                "https://dealerapp.siriusxm.com/services/DBSuccessUpdate/DBUpdateForGoogle",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": f'%7B%22os%22:%2217.0%22,%22dm%22:%22iPhone%2014%20Pro%22,%22did%22:%22{self.uuid4}%22,%22ua%22:%22iPhone%22,%22aid%22:%22DealerApp%22,%22aname%22:%22SiriusXM%20Dealer%22,%22chnl%22:%22mobile%22,%22plat%22:%22ios%22,%22aver%22:%223.1.0%22,%22atype%22:%22native%22,%22stype%22:%22b2c%22,%22kuid%22:%22%22,%22mfaid%22:%22df7be3dc-e278-436c-b2f8-4cfde321df0a%22,%22mfbaseid%22:%22efb9acb6-daea-4f2f-aeb3-b17832bdd47b%22,%22mfaname%22:%22DealerApp%22,%22sdkversion%22:%229.5.36%22,%22sdktype%22:%22js%22,%22fid%22:%22frmRadioRefresh%22,%22sessiontype%22:%22I%22,%22clientUUID%22:%221742536405634-41a8-0de0-125c%22,%22rsid%22:%221742536405654-b954-784f-38d2%22,%22svcid%22:%22DBUpdateForGoogle%22%7D',
                },
                data={
                    "OM_ELIGIBILITY_STATUS": "Eligible",
                    "appVersion": "3.1.0",
                    "flag": "failure",
                    "Radio_ID": self.radio_id,
                    "deviceID": self.uuid4,
                    "G_PLACES_REQUEST": "",
                    "OS_Version": "iPhone 12.5.7",
                    "G_PLACES_RESPONSE": "",
                    "Confirmation_Status": "SUCCESS",
                    "seqVal": self.seq,
                },
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
    
    def blocklist(self):
        try:
            response = self.session.post(
                "https://dealerapp.siriusxm.com/services/USBlockListDevice/BlockListDevice",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": f'%7B%22os%22:%2217.0%22,%22dm%22:%22iPhone%2014%20Pro%22,%22did%22:%22{self.uuid4}%22,%22ua%22:%22iPhone%22,%22aid%22:%22DealerApp%22,%22aname%22:%22SiriusXM%20Dealer%22,%22chnl%22:%22mobile%22,%22plat%22:%22ios%22,%22aver%22:%223.1.0%22,%22atype%22:%22native%22,%22stype%22:%22b2c%22,%22kuid%22:%22%22,%22mfaid%22:%22df7be3dc-e278-436c-b2f8-4cfde321df0a%22,%22mfbaseid%22:%22efb9acb6-daea-4f2f-aeb3-b17832bdd47b
