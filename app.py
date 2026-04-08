from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import random
import time
import os
import pickle
import requests

app = Flask(__name__)
app.secret_key = 'smart_electricity_theft_secret'

# ---------------- EMAIL CONFIG (RESEND) ----------------
RESEND_API_KEY = os.getenv("RESEND_API_KEY")

# ---------------- TEMP STORAGE ----------------
temp_otps = {} # {email: otp}
verified_email = None # Store globally for simplicity as per requirement 2.2

# ---------------- ML MODEL LOAD ----------------
model_path = os.path.join(os.path.dirname(__file__), "model.pkl")
model = pickle.load(open(model_path, "rb"))

def predict_theft(current, power):
    try:
        result = model.predict([[float(current), float(power)]])
        return bool(result[0])
    except:
        return False

# ---------------- DATA STORAGE ----------------
latest_data = {
    'voltage': 0,
    'current': 0,
    'power': 0,
    'energy': 0,
    'api_key': None,
    'last_update': 0,
    'theft': False
}

generated_api_key = None

# ---------------- LOGIN ----------------
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_api():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if username == 'admin' and password == '1234':
        session['user'] = 'admin'
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Invalid credentials'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')
    return render_template('dashboard.html')

# ---------------- API KEY ----------------
@app.route('/generate-key')
def generate_key():
    key = "NK" + str(random.randint(100000, 999999))
    return jsonify({"api_key": key})

@app.route('/api/validate-key', methods=['POST'])
def validate_key():
    global generated_api_key
    data = request.json
    api_key = data.get('api_key')

    if not api_key:
        return jsonify({"success": False, "message": "No API key provided"})

    if api_key == generated_api_key:
        return jsonify({"success": True})
    
    return jsonify({"success": False, "message": "Invalid API Key"})

# ---------------- ESP32 DATA RECEIVE ----------------
@app.route('/data', methods=['POST'])
def receive_data():
    global latest_data

    data = request.json

    if not data:
        return jsonify({"status": "error", "message": "No data received"}), 400

    # API key check
   #if data.get("api_key") != generated_api_key:
       #return jsonify({"status": "error", "message": "Invalid API Key"}), 403

    latest_data['voltage'] = data.get('voltage', 0)
    latest_data['current'] = data.get('current', 0)
    latest_data['power'] = data.get('power', 0)
    latest_data['energy'] = data.get('energy', 0)
    latest_data['api_key'] = data.get('api_key')
    latest_data['last_update'] = int(time.time() * 1000)

    return jsonify({"status": "success"})

# ---------------- GET DATA (FRONTEND) ----------------
@app.route('/api/latest')
def get_latest():
    global latest_data

    now = int(time.time() * 1000)

    # 1️⃣ No API key → DEMO MODE
    if latest_data['api_key'] is None:
        return jsonify({
            "voltage": random.uniform(220, 240),
            "current": random.uniform(1, 5),
            "power": random.uniform(200, 800),
            "energy": random.uniform(10, 20),
            "theft": False,
            "last_update": now,
            "is_real": False
        })

    # 2️⃣ API key iruku but data illa → WAIT MODE
    if latest_data['last_update'] == 0:
        return jsonify({
            "voltage": 0,
            "current": 0,
            "power": 0,
            "energy": 0,
            "theft": False,
            "last_update": now,
            "is_real": False
        })

    # 3️⃣ REAL DATA MODE 🔥
    theft = predict_theft(
        latest_data['current'],
        latest_data['power']
    )
    latest_data['theft'] = theft

    return jsonify({
        "voltage": latest_data['voltage'],
        "current": latest_data['current'],
        "power": latest_data['power'],
        "energy": latest_data['energy'],
        "theft": latest_data['theft'],
        "last_update": latest_data['last_update'],
        "is_real": True
    })

# ---------------- EMAIL FUNCTIONS ----------------
def send_otp_email(to_email, otp):
    try:
        import requests
        import os
        api_key = os.getenv("RESEND_API_KEY")
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "from": "onboarding@resend.dev",
                "to": [to_email],
                "subject": "OTP Verification",
                "html": f"<h3>Your OTP is: {otp}</h3>"
            }
        )
        print("RESEND RESPONSE:", response.text)
        return response.status_code == 200
    except Exception as e:
        print("EMAIL ERROR:", e)
        return False

def send_logs_email(email, logs):
    try:
        import requests
        import os
        api_key = os.getenv("RESEND_API_KEY")
        
        body_html = "<h3>Theft detected. See logs below:</h3><br>"
        for log in logs:
            body_html += f"<b>Time:</b> {log.get('time')}<br><b>Learned:</b> {log.get('learned_current')} A<br><b>Current Now:</b> {log.get('current')} A<br><b>Difference:</b> {log.get('difference')} A<br>"
            body_html += "-" * 30 + "<br>"

        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "from": "onboarding@resend.dev",
                "to": [email],
                "subject": "🚨 Smart Electricity Monitor - Theft Logs",
                "html": body_html
            }
        )
        print("RESEND RESPONSE (LOGS):", response.text)
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending logs email: {e}")
        return False

# ---------------- EMAIL ROUTES ----------------
@app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({"success": False, "message": "Email required"}), 400

    otp = random.randint(100000, 999999)

    success = send_otp_email(email, otp)

    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "Email failed"}), 500

@app.route('/verify-otp', methods=['POST'])
def verify_otp_api():
    global verified_email
    data = request.json
    email = data.get('email')
    otp = data.get('otp')
    
    if email in temp_otps and temp_otps[email] == otp:
        verified_email = email
        del temp_otps[email]
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Invalid OTP"})

@app.route('/send-logs', methods=['POST'])
def send_logs_api():
    # If frontend sends logs, use them. Otherwise, we don't have them in backend.
    data = request.json
    logs = data.get('logs', [])
    
    if not verified_email:
        return jsonify({"success": False, "message": "Email not verified"})
    
    if not logs:
        return jsonify({"success": False, "message": "No logs to send"})
    
    if send_logs_email(verified_email, logs):
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Failed to send logs email"})

# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)