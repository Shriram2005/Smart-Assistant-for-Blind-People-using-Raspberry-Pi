"""
Smart Assistant - OCR and Voice Recognition System for Raspberry Pi

Required dependencies:
pip install opencv-python
pip install pytesseract
pip install pillow
pip install SpeechRecognition
pip install translate
pip install gTTS
pip install pygame
pip install numpy
pip install pyaudio         # For microphone access

IMPORTANT: For offline speech recognition (optional but recommended):
1. First install the system dependencies:
   sudo apt-get update
   sudo apt-get install -y python3-dev libpulse-dev swig

2. Then install PocketSphinx:
   pip install pocketsphinx

If you have trouble with PocketSphinx installation, the assistant will still 
work for wake word detection with an internet connection, but offline recognition
will be disabled.

For Raspberry Pi Camera:
pip install picamera[array]  # If using the Raspberry Pi camera module

For OCR functionality:
sudo apt-get update
sudo apt-get install tesseract-ocr

For better audio recognition on Raspberry Pi:
sudo apt-get install portaudio19-dev
sudo apt-get install libportaudio2
sudo apt-get install python3-pyaudio
sudo apt-get install flac  # For audio encoding

Note: For display capabilities, X server must be running.
If running in headless mode, you may need to disable display functionality.

Troubleshooting:
- If audio devices aren't detected, check connections and run: arecord -l
- For OCR issues, verify tesseract is installed: tesseract --version
- For display issues, ensure X server is running or disable display with: export DISPLAY=:0
"""

import cv2
import pytesseract
import os
import json
import datetime
import threading
import time
import calendar
from PIL import Image
import speech_recognition as sr
from translate import Translator
from gTTS import gTTS
import pygame
from io import BytesIO
import numpy as np
import logging  # Added for error logging
import queue  # For thread-safe queue implementation
import wave  # Added for generating beep sound

# Setup basic logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('SmartAssistant')

