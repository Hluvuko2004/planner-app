import re
import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
app = Flask(__name__)
app.secret_key = os.urandom(24)

# -------------------------------------------------------------
# DATABASE CONNECTION HELPER (SQLite)
# -------------------------------------------------------------
def get_db_connection():
    db_path = os.path.join(os.path.dirname(__file__), 'planner.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn

# -------------------------------------------------------------
# INITIALIZE TABLES & DEFAULT ADMIN
# -------------------------------------------------------------
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            priority TEXT DEFAULT 'Medium',
            status TEXT DEFAULT 'todo',
            due_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subtasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            start_time TEXT NOT NULL,
            end_time TEXT,
            is_public INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_attendees (
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (event_id, user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    cursor.close()
    conn.close()

def create_default_admin():
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    admin_user = cursor.fetchone()
    
    if not admin_user:
        hashed_password = generate_password_hash('admin123')
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)",
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
    if 'user_id' in session:
        if session.get('is_admin'):
            return redirect(url_for('admin_panel'))
        return redirect(url_for('dashboard'))
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, username))
            user = cursor.fetchone()
            
            if not user:
                cursor.close()
                conn.close()
                flash('Invalid username or password', 'error')
                return redirect(url_for('login'))

            stored_password = user['password_hash'] if 'password_hash' in user.keys() else user.get('password')

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
        
        if not username or not username[0].isupper():
            flash('Username must start with a capital letter.', 'error')
            return redirect(url_for('register'))
            
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('register'))

        if len(password) < 8 or not re.search(r"\d", password):
            flash('Password must be at least 8 characters long and contain at least one number.', 'error')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, 0)",
                (username, email, hashed_password)
            )
            conn.commit()
            cursor.close()
            conn.close()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError as err:
            cursor.close()
            conn.close()
            flash(f"Username or email already exists.", 'error')
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
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
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
        "INSERT INTO tasks (user_id, title, description, priority, status, due_date) VALUES (?, ?, ?, ?, 'todo', ?)",
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
        "UPDATE tasks SET status = ? WHERE id = ? AND user_id = ?",
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
    cursor.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
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
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, start_time AS start, end_time AS end FROM events WHERE user_id = ?", (user_id,))
    events = [dict(row) for row in cursor.fetchall()]
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
        "INSERT INTO events (user_id, title, description, start_time, end_time, is_public) VALUES (?, ?, ?, ?, ?, ?)",
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
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM events WHERE user_id = ? ORDER BY start_time ASC", (user_id,))
    my_events = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("SELECT * FROM events WHERE is_public = 1 ORDER BY start_time ASC")
    public_events_raw = cursor.fetchall()
    
    public_events = []
    for event_row in public_events_raw:
        event = dict(event_row)
        cursor.execute("""
            SELECT users.id, users.username 
            FROM event_attendees 
            JOIN users ON event_attendees.user_id = users.id 
            WHERE event_attendees.event_id = ?
        """, (event['id'],))
        event['attendees'] = [dict(r) for r in cursor.fetchall()]
        event['is_attending'] = any(att['id'] == user_id for att in event['attendees'])
        public_events.append(event)
    
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
            "INSERT OR IGNORE INTO event_attendees (event_id, user_id) VALUES (?, ?)",
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
            "DELETE FROM event_attendees WHERE event_id = ? AND user_id = ?",
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
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        event = cursor.fetchone()
        
        if event:
            cursor.execute(
                """INSERT INTO events (user_id, title, description, start_time, end_time, is_public) 
                   VALUES (?, ?, ?, ?, ?, 0)""",
                (user_id, f"[Copy] {event['title']}", event['description'], event['start_time'], event['end_time'])
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
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notes WHERE user_id = ? ORDER BY updated_at DESC", (user_id,))
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
    cursor.execute("INSERT INTO notes (user_id, title, content) VALUES (?, ?, ?)", (user_id, title, content))
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
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
    task = cursor.fetchone()
    
    if not task:
        cursor.close()
        conn.close()
        return redirect(url_for('tasks_page'))

    cursor.execute("SELECT * FROM subtasks WHERE task_id = ?", (task_id,))
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
    cursor.execute("INSERT INTO subtasks (task_id, title) VALUES (?, ?)", (task_id, title))
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
    cursor = conn.cursor()
    
    cursor.execute("SELECT status, COUNT(*) as count FROM tasks WHERE user_id = ? GROUP BY status", (user_id,))
    status_counts = cursor.fetchall()
    
    cursor.execute("SELECT priority, COUNT(*) as count FROM tasks WHERE user_id = ? GROUP BY priority", (user_id,))
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
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
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
        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_password, user_id))
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
    cursor = conn.cursor()
    
    cursor.execute("SELECT is_admin FROM users WHERE id = ?", (session['user_id'],))
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
    cursor = conn.cursor()
    cursor.execute("SELECT is_admin FROM users WHERE id = ?", (session['user_id'],))
    current_user = cursor.fetchone()
    
    if not current_user or not current_user['is_admin']:
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))
        
    new_username = request.form['username']
    new_email = request.form['email']
    is_admin = 1 if 'is_admin' in request.form else 0

    cursor.execute(
        "UPDATE users SET username = ?, email = ?, is_admin = ? WHERE id = ?",
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
    cursor = conn.cursor()
    cursor.execute("SELECT is_admin FROM users WHERE id = ?", (session['user_id'],))
    current_user = cursor.fetchone()
    
    if not current_user or not current_user['is_admin'] or session['user_id'] == user_id:
        cursor.close()
        conn.close()
        return redirect(url_for('admin_panel'))
        
    cursor.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM events WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
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