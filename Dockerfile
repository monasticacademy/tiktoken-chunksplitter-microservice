
# Use a base image with Rust for compiling Python libraries written in Rust
FROM rust:1.54 AS rust-base

# Use a Python base image and copy Rust toolchain from rust-base
FROM python:3.8-slim-buster

# Copy Rust toolchain
COPY --from=rust-base /usr/local/cargo /usr/local/cargo
COPY --from=rust-base /usr/local/rustup /usr/local/rustup
ENV PATH="/usr/local/cargo/bin:${PATH}"

# Set working directory
WORKDIR /app

# Install tiktoken from scratch
RUN pip install tiktoken

# Copy app.py and swagger.yaml into the working directory
COPY app.py .
COPY swagger.yaml .

# Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 8080
EXPOSE 8080

# Run app.py using gunicorn with a timeout of 2400 seconds on port 8080
CMD ["gunicorn", "-b", "0.0.0.0:8080", "-t", "2400", "app:app"]
