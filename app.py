from flask import Flask, render_template
from flask_socketio import SocketIO, emit, join_room
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

DB_FILE = 'chat.db'

def initialize_database():
    conn = sqlite3.connect(DB_FILE)  # Ensure this matches your database file
    c = conn.cursor()
    # Create the `users` table if it doesn't exist
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        pin TEXT NOT NULL
    )
    ''')
    conn.commit()
    conn.close()

initialize_database()


# Validate user or register a new user
def validate_or_register_user(username, pin):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        # Check if user exists
        c.execute('SELECT pin FROM users WHERE username = ?', (username,))
        row = c.fetchone()
        if row:
            # User exists, validate the PIN
            stored_pin = row[0]
            return stored_pin == pin
        else:
            # New user, register with the given PIN
            c.execute('INSERT INTO users (username, pin) VALUES (?, ?)', (username, pin))
            conn.commit()
            return True  # New user registered successfully

# Create a table for storing messages for a specific user
def create_user_table(username):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(f'''CREATE TABLE IF NOT EXISTS "{username}" (id INTEGER PRIMARY KEY, sender TEXT, message TEXT)''')
        conn.commit()

# Store message in the recipient's table
def save_message(receiver, sender, message):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(f'''INSERT INTO "{receiver}" (sender, message) VALUES (?, ?)''', (sender, message))
        conn.commit()

# Fetch all messages for a specific user
def get_user_messages(username):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        try:
            c.execute(f'''SELECT sender, message FROM "{username}"''')
            return c.fetchall()
        except sqlite3.OperationalError:
            return []  # No messages if table doesn't exist

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def on_join(data):
    sender = data['sender']
    pin = data['pin']

    # Validate or register the user
    is_valid = validate_or_register_user(sender, pin)
    if not is_valid:
        emit('error', {'message': 'Invalid PIN. Please try again.'})
        return
    
    join_room(sender)

    # Register the user and create a table for storing their messages
    create_user_table(sender)

    # Fetch and send the user's message history
    messages = get_user_messages(sender)
    emit('load_messages', [{'sender': 'Team H2O member', 'message': msg[1]} for msg in messages])

@socketio.on('send_message')
def handle_message(data):
    sender = data.get('sender')
    message = data.get('message')
    receiver = data.get('receiver', 'everyone')

    # Save the message in the recipient's table(s)
    if receiver == 'everyone':
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            # Get all users from the `users` table
            c.execute('SELECT username FROM users')
            users = [row[0] for row in c.fetchall()]
            # Save the message for each user
            for user in users:
                save_message(user, sender, message)
    else:
        # Save the private message in the recipient's table
        save_message(receiver, sender, message)

    # Emit the message with the sender replaced by "Team H2O member"
    if receiver == 'everyone':
        emit('receive_message', {'message': message, 'sender': 'Team H2O member'}, broadcast=True)
    else:
        emit('receive_message', {'message': f'(Private) {message}', 'sender': 'Team H2O member'}, room=receiver)
