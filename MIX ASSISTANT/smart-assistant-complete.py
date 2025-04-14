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
from translate import Translator
from gtts import gTTS
import pygame
from io import BytesIO

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
        
        # Initialize pygame for audio playback
        pygame.mixer.init()
        
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
        """Initialize camera with optimal settings"""
        self.picam2 = Picamera2()
        # Smaller resolution to fit within screen
        self.picam2.preview_configuration.main.size = (800, 480)
        self.picam2.preview_configuration.main.format = "RGB888"
        self.picam2.configure("preview")
    
    def stop_speaking(self):
        """Stop any ongoing TTS"""
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            self.is_speaking = False
            print("Stopped speaking to listen for command.")
    
    def speak(self, text, use_tts=True):
        """Convert text to speech using gTTS and play it at 2x speed"""
        print("\n[Assistant]:", text)
        
        if not use_tts:
            return
        
        self.is_speaking = True
        
        # Create a BytesIO object
        mp3_fp = BytesIO()
        
        # Generate the speech MP3
        try:
            tts = gTTS(text=text, lang='en', slow=False)
            tts.write_to_fp(mp3_fp)
            
            # Reset the pointer to the beginning of the BytesIO object
            mp3_fp.seek(0)
            
            # Load the MP3
            pygame.mixer.music.load(mp3_fp)
            
            # Play at 2x speed by modifying the tempo
            pygame.mixer.music.set_endevent(pygame.USEREVENT)
            pygame.mixer.music.play()
            
            # Wait for the audio to finish playing
            while pygame.mixer.music.get_busy() and self.is_speaking:
                pygame.time.Clock().tick(30)  # Higher tick value for faster playback
        except Exception as e:
            print(f"TTS error: {e}")
        
        self.is_speaking = False
    
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
        
        # Math-specific queries
        if "table" in query and any(str(num) in query for num in range(2, 11)):
            for num in range(2, 11):
                if str(num) in query:
                    table_key = f"table_{num}"
                    if table_key in self.knowledge_data["math"]["tables"]:
                        return f"Multiplication table of {num}: {self.knowledge_data['math']['tables'][table_key]}"
        
        if "square" in query and ("number" in query or "root" in query):
            if "root" in query:
                roots = []
                for i in range(1, 16):
                    root_key = f"sqrt_{i}"
                    if root_key in self.knowledge_data["math"]["square_roots"]:
                        roots.append(f"√{i} = {self.knowledge_data['math']['square_roots'][root_key]}")
                return "Square roots: " + ", ".join(roots[:5])
            else:
                squares = []
                for i in range(1, 16):
                    square_key = f"square_{i}"
                    if square_key in self.knowledge_data["math"]["square_numbers"]:
                        squares.append(f"{i}² = {self.knowledge_data['math']['square_numbers'][square_key]}")
                return "Square numbers: " + ", ".join(squares[:5])
        
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
            time.sleep(0.5)
            self.speak("Camera closed.")
        else:
            self.speak("Camera is not running.")
    
    def read_text(self):
        """Capture image and extract text using OCR"""
        try:
            # Start camera if not already running
            was_camera_on = self.camera_on
            if not was_camera_on:
                self.picam2.start()
                # Wait for camera to initialize
                time.sleep(1)
            
            # Capture frame
            frame = self.picam2.capture_array()
            image_path = "captured_image.jpg"
            cv2.imwrite(image_path, frame)
            
            # Stop camera if it wasn't running before
            if not was_camera_on:
                self.picam2.stop()
            
            # Process image for better OCR
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img)
            
            if text.strip():
                self.speak("The text in the image is: " + text)
            else:
                self.speak("No text detected in the image.")
                
            self.save_to_db("read", text)
            return text
        except Exception as e:
            self.speak(f"Error reading text: {str(e)}")
            return ""
    
    def translate_text(self, target_lang="hi"):
        """Translate text from recently captured image"""
        try:
            translator = Translator(to_lang=target_lang)
            text = pytesseract.image_to_string(Image.open("captured_image.jpg"))
            
            if not text.strip():
                self.speak("No text to translate. Please capture an image with text first.")
                return
                
            translated = translator.translate(text)
            self.speak(f"Original text: {text}\nTranslated text: {translated}")
            self.save_to_db("translate", translated)
        except FileNotFoundError:
            self.speak("No recently captured image found. Please use the read command first.")
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
                   "revolution", "empire", "river", "mountain", "india"]
        
        # Check if query might be knowledge-related
        is_question = any(word in command for word in ["what", "who", "where", "when", "how", "why", "tell me about", "explain"])
        has_subject = any(subject in command for subject in subjects)
        
        if is_question or has_subject or len(command.split()) > 2:
            response = self.search_knowledge_base(command)
            self.speak(response)
            self.save_to_db(command, response)
            return
            
        # If no specific command or knowledge query recognized
        self.speak("I'm not sure what you're asking. For a list of commands, say 'help'.")
    
    def recognize_speech(self):
        """Listen for and process speech input"""
        # Stop any ongoing speech first
        self.stop_speaking()
        
        try:
            with sr.Microphone() as source:
                print("Listening...")  # Only print, don't speak
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=10)
                
                print("Processing...")  # Only print, don't speak
                command = self.recognizer.recognize_google(audio)
                print(f"Recognized: {command}")
                self.execute_command(command)
        except sr.UnknownValueError:
            print("Sorry, I didn't catch that.")  # Only print, don't speak
        except sr.RequestError:
            self.speak("Sorry, I'm having trouble with the speech recognition service.")
        except Exception as e:
            print(f"Speech recognition error: {str(e)}")
    
    def on_press(self, key):
        """Handle keyboard press events"""
        try:
            if key.char == 's':
                print("Command mode activated")  # Only print, don't speak
                self.recognize_speech()
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
        if self.conn:
            self.conn.close()
    
    def run(self):
        """Main method to start the assistant"""
        try:
            self.speak("Smart Assistant Initialized. Press 's' to speak.")
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
