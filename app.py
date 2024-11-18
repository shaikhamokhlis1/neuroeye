from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import csv
import os
import boto3
from io import StringIO
from dotenv import load_dotenv


app = Flask(_name_)
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
    'Dr. Lama': 'images_Lama.csv',
    'Dr. Yasser': 'images_Yasser.csv'
}

users = {
    'Dr. Abdullah': 'Abdullah123',
    'Dr. Laith': 'Laith123',
    'Dr. Lama': 'Lama123',
    'Dr. Yasser': 'Yasser123'
}

ADMIN_USERNAME = 'shaikha'
ADMIN_PASSWORD = 'shaikha1'

# Helper functions
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

        s3_client.put_object(Bucket=BUCKET_NAME, Key=file_name, Body=csv_data.getvalue())
    except Exception as e:
        print(f"Error writing CSV to S3: {e}")


@app.route('/')
def home():
    return render_template('welcome.html')


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
                if 'cataract' in row['imagePath'].lower():
                    total_cataract_images += 1

                    if row.get(label_column, '').strip() != 'Null':
                        labeled_cataract_images += 1

        except Exception as e:
            print(f"Error reading CSV from S3: {e}")
            return "Error reading CSV file", 500

        return render_template(
            'index.html',
            username=username,
            labeled_cataract_images=labeled_cataract_images,
            total_cataract_images=total_cataract_images
        )
    else:
        return redirect(url_for('user_login'))


@app.route('/get_images')
def get_images():
    image_urls = []
    username = session.get('username')
    if not username:
        return redirect(url_for('user_login'))

    s3_file_key = user_csv_files.get(username)
    if not s3_file_key:
        return jsonify([]), 500

    label_column = f'label_{username}'

    try:
        rows = read_csv_from_s3(s3_file_key)
        for row in rows:
            if row.get(label_column, '').strip() == 'Null':
                image_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': BUCKET_NAME, 'Key': row['imagePath']},
                    ExpiresIn=3600  # URL valid for 1 hour
                )
                image_urls.append(image_url)
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

            file_name = user_csv_files.get(username)
            if not file_name:
                return jsonify({'status': 'Error: User file not found'}), 500

            rows = read_csv_from_s3(file_name)

            for row in rows:
                if row['imagePath'] == image_url:
                    row[f'label_{username}'] = label

            if rows:
                fieldnames = rows[0].keys()
            else:
                fieldnames = ['id', 'imagePath'] + [f'label_{user}' for user in users]

            write_csv_to_s3(file_name, rows, fieldnames)

            return jsonify({'status': 'Label updated successfully'})

        except Exception as e:
            print(f"Error occurred: {e}")
            return jsonify({'status': 'Error occurred', 'message': str(e)}), 500
    else:
        return redirect(url_for('user_login'))


@app.route('/thankyou')
def thankyou():
    return render_template('thankyou.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))


if _name_ == '_main_':
    app.run(host='0.0.0.0', port=10000)