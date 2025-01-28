from flask import Flask, render_template, send_from_directory, abort, request, jsonify, send_file, session, url_for, Response, stream_with_context
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_socketio import SocketIO, emit

import os, json
import numpy as np
import soundfile as sf
from typing import Union, Literal

from groq import Groq
from dotenv import load_dotenv

from transformers import VitsModel, AutoTokenizer
import torch
import scipy.io.wavfile as wav

import torchaudio
from audiocraft.models import AudioGen, MusicGen 
from audiocraft.data.audio import audio_write

from diffusers import StableDiffusionPipeline, EulerDiscreteScheduler, LMSDiscreteScheduler

from PIL import Image
from io import BytesIO
import base64

import sqlite3

"""
TODO: 
users
- modal popups/updates instead of alerts
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

AUTHENTICATION_TOKEN = 'a123' # TODO - Delete?

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
STATIC_DIR = os.path.join(SCRIPT_DIR, 'static')
USERDATA_DIR = os.path.join(STATIC_DIR, 'userdata')
AUDIO_DIR = os.path.join(STATIC_DIR, 'audio')

load_dotenv()
CLEAR_TEMP_ON_START = True # Flag to clear all temporary files on server start

# NOTE: Debug mode causes the audio generation models to crash the server, but if set to false you will have to manually restart the server to see changes
DEBUG = False
# I have also been informed that the reloader causes issues with groq

#-------------------------------------------------------Server Setup-------------------------------------------------------#

app = Flask(__name__)

app.static_folder = 'static' # Set the static folder to the 'static' folder in the current directory
app.template_folder = 'templates' # Set the template folder to the 'templates' folder in the current directory

app.secret_key = os.urandom(24) # Set the secret key for the session

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(USERDATA_DIR, "users.db")}' # Set the database URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Disable modification tracking
db = SQLAlchemy(app) # Create a database object
bcrypt = Bcrypt(app) # Create a bcrypt object for password hashing

socketio = SocketIO(app)

if not DEBUG:
    client = Groq(api_key=os.getenv("GROQ_KEY")) # Create a GROQ client for chat completion

tts_model = VitsModel.from_pretrained("facebook/mms-tts-eng") # https://huggingface.co/facebook/mms-tts-eng  Consider wavnet? I think it's better but it requires use of google cloud services
tokeniser = AutoTokenizer.from_pretrained("facebook/mms-tts-eng") 

audio_model = None 
music_model = None
image_pipe = None
if not DEBUG: # Safety - See above (DEBUG flag)
    audio_model = AudioGen.get_pretrained('facebook/audiogen-medium') # https://github.com/facebookresearch/audiocraft/blob/main/docs/AUDIOGEN.md  https://huggingface.co/facebook/audiogen-medium
    audio_model.set_generation_params(duration=5)  # Length of audio in seconds (Will be overwritten by the duration parameter in the generate_sound_file function)
    #music_model = MusicGen.get_pretrained('facebook/musicgen-melody') # https://huggingface.co/facebook/musicgen-melody
    music_model = MusicGen.get_pretrained('facebook/musicgen-medium') # Switched away from melody since it had features that were not needed (large caused memory errors) https://huggingface.co/facebook/musicgen-medium
    music_model.set_generation_params(duration=20)

    scheduler = EulerDiscreteScheduler.from_pretrained("stabilityai/stable-diffusion-2-1-base", subfolder="scheduler")
    image_pipe = StableDiffusionPipeline.from_pretrained("stabilityai/stable-diffusion-2-1-base", scheduler=scheduler, torch_dtype=torch.float16).to("cuda")
    # Add model optimization
    if torch.cuda.is_available():
        image_pipe.enable_model_cpu_offload()  # Optimize memory usage
        image_pipe.enable_vae_slicing()
    if torch.cuda.device_count() > 1:
        image_pipe.parallelize()  # Use multiple GPUs


# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Story(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(80), nullable=False)
    data_path = db.Column(db.String(200), unique=True, nullable=False)
    isPublic = db.Column(db.Boolean, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

def add_story_to_db(title: str, data_path: str, isPublic: bool, user_id: int) -> int:
    """
    Add a story to the database
    
    Returns:
    - The ID of the newly added story
    """
    new_story = Story(title=title, data_path=data_path, isPublic=isPublic, user_id=user_id)
    db.session.add(new_story)
    db.session.commit()
    return Story.query.filter_by(data_path=data_path).first().id

def change_story_privacy(story_id: int, isPublic: bool) -> None:
    """
    Change the privacy of a story in the database
    """
    story = Story.query.filter_by(id=story_id).first()
    story.isPublic = isPublic
    db.session.commit()

def get_story_data(story_id: int) -> dict:
    """
    Get the data for a story from the database
    Data includes:
    - Title
    - Data path
    - isPublic flag
    - Username of the author
    """
    story = Story.query.filter_by(id=story_id).first()
    username = User.query.filter_by(id=story.user_id).first().username
    return {
        'title': story.title,
        'data_path': story.data_path,
        'isPublic': story.isPublic,
        'username': username
    }

def get_story_id(title: str, user_id: int) -> Union[int, None]:
    """
    Get the ID of a story from the database
    """
    story = Story.query.filter_by(title=title, user_id=user_id).first()
    if story:
        return story.id
    return None

def get_all_stories() -> list[dict]:
    """
    Get all stories from the database
    """
    stories = Story.query.all()
    story_data = []
    for story in stories:
        username = User.query.filter_by(id=story.user_id).first().username
        story_data.append({
            'title': story.title,
            'data_path': story.data_path,
            'isPublic': story.isPublic,
            'username': username
        })
    return story_data


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
    os.makedirs(os.path.join(user_dir, 'stories'))

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

def generate_sound_file(model: Literal['audio', 'music'], description: str, output_path: str, duration: int = 5) -> None:
    """
    Generate an audio file (sound effect or music) from the given description and save it to the output path
    """

    if DEBUG:
        raise ValueError("Audio generation is disabled in debug mode") # Safety - See above (DEBUG flag)

    if model == 'audio':
        log_to_console(f"Generating audio file for description: {description}", tag="GENERATE-AUDIO-FILE", spacing=1)
        audio_model.set_generation_params(duration=duration)
        wav = audio_model.generate([description])
        audio_write(output_path, wav.cpu(), audio_model.sample_rate, strategy="loudness", loudness_compressor=True)
    elif model == 'music':
        log_to_console(f"Generating music file for description: {description}", tag="GENERATE-MUSIC-FILE", spacing=1)
        music_model.set_generation_params(duration=duration)
        wav = music_model.generate([description])
        audio_write(output_path, wav.cpu(), music_model.sample_rate, strategy="loudness")
    else:
        raise ValueError("Invalid model type")

    log_to_console(f"Audio file saved successfully", tag="GENERATE-AUDIO-FILE", spacing=1)


def generate_image_file(description: str, output_path: str, style: Literal['realistic', 'artistic', 'cartoonish'] = 'artistic') -> None:
    """
    Generate an image file from the given description and save it to the output path
    """
    if DEBUG:
        raise ValueError("Image generation is disabled in debug mode")

    log_to_console(f"Generating image file for description: {description}", tag="GENERATE-IMAGE-FILE", spacing=1)

    try:
        # Style prompts dictionary
        style_prompts = {
            "realistic": "Realistic, highly detailed, professional photography, 8k, HDR lighting",
            "artistic": "highly detailed, digital painting, trending on artstation, ethereal lighting, soft focus",
            "cartoonish": "vibrant cartoon style, bold lines, pastel colors, dynamic composition"
        }

        # Enhance prompt with style
        enhanced_prompt = f"{description}, {style_prompts.get(style, '')}"

        # Generation parameters
        params = {
            'num_inference_steps': 28,
            'guidance_scale': 7.5,
            'negative_prompt': 'low quality, blurry, deformed, watermarked, signature',
        }

        # Generate image
        image = image_pipe(enhanced_prompt, **params).images[0]

        # Ensure directory exists and save
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        image.save(output_path, format='PNG')

        log_to_console(f"Image file saved successfully to: {output_path}", tag="GENERATE-IMAGE-FILE", spacing=1)

    except Exception as e:
        log_to_console(f"Error generating image: {e}", tag="GENERATE-IMAGE-FILE", spacing=1)
        raise e

def validate_request(text: str, username: str, tag: str) -> tuple[bool, Response, int]:
    """
    Validate the request data

    Returns:
    - True if the request is valid, False otherwise
    - Response object if the request is invalid
    - Status code if the request is invalid
    """
    if not text:
        log_to_console("No text provided", tag=tag, spacing=1)
        return jsonify({'error': 'No text provided'}), 400
    
    # Check if user is in database
    user = User.query.filter_by(username=username).first()
    if not user:
        log_to_console(f"User '{username}' not found", tag=tag, spacing=1)
        return jsonify({'error': 'User not found'}), 404
        
    # Check if the request_data['username'] exists
    if not os.path.exists(os.path.join(USERDATA_DIR, username)):
        log_to_console(f"Username '{username}' not found", tag=tag, spacing=1)
        return jsonify({'error': 'User not found'}), 404

    output_path = os.path.join(USERDATA_DIR, username, 'temp')
    # Create temp directory if it doesn't exist
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    return True, None, 0 # Success

def get_thumbnail(thumbnail_path, debug: bool = False) -> Union[str, None]:
    """Get the thumbnail for a file if it exist otherwise return None"""
    log_to_console(f"Checking for thumbnail at path: {thumbnail_path}", tag="THUMBNAIL", spacing=1)

    if os.path.exists(thumbnail_path):
        with open(thumbnail_path, 'rb') as thumbnail_file:
            thumbnail = base64.b64encode(thumbnail_file.read()).decode('utf-8')
        return thumbnail
    else:
        log_to_console(f"Thumbnail not found at path: {thumbnail_path}", tag="THUMBNAIL", spacing=1)
        raise FileNotFoundError(f"Thumbnail not found at path: {thumbnail_path}")

#-----------------------------------------------------Routes-----------------------------------------------------#

#-------------------------------------Pages-------------------------------------#

# Index page
@app.route('/')
@app.route('/chat')
def index():
    return render_template('index.html')

@app.route('/stories-<username>')
def user_stories(username):

    userData = os.path.join(USERDATA_DIR, username)

    if username is None:
        return render_template('content_not_found.html', error="No user provided"), 404
    elif not User.query.filter_by(username=username).first():
        return render_template('content_not_found.html', error="User not found"), 404
    elif not os.path.exists(userData):
        return render_template('content_not_found.html', error="User data not found"), 404
    elif username != session.get('username', None): # I'm not sure this is the best way to check if the user is logged in
        return render_template('forbidden_access.html', error="You do not have permission to access this page"), 403
    
    # Get the stories for the user
    stories = os.listdir(os.path.join(userData, 'stories'))

    story_data = []
    try:
        for story in stories:
            log_to_console(f"Checking story: {story}", tag="USER-STORIES", spacing=1)
            thumbnail = os.path.join(userData, 'stories', story, 'thumbnail.jpg')
            try:
                thumbnail = get_thumbnail(thumbnail)
            except FileNotFoundError:
                log_to_console(f"Thumbnail not found for story: {story} by user: {username}, skipping", tag="USER-STORIES", spacing=1)
                continue
            title = story

            userID = User.query.filter_by(username=username).first().id
            storyID = get_story_id(title, userID)
            if storyID is None:
                log_to_console(f"Story ID not found for story: {story} by user: {username}", tag="USER-STORIES", spacing=1)
                continue

            url = '/story-' + str(storyID)

            story_data.append({
                'thumbnail': thumbnail,
                'title': title,
                'url': url
            })
    except Exception as e:
        return render_template('content_not_found.html', error=str(e)), 404

    """
    TODO - consider setting this up in a way where if the user accessing this page is the same as the user in the URL
    the page will be the same as it currently is, but if the user is different it will only show that user's public stories
    with the page title being the user's name and the page giving a different message if there are no public stories
    Also if you click on a user's name it will take you to this page
    """
    return render_template('story_catalogue.html', username=username, stories=story_data, pageTitle="Your Stories")

@app.route('/public_stories')
def public_stories():

    stories = get_all_stories()
    story_data = []
    for story in stories:
        if not story['isPublic']:
            continue

        thumbnail = os.path.join(story['data_path'], 'thumbnail.jpg') # TODO - I decided to use enumerations for the story path instead of the title
        #thumbnail = os.path.join(USERDATA_DIR, story['username'], 'stories', story['title'], 'thumbnail.jpg') 
        thumbnail = get_thumbnail(thumbnail)

        story_data.append({
            'thumbnail': thumbnail,
            'title': story['title'],
            'url': '/story-' + story['username'],
            'creator': story['username']
        })
    
    return render_template('story_catalogue.html', stories=story_data, pageTitle="Public Stories")


@app.route('/story-<storyID>')
def story(storyID):
    try:
        storyID = int(storyID)
        story_data = get_story_data(storyID)
    except ValueError:
        return render_template('content_not_found.html', error="Invalid story ID"), 404
    
    # If story is not public check if the user is logged in
    if not story_data['isPublic']:
        accessingUser = session.get('username', None)
        if not accessingUser:
            return render_template('forbidden_access.html', error="You do not have permission to access this page"), 403
        if accessingUser != story_data['username']:
            return render_template('forbidden_access.html', error="You do not have permission to access this page, this story is private."), 403
        
    # Try access story data
    try:
        os.path.exists(story_data['data_path'])
        # Remove the first part of data path
        story_data['safe_path'] = story_data['data_path'].replace(USERDATA_DIR, '')[1:] # Remove the first character which is a slash
        # Change the data path so that it could be embedded in the page without creating errors due to \
        story_data['safe_path'] = story_data['safe_path'].replace('\\', '/')
        # TODO - Load story data

    except FileNotFoundError:
        return render_template('content_not_found.html', error="Story data not found"), 404
        
    return render_template('story.html', story=story_data)


#--------------------------------------API--------------------------------------#

@app.route('/prompt', methods=['POST'])
def prompt():
    data = request.json
    user_prompt = data.get('prompt', '')

    log_to_console(f"Received prompt: {user_prompt}", tag="PROMPT", spacing=1)

    if user_prompt == "error":
            raise Exception("Why would you want to see an error?")

    if DEBUG:
        return jsonify({
            'success': True,
            'reply': "This is a test reply"
        })
    
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
        if DEBUG:
            app.debug = False

        # Get user input (e.g., text or story context)
        request_data = {
            'text': request.json.get('text', ''),
            'username': request.json.get('username', ''),
            'index': request.json.get('index', ''),
            'alreadyGenerated': request.json.get('alreadyGenerated', False)
        }

        log_to_console(f"Received request to generate tts: {request_data}", tag="GENERATE-TTS", spacing=1)

        validate_success, response, status_code = validate_request(request_data['text'], request_data['username'], "GENERATE-TTS")
        if not validate_success:
            return response, status_code
        
        output_path = os.path.join(USERDATA_DIR, request_data['username'], 'temp')        
        output_path = os.path.join(output_path, f"{request_data['index']}.wav")

        # Check if the audio file already exists
        if request_data['alreadyGenerated'] and os.path.exists(output_path):
            log_to_console(f"Audio file for message {request_data['index']} already exists", tag="GENERATE-TTS", spacing=1)
            return send_file(output_path, mimetype='audio/wav')

        generate_tts_file(request_data['text'], output_path)

        # Enable debug mode (Re-enabling might introduce the same issues but it seemed to work)
        if DEBUG:
            app.debug = True

        # Return the audio file to the client
        return send_file(output_path, mimetype='audio/wav')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate-audio', methods=['POST'])
def sound_effect_request(): #TODO - change implementation to be more suitable for story ornamentation
    try:
        # disable debug mode (debug mode was causing some issue, instead of investigating, I just disabled and re-enabled later)
        if DEBUG:
            app.debug = False

        # Get user input (e.g., text or story context)
        request_data = {
            'text': request.json.get('text', ''),
            'username': request.json.get('username', ''),
            'index': request.json.get('index', '')
        }

        log_to_console(f"Received request to generate sound effect: {request_data}", tag="GENERATE-AUDIO", spacing=1)

        validate_success, response, status_code = validate_request(request_data['text'], request_data['username'], "GENERATE-AUDIO")
        if not validate_success:
            return response, status_code
        
        output_path = os.path.join(USERDATA_DIR, request_data['username'], 'temp')
        output_path = os.path.join(output_path, f"{request_data['index']}_se.wav")

        # Check if the audio file already exists
        if os.path.exists(output_path):
            log_to_console(f"Audio file for message {request_data['index']} already exists", tag="GENERATE-AUDIO", spacing=1)
            return send_file(output_path, mimetype='audio/wav')

        descriptions = request_data['text']
        generate_sound_file('audio', descriptions, output_path, duration=5)

        # Enable debug mode (Re-enabling might introduce the same issues but it seemed to work)
        if DEBUG:
            app.debug = True

        # Return
        return send_file(output_path, mimetype='audio/wav')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/generate-image', methods=['POST'])
def image_request():
    try:
        # disable debug mode temporarily
        if DEBUG:
            app.debug = False

        # Get request data
        request_data = {
            'text': request.json.get('text', ''),
            'username': request.json.get('username', ''),
            'index': request.json.get('index', ''),
            'style': request.json.get('style', 'artistic')
        }

        log_to_console(f"Received image generation request: {request_data}", tag="GENERATE-IMAGE", spacing=1)

        validate_success, response, status_code = validate_request(
            request_data['text'],
            request_data['username'],
            "GENERATE-IMAGE"
        )
        if not validate_success:
            return response, status_code

        # Create images directory if it doesn't exist
        output_path = os.path.join(USERDATA_DIR, request_data['username'], 'temp', f"{request_data['index']}.png")

        generate_image_file(request_data['text'], output_path, style=request_data['style'])

        if DEBUG:
            app.debug = True

        return send_file(output_path, mimetype='image/png')

    except Exception as e:
        log_to_console(f"Error in image generation request: {str(e)}", tag="GENERATE-IMAGE", spacing=1)
        return jsonify({'error': str(e)}), 500 #maybe change to wahtever idk error codes i copied jer

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
            loginSuccess(username)
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
    
import time
@socketio.on('generate-story')
def generate_story(data):
    emit('story-progress', {'message': 'Generating story...'})
    username = data.get('username', None)
    story_content = data.get('content', None)

    data_path = os.path.join(USERDATA_DIR, username, 'stories')
    data_path = os.path.join(data_path, f"{len(os.listdir(data_path)) + 1}") # Directories are enumerated
    # Create the story directory
    os.makedirs(data_path)

    title = 'Story Title' # TODO - Implement title generation

    log_to_console(f"Received story content: {story_content}", tag="GENERATE-STORY", spacing=1)
    time.sleep(3) # Simulate story generation

    # Currently all stories are private and need to be manually set to public TODO - remember to implement this 
    story_num = add_story_to_db(title=title, data_path=data_path, isPublic=False, user_id=User.query.filter_by(username=username).first().id)
    emit('story-complete', {'message': 'Story generated successfully!', 'title': title, 'url': f'/story-{story_num}'})

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

def fix_userData():
    """
    Fix the userData directory by creating the necessary directories for each user

    Created this for convenience since the old setup was different
    """
    users = os.listdir(USERDATA_DIR)
    for user in users:
        if not os.path.isdir(os.path.join(USERDATA_DIR, user)):
            log_to_console(f"Skipping non-directory file: {user}", tag="FIX-USERDATA", spacing=1)
            continue

        user_dir = os.path.join(USERDATA_DIR, user)
        if not os.path.exists(os.path.join(user_dir, 'temp')):
            os.makedirs(os.path.join(user_dir, 'temp'))
            log_to_console(f"Created temp directory for user: {user}", tag="FIX-USERDATA", spacing=1)
        if os.path.exists(os.path.join(user_dir, 'chat history')):
            delete_folder(os.path.join(user_dir, 'chat history'))
            log_to_console(f"Removed chat history directory for user: {user}", tag="FIX-USERDATA", spacing=1)
        if not os.path.exists(os.path.join(user_dir, 'stories')):
            os.makedirs(os.path.join(user_dir, 'stories'))
            log_to_console(f"Created stories directory for user: {user}", tag="FIX-USERDATA", spacing=1)

def delete_redundant_users():
    """
    Delete files and folders associated with users that are no longer in the database
    """

    users = os.listdir(USERDATA_DIR)
    for user in users:
        if not os.path.isdir(os.path.join(USERDATA_DIR, user)):
            log_to_console(f"Skipping non-directory file: {user}", tag="DELETE-REDUNDANT-FILES", spacing=1)
            continue

        user_db = User.query.filter_by(username=user).first()
        if not user_db:
            delete_folder(os.path.join(USERDATA_DIR, user))
            log_to_console(f"Deleted redundant files for user: {user}", tag="DELETE-REDUNDANT-FILES", spacing=1)

def clear_stories():
    """
    Clear all story data from the database
    """
    log_to_console("Clearing all story data", tag="CLEAR-STORIES", spacing=1)

    stories = Story.query.all()
    for story in stories:
        db.session.delete(story)
    db.session.commit()

    # Clear all story files for all users
    users = os.listdir(USERDATA_DIR)
    for user in users:
        if not os.path.isdir(os.path.join(USERDATA_DIR, user)):
            log_to_console(f"Skipping non-directory file: {user}", tag="CLEAR-STORIES", spacing=1)
            continue

        user_dir = os.path.join(USERDATA_DIR, user, 'stories')
        for story in os.listdir(user_dir):
            delete_folder(os.path.join(user_dir, story))
            log_to_console(f"Deleted story for user: {user}", tag="CLEAR-STORIES", spacing=1)
    

def delete_folder(path: str) -> None:
    """
    Recursively delete a folder and its contents
    """
    log_to_console(f"Recursively deleting {path}", tag="DELETE-FOLDER", spacing=0)

    if os.path.isdir(path):
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            delete_folder(item_path)
        os.rmdir(path)
    else:
        os.remove(path)


DELETE_STORIES = True

if __name__ == '__main__':
    if not os.path.exists(USERDATA_DIR):
        os.makedirs(USERDATA_DIR)

    init_db()

    fix_userData()  # TODO - remove once all users have been fixed

    if CLEAR_TEMP_ON_START:
        clear_all_temp_files()

    with app.app_context():
        debug_users()
        delete_redundant_users()
        if DELETE_STORIES:
            clear_stories()


    app.run(debug=DEBUG)
