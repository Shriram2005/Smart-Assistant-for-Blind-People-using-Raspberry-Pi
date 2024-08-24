import pytesseract
import cv2
from PIL import Image
import os
import pyttsx3


language = 'en'
engine = pyttsx3.init()
engine.setProperty('rate', 100) 
key = cv2. waitKey(1)
webcam = cv2.VideoCapture(0)
while True:
    try:
        check, frame = webcam.read()
        cv2.imshow("Capturing", frame)
        key = cv2.waitKey(1)
        if key == ord('z'):
            cv2.imwrite(filename='saved_img.jpg', img=frame)
            webcam.release()
            # pytesseract.pytesseract.tesseract_cmd = r'C:\Users\LENOVO\AppData\Tesseract_OCR\tesseract.exe'
            pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Shriram\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
            string = pytesseract.image_to_string('saved_img.jpg')
            print(string)

            engine.setProperty('rate', 125) 
            engine.say("hi")
            engine.say(string)
            engine.runAndWait()
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


