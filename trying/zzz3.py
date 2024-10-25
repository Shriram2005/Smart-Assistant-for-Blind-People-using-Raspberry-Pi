import cv2
import pytesseract
from googletrans import Translator
from gtts import gTTS
import os

# Specify the path to Tesseract executable for Windows users
pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Shriram\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'  # Update this path

def capture_and_translate(target_lang='hi'):  # Updated target_lang to 'hi' for Hindi
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
            image_path = "../captured_image.png"
            cv2.imwrite(image_path, frame)
            print("Image captured! Extracting text...")

            # Perform OCR to extract text from the image
            extracted_text = pytesseract.image_to_string(image_path)
            print(f"Extracted Text: {extracted_text}")

            # Initialize the translator and translate the extracted text
            translator = Translator()
            try:
                translation = translator.translate(extracted_text, dest=target_lang)
                if translation and translation.text:
                    translated_text = translation.text
                    print(f"Translated Text ({target_lang}): {translated_text}")

                    # Convert the translated text to speech
                    tts = gTTS(translated_text, lang=target_lang)
                    audio_path = "translated_audio.mp3"
                    tts.save(audio_path)
                    print(f"Audio saved at {audio_path}")

                    # Check if the audio file exists and is not empty
                    if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                        print("Playing translated audio...")
                        # Play the audio
                        os.system(f"start {audio_path}")  # For Windows
                    else:
                        print("Error: Audio file was not created or is empty.")
                else:
                    print("Error: Translation result is None or empty.")

            except Exception as e:
                print(f"Translation Error: {e}")

        elif key == ord('q'):
            break

    # Release the camera and close the window
    cap.release()
    cv2.destroyAllWindows()

# Run the capture and translation function
capture_and_translate(target_lang='hi')  # Changed to 'hi' for Hindi translation