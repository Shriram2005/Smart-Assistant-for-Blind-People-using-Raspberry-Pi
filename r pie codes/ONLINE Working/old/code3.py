import cv2
import pytesseract
from googletrans import Translator
from gtts import gTTS
import os
import matplotlib.pyplot as plt

# Specify the path to Tesseract executable for Linux users
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

        # Show the video frame to the user using Matplotlib
        plt.imshow(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        plt.axis('off')  # Hide axes
        plt.show(block=False)
        plt.pause(0.001)  # Pause to allow the image to render

        # Wait for user input
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
    plt.close()

# Run the capture and translation function
capture_and_translate(url="http://192.168.43.1:8080/video", target_lang='mr')
