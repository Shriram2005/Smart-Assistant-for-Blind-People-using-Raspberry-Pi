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

# Initialize pygame mixer for audio playback
pygame.mixer.init()

# Configure Gemini API
GOOGLE_API_KEY = 'AIzaSyAy2CSsv4_dASgpUxq_VcR6S2jgGd-IrNE'
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-pro")

# Initialize speech recognition
recognizer = sr.Recognizer()

# Language configurations
SUPPORTED_LANGUAGES = {
    'en': {'name': 'English', 'code': 'en-US', 'tts_code': 'en-US'},
    'hi': {'name': 'Hindi', 'code': 'hi-IN', 'tts_code': 'hi-IN'},
    'mr': {'name': 'Marathi', 'code': 'mr-IN', 'tts_code': 'mr-IN'}
}

# Story categories
STORY_CATEGORIES = [
    "moral", "fairy tale", "adventure", "mystery",
    "educational", "historical", "funny", "animal"
]

# Command keywords
COMMANDS = {
    'en': {
        'story': ['tell me a story', 'narrate a story', 'story time'],
        'meaning': ['meaning of', 'what is the meaning of', 'define'],
        'summarize': ['summarize', 'give me a summary of', 'brief me about'],
        'info': ['tell me about', 'what do you know about', 'information about'],
        'translate': ['translate', 'how do you say', 'what is the translation of'],
        'weather': ['weather', 'temperature', 'forecast'],
        'time': ['what time', 'current time', 'what is the time'],
        'date': ['what date', 'current date', 'what is the date'],
        'joke': ['tell me a joke', 'make me laugh', 'say something funny'],
        'help': ['help', 'what can you do', 'commands', 'features']
    },
    'hi': {
        'story': ['कहानी सुनाओ', 'एक कहानी सुनाओ'],
        'meaning': ['का मतलब', 'का अर्थ', 'मतलब बताओ'],
        'summarize': ['सारांश', 'संक्षेप में बताओ'],
        'info': ['के बारे में बताओ', 'की जानकारी दो'],
        'translate': ['अनुवाद', 'का अनुवाद', 'में कैसे कहते हैं'],
        'weather': ['मौसम', 'तापमान', 'मौसम कैसा है'],
        'time': ['क्या समय', 'समय क्या है', 'कितने बजे हैं'],
        'date': ['कौन सी तारीख', 'आज की तारीख', 'दिनांक'],
        'joke': ['एक जोक सुनाओ', 'मुझे हंसाओ', 'कुछ मजेदार सुनाओ'],
        'help': ['मदद', 'आप क्या कर सकते हैं', 'कमांड', 'सुविधाएं']
    }
}


def speak_text(text, language='en'):
    try:
        # Create temporary audio file
        temp_file = f"temp_speech_{time.time()}.mp3"

        # Get the correct language code for TTS
        lang_code = SUPPORTED_LANGUAGES.get(language, SUPPORTED_LANGUAGES['en'])['tts_code']

        # Generate speech using gTTS
        tts = gTTS(text=text, lang=lang_code, slow=False)
        tts.save(temp_file)

        # Play the audio
        pygame.mixer.music.load(temp_file)
        pygame.mixer.music.play()

        # Wait for audio to finish
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
            time.sleep(0.1)

        # Cleanup
        pygame.mixer.music.unload()
        try:
            os.remove(temp_file)
        except:
            pass

    except Exception as e:
        print(f"Speech Error: {str(e)}")
        pygame.mixer.quit()
        pygame.mixer.init()


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
            query = recognizer.recognize_google(audio, language=language_code)
            print(f"You said: {query}")
            return query.lower()
        except sr.WaitTimeoutError:
            print("No speech detected")
            return None
        except sr.UnknownValueError:
            print("Could not understand audio")
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


def check_command_match(text, commands):
    for command_type, phrases in commands.items():
        if any(phrase in text.lower() for phrase in phrases):
            return command_type
    return None


