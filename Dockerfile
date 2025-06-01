# Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install OS-level dependencies (remove ffmpeg)
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Set environment variables to force CPU-only installations
ENV CUDA_VISIBLE_DEVICES=-1
ENV TF_FORCE_GPU_ALLOW_GROWTH=false
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:32

# Install Python dependencies with CPU-only flags
COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu

# Download NLTK data
RUN python -m nltk.downloader punkt
RUN python -m nltk.downloader punkt_tab

# Create necessary directories
RUN mkdir -p /app/data/uploaded_files /app/data/vector_store /app/data/db

# Copy project files
COPY . .

# Set environment variables
ENV DATA_PATH=/app/data

# Expose backend port
EXPOSE 8000

# Start command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
