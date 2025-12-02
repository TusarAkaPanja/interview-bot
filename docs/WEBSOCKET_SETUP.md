# WebSocket Pipeline Setup Guide

## Binary Audio Handling Method

The WebSocket consumer handles binary audio data using the following method:

### Audio Format
- **Format**: PCM S16LE (Pulse Code Modulation, Signed 16-bit Little Endian)
- **Sample Rate**: 16 kHz (16,000 samples per second)
- **Chunk Size**: 5-second chunks (sent continuously from frontend)

### Binary Data Flow

1. **WebSocket Receive** (`consumers.py:65-87`)
   ```python
   async def receive(self, text_data=None, bytes_data=None):
       if bytes_data:
           # Binary audio chunk received
           await self.handle_audio_chunk(bytes_data)
   ```
   - The `bytes_data` parameter contains raw binary PCM audio data
   - No encoding/decoding needed at WebSocket level - raw bytes are passed directly

2. **Audio Processing** (`consumers.py:89-107`)
   ```python
   async def handle_audio_chunk(self, audio_data):
       # audio_data is raw bytes (PCM S16LE 16 kHz)
       audio_base64 = base64.b64encode(audio_data).decode('utf-8')
       # Dispatch to Celery task for processing
       process_audio_chunk.delay(...)
   ```
   - Raw binary data is base64-encoded only for transmission to Celery task queue
   - The actual audio processing (transcription) happens in the background task

3. **Task Processing** (`tasks.py:process_audio_chunk`)
   - Base64-decodes the audio back to binary
   - Processes with ASR service (to be implemented)
   - Sends transcription updates back via WebSocket

### Key Points
- **No heavy processing in WebSocket**: Audio chunks are immediately dispatched to Celery
- **Raw binary handling**: WebSocket receives raw PCM bytes, no intermediate encoding
- **Base64 encoding**: Only used for Celery task serialization (JSON-safe)
- **Streaming**: Continuous 5-second chunks create a real-time audio stream

## Starting the Server with Uvicorn

### Prerequisites
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Start Redis (required for Channels and Celery):
   ```bash
   redis-server
   ```

3. Run migrations:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

### Starting with Uvicorn

#### Option 1: Direct Command
```bash
uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --reload
```

#### Option 2: With Workers (Production)
```bash
uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers 4
```

#### Option 3: Development with Auto-reload
```bash
uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --reload --log-level debug
```

### Starting Celery Worker

In a separate terminal, start the Celery worker for background tasks:

```bash
celery -A config worker -l info
```

### Complete Startup Sequence

1. **Terminal 1 - Redis**:
   ```bash
   redis-server
   ```

2. **Terminal 2 - Django/Uvicorn**:
   ```bash
   uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --reload
   ```

3. **Terminal 3 - Celery Worker**:
   ```bash
   celery -A config worker -l info
   ```

### WebSocket Connection URL

Once the server is running, connect to WebSocket at:
```
ws://localhost:8000/ws/interview/<token>/
```

Where `<token>` is the token from `InterviewPanelCandidate.token` field.

### Testing WebSocket Connection

You can test the WebSocket connection using a tool like `websocat`:

```bash
# Install websocat (if needed)
# cargo install websocat

# Connect to WebSocket
websocat ws://localhost:8000/ws/interview/YOUR_TOKEN_HERE/
```

### Environment Variables

Make sure these are set in your `.env` file or environment:

```env
REDIS_HOST=localhost
REDIS_PORT=6379
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Notes

- **Uvicorn vs Daphne**: Uvicorn is recommended for Channels 4.0+ and provides better performance
- **WebSocket Support**: Uvicorn fully supports WebSocket connections via ASGI
- **Binary Data**: Uvicorn handles binary WebSocket frames natively
- **Production**: Use `--workers` flag for production deployments with multiple worker processes

