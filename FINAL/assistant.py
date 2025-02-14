import speech_recognition as sr
import pyttsx3
import google.generativeai as genai
import sys
import time
from google.cloud import vision, translate_v2
import os

# Initialize Google PaLM API
GOOGLE_API_KEY = 'AIzaSyAy2CSsv4_dASgpUxq_VcR6S2jgGd-IrNE'  # Get from https://makersuite.google.com/app/apikey
genai.configure(api_key=GOOGLE_API_KEY)

# Initialize the model
model = genai.GenerativeModel('gemini-pro')

# Initialize the recognizer and the text-to-speech engine
recognizer = sr.Recognizer()

# Initialize Vision API client
try:
    vision_client = vision.ImageAnnotatorClient()
    translate_client = translate_v2.Client()
except Exception as e:
    print(f"Error initializing Google Cloud clients: {str(e)}")
    sys.exit(1)

try:
    engine = pyttsx3.init()
    # Configure voice settings
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[1].id)  # Index 1 for female voice
    engine.setProperty('rate', 175)  # Speed of speech
    engine.setProperty('volume', 1.0)  # Volume level
except Exception as e:
    print(f"Error initializing text-to-speech engine: {str(e)}")
    sys.exit(1)

# Function to convert text to speech
def speak(text):
    try:
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"Error in speech synthesis: {str(e)}")

# Function to listen to the user's voice and convert it to text
def listen():
    with sr.Microphone() as source:
        print("\nListening...")
        recognizer.pause_threshold = 1
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
        except sr.WaitTimeoutError:
            print("No speech detected within timeout")
            return None

        try:
            print("Recognizing...")
            query = recognizer.recognize_google(audio, language="en-US")
            print(f"You: {query}")
            return query.lower()
        except sr.UnknownValueError:
            print("Sorry, I did not understand that.")
            speak("Sorry, I did not understand that. Please try again.")
            return None
        except sr.RequestError as e:
            print(f"Could not request results; {e}")
            speak("Sorry, my speech service is down. Please try again later.")
            return None

# Add new function to detect text from image
def detect_text_from_image(image_path):
    try:
        with open(image_path, "rb") as image_file:
            content = image_file.read()
        
        image = vision.Image(content=content)
        response = vision_client.text_detection(image=image)
        
        if not response.text_annotations:
            return None
        
        return response.text_annotations[0].description
    except Exception as e:
        print(f"Error in text detection: {str(e)}")
        return None

# Function to generate AI response using Google PaLM
def generate_response(user_input, conversation_history, ocr_context=None):
    try:
        # Prepare the context from conversation history
        context = ""
        if conversation_history:
            for msg in conversation_history[-3:]:
                context += f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}\n"
        
        # Add OCR context if available
        ocr_context_prompt = ""
        if ocr_context:
            ocr_context_prompt = f"""
            The following text was extracted from an image:
            {ocr_context}
            
            Please use this text as context when relevant to the user's query.
            """
        
        # Prepare the prompt
        prompt = f"""You are Alice, a helpful and knowledgeable AI assistant. 
        {ocr_context_prompt}
        
        Previous conversation:
        {context}
        
        User: {user_input}
        
        Provide a detailed and helpful response while maintaining a friendly tone."""

        # Generate response
        response = model.generate_content(prompt)
        ai_response = response.text.strip()
        
        # Update conversation history
        new_history = conversation_history + [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": ai_response}
        ]
        
        return ai_response, new_history

    except Exception as e:
        print(f"Error generating response: {str(e)}")
        return "I apologize, but I'm having trouble processing that right now.", conversation_history

# Function to process the user's query
def process_query(query, conversation_history, ocr_context=None):
    if any(word in query for word in ["exit", "quit", "goodbye", "bye"]):
        speak("Goodbye! Have a great day!")
        sys.exit(0)
    
    # Get response
    response, new_history = generate_response(query, conversation_history, ocr_context)
    
    # Break long responses into sentences for better speech synthesis
    sentences = response.replace('!', '.').replace('?', '?.').split('.')
    print(f"\nAssistant: {response}")
    
    # Speak each sentence with a small pause between them
    for sentence in sentences:
        sentence = sentence.strip()
        if sentence:
            speak(sentence)
            time.sleep(0.3)
    
    return new_history

# Main loop
if __name__ == "__main__":
    print("Initializing AI Assistant...")
    speak("Hello! I'm Alice, your AI assistant. I can help you with general questions and analyze text from images. How can I help you today?")
    
    conversation_history = []
    current_ocr_text = None
    
    while True:
        try:
            query = listen()
            if query:
                # Check for image analysis commands
                if "analyze image" in query or "read image" in query:
                    speak("Please specify the image path.")
                    image_path = listen()
                    if image_path:
                        current_ocr_text = detect_text_from_image(image_path)
                        if current_ocr_text:
                            speak("I've read the text from the image. What would you like to know about it?")
                        else:
                            speak("I couldn't detect any text in the image.")
                    continue
                
                # Process query with OCR context if available
                conversation_history = process_query(query, conversation_history, current_ocr_text)
                
                # Limit conversation history
                if len(conversation_history) > 6:
                    conversation_history = conversation_history[-6:]
                time.sleep(0.5)
                
        except KeyboardInterrupt:
            print("\nGoodbye!")
            speak("Goodbye! Have a great day!")
            sys.exit(0)
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            speak("I encountered an error. Please try again.")