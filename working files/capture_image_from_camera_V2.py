import cv2
import pytesseract
from gtts import gTTS
import os
import deepl

# Specify the path to Tesseract executable for Windows users
pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Shriram\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'

def capture_text(image_path):
    text = pytesseract.image_to_string(image_path, lang='eng+hin+mar')
    return text

def text_to_speech(text, language):
    tts = gTTS(text=text, lang=language)
    tts.save("output.mp3")
    os.system("start output.mp3")  # This will play the audio file on Windows

def translate_text(text, target_language):
    auth_key = "YOUR_DEEPL_AUTH_KEY"  # Replace with your DeepL API authentication key
    translator = deepl.Translator(auth_key)
    translation = translator.translate_text(text, target_lang=target_language)
    return translation.text

# Initialize OpenCV for capturing an image
webcam = cv2.VideoCapture(0)

while True:
    try:
        check, frame = webcam.read()
        cv2.imshow("Capturing", frame)
        key = cv2.waitKey(1)
        if key == ord('z'):
            cv2.imwrite(filename='../saved_img.jpg', img=frame)
            webcam.release()
            cv2.destroyAllWindows()

            # Capture text from the image
            captured_text = capture_text('../saved_img.jpg')
            print("Captured Text:", captured_text)

            # Translate the captured text
            target_language = "HI"  # Hindi
            translated_text = translate_text(captured_text, target_language)
            print("Translated Text:", translated_text)

            # Convert the translated text to speech
            text_to_speech(translated_text, 'hi')
            break

    except KeyboardInterrupt:
        print("Turning off camera.")
        webcam.release()
        cv2.destroyAllWindows()
        break