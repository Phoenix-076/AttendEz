# encode_images.py
import face_recognition
import os
import pickle

# Directory containing student images
student_images_dir = 'static/std_images'

# Lists to store encodings and names
known_face_encodings = []
known_face_names = []

# Iterate over each image file in the directory
for filename in os.listdir(student_images_dir):
    if filename.endswith('.jpg') or filename.endswith('.png'):
        # Load the image file
        image = face_recognition.load_image_file(os.path.join(student_images_dir, filename))

        # Get the face encodings for the image (assuming each image contains exactly one face)
        encodings = face_recognition.face_encodings(image)
        if encodings:  # If face encodings are found
            face_encoding = encodings[0]
            # Append the face encoding and the corresponding name (derived from filename)
            known_face_encodings.append(face_encoding)
            known_face_names.append(os.path.splitext(filename)[0])

# Save the encodings to a file for later use
with open('encodings.pickle', 'wb') as f:
    pickle.dump((known_face_encodings, known_face_names), f)

print("Encodings saved successfully.")
