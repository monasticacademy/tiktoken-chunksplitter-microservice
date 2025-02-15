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

# Function to authenticate API Key
def authenticate(api_key):
    env_key = os.getenv('API_KEY')
    logger.info(f"Received API key: {api_key}")
    logger.info(f"Environment API key: {env_key}")
    logger.info(f"Keys match: {api_key == env_key}")
    if api_key == env_key:
        return True
    return False

# Decorator for requiring basic authentication
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Try different ways headers might be formatted
        auth = (request.headers.get('API_KEY') or 
                request.headers.get('Api-Key') or 
                request.headers.get('api_key') or
                request.headers.get('api-key'))
        
        logger.error("==== AUTH DEBUG ====")
        logger.error(f"All Headers: {dict(request.headers)}")
        logger.error(f"Raw Authorization: {request.headers.get('Authorization')}")
        logger.error(f"API_KEY from headers (all attempts): {auth}")
        logger.error(f"API_KEY from env: {os.getenv('API_KEY')}")
        logger.error("===================")
        
        if not auth or not authenticate(auth):
            return jsonify({"message": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated

# Function to split text into chunks based on token limits
def split_text(enc, text, token_limit):
    # Initialize an empty list to hold the chunks of text
    chunks = []

    # Define a recursive function to split the content at different levels
    def recursive_split(content, level):
        # Access the outer variable chunks
        nonlocal chunks
        
        # If the content is empty, return without doing anything
        if len(content.strip()) == 0:
            return
        
        # Get the token count of the content
        token_count = len(enc.encode(content))
        
        # If the token count is within the limit, add the content to chunks and return
        if token_count <= token_limit:
            chunks.append(content)
            return

        # Split the content based on the current level
        if level == 0:  # Paragraph level: split on two or more newline characters
            parts = re.split(r'(\n\n+)', content)
        elif level == 1:  # Line level: split on single newline characters
            parts = re.split(r'(\n)', content)
        elif level == 2:  # Sentence level: split on sentence-ending punctuation
            parts = re.split(r'([.!?]\s*)', content)
            parts = [parts[i] + parts[i + 1] if i + 1 < len(parts) else parts[i] for i in range(0, len(parts), 2)]
        elif level == 3:  # Sentence fragment level: split on commas and semicolons
            parts = re.split(r'([,;]\s*)', content)
            parts = [parts[i] + parts[i + 1] if i + 1 < len(parts) else parts[i] for i in range(0, len(parts), 2)]
        else:  # Token level: split by individual tokens
            buffer = ''
            token_parts = []
            tokens = enc.encode(content)
            for token in tokens:
                decoded_token = enc.decode([token])
                temp_buffer = buffer + decoded_token if buffer else decoded_token
                # If the buffer with the next token is within the limit, add the token to the buffer
                if len(enc.encode(temp_buffer)) <= token_limit:
                    buffer = temp_buffer
                else:
                    # If the buffer with the next token exceeds the limit, add the buffer to parts and reset the buffer
                    token_parts.append(buffer)
                    buffer = decoded_token
            if buffer:
                token_parts.append(buffer)
            parts = token_parts

        # Initialize a buffer to hold parts of the content that fit within the token limit
        buffer = ''
        for part in parts:
            # If the buffer with the next part is within the limit, add the part to the buffer
            if len(enc.encode(buffer + part)) <= token_limit:
                buffer += part
            else:
                # If the buffer with the next part exceeds the limit, recursively split the buffer at the next level
                recursive_split(buffer, level + 1)
                # Reset the buffer with the current part
                buffer = part

        # If there's any content left in the buffer, recursively split it at the next level
        if buffer:
            recursive_split(buffer, level + 1)

    # Start the recursion at the paragraph level
    recursive_split(text, 0)
    
    # Filter out empty strings and return the chunks
    chunks = [chunk for chunk in chunks if chunk.strip()]
    return {"chunks": chunks}

# Endpoint for tokenizing text
@app.route('/tokenize', methods=['POST'])
@swag_from('swagger.yaml')
@requires_auth
def tokenize():
    try:
        # Attempt to parse JSON; if the JSON is malformed, Flask will catch the exception.
        data = request.get_json()
        if not data:
            raise ValueError("No JSON found in request.")
    except Exception as e:
        return jsonify({"error": f"Invalid JSON: {str(e)}"}), 400

    # Log the request info for debugging
    logger.info(f"Raw request data: {request.data.decode('utf-8')}")
    logger.info(f"Parsed JSON data: {data}")

    # Validating required parameters
    if not data:
        logger.error("No JSON data found in request. "
                     f"Content-Type was {request.content_type}")
        return jsonify({
            "error": "JSON payload expected with content type 'application/json'"
        }), 400

    model_name = data.get('model_name')
    token_limit = data.get('token_limit')
    text = data.get('text')

    if not model_name or not token_limit or not text:
        logger.error(f"Missing params. Received: model_name={model_name}, "
                     f"token_limit={token_limit}, text={text}")
        return jsonify({"error": "model_name, token_limit, and text are required parameters"}), 400

    token_limit = int(token_limit)
    if token_limit <= 0:
        logger.error(f"token_limit must be > 0, received: {token_limit}")
        return jsonify({"error": "token_limit must be greater than 0"}), 400

    # Encoding and splitting text
    enc = tiktoken.encoding_for_model(model_name)
    result = split_text(enc, text, token_limit)
    logger.info(f"Split text result: {result}")
    return jsonify(result)

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
