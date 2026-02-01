"""
klantenservice.ai - RunPod Serverless Worker for PersonaPlex-7B
Real-time speech-to-speech conversational AI

This worker runs on RunPod Serverless with GPU and handles:
- Loading PersonaPlex-7B model
- Processing audio input
- Generating audio responses
- Streaming results back to the client
"""
import os
import base64
import logging
import runpod
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global model instance (loaded once, reused across requests)
model = None
processor = None


def load_model():
    """Load PersonaPlex-7B model from Hugging Face."""
    global model, processor
    
    if model is not None:
        logger.info("Model already loaded")
        return
    
    logger.info("Loading PersonaPlex-7B model...")
    
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
    
    model_id = "nvidia/personaplex-7b-v1"
    hf_token = os.environ.get("HUGGINGFACE_TOKEN")
    
    # Load processor
    processor = AutoProcessor.from_pretrained(
        model_id,
        token=hf_token,
        trust_remote_code=True,
    )
    
    # Load model with optimizations
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
        token=hf_token,
    )
    
    logger.info("PersonaPlex-7B loaded successfully")


def process_audio(job_input: dict) -> dict:
    """
    Process audio input and generate response.
    
    Input format:
    {
        "audio": "<base64 encoded PCM audio at 24kHz>",
        "persona_prompt": "Je bent Lisa, een receptionist bij...",
        "session_id": "unique-session-id",
        "action": "process" | "init" | "end"
    }
    
    Output format:
    {
        "audio": "<base64 encoded PCM response audio>",
        "transcript": {"user": "...", "assistant": "..."}
    }
    """
    import torch
    import numpy as np
    
    action = job_input.get("action", "process")
    session_id = job_input.get("session_id", "default")
    
    if action == "init":
        # Initialize session (model warm-up)
        load_model()
        return {
            "status": "initialized",
            "session_id": session_id
        }
    
    if action == "end":
        # End session (cleanup if needed)
        return {
            "status": "ended",
            "session_id": session_id
        }
    
    # Process audio
    load_model()
    
    # Decode input audio
    audio_b64 = job_input.get("audio")
    if not audio_b64:
        return {"error": "No audio provided"}
    
    audio_bytes = base64.b64decode(audio_b64)
    
    # Convert bytes to numpy array (assuming 16-bit PCM at 24kHz)
    audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    
    # Get persona prompt
    persona_prompt = job_input.get("persona_prompt", "")
    
    try:
        # Process through model
        inputs = processor(
            audio=audio_array,
            sampling_rate=24000,
            return_tensors="pt",
            padding=True
        ).to(model.device)
        
        # Add persona context if provided
        if persona_prompt:
            inputs["text_prompt"] = persona_prompt
        
        # Generate response
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=1024,
                do_sample=True,
                temperature=0.7,
            )
        
        # Extract audio from outputs
        response_audio = None
        transcript = {"user": "", "assistant": ""}
        
        if hasattr(outputs, "audio"):
            response_audio_np = outputs.audio.cpu().numpy()
            # Convert back to int16 PCM
            response_bytes = (response_audio_np * 32768).astype(np.int16).tobytes()
            response_audio = base64.b64encode(response_bytes).decode("utf-8")
        
        if hasattr(outputs, "text"):
            transcript["assistant"] = outputs.text
        
        return {
            "audio": response_audio,
            "transcript": transcript,
            "session_id": session_id
        }
        
    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        return {
            "error": str(e),
            "session_id": session_id
        }


def handler(job):
    """
    RunPod Serverless handler function.
    
    This is the entry point for all requests to the serverless endpoint.
    """
    job_input = job.get("input", {})
    
    logger.info(f"Received job: action={job_input.get('action', 'process')}, session={job_input.get('session_id', 'unknown')}")
    
    result = process_audio(job_input)
    
    return result


# Generator handler for streaming responses
def generator_handler(job):
    """
    Streaming handler for real-time audio responses.
    
    Yields audio chunks as they're generated for lower latency.
    """
    import torch
    import numpy as np
    
    job_input = job.get("input", {})
    
    load_model()
    
    audio_b64 = job_input.get("audio")
    if not audio_b64:
        yield {"error": "No audio provided"}
        return
    
    audio_bytes = base64.b64decode(audio_b64)
    audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    
    persona_prompt = job_input.get("persona_prompt", "")
    
    try:
        inputs = processor(
            audio=audio_array,
            sampling_rate=24000,
            return_tensors="pt",
            padding=True
        ).to(model.device)
        
        if persona_prompt:
            inputs["text_prompt"] = persona_prompt
        
        # Stream generation
        with torch.no_grad():
            for output_chunk in model.generate(
                **inputs,
                max_new_tokens=1024,
                do_sample=True,
                temperature=0.7,
                streamer=True,  # Enable streaming if supported
            ):
                if hasattr(output_chunk, "audio"):
                    audio_np = output_chunk.audio.cpu().numpy()
                    chunk_bytes = (audio_np * 32768).astype(np.int16).tobytes()
                    yield {
                        "audio_chunk": base64.b64encode(chunk_bytes).decode("utf-8")
                    }
        
        yield {"status": "complete"}
        
    except Exception as e:
        logger.error(f"Error in streaming: {e}")
        yield {"error": str(e)}


if __name__ == "__main__":
    # Start the serverless worker
    runpod.serverless.start({
        "handler": handler,
        # Uncomment for streaming support:
        # "handler": generator_handler,
    })
