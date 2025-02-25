import speech_recognition as sr
import google.generativeai as genai
import sys
import time
from langdetect import detect
from gtts import gTTS
import os
import pygame
import wikipedia
import requests
from datetime import datetime
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
import json
import mysql.connector
from mysql.connector import pooling
import base64

# Initialize components
pygame.mixer.init()
executor = ThreadPoolExecutor(max_workers=3)

# Configure Gemini API
GOOGLE_API_KEY = 'AIzaSyAy2CSsv4_dASgpUxq_VcR6S2jgGd-IrNE'  # Replace with your API key
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-pro")

# Initialize speech recognition with enhanced settings
recognizer = sr.Recognizer()
recognizer.pause_threshold = 1
recognizer.energy_threshold = 1000
recognizer.dynamic_energy_threshold = True
recognizer.dynamic_energy_adjustment_damping = 0.15
recognizer.dynamic_energy_ratio = 1.5

# Language configurations
SUPPORTED_LANGUAGES = {
    'en': {'name': 'English', 'code': 'en-US'},
    'hi': {'name': 'Hindi', 'code': 'hi-IN'}
}

# Wake word configuration
WAKE_WORDS = {
    'hey assistant', 'hi assistant', 'hello assistant', 
    'assistant', 'smart assistant', 'hey smart assistant',
    'हेलो असिस्टेंट', 'हाय असिस्टेंट'
}

# AWS RDS Database configuration
DB_CONFIG = {
    'host': 'raspberrypi.c5csoekmm1vs.us-east-1.rds.amazonaws.com',
    'user': 'admin',
    'password': 'raspberrypi12',
    'database': 'captured_data',
    'port': 3306
}

