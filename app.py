from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify
from google_play_scraper import search, app as gp_app
import io
import csv
import os
import json
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
import threading

# App Initialization
app = Flask(__name__)
app.secret_key = "a-very-static-secret-key-for-testing"

# Configuration
LOG_FILE = 'deerwalk_logs.jsonl'
LOG_APP_NAME = "Deerwalk Learning Center"
CORRECT_PASSWORD = "dss"
KTM_TZ = pytz.timezone('Asia/Kathmandu')

# --- Scheduler Setup ---
scheduler = BackgroundScheduler(timezone=KTM_TZ)
scheduler.start()
# Global lock for thread-safe operations on the log file
log_lock = threading.Lock()

# --- Data Fetching and Logging ---

def get_app_details(app_name):
    try:
        result = search(app_name, lang='en', country='us')
        if not result:
            return {"error": "No results found for the app."}
        details = gp_app(result[0]['appId'], lang='en', country='us')
        details['score'] = details.get('score') or 0
        details['ratings'] = details.get('ratings') or 0
        details['realInstalls'] = details.get('realInstalls') or 0
        return details
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}

def log_app_data(app_name=LOG_APP_NAME):
    """Logs app data with a timezone-aware timestamp."""
    details = get_app_details(app_name)
    if 'error' in details:
        print(f"Error fetching app details: {details['error']}")
        return

    log_entry = {
        'timestamp': datetime.now(KTM_TZ).isoformat(),
        'app_name': details.get('title', 'N/A'),
        'installs': details.get('installs', 'N/A'),
        'realInstalls': details.get('realInstalls') or 0,
        'score': details.get('score') or 0,
        'ratings': details.get('ratings') or 0,
    }
    with log_lock:
        with open(LOG_FILE, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    print(f"Logged data at {log_entry['timestamp']}")

# --- Main Routes ---

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        app_name = request.form.get('app_name')
        if not app_name:
            flash("Please enter an app name.", "warning")
            return render_template('index.html', app_details=None)
        app_details = get_app_details(app_name)
        return render_template('index.html', app_details=app_details, app_name=app_name)
    return render_template('index.html', app_details=None)

@app.route('/log')
def log_page():
    logs = []
    if os.path.exists(LOG_FILE):
        with log_lock:
            with open(LOG_FILE, 'r') as f:
                for line in f:
                    try:
                        logs.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    logs.reverse()
    job = scheduler.get_job('scheduled_log')
    next_run = job.next_run_time.isoformat() if job else None
    return render_template('log.html', logs=logs, next_run_time=next_run, current_interval=getattr(scheduler, 'logging_interval_hours', 1))

@app.route('/log/manual', methods=['POST'])
def manual_log():
    if request.form.get('password') != CORRECT_PASSWORD:
        flash("Incorrect password.", "danger")
        return redirect(url_for('log_page'))
    log_app_data()
    flash("New log entry created.", "success")
    return redirect(url_for('log_page'))

@app.route('/log/export', methods=['POST'])
def export_logs():
    export_format = request.form.get('format', 'csv')
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    min_installs_str = request.form.get('min_installs', '0')

    try:
        min_installs = int(min_installs_str) if min_installs_str else 0
    except ValueError:
        flash("Invalid minimum installs value.", "warning")
        return redirect(url_for('log_page'))

    start_date = None
    if start_date_str:
        try:
            start_date = KTM_TZ.localize(datetime.strptime(start_date_str, '%Y-%m-%d'))
        except ValueError:
            flash("Invalid start date format. Use YYYY-MM-DD.", "warning")
            return redirect(url_for('log_page'))

    end_date = None
    if end_date_str:
        try:
            # Include the entire day
            end_date = KTM_TZ.localize(datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1))
        except ValueError:
            flash("Invalid end date format. Use YYYY-MM-DD.", "warning")
            return redirect(url_for('log_page'))

    logs_to_export = []
    if os.path.exists(LOG_FILE):
        with log_lock:
            with open(LOG_FILE, 'r') as f:
                for line in f:
                    try:
                        log = json.loads(line)
                        log_date = datetime.fromisoformat(log['timestamp'])

                        # Apply filters
                        if start_date and log_date < start_date:
                            continue
                        if end_date and log_date >= end_date:
                            continue
                        if log.get('realInstalls', 0) < min_installs:
                            continue

                        logs_to_export.append(log)
                    except (json.JSONDecodeError, ValueError):
                        continue

    if not logs_to_export:
        flash("No logs found matching the specified criteria.", "warning")
        return redirect(url_for('log_page'))

    mem_file = io.StringIO()
    if export_format == 'csv':
        fieldnames = logs_to_export[0].keys()
        writer = csv.DictWriter(mem_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(logs_to_export)
        mimetype = 'text/csv'
        filename = "filtered_logs.csv"
    elif export_format == 'json':
        json.dump(logs_to_export, mem_file, indent=4)
        mimetype = 'application/json'
        filename = "filtered_logs.json"
    else:
        flash("Invalid export format.", "danger")
        return redirect(url_for('log_page'))

    output = io.BytesIO(mem_file.getvalue().encode('utf-8'))
    return send_file(output, mimetype=mimetype, as_attachment=True, download_name=filename)

@app.route('/log/delete', methods=['POST'])
def delete_logs():
    if request.form.get('password') != CORRECT_PASSWORD:
        flash("Incorrect password.", "danger")
        return redirect(url_for('log_page'))
    with log_lock:
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)
            flash("All logs have been deleted.", "success")
    return redirect(url_for('log_page'))

