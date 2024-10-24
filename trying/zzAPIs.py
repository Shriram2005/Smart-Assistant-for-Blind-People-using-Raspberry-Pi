
import pytesseract
from gtts import gTTS
import speech_recognition as sr
from azure.core.credentials import AzureKeyCredential
from azure.ai.translation_text import TranslationTextClient

# OCR
def capture_text(image_path):
    text = pytesseract.image_to_string(image_path)
    return text

# TTS
def text_to_speech(text, language):
    tts = gTTS(text=text, lang=language)
    tts.save("output.mp3")
    return "output.mp3"

# Speech Recognition
def recognize_speech():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        audio = r.listen(source)
    try:
        voice_command = r.recognize_google(audio, language="en-US")
        return voice_command
    except sr.UnknownValueError:
        return None

# Machine Translation (Microsoft Azure)
def translate_text(text, target_language):
    credential = AzureKeyCredential("YOUR_AZURE_KEY")
    client = TranslationTextClient("YOUR_AZURE_ENDPOINT", credential)
    translation = client.translate_text(text, target_language)
    return translation[0].translation

# Main Program
def main():
    image_path = "path/to/image.jpg"
    text = capture_text(image_path)
    print("Captured Text:", text)

    # TTS
    language = "en"
    audio_file = text_to_speech(text, language)
    print("Speaking captured text...")

    # Speech Recognition
    voice_command = recognize_speech()
    if voice_command:
        print("Voice Command:", voice_command)

        # Machine Translation
        target_language = "hi"  # Hindi
        translated_text = translate_text(text, target_language)
        print("Translated Text:", translated_text)

        # TTS (translated text)
        translated_audio_file = text_to_speech(translated_text, "hi")
        print("Speaking translated text...")

    main()


#DeepL Translator


import pytesseract
from gtts import gTTS
import speech_recognition as sr
import deepl

# OCR
def capture_text(image_path):
    text = pytesseract.image_to_string(image_path)
    return text

# TTS
def text_to_speech(text, language):
    tts = gTTS(text=text, lang=language)
    tts.save("output.mp3")
    return "output.mp3"

# Speech Recognition
def recognize_speech():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        audio = r.listen(source)
    try:
        voice_command = r.recognize_google(audio, language="en-US")
        return voice_command
    except sr.UnknownValueError:
        return None

# Machine Translation (DeepL)
def translate_text(text, target_language):
    auth_key = "YOUR_DEEPL_KEY"
    translator = deepl.Translator(auth_key)
    translation = translator.translate_text(text, target_lang=target_language)
    return translation.text

# Main Program
def main():
    image_path = "path/to/image.jpg"
    text = capture_text(image_path)
    print("Captured Text:", text)

    # TTS
    language = "en"
    audio_file = text_to_speech(text, language)
    print("Speaking captured text...")

    # Speech Recognition
    voice_command = recognize_speech()
    if voice_command:
        print("Voice Command:", voice_command)

        # Machine Translation
        target_language = "HI"  # Hindi
        translated_text = translate_text(text, target_language)
        print("Translated Text:", translated_text)

        # TTS (translated text)
        translated_audio_file = text_to_speech(translated_text, "hi")
        print("Speaking translated text...")

    main()


#IBM Watson Language Translator


import pytesseract
from gtts import gTTS
import speech_recognition as sr
from ibm_watson import LanguageTranslatorV3

# OCR
def capture_text(image_path):
    text = pytesseract.image_to_string(image_path)
    return text

# TTS
def text_to_speech(text, language):
    tts = gTTS(text=text, lang=language)
    tts.save("output.mp3")
    return "output.mp3"

# Speech Recognition
def recognize_speech():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        audio = r.listen(source)
    try:
        voice_command = r.recognize_google(audio, language="en-US")
        return voice_command
    except sr.UnknownValueError:
        return None

# Machine Translation (IBM Watson)
def translate_text(text, target_language):
    version = "YOUR_IBM_WATSON_VERSION"
    api