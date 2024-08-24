from gtts import gTTS
import pytesseract
import cv2
from PIL import Image
import os

# Initialize OpenCV for capturing an image
webcam = cv2.VideoCapture(0)

while True:
    try:
        check, frame = webcam.read()
        cv2.imshow("Capturing", frame)
        key = cv2.waitKey(1)
        if key == ord('z'):
            cv2.imwrite(filename='saved_img.jpg', img=frame)
            webcam.release()
            pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Shriram\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
            
            # Using multiple language with Tesseract
            string = pytesseract.image_to_string('saved_img.jpg', lang='eng+hin+mar')
            print(string)

            # Convert the extracted text to speech
            tts = gTTS(text=string, lang='hi')
            tts.save("output.mp3")
            os.system("start output.mp3")  # This will play the audio file on Windows

            print("Image saved!")
            cv2.destroyAllWindows()
            break

    except KeyboardInterrupt:
        print("Turning off camera.")
        webcam.release()
        print("Camera off.")
        print("Program ended.")
        cv2.destroyAllWindows()
        break
