import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/pi/gcloud.json"
import cv2
import numpy as np
from google.cloud import vision
from google.cloud import translate_v2
from google.cloud import texttospeech
import os
import RPi.GPIO as GPIO
import time
from picamera2 import Picamera2
from PIL import Image

# GPIO Setup
BUTTON_PIN = 18
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

AUDIO_PATHS = {
    'original': "original_audio.mp3",
    'translated_1': "translated_audio_1.mp3",  # Hindi
    'translated_2': "translated_audio_2.mp3",  # Marathi
    'capture': "capture_sound.mp3",
    'no_text': "no_text_found.mp3",
    'complete': "translation_complete.mp3"
}

button_press_count = 0
camera = Picamera2()

# Initialize Cloud clients
vision_client = vision.ImageAnnotatorClient()
translate_client = translate_v2.Client()
tts_client = texttospeech.TextToSpeechClient()

def text_to_speech(text, language_code, output_path):
    # Configure the voice request
    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=f"{language_code}-Standard-A"  # Using standard (cheapest) voice
    )
    
    # Configure audio output
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.0
    )
    
    # Set the text input
    synthesis_input = texttospeech.SynthesisInput(text=text)
    
    # Perform the text-to-speech request
    response = tts_client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )
    
    # Write the response to the output file
    with open(output_path, "wb") as out:
        out.write(response.audio_content)

# Initialize feedback sounds
for message, path in [
    ("Image captured", 'capture'),
    ("No text found", 'no_text'),
    ("Translation complete", 'complete')
]:
    text_to_speech(message, "en-US", AUDIO_PATHS[path])

def detect_text_and_language(image_path):
    with open(image_path, "rb") as image_file:
        content = image_file.read()
    
    image = vision.Image(content=content)
    response = vision_client.text_detection(image=image)
    
    if not response.text_annotations:
        return None, None
    
    text = response.text_annotations[0].description
    
    # Detect language
    result = translate_client.detect_language(text)
    language = result["language"]
    
    return text, language

def translate_text(text, target_language):
    if not text:
        return None
        
    result = translate_client.translate(
        text,
        target_language=target_language
    )
    return result["translatedText"]

def capture_and_translate():
    print("Capturing image...")
    
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

    print(f"Extracted Text ({detected_language}): {extracted_text}")
    
    # Map detected language to TTS language code
    tts_lang_map = {
        'en': 'en-US',
        'hi': 'hi-IN',
        'mr': 'mr-IN',
        'eng': 'en-US',
        'hin': 'hi-IN',
        'mar': 'mr-IN'
    }
    tts_lang = tts_lang_map.get(detected_language, 'en-US')
    
    # Save original audio
    text_to_speech(extracted_text, tts_lang, AUDIO_PATHS['original'])
    
    # Translate to Hindi
    if detected_language != 'hi':
        hindi_text = translate_text(extracted_text, 'hi')
        if hindi_text:
            print(f"Hindi Translation: {hindi_text}")
            text_to_speech(hindi_text, 'hi-IN', AUDIO_PATHS['translated_1'])
    
    # Translate to Marathi
    if detected_language != 'mr':
        marathi_text = translate_text(extracted_text, 'mr')
        if marathi_text:
            print(f"Marathi Translation: {marathi_text}")
            text_to_speech(marathi_text, 'mr-IN', AUDIO_PATHS['translated_2'])
        
    os.system(f"mpg123 {AUDIO_PATHS['complete']}")
    return True

def handle_button_press():
    global button_press_count
    
    actions = {
        0: capture_and_translate,
        1: lambda: os.system(f"mpg123 {AUDIO_PATHS['original']}"),
        2: lambda: os.system(f"mpg123 {AUDIO_PATHS['translated_1']}"),  # Hindi
        3: lambda: os.system(f"mpg123 {AUDIO_PATHS['translated_2']}")   # Marathi
    }
    
    action = actions.get(button_press_count, lambda: None)
    success = action()
    
    if button_press_count == 0 and success:
        button_press_count += 1
    elif button_press_count > 0:
        button_press_count = (button_press_count + 1) % 4  # Changed to cycle through 4 states

def main():
    print("Press button to start the capture-translate-audio cycle.")
    print("Button press sequence:")
    print("1st press: Capture and process image")
    print("2nd press: Play original text")
    print("3rd press: Play Hindi translation")
    print("4th press: Play Marathi translation")
    try:
        while True:
            if GPIO.input(BUTTON_PIN) == GPIO.HIGH:
                handle_button_press()
                time.sleep(0.5)
    except KeyboardInterrupt:
        print("Program stopped by user.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()