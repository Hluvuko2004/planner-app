import re
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask import Flask, render_template, session, redirect, url_for

app = Flask(__name__)
app.secret_key = os.urandom(24)

# -------------------------------------------------------------
# DATABASE CONNECTION HELPER
# -------------------------------------------------------------
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'planner_db')
    )

# -------------------------------------------------------------
# DEFAULT ADMIN SEEDER
# -------------------------------------------------------------
def create_default_admin():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    admin_user = cursor.fetchone()
    
    if not admin_user:
        hashed_password = generate_password_hash('admin123')
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, is_admin) VALUES (%s, %s, %s, %s)",
            ('admin', 'admin@planner.com', hashed_password, 1)
        )
        conn.commit()
        print("Default admin account created successfully!")
        
    cursor.close()
    conn.close()

with app.app_context():
    create_default_admin()

# -------------------------------------------------------------
# AUTHENTICATION ROUTES
# -------------------------------------------------------------
@app.route('/')
def home():
    # If the user is already logged in, send them straight to their dashboard
    if 'user_id' in session:
        if session.get('is_admin'):
            return redirect(url_for('admin'))
        return redirect(url_for('dashboard'))
    
    # If not logged in, show the landing page template
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, username))
            user = cursor.fetchone()
            
            if not user:
                cursor.close()
                conn.close()
                flash('Invalid username or password', 'error')
                return redirect(url_for('login'))

            stored_password = user.get('password') or user.get('password_hash')

            if stored_password and check_password_hash(stored_password, password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['is_admin'] = 1 if user.get('is_admin') == 1 else 0

                cursor.close()
                conn.close()

                if session['is_admin']:
                    return redirect(url_for('admin_panel'))
                else:
                    return redirect(url_for('dashboard'))
            else:
                cursor.close()
                conn.close()
                flash('Invalid username or password', 'error')
                return redirect(url_for('login'))
        except Exception as err:
            cursor.close()
            conn.close()
            flash(f"System Error: {err}", 'error')
            return redirect(url_for('login'))

    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation: Name must start with a capital letter
        if not username or not username[0].isupper():
            flash('Username must start with a capital letter.', 'error')
            return redirect(url_for('register'))
            
        # Validation: Passwords match check
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('register'))

        # Validation: Minimum 8 characters, include a number
        if len(password) < 8 or not re.search(r"\d", password):
            flash('Password must be at least 8 characters long and contain at least one number.', 'error')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, is_admin) VALUES (%s, %s, %s, 0)",
                (username, email, hashed_password)
            )
            conn.commit()
            cursor.close()
            conn.close()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            cursor.close()
            conn.close()
            flash(f"Database Error: {err}", 'error')
            return redirect(url_for('register'))

    return render_template('auth/register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# -------------------------------------------------------------
# DASHBOARD ROUTE
# -------------------------------------------------------------
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'], active_page='dashboard')

# -------------------------------------------------------------
# TASKS MANAGEMENT ROUTES
# -------------------------------------------------------------
@app.route('/tasks')
def tasks_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM tasks WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
    all_tasks = cursor.fetchall()
    
    cursor.close()
    conn.close()

    board = {
        'todo': [t for t in all_tasks if t['status'] == 'todo'],
        'in_progress': [t for t in all_tasks if t['status'] == 'in_progress'],
        'completed': [t for t in all_tasks if t['status'] == 'completed']
    }
    
    return render_template('tasks.html', board=board, active_page='tasks')

@app.route('/tasks/add', methods=['POST'])
def add_task_secure():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    title = request.form['title']
    description = request.form['description']
    priority = request.form['priority']
    due_date = request.form.get('due_date') or None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (user_id, title, description, priority, status, due_date) VALUES (%s, %s, %s, %s, 'todo', %s)",
        (user_id, title, description, priority, due_date)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('tasks_page'))

@app.route('/api/update_task_status', methods=['POST'])
def api_update_task_status():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
    data = request.get_json()
    task_id = data.get('task_id')
    new_status = data.get('status')
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE tasks SET status = %s WHERE id = %s AND user_id = %s",
        (new_status, task_id, user_id)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True})

