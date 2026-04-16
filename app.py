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

# ---------------- LOG SYSTEM (MINUTE AVERAGING) ----------------
# We only store 1 log per minute during theft.
current_minute_data = {
    'minute_timestamp': None,
    'readings': []
}

# ---------------- HELPER FUNCTIONS ----------------
def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[ERROR] Telegram config missing")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}")

def send_theft_summary():
    if not system_state['theft_logs']:
        return
    summary = "🚨 *Theft Alert Summary*\n\n"
    for log in system_state['theft_logs'][-5:]: # Last 5 logs
        summary += f"📅 {log['timestamp']}\n💡 Learned: {log['learned_current']}A\n🔥 Current: {log['current_now']}A\n⚠️ Diff: {log['difference']}A\n\n"
    send_telegram_msg(summary)

# ---------------- LOGIN ----------------
@app.route('/')
def index():
    if 'user' in session: return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_api():
    data = request.json
    if data.get('username') == 'admin' and data.get('password') == '1234':
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
    if 'user' not in session: return redirect('/')
    return render_template('dashboard.html')

# ---------------- API KEY ----------------
@app.route('/generate-key')
def generate_key():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    if 'api_key' not in session:
        session['api_key'] = "NK-" + str(random.randint(100000, 999999))
    return jsonify({"api_key": session['api_key']})

# ---------------- ESP32 DATA RECEIVE ----------------
@app.route('/data', methods=['POST'])
def receive_data():
    data = request.json
    api_key = data.get('api_key')
    
    global active_api_key
    if 'active_api_key' not in globals(): active_api_key = None
    
    if not api_key or api_key != active_api_key:
        return jsonify({"status": "error", "message": "Invalid API Key"}), 403

    system_state['sensor_connected'] = True
    system_state['latest_data'].update({
        'voltage': float(data.get('voltage', 0)),
        'current': float(data.get('current', 0)),
        'power': float(data.get('power', 0)),
        'energy': float(data.get('energy', 0)),
        'last_update': int(time.time() * 1000)
    })

    # Theft Detection & Log Averaging
    if system_state['learned_current'] is not None:
        current_now = system_state['latest_data']['current']
        learned = system_state['learned_current']
        threshold = 0.05
        
        if current_now > learned + threshold:
            if not system_state['is_theft_active']:
                system_state['is_theft_active'] = True
                send_telegram_msg(f"🚨 *Theft Detected!* Current: {current_now}A")
            
            # Minute-based logging logic
            now = datetime.now()
            minute_key = now.strftime("%Y-%m-%d %H:%M")
            
            if current_minute_data['minute_timestamp'] != minute_key:
                # If we have data from the previous minute, save it
                if current_minute_data['readings']:
                    avg_reading = sum(current_minute_data['readings']) / len(current_minute_data['readings'])
                    system_state['theft_logs'].append({
                        'timestamp': current_minute_data['minute_timestamp'] + ":00",
                        'learned_current': round(learned, 3),
                        'current_now': round(avg_reading, 3),
                        'difference': round(avg_reading - learned, 3)
                    })
                # Reset for new minute
                current_minute_data['minute_timestamp'] = minute_key
                current_minute_data['readings'] = [current_now]
            else:
                current_minute_data['readings'].append(current_now)
        else:
            if system_state['is_theft_active']:
                system_state['is_theft_active'] = False
                # Final log for the current minute if theft ends
                if current_minute_data['readings']:
                    avg_reading = sum(current_minute_data['readings']) / len(current_minute_data['readings'])
                    system_state['theft_logs'].append({
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'learned_current': round(learned, 3),
                        'current_now': round(avg_reading, 3),
                        'difference': round(avg_reading - learned, 3)
                    })
                    current_minute_data['readings'] = []
                    current_minute_data['minute_timestamp'] = None
                send_theft_summary()

    return jsonify({"status": "success"})

# ---------------- API ENDPOINTS ----------------
@app.route('/api/latest')
def get_latest():
    now_ms = int(time.time() * 1000)
    
    # 10s Connectivity Timeout Logic
    if system_state['sensor_connected'] and (now_ms - system_state['latest_data']['last_update'] > 10000):
        # RESET SYSTEM ON DISCONNECT
        system_state['sensor_connected'] = False
        system_state['latest_data'].update({'voltage': 0, 'current': 0, 'power': 0, 'energy': 0})
        system_state['learned_current'] = None # Stop AI
        system_state['is_theft_active'] = False
        # Do NOT clear theft_logs so they can still be seen in the table if they exist

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
            "last_update": now_ms
        })
    
    # REAL MODE
    return jsonify({
        **system_state['latest_data'],
        "theft": system_state['is_theft_active'],
        "status": "Sensor Connected",
        "ai_status": "AI Running" if system_state['learned_current'] is not None else "AI Ready",
        "sensor_connected": True,
        "is_real": True,
        "api_key": session.get('api_key'),
        "learned_current": system_state['learned_current'],
        "theft_logs": system_state['theft_logs']
    })

@app.route('/api/learn', methods=['POST'])
def learn_pattern():
    if not system_state['sensor_connected']:
        return jsonify({"success": False, "message": "Sensor not connected"}), 400
    
    avg = request.json.get('average_current')
    if avg is not None:
        system_state['learned_current'] = float(avg)
        return jsonify({"success": True})
    return jsonify({"success": False}), 400

@app.route('/api/send-logs', methods=['POST'])
def manual_send_logs():
    if system_state['theft_logs']:
        send_theft_summary()
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "No logs to send"})

@app.route('/api/set-active-key', methods=['POST'])
def set_active_key():
    global active_api_key
    active_api_key = request.json.get('api_key')
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
