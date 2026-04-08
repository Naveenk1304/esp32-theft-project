from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import random
import time
import os
import pickle
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = 'smart_electricity_theft_secret'

# ---------------- EMAIL CONFIG ----------------
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "pandi40512@gmail.com"  # Replace with your email
SENDER_PASSWORD = "vmqrcjniojnkoytt" # Replace with your app password

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
    
    # If no data or data is older than 5 seconds, switch to demo data
    is_real = latest_data['api_key'] is not None and (now - latest_data['last_update']) < 5000

    if not is_real:
        latest_data['voltage'] = random.uniform(220, 240)
        latest_data['current'] = random.uniform(1, 5)
        latest_data['power'] = random.uniform(200, 800)
        latest_data['energy'] = random.uniform(10, 20)
        # Note: we don't update last_update here so it stays stale for sensor check

    # ML prediction
    theft = predict_theft(latest_data['current'], latest_data['power'])
    latest_data['theft'] = theft

    return jsonify({
        "voltage": latest_data['voltage'],
        "current": latest_data['current'],
        "power": latest_data['power'],
        "energy": latest_data['energy'],
        "theft": latest_data['theft'],
        "last_update": latest_data['last_update'],
        "is_real": is_real
    })

# ---------------- EMAIL FUNCTIONS ----------------
def send_otp_email(email, otp):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = email
    msg['Subject'] = "Your OTP for Smart Electricity Monitor Setup"
    
    body = f"Your OTP for verification is: {otp}"
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending OTP email: {e}")
        return False

def send_logs_email(email, logs):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = email
    msg['Subject'] = "🚨 Smart Electricity Monitor - Theft Logs"
    
    body = "Theft detected. See logs below:\n\n"
    for log in logs:
        body += f"Time: {log.get('time')}\nLearned: {log.get('learned_current')} A\nCurrent Now: {log.get('current')} A\nDifference: {log.get('difference')} A\n"
        body += "-" * 30 + "\n"
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending logs email: {e}")
        return False

# ---------------- EMAIL ROUTES ----------------
@app.route('/send-otp', methods=['POST'])
def send_otp_api():
    email = request.json.get('email')
    if not email:
        return jsonify({"success": False, "message": "Email is required"})
    
    otp = str(random.randint(100000, 999999))
    temp_otps[email] = otp
    
    if send_otp_email(email, otp):
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Failed to send email"})

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