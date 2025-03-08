import cv2
import numpy as np
import os
import time
import pyttsx3
import re

# Install PaddleOCR if not already installed
try:
    from paddleocr import PaddleOCR
except ImportError:
    print("Installing PaddleOCR...")
    os.system("pip install paddlepaddle paddleocr")
    from paddleocr import PaddleOCR


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


def main():
    # Initialize camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    # Initialize OCR with a model optimized for handwritten text
    ocr = PaddleOCR(
        use_angle_cls=True,  # Use text angle detection
        lang='en',  # Language
        use_gpu=False,  # CPU mode for compatibility
        show_log=False,  # Disable logs
        rec_model_dir='inference/en_PP-OCRv3_rec_infer',  # Handwritten model
        det_model_dir='inference/en_PP-OCRv3_det_infer'  # Detection model
    )

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

            # Perform OCR
            result = ocr.ocr(filename, cls=True)

            if result:
                # Extract text and confidence
                texts = []
                confidences = []

                # PaddleOCR structure: [[[points], [text, confidence]], ...]
                for line in result[0]:
                    if len(line) >= 2:
                        text, confidence = line[1]
                        texts.append(text)
                        confidences.append(confidence)

                if texts:
                    # Join text lines
                    full_text = "\n".join(texts)
                    cleaned_text = clean_text(full_text)

                    # Calculate average confidence
                    avg_conf = sum(confidences) / len(confidences) if confidences else 0

                    # Display results
                    print("\n--- Recognized Text ---")
                    print(cleaned_text)
                    print(f"Average confidence: {avg_conf:.2f}")
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
                    print("No text detected.")
            else:
                print("OCR processing failed or no text detected.")

    # Clean up
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()