from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import random
import time
import os
import requests
import json
import threading
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'smart_electricity_theft_secret')

# ---------------- CONFIG ----------------
DB_FILE = "db.json"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ---------------- IST TIME HELPER ----------------
def get_ist_time():
    # Assuming the environment might not have pytz
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def format_ist(dt):
    return dt.strftime("%d-%b-%Y %I:%M %p IST")

# ---------------- DATABASE SYSTEM ----------------
class Database:
    def __init__(self, filename):
        self.filename = filename
        self.lock = threading.Lock()
        if not os.path.exists(self.filename):
            self.data = {
                "ai_model": {
                    "avgVoltage": 0.0,
                    "avgCurrent": 0.0,
                    "avgPower": 0.0,
                    "sampleCount": 0,
                    "trained": False,
                    "learningStartTime": None
                },
                "theft_logs": [],
                "continuous_logs": [],
                "telegram_history": [],
                "active_api_key": None
            }
            self.save()
        else:
            self.load()

    def load(self):
        with self.lock:
            with open(self.filename, 'r') as f:
                self.data = json.load(f)

    def save(self):
        with self.lock:
            with open(self.filename, 'w') as f:
                json.dump(self.data, f, indent=4)

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value
        self.save()

db = Database(DB_FILE)

# ---------------- MONITORING SERVICE ----------------
class MonitoringService:
    def __init__(self):
        self.latest_data = {
            'voltage': 0, 'current': 0, 'power': 0, 'energy': 0, 'last_update': 0
        }
        self.status = "Power OFF"
        self.is_theft_active = False
        self.last_log_time = 0
        self.last_telegram_report = 0
        self.lock = threading.Lock()
        
        # Start background threads
        threading.Thread(target=self._background_loop, daemon=True).start()

    def update_data(self, data):
        with self.lock:
            self.latest_data.update({
                'voltage': float(data.get('voltage', 0)),
                'current': float(data.get('current', 0)),
                'power': float(data.get('power', 0)),
                'energy': float(data.get('energy', 0)),
                'last_update': time.time()
            })
            self._process_logic()

    def _process_logic(self):
        model = db.get("ai_model")
        current_data = self.latest_data
        
        # 1. Learning Logic
        if model.get("learningStartTime") and not model.get("trained"):
            self.status = "Learning Pattern"
            start_time = datetime.fromisoformat(model["learningStartTime"])
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            
            # EMA Smoothing: smoothed = (oldValue * 0.8) + (newValue * 0.2)
            if model["sampleCount"] == 0:
                model["avgVoltage"] = current_data["voltage"]
                model["avgCurrent"] = current_data["current"]
                model["avgPower"] = current_data["power"]
            else:
                model["avgVoltage"] = (model["avgVoltage"] * 0.8) + (current_data["voltage"] * 0.2)
                model["avgCurrent"] = (model["avgCurrent"] * 0.8) + (current_data["current"] * 0.2)
                model["avgPower"] = (model["avgPower"] * 0.8) + (current_data["power"] * 0.2)
            
            model["sampleCount"] += 1
            
            # min 10 mins (600s) OR min 1000 samples
            if elapsed >= 600 or model["sampleCount"] >= 1000:
                model["trained"] = True
                self.send_telegram_msg("✅ *Learning Complete!*\nAI is now monitoring the grid.")
            
            db.set("ai_model", model)

        # 2. Monitoring & Theft Detection
        elif model.get("trained"):
            self.status = "AI Monitoring"
            avg_current = model["avgCurrent"]
            if avg_current > 0:
                deviation = abs(current_data["current"] - avg_current) / avg_current
                if deviation > 0.50:
                    self.status = "Theft Alert"
                    if not self.is_theft_active:
                        self.is_theft_active = True
                        self._trigger_theft_alert(current_data, avg_current)
                else:
                    self.is_theft_active = False
        else:
            self.status = "AI READY"

    def _trigger_theft_alert(self, data, learned):
        ist_now = get_ist_time()
        timestamp = format_ist(ist_now)
        
        # Immediate Telegram Alert
        msg = f"🚨 *THEFT DETECTED!*\n\n" \
              f"Current: {data['current']}A\n" \
              f"Learned: {round(learned, 3)}A\n" \
              f"Time: {timestamp}"
        self.send_telegram_msg(msg)
        
        # Save Theft Log
        logs = db.get("theft_logs")
        logs.append({
            "timestamp": timestamp,
            "learned_current": round(learned, 3),
            "current_now": data["current"],
            "difference": round(data["current"] - learned, 3)
        })
        db.set("theft_logs", logs)

    def _background_loop(self):
        while True:
            try:
                now = time.time()
                
                # 30s Offline Detection
                with self.lock:
                    if now - self.latest_data['last_update'] > 30:
                        self.status = "Power OFF"
                        self.is_theft_active = False

                # 1 min Logging
                if now - self.last_log_time >= 60:
                    self._save_continuous_log()
                    self.last_log_time = now

                # 2 min Telegram Report
                if now - self.last_telegram_report >= 120:
                    self._send_periodic_report()
                    self.last_telegram_report = now

            except Exception as e:
                print(f"Error in background loop: {e}")
            time.sleep(1)

    def _save_continuous_log(self):
        with self.lock:
            if self.status == "Power OFF": return
            
            ist_now = get_ist_time()
            log = {
                "voltage": self.latest_data["voltage"],
                "current": self.latest_data["current"],
                "power": self.latest_data["power"],
                "status": self.status,
                "theftDetected": self.is_theft_active,
                "timestamp": format_ist(ist_now)
            }
            logs = db.get("continuous_logs")
            logs.append(log)
            db.set("continuous_logs", logs)

    def _send_periodic_report(self):
        with self.lock:
            if self.status == "Power OFF": return
            
            ist_now = get_ist_time()
            msg = f"SMART GRID UPDATE\n\n" \
                  f"Voltage: {int(self.latest_data['voltage'])}V\n" \
                  f"Current: {self.latest_data['current']}A\n" \
                  f"Power: {int(self.latest_data['power'])}W\n" \
                  f"Status: {self.status}\n" \
                  f"Theft: {'Yes' if self.is_theft_active else 'No'}\n" \
                  f"Time: {format_ist(ist_now)}"
            self.send_telegram_msg(msg)

    def send_telegram_msg(self, message):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        try:
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=5)
        except: pass

