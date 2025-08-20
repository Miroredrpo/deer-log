import os
import json
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, session, redirect, url_for, send_file, flash
from google_play_scraper import search, app as gp_app
import io
import csv
import threading
import time

# App Initialization
app = Flask(__name__)
app.secret_key = "a-very-static-secret-key-for-testing"

# Configuration
LOG_FILE = 'deerwalk_logs.jsonl'
LOG_APP_NAME = "Deerwalk Learning Center"
USERS = {"samir": "dss"} # User dictionary: username -> password
LOG_INTERVAL_SECONDS = 3600 # Log every hour

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

def log_app_data(username, app_name=LOG_APP_NAME):
    """Logs app data for a given user."""
    details = get_app_details(app_name)
    if 'error' in details:
        print(f"Error fetching app details: {details['error']}")
        return

    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'username': username,
        'app_name': details.get('title', 'N/A'),
        'installs': details.get('installs', 'N/A'),
        'realInstalls': details.get('realInstalls') or 0,
        'score': details.get('score') or 0,
        'ratings': details.get('ratings') or 0,
    }
    # Use a lock to prevent race conditions when writing to the file
    with threading.Lock():
        with open(LOG_FILE, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    print(f"Logged data for user '{username}' at {log_entry['timestamp']}")

# --- Background Logging Thread ---

def background_logger():
    """
    This function runs in a background thread and periodically logs data.
    NOTE: In a production environment with multiple workers (like Gunicorn),
    each worker would spawn its own thread, leading to duplicate logs.
    A more robust solution would use a dedicated scheduler (APScheduler)
    or an external cron job.
    """
    while True:
        # Log for a default user, as this runs outside any user's session
        # In a multi-user system, you might loop through all users or have a dedicated 'system' user
        log_app_data("samir", LOG_APP_NAME)
        time.sleep(LOG_INTERVAL_SECONDS)

# --- Authentication ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash("You must be logged in to view this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if USERS.get(username) == password:
            session['username'] = username
            flash(f"Welcome, {username}!", "success")
            return redirect(url_for('log_page'))
        else:
            flash("Invalid username or password.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('index'))

# --- Main Routes ---

@app.route('/')
def index():
    return render_template('index.html', app_details=None)

@app.route('/log')
@login_required
def log_page():
    user_logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            for line in f:
                try:
                    log = json.loads(line)
                    # Show logs if user is 'samir' or if it's their own log
                    if log.get('username') == session['username']:
                        user_logs.append(log)
                except json.JSONDecodeError:
                    pass
    user_logs.reverse()
    return render_template('log.html', logs=user_logs, username=session['username'])

@app.route('/log/manual', methods=['POST'])
@login_required
def manual_log():
    log_app_data(session['username'])
    flash("New log entry created.", "success")
    return redirect(url_for('log_page'))

@app.route('/log/export', methods=['POST'])
@login_required
def export_logs():
    log_ids_to_export = request.form.getlist('log_id')
    export_format = request.form.get('format', 'csv')

    if not log_ids_to_export:
        flash("Please select at least one log entry to export.", "warning")
        return redirect(url_for('log_page'))

    logs_to_export = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            for line in f:
                try:
                    log = json.loads(line)
                    if log.get('username') == session['username'] and log['timestamp'] in log_ids_to_export:
                        logs_to_export.append(log)
                except json.JSONDecodeError:
                    continue

    if not logs_to_export:
        flash("No matching logs found for export.", "warning")
        return redirect(url_for('log_page'))

    # Create file in memory
    mem_file = io.StringIO()
    if export_format == 'csv':
        fieldnames = logs_to_export[0].keys()
        writer = csv.DictWriter(mem_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(logs_to_export)
        mimetype = 'text/csv'
        filename = f"{session['username']}_logs.csv"
    elif export_format == 'json':
        json.dump(logs_to_export, mem_file, indent=4)
        mimetype = 'application/json'
        filename = f"{session['username']}_logs.json"
    else:
        flash("Invalid export format selected.", "danger")
        return redirect(url_for('log_page'))

    # Prepare response
    output = io.BytesIO(mem_file.getvalue().encode('utf-8'))
    output.seek(0)

    return send_file(
        output,
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename
    )


@app.route('/log/delete', methods=['POST'])
@login_required
def delete_logs():
    submitted_password = request.form.get('password')
    if USERS.get(session['username']) == submitted_password:
        # This implementation deletes the entire log file.
        # A safer approach for user-specific deletion is to read, filter, and rewrite.
        if os.path.exists(LOG_FILE):
            # Create a new list of logs to keep (from other users)
            logs_to_keep = []
            with open(LOG_FILE, 'r') as f:
                for line in f:
                    try:
                        log = json.loads(line)
                        if log.get('username') != session['username']:
                            logs_to_keep.append(line)
                    except json.JSONDecodeError:
                        continue

            # Rewrite the file with only the logs to keep
            with open(LOG_FILE, 'w') as f:
                for line in logs_to_keep:
                    f.write(line)

            flash(f"All logs for user '{session['username']}' have been deleted.", "success")
        else:
            flash("Log file not found.", "warning")
    else:
        flash("Incorrect password. Deletion failed.", "danger")
    return redirect(url_for('log_page'))

# Start the background logger thread
# The 'daemon=True' ensures the thread will exit when the main app exits.
logger_thread = threading.Thread(target=background_logger, daemon=True)
logger_thread.start()

# The 'if __name__ == "__main__":' block has been removed to allow deployment
# with a production WSGI server like Gunicorn, as specified in render.yaml.
