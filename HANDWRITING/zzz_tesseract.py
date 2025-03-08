import cv2
import pytesseract
import pyttsx3
import numpy as np
import os
import time
from collections import Counter
import re
import nltk
from nltk.corpus import words

try:
    nltk.data.find('corpora/words')
except LookupError:
    nltk.download('words')
english_words = set(words.words())


def update_speech_rate(val):
    """Update speech rate from trackbar."""
    # This function will be called when the speech rate trackbar is adjusted
    pass


def preprocess_normal(image, block_size, constant, blur_size, clahe_clip):
    """Normal preprocessing with adaptive thresholding."""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=clahe_clip, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(enhanced, (blur_size, blur_size), 0)

    # Apply adaptive thresholding
    binary = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, block_size, constant
    )

    # Morphological operations to clean up the image
    kernel = np.ones((2, 2), np.uint8)
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    return cleaned


def preprocess_high_contrast(image, blur_size):
    """High contrast preprocessing for better feature extraction."""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply Gaussian blur
    blurred = cv2.GaussianBlur(gray, (blur_size, blur_size), 0)

    # Apply Otsu's thresholding
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Morphological operations to clean up the image
    kernel = np.ones((2, 2), np.uint8)
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    return cleaned


def preprocess_edge_detection(image, blur_size):
    """Edge detection preprocessing for handwriting with low contrast."""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply Gaussian blur
    blurred = cv2.GaussianBlur(gray, (blur_size, blur_size), 0)

    # Apply Canny edge detection
    edges = cv2.Canny(blurred, 30, 100)

    # Dilate the edges to connect broken lines
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=1)

    return dilated


def preprocess_alternate(image):
    """Alternative preprocessing method for difficult texts."""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Bilateral filter preserves edges while removing noise
    bilateral = cv2.bilateralFilter(gray, 11, 17, 17)

    # Apply histogram equalization
    equalized = cv2.equalizeHist(bilateral)

    # Apply Otsu's thresholding
    _, binary = cv2.threshold(equalized, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    return binary


def preprocess_for_printed_text(image):
    """Specialized preprocessing for printed text."""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Enhance contrast
    enhanced = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)

    # Apply Gaussian blur
    blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)

    # Adaptive thresholding
    binary = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 15, 2
    )

    # Morphological operations
    kernel = np.ones((1, 1), np.uint8)
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    return cleaned


def deskew(image):
    """Deskew the image to correct rotation."""
    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Threshold the image
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Find all contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    # Find largest contour
    if not contours:
        return image

    largest_contour = max(contours, key=cv2.contourArea)

    # Find minimum area rectangle
    rect = cv2.minAreaRect(largest_contour)
    angle = rect[2]

    # Determine angle to rotate
    if angle < -45:
        angle = 90 + angle

    # Rotate the image
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    return rotated


def clean_text_for_speech(text):
    """Clean and normalize text for better speech synthesis."""
    # Replace common OCR errors
    replacements = {
        '|': 'I',
        '0': 'O',
        '1': 'I',
        '{': '(',
        '}': ')',
        '[': '(',
        ']': ')',
        '`': "'",
        '°': 'degrees',
        '•': 'bullet point',
        '©': 'copyright',
        '®': 'registered',
        '™': 'trademark',
        '€': 'euros',
        '£': 'pounds',
        '¥': 'yen',
        '—': '-',
        '–': '-',
        '…': '...',
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)

    # Add punctuation at the end if missing
    if text and text[-1] not in '.!?':
        text += '.'

    # Add spaces after punctuation if missing
    text = re.sub(r'([.!?])([A-Z])', r'\1 \2', text)

    # Spell check for common words (basic)
    words = text.split()
    corrected_words = []

    for word in words:
        # Keep punctuation and special characters separate
        word_only = re.sub(r'[^a-zA-Z]', '', word)
        if word_only.lower() in english_words or len(word_only) <= 2:
            corrected_words.append(word)
        else:
            # For now, keep the original word
            corrected_words.append(word)

    return ' '.join(corrected_words)


