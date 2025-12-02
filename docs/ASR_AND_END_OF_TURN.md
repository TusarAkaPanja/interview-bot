# ASR Transcription and End of Turn Detection

## Current Implementation

### 1. Transcription (ASR)

The system currently has **two ASR service options**:

#### Option A: Faster-Whisper (Recommended for CPU/M4 Mac)
- Uses `faster-whisper` library (CTranslate2 backend)
- Optimized for CPU, works great on MacBook M4
- Fast inference with "small" model
- No GPU required
- **Installation**: `pip install faster-whisper`
- **Model**: Uses "small" model by default (good balance of speed/accuracy)

#### Option B: Ollama Whisper
- Uses Whisper model via Ollama
- Requires Ollama running with Whisper model
- **Setup**: `ollama pull whisper`

### Current Flow

1. **Frontend** sends 5-second audio chunks (PCM S16LE, 16 kHz)
2. **WebSocket** receives binary audio data
3. **Celery Task** (`process_audio_chunk`) processes each chunk:
   - Decodes base64 audio
   - Calls ASR service to transcribe
   - Appends transcription to `full_transcription` field
   - Updates `transcription` field for real-time display
   - Broadcasts transcription via WebSocket

### Transcription Storage

- **`transcription`**: Real-time transcription for display (gets updated with each chunk)
- **`full_transcription`**: Complete transcription for the entire round (used for analysis)

## End of Turn Detection

### Current Mechanism: **Manual**

The end of turn is currently **manually triggered** by the frontend:

```javascript
// Frontend sends this message when user finishes answering
ws.send(JSON.stringify({ type: 'end_round' }));
```

### Flow:

1. User speaks and audio chunks are sent continuously
2. Each chunk is transcribed and displayed in real-time
3. When user finishes speaking, frontend sends `end_round` message
4. Backend receives `end_round` and:
   - Finalizes current answer
   - Triggers `finalize_answer` task
   - Which calls `analyze_and_score_answer`
   - Analysis determines next action (drill_up, drill_down, etc.)
   - Next question is selected and sent

### Code Location

**Consumer** (`consumers.py`):
```python
async def handle_end_round(self):
    """Handle end of round - finalize current answer"""
    current_answer = await self.get_current_answer()
    if current_answer:
        finalize_answer.delay(str(current_answer.uuid), str(self.interview_session.uuid))
```

## Automatic End of Turn Detection (Optional)

You can add automatic detection based on **silence detection**. Here's how:

### Implementation Option 1: Frontend Silence Detection

Add silence detection in the Next.js component:

```typescript
// Detect silence (no audio for 2 seconds)
let silenceStartTime = null;
const SILENCE_THRESHOLD_MS = 2000; // 2 seconds of silence

// In audio processing
if (audioLevel < SILENCE_THRESHOLD) {
  if (!silenceStartTime) {
    silenceStartTime = Date.now();
  } else if (Date.now() - silenceStartTime > SILENCE_THRESHOLD_MS) {
    // Send end_round after 2 seconds of silence
    ws.send(JSON.stringify({ type: 'end_round' }));
    silenceStartTime = null;
  }
} else {
  silenceStartTime = null; // Reset on audio detected
}
```

### Implementation Option 2: Backend Silence Detection

Add silence detection in the audio processing task:

```python
def detect_silence(audio_data: bytes, threshold: float = 0.01) -> bool:
    """Detect if audio chunk is silent"""
    import numpy as np
    audio_array = np.frombuffer(audio_data, dtype=np.int16)
    audio_float = audio_array.astype(np.float32) / 32768.0
    rms = np.sqrt(np.mean(audio_float**2))
    return rms < threshold

@shared_task
def process_audio_chunk(answer_uuid, audio_base64, session_uuid):
    audio_data = base64.b64decode(audio_base64)
    
    # Check for silence
    if detect_silence(audio_data):
        # Track consecutive silent chunks
        # After N silent chunks, auto-end round
        pass
```

## Recommended Approach

**Hybrid Approach** (Best UX):

1. **Frontend**: Detect silence and show "Ending answer..." indicator
2. **Frontend**: Auto-send `end_round` after 2-3 seconds of silence
3. **Backend**: Also track silence as fallback
4. **User**: Can manually click "End Answer" button anytime

## Setup Instructions

### For Faster-Whisper (Recommended):

1. Install:
   ```bash
   pip install faster-whisper numpy
   ```

2. The service will automatically use faster-whisper if available
   - First run will download the "small" model (~500MB)
   - Subsequent runs use cached model
   - Works on CPU, optimized for M4 Mac

3. Model sizes available:
   - `tiny`: Fastest, least accurate (~75MB)
   - `base`: Fast, good accuracy (~150MB)
   - `small`: **Default** - Good balance (~500MB)
   - `medium`: Slower, better accuracy (~1.5GB)
   - `large-v2`/`large-v3`: Best accuracy, slowest (~3GB)

### For Ollama Whisper:

1. Install Ollama: https://ollama.ai
2. Pull Whisper model:
   ```bash
   ollama pull whisper
   ```
3. Set environment variable:
   ```env
   WHISPER_MODEL=whisper
   ```

### Alternative ASR Services

You can also integrate:
- **Google Speech-to-Text**: High accuracy, paid
- **Azure Speech Services**: Good accuracy, paid
- **AssemblyAI**: Good for real-time, paid
- **Deepgram**: Fast, paid

To use these, modify `asr_service.py` to add new service classes.

## Testing Transcription

1. Start the server and Celery worker
2. Connect via WebSocket
3. Start recording
4. Speak into microphone
5. Check Celery logs for transcription output
6. Check WebSocket messages for `transcription_update` events

## Troubleshooting

### No Transcription Appearing

1. Check if ASR service is initialized:
   - Look for errors in Celery logs
   - Verify Whisper model is loaded or Ollama is running

2. Check audio format:
   - Ensure audio is PCM S16LE, 16 kHz
   - Verify audio chunks contain actual audio data

3. Check ASR service:
   - Test ASR service directly
   - Verify model is working

### End of Turn Not Working

1. Verify frontend is sending `end_round` message
2. Check WebSocket connection is active
3. Verify `handle_end_round` is being called
4. Check Celery worker is processing `finalize_answer` task