@app.route('/log/delete_single', methods=['POST'])
def delete_single_log():
    password = request.form.get('password')
    log_timestamp = request.form.get('timestamp')

    if password != CORRECT_PASSWORD:
        flash("Incorrect password for deletion.", "danger")
        return redirect(url_for('log_page'))

    if not log_timestamp:
        flash("Log timestamp missing.", "warning")
        return redirect(url_for('log_page'))

    logs_to_keep = []
    log_found = False
    with log_lock:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r') as f:
                for line in f:
                    try:
                        log = json.loads(line)
                        if log.get('timestamp') == log_timestamp:
                            log_found = True
                        else:
                            logs_to_keep.append(line)
                    except json.JSONDecodeError:
                        continue

            if log_found:
                with open(LOG_FILE, 'w') as f:
                    for line in logs_to_keep:
                        f.write(line)
                flash("Log entry deleted.", "success")
            else:
                flash("Log entry not found.", "warning")

    return redirect(url_for('log_page'))

@app.route('/scheduler/info')
def scheduler_info():
    job = scheduler.get_job('scheduled_log')
    if job:
        next_run = job.next_run_time.isoformat()
        return jsonify(next_run_time=next_run)
    return jsonify(next_run_time=None)

@app.route('/scheduler/reschedule', methods=['POST'])
def reschedule():
    password = request.form.get('password')
    interval_hours = request.form.get('interval', type=int)

    if password != CORRECT_PASSWORD:
        flash("Incorrect password.", "danger")
        return redirect(url_for('log_page'))

    if interval_hours and interval_hours > 0:
        scheduler.reschedule_job('scheduled_log', trigger='interval', hours=interval_hours)
        scheduler.logging_interval_hours = interval_hours # Store for display
        flash(f"Logging schedule updated to every {interval_hours} hour(s).", "success")
    else:
        flash("Invalid interval.", "warning")
    return redirect(url_for('log_page'))

@app.route('/log/latest_timestamp')
def latest_log_timestamp():
    if not os.path.exists(LOG_FILE):
        return jsonify(timestamp=None)

    with log_lock:
        with open(LOG_FILE, 'r') as f:
            # Read all lines and get the last one
            lines = f.readlines()
            if not lines:
                return jsonify(timestamp=None)

            try:
                latest_log = json.loads(lines[-1])
                return jsonify(timestamp=latest_log.get('timestamp'))
            except (json.JSONDecodeError, IndexError):
                return jsonify(timestamp=None)

# --- Initial Job Scheduling ---
# Schedule the first job to run every 1 hour by default
if not scheduler.get_job('scheduled_log'):
    scheduler.add_job(log_app_data, 'interval', hours=1, id='scheduled_log')
    scheduler.logging_interval_hours = 1

# The 'if __name__ == "__main__":' block has been removed to allow deployment
# with a production WSGI server like Gunicorn, as specified in render.yaml.
