"""
klantenservice.ai - Audio Utilities
Conversion between Twilio mulaw and PersonaPlex PCM formats
"""
import audioop
import struct


class AudioConverter:
    """
    Handles audio format conversion between Twilio and PersonaPlex.
    
    Twilio Media Streams use:
    - mulaw encoding
    - 8kHz sample rate
    - 8-bit depth
    
    PersonaPlex expects:
    - PCM encoding
    - 24kHz sample rate
    - 16-bit depth
    """
    
    TWILIO_SAMPLE_RATE = 8000
    PERSONAPLEX_SAMPLE_RATE = 24000
    
    @staticmethod
    def mulaw_to_pcm(mulaw_data: bytes) -> bytes:
        """
        Convert Twilio mulaw audio to PCM for PersonaPlex.
        
        Args:
            mulaw_data: mulaw encoded audio bytes from Twilio
            
        Returns:
            PCM encoded audio bytes at 24kHz
        """
        # Decode mulaw to linear PCM (16-bit)
        pcm_8khz = audioop.ulaw2lin(mulaw_data, 2)
        
        # Resample from 8kHz to 24kHz
        pcm_24khz, _ = audioop.ratecv(
            pcm_8khz, 
            2,  # sample width (bytes)
            1,  # channels
            AudioConverter.TWILIO_SAMPLE_RATE,
            AudioConverter.PERSONAPLEX_SAMPLE_RATE,
            None  # state
        )
        
        return pcm_24khz
    
    @staticmethod
    def pcm_to_mulaw(pcm_data: bytes) -> bytes:
        """
        Convert PersonaPlex PCM audio to mulaw for Twilio.
        
        Args:
            pcm_data: PCM encoded audio bytes at 24kHz
            
        Returns:
            mulaw encoded audio bytes at 8kHz
        """
        # Resample from 24kHz to 8kHz
        pcm_8khz, _ = audioop.ratecv(
            pcm_data,
            2,  # sample width (bytes)
            1,  # channels
            AudioConverter.PERSONAPLEX_SAMPLE_RATE,
            AudioConverter.TWILIO_SAMPLE_RATE,
            None  # state
        )
        
        # Encode to mulaw
        mulaw_data = audioop.lin2ulaw(pcm_8khz, 2)
        
        return mulaw_data
    
    @staticmethod
    def normalize_audio(pcm_data: bytes, target_db: float = -3.0) -> bytes:
        """
        Normalize audio volume to target dB level.
        
        Args:
            pcm_data: PCM encoded audio bytes
            target_db: Target volume in dB (default -3.0)
            
        Returns:
            Normalized PCM audio bytes
        """
        # Calculate current RMS
        rms = audioop.rms(pcm_data, 2)
        
        if rms == 0:
            return pcm_data
        
        # Calculate target RMS from dB
        target_rms = int(32768 * (10 ** (target_db / 20)))
        
        # Calculate multiplier
        multiplier = target_rms / rms
        
        # Apply gain (clamped to avoid clipping)
        multiplier = min(multiplier, 4.0)  # Max 12dB boost
        
        return audioop.mul(pcm_data, 2, multiplier)
