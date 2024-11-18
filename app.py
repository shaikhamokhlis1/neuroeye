from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import csv
import os
import boto3
from io import StringIO
from dotenv import load_dotenv


app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure key

load_dotenv()

aws_access_key = os.getenv("MY_AWS_ACCESS_KEY")
aws_secret_key = os.getenv("MY_AWS_SECRET_KEY")

# AWS S3 Configuration
s3_client = boto3.client(
    's3',
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key,
    region_name='eu-central-1'
)

BUCKET_NAME = 'labeling2'

user_csv_files = {
    'Dr. Abdullah': 'images_Abdullah.csv',
    'Dr. Laith': 'images_Laith.csv',
    'Dr. Lama' : 'images_Lama.csv',
    'Dr. Yasser' : 'images_Yasser.csv'
}

# Dummy user credentials
users = {
    'Dr. Abdullah': 'Abdullah123',
    'Dr. Laith': 'Laith123',
    'Dr. Lama' : 'Lama123',
    'Dr. Yasser' : 'Yasser123'
}


ADMIN_USERNAME = 'shaikha'
ADMIN_PASSWORD = 'shaikha1'

# Helper functions to interact with S3
def read_csv_from_s3(file_name):
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_name)
        data = response['Body'].read().decode('utf-8')
        csv_data = StringIO(data)
        return list(csv.DictReader(csv_data))
    except Exception as e:
        print(f"Error reading CSV from S3: {e}")
        return []

def write_csv_to_s3(file_name, rows, fieldnames):
    try:
        csv_data = StringIO()
        csv_writer = csv.DictWriter(csv_data, fieldnames=fieldnames)
        csv_writer.writeheader()
        csv_writer.writerows(rows)

        # Debugging output
        print(f"Attempting to write {len(rows)} rows to {file_name} on S3.")

        s3_client.put_object(Bucket=BUCKET_NAME, Key=file_name, Body=csv_data.getvalue())
        print(f"{file_name} successfully uploaded to S3")
    except Exception as e:
        print(f"Error writing CSV to S3: {e}")


# Home page route
@app.route('/')
def home():
    return render_template('welcome.html')

