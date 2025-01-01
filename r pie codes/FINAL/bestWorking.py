import cv2
import numpy as np
import pytesseract
from googletrans import Translator
from gtts import gTTS
import os
import RPi.GPIO as GPIO
import time
from picamera2 import Picamera2
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

BUTTON_PIN = 18
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

AUDIO_PATHS = {
    'original': "original_audio.mp3",
    'translated_1': "translated_audio_1.mp3",
    'translated_2': "translated_audio_2.mp3",
    'capture': "capture_sound.mp3",
    'no_text': "no_text_found.mp3",
    'complete': "translation_complete.mp3"
}

button_press_count = 0
camera = Picamera2()

# Initialize audio feedback files
for message, path in [
    ("Image captured", 'capture'),
    ("No text found", 'no_text'),
    ("Translation complete", 'complete')
]:
    gTTS(message, lang="en").save(AUDIO_PATHS[path])

def preprocess_image(image_path):
    """Enhanced image preprocessing for better OCR accuracy."""
    image = cv2.imread(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray)
    thresh = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 11, 2
    )
    kernel = np.ones((1, 1), np.uint8)
    dilated = cv2.dilate(thresh, kernel, iterations=1)
    preprocessed_path = "preprocessed_image.jpg"
    cv2.imwrite(preprocessed_path, dilated)
    return preprocessed_path

def validate_text(text):
    """Validate extracted text quality."""
    if not text or len(text.strip()) < 3:
        return False
    special_char_ratio = len([c for c in text if not c.isalnum()])/len(text)
    if special_char_ratio > 0.5:
        return False
    return True

def capture_and_translate(target_lang1='hi', target_lang2='mr'):
    print("Capturing image...")
    
    # Fixed camera configuration
    camera.stop()
    config = camera.create_still_configuration()
    camera.configure(config)
    camera.start()
    time.sleep(2)
    
    image_path = "captured_image.jpg"
    camera.capture_file(image_path)
    camera.stop()
    
    os.system(f"mpg123 {AUDIO_PATHS['capture']}")
    
    processed_image = preprocess_image(image_path)
    
    ocr_configs = [
        '--oem 3 --psm 3',
        '--oem 3 --psm 1',
        '--oem 3 --psm 4'
    ]
    
    extracted_text = ''
    for config in ocr_configs:
        text = pytesseract.image_to_string(
            Image.open(processed_image), 
            config=config
        ).strip()
        
        if validate_text(text):
            extracted_text = text
            break
    
    if not extracted_text:
        print("No valid text found")
        os.system(f"mpg123 {AUDIO_PATHS['no_text']}")
        return False

    extracted_text = ' '.join(
        word for word in extracted_text.split() 
        if len(word) > 1
    )
    
    print(f"Extracted Text: {extracted_text}")
    
    tts_original = gTTS(extracted_text, lang='en')
    tts_original.save(AUDIO_PATHS['original'])
    
    translator = Translator()
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            translated_text = translator.translate(
                extracted_text, 
                dest=target_lang1
            ).text
            
            print(f"Translated Text ({target_lang1}): {translated_text}")
            tts_translated = gTTS(translated_text, lang=target_lang1)
            tts_translated.save(AUDIO_PATHS['translated_1'])
            
            os.system(f"mpg123 {AUDIO_PATHS['complete']}")
            return True
            
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Translation failed after {max_retries} attempts: {e}")
                return False
            time.sleep(1)

def handle_button_press():
    global button_press_count
    
    actions = {
        0: lambda: capture_and_translate(target_lang1='hi', target_lang2='mr'),
        1: lambda: os.system(f"mpg123 {AUDIO_PATHS['original']}"),
        2: lambda: os.system(f"mpg123 {AUDIO_PATHS['translated_1']}")
    }
    
    action = actions.get(button_press_count, lambda: None)
    success = action()
    
    if button_press_count == 0 and success:
        button_press_count += 1
    elif button_press_count > 0:
        button_press_count = (button_press_count + 1) % 3

def main():
    print("Press button to start the capture-translate-audio cycle.")
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