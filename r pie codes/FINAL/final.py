import cv2
import pytesseract
from googletrans import Translator
from gtts import gTTS
import os
import RPi.GPIO as GPIO
import time
from picamera2 import Picamera2
from time import sleep

# Set up Tesseract executable path for Linux users
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'  # Adjust the path if necessary

# GPIO setup
BUTTON_PIN = 18  # GPIO pin where the button is connected
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # Pull-down resistor

# Global variables for audio paths
original_text_audio_path = "original_audio.mp3"
translated_text_audio_path_1 = "translated_audio_1.mp3"
translated_text_audio_path_2 = "translated_audio_2.mp3"
capture_audio_path = "capture_sound.mp3"
no_text_audio_path = "no_text_found.mp3"
translation_complete_audio_path = "translation_complete.mp3"

# State to track button presses in the sequence
button_press_count = 0

# Initialize the Picamera2
camera = Picamera2()

# Audio feedback for image capture
capture_feedback = gTTS("Image captured", lang="en")
capture_feedback.save(capture_audio_path)

# Audio feedback for no text found
no_text_feedback = gTTS("No text found", lang="en")
no_text_feedback.save(no_text_audio_path)

# Audio feedback for translation complete
translation_complete_feedback = gTTS("Translation complete", lang="en")
translation_complete_feedback.save(translation_complete_audio_path)

def capture_and_translate(target_lang1='hi', target_lang2='mr'):
    print("Capturing image...")

    # Capture image using the Picamera2
    image_path = "captured_image.jpg"
    camera.start()
    time.sleep(2)  # Give time for the camera to adjust
    camera.capture_file(image_path)
    camera.stop()

    # Play capture sound to indicate the image was captured
    os.system(f"mpg123 {capture_audio_path}")
    print("Image captured! Extracting text...")

    # Perform OCR to extract text from the image
    extracted_text = pytesseract.image_to_string(image_path)
    # Remove line breaks and commas
    extracted_text = " ".join(extracted_text.replace(",", "").splitlines()).strip()
    print(f"Extracted Text: {extracted_text}")

    # Check if any text was found
    if not extracted_text:
        print("No text found in the image.")
        os.system(f"mpg123 {no_text_audio_path}")
        return False

    # Save audio in the original language
    tts_original = gTTS(extracted_text, lang='en')  # Adjust the source language as needed
    tts_original.save(original_text_audio_path)

    # Initialize the translator and translate the extracted text
    translator = Translator()
    try:
        # First translated language
        translated_text_1 = translator.translate(extracted_text, dest=target_lang1).text
        print(f"Translated Text 1 ({target_lang1}): {translated_text_1}")
        tts_translated_1 = gTTS(translated_text_1, lang=target_lang1)
        tts_translated_1.save(translated_text_audio_path_1)

        # Second translated language
        #translated_text_2 = translator.translate(extracted_text, dest=target_lang2).text
        #print(f"Translated Text 2 ({target_lang2}): {translated_text_2}")
        #tts_translated_2 = gTTS(translated_text_2, lang=target_lang2)
        #tts_translated_2.save(translated_text_audio_path_2)

        print("Text translation and audio generation complete.")

        # Play translation complete audio
        os.system(f"mpg123 {translation_complete_audio_path}")

    except Exception as e:
        print(f"Translation Error: {e}")
        return False

    return True

# Function to handle the sequence of button presses
def handle_button_press():
    global button_press_count

    if button_press_count == 0:
        # First press: Capture image and perform translations
        print("Button pressed to capture image and translate text.")
        if capture_and_translate(target_lang1='hi', target_lang2='mr'):
            button_press_count += 1
        else:
            print("Capture or translation failed. Please try again.")
    elif button_press_count == 1:
        # Second press: Play audio in original language
        print("Playing audio in original language...")
        os.system(f"mpg123 {original_text_audio_path}")
        button_press_count += 1
    elif button_press_count == 2:
        # Third press: Play audio in the first translated language
        print("Playing audio in first translated language...")
        os.system(f"mpg123 {translated_text_audio_path_1}")
        button_press_count = 0  # Reset count to restart the cycle

# Function to wait for button press
def wait_for_button_press():
    print("Press button to start the capture-translate-audio cycle.")

    while True:
        if GPIO.input(BUTTON_PIN) == GPIO.HIGH:
            print("Button pressed!")
            handle_button_press()
            time.sleep(1)  # Debounce delay

# Run the button listening function in an infinite loop
try:
    wait_for_button_press()
except KeyboardInterrupt:
    print("Program stopped by user.")
finally:
    GPIO.cleanup()


