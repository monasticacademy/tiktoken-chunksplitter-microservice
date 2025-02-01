TikToken Microservice
===================

This microservice provides an API to tokenize text using TikToken into chunks based on a specific model's token limit.  It tries to find logical places at which to split the chunks, then recursively splits them at the next best place to get the proper sized chunk based on your specific token usecase.

API Endpoint
------------
- **Endpoint**: `/tokenize`
- **Method**: `POST`
- **Authentication**: Basic Authentication (default username: `user1`, password: `password1`)
- **Request Parameters**:
  - `model_name`: Name of the model to be used for tokenization (e.g., `gpt-4`)
  - `token_limit`: The maximum number of tokens allowed per chunk
  - `text`: The text to be tokenized

**Example Request**:
```json
{
  "model_name": "gpt-4",
  "token_limit": 1000,
  "text": "Your text here..."
}
```

**Response**:
The response will include an array of text chunks tokenized based on the specified token limit.

**Example Response**:
```json
{
  "chunks": ["Chunk 1...", "Chunk 2...", ...]
}
```

API Documentation
-----------------
The complete API documentation can be accessed via Swagger at `/apidocs` on the deployed application.

Logging
-------
The application logs information to standard error (stderr) after each request, including method, path, arguments, request data, response status, and content length.

Deployment to Cloud Run
-----------------------
1. Build the Docker image: `docker build -t tiktoken-microservice .`
2. Push the image to a container registry like Google Container Registry.
3. Deploy the image to Cloud Run using the Google Cloud Console or the `gcloud` command-line tool.
4. Set environment variables if needed and configure other settings as required.
5. The application will be accessible at the URL provided by Cloud Run and will listen on port 8080.

Please refer to the official [Cloud Run documentation](https://cloud.google.com/run/docs) for detailed instructions on deploying containerized applications.

Additional Information
----------------------
- The application uses Basic Authentication for securing the API endpoint.
- The logging mechanism handles cases where there's nothing to log (`response.content_length = 0`).
- The Rust environment is included in the Docker image for compiling Python libraries written in Rust.
- The application is configured to run with gunicorn with a timeout of 2400 seconds.

