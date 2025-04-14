import cv2
import numpy as np
import pytesseract
from googletrans import Translator
from gtts import gTTS
import os
import time
from PIL import Image
import subprocess
from langdetect import detect
import logging
from threading import Lock
from paddleocr import PaddleOCR
import mysql.connector
import mysql.connector.pooling
import sys
import tkinter as tk

# Aiven MySQL Configuration
MYSQL_CONFIG = {
    'host': 'mysql-raspberry-pi-shrirammange.k.aivencloud.com',  # Aiven MySQL endpoint
    'user': 'avnadmin',                # Default Aiven admin username
    'password': 'AVNS_YkuryCt4s_wLBuD8xAb',       # Your Aiven password
    'database': 'defaultdb',       # Database name
    'port': 18836,                     # Your Aiven MySQL port
    'pool_name': 'mypool',
    'pool_size': 5,
    'connect_timeout': 10,
    'ssl_ca': os.path.join(os.path.expanduser('~'), 'ca.pem')  # Update path to CA certificate
}

# Create a connection pool
try:
    connection_pool = mysql.connector.pooling.MySQLConnectionPool(**MYSQL_CONFIG)
    print("Aiven database connection pool created successfully")
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
        print("Aiven MySQL database initialized successfully")
        
    except Exception as e:
        print(f"Error initializing Aiven MySQL database: {str(e)}")
        sys.exit(1)
    finally:
        if connection:
            if 'cursor' in locals():
                cursor.close()
            connection.close()

def store_in_mysql(image_path, original_text, english_text, hindi_text, marathi_text):
    """Store data in Aiven MySQL with proper connection handling"""
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
        
        print(f"Data stored in Aiven MySQL with ID: {cursor.lastrowid}")
        
    except Exception as e:
        print(f"Error storing data in Aiven MySQL: {str(e)}")
        if connection:
            connection.rollback()
    finally:
        if connection:
            if 'cursor' in locals():
                cursor.close()
            connection.close()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure Tesseract path and languages
if os.name == 'nt':  # Windows
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else:  # Linux/Mac
    pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

# Language configurations
SUPPORTED_LANGUAGES = {
    'en': {'name': 'english', 'tesseract': 'eng', 'confidence_threshold': 0.3},
    'hi': {'name': 'hindi', 'tesseract': 'hin', 'confidence_threshold': 0.25},
    'mr': {'name': 'marathi', 'tesseract': 'mar', 'confidence_threshold': 0.25}
}

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
root = None  # Tkinter root window

