import cv2
import pytesseract
import pyttsx3
import numpy as np


def main():
    # Initialize the camera with improved resolution
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    # Set higher resolution for better image quality
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # Initialize text-to-speech engine
    engine = pyttsx3.init()

    # Configure OCR to improve text recognition
    custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,!?-"'

    print("Press Enter to capture and recognize handwriting. Press 'q' to quit.")
    print("Hold the paper still and ensure good lighting for best results.")

    # Create a window with trackbars for image adjustment
    cv2.namedWindow("Handwriting Recognition - Press Enter to capture")
    cv2.createTrackbar("Threshold", "Handwriting Recognition - Press Enter to capture", 11, 51, lambda x: None)
    cv2.createTrackbar("Contrast", "Handwriting Recognition - Press Enter to capture", 2, 20, lambda x: None)

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

        # Display the frame with guides
        cv2.imshow("Handwriting Recognition - Press Enter to capture", display_frame)

        # Wait for key press
        key = cv2.waitKey(1) & 0xFF

        # If Enter key is pressed, process the image
        if key == 13:  # Enter key
            print("Capturing image and recognizing text...")

            # Get current trackbar values
            block_size = cv2.getTrackbarPos("Threshold", "Handwriting Recognition - Press Enter to capture")
            if block_size % 2 == 0:  # Ensure block size is odd
                block_size += 1

            constant = cv2.getTrackbarPos("Contrast", "Handwriting Recognition - Press Enter to capture")

            # Process image for better OCR results
            # Extract just the region of interest
            roi = frame[int(h / 4):int(3 * h / 4), int(w / 4):int(3 * w / 4)]
            processed_image = preprocess_image(roi, block_size, constant)

            # Show the processed image
            cv2.imshow("Processed Image", processed_image)

            # Perform OCR with custom configuration
            text = pytesseract.image_to_string(processed_image, config=custom_config)
            text = text.strip()

            if text:
                print("Recognized Text:", text)

                # Convert text to speech
                engine.say(text)
                engine.runAndWait()
            else:
                print("No text was recognized. Try adjusting position or lighting.")
                engine.say("No text was recognized. Try adjusting position or lighting.")
                engine.runAndWait()

        # If 's' is pressed, save the current frame for debugging
        elif key == ord('s'):
            cv2.imwrite("handwriting_capture.jpg", frame)
            print("Image saved as 'handwriting_capture.jpg'")

        # If 'q' is pressed, quit
        elif key == ord('q'):
            break

    # Release resources
    cap.release()
    cv2.destroyAllWindows()


def preprocess_image(image, block_size=11, constant=2):
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply histogram equalization to improve contrast
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    equalized = clahe.apply(gray)

    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(equalized, (5, 5), 0)

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
    padded = cv2.copyMakeBorder(binary, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)

    return padded


if __name__ == "__main__":
    # Uncomment and set the path to tesseract executable on Windows
    pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Shriram\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'

    main()