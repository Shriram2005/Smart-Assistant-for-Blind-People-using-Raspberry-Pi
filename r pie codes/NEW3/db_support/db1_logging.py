import subprocess
import logging
import os
import json
import time
import RPi.GPIO as GPIO
from picamera2 import Picamera2
import sys
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import vision, translate_v2, texttospeech
from google.api_core import retry, exceptions

# Configure logging
logging.basicConfig(filename='/var/log/smart_aid.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger().addHandler(logging.StreamHandler())

# Load Firebase credentials
cred = credentials.Certificate('/home/pi/FirebaseServiceAccountKey.json')
firebase_admin.initialize_app(cred)

# Initialize Firestore client
db = firestore.client()

# GPIO Setup
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
        logging.info("Initializing clients...")
        vision_client = vision.ImageAnnotatorClient()
        translate_client = translate_v2.Client()
        tts_client = texttospeech.TextToSpeechClient()
        camera = Picamera2()
    except Exception as e:
        logging.error(f"Error initializing clients: {str(e)}")
        time.sleep(5)
        initialize_clients()

@retry.Retry(predicate=retry.if_exception_type(exceptions.DeadlineExceeded))
def text_to_speech(text, language_code, output_path):
    global tts_client
    try:
        logging.info(f"Generating speech for text: {text} in language: {language_code}")
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
        logging.info(f"Speech generated and saved to {output_path}")
    except Exception as e:
        logging.error(f"Error generating speech: {str(e)}")
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
            logging.info(f"Feedback sound {path} generated")
        except Exception:
            logging.error(f"Error generating feedback sound {path}")
            time.sleep(2)
            continue

@retry.Retry(predicate=retry.if_exception_type(exceptions.DeadlineExceeded))
def detect_text_and_language(image_path):
    global vision_client, translate_client
    try:
        logging.info(f"Detecting text and language from {image_path}")
        with open(image_path, "rb") as image_file:
            content = image_file.read()
        image = vision.Image(content=content)
        response = vision_client.text_detection(image=image)
        if not response.text_annotations:
            logging.warning("No valid text found")
            return None, None
        text = response.text_annotations[0].description
        result = translate_client.detect_language(text)
        logging.info(f"Detected Language: {result['language']}, Text: {text}")
        return text, result["language"]
    except Exception as e:
        logging.error(f"Error detecting text and language: {str(e)}")
        vision_client = vision.ImageAnnotatorClient()
        translate_client = translate_v2.Client()
        raise e

@retry.Retry(predicate=retry.if_exception_type(exceptions.DeadlineExceeded))
def translate_text(text, target_language):
    global translate_client
    try:
        if not text:
            logging.warning("No text to translate")
            return None
        result = translate_client.translate(
            text,
            target_language=target_language
        )
        logging.info(f"Translated text: {result['translatedText']}")
        return result["translatedText"]
    except Exception as e:
        logging.error(f"Error translating text: {str(e)}")
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
    logging.info("Capturing image...")
    try:
        camera.stop()
        config = camera.create_still_configuration()
        camera.configure(config)
        camera.start()
        time.sleep(2)
        image_path = "captured_image.jpg"
        camera.capture_file(image_path)
        camera.stop()
        play_audio(AUDIO_PATHS['capture'])
        logging.info("Image captured and saved")

        extracted_text, detected_language = detect_text_and_language(image_path)
        if not extracted_text:
            logging.warning("No valid text found")
            play_audio(AUDIO_PATHS['no_text'])
            return False
        logging.info(f"Detected Language: {detected_language}")
        logging.info(f"Extracted Text: {extracted_text}")
        current_language = detected_language

        tts_lang_map = {
            'en': 'en-US', 'hi': 'hi-IN', 'mr': 'mr-IN',
            'eng': 'en-US', 'hin': 'hi-IN', 'mar': 'mr-IN'
        }
        original_lang = tts_lang_map.get(detected_language, 'en-US')
        text_to_speech(extracted_text, original_lang, AUDIO_PATHS['original'])
        logging.info("Original text converted to speech")

        logging.info("\nGenerating translations...")
        # Initialize translation variables
        english_text = None
        hindi_text = None
        marathi_text = None

        if detected_language not in ['en', 'eng']:
            try:
                english_text = translate_text(extracted_text, 'en')
                if english_text:
                    logging.info(f"English Translation: {english_text}")
                    text_to_speech(english_text, 'en-US', AUDIO_PATHS['english'])
            except Exception as e:
                logging.error(f"Error translating to English: {str(e)}")

        if detected_language not in ['hi', 'hin']:
            try:
                hindi_text = translate_text(extracted_text, 'hi')
                if hindi_text:
                    logging.info(f"Hindi Translation: {hindi_text}")
                    text_to_speech(hindi_text, 'hi-IN', AUDIO_PATHS['hindi'])
            except Exception as e:
                logging.error(f"Error translating to Hindi: {str(e)}")

        if detected_language not in ['mr', 'mar']:
            try:
                marathi_text = translate_text(extracted_text, 'mr')
                if marathi_text:
                    logging.info(f"Marathi Translation: {marathi_text}")
                    text_to_speech(marathi_text, 'mr-IN', AUDIO_PATHS['marathi'])
            except Exception as e:
                logging.error(f"Error translating to Marathi: {str(e)}")

        logging.info("\nTranslations complete!")
        play_audio(AUDIO_PATHS['complete'])
        # Store captured image, original text, and translations in Firestore
        store_in_firestore(image_path, extracted_text, english_text, hindi_text, marathi_text)
        return True
    except Exception as e:
        logging.error(f"Error in capture_and_translate: {str(e)}")
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
                play_audio(audio_file)
                button_press_count = (button_press_count + 1) % (len(sequence) + 1)
    except Exception as e:
        logging.error(f"Error in button press handler: {str(e)}")
        time.sleep(2)
        button_press_count = 0

def play_audio(file_path):
    logging.info(f"Playing audio file: {file_path}")
    try:
        subprocess.run(['aplay', file_path], check=True)
        logging.info("Audio played successfully")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error playing audio: {str(e)}")

def store_in_firestore(image_path, original_text, english_text, hindi_text, marathi_text):
    # Read the image file
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()
    # Encode image data to base64
    encoded_image = base64.b64encode(image_data).decode('utf-8')
    # Generate a unique document ID
    doc_ref = db.collection('captured_images').document()
    # Create a dictionary to store the data
    data = {
        'image': encoded_image,
        'original_text': original_text,
        'english_translation': english_text,
        'hindi_translation': hindi_text,
        'marathi_translation': marathi_text,
        'timestamp': firestore.SERVER_TIMESTAMP
    }
    # Write the data to Firestore
    doc_ref.set(data)
    logging.info(f"Data stored in Firestore with ID: {doc_ref.id}")

def main():
    logging.info("Starting application...")
    initialize_clients()
    initialize_feedback_sounds()
    try:
        logging.info("Press button to start the capture-translate-audio cycle.")
        logging.info("Button press sequence:")
        logging.info("1st press: Capture and process image")
        logging.info("Following presses: Play original language followed by translations")
        while True:
            if GPIO.input(BUTTON_PIN) == GPIO.HIGH:
                handle_button_press()
                time.sleep(0.5)
    except KeyboardInterrupt:
        logging.info("Program stopped by user")
        GPIO.cleanup()
        sys.exit(0)
    except Exception as e:
        logging.error(f"Main loop error: {str(e)}")
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