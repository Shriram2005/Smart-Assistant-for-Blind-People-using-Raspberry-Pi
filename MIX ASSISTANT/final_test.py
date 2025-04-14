import cv2
import pytesseract
import os
import json
import datetime
import threading
import time
import calendar
from pynput import keyboard
from PIL import Image
from picamera2 import Picamera2
import speech_recognition as sr
from translate import Translator
from gtts import gTTS
import pygame
from io import BytesIO
import numpy as np

class SmartAssistant:
    def __init__(self):
        # Initialize components
        self.recognizer = sr.Recognizer()
        self.setup_camera()
        self.knowledge_data = self.load_knowledge()
        
        # Setup image directory
        self.image_dir = "/home/dsmansi/Final Assistant/Saved Images"
        os.makedirs(self.image_dir, exist_ok=True)
        self.last_image_path = ""
        self.last_extracted_text = ""
        
        # Globals
        self.camera_on = False
        self.camera_thread = None
        self.listener_thread = None
        self.is_running = True
        self.is_speaking = False
        
        # Initialize pygame for audio playback
        pygame.mixer.init()
        
        # MODIFIED: Changed OCR config to use LSTM engine instead of legacy engine
        # Using --oem 1 (LSTM only) or --oem 3 (auto) instead of --oem 0 (legacy)
        self.ocr_config = r'--oem 1 --psm 3 -l eng'
        
        # ADDED: Fallback OCR config with minimal options
        self.fallback_ocr_config = r'--psm 3'
        
        # Initialize translation cache
        self.translation_cache = {}
        
        # Warm up the camera (reduces initial delay)
        self.warmup_camera()
        
        # Help text
        self.help_text = """
        Smart Assistant Commands:
        - "show camera": Start camera live feed
        - "close camera": Stop camera feed
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
            with open("/home/dsmansi/Final Assistant/knowledge_data.json", "r") as f:
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
        query = query.lower()
        
        # Quick responses for date/time
        if "date" in query:
            return "Today's date is " + time.strftime("%d %B %Y")
            
        if "time" in query:
            return "The time is " + time.strftime("%I:%M %p")
            
        if "day" in query:
            return "Today is " + calendar.day_name[datetime.datetime.today().weekday()]
            
        # Knowledge base search
        # Check for state capital questions
        if ("capital" in query and "india" in query) or ("capital of" in query):
            state_match = None
            for state in self.knowledge_data.get("geography", {}).get("india states and capitals", {}):
                if state.lower() in query:
                    state_match = state
                    break
                    
            if state_match:
                capital = self.knowledge_data["geography"]["india states and capitals"][state_match]["capital"]
                return f"The capital of {state_match} is {capital}."
                
        # Check for table questions
        if "table" in query:
            for i in range(2, 11):
                if str(i) in query:
                    table_key = f"table_{i}"
                    if table_key in self.knowledge_data.get("math", {}).get("tables", {}):
                        return f"Here's the table of {i}: {self.knowledge_data['math']['tables'][table_key]}"
        
        # Search through all categories
        for category in self.knowledge_data:
            category_data = self.knowledge_data[category]
            
            # Direct matches
            for key in category_data:
                if isinstance(category_data[key], str) and key in query:
                    return category_data[key]
                    
            # Nested objects (for detailed topics)
            for key in category_data:
                if isinstance(category_data[key], dict):
                    for subkey in category_data[key]:
                        if subkey in query:
                            # Check if the value is a string or another dict
                            if isinstance(category_data[key][subkey], str):
                                return category_data[key][subkey]
                            elif isinstance(category_data[key][subkey], dict):
                                # For things like state descriptions
                                if "description" in category_data[key][subkey]:
                                    return f"{subkey}: {category_data[key][subkey]['description']}"
        
        return "I don't have information about that. Please ask something related to science, math, history, or geography."
    
    def show_camera(self):
        """Start camera feed in a separate thread"""
        if self.camera_on:
            self.speak("Camera is already running.")
            return
        
        self.camera_on = True
        
        def camera_feed():
            try:
                self.picam2.start()
                while self.camera_on:
                    frame = self.picam2.capture_array()
                    # Add timestamp to frame
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cv2.putText(frame, timestamp, (10, 30), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
                    # Create a smaller window that fits on screen
                    cv2.namedWindow("Pi Camera Feed", cv2.WINDOW_NORMAL)
                    cv2.resizeWindow("Pi Camera Feed", 800, 480)
                    cv2.imshow("Pi Camera Feed", frame)
                    
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                
                self.picam2.stop()
                cv2.destroyAllWindows()
            except Exception as e:
                print(f"Camera error: {e}")
                self.camera_on = False
        
        self.camera_thread = threading.Thread(target=camera_feed)
        self.camera_thread.daemon = True
        self.camera_thread.start()
        self.speak("Camera started.")
    
    def close_camera(self):
        """Stop camera feed"""
        if self.camera_on:
            self.camera_on = False
            # Give time for thread to close properly
            time.sleep(0.3)  # Reduced from 0.5 to 0.3 for faster response
            self.speak("Camera closed.")
        else:
            self.speak("Camera is not running.")
    
    def fast_preprocess_image(self, image):
        """Simplified image preprocessing optimized for speed"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Simple binary thresholding (much faster than adaptive)
        _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        
        # Skip complex filtering to save time
        return binary
    
    def read_text(self):
        """Fast image capture and OCR function with threading"""
        # Immediately tell the user we're processing to provide feedback
        print("Reading text...")
        
        # Start processing in a separate thread to keep the UI responsive
        def process_image_thread():
            try:
                # Start camera with minimal delay
                was_camera_on = self.camera_on
                if not was_camera_on:
                    self.picam2.start()
                    # Reduced warm-up time
                    time.sleep(0.5)
                
                # Capture frame
                frame = self.picam2.capture_array()
                
                # Generate unique filename with timestamp
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"capture_{timestamp}.jpg"
                self.last_image_path = os.path.join(self.image_dir, filename)
                
                # Save image in background to avoid blocking
                def save_image():
                    cv2.imwrite(self.last_image_path, frame)
                    print(f"Image saved to {self.last_image_path}")
                
                save_thread = threading.Thread(target=save_image)
                save_thread.daemon = True
                save_thread.start()
                
                # Stop camera if it wasn't running before
                if not was_camera_on:
                    self.picam2.stop()
                
                # Use the fastest preprocessing option
                processed_frame = self.fast_preprocess_image(frame)
                
                # Use PIL for OCR (required by pytesseract)
                pil_img = Image.fromarray(processed_frame)
                
                # MODIFIED: Added try-except with fallback OCR config
                try:
                    # First try with primary OCR configuration
                    text = pytesseract.image_to_string(pil_img, config=self.ocr_config)
                except Exception as ocr_error:
                    print(f"Primary OCR failed: {ocr_error}")
                    print("Trying fallback OCR configuration...")
                    try:
                        # Try with fallback configuration
                        text = pytesseract.image_to_string(pil_img, config=self.fallback_ocr_config)
                    except Exception as fallback_error:
                        print(f"Fallback OCR also failed: {fallback_error}")
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
                    # Only speak the extracted text
                    self.speak(text)
                else:
                    self.speak("No text detected.")
                    
            except Exception as e:
                print(f"Error reading text: {str(e)}")
                self.speak("Error reading text. Please make sure Tesseract OCR is properly installed.")
        
        # Run the image processing in a separate thread to avoid blocking
        process_thread = threading.Thread(target=process_image_thread)
        process_thread.daemon = True
        process_thread.start()
    
    def translate_text(self, target_lang):
        """Faster translation with minimal processing"""
        try:
            # Use last extracted text if available
            if not self.last_extracted_text or self.last_extracted_text.strip() == "":
                if not self.last_image_path or not os.path.exists(self.last_image_path):
                    self.speak("No text to translate. Please use the read command first.")
                    return
                    
                # Read the text from the last captured image with minimal processing
                img = Image.open(self.last_image_path).convert('L')  # Grayscale conversion only
                
                # MODIFIED: Added try-except with fallback OCR for translation
                try:
                    text = pytesseract.image_to_string(img, config=self.ocr_config)
                except Exception as ocr_error:
                    print(f"OCR for translation failed: {ocr_error}")
                    try:
                        text = pytesseract.image_to_string(img, config=self.fallback_ocr_config)
                    except Exception:
                        try:
                            text = pytesseract.image_to_string(img)
                        except Exception:
                            text = ""
                
                self.last_extracted_text = text
            else:
                text = self.last_extracted_text
            
            if not text.strip():
                self.speak("No text detected to translate.")
                return
            
            # Check cache first for instant response
            cache_key = f"{text[:50]}_{target_lang}"
            if cache_key in self.translation_cache:
                translated = self.translation_cache[cache_key]
                self.speak(translated)
                return
            
            # For short text, don't bother with chunking
            if len(text) < 500:
                translator = Translator(to_lang=target_lang)
                translated = translator.translate(text)
                self.translation_cache[cache_key] = translated
                self.speak(translated)
                return
            
            # For longer text, use threaded approach
            # Start translation in a separate thread
            def translate_in_background():
                translator = Translator(to_lang=target_lang)
                translated = translator.translate(text)
                self.translation_cache[cache_key] = translated
                self.speak(translated)
            
            # Run translation in background
            trans_thread = threading.Thread(target=translate_in_background)
            trans_thread.daemon = True
            trans_thread.start()
            
            # Provide immediate feedback
            self.speak("Starting translation...")
            
        except Exception as e:
            print(f"Translation error: {str(e)}")
            self.speak("Translation error.")
    
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
        self.speak("I was created by D.S. Mansi at Sandip University.")
    
    def execute_command(self, command):
        """Process and execute voice commands with faster response"""
        command = command.lower()
        
        # Handle high-priority commands immediately
        if "read" in command:
            self.read_text()
            return
            
        if "date" in command:
            self.get_current_date()
            return
            
        if "time" in command:
            self.get_current_time()
            return
        
        # Fast responses for common commands
        if "translate" in command:
            if "hindi" in command:
                self.translate_text("hi")
            elif "marathi" in command:
                self.translate_text("mr")
            else:
                # Default to Hindi
                self.translate_text("hi")
            return
        
        # Map commands to functions
        command_map = {
            "camera": self.show_camera,
            "close camera": self.close_camera,
            "stop camera": self.close_camera,
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
        subjects = ["science", "math", "history", "geography", "physics", "chemistry", "biology", 
                   "astronomy", "table", "capital", "country", "state", "india"]
        
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
                print("Listening...")
                # Faster ambient noise adjustment
                self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
                # Adjust energy threshold for better sensitivity
                self.recognizer.energy_threshold = 300
                self.recognizer.dynamic_energy_threshold = True
                
                # Reduced timeout and phrase time limit for faster response
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                
                print("Processing...")
                command = self.recognizer.recognize_google(audio, language="en-US")
                print(f"Recognized: {command}")
                self.execute_command(command)
        except sr.UnknownValueError:
            print("Sorry, I didn't catch that.")
        except sr.RequestError:
            print("Sorry, I'm having trouble with the speech recognition service.")
        except Exception as e:
            print(f"Speech recognition error: {str(e)}")
    
    def on_press(self, key):
        """Handle keyboard press events - respond to 's' key and ESC"""
        try:
            if hasattr(key, 'char') and key.char == 's':
                print("Command mode activated")
                self.recognize_speech()
            elif key == keyboard.Key.esc:
                print("Exiting...")
                self.is_running = False
                return False
        except AttributeError:
            pass
    
    def start_listener(self):
        """Start keyboard listener thread"""
        listener = keyboard.Listener(on_press=self.on_press)
        self.listener_thread = threading.Thread(target=listener.start)
        self.listener_thread.daemon = True
        self.listener_thread.start()
    
    def cleanup(self):
        """Clean up resources before exit"""
        if self.camera_on:
            self.close_camera()
    
    def run(self):
        """Main method to start the assistant"""
        try:
            # Create image directory if it doesn't exist
            if not os.path.exists(self.image_dir):
                os.makedirs(self.image_dir)
            
            # ADDED: Check Tesseract installation at startup
            ocr_available = self.check_ocr_installation()
            if not ocr_available:
                print("WARNING: Tesseract OCR installation issues detected. Text reading may not work correctly.")
                print("Consider installing required packages:")
                print("sudo apt-get install tesseract-ocr tesseract-ocr-eng")
                
            self.speak("Assistant ready. Press 's' to speak a command.")
            self.start_listener()
            
            # Keep the main thread alive
            while self.is_running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.cleanup()
            print("Assistant terminated by user")
        except Exception as e:
            print(f"Critical error: {e}")
            self.cleanup()

# Start the assistant
if __name__ == "__main__":
    assistant = SmartAssistant()
    assistant.run()