class SmartAssistant:
    def __init__(self, api_key):
        # Initialize Gemini API
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        
        # Initialize chat history directory
        self.history_dir = "chat_history"
        os.makedirs(self.history_dir, exist_ok=True)
        
        # Load chat history and initialize chat
        self.chat_history = self.load_chat_history()
        self.current_context = None
        
        # Initialize speech components
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 1
        self.recognizer.energy_threshold = 4000
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.dynamic_energy_adjustment_damping = 0.15
        self.recognizer.dynamic_energy_ratio = 1.5
        
        # Initialize the chat with context
        self.initialize_chat_with_context()
        
        # Voice activation settings
        self.wake_words = WAKE_WORDS
        self.is_active = False

    def get_db_connection(self):
        """Get a database connection with retry mechanism"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                conn = mysql.connector.connect(**DB_CONFIG)
                conn.set_charset_collation('utf8mb4', 'utf8mb4_unicode_ci')
                return conn
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"Failed to connect to database after {max_retries} attempts: {str(e)}")
                    raise
                print(f"Connection attempt {attempt + 1} failed, retrying...")
                time.sleep(retry_delay)

    def get_latest_context(self):
        """Fetch the latest captured text and translations from database"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            query = """
                SELECT original_text, english_translation, 
                       hindi_translation, marathi_translation, timestamp
                FROM captured_images 
                ORDER BY timestamp DESC 
                LIMIT 1
            """
            
            cursor.execute(query)
            result = cursor.fetchone()
            
            if result:
                # Format the context
                context = {
                    'original_text': result['original_text'],
                    'translations': {
                        'english': result['english_translation'],
                        'hindi': result['hindi_translation'],
                        'marathi': result['marathi_translation']
                    },
                    'timestamp': result['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
                }
                self.current_context = context
                return context
            return None
            
        except Exception as e:
            print(f"Error fetching context: {str(e)}")
            return None
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()

    def initialize_chat_with_context(self):
        """Initialize chat with historical context and latest captured text"""
        context = self.get_latest_context()
        
        base_context = """You are a helpful AI assistant that can:
        1. Understand and explain text in multiple languages (English, Hindi, Marathi)
        2. Provide summaries and explanations of captured text
        3. Answer questions about the captured text and its translations
        4. Help with understanding the context and meaning of the text
        
        Please use the available context to provide accurate and helpful responses."""
        
        if context:
            context_prompt = f"""
            Latest captured text and translations:
            Original Text: {context['original_text']}
            English Translation: {context['translations']['english']}
            Hindi Translation: {context['translations']['hindi']}
            Marathi Translation: {context['translations']['marathi']}
            Timestamp: {context['timestamp']}
            """
        else:
            context_prompt = "No captured text available yet."
        
        # Initialize chat with context
        self.chat = self.model.start_chat(history=[
            {"role": "user", "parts": [base_context + "\n" + context_prompt]},
            {"role": "model", "parts": ["I understand the context and am ready to help with questions about the captured text and translations."]}
        ])

    def process_input(self, user_input):
        """Process user input with context awareness"""
        try:
            # Check if we need to update context
            if "update context" in user_input.lower():
                context = self.get_latest_context()
                if context:
                    context_update = f"""
                    Updated context:
                    Original Text: {context['original_text']}
                    English Translation: {context['translations']['english']}
                    Hindi Translation: {context['translations']['hindi']}
                    Marathi Translation: {context['translations']['marathi']}
                    Timestamp: {context['timestamp']}
                    """
                    response = self.chat.send_message(f"Please note the updated context: {context_update}")
                    return response.text
                else:
                    return "No new context available."

            # Add context awareness to certain types of questions
            if any(keyword in user_input.lower() for keyword in ['summarize', 'explain', 'what does', 'meaning', 'translate']):
                if not self.current_context:
                    context = self.get_latest_context()
                    if not context:
                        return "I don't have any captured text to work with. Please capture some text first."
                
                # Enhance the user's question with context
                enhanced_input = f"""Regarding this text:
                Original: {self.current_context['original_text']}
                English: {self.current_context['translations']['english']}
                Hindi: {self.current_context['translations']['hindi']}
                Marathi: {self.current_context['translations']['marathi']}
                
                User's question: {user_input}"""
                
                response = self.chat.send_message(enhanced_input)
            else:
                # For other types of questions, just pass through
                response = self.chat.send_message(user_input)
            
            # Update chat history
            self.chat_history.append({
                'user': user_input,
                'assistant': response.text,
                'timestamp': datetime.now().isoformat()
            })
            self.save_chat_history()
            
            return response.text

        except Exception as e:
            error_msg = f"Error processing input: {str(e)}"
            print(error_msg)
            return error_msg

    def save_chat_history(self):
        """Save chat history to file"""
        history_file = os.path.join(self.history_dir, "chat_history.json")
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.chat_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving chat history: {str(e)}")

    def load_chat_history(self):
        """Load chat history from file"""
        history_file = os.path.join(self.history_dir, "chat_history.json")
        try:
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading chat history: {str(e)}")
        return []

    def speak(self, text, lang='en'):
        """Enhanced text-to-speech with proper cleanup"""
        try:
            temp_file = f"temp_speech_{time.time()}.mp3"
            tts = gTTS(text=text, lang='hi' if lang == 'hi' else 'en', slow=False)
            tts.save(temp_file)

            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(20)
                time.sleep(0.05)

            pygame.mixer.music.unload()
            os.remove(temp_file)
        except Exception as e:
            print(f"Speech Error: {str(e)}")
            pygame.mixer.quit()
            pygame.mixer.init()

    def listen_for_wake_word(self):
        """Enhanced wake word detection with noise handling"""
        print("\nWaiting for wake word 'Hey Assistant'...")
        
        with sr.Microphone() as source:
            print("Adjusting for ambient noise...")
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
            
            try:
                print("Listening for wake word...")
                audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=5)
                
                try:
                    # Try multiple language recognition
                    text = ""
                    try:
                        text = self.recognizer.recognize_google(audio, language='en-US').lower()
                    except:
                        try:
                            text = self.recognizer.recognize_google(audio, language='hi-IN').lower()
                        except:
                            return False
                    
                    print(f"Heard: {text}")
                    return any(wake_word in text.lower() or text.lower() in wake_word 
                             for wake_word in self.wake_words)
                    
                except sr.UnknownValueError:
                    return False
                    
            except (sr.WaitTimeoutError, Exception) as e:
                print(f"Error in wake word detection: {str(e)}")
                return False

    def listen_for_command(self):
        """Enhanced command listening with multiple language support"""
        with sr.Microphone() as source:
            print("\nListening for command...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            
            try:
                print("Speak now...")
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=15)
                print("Processing...")
                
                # Try both English and Hindi recognition
                try:
                    text = self.recognizer.recognize_google(audio, language='en-US')
                except:
                    try:
                        text = self.recognizer.recognize_google(audio, language='hi-IN')
                    except sr.UnknownValueError:
                        self.speak("Sorry, I couldn't understand that. Could you please repeat?")
                        return None
                    except Exception as e:
                        print(f"Error: {str(e)}")
                        return None
                
                print(f"You said: {text}")
                return text.lower()
                
            except sr.WaitTimeoutError:
                self.speak("I didn't hear anything. Please try again.")
                return None
            except Exception as e:
                print(f"Error: {str(e)}")
                return None

    def run(self):
        """Main voice interaction loop"""
        self.speak("Hello! I'm your smart assistant. Say 'Hey Assistant' to activate me!")
        
        while True:
            try:
                # Listen for wake word
                if not self.is_active:
                    if self.listen_for_wake_word():
                        self.is_active = True
                        self.speak("Yes, I'm listening! How can I help you?")
                        continue
                
                # Process commands when active
                if self.is_active:
                    command = self.listen_for_command()
                    
                    if command:
                        # Check for exit commands
                        if any(word in command.lower() for word in ["exit", "quit", "bye", "बंद", "अलविदा"]):
                            self.speak("Goodbye! Have a great day!")
                            break
                        
                        # Process the command
                        response = self.process_input(command)
                        print(f"Assistant: {response}")
                        self.speak(response, 'hi' if detect_language(command) == 'hi' else 'en')
                        
                        # Reset active state after response
                        self.is_active = False
                
                time.sleep(0.1)  # Prevent CPU overuse
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                self.speak("Goodbye!")
                break
            except Exception as e:
                print(f"Error in main loop: {str(e)}")
                continue