def initialize_system():
    """Initialize camera, translator and create feedback sounds."""
    global camera, translator
    
    try:
        # Check if required Tesseract language data is installed
        required_langs = [lang['tesseract'] for lang in SUPPORTED_LANGUAGES.values()]
        try:
            installed_langs = pytesseract.get_languages()
            
            missing_langs = [lang for lang in required_langs if lang not in installed_langs]
            if missing_langs:
                logger.error(f"Missing Tesseract language data for: {', '.join(missing_langs)}")
                if os.name == 'nt':
                    logger.error("Please install required language data from https://github.com/UB-Mannheim/tesseract/wiki")
                else:
                    logger.error("Please install required language data using:")
                    logger.error(f"sudo apt-get install tesseract-ocr-{' tesseract-ocr-'.join(missing_langs)}")
                return False
        except Exception as e:
            logger.warning(f"Could not verify Tesseract languages: {str(e)}")
        
        # Initialize webcam (instead of PiCamera)
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            logger.error("Could not open webcam")
            return False
            
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
                if os.name == 'nt':  # Windows
                    subprocess.run(['taskkill', '/F', '/IM', 'mpg123.exe'], stderr=subprocess.DEVNULL, shell=True)
                else:  # Linux/Mac
                    subprocess.run(['pkill', '-f', 'mpg123'], stderr=subprocess.DEVNULL)
                current_audio_process = None
            
            # Start new audio playback
            if os.name == 'nt':  # Windows
                current_audio_process = subprocess.Popen(['start', '', audio_path], shell=True, stderr=subprocess.DEVNULL)
            else:  # Linux/Mac
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
    
    # Initialize PaddleOCR for English
    paddle_ocr = PaddleOCR(use_angle_cls=True, lang='en')
    
    for lang_code, lang_info in SUPPORTED_LANGUAGES.items():
        tesseract_lang = lang_info['tesseract']
        confidence_threshold = lang_info['confidence_threshold']
        
        try:
            if lang_code == 'en':
                # Use PaddleOCR for English
                result = paddle_ocr.ocr(image_path, cls=True)
                if result and result[0]:
                    extracted_lines = []
                    confidence_sum = 0
                    line_count = 0
                    
                    for line in result[0]:
                        if line[1][0] and len(line[1][0]) > 0:
                            extracted_lines.append(line[1][0])
                            confidence_sum += float(line[1][1])
                            line_count += 1
                    
                    if line_count > 0:
                        text = ' '.join(extracted_lines)
                        confidence = confidence_sum / line_count
                        
                        if confidence > best_results[lang_code]['confidence'] and len(text) > 5:
                            best_results[lang_code]['text'] = text
                            best_results[lang_code]['confidence'] = confidence
            else:
                # Use Tesseract for Hindi and Marathi
                for config in ocr_configs:
                    # Add language-specific configuration
                    full_config = f"{config} -l {tesseract_lang}"
                    
                    text = pytesseract.image_to_string(
                        Image.open(image_path),
                        config=full_config
                    ).strip()
                    
                    # Calculate confidence score
                    if text:
                        # For non-Latin scripts, adjust confidence calculation
                        if lang_code in ['hi', 'mr']:
                            # Count non-space characters instead of alphanumeric
                            confidence = len([c for c in text if not c.isspace()]) / len(text)
                        else:
                            confidence = len([c for c in text if c.isalnum()]) / len(text)
                        
                        if confidence > best_results[lang_code]['confidence'] and len(text) > 5:
                            best_results[lang_code]['text'] = text
                            best_results[lang_code]['confidence'] = confidence
            
        except Exception as e:
            logger.error(f"OCR failed for {lang_info['name']}: {str(e)}")
    
    # Find the best result across all languages
    best_lang = max(best_results.items(), 
                   key=lambda x: x[1]['confidence'])
    
    if best_lang[1]['confidence'] > SUPPORTED_LANGUAGES[best_lang[0]]['confidence_threshold']:
        logger.info(f"Detected text in {SUPPORTED_LANGUAGES[best_lang[0]]['name']}")
        return best_lang[1]['text'], best_lang[0]
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
    """Capture image from webcam and perform translation with proper error handling."""
    global current_language
    logger.info("Starting capture and translate process")
    
    try:
        # Capture image from webcam
        ret, frame = camera.read()
        if not ret:
            logger.error("Failed to capture image from webcam")
            play_audio(AUDIO_PATHS['error'])
            return False
            
        image_path = "captured_image.jpg"
        cv2.imwrite(image_path, frame)
        
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
        
        # Dictionary to store translations
        translations = {
            'english': None,
            'hindi': None,
            'marathi': None
        }
        
        # Set original text in the appropriate language slot
        if detected_lang == 'en':
            translations['english'] = extracted_text
        elif detected_lang == 'hi':
            translations['hindi'] = extracted_text
        elif detected_lang == 'mr':
            translations['marathi'] = extracted_text
        
        # Translate to other supported languages
        for target_code, target_info in SUPPORTED_LANGUAGES.items():
            if target_code != detected_lang:
                translated = translate_text(extracted_text, target_code)
                if translated:
                    tts = gTTS(translated, lang=target_code)
                    tts.save(AUDIO_PATHS[target_info['name']])
                    logger.info(f"Translation to {target_info['name']} completed")
                    
                    # Store translation in the dictionary
                    translations[target_info['name']] = translated
        
        # Store all data in Aiven MySQL database
        try:
            store_in_mysql(
                image_path,
                extracted_text,
                translations['english'],
                translations['hindi'],
                translations['marathi']
            )
            logger.info("Successfully stored data in Aiven MySQL database")
        except Exception as e:
            logger.error(f"Failed to store data in database: {str(e)}")
        
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
            if os.name == 'nt':  # Windows
                subprocess.run(['taskkill', '/F', '/IM', 'mpg123.exe'], stderr=subprocess.DEVNULL, shell=True)
            else:  # Linux/Mac
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

def create_gui():
    """Create a simple GUI with a button to replace physical button."""
    global root
    
    root = tk.Tk()
    root.title("Smart Aid System")
    root.geometry("400x200")
    
    # Style the button
    style_frame = tk.Frame(root, bg="#f0f0f0")
    style_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    # Create label
    label = tk.Label(
        style_frame, 
        text="Press the button to capture image and translate text", 
        font=("Arial", 12),
        bg="#f0f0f0"
    )
    label.pack(pady=10)
    
    # Create button
    button = tk.Button(
        style_frame, 
        text="Capture/Play Audio", 
        command=handle_button_press,
        bg="#4CAF50", 
        fg="white",
        font=("Arial", 14, "bold"),
        relief=tk.RAISED,
        width=20,
        height=2
    )
    button.pack(pady=20)
    
    # Status label
    status_label = tk.Label(
        style_frame, 
        text="Status: Ready", 
        font=("Arial", 10),
        bg="#f0f0f0"
    )
    status_label.pack(pady=10)
    
    # Key binding - spacebar can also trigger the button
    root.bind("<space>", lambda event: handle_button_press())
    
    return root

def main():
    """Main program loop with proper initialization and cleanup."""
    global current_audio_process
    
    logger.info("Starting Smart Aid System")
    
    # Initialize MySQL database
    try:
        init_mysql_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        return
    
    if not initialize_system():
        logger.error("Failed to initialize system")
        return
    
    play_audio(AUDIO_PATHS['ready'])
    
    try:
        # Create and start GUI
        gui = create_gui()
        gui.mainloop()
    except KeyboardInterrupt:
        logger.info("Program stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
    finally:
        if current_audio_process:
            if os.name == 'nt':  # Windows
                subprocess.run(['taskkill', '/F', '/IM', 'mpg123.exe'], stderr=subprocess.DEVNULL, shell=True)
            else:  # Linux/Mac
                subprocess.run(['pkill', '-f', 'mpg123'], stderr=subprocess.DEVNULL)
        if camera:
            camera.release()
        logger.info("System shutdown complete")

if __name__ == "__main__":
    main()