class AudioMonitor:
    """Class for continuous audio monitoring and wake word detection."""
    
    def __init__(self, callback_function, wake_words=None):
        """Initialize audio monitoring system.
        
        Args:
            callback_function: Function to call when wake word is detected
            wake_words: List of wake words to listen for
        """
        self.callback = callback_function
        self.wake_words = wake_words or ["hey assistant", "hello assistant", "assistant", "hi assistant", "smart assistant"]
        self.is_listening = False
        self.listen_thread = None
        self.audio_queue = queue.Queue()
        
        # Audio settings optimized for Raspberry Pi
        self.sample_rate = 16000  # Lower sample rate for Raspberry Pi's limited processing power
        self.chunk_size = 1024    # Standard chunk size
        
        # Speech recognition with Raspberry Pi optimized parameters
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300  # Higher threshold for Raspberry Pi microphones
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.dynamic_energy_adjustment_damping = 0.15
        self.recognizer.dynamic_energy_ratio = 1.5
        self.recognizer.pause_threshold = 0.8
        
        # Keep track of last wake word detection time to avoid multiple triggers
        self.last_detection_time = 0
        self.cooldown_period = 2.0  # Increased cooldown period for Raspberry Pi
        
        # Find available microphone devices
        self.available_mics = self.list_microphone_devices()
        self.mic_device_index = self.find_best_microphone()
        
        logger.info(f"Audio monitor initialized with device index {self.mic_device_index}")
    
    def list_microphone_devices(self):
        """List all available microphone devices."""
        try:
            mics = []
            for index, name in enumerate(sr.Microphone.list_microphone_names()):
                mics.append((index, name))
                logger.info(f"Microphone {index}: {name}")
            return mics
        except Exception as e:
            logger.error(f"Error listing microphones: {e}")
            return []
    
    def find_best_microphone(self):
        """Find the best microphone for Raspberry Pi."""
        # First try to find USB microphones which usually work better
        for idx, name in self.available_mics:
            if "usb" in name.lower() or "headset" in name.lower() or "external" in name.lower():
                logger.info(f"Selected external microphone: {name}")
                return idx
        
        # If no USB mic found, use default device (index None)
        logger.info("No external microphone found, using default device")
        return None
    
    def start_listening(self):
        """Start the continuous listening process in a background thread."""
        if self.is_listening:
            logger.info("Already listening")
            return
            
        self.is_listening = True
        self.listen_thread = threading.Thread(target=self._listen_loop)
        self.listen_thread.daemon = True
        self.listen_thread.start()
        logger.info("Started continuous listening for wake words")
    
    def stop_listening(self):
        """Stop the continuous listening process."""
        self.is_listening = False
        if self.listen_thread:
            self.listen_thread.join(timeout=2.0)
            self.listen_thread = None
        logger.info("Stopped continuous listening")
    
    def _listen_loop(self):
        """Main listening loop that continuously monitors for wake words."""
        try:
            # Use SpeechRecognition for wake word detection
            with sr.Microphone(device_index=self.mic_device_index, sample_rate=self.sample_rate) as source:
                logger.info(f"Wake word detection activated with device index {self.mic_device_index}")
                
                # Initial ambient noise adjustment
                logger.info("Adjusting for ambient noise... Please wait.")
                self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
                logger.info(f"Ambient noise level set to {self.recognizer.energy_threshold}")
                
                # Check if Sphinx is available for offline recognition
                sphinx_available = False
                try:
                    import pocketsphinx
                    sphinx_available = True
                    logger.info("PocketSphinx found - offline recognition available")
                except ImportError:
                    logger.warning("PocketSphinx not found - offline recognition unavailable")
                    print("NOTE: For offline recognition, install pocketsphinx: pip install pocketsphinx")
                
                retry_count = 0
                max_retries = 3
                backoff_time = 1.0
                
                while self.is_listening:
                    try:
                        # Listen for phrases that might contain wake words
                        logger.info("Listening for wake words...")
                        audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                        
                        # Reset retry counter on successful listen
                        retry_count = 0
                        
                        try:
                            # Try with Google's speech recognition first
                            text = None
                            try:
                                text = self.recognizer.recognize_google(audio, language="en-US").lower()
                            except sr.UnknownValueError:
                                # If Google fails, try with Sphinx (offline recognition) if available
                                if sphinx_available:
                                    try:
                                        text = self.recognizer.recognize_sphinx(audio).lower()
                                        logger.info("Using offline recognition (Sphinx)")
                                    except Exception as sphinx_error:
                                        logger.debug(f"Sphinx recognition failed: {sphinx_error}")
                            except sr.RequestError:
                                # If there's a network error, try Sphinx if available
                                if sphinx_available:
                                    try:
                                        text = self.recognizer.recognize_sphinx(audio).lower()
                                        logger.info("Using offline recognition (Sphinx) after network error")
                                    except Exception as sphinx_error:
                                        logger.debug(f"Sphinx recognition failed: {sphinx_error}")
                            
                            if text:
                                logger.info(f"Heard: {text}")
                                
                                # Enhanced wake word detection with partial matching
                                for wake_word in self.wake_words:
                                    # Check for exact match or if the wake word is part of the text
                                    if wake_word in text or any(part in text for part in wake_word.split()):
                                        current_time = time.time()
                                        if current_time - self.last_detection_time > self.cooldown_period:
                                            logger.info(f"Wake word detected: '{wake_word}' in '{text}'")
                                            self.last_detection_time = current_time
                                            # Call the callback function
                                            self.callback()
                                        break
                                        
                        except sr.RequestError as e:
                            logger.error(f"Could not request results; {e}")
                            # Don't increment retry counter for network errors
                            time.sleep(1)  # Brief pause before retrying
                            
                    except Exception as listen_error:
                        logger.error(f"Error in listening loop: {listen_error}")
                        retry_count += 1
                        
                        # Implement exponential backoff if errors persist
                        if retry_count > max_retries:
                            retry_time = backoff_time * (2 ** (retry_count - max_retries))
                            retry_time = min(retry_time, 30)  # Cap at 30 seconds
                            logger.warning(f"Too many errors. Backing off for {retry_time} seconds")
                            time.sleep(retry_time)
                            
                            # Re-adjust for ambient noise after errors
                            try:
                                logger.info("Re-adjusting for ambient noise...")
                                self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
                                logger.info(f"New ambient noise level: {self.recognizer.energy_threshold}")
                            except Exception as adjust_error:
                                logger.error(f"Failed to readjust: {adjust_error}")
                        else:
                            time.sleep(0.5)  # Brief pause before retrying
        
        except Exception as e:
            logger.error(f"Critical error in listen loop: {e}")
            if self.is_listening:  # Try to restart if still supposed to be listening
                time.sleep(2)
                self._listen_loop()

