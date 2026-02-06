"""
Diagnostic script to identify Moshi configuration issues
Run this on your RunPod GPU to diagnose the index overflow issue
"""
import torch
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def diagnose_moshi():
    """Diagnose Moshi configuration and identify potential issues."""
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")
    
    try:
        from moshi.models import loaders, LMGen
        import sentencepiece
        from huggingface_hub import hf_hub_download
        
        hf_repo = "nvidia/personaplex-7b-v1"
        
        # Load Mimi
        logger.info("Loading Mimi...")
        mimi_weight = hf_hub_download(hf_repo, loaders.MIMI_NAME)
        mimi = loaders.get_mimi(mimi_weight, device)
        logger.info(f"Mimi loaded - sample_rate: {mimi.sample_rate}, frame_rate: {mimi.frame_rate}")
        
        # Load tokenizer
        logger.info("Loading tokenizer...")
        tokenizer_path = hf_hub_download(hf_repo, loaders.TEXT_TOKENIZER_NAME)
        text_tokenizer = sentencepiece.SentencePieceProcessor(tokenizer_path)
        logger.info(f"Tokenizer loaded - vocab size: {text_tokenizer.vocab_size()}")
        
        # Load Moshi LM
        logger.info("Loading Moshi LM...")
        moshi_weight = hf_hub_download(hf_repo, loaders.MOSHI_NAME)
        lm = loaders.get_moshi_lm(moshi_weight, device=device)
        
        # Inspect model architecture
        logger.info("Model architecture info:")
        logger.info(f"  Model type: {type(lm)}")
        
        # Check attention layers
        if hasattr(lm, 'transformer'):
            logger.info(f"  Transformer layers: {len(lm.transformer.layers) if hasattr(lm.transformer, 'layers') else 'N/A'}")
        
        # Check for streaming config
        if hasattr(lm, 'streaming'):
            logger.info(f"  Streaming config: {lm.streaming}")
        
        # Create LMGen
        frame_size = int(mimi.sample_rate / mimi.frame_rate)
        logger.info(f"Frame size: {frame_size}")
        
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
        
        logger.info("LMGen created successfully")
        
        # Set streaming mode
        mimi.streaming_forever(1)
        lm_gen.streaming_forever(1)
        
        # Test encoding
        logger.info("Testing audio encoding...")
        test_chunk = torch.zeros(1, 1, frame_size, dtype=torch.float32, device=device)
        codes = mimi.encode(test_chunk)
        logger.info(f"Encoded shape: {codes.shape}")
        logger.info(f"  Batch: {codes.shape[0]}, Codebooks: {codes.shape[1]}, Steps: {codes.shape[2]}")
        
        # Test generation
        logger.info("Testing generation step by step...")
        for c in range(codes.shape[-1]):
            logger.info(f"  Processing step {c}/{codes.shape[-1] - 1}")
            try:
                step_in = codes[:, :, c : c + 1]
                logger.info(f"    Step input shape: {step_in.shape}")
                tokens = lm_gen.step(step_in)
                if tokens is None:
                    logger.info(f"    Step {c} returned None")
                    continue
                logger.info(f"    Step {c} generated tokens shape: {tokens.shape}")
                
                # Try decoding
                decoded = mimi.decode(tokens[:, 1:9])
                logger.info(f"    Decoded audio shape: {decoded.shape}")
            except IndexError as e:
                logger.error(f"    IndexError at step {c}: {e}")
                logger.error(f"    This is where the bug occurs!")
                break
            except Exception as e:
                logger.error(f"    Error at step {c}: {e}")
                break
        
        logger.info("Diagnosis complete!")
        
    except Exception as e:
        logger.error(f"Diagnosis failed: {e}", exc_info=True)

if __name__ == "__main__":
    diagnose_moshi()