monitor = MonitoringService()

# ---------------- ROUTES ----------------
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

@app.route('/dashboard')
def dashboard():
    if 'user' not in session: return redirect('/')
    return render_template('dashboard.html')

@app.route('/generate-key')
def generate_key():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    key = "NK-" + str(random.randint(100000, 999999))
    session['api_key'] = key
    return jsonify({"api_key": key})

@app.route('/api/set-active-key', methods=['POST'])
def set_active_key():
    key = request.json.get('api_key')
    db.set("active_api_key", key)
    return jsonify({"success": True})

@app.route('/data', methods=['POST'])
def receive_data():
    data = request.json
    api_key = data.get('api_key')
    active_key = db.get("active_api_key")
    
    if not api_key or api_key != active_key:
        return jsonify({"status": "error", "message": "Invalid API Key"}), 403

    monitor.update_data(data)
    return jsonify({"status": "success"})

@app.route('/api/latest')
def get_latest():
    with monitor.lock:
        model = db.get("ai_model")
        learning_progress = 0
        if model["learningStartTime"] and not model["trained"]:
            # Progress based on samples or time
            start_time = datetime.fromisoformat(model["learningStartTime"])
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            time_progress = (elapsed / 600) * 100
            sample_progress = (model["sampleCount"] / 1000) * 100
            learning_progress = min(max(time_progress, sample_progress), 100)

        return jsonify({
            **monitor.latest_data,
            "status": monitor.status,
            "theft": monitor.is_theft_active,
            "ai_status": "RUNNING" if model["trained"] else "LEARNING" if model["learningStartTime"] else "OFF",
            "sensor_connected": monitor.status != "Power OFF",
            "api_key": db.get("active_api_key"),
            "theft_logs": db.get("theft_logs"),
            "learning_progress": learning_progress,
            "is_real": monitor.status != "Power OFF"
        })

@app.route('/api/start-learning', methods=['POST'])
def start_learning():
    model = db.get("ai_model")
    model.update({
        "avgVoltage": 0.0, "avgCurrent": 0.0, "avgPower": 0.0,
        "sampleCount": 0, "trained": False,
        "learningStartTime": datetime.utcnow().isoformat()
    })
    db.set("ai_model", model)
    return jsonify({"success": True})

@app.route('/api/reset-pattern', methods=['POST'])
def reset_pattern():
    # 1. Delete old AI learned values
    db.set("ai_model", {
        "avgVoltage": 0.0, "avgCurrent": 0.0, "avgPower": 0.0,
        "sampleCount": 0, "trained": False, "learningStartTime": None
    })
    # 2. Delete existing logs
    db.set("theft_logs", [])
    db.set("continuous_logs", [])
    
    with monitor.lock:
        monitor.is_theft_active = False
        
    return jsonify({"success": True})

@app.route('/api/clear-logs', methods=['POST'])
def clear_logs():
    db.set("theft_logs", [])
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
