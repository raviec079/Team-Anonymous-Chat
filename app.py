from flask import Flask, render_template
from flask_socketio import SocketIO, emit, join_room
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

DB_FILE = 'chat.db'

# Initialize the database
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        # Create a central table to track users
        c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE)''')
        conn.commit()

# Register a new user in the users table
def register_user(username):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''INSERT OR IGNORE INTO users (username) VALUES (?)''', (username,))
        conn.commit()

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
    join_room(sender)

    # Register the user and create a table for storing their messages
    register_user(sender)
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
