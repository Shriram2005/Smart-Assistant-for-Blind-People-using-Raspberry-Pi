import cv2
import pytesseract
from googletrans import Translator
from gtts import gTTS
import os

# Specify the path to Tesseract executable for Windows users
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'  # Adjust the path if necessary

def capture_and_translate(url, target_lang='mr'):
    # Initialize OpenCV to capture video from the IP Webcam stream
    cap = cv2.VideoCapture(url)

    if not cap.isOpened():
        print("Error: Could not open video stream.")
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
            print("Image captured! Extracting text...")

            # Perform OCR to extract text from the image
            extracted_text = pytesseract.image_to_string(image_path)
            print(f"Extracted Text: {extracted_text}")

            # Initialize the translator and translate the extracted text
            translator = Translator()
            try:
                translated_text = translator.translate(extracted_text, dest=target_lang).text
                print(f"Translated Text ({target_lang}): {translated_text}")

                # Convert the translated text to speech
                tts = gTTS(translated_text, lang=target_lang)
                tts.save("translated_audio.mp3")
                print("Playing translated audio...")

                # Play the audio
                os.system("mpg123 translated_audio.mp3")  # Install mpg123 if needed

            except Exception as e:
                print(f"Translation Error: {e}")

        elif key == ord('q'):
            break

    # Release the camera and close the window
    cap.release()
    cv2.destroyAllWindows()

# Run the capture and translation function
# Replace with the IP Webcam URL shown on your phone (e.g., http://192.168.43.1:8080/video)
capture_and_translate(url="http://192.168.43.1:8080/video", target_lang='mr')
