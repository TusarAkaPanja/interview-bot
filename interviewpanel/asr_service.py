import base64
import io
import wave
import logging
import requests
import json
from typing import Optional
from django.conf import settings
import os

logger = logging.getLogger(__name__)


class ASRService:    
    def __init__(self):
        self.ollama_base_url = getattr(settings, 'OLLAMA_BASE_URL', os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434'))
        self.whisper_model = os.getenv('WHISPER_MODEL', 'whisper') 
        self.timeout = int(getattr(settings, 'OLLAMA_TIMEOUT', os.getenv('OLLAMA_TIMEOUT', '300')))
    
    def transcribe_audio(self, audio_data: bytes, sample_rate: int = 16000) -> Optional[str]:
        try:
            wav_data = self._pcm_to_wav(audio_data, sample_rate)
            audio_base64 = base64.b64encode(wav_data).decode('utf-8')
            url = f"{self.ollama_base_url.rstrip('/')}/api/generate"
            
            prompt = f"""Transcribe the following audio. Return only the transcribed text, nothing else.
            Audio data (base64 WAV): {audio_base64[:100]}...
            """
            
            data = {
                "model": self.whisper_model,
                "prompt": prompt,
                "stream": False
            }
            response = self._call_whisper_api(audio_base64)
            
            if response:
                return response.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            return None
    
    def _call_whisper_api(self, audio_base64: str) -> Optional[str]:
        """Call Whisper API via Ollama"""
        try:
            url = f"{self.ollama_base_url.rstrip('/')}/api/audio/transcriptions"
            
            audio_bytes = base64.b64decode(audio_base64)
            
            files = {
                'file': ('audio.wav', io.BytesIO(audio_bytes), 'audio/wav')
            }
            
            data = {
                'model': self.whisper_model
            }
            
            response = requests.post(
                url,
                files=files,
                data=data,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('text', '')
            
            logger.warning("Ollama Whisper API endpoint not available, using fallback")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Whisper API call failed: {str(e)}")
            return None
    
    def _fallback_transcription(self, audio_base64: str) -> Optional[str]:
        """Fallback transcription method"""
        return None
    
    def _pcm_to_wav(self, pcm_data: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
        wav_buffer = io.BytesIO()
        
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2) 
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
        
        wav_buffer.seek(0)
        return wav_buffer.read()


class WhisperASRService:
    
    def __init__(self, model_size: str = "small"):
        self.model_size = model_size
        self.model = None
        self.whisper_available = False
        
        try:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(
                model_size,
                device="cpu",
                compute_type="int8" 
            )
            self.whisper_available = True
            logger.info(f"Loaded faster-whisper model: {model_size} (CPU, int8)")
        except ImportError as e:
            logger.warning(f"faster-whisper not installed: {str(e)}. Install with: pip install faster-whisper")
            self.whisper_available = False
        except Exception as e:
            logger.error(f"Failed to load faster-whisper model: {str(e)}")
            self.whisper_available = False
            self.model = None
    
    def transcribe_audio(self, audio_data: bytes, sample_rate: int = 16000) -> Optional[str]:
        if not self.whisper_available:
            return None
        try:
            import numpy as np
            import io
            import wave
            
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            audio_max = np.abs(audio_array).max()
            original_duration = len(audio_array) / sample_rate
            
            if audio_max > 0:
                audio_array = audio_array / audio_max
                logger.debug(f"Audio normalized: max amplitude was {audio_max:.4f}")
            else:
                logger.warning("Audio array has zero amplitude - likely silence")
            
            segments, info = self.model.transcribe(
                audio_array,
                language="en",
                task="transcribe",
                beam_size=5,
                vad_filter=True,  
                vad_parameters=dict(
                    threshold=0.3,  
                    min_silence_duration_ms=500,  
                    min_speech_duration_ms=250  
                )
            )
            
            total_segment_duration = 0.0
            transcript_parts = []
            segment_count = 0
            
            for segment in segments:
                segment_duration = segment.end - segment.start
                total_segment_duration += segment_duration
                transcript_parts.append(segment.text.strip())
                segment_count += 1
                logger.debug(f"VAD segment: {segment.start:.2f}s - {segment.end:.2f}s ({segment_duration:.2f}s): {segment.text[:50]}")
            
            if original_duration > 0:
                vad_ratio = total_segment_duration / original_duration
                logger.info(f"VAD kept {total_segment_duration:.3f}s of {original_duration:.3f}s audio "
                          f"(ratio: {vad_ratio:.2%}), {segment_count} segments")
                
                if vad_ratio < 0.1:  
                    logger.warning(f"VAD removed {100-vad_ratio*100:.1f}% of audio - may be too aggressive!")
            
            transcription = " ".join(transcript_parts).strip()
            
            if not transcription:
                logger.warning(f"No transcription produced from {segment_count} VAD segments")
            
            return transcription if transcription else None
            
        except Exception as e:
            logger.error(f"faster-whisper transcription error: {str(e)}")
            return None

