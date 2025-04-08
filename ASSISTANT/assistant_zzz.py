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
        try:
            self.microphone = sr.Microphone()
            # Initialize speech recognition settings
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
        except Exception as e:
            print(f"Error initializing microphone: {e}")
            self.microphone = None
            
        # Initialize text-to-speech engine
        try:
            self.engine = pyttsx3.init()
            voices = self.engine.getProperty('voices')
            if voices and len(voices) > voice_index:
                self.engine.setProperty('voice', voices[voice_index].id)
            self.engine.setProperty('rate', 175)  # Speed of speech
        except Exception as e:
            print(f"Error initializing speech engine: {e}")
            self.engine = None
            
        # Debug mode flag
        self.debug_mode = True
            
        # Knowledge base for common questions
        self.knowledge_base = self.load_knowledge_base()
        
        # Load science knowledge data
        self.science_knowledge = self.load_science_knowledge()
        
        try:
            # Create a connection pool with explicit configuration
            connection_config = MYSQL_CONFIG.copy()
            connection_config['pool_name'] = 'mypool'
            connection_config['pool_size'] = 5
            connection_config['connect_timeout'] = 10
            
            # Check if SSL certificate exists before using it
            if 'ssl_ca' in connection_config and not os.path.exists(connection_config['ssl_ca']):
                print(f"SSL CA file not found: {connection_config['ssl_ca']}")
                del connection_config['ssl_ca']
                
            self.connection_pool = mysql.connector.pooling.MySQLConnectionPool(**connection_config)
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
            'read_text': ['read the last text', 'last captured text', 'read captured text', 'what was the last text'],
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
        
        # Initialize pygame for sound effects
        try:
            pygame.mixer.init()
            self.listening_sound = None
            try:
                self.listening_sound = pygame.mixer.Sound('sounds/listening.wav')
            except Exception as e:
                print(f"Listening sound file not found: {e}")
        except Exception as e:
            print(f"Error initializing pygame mixer: {e}")
            self.listening_sound = None
            
        self.is_active = True
        
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
        
        # Add more facts here
        knowledge["Who is the prime minister of India"] = "Currently, Narendra Modi is the Prime Minister of India. He was first elected in 2014 and won re-election in 2019."
        knowledge["What is the capital of France"] = "Paris is the capital city of France."
        knowledge["What is the speed of light"] = "The speed of light in a vacuum is 299,792,458 meters per second, or about 186,282 miles per second."
        knowledge["Who invented the telephone"] = "Alexander Graham Bell is credited with inventing the first practical telephone in 1876."
        knowledge["What is the tallest building in the world"] = "The Burj Khalifa in Dubai, United Arab Emirates is currently the tallest building in the world, standing at 828 meters (2,717 feet)."
        
        return knowledge
        
    def load_science_knowledge(self):
        """Load science-related knowledge from JSON file"""
        try:
            # First try to find the knowledge file in the same directory as the script
            knowledge_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_data.json")
            
            # If file doesn't exist, try other common locations
            if not os.path.exists(knowledge_file_path):
                # Try current working directory
                knowledge_file_path = "knowledge_data.json"
                
                # If still not found, use default knowledge
                if not os.path.exists(knowledge_file_path):
                    print("Knowledge data file not found. Using default knowledge.")
                    return self.create_default_science_knowledge()
            
            with open(knowledge_file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception as e:
            print(f"Error loading science knowledge data: {e}")
            return self.create_default_science_knowledge()
    
    def create_default_science_knowledge(self):
        """Create default science knowledge if file can't be loaded"""
        return {
            "science": {
                "physics": {
                    "newton's laws": "1. An object at rest stays at rest, and an object in motion stays in motion unless acted upon by a force. 2. Force equals mass times acceleration (F=ma). 3. For every action, there is an equal and opposite reaction.",
                    "gravity": "Gravity is a force that attracts objects with mass toward each other. On Earth, gravity gives weight to objects and causes them to fall when dropped."
                },
                "chemistry": {
                    "periodic table": "The periodic table is a tabular arrangement of chemical elements organized by atomic number, electron configuration, and chemical properties.",
                    "atoms": "Atoms are the basic units of matter consisting of a nucleus (containing protons and neutrons) surrounded by electrons."
                },
                "biology": {
                    "photosynthesis": "Photosynthesis is the process by which plants and some other organisms convert light energy into chemical energy that can be used to fuel the organism's activities.",
                    "cells": "Cells are the basic structural and functional units of all living organisms. They are often called the 'building blocks of life'."
                }
            },
            "math": {
                "pi": "Pi (π) is the ratio of a circle's circumference to its diameter, approximately equal to 3.14159.",
                "pythagoras theorem": "In a right-angled triangle, the square of the length of the hypotenuse equals the sum of the squares of the lengths of the other two sides (a² + b² = c²)."
            },
            "history": {
                "world war 2": "World War II was a global war that lasted from 1939 to 1945, involving many of the world's nations organized into two opposing military alliances: the Allies and the Axis.",
                "ancient egypt": "Ancient Egypt was a civilization in Northeastern Africa that flourished along the Nile River from about 3100 BCE to 30 BCE, known for its pyramids, pharaohs, and cultural achievements."
            },
            "geography": {
                "continents": "Earth has seven continents: Africa, Antarctica, Asia, Australia, Europe, North America, and South America.",
                "oceans": "Earth has five oceans: Pacific, Atlantic, Indian, Southern, and Arctic."
            }
        }
    
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
            else:
                # Generate multiplication table on-the-fly
                number = int(number)
                table = "\n".join([f"{number} × {i} = {number * i}" for i in range(1, 11)])
                return f"Multiplication table of {number}:\n{table}"
        
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
            conversion_terms = conversion.split('to')
            if all(term in query_lower for term in conversion_terms):
                return info
            
        # Handle simple unit conversions on-the-fly
        conversion_match = re.search(r'(\d+(?:\.\d+)?)\s*(kilometers?|km|meters?|m|grams?|g|kilograms?|kg)\s*(?:to|in)\s*(kilometers?|km|meters?|m|grams?|g|kilograms?|kg)', query_lower)
        if conversion_match:
            try:
                value = float(conversion_match.group(1))
                from_unit = conversion_match.group(2).lower()
                to_unit = conversion_match.group(3).lower()
                
                # Standardize units
                if from_unit in ['kilometer', 'kilometers', 'km']:
                    from_unit = 'km'
                elif from_unit in ['meter', 'meters', 'm']:
                    from_unit = 'm'
                elif from_unit in ['gram', 'grams', 'g']:
                    from_unit = 'g'
                elif from_unit in ['kilogram', 'kilograms', 'kg']:
                    from_unit = 'kg'
                    
                if to_unit in ['kilometer', 'kilometers', 'km']:
                    to_unit = 'km'
                elif to_unit in ['meter', 'meters', 'm']:
                    to_unit = 'm'
                elif to_unit in ['gram', 'grams', 'g']:
                    to_unit = 'g'
                elif to_unit in ['kilogram', 'kilograms', 'kg']:
                    to_unit = 'kg'
                
                # Perform conversion
                if from_unit == 'km' and to_unit == 'm':
                    result = value * 1000
                    return f"{value} kilometers is equal to {result} meters."
                elif from_unit == 'm' and to_unit == 'km':
                    result = value / 1000
                    return f"{value} meters is equal to {result} kilometers."
                elif from_unit == 'kg' and to_unit == 'g':
                    result = value * 1000
                    return f"{value} kilograms is equal to {result} grams."
                elif from_unit == 'g' and to_unit == 'kg':
                    result = value / 1000
                    return f"{value} grams is equal to {result} kilograms."
            except Exception as e:
                if self.debug_mode:
                    print(f"Error in unit conversion: {e}")
        
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
        
        # Check for specific countries or capitals
        country_match = re.search(r"capital of ([a-zA-Z ]+)", query_lower)
        if country_match:
            country_name = country_match.group(1).strip()
            # Hardcoded common country-capital pairs
            capitals = {
                "india": "New Delhi",
                "usa": "Washington, D.C.",
                "united states": "Washington, D.C.",
                "uk": "London",
                "united kingdom": "London",
                "japan": "Tokyo",
                "china": "Beijing",
                "france": "Paris",
                "germany": "Berlin",
                "russia": "Moscow",
                "brazil": "Brasília",
                "australia": "Canberra",
                "canada": "Ottawa",
                "italy": "Rome",
                "spain": "Madrid",
                "mexico": "Mexico City",
                "south korea": "Seoul",
                "indonesia": "Jakarta"
            }
            
            for country, capital in capitals.items():
                if country == country_name or country in country_name:
                    return f"The capital of {country.title()} is {capital}."
        
        # If no direct match was found, check for keywords in any geography topic
        for topic, info in geography_data.items():
            if isinstance(info, str):
                keywords = topic.split()
                for keyword in keywords:
                    if len(keyword) > 3 and keyword.lower() in query_lower:
                        return info
        
        return None
    
    def listen(self):
        """Listen for user input and convert speech to text"""
        if not self.microphone:
            print("Microphone not available. Please enter text input:")
            return input("> ")
            
        # Play listening sound if available
        if self.listening_sound:
            self.listening_sound.play()
            
        text = ""
        try:
            with self.microphone as source:
                print("Listening...")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=5)
                
            print("Recognizing...")
            text = self.recognizer.recognize_google(audio)
            print(f"You said: {text}")
            
        except sr.WaitTimeoutError:
            self.speak("I didn't hear anything. Please try again.")
        except sr.UnknownValueError:
            self.speak("Sorry, I didn't understand that.")
        except sr.RequestError as e:
            self.speak("Could not request results; check your network connection.")
            if self.debug_mode:
                print(f"Recognition error: {e}")
        except Exception as e:
            if self.debug_mode:
                print(f"Error in listen method: {e}")
            self.speak("Something went wrong while listening. Please try again.")
            
        return text
    
    def speak(self, text):
        """Convert text to speech"""
        print(f"{self.name}: {text}")
        
        if self.engine:
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                if self.debug_mode:
                    print(f"Speech engine error: {e}")
                print("Error speaking. Falling back to text only.")
                
    def categorize_query(self, query):
        """Categorize the query into one of the predefined categories"""
        query_lower = query.lower()
        
        # Check for cached response
        if query_lower in self.query_cache:
            return "cached", self.query_cache[query_lower]
            
        for category, keywords in self.categories.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return category, None
                    
        # Check for calculation expressions
        if re.search(r'[0-9+\-*/()^]', query_lower):
            return "calculation", None
            
        # Default to general category
        return "general", None
        
    def search_wikipedia(self, query):
        """Search for information on Wikipedia"""
        try:
            import wikipedia
            # Remove common question phrases
            clean_query = query.lower()
            for phrase in ['what is', 'who is', 'tell me about', 'define']:
                clean_query = clean_query.replace(phrase, '')
            
            # Get a summary from Wikipedia
            summary = wikipedia.summary(clean_query.strip(), sentences=3)
            return summary
        except Exception as e:
            if self.debug_mode:
                print(f"Wikipedia search error: {e}")
            return f"I couldn't find reliable information about {query}."
    
    def get_news(self):
        """Get the latest news headlines"""
        try:
            # BBC News RSS feed
            url = "http://feeds.bbci.co.uk/news/world/rss.xml"
            response = requests.get(url, timeout=5)
            soup = BeautifulSoup(response.content, 'xml')
            items = soup.find_all('item', limit=5)
            
            if not items:
                return "I couldn't retrieve the latest news."
                
            news_text = "Here are the latest headlines:\n\n"
            for item in items:
                title = item.title.text
                news_text += f"- {title}\n"
                
            return news_text
            
        except Exception as e:
            if self.debug_mode:
                print(f"News retrieval error: {e}")
            return "I couldn't retrieve the latest news. Please check your internet connection."
    
    def get_weather(self, location="local"):
        """Get weather information"""
        # For a real implementation, you might use a weather API like OpenWeatherMap
        return "I'm sorry, but I don't have real-time weather data access. You would need to integrate a weather API to get current weather information."
    
    def calculate(self, expression):
        """Evaluate a mathematical expression"""
        try:
            # Remove words like 'calculate', 'compute', etc.
            for word in ['calculate', 'compute', 'what is']:
                expression = expression.replace(word, '')
                
            # Replace words with symbols
            expression = expression.replace('plus', '+')
            expression = expression.replace('minus', '-')
            expression = expression.replace('times', '*')
            expression = expression.replace('multiplied by', '*')
            expression = expression.replace('divided by', '/')
            
            # Clean the expression
            expression = re.sub(r'[^0-9+\-*/().\s]', '', expression).strip()
            
            # Evaluate the expression
            result = eval(expression)
            return f"The result of {expression} is {result}"
        except Exception as e:
            if self.debug_mode:
                print(f"Calculation error: {e}")
            return "I couldn't calculate that. Please check the expression and try again."
    
    def web_search(self, query):
        """Perform a web search"""
        # This is a placeholder. In a real implementation, you might use a search API.
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        try:
            webbrowser.open(search_url)
            return f"I've opened a web search for '{query}'."
        except Exception as e:
            if self.debug_mode:
                print(f"Web search error: {e}")
            return "I couldn't open the web browser. Please try again later."
    
    def log_query(self, query, response, category):
        """Log the query to the database"""
        if not self.connection_pool:
            if self.debug_mode:
                print("Database connection pool not available. Skipping logging.")
            return
            
        try:
            connection = self.connection_pool.get_connection()
            cursor = connection.cursor()
            
            # Create table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS query_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    query TEXT NOT NULL,
                    response TEXT,
                    category VARCHAR(50),
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Insert the query log
            insert_query = "INSERT INTO query_logs (query, response, category) VALUES (%s, %s, %s)"
            cursor.execute(insert_query, (query, response[:1000] if response else None, category))
            
            connection.commit()
            cursor.close()
            connection.close()
            
        except Exception as e:
            if self.debug_mode:
                print(f"Database logging error: {e}")
    
    def add_to_memory(self, query, response):
        """Add query and response to conversation memory"""
        self.conversation_memory.append((query, response))
        if len(self.conversation_memory) > self.memory_limit:
            self.conversation_memory.pop(0)  # Remove oldest entry
    
    def get_response_from_memory(self, query):
        """Check if we have a similar query in memory"""
        query_tokens = set(word_tokenize(query.lower()))
        stop_words = set(stopwords.words('english'))
        query_tokens = [word for word in query_tokens if word not in stop_words]
        
        best_match = None
        best_score = 0
        
        for past_query, past_response in self.conversation_memory:
            past_tokens = set(word_tokenize(past_query.lower()))
            past_tokens = [word for word in past_tokens if word not in stop_words]
            
            # Calculate similarity
            common_words = set(query_tokens).intersection(set(past_tokens))
            score = len(common_words) / max(len(query_tokens), len(past_tokens)) if max(len(query_tokens), len(past_tokens)) > 0 else 0
            
            if score > best_score and score > 0.7:  # Threshold for similarity
                best_score = score
                best_match = past_response
                
        return best_match
    
    def process_query(self, query):
        """Process the user's query and generate a response"""
        if not query:
            return "I didn't catch that. Can you please repeat?"
            
        # Check conversation memory first
        memory_response = self.get_response_from_memory(query)
        if memory_response:
            return memory_response
            
        # Categorize the query
        category, cached_response = self.categorize_query(query)
        
        # Check if we have a cached response
        if cached_response:
            return cached_response
            
        # Process based on category
        response = ""
        
        if category == "time":
            current_time = datetime.datetime.now().strftime("%I:%M %p")
            response = f"The current time is {current_time}."
            
        elif category == "date":
            current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")
            response = f"Today is {current_date}."
            
        elif category == "weather":
            response = self.get_weather()
            
        elif category == "wikipedia":
            response = self.search_wikipedia(query)
            
        elif category == "news":
            response = self.get_news()
            
        elif category == "calculation":
            response = self.calculate(query)
            
        elif category == "web_search":
            response = self.web_search(query)
            
        elif category == "greeting":
            response = f"Hello! I'm {self.name}, your smart assistant. How can I help you today?"
            
        elif category == "goodbye":
            response = "Goodbye! Have a great day!"
            self.is_active = False
            
        elif category == "about":
            response = f"I'm {self.name}, a smart voice assistant. I can help you with time, date, weather, news, calculations, web searches, and answer general questions."
            
        elif category == "science":
            science_response = self.get_science_info(query)
            if science_response:
                response = science_response
            else:
                response = "I don't have specific information about that scientific topic. Would you like me to search the web for it?"
                
        elif category == "math":
            math_response = self.get_math_info(query)
            if math_response:
                response = math_response
            else:
                response = "I don't have information on that mathematical concept. Would you like me to calculate something for you?"
                
        elif category == "history":
            history_response = self.get_history_info(query)
            if history_response:
                response = history_response
            else:
                response = "I don't have specific information about that historical topic. Would you like me to search for it?"
                
        elif category == "geography":
            geography_response = self.get_geography_info(query)
            if geography_response:
                response = geography_response
            else:
                response = "I don't have specific information about that geographical topic. Would you like me to search for it?"
                
        else:
            # Check knowledge base
            for key, value in self.knowledge_base.items():
                if key.lower() in query.lower():
                    response = value
                    break
            
            if not response:
                try:
                    # Try to use a more sophisticated search using TF-IDF
                    vectorizer = TfidfVectorizer()
                    knowledge_keys = list(self.knowledge_base.keys())
                    tfidf_matrix = vectorizer.fit_transform(knowledge_keys)
                    query_vector = vectorizer.transform([query])
                    
                    # Calculate similarity with all knowledge base keys
                    similarities = cosine_similarity(query_vector, tfidf_matrix).flatten()
                    
                    # Find the most similar if above threshold
                    if max(similarities) > 0.3:  # Threshold
                        best_match_index = similarities.argmax()
                        response = self.knowledge_base[knowledge_keys[best_match_index]]
                except Exception as e:
                    if self.debug_mode:
                        print(f"TF-IDF error: {e}")
            
            # If still no response, give a generic one
            if not response:
                response = "I'm not sure how to answer that. Would you like me to search the web for you?"
        
        # Cache the response for future use
        self.query_cache[query.lower()] = response
        
        # Add to conversation memory
        self.add_to_memory(query, response)
        
        # Log the query
        self.log_query(query, response, category)
        
        return response
        
    def run(self):
        """Main loop for the assistant"""
        while self.is_active:
            query = self.listen()
            if query:
                response = self.process_query(query)
                self.speak(response)
                
                # Handle exit commands
                if not self.is_active:
                    break

def main():
    assistant = SmartAssistant(name="Jarvis", voice_index=0)
    assistant.run()

if __name__ == "__main__":
    main()