import cv2
import pytesseract
import os
import json
import datetime
import sqlite3
import threading
import time
import calendar
from pynput import keyboard
from PIL import Image
from picamera2 import Picamera2
import speech_recognition as sr
from io import BytesIO
import pygame
import numpy as np
import requests

class SmartAssistant:
    def __init__(self):
        # Initialize components
        self.recognizer = sr.Recognizer()
        self.conn = self.setup_database()
        self.knowledge_data = self.load_knowledge()
        self.setup_camera()
        
        # Globals
        self.camera_on = False
        self.camera_thread = None
        self.listener_thread = None
        self.is_running = True
        self.is_speaking = False  # Flag to track TTS status
        self.last_captured_text = ""  # Store last captured text
        
        # Initialize pygame for audio playback
        pygame.mixer.init()
        
        # Load OCR models
        self.setup_ocr_models()
        
        # Load translation models
        self.setup_translation_models()
        
        # Help text
        self.help_text = """
        I can do the following tasks:
        - "show camera": Start camera live feed
        - "close camera": Stop camera feed
        - "read": Capture image and read text
        - "translate": Translate recently captured text to Hindi
        - "recent data": Show recent data from memory
        - "current date": Tell today's date
        - "current time": Tell current time
        - "what day is it": Tell current day
        - "who made you": Tell about the creator
        - "help": List all commands
        - You can also ask general questions about science, math, history, and geography
        """
    
    def setup_ocr_models(self):
        """Setup optimized OCR models for Raspberry Pi"""
        print("Loading OCR models... This may take a moment.")
        
        # Setup pytesseract with basic configuration
        self.tesseract_config = r'--oem 1 --psm 6 -l eng+hin'
        
        # Initialize EasyOCR - lightweight and good for multiple languages
        try:
            import easyocr
            print("Loading EasyOCR model...")
            # Use only English and Hindi to minimize memory usage
            self.reader = easyocr.Reader(['en', 'hi'], gpu=False)
            self.use_easyocr = True
            print("EasyOCR model loaded successfully!")
        except ImportError:
            print("EasyOCR not installed. Using only Tesseract.")
            self.use_easyocr = False
            
        # Initialize PaddleOCR - efficient for low-resource devices
        try:
            from paddleocr import PaddleOCR
            print("Loading PaddleOCR model...")
            # Use lightweight model with no angle detection for speed
            self.paddle_ocr = PaddleOCR(use_angle_cls=False, lang='en', use_gpu=False)
            self.use_paddleocr = True
            print("PaddleOCR model loaded successfully!")
        except ImportError:
            print("PaddleOCR not installed. Skipping.")
            self.use_paddleocr = False
            
    def setup_translation_models(self):
        """Setup lightweight translation models"""
        print("Loading translation models...")
        
        try:
            # Use smaller MarianMT model for English to Hindi
            from transformers import MarianMTModel, MarianTokenizer
            
            # Use a smaller model to save resources
            self.en_hi_model_name = "Helsinki-NLP/opus-mt-en-hi"
            print(f"Loading {self.en_hi_model_name} model...")
            
            # Load with lower precision for memory efficiency
            self.en_hi_tokenizer = MarianTokenizer.from_pretrained(self.en_hi_model_name)
            self.en_hi_model = MarianMTModel.from_pretrained(self.en_hi_model_name, 
                                                             low_cpu_mem_usage=True)
                
            self.use_marian = True
            print("MarianMT translation model loaded successfully!")
        except Exception as e:
            print(f"Failed to load translation model: {e}")
            self.use_marian = False
            
        # Setup alternative translation as fallback
        self.libretranslate_url = "https://translate.argosopentech.com/translate"
        
    def setup_database(self):
        """Setup SQLite database"""
        conn = sqlite3.connect("assistant_data.db", check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS history
                   (timestamp TEXT, command TEXT, result TEXT)''')
        conn.commit()
        return conn
    
    def load_knowledge(self):
        """Load knowledge base from JSON file"""
        try:
            with open("knowledge_data.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print("Knowledge data file not found. Creating empty knowledge base.")
            return {}
        except json.JSONDecodeError:
            print("Error parsing knowledge data. Creating empty knowledge base.")
            return {}
    
    def setup_camera(self):
        """Initialize camera with balanced settings for Pi 4B"""
        self.picam2 = Picamera2()
        # Use moderate resolution for better performance
        self.picam2.preview_configuration.main.size = (800, 600)
        self.picam2.preview_configuration.main.format = "RGB888"
        self.picam2.configure("preview")
    
    def stop_speaking(self):
        """Stop any ongoing TTS"""
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            self.is_speaking = False
            print("Stopped speaking to listen for command.")
    
    def speak(self, text, use_tts=True):
        """Convert text to speech using gTTS and play it"""
        print("\n[Assistant]:", text)
        
        if not use_tts:
            return
        
        self.is_speaking = True
        
        # Create a BytesIO object
        mp3_fp = BytesIO()
        
        # Generate the speech MP3
        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang='en', slow=False)
            tts.write_to_fp(mp3_fp)
            
            # Reset the pointer to the beginning of the BytesIO object
            mp3_fp.seek(0)
            
            # Load the MP3
            pygame.mixer.music.load(mp3_fp)
            
            # Play at normal speed to avoid issues on Pi
            pygame.mixer.music.set_endevent(pygame.USEREVENT)
            pygame.mixer.music.play()
            
            # Wait for the audio to finish playing
            while pygame.mixer.music.get_busy() and self.is_speaking:
                pygame.time.Clock().tick(10)  # Lower tick value for better Pi performance
        except Exception as e:
            print(f"TTS error: {e}")
        
        self.is_speaking = False

    def preprocess_image(self, image):
        """Optimize image for better OCR with limited resources"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply simple thresholding - less resource intensive
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Skip resource-intensive denoising for Pi
        
        # Apply minimal dilation to connect text
        kernel = np.ones((1, 1), np.uint8)
        dilated = cv2.dilate(thresh, kernel, iterations=1)
        
        return dilated, gray, thresh
    
    def get_highest_confidence_text(self, image):
        """Use multiple OCR methods optimized for Raspberry Pi"""
        all_results = []
        confidence_scores = []
        
        # Original image path
        image_path = "captured_image.jpg"
        cv2.imwrite(image_path, image)
        
        # Process image with minimal preprocessing
        processed_img, gray_img, thresh_img = self.preprocess_image(image)
        
        # Save processed image for OCR
        processed_path = "processed_image.jpg"
        cv2.imwrite(processed_path, processed_img)
        
        # Method 1: Standard Tesseract with original image (lightweight config)
        try:
            text1 = pytesseract.image_to_string(Image.open(image_path), config=self.tesseract_config)
            if text1.strip():
                all_results.append(text1)
                confidence_scores.append(len(text1.split()))
        except Exception as e:
            print(f"Standard Tesseract error: {e}")
        
        # Method 2: EasyOCR - good multilingual support & performance
        if self.use_easyocr:
            try:
                results = self.reader.readtext(image_path)
                if results:
                    text2 = " ".join([result[1] for result in results])
                    if text2.strip():
                        all_results.append(text2)
                        confidence_scores.append(len(text2.split()) * 1.3)  # Give EasyOCR a boost
            except Exception as e:
                print(f"EasyOCR error: {e}")
        
        # Method 3: PaddleOCR - optimized for performance
        if self.use_paddleocr:
            try:
                results = self.paddle_ocr.ocr(image_path, cls=False)
                if results and results[0]:
                    text3 = " ".join([line[1][0] for line in results[0]])
                    if text3.strip():
                        all_results.append(text3)
                        confidence_scores.append(len(text3.split()) * 1.4)  # Give PaddleOCR highest boost
            except Exception as e:
                print(f"PaddleOCR error: {e}")
        
        # Additional method with preprocessed image - low resource usage
        try:
            text4 = pytesseract.image_to_string(Image.open(processed_path), config=self.tesseract_config)
            if text4.strip():
                all_results.append(text4)
                confidence_scores.append(len(text4.split()) * 1.1)
        except Exception:
            pass
        
        # Find the result with highest confidence
        if all_results:
            best_index = confidence_scores.index(max(confidence_scores))
            return all_results[best_index]
        
        return ""
    
    def translate_with_marian(self, text, target_lang="hi"):
        """Translate text using MarianMT with memory efficiency adjustments"""
        try:
            if not self.use_marian:
                raise Exception("MarianMT not available")
                
            # Process in smaller chunks to save memory
            if len(text) > 100:
                chunks = [text[i:i+100] for i in range(0, len(text), 100)]
                translated_chunks = []
                
                for chunk in chunks:
                    # Tokenize and translate each chunk
                    inputs = self.en_hi_tokenizer(chunk, return_tensors="pt", padding=True)
                    
                    # Generate translation
                    translated = self.en_hi_model.generate(**inputs)
                    translated_text = self.en_hi_tokenizer.batch_decode(translated, skip_special_tokens=True)[0]
                    translated_chunks.append(translated_text)
                
                return " ".join(translated_chunks)
            else:
                # For short text, translate directly
                inputs = self.en_hi_tokenizer(text, return_tensors="pt", padding=True)
                translated = self.en_hi_model.generate(**inputs)
                translated_text = self.en_hi_tokenizer.batch_decode(translated, skip_special_tokens=True)[0]
                
                return translated_text
        except Exception as e:
            print(f"MarianMT translation error: {e}")
            return None
    
    def translate_with_libretranslate(self, text, target_lang="hi"):
        """Translate text using LibreTranslate API as fallback"""
        try:
            # Split into smaller chunks for API limit compliance
            if len(text) > 500:
                chunks = [text[i:i+500] for i in range(0, len(text), 500)]
                translated_chunks = []
                
                for chunk in chunks:
                    payload = {
                        "q": chunk,
                        "source": "en",
                        "target": target_lang,
                        "format": "text"
                    }
                    
                    headers = {"Content-Type": "application/json"}
                    
                    response = requests.post(
                        self.libretranslate_url,
                        json=payload,
                        headers=headers,
                        timeout=10  # Add timeout for reliability
                    )
                    
                    if response.status_code == 200:
                        translated_chunks.append(response.json()["translatedText"])
                    else:
                        print(f"API error: {response.status_code}")
                        return None
                
                return " ".join(translated_chunks)
            else:
                payload = {
                    "q": text,
                    "source": "en",
                    "target": target_lang,
                    "format": "text"
                }
                
                headers = {"Content-Type": "application/json"}
                
                response = requests.post(
                    self.libretranslate_url,
                    json=payload,
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    return response.json()["translatedText"]
                else:
                    print(f"API error: {response.status_code}")
                    return None
        except Exception as e:
            print(f"LibreTranslate API error: {e}")
            return None
    
    def save_to_db(self, command, result):
        """Save interactions to database"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c = self.conn.cursor()
            c.execute("INSERT INTO history (timestamp, command, result) VALUES (?, ?, ?)",
                    (timestamp, command, result))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Database error: {e}")
    
    def search_knowledge_base(self, query):
        """Search the knowledge base for answers to user queries"""
        query = query.lower()
        
        # First check for date or time in the query - highest priority
        if "date" in query:
            return "Today's date is " + time.strftime("%d %B %Y")
            
        if "time" in query:
            return "The time is " + time.strftime("%I:%M %p")
            
        if "day" in query:
            return "Today is " + calendar.day_name[datetime.datetime.today().weekday()]

        # Check direct matches in top-level categories
        for category in self.knowledge_data:
            category_data = self.knowledge_data[category]
            
            # If category data is a dictionary
            if isinstance(category_data, dict):
                # First check if the query matches a direct key in this category
                for key in category_data:
                    if query in key.lower() or key.lower() in query:
                        content = category_data[key]
                        if isinstance(content, str):
                            return content
                        elif isinstance(content, dict):
                            if "definition" in content:
                                return content["definition"]
                            summary = f"Information about {key}:\n"
                            for sub_key, value in content.items():
                                if isinstance(value, str):
                                    summary += f"- {sub_key}: {value}\n"
                            return summary
                
                # Then search through subcategories and their items
                for subcategory, content in category_data.items():
                    # If there's a direct match with subcategory name
                    if query in subcategory.lower() or subcategory.lower() in query:
                        # If content is a string, return it
                        if isinstance(content, str):
                            return content
                        # If content is a dict, return a formatted summary
                        elif isinstance(content, dict):
                            if "definition" in content:
                                return content["definition"]
                            summary = f"Information about {subcategory}:\n"
                            for key, value in content.items():
                                if isinstance(value, str):
                                    summary += f"- {key}: {value}\n"
                            return summary
                    
                    # For more complex nested structures
                    if isinstance(content, dict):
                        for key, value in content.items():
                            if query in key.lower() or key.lower() in query:
                                if isinstance(value, str):
                                    return value
                                elif isinstance(value, dict) and "description" in value:
                                    return f"{key}: {value['description']}"
                                elif isinstance(value, dict):
                                    return f"Information about {key}: {str(value)}"
            
            # If category data is a list (like history_questions)
            elif isinstance(category_data, list):
                for item in category_data:
                    if query in item.lower():
                        return item
                        
        # Special handling for questions about specific topics
        if "periodic table" in query:
            return self.knowledge_data["science"]["periodic table"]["definition"]
        
        if "newton's laws" in query or "newton laws" in query:
            return self.knowledge_data["science"]["basic physics"]["newton's laws"]
        
        if ("state" in query and "capital" in query) or "india" in query:
            # Check for specific state queries
            states = self.knowledge_data["geography"]["india states and capitals"]
            for state_name, state_info in states.items():
                if state_name.lower() in query.lower():
                    return f"{state_name}: The capital is {state_info['capital']}. {state_info['description']}"
            
            # If no specific state is mentioned, return general information
            if "india" in query:
                states_info = []
                for state, details in self.knowledge_data["geography"]["india states and capitals"].items():
                    states_info.append(f"{state}: Capital - {details['capital']}")
                return "\n".join(states_info[:5]) + "\n(Ask about specific states for more details)"
        
        # No direct matches found, check for keyword matches
        keywords = query.split()
        for keyword in keywords:
            if len(keyword) < 3:  # Skip short words
                continue
                
            # Search through categories
            for category in self.knowledge_data:
                category_data = self.knowledge_data[category]
                
                if isinstance(category_data, dict):
                    for key, value in category_data.items():
                        if keyword in key.lower():
                            if isinstance(value, str):
                                return value
                            elif isinstance(value, dict):
                                if "definition" in value:
                                    return value["definition"]
                                elif "description" in value:
                                    return value["description"]
                                else:
                                    # Return the first item in the dict
                                    for k, v in value.items():
                                        if isinstance(v, str):
                                            return f"About {key} - {k}: {v}"
                                        break
        
        return "I don't have information about that. Please ask something related to science, math, history, or geography."
    
    def show_camera(self):
        """Start camera feed in a separate thread with lower resource usage"""
        if self.camera_on:
            self.speak("Camera is already running.")
            return
        
        self.camera_on = True
        
        def camera_feed():
            try:
                self.picam2.start()
                # Create a smaller window that fits on screen
                cv2.namedWindow("Pi Camera Feed", cv2.WINDOW_NORMAL)
                cv2.resizeWindow("Pi Camera Feed", 640, 480)
                
                while self.camera_on:
                    frame = self.picam2.capture_array()
                    # Add timestamp to frame
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cv2.putText(frame, timestamp, (10, 30), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
                    # Skip frames for better performance
                    cv2.imshow("Pi Camera Feed", frame)
                    
                    # Lower refresh rate to save resources
                    if cv2.waitKey(40) & 0xFF == ord('q'):  # 25fps instead of 60fps
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
            time.sleep(0.5)
            self.speak("Camera closed.")
        else:
            self.speak("Camera is not running.")
    
    def read_text(self):
        """Capture image and extract text using optimized OCR methods"""
        try:
            # Start camera if not already running
            was_camera_on = self.camera_on
            if not was_camera_on:
                self.picam2.start()
                # Wait for camera to initialize
                time.sleep(1)
            
            self.speak("Capturing image and analyzing text...", use_tts=False)
            print("Capturing image for OCR...")
            
            # Capture frame with a slight delay to ensure stability
            time.sleep(0.5)
            frame = self.picam2.capture_array()
            
            # Stop camera if it wasn't running before
            if not was_camera_on:
                self.picam2.stop()
            
            # Save frame for processing
            cv2.imwrite("captured_image.jpg", frame)
            
            # Apply OCR
            text = self.get_highest_confidence_text(frame)
            
            # Store the text for later translation
            self.last_captured_text = text
            
            if text.strip():
                self.speak("The text in the image is: " + text)
            else:
                # Try one more time with enhanced preprocessing
                # Apply basic enhancement for difficult images
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                
                # Save and process
                cv2.imwrite("enhanced_image.jpg", otsu)
                
                # Try EasyOCR as a fallback for difficult images
                if self.use_easyocr:
                    try:
                        results = self.reader.readtext("enhanced_image.jpg")
                        if results:
                            final_text = " ".join([result[1] for result in results])
                            if final_text.strip():
                                self.speak("After enhancement, I found this text: " + final_text)
                                self.last_captured_text = final_text
                                self.save_to_db("read", self.last_captured_text)
                                return self.last_captured_text
                    except Exception:
                        pass
                        
                # As a last resort, try tesseract on enhanced image
                final_text = pytesseract.image_to_string(Image.open("enhanced_image.jpg"), 
                                                     config=self.tesseract_config)
                
                if final_text.strip():
                    self.speak("After enhancement, I found this text: " + final_text)
                    self.last_captured_text = final_text
                else:
                    self.speak("No text detected in the image. Please ensure good lighting and clear text.")
                
            self.save_to_db("read", self.last_captured_text)
            return self.last_captured_text
            
        except Exception as e:
            self.speak(f"Error reading text: {str(e)}")
            return ""
    
    def translate_text(self, target_lang="hi"):
        """Translate text using optimized translation methods"""
        try:
            if not self.last_captured_text:
                # Try to read from saved image
                try:
                    self.last_captured_text = pytesseract.image_to_string(
                        Image.open("captured_image.jpg"), 
                        config=self.tesseract_config
                    )
                except:
                    pass
                
            if not self.last_captured_text.strip():
                self.speak("No text to translate. Please capture an image with text first.")
                return
            
            # Try MarianMT first
            translated = None
            if self.use_marian:
                translated = self.translate_with_marian(self.last_captured_text, target_lang)
            
            # Fallback to LibreTranslate API
            if not translated:
                translated = self.translate_with_libretranslate(self.last_captured_text, target_lang)
            
            # If all translation methods fail, use simpler fallback option
            if not translated:
                try:
                    from translate import Translator
                    translator = Translator(to_lang=target_lang)
                    translated = translator.translate(self.last_captured_text)
                except Exception as e:
                    self.speak(f"Translation failed: {str(e)}")
                    return
            
            self.speak(f"Original text: {self.last_captured_text}\nTranslated text: {translated}")
            self.save_to_db("translate", translated)
        except Exception as e:
            self.speak(f"Translation error: {str(e)}")
    
    def show_help(self):
        """Display available commands"""
        # Print help text without TTS
        self.speak(self.help_text, use_tts=False)
        print(self.help_text)
    
    def show_recent_data(self):
        """Show recent interactions from database"""
        try:
            c = self.conn.cursor()
            c.execute("SELECT * FROM history ORDER BY timestamp DESC LIMIT 5")
            rows = c.fetchall()
            
            if rows:
                result = "Here are your recent interactions:\n"
                for row in rows:
                    result += f"At {row[0]}, command: {row[1]}, result: {row[2][:50]}...\n"
                self.speak(result)
            else:
                self.speak("No previous interactions found.")
        except sqlite3.Error as e:
            self.speak(f"Database error: {str(e)}")
    
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
        """Process and execute voice commands"""
        command = command.lower()
        
        # Check for date keyword in any command first
        if "date" in command:
            self.get_current_date()
            return
            
        # Check for time keyword in any command first
        if "time" in command:
            self.get_current_time()
            return
        
        # Map commands to functions
        command_map = {
            "show camera": self.show_camera,
            "open camera": self.show_camera,
            "start camera": self.show_camera,
            "close camera": self.close_camera,
            "stop camera": self.close_camera,
            "read": self.read_text,
            "read text": self.read_text,
            "translate": self.translate_text,
            "recent data": self.show_recent_data,
            "day": self.get_current_day,
            "what day is it": self.get_current_day,
            "who made you": self.get_creator,
            "creator": self.get_creator,
            "help": self.show_help
        }
        
        # Check for exact or partial command matches
        for cmd, func in command_map.items():
            if cmd in command:
                func()
                return
        
        # Special handling for knowledge-based queries
        # Known subjects to look for in the query
        subjects = ["science", "math", "history", "geography", "periodic table", 
                   "physics", "chemistry", "biology", "astronomy", "earth",
                   "square", "cube", "multiplication", "table", "fraction",
                   "capital", "continent", "country", "state", "war", 
                   "president", "prime minister", "river", "mountain", "ocean"]
                   
        if any(subject in command for subject in subjects):
            response = self.search_knowledge_base(command)
            self.speak(response)
            self.save_to_db(command, response)
            return
        
        # Default behavior for unknown commands
        self.speak("I didn't understand that command. Say 'help' for a list of commands.")
    
    def listen_for_command(self):
        """Listen for command using speech recognition"""
        try:
            # Use the microphone as the audio source
            with sr.Microphone() as source:
                # Stop any ongoing TTS
                self.stop_speaking()
                
                # Wait a moment before listening
                time.sleep(0.5)
                
                # Adjust for ambient noise
                self.recognizer.adjust_for_ambient_noise(source)
                print("Listening for command...")
                
                # Listen for audio input with a shorter timeout for Pi responsiveness
                audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=3)
                
                print("Recognizing...")
                try:
                    # Use Google Speech Recognition
                    command = self.recognizer.recognize_google(audio)
                    print(f"You said: {command}")
                    self.execute_command(command)
                except sr.UnknownValueError:
                    print("Could not understand audio")
                except sr.RequestError as e:
                    print(f"Google Speech API error: {str(e)}")
                except Exception as e:
                    print(f"Error processing command: {str(e)}")
        except Exception as e:
            print(f"Error listening: {str(e)}")
    
    def start_listener(self):
        """Start the voice command listener as a thread"""
        self.listener_thread = threading.Thread(target=self.listen_continuously)
        self.listener_thread.daemon = True
        self.listener_thread.start()
    
    def listen_continuously(self):
        """Continuously listen for commands"""
        print("Voice command system started. Say commands clearly...")
        self.speak("Assistant ready. Say 'help' for available commands.")
        
        while self.is_running:
            try:
                self.listen_for_command()
                # Small delay to prevent CPU overuse
                time.sleep(0.5)
            except Exception as e:
                print(f"Listening error: {e}")
                time.sleep(1)  # Add delay on error
    
    def on_key_press(self, key):
        """Handle keyboard commands"""
        try:
            # Escape key exits
            if key == keyboard.Key.esc:
                print("Exiting...")
                self.cleanup()
                return False  # Stop listener
                
            # Space key triggers voice command
            if key == keyboard.Key.space:
                print("Triggered by spacebar")
                self.listen_for_command()
                
            # C key toggles camera
            if hasattr(key, 'char') and key.char == 'c':
                if self.camera_on:
                    self.close_camera()
                else:
                    self.show_camera()
                    
            # R key reads text
            if hasattr(key, 'char') and key.char == 'r':
                self.read_text()
                
            # T key translates text
            if hasattr(key, 'char') and key.char == 't':
                self.translate_text()
                
            # H key shows help
            if hasattr(key, 'char') and key.char == 'h':
                self.show_help()
                
        except Exception as e:
            print(f"Key handler error: {e}")
    
    def cleanup(self):
        """Clean up resources before exiting"""
        self.is_running = False
        
        # Stop camera if running
        if self.camera_on:
            self.camera_on = False
            time.sleep(0.5)
            try:
                self.picam2.stop()
            except:
                pass
            
            try:
                cv2.destroyAllWindows()
            except:
                pass
        
        # Close database connection
        if self.conn:
            self.conn.close()
            
        # Stop any ongoing speech
        if pygame.mixer.get_init():
            pygame.mixer.quit()
    
    def run(self):
        """Main method to run the assistant"""
        # Start voice listener in background
        self.start_listener()
        
        # Setup keyboard listener for hotkeys
        keyboard_listener = keyboard.Listener(on_press=self.on_key_press)
        keyboard_listener.start()
        
        # Initial instructions
        print("\nSmart Assistant started!")
        print("Press SPACE to trigger voice command")
        print("Press 'c' to toggle camera")
        print("Press 'r' to read text from camera")
        print("Press 't' to translate last captured text")
        print("Press 'h' for help")
        print("Press ESC to exit\n")
        
        try:
            # Keep main thread alive with minimal CPU usage
            while self.is_running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            # Handle Ctrl+C
            print("Interrupted by user, shutting down...")
        finally:
            # Clean up on exit
            self.cleanup()

if __name__ == "__main__":
    try:
        # Create and run the smart assistant
        assistant = SmartAssistant()
        assistant.run()
    except Exception as e:
        print(f"Error starting assistant: {e}")
