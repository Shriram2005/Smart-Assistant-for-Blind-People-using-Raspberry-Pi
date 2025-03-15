import os
import cv2
import numpy as np
import matplotlib.pyplot as plt
from datasets import load_dataset
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
import torch
from PIL import Image
import win32com.client

class IAMHandwritingRecognizer:
    def __init__(self):
        """Initialize the handwriting recognizer with pre-trained models."""
        # Initialize text-to-speech engine
        self.speaker = win32com.client.Dispatch("SAPI.SpVoice")
        self.speaker.Rate = 0  # Normal speed
        self.speaker.Volume = 100  # Maximum volume
        
        # Load pre-trained TrOCR model and processor
        print("Loading pre-trained model for handwriting recognition...")
        self.processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
        self.model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-handwritten")
        
        # Set device (use GPU if available)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        print(f"Model loaded and running on {self.device}")
    
    def load_dataset_sample(self, num_samples=5):
        """Load a sample from the IAM dataset for demonstration."""
        print("Loading IAM dataset sample...")
        dataset = load_dataset("Teklia/IAM-line", split="train")
        
        # Print dataset info
        print(f"Dataset size: {len(dataset)} samples")
        print(f"Dataset features: {dataset.features}")
        
        # Return a small sample
        return dataset.select(range(min(num_samples, len(dataset))))
    
    def visualize_samples(self, samples):
        """Visualize sample images and their transcriptions."""
        plt.figure(figsize=(15, 10))
        
        for i, sample in enumerate(samples):
            image = sample["image"]
            text = sample["text"]
            
            # Convert to numpy array if needed
            if not isinstance(image, np.ndarray):
                image = np.array(image)
            
            plt.subplot(len(samples), 1, i+1)
            plt.imshow(image, cmap='gray')
            plt.title(f"Text: {text}")
            plt.axis('off')
        
        plt.tight_layout()
        plt.savefig("iam_samples.png")
        plt.close()
        print("Sample images saved to 'iam_samples.png'")
    
    def recognize_text(self, image):
        """Recognize handwritten text in an image using the pre-trained model."""
        # Convert to PIL Image if needed
        if isinstance(image, np.ndarray):
            # Convert grayscale to RGB if needed
            if len(image.shape) == 2:
                # Convert 2D grayscale to 3D RGB
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            elif image.shape[2] == 1:
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            
            # Convert to PIL Image
            image = Image.fromarray(image)
        elif not isinstance(image, Image.Image):
            # Convert PIL Image object to RGB if it's not already
            image = image.convert('RGB')
        
        # Process the image
        pixel_values = self.processor(image, return_tensors="pt").pixel_values.to(self.device)
        
        # Generate predictions
        generated_ids = self.model.generate(pixel_values)
        
        # Decode the predicted IDs to text
        predicted_text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        
        return predicted_text
    
    def preprocess_image(self, image):
        """Preprocess an image for better text recognition."""
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 10
        )
        
        # Invert if needed (text should be dark on light background for the model)
        if np.mean(thresh) < 127:
            thresh = cv2.bitwise_not(thresh)
        
        return thresh
    
    def speak_text(self, text):
        """Convert text to speech using Microsoft SAPI."""
        if text.strip():
            print("Speaking:", text)
            # Add punctuation for better speech pacing
            formatted_text = text.replace(' .', '.').replace(' ,', ',')
            self.speaker.Speak(formatted_text)
    
    def run_camera_recognition(self):
        """Run real-time handwriting recognition from camera feed."""
        # Initialize camera
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Could not open camera")
            return
        
        print("Camera is active. Press SPACE to capture and process image, Q to quit")
        
        while True:
            # Capture frame
            ret, frame = cap.read()
            if not ret:
                print("Error: Could not read frame")
                break
            
            # Display frame
            cv2.imshow('Camera Feed (SPACE to capture, Q to quit)', frame)
            
            # Handle key presses
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord(' '):  # Space key
                print("\nProcessing captured image...")
                
                # Save frame temporarily
                temp_image = "temp_capture.jpg"
                cv2.imwrite(temp_image, frame)
                
                # Preprocess the image
                processed_image = self.preprocess_image(frame)
                
                # Recognize text
                text = self.recognize_text(processed_image)
                
                # Print and speak the results
                print("\nExtracted Text:")
                print(text)
                self.speak_text(text)
                
                # Save results
                output_path = "HANDWRITING/output.txt"
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as file:
                    file.write(text)
                print(f"\nText saved to {output_path}")
                
                # Clean up temporary file
                if os.path.exists(temp_image):
                    os.remove(temp_image)
        
        # Release resources
        cap.release()
        cv2.destroyAllWindows()

def main():
    """Main function to demonstrate IAM dataset usage and handwriting recognition."""
    try:
        # Initialize the recognizer
        recognizer = IAMHandwritingRecognizer()
        
        # Load and visualize dataset samples
        samples = recognizer.load_dataset_sample()
        recognizer.visualize_samples(samples)
        
        # Test recognition on a sample
        sample_image = samples[0]["image"]
        
        # Convert sample image to PIL Image with RGB format
        if not isinstance(sample_image, np.ndarray):
            sample_image = np.array(sample_image)
        
        # Convert grayscale to RGB
        if len(sample_image.shape) == 2:
            sample_image = cv2.cvtColor(sample_image, cv2.COLOR_GRAY2RGB)
        
        # Convert to PIL Image
        sample_image_pil = Image.fromarray(sample_image)
        
        # Recognize text
        sample_text = recognizer.recognize_text(sample_image_pil)
        print(f"Sample recognition result: {sample_text}")
        print(f"Ground truth: {samples[0]['text']}")
        
        # Ask user if they want to run camera recognition
        response = input("\nDo you want to run camera-based recognition? (y/n): ")
        if response.lower() == 'y':
            recognizer.run_camera_recognition()
        
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 