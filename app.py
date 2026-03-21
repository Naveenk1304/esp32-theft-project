from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import random
import time
import os

app = Flask(__name__)
app.secret_key = 'smart_electricity_theft_secret'

# In-memory storage for latest sensor data
latest_data = {
    'voltage': 0,
    'current': 0,
    'power': 0,
    'energy': 0,
    'api_key': None,
    'last_update': 0
}

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
    session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html')

@app.route('/data', methods=['POST'])
def receive_data():
    global latest_data
    data = request.json
    # Expected: {api_key, voltage, current, power, energy}
    if not data or 'api_key' not in data:
        return jsonify({'status': 'error', 'message': 'Missing data or API key'}), 400
    
    latest_data.update({
        'voltage': data.get('voltage', 0),
        'current': data.get('current', 0),
        'power': data.get('power', 0),
        'energy': data.get('energy', 0),
        'api_key': data.get('api_key'),
        'last_update': time.time()
    })
    return jsonify({'status': 'success'})

@app.route('/api/latest')
def get_latest():
    # Return latest data and indicator if it's "real" (updated within last 5 seconds)
    is_real = (time.time() - latest_data['last_update']) < 5
    return jsonify({
        'data': latest_data,
        'is_real': is_real
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
