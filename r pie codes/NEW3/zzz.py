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
import random
import json
from datetime import datetime
import re
import sounddevice as sd
import numpy as np
from scipy.io import wavfile
import threading
import queue
import pyttsx3
from deep_translator import GoogleTranslator
import logging
from textblob import TextBlob

# Initialize pygame mixer for audio playback
pygame.mixer.init()

# Configure Gemini API
GOOGLE_API_KEY = 'AIzaSyAy2CSsv4_dASgpUxq_VcR6S2jgGd-IrNE'
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-pro")

# Initialize speech recognition
recognizer = sr.Recognizer()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='ai_assistant.log'
)

# Initialize text-to-speech engine as backup
engine = pyttsx3.init()

# Audio configurations
SAMPLE_RATE = 44100
CHANNELS = 2
CHUNK_SIZE = 1024
audio_queue = queue.Queue()

# Emotion detection thresholds
EMOTION_THRESHOLDS = {
    'positive': 0.3,
    'negative': -0.3
}

# Enhanced language configurations
SUPPORTED_LANGUAGES = {
    'en': {
        'name': 'English',
        'code': 'en-US',
        'tts_code': 'en-US',
        'voice_id': 'en-US-Standard-C',
        'speaking_rate': 1.0
    },
    'hi': {
        'name': 'Hindi',
        'code': 'hi-IN',
        'tts_code': 'hi-IN',
        'voice_id': 'hi-IN-Standard-A',
        'speaking_rate': 0.9
    },
    'mr': {
        'name': 'Marathi',
        'code': 'mr-IN',
        'tts_code': 'mr-IN',
        'voice_id': 'mr-IN-Standard-A',
        'speaking_rate': 0.9
    }
}

# Story categories
STORY_CATEGORIES = [
    "moral", "fairy tale", "adventure", "mystery",
    "educational", "historical", "funny", "animal"
]

class AudioManager:
    def __init__(self):
        self.volume = 1.0
        self.speed = 1.0
        self.is_paused = False
        self.current_stream = None
        
    def adjust_volume(self, direction):
        if direction == 'up':
            self.volume = min(2.0, self.volume + 0.2)
        else:
            self.volume = max(0.2, self.volume - 0.2)
            
    def adjust_speed(self, direction):
        if direction == 'up':
            self.speed = min(2.0, self.speed + 0.2)
        else:
            self.speed = max(0.5, self.speed - 0.2)
            
    def pause_audio(self):
        self.is_paused = True
        if self.current_stream:
            self.current_stream.stop()
            
    def resume_audio(self):
        self.is_paused = False
        if self.current_stream:
            self.current_stream.start()

audio_manager = AudioManager()

def enhance_audio_quality(audio_data):
    # Normalize audio
    audio_data = audio_data / np.max(np.abs(audio_data))
    
    # Apply basic noise reduction
    noise_threshold = 0.1
    audio_data[np.abs(audio_data) < noise_threshold] = 0
    
    return audio_data

def speak_text(text, language='en'):
    try:
        if not text or audio_manager.is_paused:
            return

        # Get language configuration
        lang_config = SUPPORTED_LANGUAGES.get(language, SUPPORTED_LANGUAGES['en'])
        
        # For Hindi, directly use gTTS as it handles Hindi better
        if language == 'hi':
            try:
                temp_file = f"temp_speech_{time.time()}.mp3"
                tts = gTTS(text=text, lang='hi', slow=False)
                tts.save(temp_file)
                
                # Initialize pygame mixer if not initialized
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                
                # Load and play the audio
                pygame.mixer.music.load(temp_file)
                pygame.mixer.music.set_volume(audio_manager.volume)
                pygame.mixer.music.play()
                
                # Wait for the audio to finish
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
                    if audio_manager.is_paused:
                        pygame.mixer.music.pause()
                        break
                
                # Cleanup
                pygame.mixer.music.unload()
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                return
                    
            except Exception as e:
                print(f"gTTS failed for Hindi: {str(e)}")
                logging.error(f"gTTS error for Hindi: {str(e)}")
                raise
        
        # For English and other languages, try pyttsx3 first
        try:
            engine = pyttsx3.init()
            
            # Configure voice properties
            voices = engine.getProperty('voices')
            
            # Select appropriate voice for the language
            selected_voice = None
            for voice in voices:
                voice_info = voice.id.lower()
                if language == 'en' and ('english' in voice_info or 'en-us' in voice_info):
                    selected_voice = voice.id
                    break
            
            if selected_voice:
                engine.setProperty('voice', selected_voice)
            
            # Set rate and volume
            engine.setProperty('rate', int(175 * audio_manager.speed))
            engine.setProperty('volume', audio_manager.volume)
            
            # Speak the text
            engine.say(text)
            engine.runAndWait()
            return
            
        except Exception as e:
            print(f"pyttsx3 failed: {str(e)}")
            logging.error(f"pyttsx3 error: {str(e)}")
            
            # Fallback to gTTS for non-Hindi languages
            try:
                temp_file = f"temp_speech_{time.time()}.mp3"
                tts = gTTS(text=text, lang=lang_config['tts_code'], slow=False)
                tts.save(temp_file)
                
                # Initialize pygame mixer if not initialized
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                
                # Load and play the audio
                pygame.mixer.music.load(temp_file)
                pygame.mixer.music.set_volume(audio_manager.volume)
                pygame.mixer.music.play()
                
                # Wait for the audio to finish
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
                    if audio_manager.is_paused:
                        pygame.mixer.music.pause()
                        break
                
                # Cleanup
                pygame.mixer.music.unload()
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    
            except Exception as e:
                print(f"gTTS fallback failed: {str(e)}")
                logging.error(f"gTTS fallback error: {str(e)}")
                raise

    except Exception as e:
        print(f"Speech Error: {str(e)}")
        logging.error(f"Speech Error: {str(e)}")

