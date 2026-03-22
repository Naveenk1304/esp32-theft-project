from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import random
import time
import os
import pickle

app = Flask(__name__)
app.secret_key = 'smart_electricity_theft_secret'

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
    global generated_api_key

    if not generated_api_key:
        generated_api_key = "KEY_" + str(random.randint(100000, 999999))

    return jsonify({"api_key": generated_api_key})

# ---------------- ESP32 DATA RECEIVE ----------------
@app.route('/data', methods=['POST'])
def receive_data():
    global latest_data

    data = request.json

    if not data:
        return jsonify({"status": "error", "message": "No data received"}), 400

    # API key check
    if data.get("api_key") != generated_api_key:
        return jsonify({"status": "error", "message": "Invalid API Key"}), 403

    latest_data['voltage'] = data.get('voltage', 0)
    latest_data['current'] = data.get('current', 0)
    latest_data['power'] = data.get('power', 0)
    latest_data['energy'] = data.get('energy', 0)
    latest_data['api_key'] = data.get('api_key')
    latest_data['last_update'] = time.time()

    return jsonify({"status": "success"})

# ---------------- GET DATA (FRONTEND) ----------------
@app.route('/api/latest')
def get_latest():
    global latest_data

    # ALWAYS generate demo data if no sensor
    if latest_data['api_key'] is None:
        latest_data['voltage'] = random.uniform(220, 240)
        latest_data['current'] = random.uniform(1, 5)
        latest_data['power'] = random.uniform(200, 800)
        latest_data['energy'] = random.uniform(10, 20)

    # ML prediction
    theft = predict_theft(latest_data['current'], latest_data['power'])
    latest_data['theft'] = theft

    return jsonify({
        "voltage": latest_data['voltage'],
        "current": latest_data['current'],
        "power": latest_data['power'],
        "energy": latest_data['energy'],
        "theft": latest_data['theft'],
        "is_real": latest_data['api_key'] is not None
    })

# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)