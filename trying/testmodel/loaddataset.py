import os
import numpy as np
import cv2
from tensorflow.keras.utils import to_categorical
from sklearn.model_selection import train_test_split

# Define dataset path
DATASET_DIR = "D:/model training/preprocessed_medicines"
IMG_SIZE = (128, 128)  # Resize images to this size

# Get class names
medicine_classes = sorted(
    [folder for folder in os.listdir(DATASET_DIR) if os.path.isdir(os.path.join(DATASET_DIR, folder))]
)
num_classes = len(medicine_classes)
print(f"✅ Classes Detected: {num_classes} - {dict(enumerate(medicine_classes))}")

# Load images and labels
X, y = [], []
for label, medicine in enumerate(medicine_classes):
    medicine_path = os.path.join(DATASET_DIR, medicine)
    for img_file in os.listdir(medicine_path):
        img_path = os.path.join(medicine_path, img_file)
        img = cv2.imread(img_path)
        if img is not None:
            img = cv2.resize(img, IMG_SIZE)
            X.append(img)
            y.append(label)
        else:
            print(f"❌ Could not read image {img_path}")

# Convert to NumPy arrays
X = np.array(X, dtype="float32") / 255.0  # Normalize
y = to_categorical(y, num_classes=num_classes)

# Split dataset
X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

# Save dataset
np.save("D:/model training/gpt/X_train.npy", X_train)
np.save("D:/model training/gpt/X_val.npy", X_val)
np.save("D:/model training/gpt/y_train.npy", y_train)
np.save("D:/model training/gpt/y_val.npy", y_val)

print(f"✅ Dataset loaded: {len(X_train)} training images, {len(X_val)} validation images")