def generate_response(user_input, conversation_history, input_lang):
    try:
        # Check for commands in the appropriate language
        command = check_command_match(user_input, COMMANDS.get(input_lang, COMMANDS['en']))

        if command == 'story':
            return get_story(lang=input_lang), conversation_history

        if command == 'meaning':
            word = user_input.split()[-1]
            return get_word_info(word, input_lang), conversation_history

        if command == 'summarize':
            text_to_summarize = " ".join(user_input.split()[1:])
            return get_summary(text_to_summarize, input_lang), conversation_history

        if command == 'info':
            query = " ".join(user_input.split()[3:]) if input_lang == 'en' else " ".join(user_input.split()[:-3])
            return get_wikipedia_info(query, input_lang), conversation_history

        if command == 'joke':
            return get_joke(input_lang), conversation_history

        if command == 'help':
            return get_help_message(input_lang), conversation_history

        if command == 'weather':
            # Extract city name from input
            city_match = re.search(r'(?:weather|temperature|मौसम|तापमान).*?(?:in|at|का|की|में)\s+([a-zA-Z\s]+)',
                                   user_input)
            if city_match:
                city = city_match.group(1).strip()
                return get_weather(city), conversation_history

        if command == 'time':
            current_time = datetime.now().strftime("%I:%M %p")
            if input_lang == 'hi':
                return f"वर्तमान समय {current_time} है", conversation_history
            else:
                return f"The current time is {current_time}", conversation_history

        if command == 'date':
            current_date = datetime.now().strftime("%B %d, %Y")
            if input_lang == 'hi':
                return f"आज की तारीख {current_date} है", conversation_history
            else:
                return f"Today's date is {current_date}", conversation_history

        # Build conversation context
        context = "\n".join([
            f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
            for msg in conversation_history[-3:]
        ])

        prompt = f"""You are Mira, a knowledgeable and friendly AI assistant who can speak English and Hindi.
        Previous conversation:
        {context}

        User: {user_input}

        Rules:
        1. If input has Hindi words, respond in Hindi using देवनागरी script
        2. Keep responses clear, natural, and engaging
        3. Use simple sentences
        4. For Hindi, use proper punctuation (। ? !)
        5. Be informative but concise
        6. If asked about facts, be accurate
        7. Show empathy and understanding
        8. If unsure, be honest about limitations
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

        return ai_response, new_history

    except Exception as e:
        print(f"Generation Error: {str(e)}")
        error_msg = "Sorry, I couldn't process that" if input_lang == 'en' else "क्षमा करें, मैं समझ नहीं पाई"
        return error_msg, conversation_history


def process_query(query, conversation_history):
    input_lang = detect_language(query)

    # Check for language switch commands
    if any(word in query.lower() for word in ["speak hindi", "hindi mode", "switch to hindi"]):
        input_lang = 'hi'
    elif any(word in query.lower() for word in ["speak english", "english mode", "switch to english"]):
        input_lang = 'en'

    # Check for exit commands
    exit_commands = {
        'en': ["exit", "quit", "goodbye", "bye", "stop"],
        'hi': ["बंद करो", "अलविदा", "बाय", "खत्म", "रुको"]
    }

    if any(cmd in query.lower() for cmd in exit_commands.get(input_lang, [])):
        goodbye_msg = "Goodbye! Have a great day!" if input_lang == 'en' else "अलविदा! आपका दिन शुभ हो!"
        speak_text(goodbye_msg, input_lang)
        sys.exit(0)

    # Generate and speak response
    response, new_history = generate_response(query, conversation_history, input_lang)
    print(f"\nAssistant: {response}")

    # Break response into sentences for better speech
    if input_lang == 'hi':
        sentences = [s.strip() for s in response.replace('।', '।\n').split('\n')]
    else:
        sentences = [s.strip() for s in response.replace('. ', '.\n').split('\n')]

    # Speak each sentence
    for sentence in sentences:
        if sentence:
            speak_text(sentence, input_lang)
            time.sleep(0.3)  # Small pause between sentences

    return new_history


def main():
    print("Starting Enhanced AI Assistant...")
    conversation_history = []

    welcome_messages = {
        'en': """Hello! I'm Mira, your AI assistant. I can help you with:
- Stories and jokes
- Word meanings and translations
- Information and summaries
- Weather updates
- Time and date
- And much more!

Just speak naturally and I'll try to help. Say 'help' for more details.""",
        'hi': """नमस्ते! मैं मीरा हूं, आपकी AI सहायक। मैं आपकी इन कामों में मदद कर सकती हूं:
- कहानियां और चुटकुले
- शब्दों के अर्थ और अनुवाद
- जानकारी और सारांश
- मौसम की जानकारी
- समय और तारीख
- और भी बहुत कुछ!

बस सामान्य रूप से बात करें और मैं मदद करने की कोशिश करूंगी। अधिक जानकारी के लिए 'मदद' कहें।"""
    }

    for lang, msg in welcome_messages.items():
        print(msg)
        speak_text(msg, lang)
        time.sleep(0.5)

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


if __name__ == "__main__":
    main()