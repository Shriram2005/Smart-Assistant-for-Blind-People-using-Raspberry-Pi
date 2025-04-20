import datetime
import os
import re
import threading
import time
import webbrowser
import json
import tempfile
import subprocess
from collections import defaultdict
import logging
from threading import Lock

import nltk
import numpy as np
import pygame
import requests
import speech_recognition as sr
from bs4 import BeautifulSoup
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import mysql.connector
from mysql.connector import pooling
import wikipedia
from gtts import gTTS

# OCR and image processing imports
import cv2
from picamera2 import Picamera2
from PIL import Image
import pytesseract
from googletrans import Translator
from langdetect import detect

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Download necessary NLTK data
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    print("Downloading required NLTK resources...")
    nltk.download('punkt')
    nltk.download('stopwords')

# Configure Tesseract path and languages
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

# Language configurations
SUPPORTED_LANGUAGES = {
    'en': {'name': 'english', 'tesseract': 'eng', 'confidence_threshold': 0.3},
    'hi': {'name': 'hindi', 'tesseract': 'hin', 'confidence_threshold': 0.25},
    'mr': {'name': 'marathi', 'tesseract': 'mar', 'confidence_threshold': 0.25}
}

# Aiven MySQL Configuration
MYSQL_CONFIG = {
    'host': 'mysql-raspberry-pi-shrirammange.k.aivencloud.com',  # Aiven MySQL endpoint
    'user': 'avnadmin',                # Default Aiven admin username
    'password': 'AVNS_YkuryCt4s_wLBuD8xAb',       # Your Aiven password
    'database': 'defaultdb',       # Database name
    'port': 18836,                     # Your Aiven MySQL port
    'ssl_ca': 'FINAL/Online Final/ca.pem',        # Path to Aiven CA certificate
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

class SmartAssistant:
    def __init__(self, name="Assistant", voice_index=0):
        self.name = name
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Initialize speech settings
        self.speech_rate = "normal"  # Normal speech rate
        self.temp_dir = tempfile.gettempdir()
        
        # Initialize speech recognition settings
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            
        # Knowledge base for common questions
        self.knowledge_base = self.load_knowledge_base()
        
        # Load science knowledge data
        self.science_knowledge = self.load_science_knowledge()
        
        # Debug mode setting
        self.debug_mode = False
        
        # Initialize database connection pool
        try:
            # Add a fixed pool_name to the connection parameters
            connection_config = MYSQL_CONFIG.copy()
            connection_config['pool_name'] = 'mypool'  # Add a short, fixed pool name
            connection_config['pool_size'] = 5  # Optional: set a specific pool size
            
            self.connection_pool = mysql.connector.pooling.MySQLConnectionPool(**connection_config)
            if self.debug_mode:
                print("Database connection pool created successfully")
        except Exception as e:
            self.connection_pool = None
            print(f"Error creating database connection pool: {e}")
        
        # Query categorization - extended with OCR categories
        self.categories = {
            'time': ['time', 'clock', 'hour'],
            'date': ['date', 'day', 'month', 'year', 'today'],
            'weather': ['weather', 'temperature', 'forecast', 'rain', 'sunny'],
            'wikipedia': ['who is', 'what is', 'tell me about', 'wikipedia', 'define'],
            'news': ['news', 'latest news', 'headlines', 'current events'],
            'general': ['how to', 'why do', 'how does', 'explain'],
            'calculation': ['calculate', 'compute', 'math', 'solve', 'plus', 'minus', 'times', 'divided by'],
            'web_search': ['search for', 'google', 'find', 'look up'],
            'greeting': ['hello', 'hi', 'hey', 'greetings'],
            'goodbye': ['goodbye', 'bye', 'see you', 'exit', 'quit', 'stop'],
            'about': ['who are you', 'what can you do', 'your name', 'about you'],
            'read_text': ['read the last text', 'last captured text', 'read captured text', 'what was the last text', 'read the last text', 'repeat the last text'],
            'science': ['periodic table', 'newton', 'physics', 'chemistry', 'biology', 'astronomy', 'earth science', 
                      'human body', 'technology', 'innovation', 'atoms', 'molecules', 'cells', 'solar system',
                      'rock cycle', 'respiratory', 'circulatory', 'digestive', 'immune', 'nervous',
                      'electricity', 'magnetism', 'renewable energy', 'nuclear energy', 'space exploration'],
            'math': ['mathematics', 'math', 'pi', 'fibonacci', 'pythagoras', 'quadratic', 'calculus', 'trigonometry',
                   'logarithm', "euler's", 'statistics', 'probability', 'square root', 'cube root', 
                   'table of', 'multiplication table', 'square number', 'cube number', 'fraction', 
                   'addition', 'subtraction', 'multiplication', 'division', 'modulus', 'percentage', 'average',
                   'conversion', 'unit convert', 'meters to', 'kilometers to', 'grams to', 'kilograms to'],
            'history': ['history', 'historical', 'ancient', 'century', 'war', 'revolution', 'empire', 
                      'civilization', 'middle ages', 'medieval', 'renaissance', 'world war', 
                      'civil war', 'cold war', 'prehistory', 'dynasty', 'monarchy', 'king', 'queen',
                      'president', 'battle', 'treaty', 'crusades', 'romans', 'greeks', 'egyptians',
                      'mesopotamia', 'ottoman', 'mongol', 'persian', 'byzantine', 'colonial', 'napoleon'],
            'geography': ['geography', 'continent', 'ocean', 'mountain', 'river', 'desert', 'forest', 
                        'rainforest', 'reef', 'canyon', 'valley', 'plateau', 'island', 'peninsula', 
                        'capital city', 'country', 'state', 'city', 'population', 'map', 'atlas', 
                        'border', 'territory', 'climate', 'landform', 'landscape', 'region', 'hemisphere',
                        'equator', 'tropics', 'arctic', 'antarctic', 'latitude', 'longitude', 'india'],
            # New OCR-related categories
            'capture': ['capture text', 'take picture', 'read this', 'scan text', 'extract text', 'ocr', 'take a photo', 'capture image'],
            'translate': ['translate text', 'translate to', 'translate in', 'convert to', 'say in'],
            'play_original': ['play original', 'original language', 'source language'],
            'play_english': ['play english', 'english translation', 'translate english', 'read in english'],
            'play_hindi': ['play hindi', 'hindi translation', 'translate hindi', 'read in hindi'],
            'play_marathi': ['play marathi', 'marathi translation', 'translate marathi', 'read in marathi'],
            # Stop commands
            'stop': ['stop', 'interrupt', 'be quiet', 'shut up', 'silence', 'pause', 'hold on']
        }
        
        # Animation and sounds for feedback
        pygame.mixer.init()
        self.listening_sound = None
        try:
            self.listening_sound = pygame.mixer.Sound('sounds/listening.wav')
        except:
            print("Listening sound file not found")
            
        # OCR and image processing components
        self.camera = None
        self.translator = None
        self.audio_lock = Lock()
        self.current_language = None
        self.current_audio_process = None
        self.last_captured_text = ""
        self.last_translated_text = {}
        
        # Flag to track if the assistant should stop speaking
        self.stop_speaking = False
        
        # Create a stop sound
        self.stop_sound_file = os.path.join(self.temp_dir, "stop_sound.mp3")
        stop_tts = gTTS(text="Stopped", lang='en', slow=False)
        stop_tts.save(self.stop_sound_file)
        
        # Initialize OCR components
        self.initialize_ocr_system()
        
        self.is_active = True
        self.debug_mode = False
        
        # Cache for recent queries
        self.query_cache = {}
        
        # Conversation memory (simple)
        self.conversation_memory = []
        self.memory_limit = 10
        
        # Start with a greeting
        self.speak(f"Hello, I'm {self.name}, your smart assistant. I can answer questions and also read and translate text from images. Say 'capture text' to use the OCR feature. How can I help you today?")

    def initialize_ocr_system(self):
        """Initialize camera, translator and create feedback sounds."""
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
            
            self.camera = Picamera2()
            self.translator = Translator()
            
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
            
            logger.info("OCR system initialized successfully")
            return True
        except Exception as e:
            logger.error(f"OCR initialization error: {str(e)}")
            return False
    
    def play_audio(self, audio_path):
        """Play audio with proper locking and error handling."""
        with self.audio_lock:
            try:
                # Kill any currently playing audio
                if self.current_audio_process and self.current_audio_process.poll() is None:
                    subprocess.run(['pkill', '-f', 'mpg123'], stderr=subprocess.DEVNULL)
                    self.current_audio_process = None
                
                # Start new audio playback using subprocess.run
                subprocess.run(['mpg123', '-q', audio_path], stderr=subprocess.DEVNULL)
            except Exception as e:
                logger.error(f"Audio playback failed: {str(e)}")
                self.current_audio_process = None
    
    def enhance_image(self, image):
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
    
    def preprocess_image(self, image_path):
        """Optimized image preprocessing for faster OCR."""
        try:
            # Read image
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError("Failed to read image")
            
            # Convert to grayscale for faster processing
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Use a faster, more lightweight processing approach
            # Instead of bilateral filter (slow), use Gaussian blur
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Use simple binary thresholding instead of adaptive for speed
            _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Save preprocessed image
            preprocessed_path = "preprocessed_image.jpg"
            cv2.imwrite(preprocessed_path, thresh)
            
            return preprocessed_path
        except Exception as e:
            logger.error(f"Preprocessing failed: {str(e)}")
            return image_path
    
    def extract_text(self, image_path):
        """Extract text using optimized OCR configurations and languages to reduce processing time."""
        # Reduced set of OCR configs for faster processing
        ocr_configs = [
            '--oem 3 --psm 3',  # Default - best for most cases
            '--oem 3 --psm 6'   # Assume uniform block of text - for simple layouts
        ]
        
        best_results = {lang_code: {'text': '', 'confidence': 0} 
                       for lang_code in SUPPORTED_LANGUAGES.keys()}
        
        # Use threading to process languages in parallel
        threads = []
        results_lock = threading.Lock()
        
        def process_language(lang_code, lang_info):
            tesseract_lang = lang_info['tesseract']
            confidence_threshold = lang_info['confidence_threshold']
            
            # Try only the first (most reliable) config first
            try:
                full_config = f"{ocr_configs[0]} -l {tesseract_lang}"
                
                text = pytesseract.image_to_string(
                    Image.open(image_path),
                    config=full_config
                ).strip()
                
                # Calculate confidence score
                if text and len(text) > 5:
                    # For non-Latin scripts, adjust confidence calculation
                    if lang_code in ['hi', 'mr']:
                        # Count non-space characters instead of alphanumeric
                        confidence = len([c for c in text if not c.isspace()]) / len(text)
                    else:
                        confidence = len([c for c in text if c.isalnum()]) / len(text)
                    
                    with results_lock:
                        if confidence > best_results[lang_code]['confidence']:
                            best_results[lang_code]['text'] = text
                            best_results[lang_code]['confidence'] = confidence
            
                # Only try the second config if the first one didn't produce good results
                if best_results[lang_code]['confidence'] < confidence_threshold and len(ocr_configs) > 1:
                    try:
                        full_config = f"{ocr_configs[1]} -l {tesseract_lang}"
                        
                        text = pytesseract.image_to_string(
                            Image.open(image_path),
                            config=full_config
                        ).strip()
                        
                        # Calculate confidence score
                        if text and len(text) > 5:
                            # For non-Latin scripts, adjust confidence calculation
                            if lang_code in ['hi', 'mr']:
                                # Count non-space characters instead of alphanumeric
                                confidence = len([c for c in text if not c.isspace()]) / len(text)
                            else:
                                confidence = len([c for c in text if c.isalnum()]) / len(text)
                            
                            with results_lock:
                                if confidence > best_results[lang_code]['confidence']:
                                    best_results[lang_code]['text'] = text
                                    best_results[lang_code]['confidence'] = confidence
                    except Exception as e:
                        logger.error(f"OCR (second config) failed for {lang_info['name']}: {str(e)}")
                        
            except Exception as e:
                logger.error(f"OCR (first config) failed for {lang_info['name']}: {str(e)}")
        
        # Create and start threads for each language
        for lang_code, lang_info in SUPPORTED_LANGUAGES.items():
            thread = threading.Thread(target=process_language, args=(lang_code, lang_info))
            threads.append(thread)
            thread.start()
            
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Find the best result across all languages
        best_lang = max(best_results.items(), 
                       key=lambda x: x[1]['confidence'])
        
        if best_lang[1]['confidence'] > SUPPORTED_LANGUAGES[best_lang[0]]['confidence_threshold']:
            logger.info(f"Detected text in {SUPPORTED_LANGUAGES[best_lang[0]]['name']}")
            return best_lang[1]['text'], best_lang[0]
        return '', None
    
    def translate_text(self, text, target_lang):
        """Translate text with retry mechanism."""
        max_retries = 3
        delay = 1
        
        for attempt in range(max_retries):
            try:
                translation = self.translator.translate(text, dest=target_lang)
                return translation.text
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Translation failed after {max_retries} attempts: {str(e)}")
                    return None
                time.sleep(delay)
                delay *= 2
        
        return None
    
    def capture_and_translate(self):
        """Capture image and perform translation with proper error handling."""
        logger.info("Starting capture and translate process")
        
        try:
            self.speak("Capturing image for text recognition. Please hold steady.")
            
            # Configure and capture image
            if self.camera:
                self.camera.stop()
                config = self.camera.create_still_configuration(main={"size": (2592, 1944)})
                self.camera.configure(config)
                self.camera.start()
                time.sleep(2)
                
                image_path = "captured_image.jpg"
                self.camera.capture_file(image_path)
                self.camera.stop()
                
                self.play_audio(AUDIO_PATHS['capture'])
                
                # Process image and extract text
                processed_path = self.preprocess_image(image_path)
                extracted_text, detected_lang = self.extract_text(processed_path)
                
                if not extracted_text:
                    logger.warning("No text detected in image")
                    self.play_audio(AUDIO_PATHS['no_text'])
                    self.speak("Sorry, I couldn't find any text in the image.")
                    return False
                
                logger.info(f"Extracted text: {extracted_text}")
                logger.info(f"Detected language: {SUPPORTED_LANGUAGES[detected_lang]['name']}")
                
                # Store the detected language and text
                self.current_language = detected_lang
                self.last_captured_text = extracted_text
                
                # Generate audio for original text
                tts = gTTS(extracted_text, lang=detected_lang)
                tts.save(AUDIO_PATHS['original'])
                
                # Translate to other supported languages
                self.last_translated_text = {}
                for target_code, target_info in SUPPORTED_LANGUAGES.items():
                    if target_code != detected_lang:
                        translated = self.translate_text(extracted_text, target_code)
                        if translated:
                            self.last_translated_text[target_code] = translated
                            tts = gTTS(translated, lang=target_code)
                            tts.save(AUDIO_PATHS[target_info['name']])
                            logger.info(f"Translation to {target_info['name']} completed")
                
                # Save to database if connection exists
                if self.connection_pool:
                    self.save_to_database(extracted_text, self.last_translated_text)
                
                self.play_audio(AUDIO_PATHS['complete'])
                
                # Tell the user what we found and immediately play the original text
                source_lang_name = SUPPORTED_LANGUAGES[detected_lang]['name'].capitalize()
                self.speak(f"I found {source_lang_name} text in the image. Here's what it says:")
                
                # Immediately play the original text
                time.sleep(1)  # Short pause
                self.play_audio(AUDIO_PATHS['original'])
                
                # Inform about translation options
                time.sleep(1)  # Give time for the original audio to finish
                self.speak(f"You can ask for translations by saying 'translate to Hindi' or similar.")
                
                return True
            else:
                self.speak("Sorry, the camera is not available.")
                return False
        
        except Exception as e:
            logger.error(f"Capture and translate failed: {str(e)}")
            self.play_audio(AUDIO_PATHS['error'])
            self.speak("Sorry, there was an error while capturing or processing the image.")
            return False
    
    def save_to_database(self, original_text, translations):
        """Save captured text and translations to database."""
        try:
            connection = self.connection_pool.get_connection()
            cursor = connection.cursor()
            
            # Get translations for each language
            english_text = translations.get('en', original_text if self.current_language == 'en' else '')
            hindi_text = translations.get('hi', original_text if self.current_language == 'hi' else '')
            marathi_text = translations.get('mr', original_text if self.current_language == 'mr' else '')
            
            # Prepare SQL query
            query = """
                INSERT INTO captured_images 
                (original_text, detected_language, english_translation, hindi_translation, marathi_translation, timestamp) 
                VALUES (%s, %s, %s, %s, %s, NOW())
            """
            
            # Execute query
            cursor.execute(query, (
                original_text,
                SUPPORTED_LANGUAGES[self.current_language]['name'],
                english_text,
                hindi_text,
                marathi_text
            ))
            
            # Commit the transaction
            connection.commit()
            cursor.close()
            connection.close()
            
            logger.info("Successfully saved text to database")
            
        except Exception as e:
            logger.error(f"Database save error: {str(e)}")
    
    def play_translation(self, language_code):
        """Play the translation for the specified language."""
        if not self.last_captured_text:
            self.speak("There's no captured text to play. Please capture text first.")
            return
        
        language_name = SUPPORTED_LANGUAGES.get(language_code, {}).get('name', '')
        
        if language_code == self.current_language:
            # Play original
            if os.path.exists(AUDIO_PATHS['original']):
                self.speak(f"Playing original {language_name} text.")
                self.play_audio(AUDIO_PATHS['original'])
            else:
                self.speak(f"Sorry, the original audio is not available.")
        else:
            # Play translation
            audio_path = AUDIO_PATHS.get(language_name)
            if os.path.exists(audio_path):
                self.speak(f"Playing {language_name} translation.")
                self.play_audio(audio_path)
            else:
                self.speak(f"Sorry, the {language_name} translation is not available.")
    
    def load_knowledge_base(self):
        """Load a basic knowledge base for common questions"""
        knowledge = defaultdict(str)
        
        # Science facts
        knowledge["What is gravity"] = "Gravity is the force that attracts objects toward one another. The law of universal gravitation states that every mass attracts every other mass in the universe."
        knowledge["What is photosynthesis"] = "Photosynthesis is the process by which green plants and some other organisms use sunlight to synthesize foods with carbon dioxide and water, generating oxygen as a byproduct."
        knowledge["What are atoms"] = "Atoms are the basic units of matter and the defining structure of elements. They consist of a nucleus containing protons and neutrons, surrounded by electrons."
        
        # Geography facts
        knowledge["What is the largest ocean"] = "The Pacific Ocean is the largest and deepest ocean on Earth, covering more than 60 million square miles."
        knowledge["What is the highest mountain"] = "Mount Everest is Earth's highest mountain above sea level, located in the Mahalangur Himal sub-range of the Himalayas with an elevation of 29,032 feet."
        knowledge["What is the longest river"] = "The Nile River in Africa is generally regarded as the longest river in the world, flowing about 4,132 miles."
        
        # History facts
        knowledge["Who was Albert Einstein"] = "Albert Einstein was a German-born theoretical physicist who developed the theory of relativity, one of the two pillars of modern physics. He is best known for his mass–energy equivalence formula E = mc²."
        knowledge["When did World War 2 end"] = "World War II ended on September 2, 1945, with the formal surrender of Japan aboard the U.S. battleship USS Missouri."
        knowledge["Who was the first person on the moon"] = "Neil Armstrong was the first person to walk on the Moon on July 21, 1969, during the Apollo 11 mission."
        
        return knowledge
        
    def load_science_knowledge(self):
        """Load science-related knowledge from JSON file"""
        try:
            knowledge_file_path = os.path.join(os.path.dirname(__file__), "knowledge_data.json")
            with open(knowledge_file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception as e:
            if hasattr(self, 'debug_mode') and self.debug_mode:
                print(f"Error loading science knowledge data: {e}")
            return {"science": {}}

    def speak(self, text):
        """Convert text to speech using gTTS and mpg123 player"""
        print(f"{self.name}: {text}")
        
        # Reset the stop flag before speaking
        self.stop_speaking = False
        
        try:
            # Create a temporary file for the speech audio
            speech_file = os.path.join(self.temp_dir, "assistant_speech.mp3")
            
            # Generate speech using gTTS
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(speech_file)
            
            # Play the speech file using mpg123 (better for Raspberry Pi)
            with self.audio_lock:
                # Stop any currently playing audio
                if self.current_audio_process and self.current_audio_process.poll() is None:
                    subprocess.run(['pkill', '-f', 'mpg123'], stderr=subprocess.DEVNULL)
                    self.current_audio_process = None
                
                # Start a thread to check for stop command while speaking
                stop_thread = threading.Thread(target=self.check_for_stop_command)
                stop_thread.daemon = True
                stop_thread.start()
                
                # Play the new audio using subprocess.run
                subprocess.run(["mpg123", "-q", speech_file])
                
                # Check if we were interrupted
                if self.stop_speaking:
                    print("Speech interrupted by user")
                    subprocess.run(["mpg123", "-q", self.stop_sound_file])
            
            # Clean up the temporary file - optional, can be kept for debugging
            try:
                os.remove(speech_file)
            except:
                pass
                
        except Exception as e:
            print(f"Speech error: {e}")
            # Fall back to just printing if speech fails
            print(f"{self.name}: {text}")
            
    def check_for_stop_command(self):
        """Check if the user wants to stop the assistant while it's speaking"""
        try:
            with self.microphone as source:
                # Set timeout to be very short so we return quickly
                audio = self.recognizer.listen(source, timeout=0.5, phrase_time_limit=1.0)
                
                try:
                    # Only use Google for quick detection of stop words
                    text = self.recognizer.recognize_google(audio, language='en-IN')
                    
                    # Check if it's a stop command
                    text_lower = text.lower()
                    if any(stop_word in text_lower for stop_word in self.categories['stop']):
                        # Set the flag to stop speaking
                        self.stop_speaking = True
                        
                        # Stop the audio immediately
                        subprocess.run(['pkill', '-f', 'mpg123'], stderr=subprocess.DEVNULL)
                        
                except (sr.UnknownValueError, sr.RequestError):
                    # Ignore speech recognition errors in this thread
                    pass
        except:
            # Ignore any errors in the thread
            pass
    
    def listen(self):
        """Listen for voice input and convert to text"""
        if self.listening_sound:
            self.listening_sound.play()
            
        print(f"{self.name} is listening...")
        
        with self.microphone as source:
            try:
                # Adjust for ambient noise before each listening session
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                # Set a dynamic energy threshold - helps with different voice volumes
                self.recognizer.energy_threshold = 250  # Lower from 300 to be more sensitive
                self.recognizer.dynamic_energy_threshold = True
                
                # Increase timeout and phrase_time_limit to give users more time to speak
                # timeout: how long to wait for speech to start
                # phrase_time_limit: maximum length of a phrase - increased to 15 seconds
                audio = self.recognizer.listen(source, timeout=12, phrase_time_limit=15)
                
                if self.listening_sound:
                    pygame.mixer.stop()
                
                # Try multiple recognition engines with fallbacks
                text = None
                
                # First try Google's service which is most accurate
                try:
                    text = self.recognizer.recognize_google(audio, language='en-IN')
                except sr.UnknownValueError:
                    if self.debug_mode:
                        print("Google Speech Recognition could not understand audio")
                except sr.RequestError as e:
                    if self.debug_mode:
                        print(f"Could not request results from Google Speech Recognition service: {e}")
                
                # If Google fails, try offline Sphinx as last resort
                if text is None:
                    try:
                        text = self.recognizer.recognize_sphinx(audio)
                    except (sr.UnknownValueError, sr.RequestError, AttributeError):
                        if self.debug_mode:
                            print("Sphinx recognition also failed or not available")
                
                if text:
                    print(f"You said: {text}")
                    return text.lower()
                else:
                    if self.debug_mode:
                        print("Could not understand audio with any recognition service")
                    return ""
                    
            except sr.WaitTimeoutError:
                if self.debug_mode:
                    print("Listening timed out - no speech detected")
                if self.listening_sound:
                    pygame.mixer.stop()
                return ""
    
    def categorize_query(self, query):
        """Determine the category of a user query using more sophisticated matching"""
        if not query:
            return None
        
        query_lower = query.lower()
        
        # Pre-process query
        query_tokens = word_tokenize(query_lower)
        stop_words = set(stopwords.words('english'))
        query_tokens = [token for token in query_tokens if token not in stop_words and len(token) > 2]
        
        # Special case handling for common misclassifications
        if "raspberry pi" in query_lower:
            return "web_search"  # Force web search for Raspberry Pi queries
        
        # Check for exact phrase matches first (more specific)
        for category, keywords in self.categories.items():
            for keyword in keywords:
                # Check for exact phrases (higher priority)
                if keyword in query_lower and len(keyword.split()) > 1:
                    return category
        
        # Use word boundary matching for single words to avoid substring matches
        for category, keywords in self.categories.items():
            for keyword in keywords:
                if len(keyword.split()) == 1:  # Single word
                    # Check if it's a whole word using word boundaries
                    pattern = r'\b' + re.escape(keyword) + r'\b'
                    if re.search(pattern, query_lower):
                        return category
        
        # For more complex queries, use a scoring system
        category_scores = {}
        words = query_lower.split()
        
        for category, keywords in self.categories.items():
            score = 0
            for keyword in keywords:
                keyword_words = keyword.split()
                # Check for partial matches
                for kw in keyword_words:
                    if kw in words and len(kw) > 2:  # Only count meaningful words
                        score += 1
            if score > 0:
                category_scores[category] = score
        
        # Return the category with the highest score if any
        if category_scores:
            best_category = max(category_scores.items(), key=lambda x: x[1])[0]
            # Only return if score is significant
            if category_scores[best_category] > 1:
                return best_category
                
        # Default to web search if no category matches
        return "web_search"
    
    def get_current_time(self):
        """Get the current time"""
        current_time = datetime.datetime.now().strftime("%I:%M %p")
        return f"The current time is {current_time}."
        
    def get_current_date(self):
        """Get the current date"""
        current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")
        return f"Today is {current_date}."
        
    def get_weather(self, location=""):
        """Get weather information for a location"""
        if not location:
            location = "current location"
            
        try:
            # Web scraping approach for weather (no API key required)
            url = f"https://www.google.com/search?q=weather+in+{location.replace(' ', '+')}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract temperature (this selector might need updates based on Google's layout changes)
            temp_div = soup.find('div', {'class': 'BNeawe iBp4i AP7Wnd'})
            if temp_div:
                temperature = temp_div.text
                return f"The temperature in {location} is currently {temperature}."
            else:
                return f"I couldn't find the weather for {location}. Please try another location."
                
        except Exception as e:
            if self.debug_mode:
                print(f"Weather error: {e}")
            return f"I'm having trouble getting weather information right now. Please try again later."
    
    def get_last_captured_text(self):
        """Retrieve the last captured text from memory or database"""
        if self.last_captured_text:
            source_lang = SUPPORTED_LANGUAGES[self.current_language]['name'].capitalize()
            return f"The last captured text ({source_lang}): {self.last_captured_text}"
        
        # If no text in memory, try database
        if self.connection_pool:
            try:
                connection = self.connection_pool.get_connection()
                cursor = connection.cursor(dictionary=True)
                
                # Query to get the most recent text entry
                query = """
                    SELECT original_text, detected_language, english_translation, hindi_translation, marathi_translation 
                    FROM captured_images 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """
                
                cursor.execute(query)
                result = cursor.fetchone()
                
                cursor.close()
                connection.close()
                
                if result and result['original_text']:
                    text = result['original_text']
                    lang = result.get('detected_language', 'unknown language')
                    return f"The last captured text ({lang}): {text}"
                else:
                    return "I couldn't find any captured text in the database."
                    
            except Exception as e:
                if self.debug_mode:
                    print(f"Database error: {e}")
                return "I'm having trouble retrieving the last captured text. Please try again later."
        
        return "There's no captured text available. Please capture text first using the 'capture text' command."
    
    def process_query(self, query):
        """Process the user's query and generate a more accurate response, including OCR commands"""
        if not query:
            return "I didn't catch that. Could you please repeat more clearly?"
            
        # Check if query is in cache
        if query in self.query_cache:
            return self.query_cache[query]
        
        # Add to conversation memory
        self.conversation_memory.append(("user", query))
        if len(self.conversation_memory) > self.memory_limit:
            self.conversation_memory.pop(0)
        
        # Check for assistant name in query to activate
        assistant_names = [self.name.lower(), "assistant"]
        is_addressed = any(name in query.lower() for name in assistant_names)
        
        # Direct time/date handling - highest priority
        query_lower = query.lower()
        
        # Time queries
        if any(phrase in query_lower for phrase in ["what time", "current time", "time now", "what's the time"]):
            return self.get_current_time()
            
        # Date queries
        if any(phrase in query_lower for phrase in ["what date", "current date", "date today", "what's the date", "what day", "day today", "what's today"]):
            return self.get_current_date()
        
        # Check if it's a goodbye intent
        if any(word in query_lower for word in self.categories['goodbye']):
            self.is_active = False
            return "Goodbye! Have a great day."
        
        # Basic greeting
        if any(word in query_lower for word in self.categories['greeting']):
            return f"Hello! How can I help you today?"
        
        # About the assistant
        if any(phrase in query_lower for phrase in self.categories['about']):
            return f"I'm {self.name}, a smart assistant designed to help answer your questions and recognize text from images. I can capture and translate text, tell you the time, date, weather, news, and information from Wikipedia, among other things. Just ask me a question or say 'capture text' to use OCR."
        
        # Handle straightforward service categories first
        category = self.categorize_query(query)
        
        # Handle OCR-related commands
        if category == "capture":
            # No need to return a response, capture_and_translate will speak 
            self.capture_and_translate()
            return "Processing image for text recognition..."
            
        elif category == "play_original" and self.last_captured_text:
            self.play_translation(self.current_language)
            return f"Playing the original text in {SUPPORTED_LANGUAGES[self.current_language]['name']}."
            
        elif category == "play_english" and self.last_captured_text:
            self.play_translation('en')
            return "Playing the English translation."
            
        elif category == "play_hindi" and self.last_captured_text:
            self.play_translation('hi')
            return "Playing the Hindi translation."
            
        elif category == "play_marathi" and self.last_captured_text:
            self.play_translation('mr')
            return "Playing the Marathi translation."
            
        elif category == "translate":
            # Check if we have text to translate
            if not self.last_captured_text:
                return "There's no captured text to translate. Please capture text first."
                
            # Determine target language
            target_lang = None
            for lang_code, lang_info in SUPPORTED_LANGUAGES.items():
                if lang_info['name'].lower() in query.lower():
                    target_lang = lang_code
                    break
                    
            if target_lang:
                self.play_translation(target_lang)
                return f"Playing the {SUPPORTED_LANGUAGES[target_lang]['name']} translation."
            else:
                return "Please specify which language you want to translate to."
                
        elif category == "read_text":
            return self.get_last_captured_text()
            
        # Standard assistant capabilities
        elif category == "time":
            response = self.get_current_time()
        elif category == "date":
            response = self.get_current_date()
        elif category == "weather":
            # Extract location if provided with improved pattern matching
            location_match = re.search(r'(?:weather|temperature|forecast)\s+(?:in|at|for)\s+([a-zA-Z ]+)', query.lower())
            if not location_match:
                # Try a simpler pattern
                location_match = re.search(r'([a-zA-Z ]+)\s+(?:weather|temperature|forecast)', query.lower())
            location = location_match.group(1).strip() if location_match else ""
            response = self.get_weather(location)
        elif category == "news":
            response = self.get_news()
        elif category == "calculation":
            response = self.handle_calculation(query)
        else:
            # For most queries, try web-based sources first (Wikipedia and web search)
            
            # First, try Wikipedia for informational queries
            wiki_result = self.get_wikipedia_info(query)
            if wiki_result:
                response = wiki_result
            else:
                # If Wikipedia doesn't have it, try general web search
                search_result = self.search_web(query)
                if search_result:
                    response = search_result
                else:
                    # Only fall back to local knowledge base if web sources fail
                    
                    # Try specific knowledge domains if the category suggests it
                    if category == "science":
                        knowledge_result = self.get_science_info(query)
                    elif category == "math":
                        knowledge_result = self.get_math_info(query)
                    elif category == "history":
                        knowledge_result = self.get_history_info(query)
                    elif category == "geography":
                        knowledge_result = self.get_geography_info(query)
                    else:
                        knowledge_result = self.find_in_knowledge_base(query)
                    
                    if knowledge_result:
                        response = knowledge_result
                    else:
                        response = f"I'm sorry, I couldn't find information about '{query}'. Could you please rephrase your question or ask me about something else?"
        
        # Save to cache
        self.query_cache[query] = response
        
        # Add to conversation memory
        self.conversation_memory.append(("assistant", response))
        if len(self.conversation_memory) > self.memory_limit:
            self.conversation_memory.pop(0)
        
        return response
        
    def run(self):
        """Run the assistant in a continuous loop"""
        try:
            while self.is_active:
                query = self.listen()
                
                if query:
                    response = self.process_query(query)
                    self.speak(response)
                    
                time.sleep(0.1)  # Small delay to prevent high CPU usage
                
        except KeyboardInterrupt:
            self.speak("Shutting down. Goodbye!")
        finally:
            # Clean up resources
            if self.camera:
                self.camera.stop()
            # Stop any playing audio
            try:
                subprocess.run(['pkill', '-f', 'mpg123'], stderr=subprocess.DEVNULL)
            except:
                pass 

    def get_science_info(self, query):
        """Find relevant science information from the knowledge data"""
        if not self.science_knowledge or "science" not in self.science_knowledge:
            return None
        
        science_data = self.science_knowledge["science"]
        query_lower = query.lower()
        
        # Pre-process query - tokenize and remove stopwords
        query_tokens = word_tokenize(query_lower)
        stop_words = set(stopwords.words('english'))
        query_tokens = [token for token in query_tokens if token not in stop_words and len(token) > 2]
        
        # Special case for general science queries
        if any(phrase in query_lower for phrase in ["what is science", "tell me about science", "explain science"]):
            overview = "Science is the systematic study of the natural world through observation and experimentation. Here are some major branches of science:\n\n"
            for topic, topic_data in science_data.items():
                if isinstance(topic_data, str):
                    overview += f"- {topic.capitalize()}: {topic_data[:100]}...\n"
                elif isinstance(topic_data, dict):
                    overview += f"- {topic.capitalize()}: {list(topic_data.keys())}\n"
            return overview
        
        # First, check for exact topic matches
        for topic, topic_data in science_data.items():
            if topic.lower() in query_lower:
                # If the topic is directly mentioned
                if isinstance(topic_data, str):
                    return topic_data
                elif isinstance(topic_data, dict):
                    # If it's a dictionary, check if any specific subtopic is mentioned
                    for subtopic, info in topic_data.items():
                        if subtopic.lower() in query_lower:
                            if isinstance(info, str):
                                return f"{subtopic.capitalize()}: {info}"
                            elif isinstance(info, dict):
                                # Check for third-level topics
                                for detail_topic, detail_info in info.items():
                                    if detail_topic.lower() in query_lower:
                                        return f"{detail_topic.capitalize()}: {detail_info}"
                                
                                # If no specific third-level topic was mentioned, give an overview
                                overview = f"About {subtopic}:\n"
                                for detail_topic, detail_info in info.items():
                                    overview += f"- {detail_topic.capitalize()}: {detail_info}\n"
                                return overview
                    
                    # If no specific subtopic was mentioned, provide a general overview of the topic
                    overview = f"About {topic}:\n\n"
                    for subtopic, info in topic_data.items():
                        if isinstance(info, str):
                            overview += f"- {subtopic.capitalize()}: {info}\n"
                        elif isinstance(info, dict):
                            overview += f"- {subtopic.capitalize()}: {list(info.keys())}\n"
                    return overview
        
        # If no direct topic match, use more sophisticated semantic matching
        # Create a simple TF-IDF based matching
        all_topics = []
        all_keys = []
        
        # Flatten the structure for better search
        for topic, topic_data in science_data.items():
            all_topics.append(topic)
            all_keys.append(topic)
            
            if isinstance(topic_data, dict):
                for subtopic, info in topic_data.items():
                    all_topics.append(f"{topic} - {subtopic}")
                    all_keys.append(f"{topic}|{subtopic}")
                    
                    if isinstance(info, dict):
                        for detail_topic, _ in info.items():
                            all_topics.append(f"{topic} - {subtopic} - {detail_topic}")
                            all_keys.append(f"{topic}|{subtopic}|{detail_topic}")
        
        # If we have topics to match against
        if all_topics:
            try:
                # Use TF-IDF vectorizer for better matching
                vectorizer = TfidfVectorizer(stop_words='english')
                vectors = vectorizer.fit_transform(all_topics)
                query_vector = vectorizer.transform([query_lower])
                
                # Calculate similarity
                similarities = cosine_similarity(query_vector, vectors)[0]
                best_match_idx = similarities.argmax()
                
                # Only consider if similarity is above threshold
                if similarities[best_match_idx] > 0.2:
                    best_match_key = all_keys[best_match_idx]
                    parts = best_match_key.split('|')
                    
                    # Navigate to the matched information
                    if len(parts) == 1:
                        topic = parts[0]
                        topic_data = science_data[topic]
                        if isinstance(topic_data, str):
                            return f"{topic.capitalize()}: {topic_data}"
                        else:
                            # Return overview for dictionary data
                            overview = f"About {topic}:\n\n"
                            for subtopic, info in topic_data.items():
                                if isinstance(info, str):
                                    overview += f"- {subtopic.capitalize()}: {info}\n"
                                else:
                                    overview += f"- {subtopic.capitalize()}\n"
                            return overview
                    
                    elif len(parts) == 2:
                        topic, subtopic = parts
                        info = science_data[topic][subtopic]
                        if isinstance(info, str):
                            return f"{subtopic.capitalize()}: {info}"
                        else:
                            # Return overview for nested dictionary
                            overview = f"About {subtopic}:\n\n"
                            for detail_topic, detail_info in info.items():
                                overview += f"- {detail_topic.capitalize()}: {detail_info}\n"
                            return overview
                    
                    elif len(parts) == 3:
                        topic, subtopic, detail_topic = parts
                        return f"{detail_topic.capitalize()}: {science_data[topic][subtopic][detail_topic]}"
            except Exception as e:
                if self.debug_mode:
                    print(f"Error in semantic matching: {e}")
        
        # Last resort - check for any keyword in the content
        for topic, topic_data in science_data.items():
            if isinstance(topic_data, dict):
                for subtopic, info in topic_data.items():
                    for query_token in query_tokens:
                        if len(query_token) > 3 and (query_token in subtopic.lower() or 
                                                    (isinstance(info, str) and query_token in info.lower())):
                            if isinstance(info, str):
                                return f"{subtopic.capitalize()}: {info}"
                            break
        
        return None

    def get_math_info(self, query):
        """Find relevant math information from the knowledge data"""
        if not self.science_knowledge or "math" not in self.science_knowledge:
            return None
        
        math_data = self.science_knowledge["math"]
        query_lower = query.lower()
        
        # Pre-process query
        query_tokens = word_tokenize(query_lower)
        stop_words = set(stopwords.words('english'))
        query_tokens = [token for token in query_tokens if token not in stop_words]
        
        # Check for direct math concept mentions
        for concept, info in math_data.items():
            if concept.lower() in query_lower:
                if isinstance(info, str):
                    return info
                elif isinstance(info, dict):
                    # For nested structures like tables, square numbers, etc.
                    overview = f"About {concept}:\n\n"
                    
                    # Look for specific sub-concepts
                    for sub_concept, sub_info in info.items():
                        # For specific tables, square roots, etc.
                        if sub_concept.lower() in query_lower:
                            return f"{sub_concept}: {sub_info}"
                    
                    # If no specific sub-concept was mentioned, provide a summary
                    if len(info) <= 7:  # For smaller collections, show all items
                        for sub_concept, sub_info in info.items():
                            overview += f"- {sub_concept}: {sub_info}\n"
                    else:  # For larger collections, just list the available items
                        overview += "Available information: " + ", ".join(info.keys())
                    
                    return overview
        
        # Handle specific number-based queries
        number_match = re.search(r'table of (\d+)', query_lower) or re.search(r'(\d+) times table', query_lower)
        if number_match:
            number = number_match.group(1)
            table_key = f"table_{number}"
            if "tables" in math_data and table_key in math_data["tables"]:
                return f"Multiplication table of {number}: {math_data['tables'][table_key]}"
            elif number.isdigit():
                # Generate the table on-the-fly if not found
                table = []
                for i in range(1, 11):
                    table.append(f"{number}x{i}={int(number)*i}")
                return f"Multiplication table of {number}: {', '.join(table)}"
        
        # Similar methods as above for other math info...
        return None
    
    def get_history_info(self, query):
        """Find relevant historical information from the knowledge data"""
        if not self.science_knowledge or "history" not in self.science_knowledge:
            return None
        
        history_data = self.science_knowledge["history"]
        query_lower = query.lower()
        
        # Similar implementation as get_science_info for history...
        return None

    def get_geography_info(self, query):
        """Find relevant geographical information from the knowledge data"""
        if not self.science_knowledge or "geography" not in self.science_knowledge:
            return None
        
        geography_data = self.science_knowledge["geography"]
        query_lower = query.lower()
        
        # Similar implementation as get_science_info for geography...
        return None
    
    def get_wikipedia_info(self, query):
        """Get information from Wikipedia"""
        try:
            # Clean up the query
            search_query = query
            for prefix in ["who is", "what is", "tell me about", "wikipedia", "define"]:
                search_query = search_query.replace(prefix, "").strip()
            
            # First try direct Wikipedia API
            try:
                # Search for Wikipedia pages
                search_results = wikipedia.search(search_query, results=3)
                
                if search_results:
                    # Get the page for the first result
                    page = wikipedia.page(search_results[0], auto_suggest=False)
                    
                    # Get a summary (first 3 sentences)
                    summary = wikipedia.summary(search_results[0], sentences=3, auto_suggest=False)
                    
                    return summary
                else:
                    return None
            except wikipedia.exceptions.DisambiguationError as e:
                # If there's a disambiguation, get the first option
                try:
                    page = wikipedia.page(e.options[0], auto_suggest=False)
                    summary = wikipedia.summary(e.options[0], sentences=3, auto_suggest=False)
                    return summary
                except:
                    pass
            except wikipedia.exceptions.PageError:
                # Page not found, continue to web scraping method
                pass
            except Exception as wiki_api_error:
                if self.debug_mode:
                    print(f"Wikipedia API error: {wiki_api_error}")
            
            # Fallback to web scraping method
            url = f"https://en.wikipedia.org/wiki/{search_query.replace(' ', '_')}"
            response = requests.get(url)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Get the first paragraph of content
                paragraphs = soup.select("div.mw-parser-output > p")
                for p in paragraphs:
                    if p.text.strip():
                        # Return the first non-empty paragraph
                        return p.text.strip()
            
            return None
            
        except Exception as e:
            if self.debug_mode:
                print(f"Wikipedia error: {e}")
            return None
    
    def get_news(self):
        """Get latest news headlines"""
        try:
            # Web scraping approach for news (no API key required)
            url = "https://news.google.com/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find news articles
            articles = soup.find_all('a', {'class': 'VDXfz'})
            
            if articles:
                headlines = []
                for i, article in enumerate(articles[:5]):  # Get top 5 headlines
                    headlines.append(f"{i+1}. {article.text.strip()}")
                    
                headlines_text = "\n".join(headlines)
                return f"Here are the latest headlines:\n{headlines_text}"
            else:
                return "I couldn't retrieve the latest news headlines. Please try again later."
                
        except Exception as e:
            if self.debug_mode:
                print(f"News error: {e}")
            return "I'm having trouble getting the news right now. Please try again later."
    
    def search_web(self, query):
        """Search the web for information with improved accuracy"""
        try:
            # Use web scraping to get search results
            search_query = query.replace("search for", "").replace("google", "").replace("find", "").replace("look up", "").strip()
            
            # First try Wikipedia with more specific handling for various topics
            try:
                # For certain topics, make the Wikipedia query more specific
                if "raspberry pi" in search_query.lower():
                    wiki_result = self.get_wikipedia_info("Raspberry Pi computer")
                elif any(state in search_query.lower() for state in ["jammu", "kashmir"]):
                    wiki_result = self.get_wikipedia_info("Jammu and Kashmir")
                else:
                    wiki_result = self.get_wikipedia_info(search_query)
                    
                if wiki_result and "I couldn't find information" not in wiki_result:
                    return wiki_result
            except Exception as wiki_error:
                if self.debug_mode:
                    print(f"Wikipedia search error: {wiki_error}")
            
            # Then try Google search with more careful parsing
            url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try to find a featured snippet or direct answer
            answer_div = soup.find('div', {'class': 'Z0LcW'}) or soup.find('div', {'class': 'IZ6rdc'})
            if answer_div:
                return answer_div.text
                
            # Look for search result snippets with better handling of nested content
            results = soup.find_all('div', {'class': 'BNeawe s3v9rd AP7Wnd'})
            if results:
                for result in results:
                    # Skip very short results as they're often not useful
                    if len(result.text.strip()) > 50:
                        return result.text.strip()
                
                # If we only found short results, return the first one anyway
                if results[0]:
                    return results[0].text.strip()
            
            # Try alternate selectors for Google's changing layout
            alternate_results = soup.find_all('div', {'class': 'kCrYT'})
            if alternate_results:
                for result in alternate_results:
                    if result.text and len(result.text.strip()) > 50:
                        return result.text.strip()
            
            # If web search fails, return None to indicate no results found
            return None
            
        except Exception as e:
            if self.debug_mode:
                print(f"Web search error: {e}")
            return None
    
    def handle_calculation(self, query):
        """Handle mathematical calculations"""
        # Extract the calculation part from the query
        query = query.replace("calculate", "").replace("compute", "").replace("solve", "").strip()
        
        # Replace word operators with symbols
        query = query.replace("plus", "+").replace("minus", "-").replace("times", "*").replace("multiplied by", "*")
        query = query.replace("divided by", "/").replace("over", "/")
        
        # Basic calculation using eval (with security measures)
        try:
            # Only allow basic arithmetic operations
            allowed_chars = set("0123456789+-*/().^ ")
            if not all(c in allowed_chars for c in query):
                return "I can only perform basic arithmetic calculations."
                
            # Replace ^ with ** for exponentiation
            query = query.replace("^", "**")
            
            result = eval(query)
            return f"The result of {query} is {result}."
            
        except Exception as e:
            if self.debug_mode:
                print(f"Calculation error: {e}")
            return "I couldn't perform that calculation. Please try a simpler arithmetic expression."
            
    def find_in_knowledge_base(self, query):
        """Find the most relevant answer in the knowledge base"""
        if not query or not self.knowledge_base:
            return None
            
        # Prepare vectorizer for text similarity
        vectorizer = TfidfVectorizer(stop_words=stopwords.words('english'))
        
        # Convert knowledge base to list format for vectorization
        keys = list(self.knowledge_base.keys())
        
        try:
            # Vectorize the knowledge base questions
            knowledge_vectors = vectorizer.fit_transform(keys)
            
            # Vectorize the query
            query_vector = vectorizer.transform([query])
            
            # Calculate similarity scores
            similarities = cosine_similarity(query_vector, knowledge_vectors)[0]
            
            # Find the most similar question
            best_match_index = np.argmax(similarities)
            best_match_score = similarities[best_match_index]
            
            # Only return if similarity is above threshold
            if best_match_score > 0.3:
                best_match_question = keys[best_match_index]
                return self.knowledge_base[best_match_question]
                
        except Exception as e:
            if self.debug_mode:
                print(f"Knowledge base error: {e}")
                
        return None 

# Main execution
if __name__ == "__main__":
    print("Initializing Smart Assistant...")
    # You can customize the assistant's name and voice
    assistant = SmartAssistant(name="Alex", voice_index=0)
    
    try:
        # Run the assistant
        assistant.run()
    except Exception as e:
        print(f"Assistant error: {e}")