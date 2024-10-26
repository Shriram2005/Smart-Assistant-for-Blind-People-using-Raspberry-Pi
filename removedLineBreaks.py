import cv2
import pytesseract
from googletrans import Translator
from gtts import gTTS
import os
import time
from playsound import playsound  # Library to play sound

# Specify the path to Tesseract executable for Windows users
pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Shriram\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'  # Update this path

def capture_and_translate(target_lang='mr'):
    # Initialize OpenCV to capture video
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    print("Press 'c' to capture an image and extract text, 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame.")
            break

        # Show the video frame to the user
        cv2.imshow('Camera Feed', frame)

        # Wait for the user to press 'c' to capture or 'q' to quit
        key = cv2.waitKey(1) & 0xFF
        if key == ord('c'):
            # Save the captured frame as an image
            image_path = "captured_image.png"
            cv2.imwrite(image_path, frame)
            print("Image captured!")

            # Notify the user that the image was captured
            notification_text = "Image captured"
            tts_notify = gTTS(notification_text, lang='en')
            tts_notify.save("capture_notification.mp3")
            playsound("capture_notification.mp3")

            # Perform OCR to extract text from the image
            extracted_text = pytesseract.image_to_string(image_path)
            print(f"Extracted Text (raw): {extracted_text}")

            # Remove line breaks and commas
            processed_text = " ".join(extracted_text.replace(",", "").splitlines())
            print(f"Processed Text: {processed_text}")

            # Initialize the translator and translate the processed text
            translator = Translator()
            try:
                translated_text = translator.translate(processed_text, dest=target_lang).text
                print(f"Translated Text ({target_lang}): {translated_text}")

                # Convert the translated text to speech
                tts = gTTS(translated_text, lang=target_lang)
                tts.save("translated_audio.mp3")
                print("Playing translated audio...")

                # Play the audio
                playsound("translated_audio.mp3")

            except Exception as e:
                print(f"Translation Error: {e}")

        elif key == ord('q'):
            print("Exiting program...")
            break

    # Release the camera and close the window
    cap.release()
    cv2.destroyAllWindows()

# Run the capture and translation function in an infinite loop
while True:
    capture_and_translate(target_lang='mr')  # You can change 'mr' to the target language code
