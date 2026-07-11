FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies for pdf2image (poppler)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    poppler-utils && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose Streamlit default port
EXPOSE 8501
