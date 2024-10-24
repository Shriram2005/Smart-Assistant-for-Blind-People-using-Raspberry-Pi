#
# import cv2
# import pytesseract
# from googletrans import Translator
# import speech_recognition as sr
# import pyaudio
#
# pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Shriram\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
#
# # Initialize speech recognition and translator
# r = sr.Recognizer()
# translator = Translator()
#
# def capture_image():
#     # Capture image using webcam
#     cap = cv2.VideoCapture(0)
#     ret, frame = cap.read()
#     cv2.imwrite('captured_image.jpg', frame)
#     cap.release()
#     cv2.destroyAllWindows()
#
# def extract_text(image_path):
#
#     # Extract text from image using Tesseract-OCR
#     text = pytesseract.image_to_string(image_path)
#     return text
#
# def translate_text(text, language):
#     # Translate text using Google Translate
#     result = translator.translate(text, dest=language)
#     return result.text
#
# def recognize_speech():
#     # Recognize speech using SpeechRecognition
#     with sr.Microphone() as source:
#         audio = r.listen(source)
#         try:
#             language = r.recognize_google(audio).lower()
#             return language
#         except sr.UnknownValueError:
#             print("Speech recognition could not understand audio")
#             return None
#
# def main():
#     print("Say 'capture' to capture image, 'translate' to translate text, or 'exit' to quit.")
#     while True:
#         command = recognize_speech()
#         if command == 'capture':
#             capture_image()
#             image_path = 'captured_image.jpg'
#             text = extract_text(image_path)
#             print("Extracted Text:", text)
#         elif command == 'translate':
#             language = recognize_speech()
#             if language:
#                 text = extract_text('captured_image.jpg')
#                 translated_text = translate_text(text, language)
#                 print("Translated Text:", translated_text)
#         elif command == 'exit':
#             break
#         else:
#             print("Invalid command. Please try again.")
#
# if __name__ == "__main__":
#     main()

import cv2
import pytesseract
from googletrans import Translator
import speech_recognition as sr
import pyaudio

# Initialize speech recognition and translator
r = sr.Recognizer()
translator = Translator()

def capture_image():
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cv2.imwrite('../captured_image.jpg', frame)
    cap.release()
    cv2.destroyAllWindows()

def extract_text(image_path):
    text = pytesseract.image_to_string(image_path)
    return text

def translate_text(text, language):
    try:
        result = translator.translate(text, dest=language)
        return result.text
    except Exception as e:
        print(f"Translation error: {str(e)}")
        return None

def recognize_speech():
    with sr.Microphone() as source:
        audio = r.listen(source)
        try:
            language = r.recognize_google(audio).lower()
            return language
        except sr.UnknownValueError:
            print("Speech recognition could not understand audio")
            return None

def main():
    pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Shriram\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
    print("Say 'capture' to capture image, 'translate' to translate text, or 'exit' to quit.")
    while True:
        command = recognize_speech()
        if command == 'capture':
            capture_image()
            image_path = '../captured_image.jpg'
            text = extract_text(image_path)
            print(f"Extracted text: {text}")
        elif command == 'translate':
            language = recognize_speech()
            print(f"Recognized language: {language}")
            text = extract_text('../captured_image.jpg')
            translated_text = translate_text(text, language)
            if translated_text:
                print(f"Translated text: {translated_text}")
        elif command == 'exit':
            break
        else:
            print("Invalid command. Please try again.")

if __name__ == "__main__":
    main()