def speak_text(text, language='en'):
    try:
        temp_file = f"temp_speech_{time.time()}.mp3"
        tts = gTTS(text=text, lang='hi' if language == 'hi' else 'en', slow=False)
        tts.save(temp_file)

        pygame.mixer.music.load(temp_file)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(20)
            time.sleep(0.05)

        pygame.mixer.music.unload()
        try:
            os.remove(temp_file)
        except:
            pass
    except Exception as e:
        print(f"Speech Error: {str(e)}")
        pygame.mixer.quit()
        pygame.mixer.init()


def detect_language(text):
    try:
        lang = detect(text)
        return lang if lang in SUPPORTED_LANGUAGES else 'en'
    except:
        return 'en'


@lru_cache(maxsize=100)
def get_word_info(word, lang='en'):
    try:
        if lang == 'en':
            url = f"https://api.dictionaryapi.dev/api/v2/entries/{lang}/{word}"
            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()[0]
                meanings = data.get('meanings', [])[:2]

                result = [f"Word: {word}"]
                for meaning in meanings:
                    pos = meaning.get('partOfSpeech', '')
                    definitions = meaning.get('definitions', [])[:2]

                    result.append(f"\n{pos}:")
                    for definition in definitions:
                        result.append(f"- {definition['definition']}")

                return "\n".join(result)
            return f"Sorry, couldn't find the meaning of '{word}'"
        else:
            prompt = f"Define the word '{word}' in Hindi briefly."
            response = model.generate_content(prompt)
            return response.text.strip()
    except Exception as e:
        return f"Sorry, couldn't find the meaning of '{word}'"


