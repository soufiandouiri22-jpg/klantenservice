"""
klantenservice.ai - RunPod Serverless Worker for PersonaPlex-7B
Real-time speech-to-speech conversational AI using NVIDIA PersonaPlex

This worker runs on RunPod Serverless with GPU and handles:
- Loading PersonaPlex/Moshi models
- Processing audio input
- Generating audio responses
"""
import os
import base64
import logging
import json
import tempfile
from typing import Optional, List
from pathlib import Path

import runpod
import numpy as np
import torch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Moshi IndexError patch - fixes 4 overflow bugs in transformer.py
from patch_moshi import apply_moshi_patch

# Global model instances (loaded once, reused across requests)
mimi = None
other_mimi = None
lm_gen = None
text_tokenizer = None
frame_size = None
device = "cuda" if torch.cuda.is_available() else "cpu"

# Session state for multi-turn conversations
sessions = {}


def load_models():
    """Load PersonaPlex/Moshi models from HuggingFace."""
    global mimi, other_mimi, lm_gen, text_tokenizer, frame_size
    
    if mimi is not None:
        logger.info("Models already loaded")
        return
    
    logger.info("Loading PersonaPlex models...")
    
    # Import moshi modules
    from moshi.models import loaders, LMGen
    import sentencepiece
    from huggingface_hub import hf_hub_download
    
    # Apply Moshi patches BEFORE any model inference
    apply_moshi_patch()
    
    hf_repo = "nvidia/personaplex-7b-v1"
    
    # Download config to increment counter
    hf_hub_download(hf_repo, "config.json")
    
    # 1) Load Mimi encoders/decoders
    logger.info("Loading Mimi encoder/decoder...")
    mimi_weight = hf_hub_download(hf_repo, loaders.MIMI_NAME)
    mimi = loaders.get_mimi(mimi_weight, device)
    other_mimi = loaders.get_mimi(mimi_weight, device)
    logger.info("Mimi loaded")
    
    # 2) Load tokenizer
    logger.info("Loading tokenizer...")
    tokenizer_path = hf_hub_download(hf_repo, loaders.TEXT_TOKENIZER_NAME)
    text_tokenizer = sentencepiece.SentencePieceProcessor(tokenizer_path)
    logger.info("Tokenizer loaded")
    
    # 3) Load Moshi LM
    logger.info("Loading Moshi LM (this may take a while)...")
    moshi_weight = hf_hub_download(hf_repo, loaders.MOSHI_NAME)
    lm = loaders.get_moshi_lm(moshi_weight, device=device)
    lm.eval()
    logger.info("Moshi LM loaded")
    
    # 4) Create LMGen for generation
    frame_size = int(mimi.sample_rate / mimi.frame_rate)
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
    )
    
    # Set streaming mode
    mimi.streaming_forever(1)
    other_mimi.streaming_forever(1)
    lm_gen.streaming_forever(1)
    
    # Warmup
    logger.info("Warming up models...")
    warmup()
    
    logger.info("PersonaPlex models loaded successfully!")


def warmup():
    """Run warmup to initialize CUDA graphs."""
    global mimi, other_mimi, lm_gen, frame_size
    
    try:
        for _ in range(4):
            chunk = torch.zeros(1, 1, frame_size, dtype=torch.float32, device=device)
            codes = mimi.encode(chunk)
            _ = other_mimi.encode(chunk)
            # Process steps - if IndexError occurs, we catch it and continue
            for c in range(codes.shape[-1]):
                try:
                    tokens = lm_gen.step(codes[:, :, c : c + 1])
                    if tokens is None:
                        continue
                    _ = mimi.decode(tokens[:, 1:9])
                    _ = other_mimi.decode(tokens[:, 1:9])
                except IndexError as e:
                    logger.warning(f"Index error during warmup at step {c}: {e}")
                    # Skip rest of warmup but continue startup
                    break
        
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        
        logger.info("Warmup completed successfully")
    except Exception as e:
        logger.error(f"Error during warmup: {e}", exc_info=True)
        logger.info("Continuing without full warmup - first requests may be slower")
        # Continue anyway - model may still work


