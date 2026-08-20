# 👁️ Smart Aid — AI & IoT Smart Assistant for Visually Impaired People

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-4B-C51A4A?style=for-the-badge&logo=raspberry-pi&logoColor=white)](https://www.raspberrypi.com/)
[![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Vision%20%7C%20Translate%20%7C%20TTS-4285F4?style=for-the-badge&logo=google-cloud&logoColor=white)](https://cloud.google.com/)
[![MySQL](https://img.shields.io/badge/Aiven%20Cloud-MySQL%20(SSL)-4479A1?style=for-the-badge&logo=mysql&logoColor=white)](https://aiven.io/)
[![Accessibility](https://img.shields.io/badge/Accessibility-Audio--First%20UI-2ea44f?style=for-the-badge)](https://github.com/)

---

## 📌 Overview

**Smart Aid** is an IoT and Cloud AI-powered assistive reading device built on **Raspberry Pi 4**. It empowers blind and visually impaired individuals to independently read printed documents, books, medicine labels, newspapers, and signboards without relying on Braille or human assistance.

With a **single physical push button**, the device captures an image of printed text, performs cloud Optical Character Recognition (OCR), automatically detects the language, translates it into regional languages (**English, Hindi, and Marathi**), and reads it aloud using natural AI speech. All scanned images and text logs are stored in a managed **Aiven MySQL Cloud Database** for audit logging and remote monitoring.

```
┌─────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│  Pi Camera v2   │ ───► │  Raspberry Pi 4 (Edge)  │ ───► │   Google Cloud APIs     │
│  (Image Input)  │      │  (Control & Audio Loop) │      │ (Vision, Translate,TTS) │
└─────────────────┘      └───────────┬─────────────┘      └────────────┬────────────┘
                                     │                                 │
                         ┌───────────▼─────────────┐                   │
                         │    Aiven Cloud MySQL    │ ◄─────────────────┘
                         │ (Encrypted Data Logs)   │
                         └─────────────────────────┘
```

---

## ✨ Key Features

- 📸 **Single-Button Camera Capture**: Automated capture with auto-exposure and fault-tolerant camera reinitialization (`@safe_camera_operation`).
- 🔍 **High-Accuracy Cloud OCR**: Powered by **Google Cloud Vision API** to recognize text across varied lighting conditions and font styles.
- 🌐 **Multilingual Translation**: Automatic language detection and translation into **English**, **Hindi**, and **Marathi** via **Google Cloud Translate API**.
- 🗣️ **Natural Speech Synthesis (TTS)**: Realistic speech generation using **Google Cloud Text-to-Speech** (WaveNet / Neural voices) played over `mpg123`.
- 🎧 **Audio-First Accessibility Interface**: Hands-free design providing clear voice and sound cues (shutter click, processing chime, ready prompt) at every stage.
- 🗄️ **Secure Cloud Database Logging**: Stores captured image binaries (`LONGBLOB`) and multilingual text logs into **Aiven MySQL** with SSL encryption and connection pooling (`MySQLConnectionPool`).
- 📊 **Web Dashboard**: Web interface to view captured scans, timestamps, extracted text, and translations.
- 🔌 **Offline Mode Available**: Includes a local fallback pipeline using **Tesseract OCR** and local TTS (`pyttsx3`/`espeak`) when internet access is unavailable.

---

## 🛠️ System Architecture & Hardware Pinout

### Hardware Components
1. **Raspberry Pi 4 Model B** (2GB/4GB/8GB RAM)
2. **Raspberry Pi Camera Module v2** (8MP, connected via CSI ribbon cable)
3. **Push Button** (Momentary switch connected to GPIO)
4. **Speaker / Headphones** (3.5mm audio jack or USB audio)
5. **5V/3A USB-C Power Supply**

### GPIO Pin Configuration

| Component | Raspberry Pi Pin (BCM) | Physical Pin Header | Notes |
| :--- | :--- | :--- | :--- |
| **Push Button (Terminal 1)** | `GPIO 18` | Pin 12 | Input pin with internal `PULL_DOWN` enabled |
| **Push Button (Terminal 2)** | `3.3V Power` | Pin 1 | When pressed, sends HIGH (3.3V) to GPIO 18 |
| **Camera Module** | CSI Port | Camera Connector | Dedicated camera bus |
| **Speaker** | 3.5mm Audio Out | Audio Jack | Audio output via `mpg123` |

```
  Raspberry Pi 4 GPIO
  ┌─────────────────────────┐
  │ [Pin 1]  3.3V ────────┐ │
  │                       │ │
  │ [Pin 12] GPIO 18 ───[Push Button]
  │ (Internal Pull-Down)    │
  └─────────────────────────┘
```

---

## 🔄 Interaction Flow (Button State Machine)

The device utilizes a simple single-button state machine designed specifically for visually impaired users:

1. **Press 1 (Capture & Process)**:
   - Plays shutter sound `capture_sound.mp3`.
   - Captures still image (`captured_image.jpg`).
   - Sends image to Google Cloud Vision for OCR.
   - Detects source language and generates translations (English, Hindi, Marathi).
   - Generates and downloads TTS MP3 audio files.
   - Saves record (Image + Texts) to Aiven MySQL database.
   - Plays `translation_complete.mp3`.
2. **Press 2**: Plays audio in the **Original Detected Language**.
3. **Press 3**: Plays **First Translated Language** (e.g., Hindi).
4. **Press 4**: Plays **Second Translated Language** (e.g., Marathi).
5. **Press 5**: Resets the state counter back to `0` for the next scan.

---

## 🚀 Getting Started

### 1. Prerequisites on Raspberry Pi

Ensure your Raspberry Pi is running Raspberry Pi OS (Bullseye or newer) and update system packages:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-picamera2 mpg123 libcamera-apps
```

### 2. Clone and Install Dependencies

```bash
git clone <repository-url>
cd "RPI Project/OCR_laptop_v1"
pip3 install -r requirements.txt
pip3 install google-cloud-vision google-cloud-translate google-cloud-texttospeech mysql-connector-python
```

### 3. Configure Google Cloud Credentials

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/).
2. Enable **Cloud Vision API**, **Cloud Translation API**, and **Cloud Text-to-Speech API**.
3. Create a Service Account, generate a JSON Key, and save it on the Raspberry Pi:
   ```bash
   /home/pi/gcloud.json
   ```
4. Export the environment variable (already configured in code):
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/home/pi/gcloud.json"
   ```

### 4. Configure Aiven Cloud MySQL

1. Obtain your Aiven MySQL connection details (Host, Port, User, Password).
2. Download the `ca.pem` SSL certificate and place it in `/home/pi/ca.pem`.
3. Verify your table schema in MySQL:
   ```sql
   CREATE TABLE IF NOT EXISTS captured_images (
       id INT AUTO_INCREMENT PRIMARY KEY,
       image LONGBLOB NOT NULL,
       original_text TEXT,
       detected_language VARCHAR(50),
       english_translation TEXT,
       hindi_translation TEXT,
       marathi_translation TEXT,
       timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

---

## 💻 Running the Application

### Start the Online Smart Aid Assistant

```bash
cd "OCR_laptop_v1/FINAL/Online Final"
python3 smart_aid.py
```
*Or use the launch script:*
```bash
bash start_smart_aid.sh
```
---

## 🛡️ Reliability & Fault Tolerance

- **Camera Auto-Recovery (`@safe_camera_operation`)**: Handles hardware lockups by catching exceptions, releasing the camera handle, and reinitializing `Picamera2`.
- **API Retry Decorators (`@retry.Retry`)**: Automatically retries Google API network calls during transient network hiccups (`DeadlineExceeded`).
- **Database Connection Pooling**: Pre-allocates a pool of 5 SSL connections, eliminating connection handshake latency on each button press.
- **Non-blocking Audio**: Executes `mpg123` via `subprocess.Popen` with automatic process cleanup (`pkill -f mpg123`) to prevent audio overlap.

---

## 👥 Authors & Acknowledgments

- **Developer**: Shriram Mange 
- **Platform**: Raspberry Pi & Google Cloud Platform
- **Database**: Aiven Cloud MySQL