@lru_cache(maxsize=50)
def get_story(lang='en'):
    try:
        prompt = f"""Tell a short, engaging story that is:
        1. Appropriate for all ages
        2. About 150 words
        3. Has a clear message
        4. {'In Hindi' if lang == 'hi' else 'In English'}
        5. Uses simple language
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return "Sorry, I couldn't generate a story right now."


def get_current_time(lang='en'):
    current_time = datetime.now().strftime("%I:%M %p")
    return f"वर्तमान समय {current_time} है" if lang == 'hi' else f"The current time is {current_time}"


@lru_cache(maxsize=100)
def get_wikipedia_info(query, lang='en'):
    try:
        wikipedia.set_lang('hi' if lang == 'hi' else 'en')
        summary = wikipedia.summary(query, sentences=2)
        return summary
    except:
        try:
            prompt = f"Provide a brief overview of {query} in {'Hindi' if lang == 'hi' else 'English'}"
            response = model.generate_content(prompt)
            return response.text.strip()
        except:
            return f"Sorry, I couldn't find information about '{query}'"


def generate_response(user_input, conversation_history, input_lang):
    try:
        # Quick responses for common queries
        if len(user_input.split()) <= 3:
            if any(word in user_input.lower() for word in ['hi', 'hello', 'hey', 'नमस्ते']):
                return ("Hello! How can I help you?" if input_lang == 'en'
                        else "नमस्ते! मैं आपकी कैसे मदद कर सकती हूं?"), conversation_history

            if any(word in user_input.lower() for word in ['thanks', 'thank', 'धन्यवाद']):
                return ("You're welcome!" if input_lang == 'en'
                        else "आपका स्वागत है!"), conversation_history

        # Check for specific commands
        if "time" in user_input.lower() or "समय" in user_input:
            return get_current_time(input_lang), conversation_history

        if "story" in user_input.lower() or "कहानी" in user_input:
            return get_story(input_lang), conversation_history

        if "meaning of" in user_input.lower() or "मतलब" in user_input:
            word = user_input.split()[-1]
            return get_word_info(word, input_lang), conversation_history

        if "tell me about" in user_input.lower() or "के बारे में बताओ" in user_input:
            query = " ".join(user_input.split()[3:])
            return get_wikipedia_info(query, input_lang), conversation_history

        # Generate contextual response
        context = "\n".join([
            f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
            for msg in conversation_history[-2:]
        ])

        prompt = f"""You are Mira, an AI assistant.
        Previous: {context}
        User: {user_input}
        Rules: Keep responses under 50 words. Use {'Hindi' if input_lang == 'hi' else 'English'}.
        """

        response = model.generate_content(prompt)
        return response.text.strip(), conversation_history[-4:]

    except Exception as e:
        print(f"Generation Error: {str(e)}")
        return ("Sorry, I couldn't process that" if input_lang == 'en'
                else "क्षमा करें, मैं समझ नहीं पाई"), conversation_history


def process_query(query, conversation_history):
    input_lang = detect_language(query)

    # Check for language switch
    if "speak hindi" in query.lower() or "hindi mode" in query:
        input_lang = 'hi'
    elif "speak english" in query.lower() or "english mode" in query:
        input_lang = 'en'

    # Check for exit
    if any(word in query.lower() for word in ["exit", "quit", "bye", "बंद", "अलविदा"]):
        goodbye = "Goodbye! Have a great day!" if input_lang == 'en' else "अलविदा! आपका दिन शुभ हो!"
        speak_text(goodbye, input_lang)
        sys.exit(0)

    # Process response in parallel
    future_response = executor.submit(generate_response, query, conversation_history, input_lang)

    try:
        response, new_history = future_response.result(timeout=10)
        print(f"\nAssistant: {response}")

        # Split response into sentences
        sentences = [s.strip() for s in response.split('। ' if input_lang == 'hi' else '. ')]

        # Speak response
        for sentence in sentences:
            if sentence:
                speak_text(sentence, input_lang)
                time.sleep(0.2)

        return new_history

    except Exception as e:
        print(f"Error: {str(e)}")
        return conversation_history


def main():
    # Replace with your Gemini API key
    API_KEY = "AIzaSyAy2CSsv4_dASgpUxq_VcR6S2jgGd-IrNE"
    
    print("Initializing Smart Assistant...")
    assistant = SmartAssistant(API_KEY)
    
    try:
        assistant.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        pygame.mixer.quit()


if __name__ == "__main__":
    main()