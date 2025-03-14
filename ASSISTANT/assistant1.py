import datetime
import os
import re
import threading
import time
import webbrowser
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

# Download necessary NLTK data
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')

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
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                
                if self.listening_sound:
                    pygame.mixer.stop()
                
                try:
                    text = self.recognizer.recognize_google(audio)
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
        """Determine the category of a user query"""
        if not query:
            return None
            
        # Check each category for matching keywords
        for category, keywords in self.categories.items():
            for keyword in keywords:
                if keyword in query:
                    return category
                    
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
        # Extract the topic from the query
        query = query.replace("who is", "").replace("what is", "").replace("tell me about", "")
        query = query.replace("wikipedia", "").replace("define", "").strip()
        
        try:
            # Web scraping approach for Wikipedia summary
            url = f"https://en.wikipedia.org/wiki/{query.replace(' ', '_')}"
            response = requests.get(url)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                paragraphs = soup.find_all('p')
                
                text = ""
                for p in paragraphs:
                    if len(p.text.strip()) > 50:  # Skip short paragraphs
                        text = p.text
                        break
                        
                if text:
                    # Clean up the text
                    text = re.sub(r'\[\d+\]', '', text)  # Remove reference numbers
                    sentences = text.split('. ')
                    short_text = '. '.join(sentences[:3]) + '.'  # First three sentences
                    
                    return short_text
                else:
                    return f"I couldn't find information about {query} on Wikipedia."
            else:
                return f"I couldn't find a Wikipedia page for {query}."
                
        except Exception as e:
            if self.debug_mode:
                print(f"Wikipedia error: {e}")
            return f"I'm having trouble searching Wikipedia right now. Please try again later."
            
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
            query = query.replace("search for", "").replace("google", "").replace("find", "").replace("look up", "").strip()
            
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
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
                
            # Fallback to opening browser
            webbrowser.open(url)
            return f"I've opened a web search for '{query}' in your browser."
            
        except Exception as e:
            if self.debug_mode:
                print(f"Web search error: {e}")
            return f"I couldn't find information about '{query}' online. Please try a different search term."
    
    def handle_calculation(self, query):
        """Handle mathematical calculations"""
        # Extract the calculation part from the query
        query = query.replace("calculate", "").replace("compute", "").replace("solve", "").strip()
        
        # Replace word operators with symbols
        query = query.replace("plus", "+").replace("minus", "-").replace("times", "").replace("multiplied by", "")
        query = query.replace("divided by", "/").replace("over", "/")
        
        # Basic calculation using eval (with security measures)
        try:
            # Only allow basic arithmetic operations
            allowed_chars = set("0123456789+-*/().^ ")
            if not all(c in allowed_chars for c in query):
                return "I can only perform basic arithmetic calculations."
                
            # Replace ^ with ** for exponentiation
            query = query.replace("^", "")
            
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
    
    def process_query(self, query):
        """Process the user's query and generate a response"""
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
            
        # Determine query category
        category = self.categorize_query(query)
        
        # Process based on category
        response = ""
        if category == "time":
            response = self.get_current_time()
        elif category == "date":
            response = self.get_current_date()
        elif category == "weather":
            # Extract location if provided
            location_match = re.search(r'weather in ([a-zA-Z ]+)', query)
            location = location_match.group(1) if location_match else ""
            response = self.get_weather(location)
        elif category == "wikipedia":
            response = self.get_wikipedia_info(query)
        elif category == "news":
            response = self.get_news()
        elif category == "calculation":
            response = self.handle_calculation(query)
        elif category == "web_search":
            # Check knowledge base first
            kb_result = self.find_in_knowledge_base(query)
            if kb_result:
                response = kb_result
            else:
                response = self.search_web(query)
        else:
            # General knowledge - check knowledge base
            kb_result = self.find_in_knowledge_base(query)
            if kb_result:
                response = kb_result
            else:
                response = self.search_web(query)
                
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
    assistant = SmartAssistant(name="Einstein", voice_index=0)
    
    # Run the assistant
    assistant.run()