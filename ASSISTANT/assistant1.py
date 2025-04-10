import datetime
import os
import re
import threading
import time
import webbrowser
import json
from collections import defaultdict

import nltk
import numpy as np
import pygame
import pyttsx3
import requests
import speech_recognition as sr
from bs4 import BeautifulSoup
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import mysql.connector
from mysql.connector import pooling
import wikipedia

# Download necessary NLTK data
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')

# Aiven MySQL Configuration
MYSQL_CONFIG = {
    'host': 'mysql-raspberry-pi-shrirammange.k.aivencloud.com',  # Aiven MySQL endpoint
    'user': 'avnadmin',                # Default Aiven admin username
    'password': 'AVNS_YkuryCt4s_wLBuD8xAb',       # Your Aiven password
    'database': 'defaultdb',       # Database name
    'port': 18836,                     # Your Aiven MySQL port
    'ssl_ca': 'FINAL/Online Final/ca.pem',        # Path to Aiven CA certificate
}

class SmartAssistant:
    def __init__(self, name="Assistant", voice_index=0):
        self.name = name
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Initialize text-to-speech engine
        self.engine = pyttsx3.init()
        voices = self.engine.getProperty('voices')
        if voices and len(voices) > voice_index:
            self.engine.setProperty('voice', voices[voice_index].id)
        self.engine.setProperty('rate', 175)  # Speed of speech
        
        # Initialize speech recognition settings
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            
        # Knowledge base for common questions
        self.knowledge_base = self.load_knowledge_base()
        
        # Load science knowledge data
        self.science_knowledge = self.load_science_knowledge()
        
        # Debug mode setting
        self.debug_mode = False
        
        try:
            # Add a fixed pool_name to the connection parameters
            connection_config = MYSQL_CONFIG.copy()
            connection_config['pool_name'] = 'mypool'  # Add a short, fixed pool name
            connection_config['pool_size'] = 5  # Optional: set a specific pool size
            
            self.connection_pool = mysql.connector.pooling.MySQLConnectionPool(**connection_config)
            if self.debug_mode:
                print("Database connection pool created successfully")
        except Exception as e:
            self.connection_pool = None
            print(f"Error creating database connection pool: {e}")
        
        # Query categorization
        self.categories = {
            'time': ['time', 'clock', 'hour'],
            'date': ['date', 'day', 'month', 'year', 'today'],
            'weather': ['weather', 'temperature', 'forecast', 'rain', 'sunny'],
            'wikipedia': ['who is', 'what is', 'tell me about', 'wikipedia', 'define'],
            'news': ['news', 'latest news', 'headlines', 'current events'],
            'general': ['how to', 'why do', 'how does', 'explain'],
            'calculation': ['calculate', 'compute', 'math', 'solve', 'plus', 'minus', 'times', 'divided by'],
            'web_search': ['search for', 'google', 'find', 'look up'],
            'greeting': ['hello', 'hi', 'hey', 'greetings'],
            'goodbye': ['goodbye', 'bye', 'see you', 'exit', 'quit', 'stop'],
            'about': ['who are you', 'what can you do', 'your name', 'about you'],
            'read_text': ['read the last text', 'last captured text', 'read captured text', 'what was the last text', 'read the last text', 'repeat the last text'],
            'science': ['periodic table', 'newton', 'physics', 'chemistry', 'biology', 'astronomy', 'earth science', 
                      'human body', 'technology', 'innovation', 'atoms', 'molecules', 'cells', 'solar system',
                      'rock cycle', 'respiratory', 'circulatory', 'digestive', 'immune', 'nervous',
                      'electricity', 'magnetism', 'renewable energy', 'nuclear energy', 'space exploration'],
            'math': ['mathematics', 'math', 'pi', 'fibonacci', 'pythagoras', 'quadratic', 'calculus', 'trigonometry',
                   'logarithm', "euler's", 'statistics', 'probability', 'square root', 'cube root', 
                   'table of', 'multiplication table', 'square number', 'cube number', 'fraction', 
                   'addition', 'subtraction', 'multiplication', 'division', 'modulus', 'percentage', 'average',
                   'conversion', 'unit convert', 'meters to', 'kilometers to', 'grams to', 'kilograms to'],
            'history': ['history', 'historical', 'ancient', 'century', 'war', 'revolution', 'empire', 
                      'civilization', 'middle ages', 'medieval', 'renaissance', 'world war', 
                      'civil war', 'cold war', 'prehistory', 'dynasty', 'monarchy', 'king', 'queen',
                      'president', 'battle', 'treaty', 'crusades', 'romans', 'greeks', 'egyptians',
                      'mesopotamia', 'ottoman', 'mongol', 'persian', 'byzantine', 'colonial', 'napoleon'],
            'geography': ['geography', 'continent', 'ocean', 'mountain', 'river', 'desert', 'forest', 
                        'rainforest', 'reef', 'canyon', 'valley', 'plateau', 'island', 'peninsula', 
                        'capital city', 'country', 'state', 'city', 'population', 'map', 'atlas', 
                        'border', 'territory', 'climate', 'landform', 'landscape', 'region', 'hemisphere',
                        'equator', 'tropics', 'arctic', 'antarctic', 'latitude', 'longitude', 'india']
        }
        
        # Animation and sounds for feedback
        pygame.mixer.init()
        self.listening_sound = None
        try:
            self.listening_sound = pygame.mixer.Sound('sounds/listening.wav')
        except:
            print("Listening sound file not found")
            
        self.is_active = True
        self.debug_mode = False
        
        # Cache for recent queries
        self.query_cache = {}
        
        # Conversation memory (simple)
        self.conversation_memory = []
        self.memory_limit = 10
        
        # Start with a greeting
        self.speak(f"Hello, I'm {self.name}, your smart assistant. How can I help you today?")
        
    def load_knowledge_base(self):
        """Load a basic knowledge base for common questions"""
        knowledge = defaultdict(str)
        
        # Science facts
        knowledge["What is gravity"] = "Gravity is the force that attracts objects toward one another. The law of universal gravitation states that every mass attracts every other mass in the universe."
        knowledge["What is photosynthesis"] = "Photosynthesis is the process by which green plants and some other organisms use sunlight to synthesize foods with carbon dioxide and water, generating oxygen as a byproduct."
        knowledge["What are atoms"] = "Atoms are the basic units of matter and the defining structure of elements. They consist of a nucleus containing protons and neutrons, surrounded by electrons."
        
        # Geography facts
        knowledge["What is the largest ocean"] = "The Pacific Ocean is the largest and deepest ocean on Earth, covering more than 60 million square miles."
        knowledge["What is the highest mountain"] = "Mount Everest is Earth's highest mountain above sea level, located in the Mahalangur Himal sub-range of the Himalayas with an elevation of 29,032 feet."
        knowledge["What is the longest river"] = "The Nile River in Africa is generally regarded as the longest river in the world, flowing about 4,132 miles."
        
        # History facts
        knowledge["Who was Albert Einstein"] = "Albert Einstein was a German-born theoretical physicist who developed the theory of relativity, one of the two pillars of modern physics. He is best known for his mass–energy equivalence formula E = mc²."
        knowledge["When did World War 2 end"] = "World War II ended on September 2, 1945, with the formal surrender of Japan aboard the U.S. battleship USS Missouri."
        knowledge["Who was the first person on the moon"] = "Neil Armstrong was the first person to walk on the Moon on July 21, 1969, during the Apollo 11 mission."
        
        return knowledge
        
    def load_science_knowledge(self):
        """Load science-related knowledge from JSON file"""
        try:
            knowledge_file_path = os.path.join(os.path.dirname(__file__), "knowledge_data.json")
            with open(knowledge_file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception as e:
            if hasattr(self, 'debug_mode') and self.debug_mode:
                print(f"Error loading science knowledge data: {e}")
            return {"science": {}}
    
    def get_science_info(self, query):
        """Find relevant science information from the knowledge data"""
        if not self.science_knowledge or "science" not in self.science_knowledge:
            return None
        
        science_data = self.science_knowledge["science"]
        query_lower = query.lower()
        
        # First, check for exact topic matches
        for topic, topic_data in science_data.items():
            if topic.lower() in query_lower:
                # If the topic is directly mentioned
                if isinstance(topic_data, str):
                    return topic_data
                elif isinstance(topic_data, dict):
                    # If it's a dictionary, check if any specific subtopic is mentioned
                    for subtopic, info in topic_data.items():
                        if subtopic.lower() in query_lower:
                            if isinstance(info, str):
                                return f"{subtopic.capitalize()}: {info}"
                            elif isinstance(info, dict):
                                # Check for third-level topics
                                for detail_topic, detail_info in info.items():
                                    if detail_topic.lower() in query_lower:
                                        return f"{detail_topic.capitalize()}: {detail_info}"
                                
                                # If no specific third-level topic was mentioned, give an overview
                                overview = f"About {subtopic}:\n"
                                for detail_topic, detail_info in info.items():
                                    overview += f"- {detail_topic.capitalize()}: {detail_info}\n"
                                return overview
                    
                    # If no specific subtopic was mentioned, provide a general overview of the topic
                    overview = f"About {topic}:\n\n"
                    for subtopic, info in topic_data.items():
                        if isinstance(info, str):
                            overview += f"- {subtopic.capitalize()}: {info}\n"
                        elif isinstance(info, dict):
                            overview += f"- {subtopic.capitalize()}: {list(info.keys())}\n"
                    return overview
        
        # If no direct topic match, look for keywords in the subtopics
        for topic, topic_data in science_data.items():
            if isinstance(topic_data, dict):
                for subtopic, info in topic_data.items():
                    if subtopic.lower() in query_lower:
                        if isinstance(info, str):
                            return f"{subtopic.capitalize()}: {info}"
                        elif isinstance(info, dict):
                            overview = f"About {subtopic}:\n"
                            for detail_topic, detail_info in info.items():
                                overview += f"- {detail_topic.capitalize()}: {detail_info}\n"
                            return overview
        
        # If still no match, check for any keyword in the content
        for topic, topic_data in science_data.items():
            if isinstance(topic_data, dict):
                for subtopic, info in topic_data.items():
                    keywords = subtopic.split()
                    for keyword in keywords:
                        if len(keyword) > 3 and keyword.lower() in query_lower:
                            if isinstance(info, str):
                                return f"{subtopic.capitalize()}: {info}"
                            break
        
        return None

    def get_math_info(self, query):
        """Find relevant math information from the knowledge data"""
        if not self.science_knowledge or "math" not in self.science_knowledge:
            return None
        
        math_data = self.science_knowledge["math"]
        query_lower = query.lower()
        
        # Check for direct math concept mentions
        for concept, info in math_data.items():
            if concept.lower() in query_lower:
                if isinstance(info, str):
                    return info
                elif isinstance(info, dict):
                    # For nested structures like tables, square numbers, etc.
                    overview = f"About {concept}:\n\n"
                    
                    # Look for specific sub-concepts
                    for sub_concept, sub_info in info.items():
                        # For specific tables, square roots, etc.
                        if sub_concept.lower() in query_lower:
                            return f"{sub_concept}: {sub_info}"
                    
                    # If no specific sub-concept was mentioned, provide a summary
                    if len(info) <= 7:  # For smaller collections, show all items
                        for sub_concept, sub_info in info.items():
                            overview += f"- {sub_concept}: {sub_info}\n"
                    else:  # For larger collections, just list the available items
                        overview += "Available information: " + ", ".join(info.keys())
                    
                    return overview
        
        # Handle specific number-based queries
        number_match = re.search(r'table of (\d+)', query_lower) or re.search(r'(\d+) times table', query_lower)
        if number_match:
            number = number_match.group(1)
            table_key = f"table_{number}"
            if "tables" in math_data and table_key in math_data["tables"]:
                return f"Multiplication table of {number}: {math_data['tables'][table_key]}"
        
        square_match = re.search(r'square of (\d+)', query_lower)
        if square_match:
            number = square_match.group(1)
            square_key = f"square_{number}"
            if "square_numbers" in math_data and square_key in math_data["square_numbers"]:
                value = math_data["square_numbers"][square_key]
                return f"The square of {number} is {value}"
            elif number.isdigit() and int(number) <= 100:
                # Calculate on-the-fly for reasonable numbers
                value = int(number) ** 2
                return f"The square of {number} is {value}"
        
        cube_match = re.search(r'cube of (\d+)', query_lower)
        if cube_match:
            number = cube_match.group(1)
            cube_key = f"cube_{number}"
            if "cube_numbers" in math_data and cube_key in math_data["cube_numbers"]:
                value = math_data["cube_numbers"][cube_key]
                return f"The cube of {number} is {value}"
            elif number.isdigit() and int(number) <= 50:
                # Calculate on-the-fly for reasonable numbers
                value = int(number) ** 3
                return f"The cube of {number} is {value}"
        
        sqrt_match = re.search(r'square root of (\d+)', query_lower)
        if sqrt_match:
            number = sqrt_match.group(1)
            sqrt_key = f"sqrt_{number}"
            if "square_roots" in math_data and sqrt_key in math_data["square_roots"]:
                value = math_data["square_roots"][sqrt_key]
                return f"The square root of {number} is {value}"
            elif number.isdigit() and int(number) <= 1000:
                # Calculate on-the-fly for reasonable numbers
                import math
                value = round(math.sqrt(int(number)), 3)
                return f"The square root of {number} is {value}"
        
        # Check for fraction terms
        for fraction, info in math_data.get("fractions", {}).items():
            if fraction in query_lower:
                return info
        
        # Check for unit conversion
        for conversion, info in math_data.get("units_conversion", {}).items():
            conversion_terms = conversion.split('_to_')
            if all(term in query_lower for term in conversion_terms):
                return info
        
        # If no direct match was found, look for any math-related keywords
        for concept, info in math_data.items():
            if isinstance(info, str):
                keywords = concept.split()
                for keyword in keywords:
                    if len(keyword) > 3 and keyword.lower() in query_lower:
                        return info
        
        return None
    
    def get_history_info(self, query):
        """Find relevant historical information from the knowledge data"""
        if not self.science_knowledge or "history" not in self.science_knowledge:
            return None
        
        history_data = self.science_knowledge["history"]
        query_lower = query.lower()
        
        # Check for direct historical event/period mentions
        for event, info in history_data.items():
            if event.lower() in query_lower:
                return info
        
        # Check history questions if available
        if "history_questions" in self.science_knowledge:
            history_questions = self.science_knowledge["history_questions"]
            
            # Find the most similar question
            best_match = None
            best_match_score = 0
            
            for question in history_questions:
                # Simple word overlap similarity
                question_words = set(question.lower().split())
                query_words = set(query_lower.split())
                common_words = question_words.intersection(query_words)
                
                # Calculate similarity score
                similarity = len(common_words) / max(len(question_words), len(query_words))
                
                if similarity > best_match_score and similarity > 0.3:  # Threshold
                    best_match_score = similarity
                    best_match = question
            
            if best_match:
                # If we found a similar question, try to provide an answer
                return f"You might be asking about: {best_match}\n\nI'll search for information on this historical topic."
        
        # If no direct match was found, look for related topics
        related_topics = []
        for event, info in history_data.items():
            # Check if any significant words from the query appear in the event or info
            event_words = event.split()
            for word in query_lower.split():
                if len(word) > 3 and (word in event.lower() or word in info.lower()):
                    related_topics.append((event, info))
                    break
        
        if related_topics:
            if len(related_topics) == 1:
                event, info = related_topics[0]
                return f"Related historical information about {event}:\n{info}"
            else:
                response = "I found several historical topics that might be related:\n\n"
                for event, _ in related_topics[:3]:  # Limit to top 3
                    response += f"- {event.title()}\n"
                response += "\nYou can ask me specifically about any of these topics."
                return response
        
        return None

    def get_geography_info(self, query):
        """Find relevant geographical information from the knowledge data"""
        if not self.science_knowledge or "geography" not in self.science_knowledge:
            return None
        
        geography_data = self.science_knowledge["geography"]
        query_lower = query.lower()
        
        # First, check for exact topic matches
        for topic, topic_data in geography_data.items():
            if topic.lower() in query_lower:
                if isinstance(topic_data, str):
                    return topic_data
                elif isinstance(topic_data, dict):
                    # Handle special cases like Indian states and UTs
                    
                    # If specific state/UT is mentioned
                    for entity_name, entity_data in topic_data.items():
                        if entity_name.lower() in query_lower:
                            if isinstance(entity_data, str):
                                return entity_data
                            elif isinstance(entity_data, dict):
                                capital = entity_data.get("capital", "Unknown")
                                description = entity_data.get("description", "")
                                return f"{entity_name}: Capital - {capital}\n{description}"
                    
                    # If no specific entity is mentioned, provide an overview
                    if "india states" in topic.lower() and "capital" in query_lower:
                        response = "States of India and their capitals:\n\n"
                        for state, data in topic_data.items():
                            capital = data.get("capital", "Unknown")
                            response += f"{state}: {capital}\n"
                        return response
                    elif "india union territories" in topic.lower():
                        response = "Union Territories of India and their capitals:\n\n"
                        for ut, data in topic_data.items():
                            capital = data.get("capital", "Unknown")
                            response += f"{ut}: {capital}\n"
                        return response
                    
                    # Provide list of items in the category
                    return f"I can provide information about the following in {topic}:\n" + ", ".join(topic_data.keys())
        
        # Check for specific entity names in Indian states and UTs
        if "state" in query_lower or "capital" in query_lower or "india" in query_lower:
            states_data = geography_data.get("india states and capitals", {})
            uts_data = geography_data.get("india union territories", {})
            
            # Check all states for a match
            for state, data in states_data.items():
                if state.lower() in query_lower:
                    capital = data.get("capital", "Unknown")
                    description = data.get("description", "")
                    return f"{state}: Capital - {capital}\n{description}"
                
                # Also check if query is asking for capital of a specific state
                capital_match = re.search(r"capital of ([a-zA-Z ]+)", query_lower)
                if capital_match:
                    state_name = capital_match.group(1).strip()
                    if state.lower() == state_name or state.lower().startswith(state_name):
                        capital = data.get("capital", "Unknown")
                        return f"The capital of {state} is {capital}."
            
            # Check all UTs for a match
            for ut, data in uts_data.items():
                if ut.lower() in query_lower:
                    capital = data.get("capital", "Unknown")
                    description = data.get("description", "")
                    return f"{ut}: Capital - {capital}\n{description}"
                
                # Also check if query is asking for capital of a specific UT
                if capital_match:
                    ut_name = capital_match.group(1).strip()
                    if ut.lower() == ut_name or ut.lower().startswith(ut_name):
                        capital = data.get("capital", "Unknown")
                        return f"The capital of {ut} is {capital}."
        
        # Check for general geographic features
        for feature in ["mountain", "river", "ocean", "desert", "rainforest", "reef", "canyon"]:
            if feature in query_lower:
                for topic, info in geography_data.items():
                    if feature in topic.lower() and isinstance(info, str):
                        return info
        
        # If no direct match, look for keywords in geography topics
        for topic, info in geography_data.items():
            if isinstance(info, str):
                topic_keywords = topic.split()
                for keyword in topic_keywords:
                    if len(keyword) > 3 and keyword.lower() in query_lower:
                        return info
        
        return None

    def speak(self, text):
        """Convert text to speech"""
        print(f"{self.name}: {text}")
        self.engine.say(text)
        self.engine.runAndWait()
    
    def listen(self):
        """Listen for voice input and convert to text"""
        if self.listening_sound:
            self.listening_sound.play()
            
        print(f"{self.name} is listening...")
        
        with self.microphone as source:
            try:
                # Adjust for ambient noise before each listening session
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                # Set a dynamic energy threshold - helps with different voice volumes
                self.recognizer.energy_threshold = 300  # Default is 300, increase for noisy environments
                self.recognizer.dynamic_energy_threshold = True
                
                # Increase timeout and phrase_time_limit to give users more time to speak
                # timeout: how long to wait for speech to start
                # phrase_time_limit: maximum length of a phrase
                audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=10)
                
                if self.listening_sound:
                    pygame.mixer.stop()
                
                try:
                    # Use a more comprehensive recognition with language specification
                    text = self.recognizer.recognize_google(audio, language='en-IN')
                    print(f"You said: {text}")
                    return text.lower()
                except sr.UnknownValueError:
                    if self.debug_mode:
                        print("Could not understand audio")
                    return ""
                except sr.RequestError as e:
                    if self.debug_mode:
                        print(f"Error with Google Speech Recognition service: {e}")
                    # Fallback to offline recognition if available
                    try:
                        text = self.recognizer.recognize_sphinx(audio)
                        print(f"You said (offline): {text}")
                        return text.lower()
                    except:
                        if self.debug_mode:
                            print("Offline recognition also failed")
                        return ""
                    
            except sr.WaitTimeoutError:
                if self.debug_mode:
                    print("Listening timed out")
                if self.listening_sound:
                    pygame.mixer.stop()
                return ""
    
    def categorize_query(self, query):
        """Determine the category of a user query using more sophisticated matching"""
        if not query:
            return None
        
        query_lower = query.lower()
        
        # Check for exact phrase matches first (more specific)
        for category, keywords in self.categories.items():
            for keyword in keywords:
                # Check for exact phrases (higher priority)
                if keyword in query_lower and len(keyword.split()) > 1:
                    return category
        
        # Use word boundary matching for single words to avoid substring matches
        # For example, 'time' should match 'what time is it' but not 'sometimes'
        for category, keywords in self.categories.items():
            for keyword in keywords:
                if len(keyword.split()) == 1:  # Single word
                    # Check if it's a whole word using word boundaries
                    pattern = r'\b' + re.escape(keyword) + r'\b'
                    if re.search(pattern, query_lower):
                        return category
        
        # For more complex queries, use a scoring system
        category_scores = {}
        words = query_lower.split()
        
        for category, keywords in self.categories.items():
            score = 0
            for keyword in keywords:
                keyword_words = keyword.split()
                # Check for partial matches
                for kw in keyword_words:
                    if kw in words and len(kw) > 2:  # Only count meaningful words
                        score += 1
            if score > 0:
                category_scores[category] = score
        
        # Return the category with the highest score if any
        if category_scores:
            return max(category_scores.items(), key=lambda x: x[1])[0]
                
        # Default to web search if no category matches
        return "web_search"
        
    def get_current_time(self):
        """Get the current time"""
        current_time = datetime.datetime.now().strftime("%I:%M %p")
        return f"The current time is {current_time}."
        
    def get_current_date(self):
        """Get the current date"""
        current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")
        return f"Today is {current_date}."
        
    def get_weather(self, location=""):
        """Get weather information for a location"""
        if not location:
            location = "current location"
            
        try:
            # Web scraping approach for weather (no API key required)
            url = f"https://www.google.com/search?q=weather+in+{location.replace(' ', '+')}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract temperature (this selector might need updates based on Google's layout changes)
            temp_div = soup.find('div', {'class': 'BNeawe iBp4i AP7Wnd'})
            if temp_div:
                temperature = temp_div.text
                return f"The temperature in {location} is currently {temperature}."
            else:
                return f"I couldn't find the weather for {location}. Please try another location."
                
        except Exception as e:
            if self.debug_mode:
                print(f"Weather error: {e}")
            return f"I'm having trouble getting weather information right now. Please try again later."
            
    def get_wikipedia_info(self, query):
        """Get information from Wikipedia"""
        try:
            # Clean up the query
            search_query = query
            for prefix in ["who is", "what is", "tell me about", "wikipedia", "define"]:
                search_query = search_query.replace(prefix, "").strip()
            
            # First try direct Wikipedia API
            try:
                # Search for Wikipedia pages
                search_results = wikipedia.search(search_query, results=3)
                
                if search_results:
                    # Get the page for the first result
                    page = wikipedia.page(search_results[0], auto_suggest=False)
                    
                    # Get a summary (first 3 sentences)
                    summary = wikipedia.summary(search_results[0], sentences=3, auto_suggest=False)
                    
                    return summary
                else:
                    return None
            except wikipedia.exceptions.DisambiguationError as e:
                # If there's a disambiguation, get the first option
                try:
                    page = wikipedia.page(e.options[0], auto_suggest=False)
                    summary = wikipedia.summary(e.options[0], sentences=3, auto_suggest=False)
                    return summary
                except:
                    pass
            except wikipedia.exceptions.PageError:
                # Page not found, continue to web scraping method
                pass
            except Exception as wiki_api_error:
                if self.debug_mode:
                    print(f"Wikipedia API error: {wiki_api_error}")
            
            # Fallback to web scraping method
            url = f"https://en.wikipedia.org/wiki/{search_query.replace(' ', '_')}"
            response = requests.get(url)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Get the first paragraph of content
                paragraphs = soup.select("div.mw-parser-output > p")
                for p in paragraphs:
                    if p.text.strip():
                        # Return the first non-empty paragraph
                        return p.text.strip()
            
            return None
            
        except Exception as e:
            if self.debug_mode:
                print(f"Wikipedia error: {e}")
            return None
    
    def get_news(self):
        """Get latest news headlines"""
        try:
            # Web scraping approach for news (no API key required)
            url = "https://news.google.com/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find news articles
            articles = soup.find_all('a', {'class': 'VDXfz'})
            
            if articles:
                headlines = []
                for i, article in enumerate(articles[:5]):  # Get top 5 headlines
                    headlines.append(f"{i+1}. {article.text.strip()}")
                    
                headlines_text = "\n".join(headlines)
                return f"Here are the latest headlines:\n{headlines_text}"
            else:
                return "I couldn't retrieve the latest news headlines. Please try again later."
                
        except Exception as e:
            if self.debug_mode:
                print(f"News error: {e}")
            return "I'm having trouble getting the news right now. Please try again later."
    
    def search_web(self, query):
        """Search the web for information"""
        try:
            # Use web scraping to get search results
            search_query = query.replace("search for", "").replace("google", "").replace("find", "").replace("look up", "").strip()
            
            # First try Wikipedia
            try:
                wiki_result = self.get_wikipedia_info(search_query)
                if wiki_result and "I couldn't find information" not in wiki_result:
                    return wiki_result
            except Exception as wiki_error:
                if self.debug_mode:
                    print(f"Wikipedia search error: {wiki_error}")
            
            # Then try Google search
            url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try to find a featured snippet or direct answer
            answer_div = soup.find('div', {'class': 'Z0LcW'}) or soup.find('div', {'class': 'IZ6rdc'})
            if answer_div:
                return answer_div.text
                
            # Look for search result snippets
            results = soup.find_all('div', {'class': 'BNeawe s3v9rd AP7Wnd'})
            if results:
                return results[0].text
            
            # If web search fails, return None to indicate no results found
            return None
            
        except Exception as e:
            if self.debug_mode:
                print(f"Web search error: {e}")
            return None
    
    def handle_calculation(self, query):
        """Handle mathematical calculations"""
        # Extract the calculation part from the query
        query = query.replace("calculate", "").replace("compute", "").replace("solve", "").strip()
        
        # Replace word operators with symbols
        query = query.replace("plus", "+").replace("minus", "-").replace("times", "*").replace("multiplied by", "*")
        query = query.replace("divided by", "/").replace("over", "/")
        
        # Basic calculation using eval (with security measures)
        try:
            # Only allow basic arithmetic operations
            allowed_chars = set("0123456789+-*/().^ ")
            if not all(c in allowed_chars for c in query):
                return "I can only perform basic arithmetic calculations."
                
            # Replace ^ with ** for exponentiation
            query = query.replace("^", "**")
            
            result = eval(query)
            return f"The result of {query} is {result}."
            
        except Exception as e:
            if self.debug_mode:
                print(f"Calculation error: {e}")
            return "I couldn't perform that calculation. Please try a simpler arithmetic expression."
            
    def find_in_knowledge_base(self, query):
        """Find the most relevant answer in the knowledge base"""
        if not query or not self.knowledge_base:
            return None
            
        # Prepare vectorizer for text similarity
        vectorizer = TfidfVectorizer(stop_words=stopwords.words('english'))
        
        # Convert knowledge base to list format for vectorization
        keys = list(self.knowledge_base.keys())
        
        try:
            # Vectorize the knowledge base questions
            knowledge_vectors = vectorizer.fit_transform(keys)
            
            # Vectorize the query
            query_vector = vectorizer.transform([query])
            
            # Calculate similarity scores
            similarities = cosine_similarity(query_vector, knowledge_vectors)[0]
            
            # Find the most similar question
            best_match_index = np.argmax(similarities)
            best_match_score = similarities[best_match_index]
            
            # Only return if similarity is above threshold
            if best_match_score > 0.3:
                best_match_question = keys[best_match_index]
                return self.knowledge_base[best_match_question]
                
        except Exception as e:
            if self.debug_mode:
                print(f"Knowledge base error: {e}")
                
        return None
    
    # get last captured text from the aiven database
    def get_last_captured_text(self):
        """Retrieve the last captured text from the database"""
        if not self.connection_pool:
            return "I'm sorry, I can't access the database at the moment."
        
        try:
            connection = self.connection_pool.get_connection()
            cursor = connection.cursor(dictionary=True)
            
            # Query to get the most recent text entry
            query = """
                SELECT original_text, english_translation, hindi_translation, marathi_translation 
                FROM captured_images 
                ORDER BY timestamp DESC 
                LIMIT 1
            """
            
            cursor.execute(query)
            result = cursor.fetchone()
            
            cursor.close()
            connection.close()
            
            if result and result['original_text']:
                text = result['original_text']
                # Return only the original text without translations
                return f"The last captured text is: {text}"
            else:
                return "I couldn't find any captured text in the database."
                
        except Exception as e:
            if self.debug_mode:
                print(f"Database error: {e}")
            return "I'm having trouble retrieving the last captured text. Please try again later."
    
    def process_query(self, query):
        """Process the user's query and generate a more accurate response"""
        if not query:
            return "I didn't catch that. Could you please repeat?"
            
        # Check if query is in cache
        if query in self.query_cache:
            return self.query_cache[query]
        
        # Add to conversation memory
        self.conversation_memory.append(("user", query))
        if len(self.conversation_memory) > self.memory_limit:
            self.conversation_memory.pop(0)
        
        # Check for assistant name in query to activate
        assistant_names = [self.name.lower(), "assistant"]
        is_addressed = any(name in query.lower() for name in assistant_names)
        
        # Check if it's a goodbye intent
        if any(word in query.lower() for word in self.categories['goodbye']):
            self.is_active = False
            return "Goodbye! Have a great day."
        
        # Basic greeting
        if any(word in query.lower() for word in self.categories['greeting']):
            return f"Hello! How can I help you today?"
        
        # About the assistant
        if any(phrase in query.lower() for phrase in self.categories['about']):
            return f"I'm {self.name}, a smart assistant designed to help answer your questions about a wide variety of topics. I can tell you the time, date, weather, news, and information from Wikipedia, among other things. Just ask me a question!"
        
        # Determine query category with improved categorization
        category = self.categorize_query(query)
        
        # Process based on category
        response = ""
        
        # Handle straightforward service categories first
        if category == "time":
            response = self.get_current_time()
        elif category == "date":
            response = self.get_current_date()
        elif category == "weather":
            # Extract location if provided with improved pattern matching
            location_match = re.search(r'(?:weather|temperature|forecast)\s+(?:in|at|for)\s+([a-zA-Z ]+)', query.lower())
            if not location_match:
                # Try a simpler pattern
                location_match = re.search(r'([a-zA-Z ]+)\s+(?:weather|temperature|forecast)', query.lower())
            location = location_match.group(1).strip() if location_match else ""
            response = self.get_weather(location)
        elif category == "news":
            response = self.get_news()
        elif category == "calculation":
            response = self.handle_calculation(query)
        elif category == "read_text":
            response = self.get_last_captured_text()
        else:
            # For knowledge-based categories, use a more sophisticated approach
            # First, try to get information from our knowledge base
            knowledge_result = None
            
            # Try the specific category first
            if category == "science":
                knowledge_result = self.get_science_info(query)
            elif category == "math":
                knowledge_result = self.get_math_info(query)
            elif category == "history":
                knowledge_result = self.get_history_info(query)
            elif category == "geography":
                knowledge_result = self.get_geography_info(query)
            else:
                # For general queries, check the basic knowledge base first
                knowledge_result = self.find_in_knowledge_base(query)
            
            # If we found a result in our knowledge base, use it
            if knowledge_result:
                response = knowledge_result
            else:
                # If no result from knowledge base, try online search
                online_result = self.search_web(query)
                
                if online_result:
                    response = online_result
                else:
                    # If online search fails, try a more comprehensive check of all knowledge sources
                    # This is a fallback for when the category might have been misidentified
                    knowledge_sources = [
                        ("science", self.get_science_info),
                        ("math", self.get_math_info),
                        ("history", self.get_history_info),
                        ("geography", self.get_geography_info)
                    ]
                    
                    for source_name, source_func in knowledge_sources:
                        if source_name != category:  # Skip the one we already checked
                            result = source_func(query)
                            if result:
                                response = result
                                break
                    
                    # If we still don't have a response, provide a more helpful fallback message
                    if not response:
                        response = f"I'm sorry, I don't have specific information about '{query}'. Could you please rephrase your question or ask me about something else?"
        
        # Save to cache
        self.query_cache[query] = response
        
        # Add to conversation memory
        self.conversation_memory.append(("assistant", response))
        if len(self.conversation_memory) > self.memory_limit:
            self.conversation_memory.pop(0)
        
        return response
        
    def run(self):
        """Run the assistant in a continuous loop"""
        try:
            while self.is_active:
                query = self.listen()
                
                if query:
                    response = self.process_query(query)
                    self.speak(response)
                    
                time.sleep(0.1)  # Small delay to prevent high CPU usage
                
        except KeyboardInterrupt:
            self.speak("Shutting down. Goodbye!")
        finally:
            # Clean up resources
            if hasattr(self, 'engine'):
                self.engine.stop()

# Main execution
if __name__ == "__main__":
    print("Starting Smart Assistant...")
    
    # You can customize the assistant's name and voice
    assistant = SmartAssistant(name="Alex", voice_index=0)
    
    # Run the assistant
    assistant.run()