import cv2
import numpy as np
import re
from paddleocr import PaddleOCR
from textblob import TextBlob

# Initialize PaddleOCR
# ocr = PaddleOCR(use_angle_cls=True, lang="en")
ocr = PaddleOCR(use_angle_cls=True, 
                lang="en",  # Use English language
                # Using default models instead of specifying paths
                # rec_model_dir='en_PP-OCRv3_rec_infer',
                # det_model_dir='en_PP-OCRv3_det_infer',
                # cls_model_dir='ch_ppocr_mobile_v2.0_cls_infer',
                use_gpu=False,
                show_log=True,  # Show logs to debug
                rec_char_dict_path=None,  # Will use the default English dictionary
                rec_batch_num=6,  # Increase batch size for faster processing
                drop_score=0.5)  # Minimum confidence threshold

def preprocess_image(image_path):
    """Enhanced preprocessing specifically for handwritten text recognition."""
    img = cv2.imread(image_path)
    
    # Resize image for better processing (if needed)
    # height, width = img.shape[:2]
    # if width > 1500:
    #     img = cv2.resize(img, (1500, int(1500 * height / width)))
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply bilateral filter to reduce noise while preserving edges
    bilateral = cv2.bilateralFilter(gray, 9, 75, 75)
    
    # Apply adaptive histogram equalization for better contrast
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(bilateral)
    
    # Apply sharpening
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    sharpened = cv2.filter2D(enhanced, -1, kernel)
    
    # Apply adaptive thresholding
    thresh = cv2.adaptiveThreshold(
        sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 11, 2
    )
    
    # Dilate to connect broken strokes
    kernel = np.ones((1, 1), np.uint8)
    dilated = cv2.dilate(thresh, kernel, iterations=1)
    
    # Invert back to black text on white background
    processed = cv2.bitwise_not(dilated)
    
    # Save the preprocessed image for debugging (optional)
    cv2.imwrite("HANDWRITING/preprocessed.jpg", processed)
    
    return processed

def extract_text(image_path):
    """Extract text from the preprocessed image using PaddleOCR with confidence filtering."""
    # First preprocess the image
    preprocessed_img = preprocess_image(image_path)
    
    # Save preprocessed image to a temporary file
    temp_path = "HANDWRITING/temp_preprocessed.jpg"
    cv2.imwrite(temp_path, preprocessed_img)
    
    # Run OCR on both original and preprocessed images
    result_orig = ocr.ocr(image_path, cls=True)
    result_prep = ocr.ocr(temp_path, cls=True)
    
    # Combine results, filtering by confidence
    extracted_text = ""
    
    # Process original image results
    if result_orig and len(result_orig) > 0:
        for line in result_orig:
            if line is not None:  # Check if line is not None
                for word_info in line:
                    if word_info is not None and len(word_info) >= 2 and word_info[1] is not None and len(word_info[1]) >= 2:
                        if word_info[1][1] > 0.6:  # Only include words with confidence > 60%
                            extracted_text += word_info[1][0] + " "
    
    # Process preprocessed image results
    if result_prep and len(result_prep) > 0:
        prep_text = ""
        for line in result_prep:
            if line is not None:  # Check if line is not None
                for word_info in line:
                    if word_info is not None and len(word_info) >= 2 and word_info[1] is not None and len(word_info[1]) >= 2:
                        if word_info[1][1] > 0.6:  # Only include words with confidence > 60%
                            prep_text += word_info[1][0] + " "
        
        # If preprocessed text is longer, it might have detected more
        if len(prep_text) > len(extracted_text):
            extracted_text = prep_text
    
    return extracted_text.strip()

def correct_spelling(text):
    """Improved spelling correction with context awareness."""
    if not text:
        return ""
        
    # Split text into words
    words = text.split()
    corrected_words = []
    
    # Process each word individually to avoid over-correction
    for word in words:
        # Skip short words, numbers, and special characters
        if len(word) <= 2 or word.isdigit() or not any(c.isalpha() for c in word):
            corrected_words.append(word)
            continue
            
        # Use TextBlob for spelling correction
        blob = TextBlob(word)
        corrected = str(blob.correct())
        
        # Only accept the correction if it's not too different
        if len(corrected) > 0 and len(word) > 0:
            # Calculate Levenshtein distance
            distance = sum(1 for a, b in zip(word.lower(), corrected.lower()) if a != b)
            distance += abs(len(word) - len(corrected))
            
            # Only accept correction if the change is not too drastic
            if distance <= len(word) // 2 + 1:
                corrected_words.append(corrected)
            else:
                corrected_words.append(word)  # Keep original if change is too big
        else:
            corrected_words.append(word)
    
    return ' '.join(corrected_words)

def clean_extracted_text(text):
    """Enhanced cleaning for handwritten text OCR results."""
    if not text:
        return ""
        
    # Fix common OCR errors in handwriting
    text = re.sub(r'\n+', ' ', text)  # Replace newlines with spaces
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize spaces
    
    # Fix common OCR misreads for handwriting
    replacements = {
        '1': 'l',  # Often confused in handwriting
        '0': 'o',  # Often confused in handwriting
        '5': 's',  # Sometimes confused
        '8': 'B',  # Sometimes confused
        '\$': 's',  # Dollar sign confused with 's'
        '@': 'a',  # @ confused with 'a'
        '&': '&',  # Keep ampersands
        '#': '#',  # Keep hash symbols
    }
    
    # Apply replacements only in contexts where they make sense
    words = text.split()
    for i, word in enumerate(words):
        # Only apply certain replacements in alphabetic contexts
        if word.isalpha() or (len(word) > 1 and any(c.isalpha() for c in word)):
            for old, new in replacements.items():
                if old in '10' and old in word:  # Only replace digits in alphabetic words
                    words[i] = words[i].replace(old, new)
    
    cleaned_text = ' '.join(words)
    return cleaned_text

# === Run OCR Workflow ===
image_path = r'C:\Users\Shriram\Desktop\project\OCR_laptop_v1\Demo Images\img8.jpg' # Add path to the input image

print("Starting OCR process...")

try:
    # Step 1: Extract text with confidence filtering
    print("Extracting text from image...")
    extracted_text = extract_text(image_path)
    if not extracted_text:
        print("Warning: No text was extracted from the image.")
        extracted_text = ""
    print("\nRaw extracted text:")
    print(extracted_text)

    # Step 2: Clean the extracted text
    print("\nCleaning text...")
    clean_text = clean_extracted_text(extracted_text)
    print("\nCleaned text:")
    print(clean_text)

    # Step 3: Correct spelling
    print("\nCorrecting spelling...")
    final_text = correct_spelling(clean_text)
    print("\nFinal text:")
    print(final_text)

    # Save Results
    text_file_path = "HANDWRITING/output.txt"
    with open(text_file_path, "w", encoding="utf-8") as file:
        file.write("Original OCR Text:\n" + extracted_text + "\n\n")
        file.write("Cleaned Text:\n" + clean_text + "\n\n")
        file.write("Final Text:\n" + final_text)

    print(f"\nResults saved to {text_file_path}")
    print("Preprocessed image saved to HANDWRITING/preprocessed.jpg")
    print("Temporary processed image saved to HANDWRITING/temp_preprocessed.jpg")

except Exception as e:
    print(f"An error occurred: {str(e)}")
    import traceback
    traceback.print_exc()
