# PersonaPlex Dedicated Pod Server
# Build: docker build -t klantenservice-personaplex-pod .
# Push: docker push yourusername/klantenservice-personaplex-pod:latest
#
# This Dockerfile creates a FastAPI WebSocket server for real-time
# bidirectional audio streaming with PersonaPlex/Moshi.

FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

WORKDIR /app

# Install system dependencies including opus for sphn
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    libopus-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Clone PersonaPlex and install moshi package
RUN git clone https://github.com/NVIDIA/personaplex.git /tmp/personaplex && \
    pip install --no-cache-dir /tmp/personaplex/moshi/. && \
    rm -rf /tmp/personaplex

# Copy requirements and install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY pod_server.py /app/pod_server.py
COPY handler.py /app/handler.py

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/runpod-volume/cache/huggingface
ENV TRANSFORMERS_CACHE=/runpod-volume/cache/huggingface
ENV PORT=8000
ENV HOST=0.0.0.0

# Expose the WebSocket/HTTP port
EXPOSE 8000

# Health check for RunPod
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the FastAPI server
CMD ["python", "-u", "pod_server.py"]
