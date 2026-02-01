# RunPod Serverless Worker for PersonaPlex-7B
# Build: docker build -t klantenservice-personaplex .
# Push: docker push yourusername/klantenservice-personaplex:latest

FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    runpod \
    transformers>=4.36.0 \
    accelerate>=0.25.0 \
    safetensors \
    sentencepiece \
    protobuf \
    numpy \
    scipy \
    soundfile \
    librosa

# Copy handler
COPY handler.py /app/handler.py

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TRANSFORMERS_CACHE=/runpod-volume/cache/huggingface
ENV HF_HOME=/runpod-volume/cache/huggingface

# Run the handler
CMD ["python", "-u", "handler.py"]
