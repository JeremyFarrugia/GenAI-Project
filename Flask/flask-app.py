from flask import Flask, render_template, send_from_directory, abort, request, jsonify, send_file, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import os, json
import torchaudio
import numpy as np
import soundfile as sf
from typing import Union
import torch
from groq import Groq
from dotenv import load_dotenv

import sqlite3


"""
TODO: 
users
- modal popups/updates instead of alerts
- logout
- profile?

chat persistance
- store chat history
- delete chat?

share chat?
public chat page?

audio generation
- TTS & sound effects

story creation

images
"""

AUTHENTICATION_TOKEN = 'a123' # Authentication token for the user

from TTS.api import TTS
tts = TTS("tts_models/en/ljspeech/tacotron2-DDC")

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
STATIC_DIR = os.path.join(SCRIPT_DIR, 'static')
USERDATA_DIR = os.path.join(STATIC_DIR, 'userdata')
AUDIO_DIR = os.path.join(STATIC_DIR, 'audio')

load_dotenv()

#-------------------------------------------------------Server Setup-------------------------------------------------------#

app = Flask(__name__)

app.static_folder = 'static' # Set the static folder to the 'static' folder in the current directory
app.template_folder = 'templates' # Set the template folder to the 'templates' folder in the current directory

app.secret_key = os.urandom(24) # Set the secret key for the session

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(USERDATA_DIR, "users.db")}' # Set the database URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Disable modification tracking
db = SQLAlchemy(app) # Create a database object
bcrypt = Bcrypt(app) # Create a bcrypt object for password hashing

client = Groq(api_key=os.getenv("GROQ_KEY")) # Create a GROQ client for chat completion


# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

def log_to_console(message: str, tag: Union[str | None] = None, spacing: int = 0) -> None:
    """Log a message to the console"""
    if tag is None:
        tag = "ROOT"
    spacing = max(0, spacing)
    spacing = min(5, spacing)
    space = "\n" * spacing
    print(f"{space}SERVER LOG [{tag}] {message}{space}")

def create_tables(db: SQLAlchemy) -> None:
    """Create the tables in the database"""
    log_to_console("Creating tables in the database", tag="DATABASE", spacing=1)
    db.create_all()

def init_db() -> None:
    """Initialise the database"""
    if not os.path.exists(os.path.join(USERDATA_DIR, 'users.db')):
        # This is done after running the app because the db requires the app to be running
        log_to_console("User Database not found.", tag="DATABASE", spacing=1)
        with app.app_context():
            create_tables(db)
    else:
        log_to_console("User Database found.", tag="DATABASE", spacing=1)

#-----------------------------------------------------Helper Functions-----------------------------------------------------#

# Authentication function - return True if the user is authorised to access the file, False otherwise
def authenticate(token: str) -> bool:
    return token == AUTHENTICATION_TOKEN
    
# Authenticate and send the file to the client
def authenticate_and_send_file(token: str, file_path: str):
    if authenticate(token):
        print('Authenticated, sending', file_path, 'to the client...')
        return send_from_directory('static', file_path)
    else:
        abort(403)

def create_user(user_name: str, password: str) -> None:
    """
    Create a new user with the given username and password
    """
    user_dir = os.path.join(USERDATA_DIR, user_name)
    os.makedirs(user_dir)
    os.makedirs(os.path.join(user_dir, 'chat history'))

def loginSuccess(username: str) -> None:
    """
    Create a new user with the given username and password
    """
    session['username'] = username

#-----------------------------------------------------Routes-----------------------------------------------------#

# Index page
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/prompt', methods=['POST'])
def prompt():
    data = request.json
    user_prompt = data.get('prompt', '')

    log_to_console(f"Received prompt: {user_prompt}", tag="PROMPT", spacing=1)

    try:
        completion = client.chat.completions.create(
        model="llama-3.3-70b-specdec",
        messages=[
            {
            "role": "system",
            "content": "You are a storytelling assistant, based on the given prompt generate a story with a title, introduction, body and conclusion and nothing else. Make sure the story is as detailed and interesting as possible.\n"
            },
            {
                "role": "user",
                "content": user_prompt
            },
        ],
        temperature=1,
        max_tokens=2048,
        top_p=1
        )

        reply = completion.choices[0].message.content
        
        log_to_console(f"Reply: {reply}", tag="PROMPT", spacing=1)
        # Run prompt
        if user_prompt == "error":
            raise Exception("Why would you want to see an error?")
        

        return jsonify({
            'success': True,
            'reply': reply
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })
    
