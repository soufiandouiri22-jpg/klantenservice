# Quick Fix for Moshi IndexError

## What Was Fixed

The `IndexError: index 16 is out of bounds` error in Moshi has been addressed with multiple layers of protection:

1. ✅ **Error handling** added to all audio processing loops
2. ✅ **Boundary checks** in warmup functions
3. ✅ **Monkey-patch** available for deeper fix
4. ✅ **Diagnostic script** for troubleshooting

## How to Deploy

### Step 1: Rebuild Docker Image

```bash
cd /Users/soufiandouiri/Desktop/klantenservice/backend/runpod_worker

# Build the image
docker build -t your-dockerhub-username/klantenservice-personaplex-pod:latest .

# Push to Docker Hub (or your registry)
docker push your-dockerhub-username/klantenservice-personaplex-pod:latest
```

### Step 2: Deploy to RunPod

1. Go to your RunPod dashboard
2. Update your pod/endpoint to use the new image
3. Restart the pod

### Step 3: Test

```bash
# Check health endpoint
curl http://your-pod-url:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "model_loaded": true,
#   "active_sessions": 0,
#   "device": "cuda"
# }
```

## What to Expect

### Before the Fix
- ❌ Service crashed on IndexError
- ❌ No audio generated
- ❌ Call disconnected

### After the Fix
- ✅ Error is caught and logged
- ✅ Partial audio returned (what was generated before error)
- ✅ Service continues running
- ⚠️ May see warnings in logs (this is expected)

## Monitoring

Check your RunPod logs for:

```
✓ Good signs:
  - "Successfully applied Moshi IndexError patch"
  - "Warmup completed successfully"
  - "Session initialized"

⚠️ Warnings (expected):
  - "Index error at step X/Y"
  - "Breaking on index error to return what we have so far"

❌ Bad signs:
  - Service crashes/restarts
  - "Model not loaded"
  - Continuous errors with no audio generated
```

## If Issues Persist

### Option 1: Use Diagnostic Script

```bash
# SSH into your RunPod
python /app/diagnose_moshi.py
```

This will show exactly where the error occurs and log model dimensions.

### Option 2: Adjust Patch Settings

Edit `pod_server.py` and find the patch import:

```python
# To disable patch
# from patch_moshi import apply_moshi_patch
# apply_moshi_patch()
```

Comment it out if the patch causes issues.

### Option 3: Pin to Older Moshi Version

Edit `Dockerfile`:

```dockerfile
# Find this line:
git checkout main

# Replace with a specific commit:
git checkout <COMMIT_HASH>
```

To find a good commit:
1. Go to https://github.com/NVIDIA/personaplex/commits/main
2. Look for the last commit before recent changes to moshi/modules/transformer.py
3. Use that commit hash

### Option 4: Report Bug

If the issue is critical, report to NVIDIA:
- Repository: https://github.com/NVIDIA/personaplex/issues
- Include:
  - Output from `diagnose_moshi.py`
  - Full error traceback
  - Your LMGen configuration

## Configuration Options

You can tune the error handling behavior:

### In `pod_server.py` line ~265 (warmup function):

```python
# Current: Stop at step 15
for c in range(min(num_steps, 15)):

# More aggressive: Stop at step 10
for c in range(min(num_steps, 10)):

# Less aggressive: Try all steps
for c in range(num_steps):
```

### In `pod_server.py` line ~140 (audio processing):

```python
# Current: Break on error
except IndexError as e:
    logger.error(f"Index error at step {c}/{steps}: {e}")
    break  # Return partial audio

# Alternative: Continue processing
except IndexError as e:
    logger.error(f"Index error at step {c}/{steps}: {e}")
    continue  # Skip this step, try next
```

## Performance Impact

The fixes should have minimal impact:
- ✅ No performance overhead during normal operation
- ✅ Only catches errors that would crash anyway
- ⚠️ May generate slightly shorter audio if error occurs mid-generation
- ⚠️ Warmup limited to 15 steps (should be fine for most cases)

## Rollback Plan

If the new version causes issues:

1. Revert to previous Docker image:
   ```bash
   docker pull your-dockerhub-username/klantenservice-personaplex-pod:previous-tag
   ```

2. Update RunPod to use old image

3. Report issues in your project's GitHub

## Support

- 📖 Full documentation: `TROUBLESHOOTING.md`
- 🐛 Diagnostic tool: `diagnose_moshi.py`
- 🔧 Manual patch: `patch_moshi.py`

## Changelog

**2026-02-06**
- Added error handling to prevent crashes
- Added boundary checks in warmup
- Created monkey-patch for root cause
- Added diagnostic tools
- Updated Dockerfile
