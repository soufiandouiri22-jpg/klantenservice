# PersonaPlex RunPod Worker

This is a RunPod Serverless worker for running NVIDIA PersonaPlex-7B speech-to-speech AI.

## Requirements

- RunPod account with GPU (24GB+ VRAM recommended, A100 or H100)
- HuggingFace account with accepted PersonaPlex license
- Docker for building the image

## Setup

### 1. Accept PersonaPlex License

Go to https://huggingface.co/nvidia/personaplex-7b-v1 and click "Agree and access repository".

### 2. Build Docker Image

```bash
cd backend/runpod_worker
docker build -t your-username/klantenservice-personaplex:latest .
docker push your-username/klantenservice-personaplex:latest
```

### 3. Create RunPod Serverless Endpoint

1. Go to RunPod Serverless
2. Create new endpoint
3. Use your Docker image: `your-username/klantenservice-personaplex:latest`
4. Set environment variable: `HF_TOKEN=hf_your_token_here`
5. Configure:
   - GPU: A100 80GB recommended
   - Max Workers: 3
   - Idle Timeout: 60 seconds (model loading is slow)

### 4. Update Backend Config

Add to your Render environment variables:
- `RUNPOD_API_KEY`: Your RunPod API key
- `RUNPOD_ENDPOINT_ID`: The endpoint ID from step 3

## API

### Initialize Session

```json
{
  "input": {
    "action": "init",
    "session_id": "unique-id",
    "persona_prompt": "Je bent Lisa, een klantenservice medewerker bij...",
    "voice_prompt": "NATF2.pt"
  }
}
```

### Process Audio

```json
{
  "input": {
    "action": "process",
    "session_id": "unique-id",
    "audio": "<base64 encoded PCM audio at 24kHz>"
  }
}
```

Response:
```json
{
  "audio": "<base64 encoded PCM response audio>",
  "transcript": {
    "user": "",
    "assistant": "Goedemiddag, waarmee kan ik u helpen?"
  }
}
```

### End Session

```json
{
  "input": {
    "action": "end",
    "session_id": "unique-id"
  }
}
```

## Available Voices

- Natural Female: `NATF0.pt`, `NATF1.pt`, `NATF2.pt`, `NATF3.pt`
- Natural Male: `NATM0.pt`, `NATM1.pt`, `NATM2.pt`, `NATM3.pt`
- Variety Female: `VARF0.pt` - `VARF4.pt`
- Variety Male: `VARM0.pt` - `VARM4.pt`

## Notes

- First request will take longer (model loading)
- Audio should be PCM 24kHz mono
- PersonaPlex is English-only (for now)

## Troubleshooting

### IndexError: index 16 is out of bounds

If you encounter this error, it's a known issue with Moshi's transformer. Multiple fixes have been applied:

1. **Error handling** - Catches the error and returns partial audio
2. **Boundary checks** - Prevents overflow in warmup
3. **Monkey-patch** - Optional deeper fix (applied automatically)

**Quick fix:**
- Rebuild and redeploy the Docker image (fixes are already in the code)
- See `QUICK_FIX.md` for deployment steps

**Detailed troubleshooting:**
- Run `python diagnose_moshi.py` in the container
- See `TROUBLESHOOTING.md` for comprehensive guide

**Files:**
- `QUICK_FIX.md` - Quick deployment guide
- `TROUBLESHOOTING.md` - Detailed troubleshooting
- `diagnose_moshi.py` - Diagnostic tool
- `patch_moshi.py` - Manual patch application

### Service Won't Start

1. Check HF_TOKEN is set correctly
2. Ensure GPU has enough VRAM (24GB+)
3. Check logs: `curl http://pod-url:8000/health`

### Poor Audio Quality

- Increase GPU memory
- Check audio input is 24kHz PCM
- Verify persona prompt is not too long

## Development

### Local Testing (with GPU)

```bash
# Build
docker build -t personaplex-test .

# Run
docker run --gpus all -p 8000:8000 \
  -e HF_TOKEN=your_token \
  personaplex-test

# Test
curl http://localhost:8000/health
```

### Debugging

```bash
# Run diagnostic
docker run --gpus all -it personaplex-test python diagnose_moshi.py

# Check logs
docker logs <container-id>
```
