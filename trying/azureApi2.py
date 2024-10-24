import pytesseract
import azure.cognitiveservices.speech as speechsdk
from azure.core.credentials import AzureKeyCredential
from azure.ai.translation.text import TextTranslationClient

pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Shriram\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'

# OCR
def capture_text(image_path):
    text = pytesseract.image_to_string(image_path)
    return text

# TTS using Azure Speech Service
def text_to_speech(text, language):
    speech_key = "1dd934dd88c248908896a9e4f73b358d"
    service_region = "eastus"
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    audio_config = speechsdk.audio.AudioOutputConfig(filename="output.mp3")
    speech_config.speech_synthesis_language = language

    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    synthesizer.speak_text_async(text).get()
    return "output.mp3"

# Speech Recognition using Azure Speech Service
def recognize_speech():
    speech_key = "1dd934dd88c248908896a9e4f73b358d"
    service_region = "eastus"
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)

    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    result = recognizer.recognize_once_async().get()

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return result.text
    else:
        return None

# Machine Translation (Microsoft Azure)
def translate_text(text, target_language):
    credential = AzureKeyCredential("22c7b7c4be2142daa86a49198a65944d")
    client = TextTranslationClient(endpoint="https://api.cognitive.microsofttranslator.com/", credential=credential)
    response = client.translate(content=[text], to=[target_language])
    return response[0].translations[0].text

# Main Program
def main():
    image_path = "../captured_image.jpg"
    text = capture_text(image_path)
    print("Captured Text:", text)

    # TTS
    language = "en-US"
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
        translated_audio_file = text_to_speech(translated_text, "hi-IN")
        print("Speaking translated text...")
main()