def get_weather(city):
    try:
        # Using OpenWeatherMap API (you should get your own API key)
        API_KEY = "YOUR_OPENWEATHERMAP_API_KEY"
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 200:
            temp = data['main']['temp']
            desc = data['weather'][0]['description']
            return f"Temperature in {city} is {temp}°C with {desc}"
        else:
            return "Sorry, I couldn't fetch the weather information"
    except:
        return "Sorry, I couldn't fetch the weather information"

def get_word_info(word, lang='en'):
    try:
        if lang == 'en':
            url = f"https://api.dictionaryapi.dev/api/v2/entries/{lang}/{word}"
            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()[0]
                response_text = f"Word: {word}\n\n"

                if 'meanings' in data:
                    response_text += "Meanings:\n"
                    for meaning in data['meanings'][:2]:  # Limit to 2 meanings for brevity
                        pos = meaning.get('partOfSpeech', '')
                        definitions = meaning.get('definitions', [])

                        response_text += f"{pos}:\n"
                        for definition in definitions[:2]:
                            response_text += f"- {definition['definition']}\n"

                        synonyms = meaning.get('synonyms', [])[:3]
                        if synonyms:
                            response_text += "Synonyms: " + ", ".join(synonyms) + "\n"

                        antonyms = meaning.get('antonyms', [])[:3]
                        if antonyms:
                            response_text += "Antonyms: " + ", ".join(antonyms) + "\n"

                return response_text
            else:
                return f"Sorry, couldn't find the meaning of '{word}'"
        else:
            prompt = f"Provide the meaning, synonyms, and antonyms for the word '{word}' in {'Hindi' if lang == 'hi' else 'Marathi'}. Keep it concise."
            response = model.generate_content(prompt)
            return response.text.strip()

    except Exception as e:
        print(f"Error in word lookup: {str(e)}")
        return f"Sorry, I couldn't find information about '{word}'"

def get_joke(lang='en'):
    try:
        if lang == 'en':
            response = requests.get("https://v2.jokeapi.dev/joke/General?safe-mode")
            data = response.json()
            if data['type'] == 'single':
                return data['joke']
            else:
                return f"{data['setup']}\n{data['delivery']}"
        else:
            prompt = f"Tell a short, clean joke in {'Hindi' if lang == 'hi' else 'Marathi'}. Keep it family-friendly."
            response = model.generate_content(prompt)
            return response.text.strip()
    except:
        return "Sorry, I couldn't fetch a joke right now."

def get_help_message(lang='en'):
    if lang == 'en':
        return """I can help you with:
1. Tell stories (say "tell me a story")
2. Define words (say "meaning of [word]")
3. Summarize text (say "summarize [text]")
4. Provide information (say "tell me about [topic]")
5. Tell jokes (say "tell me a joke")
6. Check weather (say "weather in [city]")
7. Get current time and date
8. Translate between languages

Just speak naturally and I'll try to help!"""
    else:
        # Generate help message in Hindi/Marathi using Gemini
        prompt = f"Generate a help message in {'Hindi' if lang == 'hi' else 'Marathi'} that explains the following features: stories, word meanings, summaries, information, jokes, weather, time/date, and translations. Make it natural and friendly."
        response = model.generate_content(prompt)
        return response.text.strip()