@app.route('/tasks/delete/<int:task_id>')
def delete_task_secure(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = %s AND user_id = %s", (task_id, user_id))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('tasks_page'))

# -------------------------------------------------------------
# EVENT CALENDAR ROUTES & APIS
# -------------------------------------------------------------
@app.route('/calendar')
def calendar_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('calendar.html', active_page='calendar')

@app.route('/api/events')
def api_get_events():
    if 'user_id' not in session:
        return jsonify([]), 401
        
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, title, start_time AS start, end_time AS end FROM events WHERE user_id = %s", (user_id,))
    events = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify(events)

@app.route('/events/add', methods=['POST'])
def add_event_secure():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    title = request.form.get('title')
    description = request.form.get('description', '')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time') or start_time
    is_public = 1 if 'is_public' in request.form else 0

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO events (user_id, title, description, start_time, end_time, is_public) VALUES (%s, %s, %s, %s, %s, %s)",
        (user_id, title, description, start_time, end_time, is_public)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('events_page'))

@app.route('/events')
def events_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM events WHERE user_id = %s ORDER BY start_time ASC", (user_id,))
    my_events = cursor.fetchall()
    
    cursor.execute("SELECT * FROM events WHERE is_public = 1 ORDER BY start_time ASC")
    public_events = cursor.fetchall()
    
    for event in public_events:
        cursor.execute("""
            SELECT users.id, users.username 
            FROM event_attendees 
            JOIN users ON event_attendees.user_id = users.id 
            WHERE event_attendees.event_id = %s
        """, (event['id'],))
        event['attendees'] = cursor.fetchall()
        event['is_attending'] = any(att['id'] == user_id for att in event['attendees'])
    
    cursor.close()
    conn.close()

    return render_template('events.html', my_events=my_events, public_events=public_events, active_page='events')

@app.route('/events/attend/<int:event_id>', methods=['POST'])
def attend_event(event_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT IGNORE INTO event_attendees (event_id, user_id) VALUES (%s, %s)",
            (event_id, user_id)
        )
        conn.commit()
    except Exception as err:
        print("Attend Error:", err)
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('events_page'))

@app.route('/events/unattend/<int:event_id>', methods=['POST'])
def unattend_event(event_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM event_attendees WHERE event_id = %s AND user_id = %s",
            (event_id, user_id)
        )
        conn.commit()
    except Exception as err:
        print("Unattend Error:", err)
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('events_page'))

@app.route('/events/copy/<int:event_id>', methods=['POST'])
def add_to_my_calendar(event_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM events WHERE id = %s", (event_id,))
        event = cursor.fetchone()
        
        if event:
            cursor.execute(
                """INSERT INTO events (user_id, title, description, start_time, end_time, is_public) 
                   VALUES (%s, %s, %s, %s, %s, 0)""",
                (user_id, f"[Copy] {event['title']}", event['description'], event['start_time'], event.get('end_time'))
            )
            conn.commit()
    except Exception as err:
        print("Copy Event Error:", err)
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('events_page'))

# -------------------------------------------------------------
# NOTES & TASK DETAILS ROUTES
# -------------------------------------------------------------
@app.route('/notes')
def notes_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM notes WHERE user_id = %s ORDER BY updated_at DESC", (user_id,))
    notes = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('notes.html', notes=notes, active_page='notes')

@app.route('/notes/add', methods=['POST'])
def add_note():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    title = request.form['title']
    content = request.form['content']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO notes (user_id, title, content) VALUES (%s, %s, %s)", (user_id, title, content))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('notes_page'))

