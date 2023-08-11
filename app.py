import sys
import os
import logging
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import tiktoken
import re
from flasgger import Swagger
from flasgger.utils import swag_from

# Configuring logging to stderr
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

app = Flask(__name__)
swagger = Swagger(app)

# Users for basic auth (replace with your actual username and password)
users = {
    "user1": generate_password_hash("password1"),
}

def authenticate(username, password):
    if username in users and check_password_hash(users[username], password):
        return True
    return False

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not authenticate(auth.username, auth.password):
            return jsonify({"message": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated

def split_sentence(enc, sentence, token_limit):
    words = sentence.split()
    chunk = ''
    for word in words:
        temp_chunk = chunk + ' ' + word if chunk else word
        if len(enc.encode(temp_chunk)) <= token_limit:
            chunk = temp_chunk
        else:
            break
    return chunk

@app.route('/tokenize', methods=['POST'])
@swag_from('swagger.yaml')
@requires_auth
def tokenize():
    request_data = None
    if request.content_type == 'application/json':
        request_data = request.get_json()

    try:
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

        enc = tiktoken.encoding_for_model(model_name)

        chunks = []
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunk = ''

        for sentence in sentences:
            temp_chunk = chunk + ' ' + sentence if chunk else sentence
            if len(enc.encode(temp_chunk)) <= token_limit:
                chunk = temp_chunk
            else:
                if chunk:
                    chunks.append(chunk)
                chunk = ''
                while sentence:
                    split_chunk = split_sentence(enc, sentence, token_limit)
                    chunks.append(split_chunk)
                    sentence = sentence[len(split_chunk):].strip()

        if chunk:
            chunks.append(chunk)

        return jsonify({"chunks": chunks})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.after_request
def after_request(response):
    # Handling the case where there's nothing to log
    if response.content_length == 0:
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

if __name__ == '__main__':
    # Get port from environment variable or default to 8080
    port = int(os.getenv("PORT", 8080))
    app.run(debug=True, host='0.0.0.0', port=port)