def get_story(category=None, lang='en'):
    try:
        if not category:
            category = random.choice(STORY_CATEGORIES)

        prompt = f"""Generate a {category} story that is:
        1. Engaging and appropriate for all ages
        2. Not too long (around 200 words)
        3. Has a clear beginning, middle, and end
        4. {'In Hindi using देवनागरी script' if lang == 'hi' else 'In Marathi' if lang == 'mr' else 'In English'}
        5. Uses simple language and short sentences
        6. Has some dialogue between characters
        7. Has a clear moral or message
        """

        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        print(f"Story Error: {str(e)}")
        return "Sorry, I couldn't generate a story right now."

def get_summary(text, lang='en'):
    try:
        prompt = f"""Summarize this text in {'Hindi' if lang == 'hi' else 'Marathi' if lang == 'mr' else 'English'} (keep it concise):
        {text}
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Summary Error: {str(e)}")
        return "Sorry, I couldn't generate a summary."

def get_wikipedia_info(query, lang='en'):
    try:
        # Set Wikipedia language
        wikipedia.set_lang('hi' if lang == 'hi' else 'mr' if lang == 'mr' else 'en')
        
        # Search for the query
        search_results = wikipedia.search(query)
        if not search_results:
            return f"Sorry, I couldn't find information about '{query}'"
        
        # Get the first matching page
        page = wikipedia.page(search_results[0])
        
        # Get a summary (first 3 sentences)
        summary = wikipedia.summary(search_results[0], sentences=3)
        
        return summary
    except Exception as e:
        print(f"Wikipedia Error: {str(e)}")
        # Fallback to Gemini for information
        prompt = f"Provide a brief overview (3-4 sentences) about {query} in {'Hindi' if lang == 'hi' else 'Marathi' if lang == 'mr' else 'English'}"
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except:
            return f"Sorry, I couldn't find information about '{query}'"

def listen(language_code='en-US'):
    with sr.Microphone() as source:
        print("\nListening...")
        recognizer.pause_threshold = 1
        recognizer.adjust_for_ambient_noise(source, duration=1)

        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=15)
            print("Recognizing...")
            
            # First try to detect if it's Hindi by attempting Hindi recognition
            try:
                query = recognizer.recognize_google(audio, language='hi-IN')
                # If Hindi recognition succeeds and contains Hindi characters
                if any(ord(char) >= 2304 and ord(char) <= 2431 for char in query):
                    print(f"You said (Hindi): {query}")
                    return query.lower(), 'hi'
            except:
                pass
            
            # If Hindi recognition fails, try English
            query = recognizer.recognize_google(audio, language='en-US')
            print(f"You said (English): {query}")
            return query.lower(), 'en'
            
        except sr.WaitTimeoutError:
            print("No speech detected")
            return None, None
        except sr.UnknownValueError:
            print("Could not understand audio")
            return None, None
        except Exception as e:
            print(f"Error: {str(e)}")
            return None, None

def detect_language(text):
    try:
        # Check for Hindi characters first
        if any(ord(char) >= 2304 and ord(char) <= 2431 for char in text):
            return 'hi'
        # If no Hindi characters found, check using langdetect
        lang = detect(text)
        return lang if lang in SUPPORTED_LANGUAGES else 'en'
    except:
        return 'en'

def detect_emotion(text):
    try:
        # Use TextBlob for sentiment analysis
        analysis = TextBlob(text)
        
        # Get polarity (-1 to 1) and subjectivity (0 to 1)
        polarity = analysis.sentiment.polarity
        subjectivity = analysis.sentiment.subjectivity
        
        # Determine emotion
        if polarity > EMOTION_THRESHOLDS['positive']:
            return 'positive'
        elif polarity < EMOTION_THRESHOLDS['negative']:
            return 'negative'
        return 'neutral'
    except:
        return 'neutral'

def adjust_response_style(response, emotion):
    """Adjust response based on detected emotion"""
    if emotion == 'positive':
        response = response.replace('।', '! ').replace('.', '! ')
    elif emotion == 'negative':
        # Add empathetic prefixes for negative emotions
        prefixes = {
            'en': ["I understand how you feel. ", "Let me help you. ", "Don't worry. "],
            'hi': ["मैं समझ सकती हूं। ", "मैं आपकी मदद करती हूं। ", "चिंता मत कीजिए। "]
        }
        lang = 'hi' if any(char in response for char in 'अआइईउऊएऐओऔकखगघ') else 'en'
        return random.choice(prefixes[lang]) + response
    return response

def generate_response(user_input, conversation_history, input_lang):
    try:
        # Detect emotion in user input
        emotion = detect_emotion(user_input)
        
        # Build conversation context
        context = "\n".join([
            f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
            for msg in conversation_history[-3:]
        ])

        # Adjust prompt based on detected language
        if input_lang == 'hi':
            prompt = f"""You are Mira, a knowledgeable and friendly AI assistant who speaks Hindi.
            Previous conversation:
            {context}

            User: {user_input}

            Rules:
            1. ALWAYS respond in Hindi using देवनागरी script
            2. Keep responses clear, natural, and engaging
            3. Use simple Hindi sentences
            4. Use proper Hindi punctuation (। ? !)
            5. Be informative but concise
            6. Show empathy and understanding
            7. If unsure, be honest about limitations
            8. Respond naturally without using predefined formats
            """
        else:
            prompt = f"""You are Mira, a knowledgeable and friendly AI assistant who speaks English.
            Previous conversation:
            {context}

            User: {user_input}

            Rules:
            1. ALWAYS respond in English
            2. Keep responses clear, natural, and engaging
            3. Use simple sentences
            4. Be informative but concise
            5. Show empathy and understanding
            6. If unsure, be honest about limitations
            7. Respond naturally without using predefined formats
            """

        response = model.generate_content(prompt)
        ai_response = response.text.strip()

        # Update conversation history
        new_history = conversation_history + [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": ai_response}
        ]
        
        # Keep only last 6 messages
        if len(new_history) > 6:
            new_history = new_history[-6:]

        # Adjust response based on emotion
        ai_response = adjust_response_style(ai_response, emotion)

        # Log interaction
        logging.info(f"User: {user_input} (Language: {input_lang}, Emotion: {emotion})")
        logging.info(f"Assistant: {ai_response}")
        
        return ai_response, new_history

    except Exception as e:
        logging.error(f"Response Generation Error: {str(e)}")
        error_msg = "Sorry, I couldn't process that" if input_lang == 'en' else "क्षमा करें, मैं समझ नहीं पाई"
        return error_msg, conversation_history

def process_query(query, conversation_history):
    try:
        if not query:
            return conversation_history

        # Get the detected language from listen function
        query_text, detected_lang = query if isinstance(query, tuple) else (query, detect_language(query))
        input_lang = detected_lang if detected_lang else 'en'
        
        print(f"\nDetected language: {input_lang}")

        # Generate and speak response
        response, new_history = generate_response(query_text, conversation_history, input_lang)
        print(f"\nAssistant: {response}")

        # Break response into smaller chunks for better speech
        if input_lang == 'hi':
            # For Hindi, split by Devanagari purna viram and other punctuation marks
            sentences = [s.strip() for s in re.split('[।!?\n]', response) if s.strip()]
            for sentence in sentences:
                if sentence:
                    speak_text(sentence, 'hi')  # Explicitly use Hindi for TTS
                    time.sleep(0.3)
        else:
            sentences = [s.strip() for s in re.split('[.!?\n]', response) if s.strip()]
            for sentence in sentences:
                if sentence:
                    speak_text(sentence, 'en')  # Explicitly use English for TTS
                    time.sleep(0.3)

        return new_history

    except Exception as e:
        print(f"Error in process_query: {str(e)}")
        logging.error(f"Query Processing Error: {str(e)}")
        error_msg = "Sorry, I encountered an error" if input_lang == 'en' else "क्षमा करें, कोई त्रुटि हुई"
        speak_text(error_msg, input_lang)
        return conversation_history

def main():
    print("Starting AI Assistant...")
    logging.info("AI Assistant Started")
    conversation_history = []

    # Welcome messages
    welcome_messages = {
        'en': "Hello! I'm Mira, your AI assistant. I can understand and speak both English and Hindi. How can I help you today?",
    }

    for lang, msg in welcome_messages.items():
        print(msg)
        speak_text(msg, lang)
        time.sleep(0.5)

    while True:
        try:
            query = listen()
            if query[0]:  # query is now a tuple (text, language)
                conversation_history = process_query(query, conversation_history)

        except KeyboardInterrupt:
            goodbye_msg = "Goodbye! Have a great day!" if query[1] == 'en' else "अलविदा! आपका दिन शुभ हो!"
            print(f"\n{goodbye_msg}")
            speak_text(goodbye_msg, query[1])
            logging.info("AI Assistant Stopped")
            break
        except Exception as e:
            logging.error(f"Main Loop Error: {str(e)}")
            continue

if __name__ == "__main__":
    main()