from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import random
import time
import os
import threading
from collections import deque
from twilio.rest import Client
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'smart_electricity_theft_secret')

# ---------------- TWILIO CONFIG ----------------
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER") 
RECIPIENT_PHONE_NUMBER = os.getenv("RECIPIENT_PHONE_NUMBER")

# ---------------- THEFT TRACKING ----------------
readings_history = deque(maxlen=50)
theft_logs = []
is_theft_active = False
theft_timer = None

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

# ---------------- HELPER FUNCTIONS ----------------
def send_whatsapp(message):
    try:
        if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, RECIPIENT_PHONE_NUMBER]):
            print("[ERROR] Twilio credentials missing in environment variables.")
            return

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            body=message,
            from_=f"whatsapp:{TWILIO_PHONE_NUMBER}",
            to=f"whatsapp:{RECIPIENT_PHONE_NUMBER}"
        )
        print(f"[DEBUG] WhatsApp sent: {msg.sid}")
    except Exception as e:
        print(f"[ERROR] WhatsApp failed: {e}")

def send_summary_and_clear():
    global theft_logs
    if not theft_logs:
        return
    
    summary = "🚨 *Smart Electricity Monitor - Theft Summary*\n\n"
    for log in theft_logs:
        summary += f"• {log['timestamp']}: {log['current']}A, {log['power']}W\n"
    
    send_whatsapp(summary)
    theft_logs = []
    print("[DEBUG] Theft summary sent and logs cleared.")

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
    global generated_api_key
    generated_api_key = "NK" + str(random.randint(100000, 999999))
    return jsonify({"api_key": generated_api_key})

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
    global latest_data, readings_history, theft_logs, is_theft_active, theft_timer

    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No data received"}), 400

    try:
        current = float(data.get('current', 0))
        power = float(data.get('power', 0))
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Invalid data format"}), 400

    # Update latest data
    latest_data['voltage'] = data.get('voltage', 0)
    latest_data['current'] = current
    latest_data['power'] = power
    latest_data['energy'] = data.get('energy', 0)
    latest_data['api_key'] = data.get('api_key')
    latest_data['last_update'] = int(time.time() * 1000)

    # ML Detection (Dynamic Average)
    avg_current = sum(readings_history) / len(readings_history) if readings_history else 0
    theft = False
    
    # Require at least 5 readings to establish a baseline average
    if len(readings_history) >= 5:
         if current > 1.5 * avg_current and current > 0.05: # current > 0.05 to avoid noise triggers
             theft = True

    # Update history
    readings_history.append(current)
    latest_data['theft'] = theft

    if theft:
        print(f"[DEBUG] Theft Detected! Current: {current}A, Avg: {avg_current:.2f}A")
        theft_logs.append({
            'timestamp': datetime.now().strftime("%H:%M:%S"),
            'current': current,
            'power': power
        })
        
        # Immediate alert if transition to theft
        if not is_theft_active:
            is_theft_active = True
            if theft_timer:
                theft_timer.cancel()
                theft_timer = None
            send_whatsapp(f"🚨 *Theft Alert!* \nDetected: {current}A \nAverage: {avg_current:.2f}A")
    else:
        # Check transition from theft to normal
        if is_theft_active:
            print("[DEBUG] System back to normal. Starting 10s timer for logs.")
            is_theft_active = False
            # Wait 10 seconds before sending full summary (non-blocking)
            theft_timer = threading.Timer(10.0, send_summary_and_clear)
            theft_timer.start()

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
    return jsonify({
        "voltage": latest_data['voltage'],
        "current": latest_data['current'],
        "power": latest_data['power'],
        "energy": latest_data['energy'],
        "theft": latest_data['theft'],
        "last_update": latest_data['last_update'],
        "is_real": True
    })

# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
