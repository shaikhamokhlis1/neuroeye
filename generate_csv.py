import os
import csv

# Folder containing the dataset
dataset_folder = 'static/dataset'

# Output CSV file
csv_file = 'images_Rakan.csv'

# Initialize lists to store training and testing data separately
training_data = []
testing_data = []

# Traverse the dataset folder and organize paths into training and testing sets
for root, dirs, files in os.walk(dataset_folder):
    for file in files:
        # Only process image files
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
            # Create a relative path to the image and prepend "dataset/"
            relative_path = os.path.relpath(os.path.join(root, file), os.path.dirname(dataset_folder))
            relative_path = relative_path.replace('\\', '/')  # Ensure forward slashes

            # Check if the path belongs to training or testing set based on folder name
            if 'train' in root.lower():
                training_data.append((relative_path, root))  # Store path and folder name
            elif 'test' in root.lower():
                testing_data.append((relative_path, root))  # Store path and folder name

# Initialize the CSV with headers: id, imagePath, label_Dr. Laith
with open(csv_file, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['id', 'imagePath', 'label_Dr. Rakan'])

    id_counter = 0

    # Helper function to determine label
    def determine_label(folder):
        if 'normal' in folder.lower():
            return 'Normal'  # Automatically label images from the normal folder
        else:
            return 'Null'  # Set to Null for images needing labeling

    # Write testing data after training data
    for image_path, folder in testing_data:
        label = determine_label(folder)
        writer.writerow([id_counter, image_path, label])
        id_counter += 1

    # Write training data first
    for image_path, folder in training_data:
        label = determine_label(folder)
        writer.writerow([id_counter, image_path, label])
        id_counter += 1



print(f"CSV file '{csv_file}' generated with {id_counter} image paths.")