def speak_text_clearly(engine, text):
    """Speak text with enhanced clarity and natural pauses."""
    if not text:
        return

    # Split text into sentences for more natural pauses
    sentences = re.split(r'[.!?]', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    engine.setProperty('rate', cv2.getTrackbarPos("Speech Rate", "Handwriting Recognition - Press Enter to capture"))

    # Increase volume slightly
    engine.setProperty('volume', 0.95)

    for sentence in sentences:
        if sentence:
            engine.say(sentence)
            engine.runAndWait()
            # Small pause between sentences
            time.sleep(0.3)


def font_detection(image):
    """Basic font type detection."""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply Gaussian blur
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Edge detection
    edges = cv2.Canny(blurred, 50, 150)

    # Calculate edge density
    edge_density = np.sum(edges) / (edges.shape[0] * edges.shape[1])

    # Calculate variance of pixel intensities
    pixel_variance = np.var(gray)

    # Basic font classification based on features
    if edge_density > 15 and pixel_variance > 2000:
        return "Handwritten"
    elif edge_density > 10:
        return "Serif"
    else:
        return "Sans-serif"


def enhance_pronunciation(text):
    """Enhance text for better pronunciation by text-to-speech engines."""
    # Dictionary of common pronunciation challenges
    pronunciation_dict = {
        # Numbers and symbols
        '0': 'zero',
        '1': 'one',
        '2': 'two',
        '3': 'three',
        '4': 'four',
        '5': 'five',
        '6': 'six',
        '7': 'seven',
        '8': 'eight',
        '9': 'nine',
        '+': 'plus',
        '-': 'minus',
        '*': 'times',
        '/': 'divided by',
        '%': 'percent',
        '=': 'equals',
        # Common acronyms
        'NASA': 'N A S A',
        'FBI': 'F B I',
        'CIA': 'C I A',
        'HTML': 'H T M L',
        'CSS': 'C S S',
        'USA': 'U S A',
        'UK': 'U K',
        'EU': 'E U',
        'FAQ': 'F A Q',
        'DIY': 'D I Y',
        # Hard to pronounce words
        'worcestershire': 'wooster-sher',
        'quinoa': 'keen-wah',
        'acai': 'ah-sigh-ee',
        'cache': 'cash',
        'facade': 'fuh-sod',
    }

    # Split text while preserving delimiters
    tokens = re.findall(r'[\w\']+|[.,!?;]', text)

    # Replace words with their pronunciation alternatives
    for i, token in enumerate(tokens):
        if token.upper() in pronunciation_dict and token.isupper():  # For acronyms
            tokens[i] = pronunciation_dict[token.upper()]
        elif token in pronunciation_dict:  # For other replacements
            tokens[i] = pronunciation_dict[token]

    # Rejoin text
    enhanced_text = ' '.join(tokens)
    # Clean up spaces before punctuation
    enhanced_text = re.sub(r' ([.,!?;])', r'\1', enhanced_text)

    return enhanced_text


def main():
    # Initialize the camera with improved resolution
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    # Set higher resolution for better image quality
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    # Initialize text-to-speech engine with improved settings
    engine = pyttsx3.init()

    # Configure voice settings for clearer pronunciation
    voices = engine.getProperty('voices')
    # Use the first voice (usually higher quality)
    if voices:
        engine.setProperty('voice', voices[0].id)

    # Improve speech clarity
    engine.setProperty('rate', 150)  # Speed: lower is slower
    engine.setProperty('volume', 0.9)  # Volume: 0.0 to 1.0

    # Create a window with trackbars for advanced image adjustment
    cv2.namedWindow("Handwriting Recognition - Press Enter to capture")
    cv2.createTrackbar("Block Size", "Handwriting Recognition - Press Enter to capture", 11, 51, lambda x: None)
    cv2.createTrackbar("Constant", "Handwriting Recognition - Press Enter to capture", 2, 20, lambda x: None)
    cv2.createTrackbar("Blur", "Handwriting Recognition - Press Enter to capture", 5, 15, lambda x: None)
    cv2.createTrackbar("CLAHE Clip", "Handwriting Recognition - Press Enter to capture", 2, 10, lambda x: None)
    cv2.createTrackbar("Mode", "Handwriting Recognition - Press Enter to capture", 0, 4, lambda x: None)
    cv2.createTrackbar("Speech Rate", "Handwriting Recognition - Press Enter to capture", 150, 250, update_speech_rate)

    # Create directory for saving data if it doesn't exist
    os.makedirs("handwriting_data", exist_ok=True)

    # Tesseract language packs
    available_langs = "eng+osd"  # Default language

    # Try to detect if other languages are installed
    try:
        all_langs = pytesseract.get_languages()
        if all_langs:
            available_langs = "+".join(all_langs)
    except:
        pass

    print("Press Enter to capture and recognize text. Press 'q' to quit.")
    print("Hold the paper still and ensure good lighting for best results.")
    print(f"Available language packs: {available_langs}")

    while True:
        # Capture frame from camera
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to capture image.")
            break

        # Create a copy of the frame for display
        display_frame = frame.copy()

        # Draw a center rectangle as a guide for positioning text
        h, w = frame.shape[:2]
        cv2.rectangle(display_frame, (int(w / 4), int(h / 4)), (int(3 * w / 4), int(3 * h / 4)), (0, 255, 0), 2)
        cv2.putText(display_frame, "Position text here", (int(w / 4), int(h / 4) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Get current mode
        mode = cv2.getTrackbarPos("Mode", "Handwriting Recognition - Press Enter to capture")

        # Display information
        # Display information about current mode
        mode_names = ["Normal", "High Contrast", "Edge Detection", "Alternative", "Printed Text"]
        cv2.putText(display_frame, f"Mode: {mode_names[mode]}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Show the frame
        cv2.imshow("Handwriting Recognition - Press Enter to capture", display_frame)

        # Wait for key press
        key = cv2.waitKey(1) & 0xFF

        # Quit if 'q' is pressed
        if key == ord('q'):
            break

        # Process image when Enter is pressed
        if key == 13:  # Enter key
            # Capture region of interest
            roi = frame[int(h / 4):int(3 * h / 4), int(w / 4):int(3 * w / 4)]

            # Get current parameter values
            block_size = cv2.getTrackbarPos("Block Size", "Handwriting Recognition - Press Enter to capture")
            # Ensure block size is odd
            block_size = block_size if block_size % 2 == 1 else block_size + 1
            constant = cv2.getTrackbarPos("Constant", "Handwriting Recognition - Press Enter to capture")
            blur_size = cv2.getTrackbarPos("Blur", "Handwriting Recognition - Press Enter to capture")
            # Ensure blur size is odd
            blur_size = blur_size if blur_size % 2 == 1 else blur_size + 1
            clahe_clip = cv2.getTrackbarPos("CLAHE Clip", "Handwriting Recognition - Press Enter to capture")

            # Deskew the image
            deskewed = deskew(roi)

            # Apply preprocessing based on mode
            if mode == 0:
                processed = preprocess_normal(deskewed, block_size, constant, blur_size, clahe_clip)
            elif mode == 1:
                processed = preprocess_high_contrast(deskewed, blur_size)
            elif mode == 2:
                processed = preprocess_edge_detection(deskewed, blur_size)
            elif mode == 3:
                processed = preprocess_alternate(deskewed)
            else:
                processed = preprocess_for_printed_text(deskewed)

            # Save the processed image
            timestamp = int(time.time())
            cv2.imwrite(f"handwriting_data/processed_{timestamp}.jpg", processed)

            # Detect font type
            font_type = font_detection(roi)
            print(f"Detected font type: {font_type}")

            # Configure Tesseract based on detected font
            config = r'--oem 3 --psm 6'
            if font_type == "Handwritten":
                config = r'--oem 3 --psm 6 -c tessedit_char_whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,?!:;\'"()- "'

            # Perform OCR
            text = pytesseract.image_to_string(processed, lang=available_langs, config=config)

            # Clean and enhance text
            cleaned_text = clean_text_for_speech(text)
            enhanced_text = enhance_pronunciation(cleaned_text)

            # Save the recognized text
            with open(f"handwriting_data/text_{timestamp}.txt", "w") as f:
                f.write(text)

            # Display results
            print("\n--- Recognized Text ---")
            print(text)
            print("----------------------\n")

            # Display the processed image
            cv2.imshow("Processed Image", processed)

            # Speak the text
            print("Speaking text... Press any key to stop.")
            speak_text_clearly(engine, enhanced_text)

            # Save confidence data for analysis
            conf_data = pytesseract.image_to_data(processed, lang=available_langs, output_type=pytesseract.Output.DICT)
            conf_values = conf_data.get('conf', [])
            valid_conf = [c for c in conf_values if c != -1]

            if valid_conf:
                avg_conf = sum(valid_conf) / len(valid_conf)
                print(f"Average confidence: {avg_conf:.2f}%")

                # If confidence is low, suggest another mode
                if avg_conf < 60:
                    suggested_mode = (mode + 1) % 5
                    print(f"Low confidence detected. Consider trying '{mode_names[suggested_mode]}' mode.")

        # Clean up
    cap.release()
    cv2.destroyAllWindows()
    engine.stop()


if __name__ == "__main__":
    # Configure Tesseract path and languages
    pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Shriram\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
    main()