def wrap_with_system_tags(text: str) -> str:
    """Add system tags as the model expects."""
    cleaned = text.strip()
    if cleaned.startswith("<|system|>") and cleaned.endswith("<|/system|>"):
        return cleaned
    return f"<|system|> {cleaned} <|/system|>"


def init_session(session_id: str, text_prompt: str, voice_prompt: str = "NATF2.pt"):
    """Initialize a new conversation session."""
    global mimi, other_mimi, lm_gen, text_tokenizer, sessions
    
    from huggingface_hub import hf_hub_download
    import tarfile
    
    logger.info(f"Initializing session {session_id}")
    
    # Download voice prompts if needed
    hf_repo = "nvidia/personaplex-7b-v1"
    voices_tgz = hf_hub_download(hf_repo, "voices.tgz")
    voices_tgz = Path(voices_tgz)
    voices_dir = voices_tgz.parent / "voices"
    
    if not voices_dir.exists():
        logger.info(f"Extracting voice prompts...")
        with tarfile.open(voices_tgz, "r:gz") as tar:
            tar.extractall(path=voices_tgz.parent)
    
    voice_prompt_path = str(voices_dir / voice_prompt)
    
    # Reset streaming state
    mimi.reset_streaming()
    other_mimi.reset_streaming()
    lm_gen.reset_streaming()
    
    # Load voice prompt
    if voice_prompt_path.endswith('.pt'):
        lm_gen.load_voice_prompt_embeddings(voice_prompt_path)
    else:
        lm_gen.load_voice_prompt(voice_prompt_path)
    
    # Set text prompt
    if text_prompt:
        lm_gen.text_prompt_tokens = text_tokenizer.encode(wrap_with_system_tags(text_prompt))
    else:
        lm_gen.text_prompt_tokens = None
    
    # Run system prompts phase
    lm_gen.step_system_prompts(mimi)
    mimi.reset_streaming()
    
    # Store session
    sessions[session_id] = {
        "text_prompt": text_prompt,
        "voice_prompt": voice_prompt,
        "transcript_user": [],
        "transcript_assistant": [],
    }
    
    logger.info(f"Session {session_id} initialized")
    return {"status": "initialized", "session_id": session_id}


def process_audio(session_id: str, audio_b64: str) -> dict:
    """Process audio input and generate response."""
    global mimi, other_mimi, lm_gen, text_tokenizer, frame_size
    
    from moshi.models.lm import _iterate_audio as lm_iterate_audio
    from moshi.models.lm import encode_from_sphn as lm_encode_from_sphn
    
    if session_id not in sessions:
        logger.error(f"Session {session_id} not in sessions dict: {list(sessions.keys())}")
        return {"error": f"Session {session_id} not found. Call init first."}
    
    # Decode input audio (PCM 24kHz)
    audio_bytes = base64.b64decode(audio_b64)
    audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    
    logger.info(f"Audio decoded: {len(audio_np)} samples, duration={len(audio_np)/24000:.2f}s")
    
    # Reshape for model (1, T) - keep on CPU for _iterate_audio (numpy ops)
    user_audio = torch.from_numpy(audio_np).unsqueeze(0)
    
    # Process through model
    generated_frames = []
    generated_text = []
    
    sample_rate = mimi.sample_rate
    
    # Encode and process user audio
    step_count = 0
    token_count = 0
    
    for user_encoded in lm_encode_from_sphn(
        mimi,
        lm_iterate_audio(user_audio, sample_interval_size=frame_size, pad=True),
        max_batch=1,
    ):
        steps = user_encoded.shape[-1]
        for c in range(steps):
            step_count += 1
            try:
                step_in = user_encoded[:, :, c : c + 1]
                tokens = lm_gen.step(step_in)
                
                if tokens is None:
                    continue
                
                token_count += 1
                
                # Decode audio
                pcm = mimi.decode(tokens[:, 1:9])
                _ = other_mimi.decode(tokens[:, 1:9])
                pcm_np = pcm.detach().cpu().numpy()[0, 0]
                generated_frames.append(pcm_np)
                
                # Decode text token
                text_token = tokens[0, 0, 0].item()
                if text_token not in (0, 3):  # Skip PAD tokens
                    text = text_tokenizer.id_to_piece(text_token)
                    text = text.replace("▁", " ")
                    generated_text.append(text)
            except IndexError as e:
                logger.error(f"Index error at step {c}/{steps}: {e}")
                # Break on index error to return what we have so far
                break
            except Exception as e:
                logger.error(f"Error processing step {c}: {e}")
                continue
    
    logger.info(f"Processed {step_count} steps, generated {token_count} tokens, {len(generated_frames)} audio frames")
    
    if len(generated_frames) == 0:
        logger.warning(f"No audio frames generated for session {session_id}")
        return {"audio": None, "transcript": {"user": "", "assistant": ""}}
    
    # Concatenate frames
    output_pcm = np.concatenate(generated_frames, axis=-1)
    
    # Convert to int16 PCM
    output_bytes = (output_pcm * 32768).astype(np.int16).tobytes()
    output_b64 = base64.b64encode(output_bytes).decode("utf-8")
    
    # Update session transcript
    assistant_text = "".join(generated_text)
    sessions[session_id]["transcript_assistant"].append(assistant_text)
    
    logger.info(f"Generated {len(output_bytes)} bytes audio, transcript: '{assistant_text[:100]}'")
    
    return {
        "audio": output_b64,
        "transcript": {
            "user": "",  # We don't have ASR here
            "assistant": assistant_text
        },
        "session_id": session_id
    }


