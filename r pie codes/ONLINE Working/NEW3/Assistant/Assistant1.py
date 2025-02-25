import speech_recognition as sr
import pyttsx3
import google.generativeai as genai
import sys
import time

# Initialize Google PaLM API
GOOGLE_API_KEY = 'AIzaSyAy2CSsv4_dASgpUxq_VcR6S2jgGd-IrNE'  # Get from https://makersuite.google.com/app/apikey
genai.configure(api_key=GOOGLE_API_KEY)

# Initialize the model
model = genai.GenerativeModel('gemini-pro')

# Initialize the recognizer and the text-to-speech engine
recognizer = sr.Recognizer()

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

# Function to generate AI response using Google PaLM
def generate_response(user_input, conversation_history):
    try:
        # Prepare the context from conversation history
        context = ""
        if conversation_history:
            for msg in conversation_history[-3:]:  # Use last 3 messages for context
                context += f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}\n"
        
        # Prepare the prompt
        prompt = f"""You are Alice, a helpful and knowledgeable AI assistant. 
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
def process_query(query, conversation_history):
    if any(word in query for word in ["exit", "quit", "goodbye", "bye"]):
        speak("Goodbye! Have a great day!")
        sys.exit(0)
    
    # Get response
    response, new_history = generate_response(query, conversation_history)
    
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
    speak("Hello! I'm Alice, your AI assistant. How can I help you today?")
    
    conversation_history = []
    while True:
        try:
            query = listen()
            if query:
                conversation_history = process_query(query, conversation_history)
                # Limit conversation history
                if len(conversation_history) > 6:  # Keep last 3 exchanges (6 messages)
                    conversation_history = conversation_history[-6:]
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nGoodbye!")
            speak("Goodbye! Have a great day!")
            sys.exit(0)
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            speak("I encountered an error. Please try again.")