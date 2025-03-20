import numpy as np
from tensorflow.keras.preprocessing.image import ImageDataGenerator

# Load the dataset
X_train = np.load("D:/model training/gpt/X_train.npy")
y_train = np.load("D:/model training/gpt/y_train.npy")

# Define augmentation
datagen = ImageDataGenerator(
    rotation_range=20,
    width_shift_range=0.2,
    height_shift_range=0.2,
    shear_range=0.2,
    zoom_range=0.2,
    horizontal_flip=True,
    fill_mode="nearest",
)

datagen.fit(X_train)

print(f"✅ Data augmentation applied to {len(X_train)} images")
