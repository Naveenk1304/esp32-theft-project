from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import random
import time
import os
import requests
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'smart_electricity_theft_secret')

# ---------------- TELEGRAM CONFIG ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ---------------- SYSTEM STATE ----------------
# Use global dictionary for simplicity, but session for user-specific data
system_state = {
    'latest_data': {
        'voltage': 0,
        'current': 0,
        'power': 0,
        'energy': 0,
        'last_update': 0
    },
    'sensor_connected': False,
    'learned_current': None,
    'theft_logs': [],
    'is_theft_active': False
}

# ---------------- HELPER FUNCTIONS ----------------
def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[ERROR] Telegram config missing")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}")

def send_theft_summary():
    if not system_state['theft_logs']:
        return
    
    summary = "🚨 *Theft Alert Summary*\n\n"
    for log in system_state['theft_logs'][-5:]: # Last 5 logs
        summary += f"📅 {log['timestamp']}\n"
        summary += f"💡 Learned: {log['learned_current']}A\n"
        summary += f"🔥 Current: {log['current_now']}A\n"
        summary += f"⚠️ Diff: {log['difference']}A\n\n"
    
    send_telegram_msg(summary)

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
        # Reset session key on login if not already set (re-login generates new key if needed?)
        # User requirement: "API key must be generated ONLY ONCE per login session"
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
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    if 'api_key' not in session:
        session['api_key'] = "NK-" + str(random.randint(100000, 999999))
    
    return jsonify({"api_key": session['api_key']})

# ---------------- ESP32 DATA RECEIVE ----------------
@app.route('/data', methods=['POST'])
def receive_data():
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No data received"}), 400

    api_key = data.get('api_key')
    # Validation logic: If there's a session with this API key
    # Since multiple users might be logged in, we check if this key exists in system or session
    # But Flask sessions are browser-side. To validate ESP data, we need a server-side storage of valid keys.
    # For simplicity, since the user requirement implies a single user login system, 
    # we can use a global variable or store the current active key.
    
    # Let's use a simple global valid_api_key for ESP validation
    # Actually, the user says "API key must be generated ONLY ONCE per login session".
    # And "ESP sends data to backend with API key. Validate API key. If valid -> sensor_connected = True".
    
    # We'll check against session['api_key'] if we can access it, but /data is called by ESP.
    # ESP doesn't have the user's session cookie.
    # So we need to store the generated key in a way that /data can access it.
    
    global active_api_key
    if 'active_api_key' not in globals():
        active_api_key = None
    
    # When a key is generated, we set active_api_key
    # (This is a simplification, but fits the "single user" or "last generated" context)
    
    if not api_key or api_key != active_api_key:
        return jsonify({"status": "error", "message": "Invalid API Key"}), 403

    system_state['sensor_connected'] = True
    system_state['latest_data']['voltage'] = data.get('voltage', 0)
    system_state['latest_data']['current'] = float(data.get('current', 0))
    system_state['latest_data']['power'] = float(data.get('power', 0))
    system_state['latest_data']['energy'] = data.get('energy', 0)
    system_state['latest_data']['last_update'] = int(time.time() * 1000)

    # Theft Detection
    if system_state['learned_current'] is not None:
        current_now = system_state['latest_data']['current']
        learned = system_state['learned_current']
        threshold = 0.05 # Minimum noise threshold
        
        if current_now > learned + threshold:
            if not system_state['is_theft_active']:
                system_state['is_theft_active'] = True
                send_telegram_msg(f"🚨 *Theft Detected!* Current: {current_now}A")
            
            log = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'learned_current': round(learned, 3),
                'current_now': round(current_now, 3),
                'difference': round(current_now - learned, 3)
            }
            system_state['theft_logs'].append(log)
        else:
            if system_state['is_theft_active']:
                system_state['is_theft_active'] = False
                send_theft_summary() # Send summary when theft session ends

    return jsonify({"status": "success"})

# ---------------- API ENDPOINTS ----------------
@app.route('/api/latest')
def get_latest():
    now = int(time.time() * 1000)
    
    # Check if key is generated
    key_generated = 'api_key' in session
    
    if not system_state['sensor_connected']:
        # DEMO MODE
        return jsonify({
            "voltage": 230.5 + random.uniform(-0.5, 0.5),
            "current": 1.2 + random.uniform(-0.02, 0.02),
            "power": 276.6 + random.uniform(-5, 5),
            "energy": 12.45,
            "theft": False,
            "status": "Sensor Not Connected",
            "ai_status": "AI Not Running",
            "sensor_connected": False,
            "is_real": False,
            "api_key": session.get('api_key', "NOT GENERATED"),
            "last_update": now
        })
    
    # REAL MODE
    ai_status = "AI Ready"
    if system_state['learned_current'] is not None:
        ai_status = "AI Running"
    
    return jsonify({
        "voltage": system_state['latest_data']['voltage'],
        "current": system_state['latest_data']['current'],
        "power": system_state['latest_data']['power'],
        "energy": system_state['latest_data']['energy'],
        "theft": system_state['is_theft_active'],
        "status": "Sensor Connected",
        "ai_status": ai_status,
        "sensor_connected": True,
        "is_real": True,
        "api_key": session.get('api_key'),
        "last_update": system_state['latest_data']['last_update'],
        "learned_current": system_state['learned_current'],
        "theft_logs": system_state['theft_logs']
    })

@app.route('/api/learn', methods=['POST'])
def learn_pattern():
    data = request.json
    avg_current = data.get('average_current')
    if avg_current is not None:
        system_state['learned_current'] = float(avg_current)
        return jsonify({"success": True, "learned_current": system_state['learned_current']})
    return jsonify({"success": False}), 400

@app.route('/api/send-logs', methods=['POST'])
def manual_send_logs():
    if system_state['theft_logs']:
        send_theft_summary()
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "No logs to send"})

@app.route('/api/set-active-key', methods=['POST'])
def set_active_key():
    # Helper to sync session key to global active_key for ESP validation
    global active_api_key
    data = request.json
    key = data.get('api_key')
    if key:
        active_api_key = key
        return jsonify({"success": True})
    return jsonify({"success": False})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
