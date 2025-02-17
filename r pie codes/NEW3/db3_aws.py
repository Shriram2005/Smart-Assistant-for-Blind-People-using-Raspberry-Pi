import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/pi/gcloud.json"
from google.cloud import vision, translate_v2, texttospeech
from google.api_core import retry, exceptions
import os
import RPi.GPIO as GPIO
import time
from picamera2 import Picamera2
import sys
import mysql.connector
from mysql.connector import pooling
import base64
from datetime import datetime

# AWS RDS MySQL Configuration
MYSQL_CONFIG = {
    'host': 'smart-aid-db.cjlzjqasq5hy.ap-south-1.rds.amazonaws.com',  # AWS RDS endpoint
    'user': 'admin',                # AWS RDS username
    'password': 'smartaid123',      # AWS RDS password
    'database': 'smart_aid_db',     # AWS RDS database name
    'port': 3306,                   # AWS RDS port
    'pool_name': 'mypool',
    'pool_size': 5,
    'connect_timeout': 10
}

# Create a connection pool
try:
    connection_pool = mysql.connector.pooling.MySQLConnectionPool(**MYSQL_CONFIG)
    print("Database connection pool created successfully")
except Exception as e:
    print(f"Error creating connection pool: {str(e)}")
    sys.exit(1)

