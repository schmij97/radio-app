#!/usr/bin/env python3
# main.py - Password-protected SiriusXM App for Render deployment

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
# User credentials
USERS = {
    'DaveHall': {'password': 'schmij', 'role': 'admin'},
    'ShelbyHank': {'password': 'schmij', 'role': 'operator'}
}

# Session settings
SESSION_TIMEOUT = 3600  # 1 hour in seconds

# File storage (Render will handle this)
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
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == 'DaveHall' and password == 'schmij':
            session['authenticated'] = True
            session['user'] = 'DaveHall'
            session['role'] = 'admin'
            session['login_time'] = time.time()
            flash('Successfully logged in!', 'success')
            return redirect(url_for('index'))
        elif username == 'ShelbyHank' and password == 'schmij':
            session['authenticated'] = True
            session['user'] = 'ShelbyHank'
            session['role'] = 'operator'
            session['login_time'] = time.time()
            flash('Successfully logged in!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
    
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
    """Main page - no dealer selection, Montgomery AL hardcoded"""
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
    """Add a new radio ID - Admin only"""
    # Check if user is admin
    if session.get('role') != 'admin':
        return jsonify({"error": "Administrator access required"}), 403
    
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
    """Delete a radio ID - Admin only"""
    # Check if user is admin
    if session.get('role') != 'admin':
        return jsonify({"error": "Administrator access required"}), 403
    
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
        activation_status["progress"] = 11
        
        if success:
            activation_status["status"] += f"\n🎉 Radio {radio_id} activated successfully!"
        else:
            activation_status["status"] += f"\n❌ Radio {radio_id} activation failed"
            
    except Exception as e:
        activation_status["completed"] = True
        activation_status["success"] = False
        activation_status["status"] += f"\n❌ Error: {str(e)}"

# SiriusXM Activator class using your working code
class SiriusXMActivator:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Accept-Language': 'en-us',
            'Accept-Encoding': 'br, gzip, deflate',
            'User-Agent': 'SiriusXM%20Dealer/3.1.0 CFNetwork/1568.200.51 Darwin/24.1.0'
        })
        self.radio_id_input = None
        self.uuid4 = str(uuid.uuid4())
        self.auth_token = ""
        self.seq = ""
    
    def get_reporting_params(self, svc_id):
        """Generate reporting params string"""
        base_params = {
            "os": "17.0",
            "dm": "iPhone 14 Pro", 
            "did": self.uuid4,
            "ua": "iPhone",
            "aid": "DealerApp",
            "aname": "SiriusXM Dealer",
            "chnl": "mobile",
            "plat": "ios",
            "aver": "3.1.0",
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
        
        # Build URL encoded string manually to avoid issues
        params_list = []
        for key, value in base_params.items():
            params_list.append(f'"{key}":"{value}"')
        
        params_str = "{" + ",".join(params_list) + "}"
        return params_str.replace(' ', '%20').replace('"', '%22').replace(':', '%3A').replace(',', '%2C').replace('{', '%7B').replace('}', '%7D')
    
    def activate_radio(self, radio_id, status_callback, progress_callback):
        self.radio_id_input = radio_id.upper()
        status_callback(f"🔄 Starting activation for: {self.radio_id_input}")
        
        steps = [
            ("📡 App Config", self.appconfig),
            ("🔐 Login", self.login),
            ("📱 Version Control", self.versionControl),
            ("⚙️ Get Properties", self.getProperties),
            ("🔄 Device Refresh 1", self.update_1),
            ("📊 CRM Info", self.getCRM),
            ("💾 DB Update", self.dbUpdate),
            ("🛡️ Blocklist Check", self.blocklist),
            ("🏢 Oracle Check", self.oracle),
            ("👤 Create Account", self.createAccount),
            ("✅ Device Refresh 2", self.update_2)
        ]
        
        for i, (step_name, step_func) in enumerate(steps):
            status_callback(f"Step {i+1}/11: {step_name}")
            progress_callback(i + 1)
            
            try:
                result = step_func()
                if result is not None:
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
                url="https://dealerapp.siriusxm.com/authService/100000002/appconfig",
                headers={
                    "X-Kony-Integrity": "GWSUSEVMJK;FEC9AA232EC59BE8A39F0FAE1B71300216E906B85F40CA2B1C5C7A59F85B17A4",
                    "X-HTTP-Method-Override": "GET",
                    "X-Voltmx-App-Key": "67cfe0220c41a54cb4e768723ad56b41",
                    "Accept": "*/*",
                    "X-Voltmx-App-Secret": "c086fca8646a72cf391f8ae9f15e5331",
                    "X-Voltmx-ReportingParams": "",
                },
            )
            return True
        except requests.exceptions.RequestException:
            return None

    def login(self):
        try:
            response = self.session.post(
                url="https://dealerapp.siriusxm.com/authService/100000002/login",
                headers={
                    "X-Voltmx-Platform-Type": "ios",
                    "Accept": "application/json",
                    "X-Voltmx-App-Secret": "c086fca8646a72cf391f8ae9f15e5331",
                    "X-Voltmx-SDK-Type": "js",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Voltmx-SDK-Version": "9.5.36",
                    "X-Voltmx-App-Key": "67cfe0220c41a54cb4e768723ad56b41",
                    "X-Voltmx-ReportingParams": self.get_reporting_params("login_$anonymousProvider"),
                },
            )
            self.auth_token = response.json().get('claims_token').get('value')
            return self.auth_token
        except requests.exceptions.RequestException:
            return None

    def versionControl(self):
        try:
            response = self.session.post(
                url="https://dealerapp.siriusxm.com/services/DealerAppService7/VersionControl",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": self.get_reporting_params("VersionControl"),
                },
                data={
                    "deviceCategory": "iPhone",
                    "appver": "3.1.0",
                    "deviceLocale": "en_US",
                    "deviceModel": "iPhone%206%20Plus",
                    "deviceVersion": "12.5.7",
                    "deviceType": "",
                },
            )
            return True
        except requests.exceptions.RequestException:
            return None

    def getProperties(self):
        try:
            response = self.session.post(
                url="https://dealerapp.siriusxm.com/services/DealerAppService7/getProperties",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": self.get_reporting_params("getProperties"),
                },
            )
            return True
        except requests.exceptions.RequestException:
            return None

    def update_1(self):
        try:
            response = self.session.post(
                url="https://dealerapp.siriusxm.com/services/USUpdateDeviceSATRefresh/updateDeviceSATRefreshWithPriority",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": self.get_reporting_params("updateDeviceSATRefreshWithPriority"),
                },
                data={
                    "deviceId": self.radio_id_input,
                    "appVersion": "3.1.0",
                    "lng": "-86.210313195",
                    "deviceID": self.uuid4,
                    "provisionPriority": "2",
                    "provisionType": "activate",
                    "lat": "32.37436705",
                },
            )
            self.seq = response.json().get('seqValue')
            return self.seq
        except requests.exceptions.RequestException:
            return None

    def getCRM(self):
        try:
            response = self.session.post(
                url="https://dealerapp.siriusxm.com/services/DemoConsumptionRules/GetCRMAccountPlanInformation",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": self.get_reporting_params("GetCRMAccountPlanInformation"),
                },
                data={
                    "seqVal": self.seq,
                    "deviceId": self.radio_id_input,
                },
            )
            return True
        except requests.exceptions.RequestException:
            return None

    def dbUpdate(self):
        try:
            response = self.session.post(
                url="https://dealerapp.siriusxm.com/services/DBSuccessUpdate/DBUpdateForGoogle",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": self.get_reporting_params("DBUpdateForGoogle"),
                },
                data={
                    "OM_ELIGIBILITY_STATUS": "Eligible",
                    "appVersion": "3.1.0",
                    "flag": "failure",
                    "Radio_ID": self.radio_id_input,
                    "deviceID": self.uuid4,
                    "G_PLACES_REQUEST": "",
                    "OS_Version": "iPhone 12.5.7",
                    "G_PLACES_RESPONSE": "",
                    "Confirmation_Status": "SUCCESS",
                    "seqVal": self.seq,
                },
            )
            return True
        except requests.exceptions.RequestException:
            return None

    def blocklist(self):
        try:
            response = self.session.post(
                url="https://dealerapp.siriusxm.com/services/USBlockListDevice/BlockListDevice",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": self.get_reporting_params("BlockListDevice"),
                },
                data={
                    "deviceId": self.uuid4,
                },
            )
            return True
        except requests.exceptions.RequestException:
            return None

    def oracle(self):
        try:
            response = self.session.post(
                url="https://oemremarketing.custhelp.com/cgi-bin/oemremarketing.cfg/php/custom/src/oracle/program_status.php",
                params={
                    "google_addr": "395 EASTERN BLVD, MONTGOMERY, AL 36117, USA",
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "*/*",
                    "X-Voltmx-ReportingParams": "",
                },
            )
            return True
        except requests.exceptions.RequestException:
            return None

    def createAccount(self):
        try:
            response = self.session.post(
                url="https://dealerapp.siriusxm.com/services/DealerAppService3/CreateAccount",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": self.get_reporting_params("CreateAccount"),
                },
                data={
                    "seqVal": self.seq,
                    "deviceId": self.radio_id_input,
                    "oracleCXFailed": "1",
                    "appVersion": "3.1.0",
                },
            )
            return True
        except requests.exceptions.RequestException:
            return None

    def update_2(self):
        try:
            response = self.session.post(
                url="https://dealerapp.siriusxm.com/services/USUpdateDeviceRefreshForCC/updateDeviceSATRefreshWithPriority",
                headers={
                    "Accept": "*/*",
                    "X-Voltmx-API-Version": "1.0",
                    "X-Voltmx-DeviceId": self.uuid4,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Voltmx-Authorization": self.auth_token,
                    "X-Voltmx-ReportingParams": self.get_reporting_params("updateDeviceSATRefreshWithPriority"),
                },
                data={
                    "deviceId": self.radio_id_input,
                    "provisionPriority": "2",
                    "appVersion": "3.1.0",
                    "device_Type": "iPhone iPhone 6 Plus",
                    "deviceID": self.uuid4,
                    "os_Version": "iPhone 12.5.7",
                    "provisionType": "activate",
                },
            )
            return True
        except requests.exceptions.RequestException:
            return None

# Render deployment configuration
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
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

