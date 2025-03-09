import cv2
import numpy as np
import re
from paddleocr import PaddleOCR
from textblob import TextBlob

# Initialize PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang="en")

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
image_path = "C:/Users/Shriram/Desktop/project/OCR_laptop_v1/Demo Images/img4.jpg" # Add path to the input image

# Step 1: Preprocess Image
preprocessed_image = preprocess_image(image_path)

# Step 2: Run OCR on the preprocessed image
extracted_text = extract_text(image_path)

# Step 3: Clean & Correct Text
clean_text = clean_extracted_text(extracted_text)
final_text = correct_spelling(clean_text)

# Print and Save Results
print("Final Extracted Text://n", final_text)

text_file_path = "HANDWRITING/output.txt" # Create a text file and add it's path here 
with open(text_file_path, "w", encoding="utf-8") as file:
    file.write(final_text)