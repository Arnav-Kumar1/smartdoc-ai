# Base image - match your Python version
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install OS-level dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    # Add any other required system dependencies here
    && rm -rf /var/lib/apt/lists/*

# Set environment variables to force CPU-only installations
ENV CUDA_VISIBLE_DEVICES=-1
# Remove GPU-specific env vars as they're not needed for CPU-only
# ENV TF_FORCE_GPU_ALLOW_GROWTH=false
# ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:32

# Install Python dependencies with CPU-only flags
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt \
    --extra-index-url https://download.pytorch.org/whl/cpu

# Download NLTK data (single command)
RUN python -m nltk.downloader punkt punkt_tab

# Create necessary directories
RUN mkdir -p /app/data/uploaded_files /app/data/vector_store /app/data/db

# Copy project files (use .dockerignore to exclude unnecessary files)
COPY . .

# Set environment variables
ENV DATA_PATH=/app/data \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Expose backend port
EXPOSE 8000

# Start command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]