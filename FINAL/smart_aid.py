import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/pi/gcloud.json"
from google.cloud import vision, translate_v2, texttospeech
from google.api_core import retry, exceptions
import os
import RPi.GPIO as GPIO
import time
from picamera2 import Picamera2
import sys
from pydub import AudioSegment
from pydub.playback import play
import pygame
import subprocess

os.environ['SDL_AUDIODRIVER'] = 'alsa'
os.environ['AUDIODEV'] = 'hw:0,0'

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
    'complete': "translation_complete.mp3",
    'ready': "ready_sound.mp3"
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
        ("Translation complete", 'complete'),
        ("Ready to capture image", 'ready')
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

def initialize_audio():
    # No initialization needed for mpg123
    pass

def play_audio(audio_path):
    try:
        subprocess.run(['mpg123', '-q', audio_path], check=True, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Audio playback failed: {str(e)}")
        time.sleep(1)

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
        
        play_audio(AUDIO_PATHS['capture'])
        
        extracted_text, detected_language = detect_text_and_language(image_path)
        
        if not extracted_text:
            print("No valid text found")
            play_audio(AUDIO_PATHS['no_text'])
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
        play_audio(AUDIO_PATHS['complete'])
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
                play_audio(audio_file)
                button_press_count = (button_press_count + 1) % (len(sequence) + 1)
    except Exception as e:
        print(f"Error in button press handler: {str(e)}")
        time.sleep(2)
        button_press_count = 0

def main():
    print("Starting application...")
    initialize_clients()
    initialize_audio()
    initialize_feedback_sounds()
    
    # Play ready sound when program starts
    play_audio(AUDIO_PATHS['ready'])
    
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