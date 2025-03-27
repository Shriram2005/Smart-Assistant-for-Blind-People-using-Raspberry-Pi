import os
import time
import threading
import queue
import json
import sounddevice as sd
from vosk import Model, KaldiRecognizer
from gtts import gTTS
from pynput import keyboard
from datetime import datetime
import tkinter as tk
import webbrowser
import wikipedia
import requests
import cv2
from threading import Event

# Global Variables
listening = False
stt_queue = queue.Queue()  # Queue to handle STT and TTS tasks
model = None
video_thread = None  # Thread for playing the video
video_thread_stop_event = Event()
interaction_timeout = 10  # Timeout in seconds after TTS completes

# Q&A Database
qa_dict = {
    "location": "Sandip University is located in Nashik, Maharashtra, India on Trimbak Road.",
    "courses": "Sandip University offers courses in engineering, management, law, pharmacy, design, science, and more.",
    "founder": "Sandip University was founded by Dr. Sandip N. Jha in 2014.",
    "mission": "The mission is to provide quality education, foster innovation, and empower students for global challenges.",
    "contact": "You can reach Sandip University at +91-2594-222571.",
    "admission": "Admission requirements vary by program, but generally include passing 12th grade or equivalent and entrance exams where applicable.",
    "campus": "The campus spans over 250 acres with modern facilities.",
    "facilities": "The university provides hostels, libraries, sports complexes, labs, and Wi-Fi across the campus."
}

# Load the Vosk model
MODEL_PATH = r'C:\Users\Shriram\Downloads\vosk-model-small-en-us-0.15'
def load_model():
    global model
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"Model not found at {MODEL_PATH}")
    model = Model(MODEL_PATH)
    print("Vosk model loaded.")

# TTS Function (non-blocking)
def speak(text, gui):
    def play_audio():
        tts = gTTS(text=text, lang="en")
        output_file = "/tmp/output.mp3"
        tts.save(output_file)
        gui.update_output(text)
        os.system(f"mpg123 -q {output_file}")
        os.remove(output_file)

        # Restart idle video after timeout
        threading.Timer(interaction_timeout, restart_idle_video).start()

    threading.Thread(target=play_audio, daemon=True).start()

# Restart Idle Video
def restart_idle_video():
    global video_thread, video_thread_stop_event
    if not listening:
        stop_idle_video()  # Ensure the current video thread is stopped
        video_thread_stop_event.clear()
        video_thread = threading.Thread(target=play_idle_video, args=("/home/saklen/Downloads/Sandip University Nashik Campus.mp4", video_thread_stop_event), daemon=True)
        video_thread.start()

# Stop Idle Video
def stop_idle_video():
    global video_thread_stop_event
    video_thread_stop_event.set()
    time.sleep(1)  # Allow the video thread to stop cleanly

# Weather Function
def get_weather(city="Nashik"):
    url = f"https://api.open-meteo.com/v1/forecast?latitude=20.01&longitude=73.78&current_weather=true"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if "current_weather" in data:
            temp = data["current_weather"]["temperature"]
            windspeed = data["current_weather"]["windspeed"]
            return f"The current temperature in {city} is {temp}°C with a windspeed of {windspeed} km/h."
        else:
            return "Sorry, I couldn't fetch the weather right now."
    except Exception as e:
        print(f"Weather fetch error: {e}")
        return "Sorry, I couldn't fetch the weather right now."

# Wikipedia Search
def wikipedia_search(query):
    try:
        result = wikipedia.summary(query, sentences=2)
        return result
    except Exception as e:
        print(f"Error fetching Wikipedia data: {e}")
        return "Sorry, I couldn't find anything on Wikipedia about that."

# Process Command Function
def process_command(text, gui):
    text = text.lower()
    gui.update_output(f"You said: {text}")
    if "weather" in text:
        weather = get_weather()
        gui.update_output(weather)
        speak(weather, gui)
    elif "time" in text:
        current_time = datetime.now().strftime("%I:%M %p")
        gui.update_output(f"The current time is {current_time}")
        speak(f"The current time is {current_time}", gui)
    elif "admission" in text:
        answer = qa_dict.get("admission", "I don't have information on that.")
        gui.update_output(answer)
        speak(answer, gui)
    elif "play song" in text:
        gui.update_output("Playing song...")
        speak("Playing song...", gui)
        os.system("xdg-open /path/to/your/song.mp3")  # Replace with the path to your song file
    elif "open youtube" in text:
        gui.update_output("Opening YouTube...")
        speak("Opening YouTube...", gui)
        webbrowser.get("chromium-browser").open("https://www.youtube.com")
    elif "wikipedia" in text:
        query = text.replace("wikipedia", "").strip()
        if query:
            result = wikipedia_search(query)
            gui.update_output(result)
            speak(result, gui)
        else:
            gui.update_output("Please specify what to search on Wikipedia.")
            speak("Please specify what to search on Wikipedia.", gui)
    elif any(keyword in text for keyword in qa_dict):
        for keyword, response in qa_dict.items():
            if keyword in text:
                gui.update_output(response)
                speak(response, gui)
                return
    else:
        gui.update_output("I'm sorry, I didn't understand that.")
        speak("I'm sorry, I didn't understand that.", gui)

# Speech Recognition Function
def recognize_voice(gui):
    global listening
    listening = True
    stop_idle_video()  # Stop the idle video

    def audio_callback(indata, frames, time, status):
        if status:
            print(status)
        stt_queue.put(bytes(indata))

    recognizer = KaldiRecognizer(model, 16000)
    with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype="int16",
                           channels=1, callback=audio_callback):
        gui.update_output("Listening...")
        while listening:
            data = stt_queue.get()
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "")
                process_command(text, gui)
                break
        listening = False
        gui.update_output("Stopped Listening.")

# Play Idle Video
def play_idle_video(video_path, stop_event):
    while not stop_event.is_set():
        cap = cv2.VideoCapture(video_path)
        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            resized_frame = cv2.resize(frame, (1920, 1080))
            cv2.namedWindow("Idle Video", cv2.WND_PROP_FULLSCREEN)
            cv2.setWindowProperty("Idle Video", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            cv2.imshow("Idle Video", resized_frame)

            if cv2.waitKey(30) & 0xFF == ord("q"):
                break

        cap.release()
        cv2.destroyAllWindows()

# GUI Class
class RobotAssistantGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Jarvis Assistant")
        self.configure(bg="black")
        self.attributes("-fullscreen", True)

        self.output_label = tk.Label(self, text="", fg="white", bg="black", font=("Arial", 24), wraplength=1000, justify="center")
        self.output_label.pack(expand=True)

    def update_output(self, text):
        self.output_label.config(text=text)

# Listen for 'S' key
def listen_for_keypress(gui):
    def on_press(key):
        global listening
        try:
            if key.char == 's' and not listening:
                threading.Thread(target=recognize_voice, args=(gui,), daemon=True).start()
        except AttributeError:
            pass

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

# Main Function
def main():
    global video_thread_stop_event, video_thread
    gui = RobotAssistantGUI()
    threading.Thread(target=listen_for_keypress, args=(gui,), daemon=True).start()
    load_model()

    video_path = "/home/saklen/Downloads/Sandip University Nashik Campus.mp4"
    video_thread = threading.Thread(target=play_idle_video, args=(video_path, video_thread_stop_event), daemon=True)
    video_thread.start()

    gui.mainloop()

    stop_idle_video()
    video_thread.join()

if __name__ == "__main__":
    main()