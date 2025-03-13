import cv2
import numpy as np
import pytesseract
from spellchecker import SpellChecker
import torch
import torch.nn as nn
import os

# --- Preprocessing Function ---
def preprocess_image(image_path):
    """Preprocess image to enhance text extraction accuracy."""
    # Load image in grayscale
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Could not load image at {image_path}")
    
    # Noise removal
    img = cv2.fastNlMeansDenoising(img, h=30)
    
    # Adaptive thresholding
    img = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                cv2.THRESH_BINARY, 11, 2)
    
    # Deskew image
    coords = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
    if len(coords) > 0:
        angle = cv2.minAreaRect(coords[0])[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        (h, w) = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        img = cv2.warpAffine(img, M, (w, h))
    
    # Dilate to connect broken characters
    kernel = np.ones((2, 2), np.uint8)
    img = cv2.dilate(img, kernel, iterations=1)
    
    return img

# --- Text Detection Function ---
def detect_text_regions(image):
    """Detect text regions using a simplified contour-based approach."""
    # Find contours
    contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        # Filter small or noisy regions
        if w > 10 and h > 10:
            boxes.append([x, y, x + w, y + h])
    return boxes

# --- Printed Text Extraction (Tesseract) ---
def extract_printed_text(image, box):
    """Extract printed text using Tesseract OCR."""
    x, y, w, h = box
    roi = image[y:h, x:w]
    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(roi, config=custom_config)
    return text.strip()

# --- CRNN Model for Handwritten/Cursive Text ---
class CRNN(nn.Module):
    def __init__(self, num_classes=80):  # 80 = alphabet + digits + special chars
        super(CRNN, self).__init__()
        self.cnn = nn.Sequential(
            nn.Conv2d(1, 64, 3, 1, 1), nn.ReLU(True),
            nn.MaxPool2d(2, 2),
            nn.Conv2d(64, 128, 3, 1, 1), nn.ReLU(True),
            nn.MaxPool2d(2, 2)
        )
        self.rnn = nn.Sequential(
            nn.LSTM(128, 256, bidirectional=True),
            nn.LSTM(256, 256, bidirectional=True)
        )
        self.fc = nn.Linear(512, num_classes)

    def forward(self, x):
        conv = self.cnn(x)
        batch, channels, height, width = conv.size()
        conv = conv.squeeze(2)
        conv = conv.permute(2, 0, 1)
        rnn_out, _ = self.rnn(conv)
        out = self.fc(rnn_out)
        return out

def extract_handwritten_text(image, box, model):
    """Extract handwritten/cursive text using CRNN (placeholder)."""
    x, y, w, h = box
    roi = image[y:h, x:w]
    roi = cv2.resize(roi, (128, 32))  # CRNN input size
    roi = torch.tensor(roi, dtype=torch.float32).unsqueeze(0).unsqueeze(0) / 255.0
    model.eval()
    with torch.no_grad():
        preds = model(roi)
        _, preds = preds.max(2)
        text = decode_ctc(preds)  # Simplified decoding
    return text

def decode_ctc(preds):
    """Simplified CTC decoding (placeholder)."""
    # In a real scenario, use a proper CTC decoder (e.g., from `torchvision`)
    char_list = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "
    pred_text = "".join([char_list[p.item()] for p in preds[0] if p.item() < len(char_list)])
    return pred_text.strip()

# --- Post-Processing ---
def correct_text(text):
    """Correct extracted text using offline spellchecker."""
    spell = SpellChecker()
    words = text.split()
    corrected = [spell.correction(word) if word in spell else word for word in words]
    return " ".join(corrected)

# --- Main Extraction Function ---
def extract_text(image_path, crnn_model=None):
    """Extract text from an image with high accuracy."""
    # Preprocess image
    img = preprocess_image(image_path)
    
    # Detect text regions
    boxes = detect_text_regions(img)
    if not boxes:
        return "No text detected."
    
    # Initialize CRNN model if not provided
    if crnn_model is None:
        crnn_model = CRNN(num_classes=80)
        # Normally, load pre-trained weights here: crnn_model.load_state_dict(torch.load("crnn_model.pth"))
    
    # Extract text from each region
    extracted_text = []
    for box in boxes:
        # Try printed text first
        printed_text = extract_printed_text(img, box)
        if printed_text and len(printed_text) > 2:  # Basic heuristic for valid text
            corrected = correct_text(printed_text)
            extracted_text.append(corrected)
        else:
            # Fall back to handwritten text
            handwritten_text = extract_handwritten_text(img, box, crnn_model)
            corrected = correct_text(handwritten_text)
            extracted_text.append(corrected)
    
    return "\n".join(extracted_text)

# --- Main Execution ---
if __name__ == "__main__":

    pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Shriram\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
    # Example usage
    image_path = r'C:\Users\Shriram\Desktop\project\OCR_laptop_v1\Demo Images\img2.jpg'  # Replace with your image path
    if not os.path.exists(image_path):
        print(f"Error: Image file '{image_path}' not found.")
    else:
        result = extract_text(image_path)
        print("Extracted Text:")
        print(result)
        
        # Optionally save to file
        with open("extracted_text.txt", "w") as f:
            f.write(result)
        print("Text saved to 'extracted_text.txt'")