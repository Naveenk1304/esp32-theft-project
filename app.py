from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import os
import datetime
import time
import smtplib
from email.mime.text import MIMEText
import random
from model import TheftDetector

app = Flask(__name__)
# Enable CORS for frontend integration
CORS(app)

# --- CONFIGURATION ---

EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
print("EMAIL_USER:", EMAIL_USER)
print("EMAIL_PASS:", EMAIL_PASS)

# Persistence: Stored in memory (could be file for true persistence across restarts)
LAST_SEEN_TIME = 0 # Unix timestamp of last received sensor data

# Temporary OTP Store {email: otp}
OTP_STORE = {}

# Initialize AI Detector
detector = TheftDetector()

def get_sensor_status():
    """Returns True if data received in last 10 seconds"""
    if LAST_SEEN_TIME == 0:
        return False
    # Check if last seen was within 10 seconds
    return (time.time() - LAST_SEEN_TIME) < 10

def send_email(to_email, subject, message):
    try:
        msg = MIMEText(message)
        msg['Subject'] = subject
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, to_email, msg.as_string())
        server.quit()
        return True, "success"
         except Exception as e:
        print("FULL EMAIL ERROR:", str(e))  # 🔥 IMPORTANT
        return False

@app.route("/")
def index():
    return send_file("sms-alert-bot.html")

@app.route("/dashboard")
def dashboard():
    return send_file("dashboard.html")
    

@app.route("/sensor-status", methods=['GET'])
def sensor_status():
    """New API: Returns connection state and last seen time"""
    email = request.args.get('email') # Accepted but not used for filtering yet
    is_connected = get_sensor_status()
    return jsonify({
        "esp_connected": is_connected,
        "last_seen": datetime.datetime.fromtimestamp(LAST_SEEN_TIME).strftime('%Y-%m-%d %H:%M:%S') if LAST_SEEN_TIME > 0 else "Never"
    })

@app.route("/send-otp", methods=['POST'])
def send_otp():
    try:
        data = request.get_json()
        email = data.get('email')

        print("Trying to send OTP to:", email)  # ✅ HERE

        if not email:
            return jsonify({"status": "error", "message": "Email required"}), 400

        otp = str(random.randint(100000, 999999))
        OTP_STORE[email] = otp

        print(f"OTP for {email}: {otp}")

        success, err = send_email(email, "🔐 Verification Code", f"Your OTP is: {otp}")

        return jsonify({
            "status": "success" if success else "error",
            "message": "OTP Sent" if success else err
        })

    except Exception as e:
        print("SEND OTP ERROR:", str(e))  # 🔥 add this also
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/verify-otp", methods=['POST'])
def verify_otp():
    try:
        data = request.get_json()
        email = data.get('email')
        otp = data.get('otp')
        if OTP_STORE.get(email) == str(otp):
            del OTP_STORE[email]
            return jsonify({"status": "success", "verified": True, "email": email})
        return jsonify({"status": "error", "message": "Invalid OTP"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/data', methods=['POST'])
def receive_data():
    """Receives ESP32 data and updates last_seen"""
    global LAST_SEEN_TIME
    try:
        data = request.get_json()
        if not data: return jsonify({"status": "error", "message": "No data"}), 400

        # Update sensor heartbeat
        LAST_SEEN_TIME = time.time()

        current = float(data.get('current', 0))
        power = float(data.get('power', 0))
        energy = float(data.get('energy', 0))
        email = data.get('email') # Receiver email from request
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Run AI ONLY if connected (implicitly true if we are here)
        prediction_code = detector.predict(current, power, energy)
        prediction_text = "THEFT" if prediction_code == 1 else "NORMAL"

        # Save data
        row = {"timestamp": timestamp, "current": current, "power": power, "energy": energy, "prediction": prediction_text}
        pd.DataFrame([row]).to_csv(LIVE_DATA_FILE, mode='a', header=not os.path.exists(LIVE_DATA_FILE), index=False)

        # Alert receiver if email provided
        if prediction_code == 1 and email:
            body = f"🚨 Theft Alert!\nCurrent: {current}A\nPower: {power}W\nTime: {timestamp}"
            send_email(email, "⚠️ Electricity Theft Detected", body)

        return jsonify({"status": "success", "prediction": prediction_text})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/status', methods=['GET'])
def get_status():
    """Updated status: Checks real ESP32 connection"""
    email = request.args.get('email')
    is_connected = get_sensor_status()
    return jsonify({
        "esp_connected": is_connected,
        "ai_running": (is_connected and detector.model is not None)
    })

@app.route('/history', methods=['GET'])
def get_history():
    email = request.args.get('email')
    if not os.path.exists(LIVE_DATA_FILE): return jsonify([])
    return jsonify(pd.read_csv(LIVE_DATA_FILE).tail(30).to_dict(orient='records'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
