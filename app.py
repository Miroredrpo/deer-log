import os
import json
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, session, redirect, url_for, send_file
from google_play_scraper import search, app as gp_app
import io
import csv

# App Initialization
app = Flask(__name__)
app.secret_key = "a-very-static-secret-key-for-testing"

# Configuration
LOG_FILE = 'deerwalk_logs.jsonl'
LOG_APP_NAME = "Deerwalk Learning Center"
LOG_PASSWORD = "dss"

# --- Data Fetching and Logging ---

def get_app_details(app_name):
    try:
        result = search(app_name, lang='en', country='us')
        if not result:
            return {"error": "No results found for the app."}

        details = gp_app(result[0]['appId'], lang='en', country='us')

        # Sanitize the output to prevent template errors from None values
        details['score'] = details.get('score') or 0
        details['ratings'] = details.get('ratings') or 0
        details['realInstalls'] = details.get('realInstalls') or 0

        return details
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}

def log_app_data(app_name=LOG_APP_NAME):
    details = get_app_details(app_name)
    if 'error' in details:
        return
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'app_name': details.get('title', 'N/A'),
        'installs': details.get('installs', 'N/A'),
        'realInstalls': details.get('realInstalls') or 0,
        'score': details.get('score') or 0,
        'ratings': details.get('ratings') or 0,
    }
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')

# --- Authentication ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == LOG_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('log_page'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

# --- Main Routes ---

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        app_name = request.form['app_name']
        app_details = get_app_details(app_name)
        return render_template('index.html', app_details=app_details, app_name=app_name)
    return render_template('index.html', app_details=None)

@app.route('/log')
@login_required
def log_page():
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            for line in f:
                try:
                    logs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    logs.reverse()
    return render_template('log.html', logs=logs)

@app.route('/log/manual', methods=['POST'])
@login_required
def manual_log():
    log_app_data()
    return redirect(url_for('log_page'))

@app.route('/log/export')
@login_required
def export_logs():
    # This feature is temporarily simplified
    return "Export not available in simplified mode."

@app.route('/log/delete', methods=['POST'])
@login_required
def delete_logs():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    return redirect(url_for('log_page'))

# The 'if __name__ == "__main__":' block has been removed to allow deployment
# with a production WSGI server like Gunicorn, as specified in render.yaml.
