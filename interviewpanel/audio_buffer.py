"""
Audio buffering service to batch audio chunks before processing.
Prevents Celery task spam for high-frequency audio streaming.
"""
import time
import logging
from typing import List, Optional
from collections import deque
from threading import Lock

logger = logging.getLogger(__name__)


class AudioBuffer:    
    def __init__(self, buffer_duration_seconds: float = 3.0, max_chunks: int = 3):
        self.buffer_duration = buffer_duration_seconds
        self.max_chunks = max_chunks
        self.buffers = {}  
        self.skip_counts = {}  
        self.locks = {}  
        self._lock = Lock()  
        
    def _get_lock(self, session_uuid: str) -> Lock:
        with self._lock:
            if session_uuid not in self.locks:
                self.locks[session_uuid] = Lock()
            return self.locks[session_uuid]
    
    def add_chunk(
        self,
        session_uuid: str,
        answer_uuid: str,
        audio_base64: str,
        chunk_timestamp: float
    ) -> Optional[dict]:
        lock = self._get_lock(session_uuid)
        
        with lock:
            if session_uuid not in self.buffers:
                self.buffers[session_uuid] = {
                    'answer_uuid': answer_uuid,
                    'chunks': [],
                    'first_chunk_time': chunk_timestamp,
                    'last_chunk_time': chunk_timestamp
                }
                self.skip_counts[answer_uuid] = 0
            
            buffer = self.buffers[session_uuid]
            buffer['chunks'].append(audio_base64)
            buffer['last_chunk_time'] = chunk_timestamp
            
            time_elapsed = chunk_timestamp - buffer['first_chunk_time']
            chunk_count = len(buffer['chunks'])
            
            should_flush = (
                time_elapsed >= self.buffer_duration or
                chunk_count >= self.max_chunks
            )
            
            if should_flush:
                return self._flush(session_uuid)
            
            return None
    
    def _flush(self, session_uuid: str) -> Optional[dict]:
        if session_uuid not in self.buffers:
            return None
        buffer = self.buffers[session_uuid]
        if not buffer['chunks']:
            del self.buffers[session_uuid]
            return None
        combined_audio = buffer['chunks']
        result = {
            'answer_uuid': buffer['answer_uuid'],
            'audio_chunks': combined_audio,
            'chunk_count': len(combined_audio),
            'duration': buffer['last_chunk_time'] - buffer['first_chunk_time']
        }
        
        del self.buffers[session_uuid]
        
        logger.debug(f"Flushed audio buffer for {session_uuid}: {len(combined_audio)} chunks")
        return result
    
    def flush_session(self, session_uuid: str) -> Optional[dict]:
        lock = self._get_lock(session_uuid)
        with lock:
            return self._flush(session_uuid)
    
    def cleanup_session(self, session_uuid: str):
        lock = self._get_lock(session_uuid)
        with lock:
            if session_uuid in self.buffers:
                answer_uuid = self.buffers[session_uuid].get('answer_uuid')
                if answer_uuid and answer_uuid in self.skip_counts:
                    del self.skip_counts[answer_uuid]
                del self.buffers[session_uuid]
            if session_uuid in self.locks:
                del self.locks[session_uuid]
    
    def reset_skip_count(self, answer_uuid: str):
        if answer_uuid in self.skip_counts:
            self.skip_counts[answer_uuid] = 0
            logger.debug(f"Reset skip count for answer {answer_uuid}")
    
    def get_skip_count(self, answer_uuid: str) -> int:
        return self.skip_counts.get(answer_uuid, 0)


audio_buffer = AudioBuffer(buffer_duration_seconds=3.0, max_chunks=3)

