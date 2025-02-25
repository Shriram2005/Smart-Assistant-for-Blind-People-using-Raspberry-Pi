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
import subprocess
from langdetect import detect
import logging
from threading import Lock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

# GPIO Configuration
BUTTON_PIN = 18
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Audio file paths
AUDIO_PATHS = {
    'original': "original_audio.mp3",
    'english': "english_audio.mp3",
    'hindi': "hindi_audio.mp3",
    'marathi': "marathi_audio.mp3",
    'capture': "capture_sound.mp3",
    'no_text': "no_text_found.mp3",
    'complete': "translation_complete.mp3",
    'ready': "ready_sound.mp3",
    'error': "error_sound.mp3"
}

# Global variables
button_press_count = 0
camera = None
translator = None
audio_lock = Lock()

def initialize_system():
    """Initialize camera, translator and create feedback sounds."""
    global camera, translator
    
    try:
        camera = Picamera2()
        translator = Translator()
        
        # Initialize audio feedback files
        feedback_messages = {
            'capture': "Image captured",
            'no_text': "No text found",
            'complete': "Translation complete",
            'ready': "System ready",
            'error': "An error occurred"
        }
        
        for key, message in feedback_messages.items():
            if not os.path.exists(AUDIO_PATHS[key]):
                tts = gTTS(message, lang="en")
                tts.save(AUDIO_PATHS[key])
        
        logger.info("System initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Initialization error: {str(e)}")
        return False

def play_audio(audio_path):
    """Play audio with proper locking and error handling."""
    with audio_lock:
        try:
            # Kill any currently playing audio
            subprocess.run(['pkill', '-f', 'mpg123'], stderr=subprocess.DEVNULL)
            # Start new audio playback
            subprocess.run(['mpg123', '-q', audio_path], stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.error(f"Audio playback failed: {str(e)}")

def enhance_image(image):
    """Apply advanced image enhancement techniques."""
    try:
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply bilateral filter for noise reduction while preserving edges
        denoised = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Apply morphological operations
        kernel = np.ones((1, 1), np.uint8)
        morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return morph
    except Exception as e:
        logger.error(f"Image enhancement failed: {str(e)}")
        return gray

def preprocess_image(image_path):
    """Preprocess image with multiple enhancement techniques."""
    try:
        # Read image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError("Failed to read image")
        
        # Basic enhancement
        enhanced = enhance_image(image)
        
        # Save preprocessed image
        preprocessed_path = "preprocessed_image.jpg"
        cv2.imwrite(preprocessed_path, enhanced)
        
        return preprocessed_path
    except Exception as e:
        logger.error(f"Preprocessing failed: {str(e)}")
        return image_path

def extract_text(image_path):
    """Extract text using multiple OCR configurations."""
    ocr_configs = [
        '--oem 3 --psm 3',  # Default
        '--oem 3 --psm 1',  # Automatic page segmentation
        '--oem 3 --psm 4',  # Assume single column of text
        '--oem 3 --psm 6'   # Assume uniform block of text
    ]
    
    best_text = ''
    max_confidence = 0
    
    for config in ocr_configs:
        try:
            text = pytesseract.image_to_string(
                Image.open(image_path),
                config=config
            ).strip()
            
            # Calculate confidence score
            confidence = len([c for c in text if c.isalnum()]) / max(len(text), 1)
            
            if confidence > max_confidence and len(text) > 10:
                best_text = text
                max_confidence = confidence
        except Exception as e:
            logger.error(f"OCR failed with config {config}: {str(e)}")
    
    return best_text if max_confidence > 0.3 else ''

def translate_text(text, target_lang):
    """Translate text with retry mechanism."""
    max_retries = 3
    delay = 1
    
    for attempt in range(max_retries):
        try:
            translation = translator.translate(text, dest=target_lang)
            return translation.text
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Translation failed after {max_retries} attempts: {str(e)}")
                return None
            time.sleep(delay)
            delay *= 2
    
    return None

def capture_and_translate():
    """Capture image and perform translation with proper error handling."""
    logger.info("Starting capture and translate process")
    
    try:
        # Configure and capture image
        camera.stop()
        config = camera.create_still_configuration(main={"size": (2592, 1944)})
        camera.configure(config)
        camera.start()
        time.sleep(2)
        
        image_path = "captured_image.jpg"
        camera.capture_file(image_path)
        camera.stop()
        
        play_audio(AUDIO_PATHS['capture'])
        
        # Process image and extract text
        processed_path = preprocess_image(image_path)
        extracted_text = extract_text(processed_path)
        
        if not extracted_text:
            logger.warning("No text detected in image")
            play_audio(AUDIO_PATHS['no_text'])
            return False
        
        logger.info(f"Extracted text: {extracted_text}")
        
        # Detect language and translate
        try:
            source_lang = detect(extracted_text)
        except:
            source_lang = 'en'
        
        # Generate audio for original text
        tts = gTTS(extracted_text, lang=source_lang)
        tts.save(AUDIO_PATHS['original'])
        
        # Translate to target languages
        translations = {
            'english': ('en', AUDIO_PATHS['english']),
            'hindi': ('hi', AUDIO_PATHS['hindi']),
            'marathi': ('mr', AUDIO_PATHS['marathi'])
        }
        
        for lang, (code, path) in translations.items():
            if code != source_lang:
                translated = translate_text(extracted_text, code)
                if translated:
                    tts = gTTS(translated, lang=code)
                    tts.save(path)
                    logger.info(f"Translation to {lang} completed")
        
        play_audio(AUDIO_PATHS['complete'])
        return True
    
    except Exception as e:
        logger.error(f"Capture and translate failed: {str(e)}")
        play_audio(AUDIO_PATHS['error'])
        return False

def handle_button_press():
    """Handle button press events with proper state management."""
    global button_press_count
    
    try:
        if button_press_count == 0:
            success = capture_and_translate()
            if success:
                button_press_count = 1
        else:
            audio_files = [
                AUDIO_PATHS['original'],
                AUDIO_PATHS['english'],
                AUDIO_PATHS['hindi'],
                AUDIO_PATHS['marathi']
            ]
            
            if os.path.exists(audio_files[button_press_count - 1]):
                play_audio(audio_files[button_press_count - 1])
            
            button_press_count = (button_press_count + 1) % 5
    
    except Exception as e:
        logger.error(f"Button press handling failed: {str(e)}")
        play_audio(AUDIO_PATHS['error'])
        button_press_count = 0

def main():
    """Main program loop with proper initialization and cleanup."""
    logger.info("Starting Smart Aid System")
    
    if not initialize_system():
        logger.error("Failed to initialize system")
        return
    
    play_audio(AUDIO_PATHS['ready'])
    
    try:
        while True:
            if GPIO.input(BUTTON_PIN) == GPIO.HIGH:
                handle_button_press()
                time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("Program stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
    finally:
        if camera:
            camera.stop()
        GPIO.cleanup()
        logger.info("System shutdown complete")

if __name__ == "__main__":
    main()