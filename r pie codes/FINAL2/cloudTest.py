import os
import time
import sys
import RPi.GPIO as GPIO
from picamera2 import Picamera2
from google.cloud import vision, translate_v2, texttospeech
from google.api_core import retry, exceptions

# Configuration
BUTTON_PIN = 18
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/pi/gcloud.json"

# Global variables
button_press_count = 0
current_language = None
vision_client = vision.ImageAnnotatorClient()
translate_client = translate_v2.Client()
tts_client = texttospeech.TextToSpeechClient()
camera = Picamera2()

AUDIO_PATHS = {
    'original': "original_audio.mp3",
    'english': "english_audio.mp3",
    'hindi': "hindi_audio.mp3",
    'marathi': "marathi_audio.mp3",
    'capture': "capture_sound.mp3",
    'no_text': "no_text_found.mp3",
    'complete': "translation_complete.mp3"
}

LANGUAGE_SEQUENCES = {
    'en': ['original', 'hindi', 'marathi'],
    'hi': ['original', 'english', 'marathi'],
    'mr': ['original', 'english', 'hindi']
}

@retry.Retry(predicate=retry.if_exception_type(exceptions.DeadlineExceeded))
def text_to_speech(text, language_code, output_path):
    try:
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=f"{language_code}-Standard-A"
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        response = tts_client.synthesize_speech(
            input=texttospeech.SynthesisInput(text=text),
            voice=voice,
            audio_config=audio_config
        )
        with open(output_path, "wb") as out:
            out.write(response.audio_content)
    except Exception as e:
        global tts_client
        tts_client = texttospeech.TextToSpeechClient()
        raise e

@retry.Retry(predicate=retry.if_exception_type(exceptions.DeadlineExceeded))
def detect_and_translate(image_path):
    try:
        with open(image_path, "rb") as image_file:
            content = image_file.read()
        
        # Detect text and language
        image = vision.Image(content=content)
        response = vision_client.text_detection(image=image)
        
        if not response.text_annotations:
            return None, None
        
        text = response.text_annotations[0].description
        detected_lang = translate_client.detect_language(text)["language"]
        
        # Generate translations
        translations = {'original': text}
        if detected_lang not in ['en', 'eng']:
            translations['english'] = translate_client.translate(text, target_language='en')["translatedText"]
        if detected_lang not in ['hi', 'hin']:
            translations['hindi'] = translate_client.translate(text, target_language='hi')["translatedText"]
        if detected_lang not in ['mr', 'mar']:
            translations['marathi'] = translate_client.translate(text, target_language='mr')["translatedText"]
        
        return detected_lang, translations
        
    except Exception as e:
        global vision_client, translate_client
        vision_client = vision.ImageAnnotatorClient()
        translate_client = translate_v2.Client()
        raise e

def capture_image():
    global camera
    try:
        camera.stop()
        config = camera.create_still_configuration()
        camera.configure(config)
        camera.start()
        time.sleep(2)
        camera.capture_file("captured_image.jpg")
        camera.stop()
        return True
    except Exception:
        camera = Picamera2()
        return False

def handle_button_press():
    global button_press_count, current_language
    
    try:
        if button_press_count == 0:
            # First press: Capture and process
            os.system(f"mpg123 {AUDIO_PATHS['capture']}")
            
            if not capture_image():
                return
                
            detected_lang, translations = detect_and_translate("captured_image.jpg")
            if not translations:
                os.system(f"mpg123 {AUDIO_PATHS['no_text']}")
                return
                
            current_language = detected_lang
            
            # Generate audio files
            lang_codes = {'original': f"{detected_lang}-IN", 'english': 'en-US', 
                         'hindi': 'hi-IN', 'marathi': 'mr-IN'}
            
            for lang, text in translations.items():
                if text:
                    text_to_speech(text, lang_codes[lang], AUDIO_PATHS[lang])
            
            os.system(f"mpg123 {AUDIO_PATHS['complete']}")
            button_press_count += 1
            
        else:
            # Subsequent presses: Play audio
            sequence = LANGUAGE_SEQUENCES.get(current_language, ['original', 'hindi', 'marathi'])
            if button_press_count <= len(sequence):
                os.system(f"mpg123 {AUDIO_PATHS[sequence[button_press_count - 1]]}")
                button_press_count = (button_press_count + 1) % (len(sequence) + 1)
                
    except Exception as e:
        print(f"Error in button press handler: {str(e)}")
        time.sleep(2)
        button_press_count = 0

def main():
    # GPIO Setup
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    
    # Initialize feedback sounds
    for message, path in [("Image captured", 'capture'), 
                         ("No text found", 'no_text'),
                         ("Translation complete", 'complete')]:
        text_to_speech(message, "en-US", AUDIO_PATHS[path])
    
    print("Starting application... Press button to begin.")
    
    while True:
        try:
            if GPIO.input(BUTTON_PIN) == GPIO.HIGH:
                handle_button_press()
                time.sleep(0.5)
        except KeyboardInterrupt:
            GPIO.cleanup()
            sys.exit(0)
        except Exception as e:
            print(f"Main loop error: {str(e)}")
            time.sleep(2)
            GPIO.cleanup()
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

if __name__ == "__main__":
    main()