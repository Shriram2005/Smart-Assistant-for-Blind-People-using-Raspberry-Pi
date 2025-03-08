import cv2
import easyocr
import matplotlib.pyplot as plt

def preprocess_image(image_path):
    # Load the image
    image = cv2.imread(image_path)
    # Convert to grayscale
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Apply Gaussian blur to reduce noise
    blurred_image = cv2.GaussianBlur(gray_image, (5, 5), 0)
    # Apply adaptive thresholding
    binary_image = cv2.adaptiveThreshold(blurred_image, 255, 
                                         cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                         cv2.THRESH_BINARY_INV, 11, 2)
    return binary_image

def extract_handwritten_text(image_path):
    # Preprocess the image
    processed_image = preprocess_image(image_path)

    # Initialize the EasyOCR reader
    reader = easyocr.Reader(['en'], gpu=True)  # Use GPU if available

    # Perform OCR on the processed image
    results = reader.readtext(processed_image)

    # Extract and return the text
    extracted_text = ' '.join([result[1] for result in results])
    return extracted_text

if __name__ == "__main__":
    image_path = r'C:\Users\Shriram\Desktop\project\OCR_laptop_v1\Demo Images\img4.jpg'  # Replace with your image path
    text = extract_handwritten_text(image_path)
    print("Extracted Text:", text)

    # Display the image using Matplotlib
    plt.imshow(cv2.cvtColor(cv2.imread(image_path), cv2.COLOR_BGR2RGB))
    plt.axis('off')  # Hide axes
    plt.show()
