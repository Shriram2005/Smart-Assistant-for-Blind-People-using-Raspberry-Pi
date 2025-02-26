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

# Configure Tesseract path and languages
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

# Language configurations
SUPPORTED_LANGUAGES = {
    'en': {'name': 'english', 'tesseract': 'eng', 'confidence_threshold': 0.3},
    'hi': {'name': 'hindi', 'tesseract': 'hin', 'confidence_threshold': 0.3},
    'mr': {'name': 'marathi', 'tesseract': 'mar', 'confidence_threshold': 0.3}
}

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
current_language = None
current_audio_process = None  # Add this to track current audio playback

def initialize_system():
    """Initialize camera, translator and create feedback sounds."""
    global camera, translator
    
    try:
        # Check if required Tesseract language data is installed
        required_langs = [lang['tesseract'] for lang in SUPPORTED_LANGUAGES.values()]
        installed_langs = pytesseract.get_languages()
        
        missing_langs = [lang for lang in required_langs if lang not in installed_langs]
        if missing_langs:
            logger.error(f"Missing Tesseract language data for: {', '.join(missing_langs)}")
            logger.error("Please install required language data using:")
            logger.error(f"sudo apt-get install tesseract-ocr-{' tesseract-ocr-'.join(missing_langs)}")
            return False
        
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
    global current_audio_process
    
    with audio_lock:
        try:
            # Kill any currently playing audio
            if current_audio_process and current_audio_process.poll() is None:
                subprocess.run(['pkill', '-f', 'mpg123'], stderr=subprocess.DEVNULL)
                current_audio_process = None
            
            # Start new audio playback
            current_audio_process = subprocess.Popen(['mpg123', '-q', audio_path], stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.error(f"Audio playback failed: {str(e)}")
            current_audio_process = None

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

def is_devanagari(char):
    """Check if a character is in Devanagari script."""
    return '\u0900' <= char <= '\u097F'

def is_latin(char):
    """Check if a character is in Latin script."""
    return (
        ('a' <= char.lower() <= 'z') or 
        char in ".,!?-'\"() " or 
        char.isdigit()
    )

def calculate_script_ratio(text, script_checker):
    """Calculate the ratio of characters matching a specific script."""
    if not text:
        return 0
    total_chars = len([c for c in text if not c.isspace()])
    if total_chars == 0:
        return 0
    script_chars = sum(1 for c in text if not c.isspace() and script_checker(c))
    return script_chars / total_chars

def extract_text(image_path):
    """Extract text using multiple OCR configurations and languages."""
    ocr_configs = [
        '--oem 3 --psm 3',  # Default
        '--oem 3 --psm 1',  # Automatic page segmentation
        '--oem 3 --psm 4',  # Assume single column of text
        '--oem 3 --psm 6'   # Assume uniform block of text
    ]
    
    best_results = {lang_code: {'text': '', 'confidence': 0} 
                   for lang_code in SUPPORTED_LANGUAGES.keys()}
    
    for lang_code, lang_info in SUPPORTED_LANGUAGES.items():
        tesseract_lang = lang_info['tesseract']
        
        for config in ocr_configs:
            try:
                # Add language-specific configuration
                full_config = f"{config} -l {tesseract_lang}"
                
                text = pytesseract.image_to_string(
                    Image.open(image_path),
                    config=full_config
                ).strip()
                
                # Skip empty or very short texts
                if not text or len(text) < 5:
                    continue
                
                # Calculate script-based confidence
                if lang_code == 'en':
                    # For English text
                    latin_ratio = calculate_script_ratio(text, is_latin)
                    devanagari_ratio = calculate_script_ratio(text, is_devanagari)
                    
                    # If significant Devanagari presence, reduce English confidence
                    if devanagari_ratio > 0.15:
                        confidence = 0
                    else:
                        confidence = latin_ratio
                        
                        # Additional checks for English
                        words = text.split()
                        if words:
                            # Check word characteristics
                            valid_words = sum(1 for word in words if 2 <= len(word) <= 15)
                            word_confidence = valid_words / len(words)
                            confidence = (confidence + word_confidence) / 2
                
                else:  # Hindi or Marathi
                    # Calculate Devanagari ratio
                    devanagari_ratio = calculate_script_ratio(text, is_devanagari)
                    latin_ratio = calculate_script_ratio(text, is_latin)
                    
                    # If more Latin than Devanagari, reduce confidence
                    if latin_ratio > devanagari_ratio:
                        confidence = 0
                    else:
                        confidence = devanagari_ratio
                
                if confidence > best_results[lang_code]['confidence']:
                    best_results[lang_code]['text'] = text
                    best_results[lang_code]['confidence'] = confidence
                    logger.debug(f"New best confidence for {lang_code}: {confidence}")
                
            except Exception as e:
                logger.error(f"OCR failed for {lang_info['name']} with config {config}: {str(e)}")
    
    # Log confidence scores for debugging
    for lang_code, result in best_results.items():
        logger.info(f"Final confidence for {lang_code}: {result['confidence']}")
    
    # Find the best result across all languages
    best_lang = max(best_results.items(), 
                   key=lambda x: x[1]['confidence'])
    
    # Only accept a language if it has significantly higher confidence
    highest_confidence = best_lang[1]['confidence']
    threshold = SUPPORTED_LANGUAGES[best_lang[0]]['confidence_threshold']
    
    if highest_confidence >= threshold:
        # Check if there's a clear winner
        other_confidences = [res['confidence'] for lang, res in best_results.items() if lang != best_lang[0]]
        max_other_confidence = max(other_confidences) if other_confidences else 0
        
        # Ensure the best confidence is significantly higher than others
        if highest_confidence > max_other_confidence + 0.1:
            logger.info(f"Detected language: {SUPPORTED_LANGUAGES[best_lang[0]]['name']} "
                       f"with confidence {highest_confidence}")
            return best_lang[1]['text'], best_lang[0]
    
    # If no clear winner, try to make a best guess based on script presence
    text = best_lang[1]['text']
    if text:
        devanagari_ratio = calculate_script_ratio(text, is_devanagari)
        latin_ratio = calculate_script_ratio(text, is_latin)
        
        if devanagari_ratio > latin_ratio and devanagari_ratio > 0.3:
            # If mostly Devanagari, use the higher confidence between Hindi and Marathi
            hi_conf = best_results['hi']['confidence']
            mr_conf = best_results['mr']['confidence']
            detected_lang = 'hi' if hi_conf > mr_conf else 'mr'
            return best_results[detected_lang]['text'], detected_lang
        elif latin_ratio > devanagari_ratio and latin_ratio > 0.3:
            return best_results['en']['text'], 'en'
    
    return '', None

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

def get_language_sequence(detected_lang):
    """Get the appropriate sequence of audio playback based on detected language."""
    sequences = {
        'en': ['original', 'hindi', 'marathi'],
        'hi': ['original', 'english', 'marathi'],
        'mr': ['original', 'english', 'hindi']
    }
    return sequences.get(detected_lang, ['original', 'english', 'hindi', 'marathi'])

def capture_and_translate():
    """Capture image and perform translation with proper error handling."""
    global current_language
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
        extracted_text, detected_lang = extract_text(processed_path)
        
        if not extracted_text:
            logger.warning("No text detected in image")
            play_audio(AUDIO_PATHS['no_text'])
            return False
        
        logger.info(f"Extracted text: {extracted_text}")
        logger.info(f"Detected language: {SUPPORTED_LANGUAGES[detected_lang]['name']}")
        
        # Store the detected language
        current_language = detected_lang
        
        # Generate audio for original text
        tts = gTTS(extracted_text, lang=detected_lang)
        tts.save(AUDIO_PATHS['original'])
        
        # Translate to other supported languages
        for target_code, target_info in SUPPORTED_LANGUAGES.items():
            if target_code != detected_lang:
                translated = translate_text(extracted_text, target_code)
                if translated:
                    tts = gTTS(translated, lang=target_code)
                    tts.save(AUDIO_PATHS[target_info['name']])
                    logger.info(f"Translation to {target_info['name']} completed")
        
        play_audio(AUDIO_PATHS['complete'])
        return True
    
    except Exception as e:
        logger.error(f"Capture and translate failed: {str(e)}")
        play_audio(AUDIO_PATHS['error'])
        return False

def handle_button_press():
    """Handle button press events with proper state management."""
    global button_press_count, current_audio_process
    
    try:
        # Stop any currently playing audio immediately
        if current_audio_process and current_audio_process.poll() is None:
            subprocess.run(['pkill', '-f', 'mpg123'], stderr=subprocess.DEVNULL)
            current_audio_process = None
        
        if button_press_count == 0:
            success = capture_and_translate()
            if success:
                button_press_count = 1
        else:
            # Get the appropriate sequence based on detected language
            sequence = get_language_sequence(current_language)
            
            if button_press_count <= len(sequence):
                audio_file = AUDIO_PATHS[sequence[button_press_count - 1]]
                if os.path.exists(audio_file):
                    play_audio(audio_file)
                
                button_press_count = (button_press_count + 1) % (len(sequence) + 1)
    
    except Exception as e:
        logger.error(f"Button press handling failed: {str(e)}")
        play_audio(AUDIO_PATHS['error'])
        button_press_count = 0

def main():
    """Main program loop with proper initialization and cleanup."""
    global current_audio_process
    
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
        if current_audio_process:
            subprocess.run(['pkill', '-f', 'mpg123'], stderr=subprocess.DEVNULL)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
    finally:
        if current_audio_process:
            subprocess.run(['pkill', '-f', 'mpg123'], stderr=subprocess.DEVNULL)
        if camera:
            camera.stop()
        GPIO.cleanup()
        logger.info("System shutdown complete")

if __name__ == "__main__":
    main()