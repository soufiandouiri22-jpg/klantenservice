# RunPod Serverless Worker for PersonaPlex-7B
# Build: docker build -t klantenservice-personaplex .
# Push: docker push yourusername/klantenservice-personaplex:latest

FROM runpod/pytorch:2.4.0-py3.12-cuda12.4.1-devel-ubuntu22.04

WORKDIR /app

# Install system dependencies including opus for sphn
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    libopus-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Clone PersonaPlex and install moshi package
RUN git clone https://github.com/NVIDIA/personaplex.git /tmp/personaplex && \
    pip install --no-cache-dir /tmp/personaplex/moshi/. && \
    rm -rf /tmp/personaplex

# Install additional Python dependencies
RUN pip install --no-cache-dir \
    runpod>=1.6.0 \
    huggingface_hub \
    sphn

# Copy handler
COPY handler.py /app/handler.py

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/runpod-volume/cache/huggingface
ENV TRANSFORMERS_CACHE=/runpod-volume/cache/huggingface

# Run the handler
CMD ["python", "-u", "handler.py"]
