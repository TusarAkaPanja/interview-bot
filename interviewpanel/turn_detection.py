"""
End-of-turn detection for automatic round finalization.
Detects silence, speech endpoints, and enforces time budgets.
"""
import time
import logging
from typing import Optional
from collections import deque

logger = logging.getLogger(__name__)


class TurnDetector:
    """
    Detects end of turn based on:
    - Silence duration
    - Speech endpoint detection
    - Time budget enforcement
    Supports different timeout for questions (2min)
    """
    
    def __init__(
        self,
        silence_threshold_seconds: float = 2.0,
        max_turn_duration_seconds: float = 300.0,  
        min_turn_duration_seconds: float = 3.0, 
        question_timeout_seconds: float = 120.0 
    ):
        self.silence_threshold = silence_threshold_seconds
        self.max_turn_duration = max_turn_duration_seconds
        self.min_turn_duration = min_turn_duration_seconds
        self.question_timeout = question_timeout_seconds
        self.sessions = {}
    
    def start_turn(self, session_uuid: str, answer_uuid: str, is_greeting: bool = False):
        timeout = self.question_timeout
        
        self.sessions[session_uuid] = {
            'answer_uuid': answer_uuid,
            'start_time': time.time(),
            'last_audio_time': time.time(),
            'silence_start': None,
            'has_speech': False,
            'timeout': timeout,
            'transcriptions': [],
            'chunk_count': 0,
            'last_chunk_time': time.time()
        }
        logger.info(f"Started turn for {session_uuid}, timeout={timeout}s")
    
    def update_audio(self, session_uuid: str, has_speech: bool = True, chunk_received: bool = False):
        if session_uuid not in self.sessions:
            return None
        
        state = self.sessions[session_uuid]
        current_time = time.time()
        if has_speech:
            state['has_speech'] = True
            state['last_audio_time'] = current_time
            state['silence_start'] = None
        else:
            if state['silence_start'] is None and state['has_speech']:
                state['silence_start'] = current_time
                logger.debug(f"Silence started for {session_uuid} at {current_time}")
        
        # Track chunk count 
        if chunk_received:
            state['chunk_count'] += 1
            state['last_chunk_time'] = current_time
            logger.debug(f"Chunk {state['chunk_count']} received for {session_uuid}")
        
        return self._check_end_of_turn(session_uuid, current_time)
    
    def _check_end_of_turn(self, session_uuid: str, current_time: float) -> Optional[dict]:
        if session_uuid not in self.sessions:
            return None
        
        state = self.sessions[session_uuid]
        elapsed = current_time - state['start_time']
        time_since_last_audio = current_time - state['last_audio_time']
        time_since_last_chunk = current_time - state.get('last_chunk_time', state['start_time'])
        timeout = state.get('timeout', self.question_timeout)
        chunk_count = state.get('chunk_count', 0)
        
        # Regular question handling 
        # Condition 1: Timeout reached
        # For questions: 2 minutes of no speech from start
        if not state['has_speech']:
            if elapsed >= timeout:
                logger.info(f"Turn ended for {session_uuid}: timeout reached ({timeout}s) with no speech")
                return {
                    'reason': 'timeout_no_speech',
                    'answer_uuid': state['answer_uuid'],
                    'duration': elapsed,
                }
        else:
            # Had speech, check two conditions:
            # 1. Silence threshold (short silence after speech)
            if state['silence_start']:
                silence_duration = current_time - state['silence_start']
                # If silence exceeds threshold and minimum turn duration met, end turn
                # Also ensure at least 10 seconds have passed since turn started (give user time to start speaking)
                min_elapsed_time = max(self.min_turn_duration, 10.0)
                if silence_duration >= self.silence_threshold and elapsed >= min_elapsed_time:
                    logger.info(f"Turn ended for {session_uuid}: silence threshold exceeded ({silence_duration:.2f}s >= {self.silence_threshold}s) after {elapsed:.2f}s elapsed")
                    return {
                        'reason': 'silence',
                        'answer_uuid': state['answer_uuid'],
                        'duration': elapsed,
                        'silence_duration': silence_duration
                    }
            
            # 2. Timeout after speech (long silence after speech)
            # For questions: 2 minutes since last audio
            if time_since_last_audio >= timeout:
                logger.info(f"Turn ended for {session_uuid}: timeout after speech ({timeout}s since last audio)")
                return {
                    'reason': 'timeout_after_speech',
                    'answer_uuid': state['answer_uuid'],
                    'duration': elapsed,
                    'time_since_last_audio': time_since_last_audio,
                }
        
        # Condition 2: Max duration reached (absolute maximum, regardless of type)
        if elapsed >= self.max_turn_duration:
            logger.info(f"Turn ended for {session_uuid}: max duration reached")
            return {
                'reason': 'max_duration',
                'answer_uuid': state['answer_uuid'],
                'duration': elapsed
            }
        
        return None
    
    def end_turn(self, session_uuid: str):
        """Manually end turn"""
        if session_uuid in self.sessions:
            del self.sessions[session_uuid]
    
    def add_transcription(self, session_uuid: str, transcription: str):
        """Add transcription to the current turn (saved until turn out)"""
        if session_uuid not in self.sessions:
            return
        
        if 'transcriptions' not in self.sessions[session_uuid]:
            self.sessions[session_uuid]['transcriptions'] = []
        
        self.sessions[session_uuid]['transcriptions'].append({
            'text': transcription,
            'timestamp': time.time()
        })
        logger.debug(f"Added transcription to turn for {session_uuid}: {transcription[:50]}...")
    
    def get_transcriptions(self, session_uuid: str) -> list:
        """Get all transcriptions for the current turn"""
        if session_uuid not in self.sessions:
            return []
        
        return self.sessions[session_uuid].get('transcriptions', [])
    
    def get_turn_state(self, session_uuid: str) -> Optional[dict]:
        """Get current turn state"""
        if session_uuid not in self.sessions:
            return None
        
        state = self.sessions[session_uuid]
        current_time = time.time()
        silence_duration = 0
        if state['silence_start']:
            silence_duration = current_time - state['silence_start']
        
        return {
            'elapsed': current_time - state['start_time'],
            'time_since_last_audio': current_time - state['last_audio_time'],
            'has_speech': state['has_speech'],
            'silence_duration': silence_duration,
            'silence_start': state['silence_start'],
            'chunk_count': state.get('chunk_count', 0),
            'transcription_count': len(state.get('transcriptions', []))
        }


# Global turn detector
turn_detector = TurnDetector(
    silence_threshold_seconds=10.0,
    max_turn_duration_seconds=300.0,
    question_timeout_seconds=120.0
)

