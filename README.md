# Core Services

Backend for the InterviewBot platform, powering authentication, question delivery, live scoring, and PDF reporting for AI-assisted technical interviews.

## Getting started

### Prerequisites
- macOS/Linux/Windows with Python **3.12+**
- PostgreSQL database
- Redis instance (used for Channels + Celery broker + result backend)
- Ollama or another embedding/LLM host for scoring (`OLLAMA_BASE_URL`)
- System libs for WeasyPrint (cairo, pango, gdk-pixbuf, libffi) if you plan to generate PDFs locally 

### Installation (You can use 'uv')
1. `git clone <repo>` and `cd core-services`
2. `python -m venv .venv` && `source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. Copy `.env.example`/create `.env` with the values described below
5. Run migrations: `python manage.py migrate`
6. `python manage.py create_roles` to populate roles

### Environment variables
```
SECRET_KEY=...
DEBUG=True
DB_NAME=interviewbot_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
REDIS_HOST=localhost
REDIS_PORT=6379
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```
You can add any other Django or third-party settings in `.env` because `config/settings.py` loads them via `python-dotenv`.

### Running services
- Start the Django ASGI server: `python manage.py runserver 0.0.0.0:8000`
- Start a Celery worker: `celery -A config worker --loglevel=info`
- Ensure Redis is running before starting Channels/Celery.
- Run uvicorn for websocket `uvicorn config.asgi:application --host 0.0.0.0 --port 4545`
- The WebSocket endpoint lives at `ws://<host>/ws/interview/<token>/`.

## Architecture & request flow

### Apps overview
- `authentication`: custom `User` model plus JWT tokens via Simple JWT.
- `organizations`: contains tenant/org metadata referenced in panels.
- `questionbank`: question catalog, topic/category/weightage helpers, and the Ollama-backed generator/analysis helpers.
- `interviewpanel`: orchestrates sessions, answers, live scoring, WebSocket consumers, Celery tasks, and report generation.
- `reports/`: stores generated PDFs (WeasyPrint).

### Interview flow
1. A candidate receives a `InterviewPanelCandidate` record/token (typically via the organizations panel).
2. The frontend connects to `InterviewConsumer` over Channels using that token. The consumer validates the token, loads the associated `InterviewSession`, and joins the `interview_<uuid>` group.
3. A greeting is generated (`generate_greeting`) and the first question is selected (`select_and_send_next_question`) in background Celery tasks.
4. Candidate audio chunks stream through the WebSocket and are buffered via `audio_buffer`.
5. Buffered chunks trigger `process_buffered_audio`, which transcribes audio (faster-whisper), updates the current `InterviewAnswer`, and broadcasts transcription updates.
6. The adaptive question selector (`select_and_send_next_question`) now honors the panel’s `InterviewPanelQuestionDistribution`, preferring unanswered questions that still satisfy the configured topic/subtopic difficulty quotas before falling back to other difficulty levels.
7. After the candidate finishes speaking, `finalize_answer` queues `analyze_and_score_answer`, which:
   - Calls `AnswerAnalysisService`/LLM services to score the answer.
   - Updates answer/session statistics and difficulty.
   - Broadcasts scoring updates via Channels.
   - Triggers `select_and_send_next_question` to continue or finish the interview.
8. When the interview completes or disconnects, `generate_interview_report` compiles scored answers and AI feedback (via `OllamaService`) into a PDF stored under `reports/`.

### End-of-turn flow
The system automatically detects when a candidate has finished speaking using `TurnDetector`:

- **Silence detection**: After speech is detected, if 10 seconds of silence pass (and minimum 10 seconds have elapsed since turn start), the turn ends automatically.
- **Timeout handling**: 
  - If no speech is detected within 2 minutes from turn start, the turn times out.
  - If speech was detected but 2 minutes pass since the last audio chunk, the turn times out.
- **Maximum duration**: Absolute maximum of 5 minutes per turn, regardless of speech activity.
- **Automatic finalization**: When end-of-turn is detected, `handle_end_round()` is triggered, which calls `finalize_answer()` to queue answer analysis and scoring.

The `_periodic_timeout_check()` coroutine in `InterviewConsumer` runs every second to monitor turn state and trigger finalization when conditions are met.

### Asynchronous & scoring helpers
- `SessionManager` guards concurrency with transactions when mutating session/answer state.
- `turn_detection` monitors speech activity to detect end-of-turn/timeouts server-side.
- `score_calculator` and `interview_services.AnswerAnalysisService` handle normalizing component scores and deriving the candidate's next action.
- Celery tasks (`tasks.py`) keep CPU/LLM-heavy work off the request thread while letting Channels handle realtime updates via `channel_layer.group_send`.

## Development tips
- Run tests with `python manage.py test interviewpanel`.
- Use `python manage.py shell` to inspect models (`InterviewPanelCandidate`, `InterviewAnswer`, `InterviewSession`).
- To regenerate WeasyPrint PDFs locally install `brew install cairo pango gdk-pixbuf libffi` (macOS) and set `DYLD_FALLBACK_LIBRARY_PATH`.
- When adding new Celery tasks, expose them via `interviewpanel/tasks.py` and ensure they are registered in `__all__` if needed.

## Next steps
- Hook the frontend to `ws://.../ws/interview/<token>/` and listen for message types: `transcription_update`, `scoring_update`, `next_question`, `interview_completed`, `greeting`.
- Populate the Question Bank (via admin/API) so the adaptive selector can pick valid questions.

## Future scope
The following enhancements are planned for future releases:

1. **Video doubt analysis**: Integrate video analysis capabilities to detect candidate behavior, body language, and engagement patterns during interviews. This will provide additional insights beyond audio transcription for more comprehensive candidate assessment.

2. **SMTP integration for candidate notifications**: Add email functionality to automatically send interview panel join links and credentials to candidates via SMTP. This will streamline the candidate onboarding process and reduce manual communication overhead.

3. **Candidate queue system**: Implement a queueing mechanism to manage multiple candidates waiting to start their interviews. This will help handle concurrent interview sessions more efficiently and provide better resource allocation.

4. **GPU-accelerated transcription**: Migrate the transcription service to a GPU-enabled machine using OpenAI Whisper Large model for faster and more accurate audio transcription. This will significantly improve transcription quality and reduce processing latency during live interviews.
