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
from datetime import datetime
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor

# Initialize components
pygame.mixer.init()
executor = ThreadPoolExecutor(max_workers=3)

# Configure Gemini API
GOOGLE_API_KEY = 'AIzaSyAy2CSsv4_dASgpUxq_VcR6S2jgGd-IrNE'  # Replace with your API key
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-pro")

# Initialize speech recognition
recognizer = sr.Recognizer()
recognizer.pause_threshold = 0.5
recognizer.energy_threshold = 400

# Language configurations
SUPPORTED_LANGUAGES = {
    'en': {'name': 'English', 'code': 'en-US'},
    'hi': {'name': 'Hindi', 'code': 'hi-IN'}
}


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


def listen(language_code='en-US'):
    with sr.Microphone() as source:
        print("\nListening...")
        recognizer.adjust_for_ambient_noise(source, duration=0.3)

        try:
            audio = recognizer.listen(source, timeout=3, phrase_time_limit=10)
            print("Recognizing...")
            query = recognizer.recognize_google(audio, language=language_code)
            print(f"You said: {query}")
            return query.lower()
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            return None
        except Exception as e:
            print(f"Error: {str(e)}")
            return None


def detect_language(text):
    try:
        lang = detect(text)
        return lang if lang in SUPPORTED_LANGUAGES else 'en'
    except:
        return 'en'


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
    print("Starting AI Assistant...")
    conversation_history = []

    # Welcome message
    welcome = {
        'en': "Hello! I'm Mira, your AI assistant. How can I help you today?",
        'hi': "नमस्ते! मैं मीरा हूं, आपकी AI सहायक। मैं आपकी कैसे मदद कर सकती हूं?"
    }

    for lang, msg in welcome.items():
        print(msg)
        speak_text(msg, lang)
        time.sleep(0.3)

    while True:
        try:
            query = listen()
            if query:
                conversation_history = process_query(query, conversation_history)
        except KeyboardInterrupt:
            print("\nGoodbye!")
            speak_text("Goodbye!", 'en')
            break
        except Exception as e:
            print(f"Error: {str(e)}")
            continue


if _name_ == "_main_":
    main()