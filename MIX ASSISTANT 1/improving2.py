import cv2
import pytesseract
import os
import json
import datetime
import threading
import time
import calendar
import RPi.GPIO  # Added GPIO library
from PIL import Image
from picamera2 import Picamera2
import speech_recognition as sr
from translate import Translator
from gtts import gTTS
import pygame
from io import BytesIO
import numpy as np
import logging  # Added for error logging

# Setup basic logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SmartAssistant')

class SmartAssistant:
    def __init__(self):
        # Initialize components
        self.recognizer = sr.Recognizer()
        self.setup_camera()
        self.knowledge_data = self.load_knowledge()
        
        # Setup image directory
        self.image_dir = "/home/pi/Desktop/Saved Images"
        os.makedirs(self.image_dir, exist_ok=True)
        self.last_image_path = ""
        self.last_extracted_text = ""
        
        # Globals
        self.button_thread = None
        self.is_running = True
        self.is_speaking = False
        
        # GPIO setup
        self.BUTTON_PIN = 17  # GPIO17 (Pin 11) - Change this to your preferred GPIO pin
        RPi.GPIO.setmode(RPi.GPIO.BCM)  # Use BCM pin numbering
        RPi.GPIO.setup(self.BUTTON_PIN, RPi.GPIO.IN, pull_up_down=RPi.GPIO.PUD_UP)  # Set as input with pull-up
        
        # Initialize pygame for audio playback
        pygame.mixer.init()
        
        # OCR configs
        self.ocr_config = r'--oem 1 --psm 3 -l eng'
        self.fallback_ocr_config = r'--psm 3'
        
        # Initialize translation cache
        self.translation_cache = {}
        
        # Add supported languages for auto-translation
        self.supported_languages = {
            "hi": "Hindi",
            "mr": "Marathi"
        }
        
        # Warm up the camera (reduces initial delay)
        self.warmup_camera()
        
        # Help text
        self.help_text = """
        Smart Assistant Commands:
        - "capture": Take a photo and display it
        - "read": Capture image and read text
        - "translate it in Hindi": Translate text from last image to Hindi
        - "translate it in Marathi": Translate text from last image to Marathi
        - "current date": Tell today's date
        - "current time": Tell current time
        - "what day is it": Tell current day
        - "who made you": Tell about the creator
        - "help": List all commands
        - You can also ask general questions about science, math, history, and geography
        """
    
    def load_knowledge(self):
        """Load knowledge base from JSON file using absolute path"""
        try:
            # MODIFIED: Using absolute path to knowledge_data.json
            with open("/home/pi/Desktop/knowledge_data.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print("Knowledge data file not found. Creating empty knowledge base.")
            return {}
        except json.JSONDecodeError:
            print("Error parsing knowledge data. Creating empty knowledge base.")
            return {}
    
    def setup_camera(self):
        """Initialize camera with balanced settings for speed and quality"""
        self.picam2 = Picamera2()
        # Use a more moderate resolution for faster processing while maintaining decent quality
        self.picam2.preview_configuration.main.size = (1280, 720)
        self.picam2.preview_configuration.main.format = "RGB888"
        self.picam2.configure("preview")
    
    def warmup_camera(self):
        """Pre-initialize camera to reduce startup delay when reading"""
        try:
            self.picam2.start()
            time.sleep(0.3)  # Brief warmup
            self.picam2.stop()
            print("Camera pre-initialized")
        except Exception as e:
            print(f"Camera warmup error: {e}")
    
    def stop_speaking(self):
        """Stop any ongoing TTS"""
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            self.is_speaking = False
            print("Stopped speaking to listen for command.")
    
    def speak(self, text, use_tts=True):
        """Optimized TTS function with faster response time"""
        print("\n[Assistant]:", text)
        
        if not use_tts:
            return
        
        self.is_speaking = True
        
        try:
            # Create a separate thread for TTS generation to avoid blocking
            def generate_and_play_speech():
                # Use faster TTS settings
                tts = gTTS(text=text, lang='en', slow=False)
                mp3_fp = BytesIO()
                tts.write_to_fp(mp3_fp)
                mp3_fp.seek(0)
                
                # Play the audio
                pygame.mixer.music.load(mp3_fp)
                pygame.mixer.music.play()
                
                # Wait for audio to finish
                while pygame.mixer.music.get_busy() and self.is_speaking:
                    pygame.time.Clock().tick(60)
                
                self.is_speaking = False
            
            # Start TTS in background thread
            speech_thread = threading.Thread(target=generate_and_play_speech)
            speech_thread.daemon = True
            speech_thread.start()
        except Exception as e:
            print(f"TTS error: {e}")
            self.is_speaking = False
    
    def search_knowledge_base(self, query):
        """Search the knowledge base for answers to user queries"""
        # ...existing code...
        return "I don't have information about that. Please ask something related to science, math, history, or geography."
    
    def capture_image(self):
        """Capture an image and display it on screen"""
        self.speak("Taking a photo. Please hold steady.")
        
        try:
            # Start camera
            self.picam2.start()
            time.sleep(0.5)  # Brief warm-up time
            
            # Capture the image
            frame = self.picam2.capture_array()
            
            # Generate unique filename with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"capture_{timestamp}.jpg"
            self.last_image_path = os.path.join(self.image_dir, filename)
            
            # Save the image
            cv2.imwrite(self.last_image_path, frame)
            print(f"Image saved to {self.last_image_path}")
            
            # Add timestamp to the displayed image
            display_frame = frame.copy()
            timestamp_text = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(display_frame, timestamp_text, (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Display the image
            cv2.namedWindow("Captured Image", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Captured Image", 800, 480)
            cv2.imshow("Captured Image", display_frame)
            
            # Stop camera
            self.picam2.stop()
            
            # Keep image displayed until a key is pressed or for timeout
            self.speak("Image captured. Press any key to close the image.")
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            
            return self.last_image_path
            
        except Exception as e:
            print(f"Image capture error: {str(e)}")
            self.speak("I encountered an error while capturing the image. Please try again.")
            return None
    
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
    
    def fast_preprocess_image(self, image):
        """Enhanced image preprocessing optimized for OCR accuracy"""
        return self.enhance_image(image)
    
    def generate_translations_background(self, text):
        """Generate translations in background for all supported languages"""
        if not text or not text.strip():
            return
            
        def translate_worker():
            for lang_code, lang_name in self.supported_languages.items():
                # Skip if translation already in cache
                cache_key = f"{text[:5000]}_{lang_code}"
                if cache_key in self.translation_cache:
                    continue
                    
                try:
                    print(f"Generating {lang_name} translation in background...")
                    translator = Translator(to_lang=lang_code)
                    translated = translator.translate(text)
                    self.translation_cache[cache_key] = translated
                    print(f"Background {lang_name} translation complete")
                except Exception as e:
                    print(f"Background translation error ({lang_name}): {str(e)}")
        
        # Start translation in background thread
        trans_thread = threading.Thread(target=translate_worker)
        trans_thread.daemon = True
        trans_thread.start()
    
    def read_text(self):
        """Capture an image and perform OCR on it"""
        # Capture an image first
        image_path = self.capture_image()
        if not image_path:
            self.speak("Failed to capture an image for reading.")
            return
        
        self.speak("Processing the text from the captured image.")
        
        # Process the image in a separate thread
        def process_image_thread():
            try:
                # Read the image
                frame = cv2.imread(image_path)
                if frame is None:
                    self.speak("Failed to read the captured image.")
                    return
                
                # Use enhanced image preprocessing for better OCR results
                processed_frame = self.enhance_image(frame)
                
                # Use PIL for OCR (required by pytesseract)
                pil_img = Image.fromarray(processed_frame)
                
                # Try OCR with multiple configurations if needed
                try:
                    # First try with primary OCR configuration
                    text = pytesseract.image_to_string(pil_img, config=self.ocr_config)
                except Exception as ocr_error:
                    print(f"Primary OCR failed: {ocr_error}")
                    self.speak("Trying different recognition method.")
                    try:
                        # Try with fallback configuration
                        text = pytesseract.image_to_string(pil_img, config=self.fallback_ocr_config)
                    except Exception as fallback_error:
                        print(f"Fallback OCR also failed: {fallback_error}")
                        self.speak("Still having difficulty. Trying one more method.")
                        # Last resort: try with no special config
                        try:
                            text = pytesseract.image_to_string(pil_img)
                        except Exception as last_error:
                            print(f"All OCR attempts failed: {last_error}")
                            text = ""
                
                # Clean up the text - remove extra newlines and spaces
                text = " ".join(text.split())
                
                # Store the extracted text
                self.last_extracted_text = text
                
                # Only speak the extracted text, not the metadata
                if text.strip():
                    # Provide feedback before reading the text
                    self.speak("Here's the text I found:")
                    time.sleep(0.3)  # Short pause before reading content
                    # Only speak the extracted text
                    self.speak(text)
                    
                    # Start generating translations in background
                    self.speak("I'm preparing translations in the background for later use.")
                    self.generate_translations_background(text)
                else:
                    self.speak("I couldn't detect any text in this image. Please try again with clearer text or better lighting.")
                    
            except Exception as e:
                print(f"Error reading text: {str(e)}")
                self.speak("I encountered an error while reading the text. Please try again.")
        
        # Run the image processing in a separate thread to avoid blocking
        process_thread = threading.Thread(target=process_image_thread)
        process_thread.daemon = True
        process_thread.start()
    
    def translate_text(self, target_lang):
        """Translate text with minimal processing"""
        try:
            # Use last extracted text if available
            if not self.last_extracted_text or self.last_extracted_text.strip() == "":
                if not self.last_image_path or not os.path.exists(self.last_image_path):
                    self.speak("No text to translate. Please use the read command first to capture some text.")
                    return
                    
                # Read the text from the last captured image with enhanced processing
                self.speak("Looking for text to translate from the last image.")
                img = cv2.imread(self.last_image_path)
                if img is None:
                    self.speak("Cannot read the saved image for translation.")
                    return
                
                # Use enhanced image processing for better OCR in translation
                processed_img = self.enhance_image(img)
                pil_img = Image.fromarray(processed_img)
                
                # Try multiple OCR configurations if needed
                try:
                    text = pytesseract.image_to_string(pil_img, config=self.ocr_config)
                except Exception as ocr_error:
                    print(f"OCR for translation failed: {ocr_error}")
                    try:
                        text = pytesseract.image_to_string(pil_img, config=self.fallback_ocr_config)
                    except Exception:
                        try:
                            text = pytesseract.image_to_string(pil_img)
                        except Exception:
                            text = ""
                
                self.last_extracted_text = text
                
                # Start background translations for other languages after extracting text
                if text.strip():
                    self.generate_translations_background(text)
            else:
                text = self.last_extracted_text
            
            if not text.strip():
                self.speak("No text detected to translate. Please try reading text first.")
                return
            
            # Provide language-specific feedback
            lang_name = self.supported_languages.get(target_lang, target_lang)
            
            # Check cache first for instant response
            cache_key = f"{text[:5000]}_{target_lang}"
            if cache_key in self.translation_cache:
                translated = self.translation_cache[cache_key]
                self.speak(f"Here's the {lang_name} translation:")
                time.sleep(0.2)  # Brief pause
                self.speak(translated)
                return
            
            # Translation not in cache, generate it now
            self.speak(f"Translation to {lang_name} not ready yet. Translating now, please wait.")
            
            # For short text, don't bother with chunking
            if len(text) < 2000:
                translator = Translator(to_lang=target_lang)
                translated = translator.translate(text)
                self.translation_cache[cache_key] = translated
                self.speak(f"Here's the {lang_name} translation:")
                time.sleep(0.2)  # Brief pause
                self.speak(translated)
                return
            
            # For longer text, use threaded approach
            def translate_in_background():
                translator = Translator(to_lang=target_lang)
                translated = translator.translate(text)
                self.translation_cache[cache_key] = translated
                self.speak("Translation complete:")
                time.sleep(0.2)  # Brief pause
                self.speak(translated)
            
            # Run translation in background
            trans_thread = threading.Thread(target=translate_in_background)
            trans_thread.daemon = True
            trans_thread.start()
            
            # Provide immediate feedback
            self.speak(f"This is a longer text. Starting translation to {lang_name}...")
            
        except Exception as e:
            print(f"Translation error: {str(e)}")
            self.speak("Sorry, I encountered a problem with translation. Please check your internet connection and try again.")
    
    # ADDED: Method to check tesseract installation
    def check_ocr_installation(self):
        """Check if Tesseract OCR is properly installed"""
        try:
            # Try to get tesseract version
            version = pytesseract.get_tesseract_version()
            languages = pytesseract.get_languages()
            print(f"Tesseract version: {version}")
            print(f"Available languages: {languages}")
            return True
        except Exception as e:
            print(f"Tesseract installation issue: {e}")
            return False
    
    def show_help(self):
        """Display available commands"""
        print(self.help_text)
    
    def get_current_date(self):
        """Get current date"""
        self.speak("Today's date is " + time.strftime("%d %B %Y"))
    
    def get_current_time(self):
        """Get current time"""
        self.speak("The time is " + time.strftime("%I:%M %p"))
    
    def get_current_day(self):
        """Get current day of week"""
        self.speak("Today is " + calendar.day_name[datetime.datetime.today().weekday()])
    
    def get_creator(self):
        """Info about creator"""
        self.speak("I was created by Students at Sandip University.")
    
    def execute_command(self, command):
        """Process and execute voice commands with faster response"""
        command = command.lower()
        
        # Handle high-priority commands immediately
        if "read" in command:
            self.read_text()
            return
        
        # Enhanced capture image wake words
        capture_keywords = [
            "capture", "take photo", "take picture", "take a photo", "take a picture",
            "capture image", "capture the image", "image capture"
        ]
        
        # Check if command contains any capture keywords
        if any(keyword in command for keyword in capture_keywords):
            self.capture_image()
            return
            
        if "date" in command:
            self.get_current_date()
            return
            
        if "time" in command:
            self.get_current_time()
            return
        
        # Fast responses for common commands
        if "translate" in command:
            target_lang = "hi"  # Default to Hindi
            if "hindi" in command:
                target_lang = "hi"
            elif "marathi" in command:
                target_lang = "mr"
            
            self.translate_text(target_lang)
            return
        
        # Map commands to functions
        command_map = {
            "day": self.get_current_day,
            "made you": self.get_creator,
            "creator": self.get_creator,
            "help": self.show_help
        }
        
        # Check for command matches
        for cmd, func in command_map.items():
            if cmd in command:
                func()
                return
        
        # Process knowledge queries
        subjects = ["science", "math", "history", "geography", "physics", "chemistry", "biology", "astronomy", "table", "capital", "country", "state", "india"]
        
        is_question = any(word in command for word in ["what", "who", "where", "when", "how", "why"])
        has_subject = any(subject in command for subject in subjects)
        
        if is_question or has_subject or len(command.split()) > 2:
            response = self.search_knowledge_base(command)
            self.speak(response)
            return
            
        # If no specific command recognized
        self.speak("I'm not sure what you're asking. Say 'help' for a list of commands.")
    
    def recognize_speech(self):
        """Optimized speech recognition for faster response"""
        # Stop any ongoing speech first
        self.stop_speaking()
        
        try:
            with sr.Microphone() as source:
                self.speak("I'm listening. Please speak your command.")
                print("Listening...")
                # Faster ambient noise adjustment
                self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
                # Adjust energy threshold for better sensitivity
                self.recognizer.energy_threshold = 300
                self.recognizer.dynamic_energy_threshold = True
                
                # Reduced timeout and phrase time limit for faster response
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                
                self.speak("Processing your command.")
                print("Processing...")
                command = self.recognizer.recognize_google(audio, language="en-US")
                print(f"Recognized: {command}")
                self.execute_command(command)
        except sr.UnknownValueError:
            self.speak("Sorry, I didn't understand that. Please try again.")
        except sr.RequestError:
            self.speak("I'm having trouble connecting to the speech recognition service. Please check your internet connection.")
        except Exception as e:
            print(f"Speech recognition error: {str(e)}")
            self.speak("There was a problem understanding your command. Please try again.")
    
    def button_callback(self, channel):
        """Callback function for button press"""
        # Debounce the button input
        time.sleep(0.05)
        # Check if button is still pressed after debounce
        if RPi.GPIO.input(self.BUTTON_PIN) == 0:  # Button is pressed (LOW)
            print("Button pressed - Command mode activated")
            self.speak("Button pressed. Ready for your command.")
            self.recognize_speech()
    
    def start_button_listener(self):
        """Start GPIO button listener"""
        try:
            # Add event detection for button press (falling edge)
            RPi.GPIO.add_event_detect(self.BUTTON_PIN, RPi.GPIO.FALLING, 
                                     callback=self.button_callback, bouncetime=300)
            self.speak("I'm ready. Press the button when you want to give me a command.")
            print("Button listener started. Press the button to activate command mode.")
        except Exception as e:
            print(f"Error setting up button: {e}")
            self.speak("There was a problem setting up the button interface. Please restart the device.")
    
    def cleanup(self):
        """Clean up resources before exit"""
        self.speak("Shutting down. Goodbye.")
        # Clean up GPIO
        RPi.GPIO.cleanup()
    
    def run(self):
        """Main method to start the assistant"""
        try:
            # Create image directory if it doesn't exist
            if not os.path.exists(self.image_dir):
                os.makedirs(self.image_dir)
            
            # Check Tesseract installation at startup
            self.speak("Starting up. Checking system readiness.")
            ocr_available = self.check_ocr_installation()
            if not ocr_available:
                self.speak("Warning: Text recognition system may not be working properly.")
                print("WARNING: Tesseract OCR installation issues detected. Text reading may not work correctly.")
                print("Consider installing required packages:")
                print("sudo apt-get install tesseract-ocr tesseract-ocr-eng")
            else:
                self.speak("System checks complete.")
                
            self.speak("Smart Assistant ready. Press the button to speak a command.")
            self.start_button_listener()
            
            # Keep the main thread alive
            while self.is_running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.cleanup()
            print("Assistant terminated by user")
        except Exception as e:
            print(f"Critical error: {e}")
            self.speak("A critical error occurred. The system needs to restart.")
            self.cleanup()

# Start the assistant
if __name__ == "__main__":
    try:
        assistant = SmartAssistant()
        assistant.run()
    finally:
        # Make sure we clean up GPIO resources on exit
        RPi.GPIO.cleanup()
