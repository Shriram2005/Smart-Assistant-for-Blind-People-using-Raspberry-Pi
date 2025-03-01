import cv2
import easyocr

def extract_handwritten_text(image_path):
    # Load the image
    image = cv2.imread(image_path)
    # Convert to grayscale
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Initialize the EasyOCR reader
    reader = easyocr.Reader(['en'])  # Specify the language

    # Perform OCR on the image
    results = reader.readtext(gray_image)

    # Extract and return the text
    extracted_text = ' '.join([result[1] for result in results])
    return extracted_text

if __name__ == "__main__":
    image_path = r'C:\Users\Shriram\OneDrive\Desktop\project\OCR_laptop_v1\f684c800f8e086b488b89ca0048aa1e4.jpg'  # Replace with your image path
    text = extract_handwritten_text(image_path)
    print("Extracted Text:", text)
