import cv2
import pytesseract
import pyttsx3
import numpy as np
import os
import time


def main():
    # Initialize the camera with improved resolution
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    # Set higher resolution for better image quality
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    # Initialize text-to-speech engine
    engine = pyttsx3.init()

    # Configure tesseract language and models for better recognition
    # This includes training data for multiple fonts and handwriting styles
    custom_config = r'--oem 3 --psm 6 -l eng+osd --dpi 300'

    print("Press Enter to capture and recognize handwriting. Press 'q' to quit.")
    print("Hold the paper still and ensure good lighting for best results.")

    # Create a window with trackbars for advanced image adjustment
    cv2.namedWindow("Handwriting Recognition - Press Enter to capture")
    cv2.createTrackbar("Block Size", "Handwriting Recognition - Press Enter to capture", 11, 51, lambda x: None)
    cv2.createTrackbar("Constant", "Handwriting Recognition - Press Enter to capture", 2, 20, lambda x: None)
    cv2.createTrackbar("Blur", "Handwriting Recognition - Press Enter to capture", 5, 15, lambda x: None)
    cv2.createTrackbar("CLAHE Clip", "Handwriting Recognition - Press Enter to capture", 2, 10, lambda x: None)
    cv2.createTrackbar("Mode", "Handwriting Recognition - Press Enter to capture", 0, 2, lambda x: None)

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

        # Get current mode (0=normal, 1=high contrast, 2=edge detection)
        mode = cv2.getTrackbarPos("Mode", "Handwriting Recognition - Press Enter to capture")

        # Display information about current mode
        mode_names = ["Normal", "High Contrast", "Edge Detection"]
        cv2.putText(display_frame, f"Mode: {mode_names[mode]}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Display the frame with guides
        cv2.imshow("Handwriting Recognition - Press Enter to capture", display_frame)

        # Wait for key press
        key = cv2.waitKey(1) & 0xFF

        # If Enter key is pressed, process the image
        if key == 13:  # Enter key
            print("Capturing image and recognizing text...")

            # Get current trackbar values
            block_size = cv2.getTrackbarPos("Block Size", "Handwriting Recognition - Press Enter to capture")
            if block_size % 2 == 0:  # Ensure block size is odd
                block_size += 1

            constant = cv2.getTrackbarPos("Constant", "Handwriting Recognition - Press Enter to capture")
            blur_size = cv2.getTrackbarPos("Blur", "Handwriting Recognition - Press Enter to capture")
            if blur_size % 2 == 0:  # Ensure blur size is odd
                blur_size += 1

            clahe_clip = cv2.getTrackbarPos("CLAHE Clip", "Handwriting Recognition - Press Enter to capture")

            # Extract just the region of interest
            roi = frame[int(h / 4):int(3 * h / 4), int(w / 4):int(3 * w / 4)]

            # Try multiple preprocessing techniques and merge results
            recognized_texts = []

            # Process image with different methods based on the selected mode
            if mode == 0:  # Normal mode
                processed_image = preprocess_normal(roi, block_size, constant, blur_size, clahe_clip)
                cv2.imshow("Processed Image", processed_image)
                text = pytesseract.image_to_string(processed_image, config=custom_config)
                recognized_texts.append(text.strip())

            elif mode == 1:  # High contrast mode
                processed_image = preprocess_high_contrast(roi, blur_size)
                cv2.imshow("Processed Image", processed_image)
                text = pytesseract.image_to_string(processed_image, config=custom_config)
                recognized_texts.append(text.strip())

            elif mode == 2:  # Edge detection mode
                processed_image = preprocess_edge_detection(roi, blur_size)
                cv2.imshow("Processed Image", processed_image)
                text = pytesseract.image_to_string(processed_image, config=custom_config)
                recognized_texts.append(text.strip())

            # Try alternate preprocessing for better recognition
            alt_processed = preprocess_alternate(roi)
            alt_text = pytesseract.image_to_string(alt_processed, config=custom_config)
            recognized_texts.append(alt_text.strip())

            # Try specific handwriting-optimized config
            handwriting_config = r'--oem 3 --psm 13 -l eng'  # PSM 13 is for sparse text
            handwriting_text = pytesseract.image_to_string(processed_image, config=handwriting_config)
            recognized_texts.append(handwriting_text.strip())

            # Filter empty strings and select best result (longest recognized text)
            recognized_texts = [text for text in recognized_texts if text]

            if recognized_texts:
                # Select the longest recognized text (usually most accurate)
                best_text = max(recognized_texts, key=len)
                print("Recognized Text:", best_text)

                # Save the recognized text to a log file with timestamp
                timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
                with open(f"recognized_text_{timestamp}.txt", "w") as f:
                    f.write(f"Recognized text: {best_text}\n")
                    f.write(f"All recognized variations:\n")
                    for i, text in enumerate(recognized_texts):
                        f.write(f"{i + 1}. {text}\n")

                # Convert text to speech
                engine.say(best_text)
                engine.runAndWait()
            else:
                print("No text was recognized. Try adjusting position, lighting, or mode.")
                engine.say("No text was recognized. Try adjusting position, lighting, or mode.")
                engine.runAndWait()

        # If 's' is pressed, save the current frame for debugging
        elif key == ord('s'):
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            cv2.imwrite(f"handwriting_capture_{timestamp}.jpg", frame)
            print(f"Image saved as 'handwriting_capture_{timestamp}.jpg'")

        # If 'q' is pressed, quit
        elif key == ord('q'):
            break

    # Release resources
    cap.release()
    cv2.destroyAllWindows()


def preprocess_normal(image, block_size=11, constant=2, blur_size=5, clahe_clip=2.0):
    """Standard preprocessing pipeline with adaptive parameters"""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply histogram equalization to improve contrast
    clahe = cv2.createCLAHE(clipLimit=clahe_clip, tileGridSize=(8, 8))
    equalized = clahe.apply(gray)

    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(equalized, (blur_size, blur_size), 0)

    # Apply adaptive thresholding with parameters from trackbars
    binary = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, block_size, constant
    )

    # Apply morphological operations to clean up the image
    kernel = np.ones((2, 2), np.uint8)
    # Dilate to thicken the text
    binary = cv2.dilate(binary, kernel, iterations=1)
    # Erode to remove small noise
    binary = cv2.erode(binary, kernel, iterations=1)

    # Add padding around the image (white border)
    padded = cv2.copyMakeBorder(binary, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)

    return padded


