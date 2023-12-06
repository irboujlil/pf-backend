import io
import os
from PIL import Image
from openai import OpenAI
from celery import Celery
import base64
import mimetypes
client = OpenAI(api_key= os.environ.get('API_TOKEN'))
from flask import Flask, request, jsonify
from pdf2image import convert_from_bytes
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Use REDIS_URL from environment variables if available, else default to localhost
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

app.config['CELERY_BROKER_URL'] = redis_url
app.config['result_backend'] = redis_url

# Initialize Celery
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)



def image_to_base64(image_path):
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type or not mime_type.startswith('image'):
        raise ValueError("The file type is not recognized as an image")

    with open(image_path, 'rb') as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

    image_base64 = f"data:{mime_type};base64,{encoded_string}"
    return image_base64

@app.route('/api/upload-pdf', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    filename = file.filename.lower()

    # Now process the file based on its type
    if filename.endswith('.pdf'):
        # Convert PDF stream to images
        images = convert_from_bytes(file.read())
        base64_images = []
        for image in images:
            # Convert images to base64 strings
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            base64_images.append(img_str)
        
        # Further processing and OpenAI Vision API call goes here...

    elif any(filename.endswith(ext) for ext in ['.png', '.jpg', '.jpeg']):
        # Handle image file
        # Convert to base64 string
        img_str = base64.b64encode(file.read()).decode()
        base64_images = [img_str]
        # OpenAI Vision API call goes here...

    else:
        return jsonify({'error': 'Unsupported file type'}), 400
    
    response = client.chat.completions.create(
    model="gpt-4-vision-preview",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe the attached image"},
                {"type": "image_url", "image_url": {"url": base64_images, "detail": "low"}}
            ]
        }
    ],
    max_tokens=300
    )
    #print(response.choices[0].message.content)
    return jsonify(response.choices[0].message.content)

    return jsonify({'response': openai_response})
    response = file({'file': base64_strings})
    return response

@app.route('/api/assist', methods=['POST'])
def assist():
    data = request.json
    prompt = data.get('prompt')

    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400

    try:
        response = client.chat.completions.create(model="gpt-4",  # Specify the desired model
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ])
        return jsonify(response.choices[0].message.content)
        print(jsonify(response_message))
        #return jsonify({'response': response['choices'][0]['message']['content']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    


@app.route('/api/file', methods=['POST'])
def file():
    data = request.json
    filedata = data['filedata']
    filename = data['filename']
    #print(data)
    #file_bytes = base64.b64decode(filedata.split(',')[1])  # Decode base64
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Give me a list of the critical points in this file. Keep and it short and concise, 3-5 is good, with 1-2 subpoints for each. After that, generate test questions regarding the critical points. At least 8 questions.",
                }
            ],
        }
    ]

    if filename.endswith('.pdf'):
        # Convert PDF bytes to images in memory
        images = convert_from_bytes(file.read())
        for image in images:
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
            messages[0]['content'].append({
                "type": "image_base64",
                "image_base64": img_str
            })
    else:
        # Read the image and convert it to base64
        #img_str = base64.b64encode(file.read()).decode('utf-8')
        messages[0]['content'].append({
            "type": "image_url", "image_url": {"url": filedata, "detail": "low"},
        })
    response = client.chat.completions.create(
    model="gpt-4-vision-preview",
    messages=messages,
    max_tokens=300
    )
    #print(response.choices[0].message.content)
    return jsonify(response.choices[0].message.content)

@celery.task
def process_file_task(filedata, filename):
    print(filename)
    messages = []
    # Your existing logic for processing the file
    file_bytes = base64.b64decode(filedata.split(',')[1])  # Decode base64
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Give me a list of the critical points in this file and keep and it short and concise, 3-5 is good, with 1-2 subpoints for each. After that, generate various test questions regarding the critical points. The various questions must be in multiple choice format, long response format, short response format, and fill in the blank format. Make sure the format is given properly and clean. At least 8 questions.",
                }
            ],
        }
    ]

    #messages = []
    #file_bytes = base64.b64decode(filedata.split(',')[1])  # Decode base64

    if filename.endswith('.pdf'):
        images = convert_from_bytes(file_bytes)
        for image in images:
            # Resize or compress the image if necessary
            image = resize_and_compress_image(image)  # Function to be implemented
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG", quality=85)  # Adjust quality to manage size
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            img_data_uri = f"data:image/jpeg;base64,{img_base64}"
            messages[0]["content"].append({"type": "image_url", "image_url": {"url": img_data_uri, "detail": "low"}})
    else:
        # Read the image and convert it to base64
        #img_str = base64.b64encode(file.read()).decode('utf-8')
        messages[0]['content'].append({
            "type": "image_url", "image_url": {"url": filedata, "detail": "low"},
        })
    print(messages)
    response = client.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=messages,
        max_tokens=400
    )
    return response.choices[0].message.content



@app.route('/api/image', methods=['POST'])
def file2():
    data = request.json
    filedata = data['filedata']
    filename = data['filename']
    #print(filedata)
    print(filename)

    # Enqueue the task
    task = process_file_task.delay(filedata, filename)
    
    return jsonify({"task_id": task.id}), 202

@app.route('/api/task/<task_id>', methods=['GET'])
def get_task_status(task_id):
    task = process_file_task.AsyncResult(task_id)
    if task.state == 'PENDING':
        print("PENDING PDF")
        return jsonify({"status": "pending"}), 202
    elif task.state == 'FAILURE':
        print("FAILED IN PDF")
        return jsonify({"status": "failure", "error": str(task.info)}), 500
    print(task.result)
    return jsonify({"status": "success", "result": task.result})

def resize_and_compress_image(image, max_width=1280, max_height=720, quality=85):
    """
    Resize and compress an image.
    max_width: Maximum width of the resized image.
    max_height: Maximum height of the resized image.
    quality: JPEG quality for compression.
    """
    # Resize the image
    image.thumbnail((max_width, max_height))

    # Compress the image
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG", quality=quality)
    
    # Get the compressed image
    compressed_image = Image.open(buffered)

    return compressed_image

@app.route('/')
def home():
    return "Hello, this is the Python Flask backend!"


@app.route('/api/data')
def get_data():
    # This is where you can fetch or compute data
    data = {
        "message": "Data from Flask backend",
        "items": [1, 2, 3, 4, 5]
    }
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)



