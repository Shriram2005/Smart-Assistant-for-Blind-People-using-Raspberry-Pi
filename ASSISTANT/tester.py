import cv2
import easyocr
from gensim.models import KeyedVectors
import pytesseract
import pygame
from gtts import gTTS
import os
import subprocess  # To interact with the `ollama` CLI
import sqlite3
import speech_recognition as sr
import wikipedia
from datetime import datetime

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"  # Workaround for an issue with Word2Vec

# Configure Tesseract OCR
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Database setup
conn = sqlite3.connect("smart_assistant.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS recent_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

# Load pre-trained Word2Vec model
word2vec_model_path = r"D:\project\smart-assistant\models\GoogleNews-vectors-negative300.bin"

try:
    word2vec_model = KeyedVectors.load_word2vec_format(word2vec_model_path, binary=True)
    print("Word2Vec model loaded successfully.")
except Exception as e:
    print(f"Error loading Word2Vec model: {e}")
    word2vec_model = None

def correct_text_with_word2vec(text, model):
    """Correct OCR text using Word2Vec."""
    corrected_words = []
    for word in text.split():
        if not word.isalnum() or len(word) < 2:       
            corrected_words.append(word)
            continue

        if word in model.key_to_index:
            corrected_words.append(word)
        else:
            try:
                similar_words = model.most_similar(word, topn=1)
                if similar_words:
                    corrected_words.append(similar_words[0][0])
                else:
                    corrected_words.append(word)
            except KeyError:
                corrected_words.append(word)
    return " ".join(corrected_words)

def speak_text(text, lang='en'):
    """Speak the given text using gTTS and play it using pygame."""
    try:
        tts = gTTS(text=text, lang=lang)
        audio_file = "temp_audio.mp3"
        tts.save(audio_file)

        pygame.mixer.init()
        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

        pygame.mixer.music.stop()
        pygame.mixer.quit()
        os.remove(audio_file)
    except Exception as e:
        print(f"Error in text-to-speech: {e}")

def save_to_database(text):
    """Save text to the database."""
    cursor.execute("INSERT INTO recent_data (text) VALUES (?)", (text,))
    conn.commit()

def answer_question_with_tinyllama(question):
    """Answer general knowledge questions using the TinyLlama model."""
    try:
        print("Using TinyLlama model to answer the question...")
        result = subprocess.run(
            ["ollama", "run", "tinyllama"],
            input=question.encode(),  # Pass as bytes
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            answer = result.stdout.strip()
            print(f"TinyLlama Answer: {answer}")
            speak_text(answer)
        else:
            print(f"TinyLlama model error: {result.stderr.strip()}")
            raise Exception(result.stderr.strip())
    except Exception as e:
        print(f"Error using TinyLlama model: {e}")
        speak_text("Sorry, I couldn't find an answer using TinyLlama. Trying Wikipedia...")
        try:
            summary = wikipedia.summary(question, sentences=2)
            print(f"Wikipedia Answer: {summary}")
            speak_text(summary)
        except Exception as e:
            print(f"Error using Wikipedia: {e}")
            speak_text("Sorry, I couldn't find an answer.")

def speech_to_speech():
    """Capture a question via speech, process it, and respond with speech."""
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("Listening for your question...")
            speak_text("Please ask your question.")
            try:
                audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)
                print("Processing your question...")
                question = recognizer.recognize_google(audio)
                print(f"You asked: {question}")
                speak_text(f"You asked: {question}")

                answer_question_with_tinyllama(question)
            except sr.UnknownValueError:
                print("Sorry, I could not understand your question.")
                speak_text("Sorry, I could not understand your question.")
            except sr.RequestError as e:
                print(f"Speech recognition service error: {e}")
                speak_text("Sorry, there was an error with the speech recognition service.")
    except OSError as e:
        print(f"Microphone error: {e}")
        speak_text("Sorry, I could not access the microphone.")

def main():
    while True:
        print("\nOptions: \n1. Capture Printed Text\n2. Capture from Camera\n3. Capture Handwritten Text\n4. Translate Text\n5. Get Recent Data\n6. Ask a Question\n7. Speech-to-Speech\n8. Get Date and Time\n9. Exit")
        speak_text("Please choose an option.")
        choice = input("Enter your choice: ").strip().lower()

        if choice in ["6", "ask a question"]:
            speak_text("What is your question?")
            question = input("Enter your question: ").strip()
            if question:
                answer_question_with_tinyllama(question)

        elif choice in ["7", "speech-to-speech"]:
            speech_to_speech()

        elif choice in ["8", "get date and time"]:
            now = datetime.now()
            current_time = now.strftime("%Y-%m-%d %H:%M:%S")
            print(f"Current Date and Time: {current_time}")
            speak_text(f"The current date and time is {current_time}.")

        elif choice in ["9", "exit"]:
            speak_text("Goodbye!")
            break

        else:
            speak_text("Invalid choice. Please try again.")

    conn.close()  # Close the database connection

if __name__ == "__main__":
    main()
