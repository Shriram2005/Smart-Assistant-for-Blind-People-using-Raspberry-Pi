from google.cloud import vision
import io
import pyttsx3

# Set up Google Cloud Vision client
client = vision.ImageAnnotatorClient()

def detect_text(image_path):
    with io.open(image_path, 'rb') as image_file:
        content = image_file.read()

    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    if texts:
        return texts[0].description
    return ""

# Initialize text-to-speech engine
engine = pyttsx3.init()
engine.setProperty('rate', 125)

image_path = '../OCR_laptop_v2/saved_img.jpg'
text = detect_text(image_path)
print(text)

# Text-to-speech
engine.say("hi")
engine.say(text)
engine.runAndWait()
