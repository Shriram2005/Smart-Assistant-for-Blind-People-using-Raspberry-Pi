import cv2
import numpy as np
import re
import os
import matplotlib.pyplot as plt
from paddleocr import PaddleOCR
from textblob import TextBlob
from PIL import Image, ImageEnhance
import pytesseract
from spellchecker import SpellChecker


class HandwritingRecognizer:
    def __init__(self, language="en", use_gpu=False):
        """Initialize OCR engines and tools."""
        # Initialize PaddleOCR with better configurations for handwriting
        self.paddle_ocr = PaddleOCR(
            use_angle_cls=True,
            lang=language,
            use_gpu=use_gpu,
            rec_algorithm="SVTR_LCNet",  # Better for handwritten text
            rec_batch_num=8,
            det_db_thresh=0.3,  # Lower threshold to detect more text regions
            det_db_box_thresh=0.5,
            det_db_unclip_ratio=1.8  # Higher unclip ratio for connected handwriting
        )

        # Initialize Tesseract as backup OCR
        # Make sure to install Tesseract and point to the correct path
        if os.name == 'nt':  # Windows
            pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Shriram\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
        # Initialize spell checker
        self.spell_checker = SpellChecker(language=language)
        self.language = language

    def enhance_image(self, image):
        """Apply multiple enhancement techniques to improve image quality."""
        # Convert PIL Image to OpenCV format if needed
        if isinstance(image, Image.Image):
            image = np.array(image)
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        # Create a copy to avoid modifying the original
        enhanced = image.copy()

        # Convert to grayscale
        gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)

        # Denoise image
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)

        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced_contrast = clahe.apply(denoised)

        # Apply bilateral filter to smooth while preserving edges
        smooth = cv2.bilateralFilter(enhanced_contrast, 9, 75, 75)

        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            smooth, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )

        # Dilate to connect broken strokes - especially useful for handwriting
        kernel = np.ones((1, 1), np.uint8)
        dilated = cv2.dilate(thresh, kernel, iterations=1)

        # Invert back for OCR
        processed = cv2.bitwise_not(dilated)

        return processed

    def alternative_preprocessing(self, image_path):
        """Apply alternative preprocessing steps for comparison."""
        # Open with PIL for different image enhancements
        image = Image.open(image_path)

        # Enhance contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)

        # Enhance sharpness
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)

        # Convert to OpenCV format
        cv_image = np.array(image)
        cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)

        # Apply Otsu's thresholding
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        return binary

    def deskew(self, image):
        """Deskew the image to straighten text lines."""
        # Convert to binary if not already
        if len(image.shape) > 2:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Apply threshold if not already binary
        if np.max(gray) > 1:
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        else:
            binary = gray

        # Calculate skew angle
        coords = np.column_stack(np.where(binary > 0))
        angle = cv2.minAreaRect(coords)[-1]

        # Adjust angle
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        # Rotate image to deskew
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        deskewed = cv2.warpAffine(image, rotation_matrix, (w, h),
                                  flags=cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_REPLICATE)

        return deskewed

    def segment_lines(self, image):
        """Segment the image into text lines for better recognition."""
        # Convert to binary if not already
        if len(image.shape) > 2:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        else:
            binary = cv2.bitwise_not(image) if np.mean(image) > 127 else image

        # Dilate to connect characters in the same line
        kernel = np.ones((5, 40), np.uint8)
        dilated = cv2.dilate(binary, kernel, iterations=1)

        # Find contours of text lines
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Sort contours from top to bottom
        bounding_boxes = [cv2.boundingRect(contour) for contour in contours]
        (contours, bounding_boxes) = zip(*sorted(zip(contours, bounding_boxes),
                                                 key=lambda x: x[1][1]))

        # Extract line images
        line_images = []
        for box in bounding_boxes:
            x, y, w, h = box
            # Add padding
            pad = 10
            x_start = max(0, x - pad)
            y_start = max(0, y - pad)
            x_end = min(image.shape[1], x + w + pad)
            y_end = min(image.shape[0], y + h + pad)

            line = image[y_start:y_end, x_start:x_end]
            if line.size > 0:  # Ensure line isn't empty
                line_images.append(line)

        return line_images

    def extract_text_paddle(self, image):
        """Extract text using PaddleOCR with confidence scores."""
        result = self.paddle_ocr.ocr(image, cls=True)

        if not result or len(result) == 0 or result[0] is None:
            return "", []

        extracted_text = ""
        confidence_scores = []

        for line in result:
            for word_info in line:
                if len(word_info) >= 2 and len(word_info[1]) >= 2:
                    word, confidence = word_info[1][0], word_info[1][1]
                    extracted_text += word + " "
                    confidence_scores.append(confidence)

        return extracted_text.strip(), confidence_scores

    def extract_text_tesseract(self, image):
        """Extract text using Tesseract with specialized configurations."""
        # Convert image to correct format for Tesseract
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Configure Tesseract for handwriting
        custom_config = '--oem 1 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:\'()-!? '

        # Add language parameter if specified
        if self.language != "en":
            custom_config += f' -l {self.language}'

        # Apply recognition
        text = pytesseract.image_to_string(Image.fromarray(image), config=custom_config)

        return text.strip()

    def combine_ocr_results(self, image):
        """Combine results from multiple OCR engines for better accuracy."""
        # Extract using both engines
        paddle_text, confidence_scores = self.extract_text_paddle(image)
        tesseract_text = self.extract_text_tesseract(image)

        # If one engine fails, return the other
        if not paddle_text.strip():
            return tesseract_text
        if not tesseract_text.strip():
            return paddle_text

        # Choose based on confidence or length
        avg_confidence = np.mean(confidence_scores) if confidence_scores else 0

        if avg_confidence > 0.85:
            return paddle_text
        elif len(paddle_text) > 2 * len(tesseract_text):
            return paddle_text
        elif len(tesseract_text) > 2 * len(paddle_text):
            return tesseract_text
        else:
            # Merge results with preference to longer words
            paddle_words = paddle_text.split()
            tesseract_words = tesseract_text.split()

            # Choose longer words when there's overlap
            if len(paddle_words) == len(tesseract_words):
                merged_words = []
                for p_word, t_word in zip(paddle_words, tesseract_words):
                    merged_words.append(p_word if len(p_word) > len(t_word) else t_word)
                return " ".join(merged_words)
            else:
                # When different lengths, choose the one with more content
                return paddle_text if len(paddle_text) > len(tesseract_text) else tesseract_text

    def correct_text(self, text):
        """Apply advanced text correction with context awareness."""
        if not text.strip():
            return text

        # Split text into words
        words = re.findall(r'\b\w+\b', text)

        # Identify misspelled words
        misspelled = self.spell_checker.unknown(words)

        # Create TextBlob for context-based correction
        blob = TextBlob(text)
        corrected_text = str(blob.correct())

        # Additional OCR-specific corrections
        corrected_text = re.sub(r'\s+', ' ', corrected_text)  # Fix extra spaces
        corrected_text = re.sub(r'(?<!\d)1(?!\d)', 'l', corrected_text)  # Fix "1" as "l" but not in numbers
        corrected_text = re.sub(r'(?<!\d)0(?!\d)', 'o', corrected_text)  # Fix "0" as "o" but not in numbers
        corrected_text = re.sub(r'5(?!\d)', 's', corrected_text)  # Fix "5" as "s" but not in numbers
        corrected_text = re.sub(r'(?<!\d)8(?!\d)', 'B', corrected_text)  # Fix "8" as "B" but not in numbers

        # Fix common OCR errors with handwriting
        ocr_fixes = {
            'rn': 'm',
            'cl': 'd',
            'vv': 'w',
            'll': 'll',  # Keep double l as is
            '1l': 'll'  # Fix mixed 1 and l
        }

        for error, fix in ocr_fixes.items():
            corrected_text = corrected_text.replace(error, fix)

        return corrected_text

    def process_image(self, image_path, debug=False):
        """Main function to process an image and extract text."""
        # Load image
        original = cv2.imread(image_path)
        if original is None:
            return "Error: Could not load image."

        # Resize large images to improve processing speed
        h, w = original.shape[:2]
        max_dim = 2000
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            original = cv2.resize(original, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

        # Deskew
        deskewed = self.deskew(original)

        # Apply different preprocessing techniques
        enhanced = self.enhance_image(deskewed)
        alternative = self.alternative_preprocessing(image_path)

        # Debug visualizations
        if debug:
            plt.figure(figsize=(15, 10))
            plt.subplot(2, 2, 1), plt.imshow(cv2.cvtColor(original, cv2.COLOR_BGR2RGB))
            plt.title('Original'), plt.axis('off')
            plt.subplot(2, 2, 2), plt.imshow(deskewed, cmap='gray')
            plt.title('Deskewed'), plt.axis('off')
            plt.subplot(2, 2, 3), plt.imshow(enhanced, cmap='gray')
            plt.title('Enhanced'), plt.axis('off')
            plt.subplot(2, 2, 4), plt.imshow(alternative, cmap='gray')
            plt.title('Alternative'), plt.axis('off')
            plt.tight_layout()
            plt.savefig(f"{os.path.splitext(image_path)[0]}_debug.png")

        # Try extracting text from different preprocessed images
        results = []

        # Segment into lines for better recognition (for enhanced image)
        lines = self.segment_lines(enhanced)
        enhanced_text = ""
        for line in lines:
            line_text = self.combine_ocr_results(line)
            enhanced_text += line_text + " "

        # Process the alternative preprocessing directly
        alternative_text = self.combine_ocr_results(alternative)

        # Process original image directly
        original_text = self.combine_ocr_results(original)

        # Collect results
        results.append((enhanced_text.strip(), "enhanced", len(enhanced_text.strip().split())))
        results.append((alternative_text.strip(), "alternative", len(alternative_text.strip().split())))
        results.append((original_text.strip(), "original", len(original_text.strip().split())))

        # Choose best result based on word count
        results.sort(key=lambda x: x[2], reverse=True)
        best_text = results[0][0]

        # Correct text
        corrected_text = self.correct_text(best_text)

        return corrected_text


def process_batch(directory, output_dir="output"):
    """Process all images in a directory."""
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Initialize recognizer
    recognizer = HandwritingRecognizer()

    # Process each image
    for filename in os.listdir(directory):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')):
            image_path = os.path.join(directory, filename)
            print(f"Processing {filename}...")

            # Extract text
            text = recognizer.process_image(image_path, debug=True)

            # Save results
            base_name = os.path.splitext(filename)[0]
            output_path = os.path.join(output_dir, f"{base_name}_text.txt")

            with open(output_path, "w", encoding="utf-8") as file:
                file.write(text)

            print(f"Completed: Results saved to {output_path}")


# Use the improved system
if __name__ == "__main__":
    # Single image processing
    image_path = "C:/Users/Shriram/Desktop/project/OCR_laptop_v1/Demo Images/img1.jpg"
    recognizer = HandwritingRecognizer()

    # Process with debug visualization
    text = recognizer.process_image(image_path, debug=True)

    print("\nExtracted Text:")
    print(text)

    # Save results
    output_path = "HANDWRITING/output.txt"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(text)

    print(f"\nText saved to {output_path}")

    # Uncomment to process a directory of images
    # process_batch("path/to/images/directory")