def preprocess_high_contrast(image, blur_size=5):
    """High contrast preprocessing for faded or light handwriting"""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply strong histogram equalization
    # Global equalization
    equalized = cv2.equalizeHist(gray)

    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(equalized, (blur_size, blur_size), 0)

    # Apply Otsu's thresholding
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Clean up the image with morphological operations
    kernel = np.ones((2, 2), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)

    # Add padding around the image (white border)
    padded = cv2.copyMakeBorder(binary, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)

    return padded


def preprocess_edge_detection(image, blur_size=5):
    """Edge detection preprocessing for cursive or connected handwriting"""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (blur_size, blur_size), 0)

    # Apply Canny edge detection
    edges = cv2.Canny(blurred, 30, 100)

    # Dilate to connect edge components
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=2)

    # Invert for OCR (text should be black on white)
    inverted = 255 - dilated

    # Add padding around the image (white border)
    padded = cv2.copyMakeBorder(inverted, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)

    return padded


def preprocess_alternate(image):
    """Alternative preprocessing method with different parameters"""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Increase contrast
    alpha = 1.5  # Contrast control
    beta = 10  # Brightness control
    adjusted = cv2.convertScaleAbs(gray, alpha=alpha, beta=beta)

    # Apply bilateral filter to preserve edges while reducing noise
    filtered = cv2.bilateralFilter(adjusted, 11, 17, 17)

    # Apply adaptive thresholding
    binary = cv2.adaptiveThreshold(
        filtered, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV, 15, 4
    )

    # Clean up with morphological operations
    kernel = np.ones((2, 2), np.uint8)
    morphed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)

    # Add padding
    padded = cv2.copyMakeBorder(morphed, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)

    return padded


if __name__ == "__main__":
    # Uncomment and set the path to tesseract executable on Windows
    pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Shriram\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'

    # For improved language support, download and install additional language data
    # On Linux: sudo apt-get install tesseract-ocr-eng tesseract-ocr-osd
    # On Windows: Download from https://github.com/tesseract-ocr/tessdata

    main()