@app.route('/tasks/<int:task_id>')
def task_details_page(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM tasks WHERE id = %s AND user_id = %s", (task_id, user_id))
    task = cursor.fetchone()
    
    if not task:
        cursor.close()
        conn.close()
        return redirect(url_for('tasks_page'))

    cursor.execute("SELECT * FROM subtasks WHERE task_id = %s", (task_id,))
    subtasks = cursor.fetchall()
    
    cursor.close()
    conn.close()

    return render_template('task_details.html', task=task, subtasks=subtasks, active_page='tasks')

@app.route('/tasks/<int:task_id>/subtask/add', methods=['POST'])
def add_subtask(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    title = request.form['title']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO subtasks (task_id, title) VALUES (%s, %s)", (task_id, title))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('task_details_page', task_id=task_id))

# -------------------------------------------------------------
# REPORTS & ANALYTICS ROUTE
# -------------------------------------------------------------
@app.route('/reports')
def reports_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT status, COUNT(*) as count FROM tasks WHERE user_id = %s GROUP BY status", (user_id,))
    status_counts = cursor.fetchall()
    
    cursor.execute("SELECT priority, COUNT(*) as count FROM tasks WHERE user_id = %s GROUP BY priority", (user_id,))
    priority_counts = cursor.fetchall()

    cursor.close()
    conn.close()

    status_map = {'todo': 0, 'in_progress': 0, 'completed': 0}
    for row in status_counts:
        if row['status'] in status_map:
            status_map[row['status']] = row['count']

    priority_map = {'Low': 0, 'Medium': 0, 'High': 0}
    for row in priority_counts:
        if row['priority'] in priority_map:
            priority_map[row['priority']] = row['count']

    return render_template('reports.html', status_data=status_map, priority_data=priority_map, active_page='reports')

# -------------------------------------------------------------
# PASSWORD RESET ROUTES
# -------------------------------------------------------------
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form['username']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            return redirect(url_for('reset_password_direct', user_id=user['id']))
        else:
            return render_template('auth/forgot_password.html', error="Username not found.")
            
    return render_template('auth/forgot_password.html')


@app.route('/reset-password/<int:user_id>', methods=['GET', 'POST'])
def reset_password_direct(user_id):
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('reset_password_direct', user_id=user_id))

        if len(password) < 8 or not re.search(r"\d", password):
            flash('Password must be at least 8 characters long and contain at least one number.', 'error')
            return redirect(url_for('reset_password_direct', user_id=user_id))

        new_password = generate_password_hash(password)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_password, user_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Password successfully reset! Please log in with your new password.', 'success')
        return redirect(url_for('login'))
        
    return render_template('auth/reset_direct.html', user_id=user_id)

# -------------------------------------------------------------
# ADMIN PANEL ROUTE & CRUD
# -------------------------------------------------------------
@app.route('/admin')
def admin_panel():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT is_admin FROM users WHERE id = %s", (session['user_id'],))
    current_user = cursor.fetchone()
    
    if not current_user or not current_user['is_admin']:
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))
        
    cursor.execute("SELECT id, username, email, created_at, is_admin FROM users")
    all_users = cursor.fetchall()
    
    cursor.execute("SELECT COUNT(*) as count FROM tasks")
    total_tasks = cursor.fetchone()['count']
    
    cursor.close()
    conn.close()

    return render_template('admin.html', users=all_users, total_tasks=total_tasks, active_page='admin')

@app.route('/admin/users/edit/<int:user_id>', methods=['POST'])
def admin_edit_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT is_admin FROM users WHERE id = %s", (session['user_id'],))
    current_user = cursor.fetchone()
    
    if not current_user or not current_user['is_admin']:
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))
        
    new_username = request.form['username']
    new_email = request.form['email']
    is_admin = 1 if 'is_admin' in request.form else 0

    cursor.execute(
        "UPDATE users SET username = %s, email = %s, is_admin = %s WHERE id = %s",
        (new_username, new_email, is_admin, user_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/admin/users/delete/<int:user_id>')
def admin_delete_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT is_admin FROM users WHERE id = %s", (session['user_id'],))
    current_user = cursor.fetchone()
    
    if not current_user or not current_user['is_admin'] or session['user_id'] == user_id:
        cursor.close()
        conn.close()
        return redirect(url_for('admin_panel'))
        
    cursor.execute("DELETE FROM tasks WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM events WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('admin_panel'))

# -------------------------------------------------------------
# POMODORO FOCUS TIMER ROUTE
# -------------------------------------------------------------
@app.route('/pomodoro')
def pomodoro_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('pomodoro.html', active_page='pomodoro')

if __name__ == '__main__':
    app.run(debug=True)