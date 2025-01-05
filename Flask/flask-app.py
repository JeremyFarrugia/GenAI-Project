from flask import Flask, render_template, send_from_directory, abort, request, jsonify, send_file, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import os, json
import numpy as np
import soundfile as sf
from typing import Union


from transformers import VitsModel, AutoTokenizer
import torch
import scipy.io.wavfile as wav

tts_model = VitsModel.from_pretrained("facebook/mms-tts-eng") # https://huggingface.co/facebook/mms-tts-eng  Consider wavnet? I think it's better but it requires use of google cloud services
tokeniser = AutoTokenizer.from_pretrained("facebook/mms-tts-eng")

def generate_tts_file(text: str, output_path: str) -> None:
    """
    Generate a TTS audio file from the given text and save it to the output path
    """
    log_to_console(f"Generating TTS audio file for text: {text}", tag="GENERATE-TTS-FILE", spacing=1)
    inputs = tokeniser(text, return_tensors="pt")

    with torch.no_grad():
        output = tts_model(**inputs).waveform.squeeze(0)  # Remove batch dimension if present

    # Scale waveform to int16
    audio_data = (output.numpy() * 32767).astype(np.int16)  # Scale to 16-bit PCM

    log_to_console(f"Saving audio file to: {output_path}", tag="GENERATE-TTS-FILE", spacing=1)
    wav.write(output_path, rate=tts_model.config.sampling_rate, data=audio_data)
    log_to_console(f"Audio file saved successfully", tag="GENERATE-TTS-FILE", spacing=1)

import torchaudio
from audiocraft.models import AudioGen # https://github.com/facebookresearch/audiocraft/blob/main/docs/AUDIOGEN.md
from audiocraft.data.audio import audio_write

#audio_model = AudioGen.get_pretrained('facebook/audiogen-medium')

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

#from TTS.api import TTS
#tts = TTS("tts_models/en/ljspeech/tacotron2-DDC")

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
STATIC_DIR = os.path.join(SCRIPT_DIR, 'static')
USERDATA_DIR = os.path.join(STATIC_DIR, 'userdata')
AUDIO_DIR = os.path.join(STATIC_DIR, 'audio')

CLEAR_TEMP_ON_START = True # Flag to clear all temporary files on server start

#-------------------------------------------------------Server Setup-------------------------------------------------------#

app = Flask(__name__)

app.static_folder = 'static' # Set the static folder to the 'static' folder in the current directory
app.template_folder = 'templates' # Set the template folder to the 'templates' folder in the current directory

app.secret_key = os.urandom(24) # Set the secret key for the session

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(USERDATA_DIR, "users.db")}' # Set the database URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Disable modification tracking
db = SQLAlchemy(app) # Create a database object
bcrypt = Bcrypt(app) # Create a bcrypt object for password hashing

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
    os.makedirs(os.path.join(user_dir, 'temp'))
    os.makedirs(os.path.join(user_dir, 'chat history'))

def loginSuccess(username: str) -> None:
    """
    Create a new user with the given username and password
    """
    session['username'] = username

def clear_temp_files(username: str) -> None:
    """
    Clear the temporary files for the given user
    """
    temp_dir = os.path.join(USERDATA_DIR, username, 'temp')
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    for file in os.listdir(temp_dir):
        file_path = os.path.join(temp_dir, file)
        os.remove(file_path)
        log_to_console(f"Removed temporary file: {file_path}", tag="CLEAR-TEMP-FILES", spacing=0)

def clear_all_temp_files() -> None:
    """
    Clear all temporary files
    """
    try:
        for user in os.listdir(USERDATA_DIR):
            if os.path.isdir(os.path.join(USERDATA_DIR, user)):
                clear_temp_files(user)
            else:
                log_to_console(f"Skipping non-directory file: {user}", tag="CLEAR-TEMP-FILES", spacing=1)
    except Exception as e:
        log_to_console(f"Error clearing temporary files: {e}", tag="CLEAR-TEMP-FILES", spacing=1)

def debug_users() -> None:
    """
    Debug function to print all user details from the database
    """
    users = User.query.all()
    log_to_console("Printing all users in the database", tag="DEBUG-USERS", spacing=1)
    for user in users:
        # Note: password is currently printed as encrypted
        log_to_console(f"User: {user.username}, Password: {user.password}", tag="DEBUG-USERS", spacing=0)

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
        # Run prompt
        reply = "I repeat what you say: " + user_prompt
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
    
@app.route('/generate-tts', methods=['POST'])
def tts_request():
    try:
        # disable debug mode (debug mode was causing some issue, instead of investigating, I just disabled and re-enabled later)
        app.debug = False

        # Get user input (e.g., text or story context)
        request_data = {
            'text': request.json.get('text', ''),
            'username': request.json.get('username', ''),
            'chatID': request.json.get('chatID', ''),
            'index': request.json.get('index', '')
        }

        log_to_console(f"Received request to generate tts: {request_data}", tag="GENERATE-TTS", spacing=1)

        if not request_data['text']:
            log_to_console("No text provided", tag="GENERATE-TTS", spacing=1)
            return jsonify({'error': 'No text provided'}), 400
        
        # Check if the request_data['username'] exists
        if not os.path.exists(os.path.join(USERDATA_DIR, request_data['username'])):
            log_to_console(f"Username '{request_data['username']}' not found", tag="GENERATE-TTS", spacing=1)
            return jsonify({'error': 'User not found'}), 404

        output_path = os.path.join(USERDATA_DIR, request_data['username'], 'temp')
        # Create temp directory if it doesn't exist
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        output_path = os.path.join(output_path, f"{request_data['chatID']}_{request_data['index']}.wav")

        # Check if the audio file already exists
        if os.path.exists(output_path):
            log_to_console(f"Audio file for message {request_data['index']} in chat {request_data['chatID']} already exists", tag="GENERATE-TTS", spacing=1)
            return send_file(output_path, mimetype='audio/wav')

        #tts.tts_to_file(request_data['text'], file_path=output_path)

        generate_tts_file(request_data['text'], output_path)

        # Enable debug mode (Re-enabling might introduce the same issues but it seemed to work)
        app.debug = True

        # Return the audio file to the client
        return send_file(output_path, mimetype='audio/wav')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