# User login route
@app.route('/user_login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username] == password:
            session['username'] = username
            return redirect(url_for('label'))
        else:
            return "Invalid username or password."
    return render_template('user_login.html')

# Labeling page for logged-in users
@app.route('/label')
def label():
    if 'username' in session:
        username = session['username']
        s3_file_key = user_csv_files.get(username)

        if not s3_file_key:
            return "Error: User file not found", 500

        label_column = f'label_{username}'
        total_cataract_images = 0
        labeled_cataract_images = 0

        try:
            rows = read_csv_from_s3(s3_file_key)

            for row in rows:
                # Count total cataract images
                if 'cataract' in row['imagePath'].lower():
                    total_cataract_images += 1

                    # Check if the cataract image has been labeled
                    if row.get(label_column, '').strip() != 'Null':
                        labeled_cataract_images += 1

        except Exception as e:
            print(f"Error reading CSV from S3: {e}")
            return "Error reading CSV file", 500

        # Pass progress data to the template
        return render_template(
            'index.html',
            username=username,
            labeled_cataract_images=labeled_cataract_images,
            total_cataract_images=total_cataract_images
        )
    else:
        return redirect(url_for('user_login'))


# Admin login route
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return "Invalid admin credentials."
    return render_template('admin_login.html')

# Admin dashboard route
@app.route('/admin_dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    total_images = {}
    normal_images = {}
    cataract_images = {}
    user_labels_normal = {}
    user_labels_cataract = {}

    try:
        for user, file_name in user_csv_files.items():
            # Initialize counters for each user
            total_images[user] = 0
            normal_images[user] = 0
            cataract_images[user] = 0
            user_labels_normal[user] = 0
            user_labels_cataract[user] = 0

            # Load each user's specific CSV file
            rows = read_csv_from_s3(file_name)
            for row in rows:
                total_images[user] += 1
                if 'normal' in row['imagePath'].lower():
                    normal_images[user] += 1
                    if row.get(f'label_{user}', '').strip() != 'Null':
                        user_labels_normal[user] += 1
                else:
                    cataract_images[user] += 1
                    if row.get(f'label_{user}', '').strip() != 'Null':
                        user_labels_cataract[user] += 1

        # Check if total_images, normal_images, and cataract_images are identical across all users
        unique_total_images = set(total_images.values())
        unique_normal_images = set(normal_images.values())
        unique_cataract_images = set(cataract_images.values())

        # If they are identical, get the common value; otherwise, keep them as dictionaries
        total_images_shared = unique_total_images.pop() if len(unique_total_images) == 1 else total_images
        normal_images_shared = unique_normal_images.pop() if len(unique_normal_images) == 1 else normal_images
        cataract_images_shared = unique_cataract_images.pop() if len(unique_cataract_images) == 1 else cataract_images

        # Calculate label percentages for each user
        total_labeled = {user: user_labels_normal[user] + user_labels_cataract[user] for user in users}
        labeled_percentage_normal = {
            user: (user_labels_normal[user] / normal_images[user]) * 100 if normal_images[user] > 0 else 0 for user in users
        }
        labeled_percentage_cataract = {
            user: (user_labels_cataract[user] / cataract_images[user]) * 100 if cataract_images[user] > 0 else 0 for user in users
        }
        labeled_percentage_total = {
            user: (total_labeled[user] / total_images[user]) * 100 if total_images[user] > 0 else 0 for user in users
        }

        # Calculate overall summary statistics
        overall_total_images = sum(total_images.values())
        overall_labeled_images = sum(total_labeled.values())
        overall_completion_percentage = (overall_labeled_images / overall_total_images) * 100 if overall_total_images > 0 else 0
        overall_unlabeled_images = overall_total_images - overall_labeled_images

        # Pass everything to the template
        return render_template(
            'admin_dashboard.html',
            total_images=total_images_shared,
            normal_images=normal_images_shared,
            cataract_images=cataract_images_shared,
            user_labels_normal=user_labels_normal,
            user_labels_cataract=user_labels_cataract,
            total_labeled=total_labeled,
            labeled_percentage_normal=labeled_percentage_normal,
            labeled_percentage_cataract=labeled_percentage_cataract,
            labeled_percentage_total=labeled_percentage_total,
            # Additional overall summary statistics
            overall_total_images=overall_total_images,
            overall_labeled_images=overall_labeled_images,
            overall_unlabeled_images=overall_unlabeled_images,
            overall_completion_percentage=overall_completion_percentage
        )

    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return "Error reading CSV file", 500


# Get images for the logged-in user to label
@app.route('/get_images')
def get_images():
    image_urls = []
    username = session.get('username')
    if not username:
        return redirect(url_for('user_login'))

    # Get the correct CSV file for the logged-in user
    s3_file_key = user_csv_files.get(username)
    if not s3_file_key:
        return jsonify([]), 500

    label_column = f'label_{username}'

    try:
        rows = read_csv_from_s3(s3_file_key)
        print(f"Fetched {len(rows)} rows from S3 for {username}.")  # Debugging
        for row in rows:
            if row.get(label_column, '').strip() == 'Null':
                image_urls.append(row['imagePath'])
        print(f"Unlabeled images for {username}: {image_urls}")  # Debugging
        return jsonify(image_urls)
    except Exception as e:
        print(f"Error reading CSV from S3: {e}")
        return jsonify([]), 500


@app.route('/save_label', methods=['POST'])
def save_label():
    if 'username' in session:
        try:
            data = request.json
            image_url = data['imagePath']
            label = data['label']
            username = session.get('username')

            # Get the correct CSV file for the logged-in user
            file_name = user_csv_files.get(username)
            if not file_name:
                return jsonify({'status': 'Error: User file not found'}), 500

            rows = read_csv_from_s3(file_name)

            # Update the label in the appropriate row
            for row in rows:
                if row['imagePath'] == image_url:
                    row[f'label_{username}'] = label

            # Dynamically determine fieldnames based on existing CSV headers
            if rows:
                fieldnames = rows[0].keys()
            else:
                # Default fieldnames if the file is empty
                fieldnames = ['id', 'imagePath'] + [f'label_{user}' for user in users]

            # Write the updated rows back to S3
            write_csv_to_s3(file_name, rows, fieldnames)

            # Return a success response for JavaScript to handle
            return jsonify({'status': 'Label updated successfully'})

        except Exception as e:
            print(f"Error occurred: {e}")
            return jsonify({'status': 'Error occurred', 'message': str(e)}), 500
    else:
        return redirect(url_for('user_login'))


# Thank you page route
@app.route('/thankyou')
def thankyou():
    return render_template('thankyou.html')

# Logout route for regular users
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

# Logout route for admin users
@app.route('/admin_logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('home'))

from flask import Response

# Download CSV file route (admin access only)
from flask import Response

@app.route('/download_csv')
def download_csv():
    if session.get('admin'):
        user = request.args.get('user')  # Get the user from the dropdown selection
        if user == 'merged':
            # Merge the CSV files
            return download_merged_csv()
        else:
            # Download the specific user's CSV file
            file_name = user_csv_files.get(user)
            if not file_name:
                return "Error: User file not found", 500

            try:
                response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_name)
                data = response['Body'].read().decode('utf-8')

                # Set response headers to trigger download
                return Response(
                    data,
                    mimetype='text/csv',
                    headers={"Content-Disposition": f"attachment;filename={file_name}"}
                )
            except Exception as e:
                print(f"Error downloading CSV from S3: {e}")
                return "Error downloading CSV file", 500
    return "Unauthorized", 403

@app.route('/get_progress')
def get_progress():
    if 'username' in session:
        username = session['username']
        s3_file_key = user_csv_files.get(username)

        if not s3_file_key:
            return jsonify({'error': 'User file not found'}), 500

        label_column = f'label_{username}'
        total_cataract_images = 0
        labeled_cataract_images = 0

        try:
            rows = read_csv_from_s3(s3_file_key)

            for row in rows:
                if 'cataract' in row['imagePath'].lower():
                    total_cataract_images += 1
                    if row.get(label_column, '').strip() != 'Null':
                        labeled_cataract_images += 1

            return jsonify({
                'labeled_cataract_images': labeled_cataract_images,
                'total_cataract_images': total_cataract_images
            })
        except Exception as e:
            print(f"Error fetching progress: {e}")
            return jsonify({'error': 'Error fetching progress'}), 500
    else:
        return jsonify({'error': 'Unauthorized'}), 403



import pandas as pd

def download_merged_csv():
    try:
        # Step 1: Load each CSV into a DataFrame and check for user-specific label columns
        data_frames = []
        for user, file_name in user_csv_files.items():
            print(f"Loading CSV for {user} from S3.")
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_name)
            csv_data = response['Body'].read().decode('utf-8')
            df = pd.read_csv(StringIO(csv_data))
            print(f"Loaded CSV for {user}: {df.head()}")

            # Check for the user's specific label column; create it if it doesn't exist
            user_label_column = f'label_{user}'
            if user_label_column not in df.columns:
                print(f"Warning: '{user_label_column}' column not found in {file_name}. Adding it as 'Null'.")
                df[user_label_column] = 'Null'  # Fill missing label column with 'Null'

            # Retain only necessary columns for merging
            data_frames.append(df[['id', 'imagePath', user_label_column]])

        # Step 2: Merge the DataFrames on 'id' and 'imagePath', filling missing values with "Null"
        print("Merging DataFrames.")
        merged_df = data_frames[0]
        for df in data_frames[1:]:
            user_label_column = df.columns[-1]  # Get the specific label column name for merging
            merged_df = pd.merge(merged_df, df, on=['id', 'imagePath'], how='outer')

        # Step 3: Replace any NaN values in the label columns with "Null"
        label_columns = [f'label_{user}' for user in user_csv_files.keys()]
        merged_df[label_columns] = merged_df[label_columns].fillna('Null')
        print("Merged DataFrame:", merged_df.head())

        # Step 4: Convert the merged DataFrame back to CSV format
        merged_csv_data = StringIO()
        merged_df.to_csv(merged_csv_data, index=False)
        merged_csv_content = merged_csv_data.getvalue()

        # Step 5: Return as downloadable response
        return Response(
            merged_csv_content,
            mimetype='text/csv',
            headers={"Content-Disposition": "attachment;filename=merged_labels.csv"}
        )

    except Exception as e:
        print(f"Error merging CSV files: {e}")
        return f"Error merging CSV files: {e}", 500



def download_csv_from_s3(file_name):
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_name)
        data = response['Body'].read().decode('utf-8')
        print(data)  # This will print the contents of the file for debugging
        return data  # Optionally return the data if needed elsewhere
    except Exception as e:
        print(f"Error downloading CSV from S3: {e}")
        return None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
