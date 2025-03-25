import cv2
import numpy as np
import re
from paddleocr import PaddleOCR
from textblob import TextBlob

# Initialize PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang="en")

def capture_image_from_camera():
    """Capture an image from the camera and save it temporarily."""
    # Initialize the camera
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        raise IOError("Cannot open webcam")
    
    print("Camera opened. Press SPACE to capture or ESC to quit.")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        # Display the frame
        cv2.imshow('Capture Image', frame)
        
        # Wait for key press
        key = cv2.waitKey(1)
        
        # If space bar is pressed, capture the image
        if key == 32:  # SPACE key
            temp_image_path = "temp_captured_image.jpg"
            cv2.imwrite(temp_image_path, frame)
            print(f"Image captured and saved as {temp_image_path}")
            break
        # If ESC is pressed, exit
        elif key == 27:  # ESC key
            print("Image capture cancelled")
            cap.release()
            cv2.destroyAllWindows()
            return None
    
    # Release the camera and close windows
    cap.release()
    cv2.destroyAllWindows()
    
    return temp_image_path

def preprocess_image(image_path):
    """Enhance image quality before OCR for better text recognition."""
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Apply sharpening
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharpened = cv2.filter2D(gray, -1, kernel)

    # Adaptive Thresholding for better contrast
    thresh = cv2.adaptiveThreshold(
        sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )
    
    return thresh

def extract_text(image_path):
    """Extract text from the preprocessed image using PaddleOCR."""
    result = ocr.ocr(image_path, cls=True)
    
    # Combine recognized words into a structured text output
    extracted_text = " ".join([word_info[1][0] for line in result for word_info in line])
    return extracted_text.strip()

def correct_spelling(text):
    """Correct spelling errors using TextBlob for context-aware fixes."""
    blob = TextBlob(text)
    corrected_text = blob.correct()
    return str(corrected_text)

def clean_extracted_text(text):
    """Clean and format extracted text to remove extra spaces and fix common OCR misreads."""
    text = re.sub(r"//n+", " ", text)  # Remove extra newlines
    text = re.sub(r"//s+", " ", text).strip()  # Remove extra spaces
    text = re.sub(r"1", "l", text)  # Fix OCR misreading "1" as "l"
    text = re.sub(r"0", "o", text)  # Fix OCR misreading "0" as "o"
    return text

# === Run OCR Workflow ===
# Step 1: Capture Image from Camera
image_path = capture_image_from_camera()

if image_path:
    # Step 2: Preprocess Image
    preprocessed_image = preprocess_image(image_path)

    # Step 3: Run OCR on the preprocessed image
    extracted_text = extract_text(image_path)

    # Step 4: Clean & Correct Text
    clean_text = clean_extracted_text(extracted_text)
    final_text = correct_spelling(clean_text)

    # Print and Save Results
    print("Final Extracted Text:\n", final_text)

    text_file_path = "HANDWRITING/output.txt" 
    with open(text_file_path, "w", encoding="utf-8") as file:
        file.write(final_text)
else:
    print("OCR process cancelled as no image was captured.")