@app.route('/generate-audio', methods=['POST'])
def generate_audio():
    try:
        # Get user input (e.g., text or story context)
        request_data = {
            'text': request.json.get('text', ''),
            'username': request.json.get('username', ''),
            'chatID': request.json.get('chatID', ''),
            'index': request.json.get('index', '')
        }

        log_to_console(f"Received request to generate audio: {request_data}", tag="GENERATE-AUDIO", spacing=1)

        if not request_data['text']:
            log_to_console("No text provided", tag="GENERATE-AUDIO", spacing=1)
            return jsonify({'error': 'No text provided'}), 400
        
        # Check if the request_data['username'] exists
        if not os.path.exists(os.path.join(USERDATA_DIR, request_data['username'])):
            log_to_console(f"Usernam '{request_data['username']}' not found", tag="GENERATE-AUDIO", spacing=1)
            return jsonify({'error': 'User not found'}), 404

        # Generate audio using WaveNet or equivalent model
        output_path = os.path.join(USERDATA_DIR, request_data['username'], 'chat history', str(request_data['chatID']), 'audio', f'{request_data["index"]}.wav')

        # Check if the audio file already exists
        if os.path.exists(output_path):
            log_to_console(f"Audio file for message {request_data['index']} in chat {request_data['chatID']} already exists", tag="GENERATE-AUDIO", spacing=1)
            return send_file(output_path, mimetype='audio/wav')

        tts.tts_to_file(request_data['text'], file_path=output_path)

        # Return the audio file to the client
        return send_file(output_path, mimetype='audio/wav')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/chat-id', methods=['POST'])
def get_chat_id():
    current_user = request.json.get('username', None)

    log_to_console(f"Received request for chat ID from {current_user}", tag="CHAT-ID", spacing=1)

    if current_user is None:
        log_to_console("No user provided", tag="CHAT-ID", spacing=1)
        return jsonify({'error': 'No user provided'}), 400

    users = os.listdir(USERDATA_DIR)

    if current_user not in users:
        log_to_console(f"User {current_user} not found", tag="CHAT-ID", spacing=1)
        return jsonify({'error': 'User not found'}), 404
    
    # Get the chat history of the user
    chat_history = os.listdir(os.path.join(USERDATA_DIR, current_user, 'chat history'))

    if len(chat_history) == 0:
        log_to_console(f"No chat history found for {current_user}, starting new chat", tag="CHAT-ID", spacing=1)
        chat_id = 1
        chat_dir = os.path.join(USERDATA_DIR, current_user, 'chat history', str(chat_id))
        # Create chat files
        os.makedirs(chat_dir)
        os.makedirs(os.path.join(chat_dir, 'audio'))
        os.makedirs(os.path.join(chat_dir, 'chat'))
        # Create messages json
        with open(os.path.join(chat_dir, 'chat', 'messages.json'), 'w') as f:
            json.dump([], f)
        os.makedirs(os.path.join(chat_dir, 'images'))
    else:
        # Check if most recent chat is empty
        most_recent_chat = chat_history[-1]
        chat_dir = os.path.join(USERDATA_DIR, current_user, 'chat history', most_recent_chat)
        # Load messages
        with open(os.path.join(chat_dir, 'chat', 'messages.json'), 'r') as f:
            messages = json.load(f)
        if len(messages) == 0:
            # Use the most recent chat
            chat_id = int(most_recent_chat)
        else:
            # Create a new chat
            chat_id = len(chat_history) + 1

            chat_dir = os.path.join(USERDATA_DIR, current_user, 'chat history', str(chat_id))

            # Create chat files
            os.makedirs(chat_dir)
            os.makedirs(os.path.join(chat_dir, 'audio'))
            os.makedirs(os.path.join(chat_dir, 'chat'))
            os.makedirs(os.path.join(chat_dir, 'images'))

    log_to_console(f"Chat ID for {current_user}: {chat_id}", tag="CHAT-ID", spacing=1)
        
    return jsonify({'chatID': chat_id}), 200

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    log_to_console(f"Received login request for user: {username}", tag="LOGIN", spacing=1)

    if not username or not password:
        return jsonify({'error': 'Missing username or password'}), 400

    user = User.query.filter_by(username=username).first()

    if user and bcrypt.check_password_hash(user.password, password):
        log_to_console(f"User {username} logged in successfully", tag="LOGIN", spacing=1)
        loginSuccess(username)
        return jsonify({'message': f'Welcome, {username}!'}), 200
    else:
        return jsonify({'error': 'Invalid username or password'}), 401
    
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get("password")

    log_to_console(f"Received registration request for user: {username}", tag="REGISTER", spacing=1)

    if not username or not password:
        return jsonify({'error': 'Missing username or password'}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'User already exists'}), 400
    
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    new_user = User(username=username, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    create_user(username, password)

    log_to_console(f"User {username} created successfully", tag="REGISTER", spacing=1)
    loginSuccess(username)
    return jsonify({'message': f'User {username} created successfully'}), 201


@app.route('/session-status', methods=['GET'])
def session_status():

    log_to_console(f"Checking session status for user: {session.get('username', 'None')}", tag="SESSION-STATUS", spacing=1)

    if 'username' in session:
        return jsonify({'loggedIn': True, 'user': session['username']})
    else:
        return jsonify({'loggedIn': False})

#-----------------------------------------------------Error Handling-----------------------------------------------------#

# Page to display when content is not found
@app.errorhandler(404)
def not_found_error(error):
    return render_template('content_not_found.html', error=error), 404

# Page to display when access is forbidden
@app.errorhandler(403)
def forbidden_error(error):
    return render_template('forbidden_access.html', error=error), 403

#-----------------------------------------------------Main Function-----------------------------------------------------#

if __name__ == '__main__':
    if not os.path.exists(USERDATA_DIR):
        os.makedirs(USERDATA_DIR)

    init_db()
    app.run(debug=True, use_reloader=False)