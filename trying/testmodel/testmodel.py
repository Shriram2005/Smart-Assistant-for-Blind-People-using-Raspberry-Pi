import cv2
import numpy as np
import tensorflow as tf
import os

# Load the trained model
MODEL_PATH = r"D:\model training\gpt\fine_tuned_handwritten_medicine_model.h5"
model = tf.keras.models.load_model(MODEL_PATH)
print("✅ Model loaded successfully!")

# Define the image path 
IMAGE_PATH = r"D:\model training\handwritten_medicines\Limcee\2.jpg"

# Check if the image file exists
if not os.path.exists(IMAGE_PATH):
    print(f"❌ Error: File not found at {IMAGE_PATH}")
    exit()

# Read and preprocess the image
img = cv2.imread(IMAGE_PATH)
if img is None:
    print(f"❌ Error: Could not read image at {IMAGE_PATH}")
    exit()

# Resize to match model input size (assuming 128x128)
img = cv2.resize(img, (128, 128))
img = img.astype("float32") / 255.0  # Normalize
img = np.expand_dims(img, axis=0)  # Add batch dimension

# Predict the class
predictions = model.predict(img)
predicted_class = np.argmax(predictions)
confidence = np.max(predictions) * 100

# Load class names (ensure this matches training labels)
class_names = ['Azithromycin', 'Corcin', 'Dynapar Tab', 'Erythromycin', 'Feronia - xt',
               'Limcee', 'Omidi', 'Pantoprazole', 'Vitamin B3', 'Zerodol - SP']

# Display prediction result
if predicted_class < len(class_names):
    print(f"✅ Predicted Medicine: {class_names[predicted_class]} ({confidence:.2f}%)")
else:
    print("❌ Error: Predicted class index out of range")