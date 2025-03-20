import numpy as np
import tensorflow as tf
from tensorflow.keras.models import load_model, Model
from tensorflow.keras.layers import Dense, Dropout
from loaddataset import X_train, y_train, X_val, y_val  # Ensure dataset is loaded

# Define medicine classes
medicine_classes = {"Corcin": 0, "Zerodol-SP": 1, "Omidi": 2}  # Add all classes

# Load pre-trained model
model_path = "D:/model training/fine_tuned_handwritten_medicine_model.h5"
model = load_model(model_path)
print("✅ Model loaded successfully!")

# Modify the last layer for fine-tuning
x = model.layers[-2].output  # Get the second last layer output
x = Dropout(0.5, name="new_dropout")(x)  # Prevent duplicate layer names
x = Dense(len(medicine_classes), activation="softmax", name="new_output")(x)

# Create new fine-tuned model
fine_tuned_model = Model(inputs=model.input, outputs=x)

# Compile model
fine_tuned_model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.0001),
    loss="categorical_crossentropy",
    metrics=["accuracy"]
)

# Train model
fine_tuned_model.fit(
    X_train, y_train,
    validation_data=(X_val, y_val),
    epochs=10,
    batch_size=16
)

# Save the fine-tuned model
fine_tuned_model.save("D:/model training/fine_tuned_handwritten_medicine_model_v2.h5")
print("✅ Fine-tuning completed and model saved successfully!")
