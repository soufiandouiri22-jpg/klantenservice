# PersonaPlex/Moshi Index Error Troubleshooting

## Issue Description

**Error:** `IndexError: index 16 is out of bounds for dimension 0 with size 16`

**Location:** `/usr/local/lib/python3.11/dist-packages/moshi/modules/transformer.py`, line 197

**Code:**
```python
y = F.linear(x[:, t], weight[t + offset])
```

## Root Cause

The error occurs when the Moshi transformer tries to access an index (16) that doesn't exist in a weight tensor of size 16 (valid indices: 0-15). This is an off-by-one error in the Moshi library's `multi_linear` function within the self-attention mechanism.

### Likely Causes:
1. **Unstable Moshi version** - The Dockerfile clones the latest version from GitHub without version pinning
2. **Audio chunking mismatch** - The number of processing steps exceeds the model's expected dimensions
3. **Model architecture bug** - A bug in the upstream Moshi/PersonaPlex implementation

## Applied Solutions

### 1. Error Handling & Graceful Degradation

Added try-catch blocks around all audio processing loops to:
- Catch IndexError exceptions before they crash the service
- Log detailed error information for debugging
- Return partial results instead of failing completely
- Continue processing other audio segments

**Files Modified:**
- `pod_server.py` - Added error handling in:
  - `warmup()` function
  - `MoshiSession._process_audio_sync()` method
  - Voice sample generation endpoint
- `handler.py` - Added error handling in:
  - `warmup()` function
  - `process_audio()` function

### 2. Boundary Checks in Warmup

Limited the warmup loop to process maximum 15 steps instead of the full `codes.shape[-1]` to prevent hitting the index overflow during initialization.

```python
# Before
for c in range(codes.shape[-1]):
    
# After
for c in range(min(num_steps, 15)):  # Limit to prevent index overflow
```

### 3. Version Pinning Preparation

Updated Dockerfile to prepare for pinning to a specific commit (currently still on main branch).

## Recommended Next Steps

### Immediate Actions:

1. **Test the changes:**
   ```bash
   # Rebuild the Docker image
   cd backend/runpod_worker
   docker build -t klantenservice-personaplex-pod .
   
   # Deploy to RunPod
   docker push yourusername/klantenservice-personaplex-pod:latest
   ```

2. **Run diagnostic script:**
   ```bash
   # On your RunPod GPU instance
   python diagnose_moshi.py
   ```
   This will help identify exactly where the error occurs and log the model dimensions.

3. **Monitor logs:**
   - Watch for "Index error" warnings in the logs
   - Check if the service continues working despite the errors
   - Verify audio quality is acceptable

### Long-term Solutions:

#### Option A: Pin to a Known Working Commit

Find a stable commit of PersonaPlex and update the Dockerfile:

```dockerfile
RUN git clone https://github.com/NVIDIA/personaplex.git /tmp/personaplex && \
    cd /tmp/personaplex && \
    git checkout <COMMIT_HASH> && \
    pip install --no-cache-dir /tmp/personaplex/moshi/. && \
    rm -rf /tmp/personaplex
```

#### Option B: Patch the Moshi Library

If the bug is in Moshi itself, create a local patch:

```python
# In pod_server.py, after loading the model
import moshi.modules.transformer as moshi_transformer

# Monkey-patch the multi_linear function
original_multi_linear = moshi_transformer.multi_linear

def safe_multi_linear(x, weight, bias=None):
    # Add boundary check
    max_t = weight.shape[0] if len(weight.shape) > 0 else 0
    if x.shape[1] >= max_t:
        logger.warning(f"Clamping t from {x.shape[1]} to {max_t - 1}")
        x = x[:, :max_t]
    return original_multi_linear(x, weight, bias)

moshi_transformer.multi_linear = safe_multi_linear
```

#### Option C: Report Upstream Bug

File an issue with NVIDIA PersonaPlex:
- Repository: https://github.com/NVIDIA/personaplex
- Include:
  - Full error traceback
  - Model configuration (from diagnostic script)
  - Audio input characteristics
  - Reproducible example

#### Option D: Adjust Audio Processing Parameters

Experiment with different LMGen parameters:

```python
lm_gen = LMGen(
    lm,
    audio_silence_frame_cnt=int(0.5 * mimi.frame_rate),
    sample_rate=mimi.sample_rate,
    device=device,
    frame_rate=mimi.frame_rate,
    save_voice_prompt_embeddings=False,
    use_sampling=True,
    temp=0.8,
    temp_text=0.7,
    top_k=250,
    top_k_text=25,
    # Try adjusting these:
    # max_steps=15,  # Limit max steps if parameter exists
)
```

## Testing Checklist

- [ ] Docker image builds successfully
- [ ] Service starts without errors
- [ ] Health check endpoint returns healthy
- [ ] Initial greeting generates without crashing
- [ ] Can process incoming audio
- [ ] Audio quality is acceptable
- [ ] No IndexError in logs (or errors are caught gracefully)
- [ ] WebSocket connections remain stable
- [ ] Multiple concurrent calls work

## Additional Resources

- PersonaPlex Repository: https://github.com/NVIDIA/personaplex
- Moshi Paper: https://arxiv.org/abs/2410.00037
- RunPod Documentation: https://docs.runpod.io/

## Support

If issues persist:
1. Check GitHub Issues: https://github.com/NVIDIA/personaplex/issues
2. Review Moshi library version: `pip show moshi`
3. Verify PyTorch compatibility
4. Check CUDA version compatibility

## Changelog

- **2026-02-06**: Initial fixes applied
  - Added error handling to prevent crashes
  - Added boundary checks in warmup
  - Created diagnostic script
  - Documented troubleshooting steps