'''@app.route('/generate-audio', methods=['POST'])
def sound_effect_request(): #TODO - change implementation to be more suitable for story ornamentation
    try:
        # disable debug mode (debug mode was causing some issue, instead of investigating, I just disabled and re-enabled later)
        app.debug = False

        # Get user input (e.g., text or story context)
        request_data = {
            'text': request.json.get('text', ''),
            'username': request.json.get('username', ''),
            'chatID': request.json.get('chatID', ''),
            'index': request.json.get('index', '')
        }

        log_to_console(f"Received request to generate sound effect: {request_data}", tag="GENERATE-AUDIO", spacing=1)

        if not request_data['text']:
            log_to_console("No text provided", tag="GENERATE-AUDIO", spacing=1)
            return jsonify({'error': 'No text provided'}), 400
        
        # Check if the request_data['username'] exists # TODO - turn all these checks into functions
        if not os.path.exists(os.path.join(USERDATA_DIR, request_data['username'])):
            log_to_console(f"Username '{request_data['username']}' not found", tag="GENERATE-AUDIO", spacing=1)
            return jsonify({'error': 'User not found'}), 404

        output_path = os.path.join(USERDATA_DIR, request_data['username'], 'temp')
        # Create temp directory if it doesn't exist
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        output_path = os.path.join(output_path, f"{request_data['chatID']}_{request_data['index']}_se.wav")

        # Check if the audio file already exists
        if os.path.exists(output_path):
            log_to_console(f"Audio file for message {request_data['index']} in chat {request_data['chatID']} already exists", tag="GENERATE-AUDIO", spacing=1)
            return send_file(output_path, mimetype='audio/wav')

        descriptions = request_data['text']
        wav = audio_model.generate(descriptions)

        # Will save with loudness normalization at -14 db LUFS.
        audio_write(output_path, wav.cpu(), audio_model.sample_rate, strategy="loudness", loudness_compressor=True)

        # Enable debug mode (Re-enabling might introduce the same issues but it seemed to work)
        app.debug = True

        # Return
        return send_file(output_path, mimetype='audio/wav')
    except Exception as e:
        return jsonify({'error': str(e)}), 500'''
    
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

        message_file = os.path.join(chat_dir, 'chat', 'messages.json') # Idk something was breaking here, tbh long term I think this is getting removed anyway
        if not os.path.exists(message_file):
            os.makedirs(os.path.join(chat_dir, 'chat'), exist_ok=True)
            # Create file
            with open(message_file, 'w') as f:
                json.dump([], f)
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
    
@app.route('/logout', methods=['POST'])
def logout():
    log_to_console(f"Logging out user: {session.get('username', 'None')}", tag="LOGOUT", spacing=1)
    session.pop('username', None)

    # Clear cookies
    response = jsonify({'message': 'Logged out successfully'})
    response.set_cookie('logged_in', '', expires=0)
    response.set_cookie('username', '', expires=0)
    return response
    
@app.route('/set-login-cookie', methods=['POST'])
def set_login_cookie():
    data = request.json
    username = data.get('username')

    log_to_console(f"Setting login cookie for user: {username}", tag="SET-COOKIE", spacing=1)

    days = 30
    duration = 60*60*24 * days
    response = jsonify({'message': f'Login cookie set for {username}'})
    response.set_cookie('logged_in', 'true', max_age=duration, secure=True, httponly=True, samesite='Strict')
    response.set_cookie('username', username, max_age=duration, secure=True, httponly=True, samesite='Strict')
    return response
    
# Check user login status by checkin cookies
@app.route('/login-status', methods=['GET'])
def login_status():
    log_to_console("Checking login status", tag="LOGIN-STATUS", spacing=1)
    logged_in = request.cookies.get('logged_in')
    if logged_in:
        log_to_console(f"log in flag found: {logged_in}", tag="LOGIN-STATUS", spacing=1)
        username = request.cookies.get('username')
        # Check if the user exists
        log_to_console(f"Checking if user {username} exists", tag="LOGIN-STATUS", spacing=1)
        if User.query.filter_by(username=username).first():
            log_to_console(f"User {username} found", tag="LOGIN-STATUS", spacing=1)
            return jsonify({'logged_in': True, 'user': username})
        else:
            log_to_console(f"User {username} not found", tag="LOGIN-STATUS", spacing=1)
            return jsonify({'logged_in': False})
    else:
        return jsonify({'logged_in': False})
    
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

    if CLEAR_TEMP_ON_START:
        clear_all_temp_files()

    with app.app_context():
        debug_users()

    app.run(debug=True)