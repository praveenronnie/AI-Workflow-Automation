FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies for pdf2image (poppler) and ML libraries (OpenMP for PyTorch/FAISS)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    poppler-utils \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Backend package lives under backend/
ENV PYTHONPATH=/app/backend

# Expose FastAPI default port (for when API service is enabled later)
EXPOSE 8000
