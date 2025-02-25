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

# State to track button presses in the sequence
button_press_count = 0

# Initialize the Picamera2
camera = Picamera2()

def capture_and_translate(target_lang1='mr', target_lang2='hi'):
    print("Capturing image...")

    # Capture image using the Picamera2
    image_path = "captured_image.jpg"
    camera.start()
    time.sleep(2)  # Give time for the camera to adjust
    camera.capture_file(image_path)
    camera.stop()
    print("Image captured! Extracting text...")

    # Perform OCR to extract text from the image
    extracted_text = pytesseract.image_to_string(image_path)
    # Remove line breaks and commas
    extracted_text = " ".join(extracted_text.replace(",", "").splitlines())
    print(f"Extracted Text: {extracted_text}")

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
        translated_text_2 = translator.translate(extracted_text, dest=target_lang2).text
        print(f"Translated Text 2 ({target_lang2}): {translated_text_2}")
        tts_translated_2 = gTTS(translated_text_2, lang=target_lang2)
        tts_translated_2.save(translated_text_audio_path_2)

        print("Text translation and audio generation complete.")

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
        if capture_and_translate(target_lang1='mr', target_lang2='hi'):
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
        button_press_count += 1
    elif button_press_count == 3:
        # Fourth press: Play audio in the second translated language
        print("Playing audio in second translated language...")
        os.system(f"mpg123 {translated_text_audio_path_2}")
        button_press_count = 0  # Reset count to restart the cycle

# Function to wait for button press
def wait_for_button_press():
    print("Press button to start the capture-translate-audio cycle.")

    while True:
        if GPIO.input(BUTTON_PIN) == GPIO.HIGH:
            print("Button pressed!")
            handle_button_press()
            time.sleep(1)  # Debounce delay

# Run the button listening function
try:
    wait_for_button_press()
except KeyboardInterrupt:
    print("Program stopped by user.")
finally:
    GPIO.cleanup()