class SmartAssistant:
    def __init__(self):
        # Initialize components
        self.recognizer = sr.Recognizer()
        
        # Add Raspberry Pi specific configuration
        # Check if running on Raspberry Pi
        self.is_raspberry_pi = self.check_if_raspberry_pi()
        if self.is_raspberry_pi:
            logger.info("Running on Raspberry Pi - using optimized settings")
            
        # Setup camera with Raspberry Pi awareness
        self.setup_camera()
        
        self.knowledge_data = self.load_knowledge()
        
        # Setup image directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.image_dir = os.path.join(script_dir, "Saved Images")
        os.makedirs(self.image_dir, exist_ok=True)
        self.last_image_path = ""
        self.last_extracted_text = ""
        
        # Globals
        self.is_running = True
        self.is_speaking = False
        self.is_processing_command = False  # Flag to prevent multiple command processing
        
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
        
        # Initialize the audio monitor for wake word detection
        self.audio_monitor = AudioMonitor(self.on_wake_word_detected)
        
        # Warm up the camera (reduces initial delay)
        self.warmup_camera()
        
        # Help text
        self.help_text = """
        Smart Assistant Commands:
        - Say "Hey Assistant" or "Hello Assistant" to wake me up
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
    
    def check_if_raspberry_pi(self):
        """Check if the code is running on Raspberry Pi"""
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                return 'Raspberry Pi' in model
        except:
            try:
                # Alternative check
                import platform
                return platform.machine().startswith('arm')
            except:
                return False
    
    def load_knowledge(self):
        """Load knowledge base from JSON file using path relative to script"""
        try:
            # Get the directory of the current script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            knowledge_path = os.path.join(script_dir, "knowledge_data.json")
            
            with open(knowledge_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print("Knowledge data file not found. Creating empty knowledge base.")
            return {}
        except json.JSONDecodeError:
            print("Error parsing knowledge data. Creating empty knowledge base.")
            return {}
    
    def setup_camera(self):
        """Initialize camera using appropriate camera for the platform"""
        try:
            if self.is_raspberry_pi:
                logger.info("Setting up camera for Raspberry Pi")
                
                # Try to import picamera and the PiRGBArray
                try:
                    import picamera
                    import picamera.array
                    self.has_picamera = True
                    logger.info("PiCamera module found - using native Raspberry Pi camera")
                    
                    # Initialize the PiCamera
                    try:
                        # Set up PiCamera with appropriate resolution for OCR
                        self.pi_camera = picamera.PiCamera()
                        self.pi_camera.resolution = (1280, 720)
                        self.pi_camera.framerate = 30
                        # Allow time for the camera to warm up
                        time.sleep(2)
                        logger.info("PiCamera initialized successfully")
                        return True
                    except Exception as picam_error:
                        logger.error(f"Failed to initialize PiCamera: {picam_error}")
                        self.has_picamera = False
                except ImportError:
                    logger.info("PiCamera module not found - will use standard OpenCV camera")
                    self.has_picamera = False
            else:
                self.has_picamera = False
                logger.info("Not on Raspberry Pi - using standard webcam")
            
            # Fallback to OpenCV's VideoCapture for webcam
            device_indices = [0, 1, 2]  # Try these camera indices
            
            for idx in device_indices:
                logger.info(f"Trying camera index {idx}")
                camera = cv2.VideoCapture(idx)
                if camera.isOpened():
                    # Found a working camera
                    self.camera = camera
                    # Set camera properties for better quality
                    self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    # Try to set autofocus if available
                    try:
                        self.camera.set(cv2.CAP_PROP_AUTOFOCUS, 1)
                    except:
                        pass
                    
                    logger.info(f"Camera initialized successfully using index {idx}")
                    return True
                else:
                    # Close the camera and try next index
                    camera.release()
            
            # If we reach here, no camera was found
            logger.error("No working camera found")
            print("Error: Could not find a working camera")
            return False
                
        except Exception as e:
            print(f"Camera setup error: {e}")
            logger.error(f"Camera setup error: {e}")
            return False
    
    def warmup_camera(self):
        """Pre-initialize camera to reduce startup delay when reading"""
        try:
            # For laptop implementation, just briefly open and close the camera
            if not hasattr(self, 'camera'):
                self.setup_camera()
                
            ret, _ = self.camera.read()
            if not ret:
                logger.warning("Camera warmup failed")
            else:
                logger.info("Camera pre-initialized")
        except Exception as e:
            logger.error(f"Camera warmup error: {e}")
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
        """Capture an image using the appropriate camera for the platform"""
        self.speak("Taking a photo. Please hold steady.")
        
        try:
            # Check if we're using Raspberry Pi camera
            if hasattr(self, 'has_picamera') and self.has_picamera and hasattr(self, 'pi_camera'):
                logger.info("Capturing image with PiCamera")
                
                # Import PiCamera modules if not already imported
                import picamera
                import picamera.array
                
                # Generate unique filename with timestamp
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"capture_{timestamp}.jpg"
                self.last_image_path = os.path.join(self.image_dir, filename)
                
                # Capture directly to file with PiCamera
                self.pi_camera.capture(self.last_image_path)
                logger.info(f"PiCamera image saved to {self.last_image_path}")
                
                # Read the saved image for display
                frame = cv2.imread(self.last_image_path)
                if frame is None:
                    raise Exception("Failed to read captured image")
            else:
                # Use OpenCV camera capture
                logger.info("Capturing image with OpenCV camera")
                
                # Make sure camera is initialized
                if not hasattr(self, 'camera') or not self.camera.isOpened():
                    self.setup_camera()
                    
                # Warmup - capture a few frames to adjust auto exposure
                for _ in range(5):
                    ret, _ = self.camera.read()
                    if not ret:
                        self.speak("Camera not responding. Please check your camera connection.")
                        return None
                    time.sleep(0.1)
                
                # Capture the actual image
                ret, frame = self.camera.read()
                if not ret or frame is None:
                    self.speak("Failed to capture an image.")
                    return None
                
                # Generate unique filename with timestamp
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"capture_{timestamp}.jpg"
                self.last_image_path = os.path.join(self.image_dir, filename)
                
                # Save the image
                cv2.imwrite(self.last_image_path, frame)
                logger.info(f"OpenCV image saved to {self.last_image_path}")
            
            # Add timestamp to the displayed image
            display_frame = frame.copy()
            timestamp_text = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(display_frame, timestamp_text, (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Display the image
            try:
                cv2.namedWindow("Captured Image", cv2.WINDOW_NORMAL)
                cv2.resizeWindow("Captured Image", 800, 480)
                cv2.imshow("Captured Image", display_frame)
                
                # Keep image displayed for 5 seconds or until a key is pressed
                self.speak("Image captured. The image will close automatically in a few seconds, or press any key to close it now.")
                
                # Use a separate thread to wait for key press or timeout
                def close_image_after_timeout():
                    start_time = time.time()
                    while time.time() - start_time < 5:  # 5 seconds timeout
                        if cv2.waitKey(100) != -1:  # Check for key press every 100ms
                            break
                    try:
                        cv2.destroyWindow("Captured Image")
                    except:
                        pass
                
                close_thread = threading.Thread(target=close_image_after_timeout)
                close_thread.daemon = True
                close_thread.start()
            except Exception as display_error:
                logger.error(f"Error displaying image: {display_error}")
                self.speak("Image captured and saved, but couldn't display it on screen.")
            
            return self.last_image_path
            
        except Exception as e:
            print(f"Image capture error: {str(e)}")
            logger.error(f"Image capture error: {str(e)}")
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
    
    def play_activation_sound(self):
        """Play a short sound to indicate that the assistant is listening."""
        try:
            # Generate a simple beep using pygame
            pygame.mixer.Sound(self.generate_beep()).play()
        except Exception as e:
            logger.error(f"Error playing activation sound: {e}")
    
    def generate_beep(self, frequency=1000, duration=0.2):
        """Generate a short beep sound."""
        # Sample rate in Hz
        sample_rate = 44100
        
        # Generate time array
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        
        # Generate sine wave
        tone = np.sin(frequency * 2 * np.pi * t)
        
        # Normalize to 16-bit range
        tone = np.int16(tone * 32767)
        
        # Convert to bytes
        buffer = tone.tobytes()
        
        # Create in-memory file object
        buffer_io = BytesIO()
        
        # Write WAV file to memory
        with wave.open(buffer_io, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(buffer)
        
        buffer_io.seek(0)
        return buffer_io
    
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
        """Enhanced speech recognition with increased listening time and improved accuracy"""
        # Stop any ongoing speech first
        self.stop_speaking()
        
        try:
            # Use the same microphone device index that was found during initialization
            with sr.Microphone(device_index=self.audio_monitor.mic_device_index, sample_rate=16000) as source:
                self.speak("I'm listening. Please speak your command.")
                print("Listening for up to 10 seconds...")
                
                # More thorough ambient noise adjustment for Raspberry Pi
                self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
                print(f"Energy threshold set to {self.recognizer.energy_threshold}")
                
                # Enhanced recognition parameters optimized for Raspberry Pi
                self.recognizer.energy_threshold = 300  # Better for Raspberry Pi microphones
                self.recognizer.dynamic_energy_threshold = True
                self.recognizer.dynamic_energy_adjustment_damping = 0.15
                self.recognizer.dynamic_energy_ratio = 1.5
                self.recognizer.pause_threshold = 0.8
                
                # Wait for the TTS to complete before starting to listen
                # This ensures we don't start listening while the assistant is still speaking
                while pygame.mixer.music.get_busy() and self.is_speaking:
                    time.sleep(0.1)
                
                # Add a short pause to make sure the user has time to start speaking
                time.sleep(0.5)
                
                print("Now listening for your command...")
                
                # Reduced timeout for better responsiveness on Raspberry Pi
                # timeout: how long to wait for speech to start (8 seconds)
                # phrase_time_limit: maximum length of a phrase (10 seconds)
                try:
                    audio = self.recognizer.listen(source, timeout=8, phrase_time_limit=10)
                    print("Audio captured, processing...")
                    
                    # Only say "Processing your command" if we actually captured audio
                    self.speak("Processing your command.")
                    print("Processing speech...")
                    
                    # Try recognition with error handling suitable for Raspberry Pi
                    command = None
                    
                    # First try Google's online recognition
                    try:
                        command = self.recognizer.recognize_google(audio, language="en-US")
                        print(f"Recognized with Google: {command}")
                    except sr.UnknownValueError:
                        print("Google recognition failed - speech not understood")
                        # Try Sphinx (offline recognition) as fallback only if available
                        try:
                            # Check if pocketsphinx is installed
                            import pocketsphinx
                            command = self.recognizer.recognize_sphinx(audio)
                            print(f"Recognized with Sphinx (offline): {command}")
                        except ImportError:
                            print("PocketSphinx not installed - skipping offline recognition")
                        except Exception as sphinx_error:
                            print(f"Sphinx recognition failed: {sphinx_error}")
                    except sr.RequestError as req_error:
                        print(f"Google recognition request failed: {req_error}")
                        # Try Sphinx (offline recognition) as fallback only if available
                        try:
                            # Check if pocketsphinx is installed
                            import pocketsphinx
                            command = self.recognizer.recognize_sphinx(audio)
                            print(f"Recognized with Sphinx (offline): {command}")
                        except ImportError:
                            print("PocketSphinx not installed - skipping offline recognition")
                        except Exception as sphinx_error:
                            print(f"Sphinx recognition failed: {sphinx_error}")
                    
                    if command:
                        print(f"Final recognized command: {command}")
                        self.execute_command(command)
                    else:
                        self.speak("I didn't understand that. Please try again.")
                
                except sr.WaitTimeoutError:
                    print("No speech detected within timeout period")
                    self.speak("I didn't hear anything. Please try again when you're ready to speak.")
                
        except sr.UnknownValueError:
            self.speak("Sorry, I didn't understand that. Please try speaking more clearly.")
        except sr.RequestError:
            self.speak("I'm having trouble with the speech recognition service. Please check your internet connection.")
        except Exception as e:
            print(f"Speech recognition error: {str(e)}")
            logger.error(f"Speech recognition error: {str(e)}")
            self.speak("There was a problem understanding your command. Please try again.")
    
    def cleanup(self):
        """Clean up resources before exit"""
        self.speak("Shutting down. Goodbye.")
    
    def on_wake_word_detected(self):
        """Callback function when wake word is detected."""
        # Avoid processing multiple commands at once
        if self.is_processing_command:
            logger.info("Already processing a command, ignoring wake word")
            return
        
        self.is_processing_command = True
        
        try:
            # Visual feedback that wake word was detected
            print("\n\n[WAKE WORD DETECTED] - Listening for command...")
            
            # Stop any ongoing speech
            self.stop_speaking()
            
            # Play a short sound to indicate wake word detection
            self.play_activation_sound()
            
            # Start listening for the actual command
            self.recognize_speech()
        finally:
            self.is_processing_command = False
    
    def run(self):
        """Main method to start the assistant"""
        try:
            # Create image directory if it doesn't exist
            script_dir = os.path.dirname(os.path.abspath(__file__))
            self.image_dir = os.path.join(script_dir, "Saved Images")
            if not os.path.exists(self.image_dir):
                os.makedirs(self.image_dir)
            
            # Initialize with Raspberry Pi specific checks
            self.speak("Starting up. Checking system readiness.")
            
            # Check audio devices first
            self.check_audio_devices()
            
            # Check Tesseract installation
            ocr_available = self.check_ocr_installation()
            if not ocr_available:
                self.speak("Warning: Text recognition system may not be working properly.")
                print("WARNING: Tesseract OCR installation issues detected. Text reading may not work correctly.")
                print("Make sure Tesseract OCR is properly installed.")
            else:
                self.speak("OCR system check complete.")
            
            # Initial welcome and instructions for the user
            welcome_message = (
                "Smart Assistant is ready and listening for wake words. "
                "Say 'Hey Assistant' or 'Hello Assistant' to activate me. "
                "Then you can give commands like 'capture', 'read', or 'help'."
            )
            self.speak(welcome_message)
            print("\n" + "-"*80)
            print("SMART ASSISTANT IS LISTENING")
            print("Say 'Hey Assistant' or 'Hello Assistant' to activate")
            print("-"*80 + "\n")
            
            # Start audio monitoring for wake words
            self.audio_monitor.start_listening()
            
            # Keep the main thread alive
            while self.is_running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.cleanup()
            print("Assistant terminated by user")
        except Exception as e:
            print(f"Critical error: {e}")
            logger.error(f"Critical error: {e}")
            self.speak("A critical error occurred. The system needs to restart.")
            self.cleanup()
        finally:
            # Clean up resources
            if hasattr(self, 'audio_monitor'):
                self.audio_monitor.stop_listening()
                
            if hasattr(self, 'camera') and self.camera is not None:
                self.camera.release()
                
            if hasattr(self, 'pi_camera') and self.has_picamera:
                self.pi_camera.close()
    
    def check_audio_devices(self):
        """Check available audio devices and troubleshoot if necessary"""
        try:
            print("\nChecking audio devices:")
            devices = sr.Microphone.list_microphone_names()
            
            if not devices:
                print("WARNING: No microphone devices found!")
                self.speak("No microphone devices found. Please check your microphone connection.")
                return False
            
            print(f"Found {len(devices)} microphone devices:")
            for i, device in enumerate(devices):
                print(f"  {i}: {device}")
            
            # Test microphone with brief recording to verify it works
            print("\nTesting microphone...")
            try:
                with sr.Microphone(device_index=self.audio_monitor.mic_device_index, sample_rate=16000) as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
                    print(f"Microphone test successful. Energy threshold: {self.recognizer.energy_threshold}")
                    self.speak("Microphone check successful.")
                    return True
            except Exception as e:
                print(f"Microphone test failed: {e}")
                self.speak("Microphone test failed. Voice commands may not work properly.")
                return False
                
        except Exception as e:
            print(f"Error checking audio devices: {e}")
            self.speak("Warning: Could not check audio devices.")
            return False

# Start the assistant
if __name__ == "__main__":
    try:
        # Check for essential dependencies before starting
        def check_dependencies():
            missing_dependencies = []
            
            # Check for essential Python packages
            try:
                import cv2
                print("✓ OpenCV installed")
            except ImportError:
                missing_dependencies.append("opencv-python")
                print("✗ OpenCV missing")
            
            try:
                import pytesseract
                print("✓ PyTesseract installed")
            except ImportError:
                missing_dependencies.append("pytesseract")
                print("✗ PyTesseract missing")
            
            try:
                import speech_recognition
                print("✓ SpeechRecognition installed")
            except ImportError:
                missing_dependencies.append("SpeechRecognition")
                print("✗ SpeechRecognition missing")
            
            try:
                import pygame
                print("✓ PyGame installed")
            except ImportError:
                missing_dependencies.append("pygame")
                print("✗ PyGame missing")
                
            # Check for Tesseract executable
            try:
                pytesseract.get_tesseract_version()
                print("✓ Tesseract OCR executable found")
            except:
                print("✗ Tesseract OCR executable not found or not in PATH")
                print("  Install with: sudo apt-get install tesseract-ocr")
            
            # Check for PocketSphinx (optional)
            try:
                import pocketsphinx
                print("✓ PocketSphinx installed (offline recognition available)")
            except ImportError:
                print("! PocketSphinx not installed (offline recognition unavailable)")
                print("  This is optional but recommended for wake word detection without internet")
                print("  Install with: pip install pocketsphinx")
            
            # Check for PyAudio (essential for microphone)
            try:
                import pyaudio
                print("✓ PyAudio installed")
            except ImportError:
                missing_dependencies.append("pyaudio")
                print("✗ PyAudio missing - microphone functionality will not work")
                print("  Install with: pip install pyaudio")
                print("  On Raspberry Pi you may need: sudo apt-get install python3-pyaudio")
            
            # If missing essential dependencies, provide installation instructions
            if missing_dependencies:
                print("\nMissing essential dependencies. Please install them with:")
                print(f"pip install {' '.join(missing_dependencies)}")
                choice = input("\nDo you want to continue anyway? (y/n): ").strip().lower()
                return choice == 'y'
            
            return True
        
        # Run dependency check
        if check_dependencies():
            print("\nStarting Smart Assistant...\n")
            assistant = SmartAssistant()
            assistant.run()
        else:
            print("\nExiting due to missing dependencies.\n")
    except KeyboardInterrupt:
        print("\nAssistant terminated by user.")
    except Exception as e:
        print(f"\nCritical error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Exiting...")
