import sys
import os
import logging
import tiktoken
import re
from functools import wraps
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flasgger import Swagger
from flasgger.utils import swag_from

# Configuring logging to stderr for monitoring and debugging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

# Creating a Flask app instance
app = Flask(__name__)
# Enabling Swagger documentation for the API
swagger = Swagger(app)

# Users for basic authentication (hardcoded for demonstration purposes)
users = {
    "user1": generate_password_hash("password1"),
}

# Function to authenticate username and password
def authenticate(username, password):
    if username in users and check_password_hash(users[username], password):
        return True
    return False

# Decorator for requiring basic authentication
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not authenticate(auth.username, auth.password):
            return jsonify({"message": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated

# Function to split text into chunks based on token limits
def split_text(enc, text, token_limit):
    chunks = []

    # Recursive function to handle different levels of text splitting
    def recursive_split(content, level):
        nonlocal chunks
        if len(content.strip()) == 0:
            return
        token_count = len(enc.encode(content))
        if token_count <= token_limit:
            chunks.append(content)
            return

        # Splitting logic based on the current level
        if level == 0:  # Paragraph level
            parts = re.split(r'(\n\n+)', content)
        elif level == 1:  # Sentence level
            parts = re.split(r'([.!?]\s*)', content)
        elif level == 2:  # Sentence fragment level
            parts = re.split(r'([,;]\s*)', content)
        else:  # Token level
            buffer = ''  # Buffer to hold concatenated tokens within the token_limit
            token_parts = []  # List to hold chunks of tokens
            tokens = enc.encode(content)
            for token in tokens:
                decoded_token = enc.decode([token])
                # Concatenate the decoded token to the buffer if within the token_limit
                temp_buffer = buffer + decoded_token if buffer else decoded_token
                if len(enc.encode(temp_buffer)) <= token_limit:
                    buffer = temp_buffer
                else:
                    # If the buffer exceeds the token_limit, add to the token_parts
                    token_parts.append(buffer)
                    # Start a new buffer with the current decoded token
                    buffer = decoded_token
            if buffer:
                # Add any remaining buffer to token_parts
                token_parts.append(buffer)
            parts = token_parts

        buffer = ''
        for part in parts:
            if len(enc.encode(buffer + part)) <= token_limit:
                buffer += part
            else:
                # If the buffer exceeds the token_limit, recursively split it
                recursive_split(buffer, level + 1)
                # Start a new buffer with the current part
                buffer = part

        if buffer:
            # Recursively split any remaining buffer
            recursive_split(buffer, level + 1)

    recursive_split(text, 0)  # Start recursion at the paragraph level

    # Filter out empty strings before returning
    chunks = [chunk for chunk in chunks if chunk.strip()]

    return {"chunks": chunks}

# Endpoint for tokenizing text
@app.route('/tokenize', methods=['POST'])
@swag_from('swagger.yaml')
@requires_auth
def tokenize():
    # Checking content type
    request_data = None
    if request.content_type == 'application/json':
        request_data = request.get_json()

    try:
        # Validating required parameters
        if not request_data:
            return jsonify({"error": "JSON payload expected with content type 'application/json'"}), 400
        model_name = request_data.get('model_name')
        token_limit = request_data.get('token_limit')
        text = request_data.get('text')
        if not model_name or not token_limit or not text:
            return jsonify({"error": "model_name, token_limit, and text are required parameters"}), 400
        token_limit = int(token_limit)
        if token_limit <= 0:
            return jsonify({"error": "token_limit must be greater than 0"}), 400

        # Encoding and splitting text
        enc = tiktoken.encoding_for_model(model_name)
        return jsonify(split_text(enc, text, token_limit))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# After-request handler for logging
@app.after_request
def after_request(response):
    if response.content_length == 0:  # Skip logging if there's nothing to log
        return response

    log_data = {
        "request_method": request.method,
        "request_path": request.path,
        "request_args": request.args,
        "request_data": request.data.decode('utf-8'),
        "response_status": response.status,
        "response_content_length": response.content_length,
    }
    logger.info(log_data)
    return response

# Main entry point
if __name__ == '__main__':
    # Getting port from environment variable or defaulting to 8080
    port = int(os.getenv("PORT", 8080))
    app.run(debug=True, host='0.0.0.0', port=port)
