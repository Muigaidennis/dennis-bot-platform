import os
import sqlite3
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet
from flask_session import Session
import bot_runner

# Configuration
APP_ID = 117276
REDIRECT_URI = "https://nongeneric-tousledly-shawanna.ngrok-free.dev/callback"  # CHANGE when ngrok restarts
DATABASE = 'users.db'
SECRET_KEY = os.urandom(24)
UPLOAD_FOLDER = 'bots'
ALLOWED_EXTENSIONS = {'py'}
REMEMBER_COOKIE_DURATION = timedelta(days=30)

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SESSION_TYPE'] = 'filesystem'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PERMANENT_SESSION_LIFETIME'] = REMEMBER_COOKIE_DURATION
Session(app)

ENCRYPTION_KEY = b'4M-facj1b_t1QInD9SAr0swkafcL7pkuvaX9MVbN72g='
cipher_suite = Fernet(ENCRYPTION_KEY)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.before_request
def make_session_permanent():
    session.permanent = True
    app.permanent_session_lifetime = REMEMBER_COOKIE_DURATION

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, hashed_password))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists.', 'error')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = 'remember' in request.form
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['account_type'] = 'demo'
            session.permanent = remember
            flash('Logged in successfully.', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    
    deriv_connected = user['deriv_token_encrypted'] is not None
    balance = bot_runner.get_account_balance_display(session['user_id']) if deriv_connected else "Not connected"
    
    return render_template('dashboard.html', 
                           deriv_connected=deriv_connected, 
                           app_id=APP_ID, 
                           balance_display=balance,
                           account_type=session.get('account_type', 'demo'),
                           username=session['username'])

@app.route('/switch_account', methods=['POST'])
def switch_account():
    account_type = request.form.get('account_type', 'demo')
    session['account_type'] = account_type
    flash(f'Switched to {account_type.capitalize()} account.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/trading_bots')
def trading_bots():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    
    deriv_connected = user['deriv_token_encrypted'] is not None
    balance = bot_runner.get_account_balance_display(session['user_id']) if deriv_connected else "Not connected"
    
    available_bots = []
    if os.path.exists(app.config['UPLOAD_FOLDER']):
        available_bots = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if f.endswith('.py')]
    
    return render_template('trading_bots.html', 
                           deriv_connected=deriv_connected, 
                           balance_display=balance, 
                           bots=available_bots,
                           username=session['username'])

@app.route('/upload_bot', methods=['POST'])
def upload_bot():
    if session.get('username') != 'dennis':
        flash('Only admin can upload bots.', 'error')
        return redirect(url_for('trading_bots'))
    
    if 'bot_file' not in request.files:
        flash('No file selected.', 'error')
        return redirect(url_for('trading_bots'))
    
    file = request.files['bot_file']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        flash(f'Bot {filename} uploaded successfully!', 'success')
    else:
        flash('Invalid file — only .py allowed.', 'error')
    
    return redirect(url_for('trading_bots'))

@app.route('/callback')
def callback():
    token = request.args.get('token1')
    if not token or 'user_id' not in session:
        flash('Connection failed.', 'error')
        return redirect(url_for('dashboard'))
    
    encrypted_token = cipher_suite.encrypt(token.encode()).decode()
    conn = get_db_connection()
    conn.execute('UPDATE users SET deriv_token_encrypted = ? WHERE id = ?', (encrypted_token, session['user_id']))
    conn.commit()
    conn.close()
    
    flash('Deriv connected successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/start_bot', methods=['POST'])
def start_bot():
    if 'user_id' not in session:
        flash('Please log in.', 'error')
        return redirect(url_for('login'))
    
    bot_name = request.form.get('bot_name')
    if not bot_name:
        flash('No bot selected.', 'error')
        return redirect(url_for('trading_bots'))
    
    conn = get_db_connection()
    user = conn.execute('SELECT deriv_token_encrypted FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    
    if not user['deriv_token_encrypted']:
        flash('Deriv account not connected. Go to Dashboard to link it first.', 'error')
        return redirect(url_for('trading_bots'))
    
    params = {
        'market': request.form.get('market', 'R_75'),
        'stake': float(request.form.get('stake', 1.0)),
        'duration': int(request.form.get('duration', 5)),
        'contract_type': request.form.get('contract_type', 'RISE')
    }
    
    msg = bot_runner.run_bot(session['user_id'], bot_name, params=params)
    flash(msg, 'info')
    return redirect(url_for('trading_bots'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