def end_session(session_id: str) -> dict:
    """End a conversation session and return transcript."""
    if session_id not in sessions:
        return {"error": f"Session {session_id} not found"}
    
    session = sessions[session_id]
    transcript = {
        "user": " ".join(session["transcript_user"]),
        "assistant": " ".join(session["transcript_assistant"])
    }
    
    del sessions[session_id]
    
    return {
        "status": "ended",
        "session_id": session_id,
        "transcript": transcript
    }


def handler(job):
    """
    RunPod Serverless handler function.
    
    Actions:
    - init: Initialize a new session with persona prompt
    - process: Process audio and get response
    - end: End session and get transcript
    
    NOTE: Moshi is stateful - each worker maintains its own session state.
    RunPod may route requests to different workers, so we auto-init on each worker.
    """
    job_input = job.get("input", {})
    action = job_input.get("action", "process")
    session_id = job_input.get("session_id", "default")
    
    logger.info(f"Received job: action={action}, session={session_id}, existing_sessions={list(sessions.keys())}")
    
    try:
        # Load models if not already loaded
        load_models()
        
        if action == "init":
            text_prompt = job_input.get("persona_prompt", "You are a wise and friendly teacher.")
            voice_prompt = job_input.get("voice_prompt", "NATF2.pt")
            logger.info(f"Init session {session_id} with prompt length {len(text_prompt)}")
            return init_session(session_id, text_prompt, voice_prompt)
        
        elif action == "process":
            audio_b64 = job_input.get("audio")
            if not audio_b64:
                return {"error": "No audio provided"}
            
            # Auto-init session if needed (handles stateless serverless routing)
            if session_id not in sessions:
                text_prompt = job_input.get("persona_prompt")
                if not text_prompt:
                    logger.error(f"Session {session_id} not found on this worker and no persona_prompt provided!")
                    return {"error": f"Session {session_id} not found on this worker. Provide persona_prompt for auto-init."}
                
                logger.info(f"Auto-initializing session {session_id} on this worker (routed from different worker)")
                init_session(session_id, text_prompt)
            
            audio_bytes = base64.b64decode(audio_b64)
            logger.info(f"Processing {len(audio_bytes)} bytes audio for session {session_id}")
            
            result = process_audio(session_id, audio_b64)
            
            # Log result details
            has_audio = bool(result.get("audio"))
            logger.info(f"Process result: has_audio={has_audio}, transcript={result.get('transcript', {}).get('assistant', '')[:50]}")
            
            return result
        
        elif action == "end":
            return end_session(session_id)
        
        else:
            return {"error": f"Unknown action: {action}"}
    
    except Exception as e:
        logger.error(f"Error in handler: {e}", exc_info=True)
        return {"error": str(e)}


if __name__ == "__main__":
    # Start the serverless worker
    runpod.serverless.start({"handler": handler})
