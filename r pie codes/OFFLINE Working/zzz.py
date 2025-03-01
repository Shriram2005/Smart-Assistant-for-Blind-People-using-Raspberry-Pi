import cv2
import numpy as np
import pytesseract
import fasttext
from googletrans import Translator
from gtts import gTTS
import os
import RPi.GPIO as GPIO
import time
from picamera2 import Picamera2
from PIL import Image
import subprocess
import logging
from threading import Lock
import torch
import torchvision.transforms as transforms
from torchvision import models
import wget

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load pretrained fastText model for language detection
LANG_MODEL_PATH = "lid.176.bin"
if not os.path.exists(LANG_MODEL_PATH):
    logger.info("Downloading language detection model...")
    try:
        model_url = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin"
        wget.download(model_url, LANG_MODEL_PATH)
        logger.info("Model downloaded successfully")
    except Exception as e:
        logger.error(f"Failed to download language model: {str(e)}")
        logger.error("Please download manually from https://fasttext.cc/docs/en/language-identification.html")
        exit(1)
        
lang_model = fasttext.load_model(LANG_MODEL_PATH)

# Load deep learning OCR model for text detection
ocr_net = models.detection.fasterrcnn_resnet50_fpn(pretrained=True)
ocr_net.eval()

# Tesseract Configuration
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

# GPIO Configuration
BUTTON_PIN = 18
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Initialize camera
camera = Picamera2()
translator = Translator()
audio_lock = Lock()
current_audio_process = None

# Audio file paths
AUDIO_PATHS = {
    'capture': "capture_sound.mp3",
    'no_text': "no_text_found.mp3",
    'complete': "translation_complete.mp3",
    'ready': "ready_sound.mp3",
    'error': "error_sound.mp3"
}

def play_audio(audio_path):
    global current_audio_process
    with audio_lock:
        try:
            if current_audio_process:
                current_audio_process.terminate()
            current_audio_process = subprocess.Popen(['mpg123', '-q', audio_path])
        except Exception as e:
            logger.error(f"Audio playback failed: {str(e)}")

# Image Enhancement using Deep Learning
def detect_text_regions(image):
    transform = transforms.Compose([
        transforms.ToTensor()
    ])
    image_tensor = transform(image).unsqueeze(0)
    with torch.no_grad():
        predictions = ocr_net(image_tensor)[0]
    
    boxes = [predictions['boxes'][i] for i in range(len(predictions['scores'])) if predictions['scores'][i] > 0.5]
    return boxes

# Language Detection using fastText
def detect_language(text):
    if not text.strip():
        return None
    # Clean the text: replace newlines with spaces and normalize whitespace
    cleaned_text = ' '.join(text.split())
    try:
        prediction = lang_model.predict(cleaned_text)[0][0]
        return prediction.replace('__label__', '')
    except Exception as e:
        logger.error(f"Language detection failed: {str(e)}")
        return 'en'  # fallback to English if detection fails

def preprocess_image(image_path):
    image = Image.open(image_path).convert('RGB')
    text_boxes = detect_text_regions(image)
    
    if not text_boxes:
        return image_path
    
    image_np = np.array(image)
    for box in text_boxes:
        x1, y1, x2, y2 = map(int, box)
        roi = image_np[y1:y2, x1:x2]
        image_np = cv2.rectangle(image_np, (x1, y1), (x2, y2), (255, 0, 0), 2)
    
    preprocessed_path = "preprocessed_image.jpg"
    cv2.imwrite(preprocessed_path, image_np)
    return preprocessed_path

def extract_text(image_path):
    image = Image.open(image_path)
    text = pytesseract.image_to_string(image, config='--oem 3 --psm 6')
    detected_lang = detect_language(text)
    return text, detected_lang

def translate_text(text, target_lang):
    try:
        return translator.translate(text, dest=target_lang).text
    except Exception as e:
        logger.error(f"Translation failed: {str(e)}")
        return None

def capture_and_translate():
    camera.stop()
    config = camera.create_still_configuration(main={"size": (2592, 1944)})
    camera.configure(config)
    camera.start()
    time.sleep(2)
    image_path = "captured_image.jpg"
    camera.capture_file(image_path)
    camera.stop()
    play_audio(AUDIO_PATHS['capture'])
    processed_path = preprocess_image(image_path)
    extracted_text, detected_lang = extract_text(processed_path)
    
    if not extracted_text:
        play_audio(AUDIO_PATHS['no_text'])
        return False
    
    logger.info(f"Detected language: {detected_lang}")
    tts = gTTS(extracted_text, lang=detected_lang)
    tts.save("original_audio.mp3")
    
    translated_text = translate_text(extracted_text, 'en')
    if translated_text:
        tts = gTTS(translated_text, lang='en')
        tts.save("translated_audio.mp3")
    
    play_audio(AUDIO_PATHS['complete'])
    return True

def handle_button_press():
    if GPIO.input(BUTTON_PIN) == GPIO.HIGH:
        capture_and_translate()
        time.sleep(0.5)

def main():
    play_audio(AUDIO_PATHS['ready'])
    try:
        while True:
            handle_button_press()
    except KeyboardInterrupt:
        logger.info("Program stopped by user")
    finally:
        GPIO.cleanup()
        logger.info("System shutdown complete")

if __name__ == "__main__":
    main()