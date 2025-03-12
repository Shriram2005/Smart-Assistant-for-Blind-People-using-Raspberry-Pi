import cv2
import numpy as np
import os
import time
import pyttsx3
import re
import easyocr
import nltk
from nltk.corpus import words

try:
    nltk.data.find('corpora/words')
except LookupError:
    nltk.download('words')
english_words = set(words.words())

# Initialize EasyOCR reader (do this only once as it loads models)
reader = easyocr.Reader(['en'], gpu=False)  # Add more languages if needed


def update_speech_rate(val):
    """Update speech rate from trackbar."""
    # This function will be called when the speech rate trackbar is adjusted
    pass


def preprocess_normal(image, blur_size, clahe_clip):
    """Basic preprocessing to enhance text visibility."""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=clahe_clip, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(enhanced, (blur_size, blur_size), 0)

    return blurred


def preprocess_high_contrast(image, blur_size):
    """High contrast preprocessing for better feature extraction."""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply Gaussian blur
    blurred = cv2.GaussianBlur(gray, (blur_size, blur_size), 0)

    # Enhance contrast
    enhanced = cv2.convertScaleAbs(blurred, alpha=1.5, beta=0)

    return enhanced


def preprocess_for_cursive(image):
    """Specialized preprocessing for cursive handwriting."""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Enhance contrast
    enhanced = cv2.convertScaleAbs(gray, alpha=1.5, beta=10)

    # Apply bilateral filter to preserve edges while removing noise
    bilateral = cv2.bilateralFilter(enhanced, 9, 75, 75)

    return bilateral


def preprocess_for_printed_text(image):
    """Specialized preprocessing for printed text."""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Enhance contrast
    enhanced = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)

    # Apply Gaussian blur
    blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)

    return blurred


def preprocess_shadow_removal(image):
    """Remove shadows from the image for better recognition."""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Create a structuring element
    dilated = cv2.dilate(gray, np.ones((7, 7), np.uint8))

    # Apply morphological opening
    bg = cv2.medianBlur(dilated, 21)

    # Subtract background to get shadow-free image
    diff = 255 - cv2.absdiff(gray, bg)

    # Normalize the image
    norm = cv2.normalize(diff, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)

    return norm


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


def recognize_text_with_easyocr(image, detail=0):
    """Recognize text in image using EasyOCR.

    Args:
        image: Image to process
        detail: 0 for text only, 1 for text with confidence, 2 for text with confidence and bounding boxes

    Returns:
        Text and confidence information based on detail level
    """
    results = reader.readtext(image)

    if not results:
        return "", []

    text = " ".join([result[1] for result in results])
    confidences = [result[2] for result in results]
    avg_confidence = sum(confidences) / len(confidences) * 100 if confidences else 0

    if detail == 0:
        return text
    elif detail == 1:
        return text, avg_confidence
    else:
        return text, avg_confidence, results


def visualize_results(image, results):
    """Draw bounding boxes and text on the image."""
    output = image.copy()

    for (bbox, text, prob) in results:
        # Convert coordinates to integers
        (tl, tr, br, bl) = bbox
        tl = (int(tl[0]), int(tl[1]))
        tr = (int(tr[0]), int(tr[1]))
        br = (int(br[0]), int(br[1]))
        bl = (int(bl[0]), int(bl[1]))

        # Draw the bounding box
        cv2.line(output, tl, tr, (0, 255, 0), 2)
        cv2.line(output, tr, br, (0, 255, 0), 2)
        cv2.line(output, br, bl, (0, 255, 0), 2)
        cv2.line(output, bl, tl, (0, 255, 0), 2)

        # Calculate the center of the box to place the text
        cx = int((tl[0] + br[0]) / 2.0)
        cy = int((tl[1] + br[1]) / 2.0)

        # Draw text and confidence
        cv2.putText(output, f"{text} ({prob:.2f})", (tl[0], tl[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    return output


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
    cv2.createTrackbar("Blur", "Handwriting Recognition - Press Enter to capture", 5, 15, lambda x: None)
    cv2.createTrackbar("CLAHE Clip", "Handwriting Recognition - Press Enter to capture", 2, 10, lambda x: None)
    cv2.createTrackbar("Mode", "Handwriting Recognition - Press Enter to capture", 0, 4, lambda x: None)
    cv2.createTrackbar("Speech Rate", "Handwriting Recognition - Press Enter to capture", 150, 250, update_speech_rate)

    # Create directory for saving data if it doesn't exist
    os.makedirs("handwriting_data", exist_ok=True)

    print("Press Enter to capture and recognize text. Press 'q' to quit.")
    print("Hold the paper still and ensure good lighting for best results.")
    print("Using EasyOCR for improved handwriting recognition.")

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

        # Display information about current mode
        mode_names = ["Normal", "High Contrast", "Cursive", "Printed Text", "Shadow Removal"]
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
            blur_size = cv2.getTrackbarPos("Blur", "Handwriting Recognition - Press Enter to capture")
            # Ensure blur size is odd
            blur_size = blur_size if blur_size % 2 == 1 else blur_size + 1
            clahe_clip = cv2.getTrackbarPos("CLAHE Clip", "Handwriting Recognition - Press Enter to capture")

            # Deskew the image
            deskewed = deskew(roi)

            # Apply preprocessing based on mode
            if mode == 0:
                processed = preprocess_normal(deskewed, blur_size, clahe_clip)
            elif mode == 1:
                processed = preprocess_high_contrast(deskewed, blur_size)
            elif mode == 2:
                processed = preprocess_for_cursive(deskewed)
            elif mode == 3:
                processed = preprocess_for_printed_text(deskewed)
            else:
                processed = preprocess_shadow_removal(deskewed)

            # Save the processed image
            timestamp = int(time.time())
            cv2.imwrite(f"handwriting_data/processed_{timestamp}.jpg", processed)

            # Perform text recognition with EasyOCR
            text, confidence, detailed_results = recognize_text_with_easyocr(processed, detail=2)

            # Visualize the results
            result_image = visualize_results(roi, detailed_results)

            # Clean and enhance text
            cleaned_text = clean_text_for_speech(text)
            enhanced_text = enhance_pronunciation(cleaned_text)

            # Save the recognized text
            with open(f"handwriting_data/text_{timestamp}.txt", "w") as f:
                f.write(text)

            # Display results
            print("\n--- Recognized Text ---")
            print(text)
            print(f"Average confidence: {confidence:.2f}%")
            print("----------------------\n")

            # Display the processed and result images
            cv2.imshow("Processed Image", processed)
            cv2.imshow("Recognition Results", result_image)

            # Speak the text
            print("Speaking text... Press any key to stop.")
            speak_text_clearly(engine, enhanced_text)

            # If confidence is low, suggest another mode
            if confidence < 60:
                suggested_mode = (mode + 1) % 5
                print(f"Low confidence detected. Consider trying '{mode_names[suggested_mode]}' mode.")

    # Clean up
    cap.release()
    cv2.destroyAllWindows()
    engine.stop()


if __name__ == "__main__":
    main()