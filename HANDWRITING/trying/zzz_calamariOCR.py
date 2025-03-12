import cv2
import numpy as np
import os
import time
import pyttsx3
import re
import subprocess
import sys


# Ensure all dependencies are installed
def install_dependencies():
    print("Installing required dependencies...")
    
    # First install tensorflow as it's a prerequisite
    try:
        import tensorflow
    except ImportError:
        print("Installing TensorFlow...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "tensorflow==2.10.0"])

    required_packages = [
        "opencv-python",
        "pyttsx3",
        "numpy",
        "calamari_ocr[tensorflow]"
    ]

    for package in required_packages:
        try:
            if package.startswith("calamari"):
                print(f"Installing {package}...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-deps", package])
                # Install additional Calamari dependencies
                subprocess.check_call([sys.executable, "-m", "pip", "install", 
                    "edit_distance", 
                    "networkx", 
                    "scipy", 
                    "tqdm",
                    "h5py",
                    "pillow",
                    "shapely"
                ])
            else:
                if not package.split('[')[0] in sys.modules:
                    print(f"Installing {package}...")
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        except Exception as e:
            print(f"Error installing {package}: {str(e)}")
            if package.startswith("calamari"):
                print("Failed to install Calamari OCR. Please try installing it manually:")
                print("pip install calamari_ocr[tensorflow]")
                sys.exit(1)


# Install dependencies first
print("Checking and installing dependencies...")
install_dependencies()

# Now import Calamari OCR
try:
    from calamari_ocr.scripts.predict import run_prediction
    from calamari_ocr.ocr import Predictor, MultiPredictor
    from calamari_ocr.ocr.voting import voter_from_voter_list
    print("Successfully imported Calamari OCR!")
except ImportError as e:
    print(f"Error importing Calamari OCR: {str(e)}")
    print("Make sure it's properly installed. You might need to restart your Python environment.")
    sys.exit(1)


def download_model():
    """Download Calamari model for handwriting recognition"""
    models_dir = "models"
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)

    # Default model directory
    model_path = os.path.join(models_dir, "handwritten_model")

    if not os.path.exists(model_path):
        print("Downloading handwritten text recognition model...")
        # Using a common handwritten text model
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "https://github.com/Calamari-OCR/calamari_models/releases/download/v1.0/antiqua_handwritten.zip"
        ])
        print("Model downloaded successfully.")

    return model_path


def deskew(image):
    """Deskew the image to straighten text"""
    try:
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Calculate skew angle
        coords = np.column_stack(np.where(gray > 0))
        angle = cv2.minAreaRect(coords)[-1]

        # Adjust angle
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        # Rotate image
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

        return rotated
    except:
        return image


def preprocess_image(image, mode="handwritten"):
    """Preprocess image for better OCR results"""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    if mode == "handwritten":
        # Apply adaptive thresholding
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY_INV, 11, 2)

        # Denoise
        kernel = np.ones((2, 2), np.uint8)
        opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

        # Invert back for OCR
        processed = cv2.bitwise_not(opening)
    else:
        # For printed text
        _, processed = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return processed


def clean_text(text):
    """Clean and normalize recognized text"""
    if not text:
        return ""

    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)

    # Remove non-printable characters
    text = ''.join(char for char in text if char.isprintable() or char.isspace())

    # Strip leading/trailing whitespace
    return text.strip()


def initialize_speech_engine():
    """Initialize the TTS engine"""
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)  # Speech rate
    engine.setProperty('volume', 0.9)  # Volume
    return engine


def initialize_calamari():
    """Initialize Calamari OCR with pretrained model"""
    # Check if models are available
    model_path = download_model()

    import glob

    # Look for models
    models = glob.glob(
        os.path.join(os.path.expanduser("~"), ".calamari", "models", "antiqua_handwritten", "*.ckpt.json"))

    if not models:
        print("No Calamari models found. Using default models...")
        # Use default models that come with Calamari
        models = ["antiqua_handwritten"]

    print(f"Using Calamari models: {models}")

    # Create predictor with the models
    predictor = MultiPredictor(
        checkpoints=models,
        voter=voter_from_voter_list(["confidence_voter_default_ctc"]),
        batch_size=1
    )

    return predictor


def main():
    # Initialize camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    # Initialize Calamari OCR
    try:
        predictor = initialize_calamari()
    except Exception as e:
        print(f"Failed to initialize Calamari OCR: {e}")
        print("Trying to continue with basic recognition...")
        predictor = None

    # Initialize speech engine
    engine = initialize_speech_engine()

    # Create window and set parameters
    cv2.namedWindow("Handwriting Recognition - Press 'c' to capture")

    # Create directory for saving data
    os.makedirs("handwriting_data", exist_ok=True)

    print("Press 'c' to capture and recognize handwritten text. Press 'q' to quit.")
    print("Hold the paper still and ensure good lighting for best results.")

    # Processing mode (0: handwritten, 1: printed)
    mode = 0

    while True:
        # Capture frame
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to capture image.")
            break

        # Create copy for display
        display_frame = frame.copy()

        # Draw guide rectangle
        h, w = frame.shape[:2]
        cv2.rectangle(display_frame, (int(w / 4), int(h / 4)), (int(3 * w / 4), int(3 * h / 4)), (0, 255, 0), 2)
        cv2.putText(display_frame, "Position text here", (int(w / 4), int(h / 4) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Show mode
        mode_name = "Handwritten" if mode == 0 else "Printed"
        cv2.putText(display_frame, f"Mode: {mode_name} (Press 'm' to switch)",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Show the frame
        cv2.imshow("Handwriting Recognition - Press 'c' to capture", display_frame)

        # Wait for key press
        key = cv2.waitKey(1) & 0xFF

        # Quit if 'q' is pressed
        if key == ord('q'):
            break

        # Switch mode if 'm' is pressed
        if key == ord('m'):
            mode = 1 - mode  # Toggle between 0 and 1

        # Process image when 'c' is pressed
        if key == ord('c'):
            # Extract region of interest
            roi = frame[int(h / 4):int(3 * h / 4), int(w / 4):int(3 * w / 4)]

            # Preprocess image
            deskewed = deskew(roi)
            processed = preprocess_image(deskewed, "handwritten" if mode == 0 else "printed")

            # Save the processed image
            timestamp = int(time.time())
            filename = f"handwriting_data/processed_{timestamp}.jpg"
            cv2.imwrite(filename, processed)

            # Show the processing steps
            cv2.imshow("Processed Image", processed)
            print("Processing image...")

            try:
                if predictor:
                    # Use Calamari for prediction
                    prediction = predictor.predict_single(filename)

                    # Extract text from prediction
                    recognized_text = prediction.sentence
                    cleaned_text = clean_text(recognized_text)
                    confidence = prediction.avg_char_probability

                    # Display results
                    print("\n--- Recognized Text ---")
                    print(cleaned_text)
                    print(f"Average confidence: {confidence:.2f}")
                    print("----------------------\n")

                    # Save the recognized text
                    with open(f"handwriting_data/text_{timestamp}.txt", "w") as f:
                        f.write(cleaned_text)

                    # Speak the text
                    if cleaned_text:
                        print("Speaking text... Press any key to stop.")
                        engine.say(cleaned_text)
                        engine.runAndWait()
                    else:
                        print("No readable text found.")
                else:
                    print("Calamari OCR not available.")
            except Exception as e:
                print(f"Error recognizing text: {e}")
                print("Make sure the Calamari models are correctly installed.")

    # Clean up
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()