def get_db_connection():
    """Get a connection from the pool with retry mechanism"""
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            connection = connection_pool.get_connection()
            return connection
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Failed to get database connection after {max_retries} attempts: {str(e)}")
                raise
            print(f"Connection attempt {attempt + 1} failed, retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)

def init_mysql_database():
    """Initialize the database with proper error handling"""
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Create table if it doesn't exist with optimized structure
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS captured_images (
                id INT AUTO_INCREMENT PRIMARY KEY,
                image LONGBLOB NOT NULL,
                original_text TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                english_translation TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                hindi_translation TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                marathi_translation TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_timestamp (timestamp)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ''')
        
        connection.commit()
        print("AWS RDS MySQL database initialized successfully")
        
    except Exception as e:
        print(f"Error initializing AWS RDS database: {str(e)}")
        sys.exit(1)
    finally:
        if connection:
            if 'cursor' in locals():
                cursor.close()
            connection.close()

def store_in_mysql(image_path, original_text, english_text, hindi_text, marathi_text):
    """Store data in AWS RDS with proper connection handling"""
    connection = None
    try:
        # Read and compress the image file
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Insert data with proper parameter handling
        query = '''
            INSERT INTO captured_images 
            (image, original_text, english_translation, hindi_translation, marathi_translation)
            VALUES (%s, %s, %s, %s, %s)
        '''
        values = (image_data, original_text, english_text, hindi_text, marathi_text)
        
        cursor.execute(query, values)
        connection.commit()
        
        print(f"Data stored in AWS RDS with ID: {cursor.lastrowid}")
        
    except Exception as e:
        print(f"Error storing data in AWS RDS: {str(e)}")
        if connection:
            connection.rollback()
    finally:
        if connection:
            if 'cursor' in locals():
                cursor.close()
            connection.close()

# Rest of the imports and GPIO setup remain the same
BUTTON_PIN = 18
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Global variables
button_press_count = 0
current_language = None
vision_client = None
translate_client = None
tts_client = None
camera = None

AUDIO_PATHS = {
    'original': "original_audio.mp3",
    'english': "english_audio.mp3",
    'hindi': "hindi_audio.mp3",
    'marathi': "marathi_audio.mp3",
    'capture': "capture_sound.mp3",
    'no_text': "no_text_found.mp3",
    'complete': "translation_complete.mp3"
}

def initialize_clients():
    global vision_client, translate_client, tts_client, camera
    try:
        vision_client = vision.ImageAnnotatorClient()
        translate_client = translate_v2.Client()
        tts_client = texttospeech.TextToSpeechClient()
        camera = Picamera2()
    except Exception as e:
        time.sleep(5)
        initialize_clients()

@retry.Retry(predicate=retry.if_exception_type(exceptions.DeadlineExceeded))
def text_to_speech(text, language_code, output_path):
    global tts_client
    try:
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=f"{language_code}-Standard-A"
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0
        )
        
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        with open(output_path, "wb") as out:
            out.write(response.audio_content)
    except Exception as e:
        tts_client = texttospeech.TextToSpeechClient()
        raise e

def initialize_feedback_sounds():
    messages = [
        ("Image captured", 'capture'),
        ("No text found", 'no_text'),
        ("Translation complete", 'complete')
    ]
    for message, path in messages:
        try:
            text_to_speech(message, "en-US", AUDIO_PATHS[path])
        except Exception:
            time.sleep(2)
            continue

@retry.Retry(predicate=retry.if_exception_type(exceptions.DeadlineExceeded))
def detect_text_and_language(image_path):
    global vision_client, translate_client
    try:
        with open(image_path, "rb") as image_file:
            content = image_file.read()
        
        image = vision.Image(content=content)
        response = vision_client.text_detection(image=image)
        
        if not response.text_annotations:
            return None, None
        
        text = response.text_annotations[0].description
        result = translate_client.detect_language(text)
        return text, result["language"]
    except Exception as e:
        vision_client = vision.ImageAnnotatorClient()
        translate_client = translate_v2.Client()
        raise e

@retry.Retry(predicate=retry.if_exception_type(exceptions.DeadlineExceeded))
def translate_text(text, target_language):
    global translate_client
    try:
        if not text:
            return None
        result = translate_client.translate(
            text,
            target_language=target_language
        )
        return result["translatedText"]
    except Exception as e:
        translate_client = translate_v2.Client()
        raise e

def safe_camera_operation(func):
    def wrapper(*args, **kwargs):
        global camera
        try:
            return func(*args, **kwargs)
        except Exception:
            try:
                camera.stop()
            except:
                pass
            camera = Picamera2()
            return func(*args, **kwargs)
    return wrapper

@safe_camera_operation
def capture_and_translate():
    global current_language, camera
    print("\nCapturing image...")

    try:
        camera.stop()
        config = camera.create_still_configuration()
        camera.configure(config)
        camera.start()
        time.sleep(2)

        image_path = "captured_image.jpg"
        camera.capture_file(image_path)
        camera.stop()

        os.system(f"mpg123 {AUDIO_PATHS['capture']}")

        extracted_text, detected_language = detect_text_and_language(image_path)

        if not extracted_text:
            print("No valid text found")
            os.system(f"mpg123 {AUDIO_PATHS['no_text']}")
            return False
        print(f"\nDetected Language: {detected_language}")
        print(f"Extracted Text: {extracted_text}")
        current_language = detected_language

        tts_lang_map = {
            'en': 'en-US', 'hi': 'hi-IN', 'mr': 'mr-IN',
            'eng': 'en-US', 'hin': 'hi-IN', 'mar': 'mr-IN'
        }

        original_lang = tts_lang_map.get(detected_language, 'en-US')
        text_to_speech(extracted_text, original_lang, AUDIO_PATHS['original'])

        print("\nGenerating translations...")

        # Initialize translation variables
        english_text = None
        hindi_text = None
        marathi_text = None

        if detected_language not in ['en', 'eng']:
            english_text = translate_text(extracted_text, 'en')
            if english_text:
                print(f"English Translation: {english_text}")
                text_to_speech(english_text, 'en-US', AUDIO_PATHS['english'])

        if detected_language not in ['hi', 'hin']:
            hindi_text = translate_text(extracted_text, 'hi')
            if hindi_text:
                print(f"Hindi Translation: {hindi_text}")
                text_to_speech(hindi_text, 'hi-IN', AUDIO_PATHS['hindi'])

        if detected_language not in ['mr', 'mar']:
            marathi_text = translate_text(extracted_text, 'mr')
            if marathi_text:
                print(f"Marathi Translation: {marathi_text}")
                text_to_speech(marathi_text, 'mr-IN', AUDIO_PATHS['marathi'])

        print("\nTranslations complete!")
        os.system(f"mpg123 {AUDIO_PATHS['complete']}")

        # Store captured image and translations in MySQL instead of Firestore
        store_in_mysql(image_path, extracted_text, english_text, hindi_text, marathi_text)

        return True

    except Exception as e:
        print(f"Error in capture_and_translate: {str(e)}")
        time.sleep(2)
        return capture_and_translate()

def get_language_sequence(detected_lang):
    sequences = {
        'en': ['original', 'hindi', 'marathi'],
        'eng': ['original', 'hindi', 'marathi'],
        'hi': ['original', 'english', 'marathi'],
        'hin': ['original', 'english', 'marathi'],
        'mr': ['original', 'english', 'hindi'],
        'mar': ['original', 'english', 'hindi']
    }
    return sequences.get(detected_lang, ['original', 'hindi', 'marathi'])

def handle_button_press():
    global button_press_count
    try:
        if button_press_count == 0:
            if capture_and_translate():
                button_press_count += 1
        else:
            sequence = get_language_sequence(current_language)
            if button_press_count <= len(sequence):
                audio_file = AUDIO_PATHS[sequence[button_press_count - 1]]
                os.system(f"mpg123 {audio_file}")
                button_press_count = (button_press_count + 1) % (len(sequence) + 1)
    except Exception as e:
        print(f"Error in button press handler: {str(e)}")
        time.sleep(2)
        button_press_count = 0

def main():
    print("Starting application...")
    initialize_clients()
    initialize_feedback_sounds()
    init_mysql_database()  # Initialize MySQL database
    
    while True:
        try:
            print("\nPress button to start the capture-translate-audio cycle.")
            print("Button press sequence:")
            print("1st press: Capture and process image")
            print("Following presses: Play original language followed by translations")
            
            while True:
                if GPIO.input(BUTTON_PIN) == GPIO.HIGH:
                    handle_button_press()
                    time.sleep(0.5)
        
        except KeyboardInterrupt:
            print("\nProgram stopped by user")
            GPIO.cleanup()
            sys.exit(0)
        
        except Exception as e:
            print(f"Main loop error: {str(e)}")
            time.sleep(2)
            try:
                GPIO.cleanup()
            except:
                pass
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            initialize_clients()

if __name__ == "__main__":
    main()