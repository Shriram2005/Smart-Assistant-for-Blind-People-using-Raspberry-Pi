import google.generativeai as genai
import json
from datetime import datetime
import os
from deep_translator import GoogleTranslator
import pyttsx3
import threading
from concurrent.futures import ThreadPoolExecutor
import speech_recognition as sr
import time
from functools import lru_cache
import queue
import numpy as np

class SmartAssistant:
    def __init__(self, api_key):
        # Initialize Gemini API
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        
        # Initialize translator
        self.translator = {
            'en': GoogleTranslator(source='auto', target='en'),
            'hi': GoogleTranslator(source='auto', target='hi')
        }
        
        # Initialize TTS engine with optimized settings
        self.engine = None
        self.tts_lock = threading.Lock()
        self.initialize_tts_engine()
        
        # Create chat history directory
        self.history_dir = "chat_history"
        os.makedirs(self.history_dir, exist_ok=True)
        
        # Initialize response cache and command queue
        self.response_cache = {}
        self.command_queue = queue.Queue()
        
        # Load chat history and initialize chat with context
        self.chat_history = self.load_chat_history()
        self.initialize_chat_with_context()
        
        # Thread pool for parallel processing
        self.executor = ThreadPoolExecutor(max_workers=3)
        
        # Control flags
        self.is_active = False
        self.is_running = True
        
        # Audio settings
        self.sample_rate = 16000
        self.chunk_size = 1024
        
        # Initialize speech recognition with noise reduction
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 4000
        self.recognizer.pause_threshold = 0.8
        self.recognizer.dynamic_energy_adjustment_ratio = 1.5
        
        # Initialize microphone with optimal settings
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
        except Exception as e:
            print(f"Microphone initialization error: {str(e)}")

    def initialize_tts_engine(self):
        """Initialize TTS engine with proper resource management"""
        with self.tts_lock:
            if self.engine is not None:
                try:
                    self.engine.stop()
                except:
                    pass
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 175)
            self.engine.setProperty('volume', 0.9)
            
            # Cache voices for faster access
            self.voices = self.engine.getProperty('voices')
            self.english_voice = self.voices[0].id
            self.hindi_voice = next((v.id for v in self.voices if 'hi' in v.id.lower()), self.voices[0].id)

    def detect_language(self, text):
        """Detect language of input text"""
        # Simple language detection based on character set
        devanagari_range = range(0x0900, 0x097F)
        hindi_chars = [c for c in text if ord(c) in devanagari_range]
        return 'hi' if hindi_chars else 'en'

    @lru_cache(maxsize=100)
    def translate_text_cached(self, text, target_lang):
        """Cached version of translate_text for better performance"""
        try:
            if text in self.response_cache:
                return self.response_cache[text]
            
            if target_lang not in ['en', 'hi']:
                return text
                
            translation = self.translator[target_lang].translate(text)
            if translation:
                self.response_cache[text] = translation
                return translation
            return text
        except Exception as e:
            print(f"Translation error: {str(e)}")
            return text

    def speak(self, text, lang='en'):
        """Thread-safe text-to-speech with proper resource management"""
        with self.tts_lock:
            try:
                if self.engine is None:
                    self.initialize_tts_engine()
                
                self.engine.setProperty('voice', self.hindi_voice if lang == 'hi' else self.english_voice)
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                print(f"TTS Error: {str(e)}")
                # Reinitialize engine on error
                self.initialize_tts_engine()

    def save_chat_history(self):
        """Save chat history to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.history_dir}/chat_history_{timestamp}.json"
        
        history_data = {
            'timestamp': timestamp,
            'messages': self.chat_history
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)

    def load_chat_history(self):
        """Load most recent chat history"""
        try:
            history_files = sorted([f for f in os.listdir(self.history_dir) if f.endswith('.json')])
            if history_files:
                latest_file = history_files[-1]
                with open(f"{self.history_dir}/{latest_file}", 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('messages', [])
        except Exception as e:
            print(f"Error loading chat history: {str(e)}")
        return []

    def initialize_chat_with_context(self):
        """Initialize chat with historical context"""
        context = "You are a helpful AI assistant that can communicate in both English and Hindi."
        
        # Add recent history as context (last 5 conversations)
        recent_history = self.chat_history[-5:] if self.chat_history else []
        history_messages = []
        
        for entry in recent_history:
            history_messages.extend([
                {"role": "user", "parts": [entry['user']]},
                {"role": "model", "parts": [entry['assistant']]}
            ])
        
        self.chat = self.model.start_chat(history=history_messages)

    def listen_for_wake_word(self):
        """Enhanced wake word detection with noise filtering"""
        try:
            with sr.Microphone(sample_rate=self.sample_rate) as source:
                print("Listening for wake word...")
                audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=3)
                
                # Convert audio to numpy array for processing
                audio_data = np.frombuffer(audio.get_raw_data(), dtype=np.int16)
                
                # Simple noise filtering
                audio_data = audio_data[abs(audio_data) > np.mean(np.abs(audio_data))]
                
                if len(audio_data) > 0:
                    text = self.recognizer.recognize_google(audio).lower()
                    return "hey smart assistant" in text
                return False
        except (sr.WaitTimeoutError, sr.UnknownValueError):
            return False
        except Exception as e:
            print(f"Error listening for wake word: {str(e)}")
            return False

    def listen_for_command(self):
        """Listen for user command"""
        try:
            with sr.Microphone() as source:
                print("Listening for command...")
                self.speak("I'm listening", 'en')
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                text = self.recognizer.recognize_google(audio)
                print(f"You said: {text}")
                return text
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            self.speak("Sorry, I didn't catch that. Could you repeat?", 'en')
            return None
        except Exception as e:
            print(f"Error listening for command: {str(e)}")
            return None

    def process_command_async(self, command):
        """Process commands asynchronously"""
        try:
            future = self.executor.submit(self.process_input, command)
            return future
        except Exception as e:
            print(f"Async processing error: {str(e)}")
            return None

    def run(self):
        """Optimized main loop with parallel processing"""
        self.speak("Smart Assistant initialized. Say 'Hey Smart Assistant' to begin.", 'en')
        
        command_futures = []
        
        while self.is_running:
            try:
                # Clean up completed futures
                command_futures = [f for f in command_futures if not f.done()]
                
                # Listen for wake word
                if not self.is_active:
                    if self.listen_for_wake_word():
                        self.is_active = True
                        continue
                
                # Process commands in parallel if active
                if self.is_active:
                    command = self.listen_for_command()
                    
                    if command:
                        if command.lower() == "stop":
                            self.is_active = False
                            self.speak("Going to sleep. Say 'Hey Smart Assistant' to wake me up.", 'en')
                            continue
                        
                        # Process command asynchronously
                        future = self.process_command_async(command)
                        if future:
                            command_futures.append(future)
                
                # Small delay with adaptive timing
                time.sleep(0.05)
                
            except Exception as e:
                print(f"Error in main loop: {str(e)}")
                continue

    def process_input(self, user_input):
        """Optimized input processing with proper error handling"""
        try:
            # Check cache first
            cache_key = f"{user_input}"
            if cache_key in self.response_cache:
                cached_response = self.response_cache[cache_key]
                self.speak(cached_response['response'], cached_response['lang'])
                return cached_response['response']
            
            # Process new input
            input_lang = self.detect_language(user_input)
            
            # Only translate if necessary
            if input_lang == 'hi':
                english_input = self.translate_text_cached(user_input, 'en')
            else:
                english_input = user_input
            
            # Generate response
            response = self.chat.send_message(english_input)
            english_response = response.text
            
            # Translate response if necessary
            if input_lang == 'hi':
                final_response = self.translate_text_cached(english_response, 'hi')
            else:
                final_response = english_response
            
            # Cache the response
            self.response_cache[cache_key] = {
                'response': final_response,
                'lang': input_lang
            }
            
            # Update chat history asynchronously
            self.executor.submit(self.update_chat_history, user_input, final_response)
            
            # Speak response
            self.speak(final_response, input_lang)
            
            return final_response

        except Exception as e:
            error_msg = f"Error processing input: {str(e)}"
            print(error_msg)
            self.speak("Sorry, I encountered an error. Please try again.", 'en')
            return error_msg

    def update_chat_history(self, user_input, response):
        """Asynchronous chat history update"""
        try:
            self.chat_history.append({
                'user': user_input,
                'assistant': response,
                'timestamp': datetime.now().isoformat()
            })
            self.save_chat_history()
        except Exception as e:
            print(f"Error updating chat history: {str(e)}")

def main():
    # Replace with your Gemini API key
    API_KEY = "AIzaSyAy2CSsv4_dASgpUxq_VcR6S2jgGd-IrNE"
    
    print("Initializing Smart Assistant...")
    assistant = SmartAssistant(API_KEY)
    
    try:
        assistant.run()
    except KeyboardInterrupt:
        print("\nShutting down Smart Assistant...")
        assistant.is_running = False
        assistant.speak("Goodbye!", 'en')

if __name__ == "__main__":
    main()