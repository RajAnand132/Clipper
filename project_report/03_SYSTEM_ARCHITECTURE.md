# Clipper — System Architecture & Technical Design

This document details the software architecture, module decomposition, data flow, concurrency model, and database entity relationships of the **Clipper** system.

---

## 1. High-Level Architectural Principles

Clipper is designed around five core engineering principles:

1. **Single-Process Async Micro-Kernel**: The backend runs as a single async Python process using FastAPI and Uvicorn. There are no heavy external task broker requirements (no Celery, Redis, or RabbitMQ required for local execution).
2. **Zero-Dependency Frontend**: The user interface is pure, modern vanilla HTML5, CSS3, and JavaScript. It requires no `node_modules`, `npm install`, Webpack, or Vite build steps, ensuring instant startup and low disk footprint.
3. **Hybrid Local/Cloud Processing**: Heavy media operations (audio demuxing, speech recognition, visual computer vision, video rendering) execute 100% locally on the host CPU/GPU. Generative reasoning (transcript context analysis, virality scoring) utilizes cloud LLMs with local fallback support.
4. **Resilient Job State Machine**: Video processing tasks follow a deterministic multi-stage lifecycle with state persistence in SQLite, enabling cancellation, retries, and atomic error reporting.
5. **Real-Time Client Synchronization**: Lightweight memory-buffered state tracking (`ctx.bump()`) allows frontend clients to poll `/api/sync` efficiently without triggering repeated database queries.

---

## 2. High-Level Architecture Diagram

```mermaid
flowchart TD
    subgraph Client["Client Tier (Browser)"]
        UI["Web UI Dashboard<br/>(Vanilla HTML5 / CSS3 / ES6)"]
        Poll["State Sync Poller<br/>(/api/sync)"]
        Upload["Direct File Streamer<br/>(/api/upload)"]
    end

    subgraph API["FastAPI Application Tier (server.py)"]
        Router["API Route Handlers<br/>(Jobs, Settings, Creators, Accounts)"]
        MemSync["In-Memory Sync Buffer<br/>(ctx.bump & state cache)"]
        StaticServe["Static File Provider<br/>(web/*)"]
    end

    subgraph Engine["Processing Core (jobs.py & worker threads)"]
        Queue["Job Scheduling Queue<br/>(ThreadPoolExecutor)"]
        StateMachine["Job State Machine<br/>(queued -> downloading -> transcribing -> analyzing -> rendering -> done)"]
    end

    subgraph Pipelines["Specialized Pipelines"]
        YTDL["Media Ingest<br/>(media.py / yt-dlp)"]
        ASR["Offline Speech Engine<br/>(transcribe.py / sherpa-onnx)"]
        Brain["AI Viral Analysis<br/>(brain.py & ai.py)"]
        CV["Gaming Facecam Detector<br/>(facecam.py / OpenCV)"]
        Render["FFmpeg Compositor<br/>(render.py / Pillow / ASS)"]
        LiveEng["Live Stream Engine<br/>(live.py / Rolling Buffer)"]
        SocialPub["Social Publisher<br/>(posting.py / OAuth2)"]
    end

    subgraph Storage["Persistence & Local Storage Tier"]
        DB[("SQLite Database<br/>data/peakcut.db")]
        Models["Model Cache<br/>data/models/*"]
        MediaFiles["Media Store<br/>data/jobs/* & data/clips/*"]
    end

    UI --> Router
    Poll --> MemSync
    Upload --> Router
    Router --> Queue
    Queue --> StateMachine

    StateMachine --> YTDL
    StateMachine --> ASR
    StateMachine --> Brain
    StateMachine --> CV
    StateMachine --> Render
    StateMachine --> SocialPub

    ASR --> Models
    YTDL --> MediaFiles
    Render --> MediaFiles
    StateMachine --> DB
    Router --> DB
```

---

## 3. Technology Stack Matrix

| Layer | Component | Technology / Library | Purpose |
| :--- | :--- | :--- | :--- |
| **Web Server** | ASGI Framework | **FastAPI 0.115+** | High-performance asynchronous REST API routing |
| **ASGI Engine**| Server Runner | **Uvicorn** | Fast event-loop ASGI server with hot-reloading |
| **Frontend** | Client Dashboard | **Vanilla HTML5 / CSS3 / JS** | Zero-bundle responsive UI with real-time sync |
| **Media Extraction** | Downloader | **yt-dlp** | Robust video and audio stream extraction from 1000+ sites |
| **ASR Speech** | Offline Transcriber| **sherpa-onnx** | Quantized NeMo Parakeet TDT 0.6B INT8 offline speech recognition |
| **AI LLM** | Viral Candidate Selector| **Google Gemini API / OpenAI / Ollama** | Context reasoning, virality scoring, hook titling, JSON structured output |
| **Computer Vision** | Face & Webcam Detection| **OpenCV (headless) & Pillow** | Temporal edge variance calculation, facecam bounding box isolation |
| **Video Engine** | Compositor & Encoder | **FFmpeg & FFprobe (Gyan 9.0+)** | Complex filtergraphs, scaling, pad, overlay, audio loudnorm, H.264/AAC |
| **Database** | Relational Store | **SQLite3 & SQLAlchemy 2.0+** | Local persistence of jobs, clips, creator profiles, and OAuth credentials |

---

## 4. Module-by-Module Breakdown

### 4.1. `peakcut/server.py`
The central HTTP entry point.
- Configures FastAPI routes for jobs, settings, creators, media streaming, and live feeds.
- Serves static assets from the `web/` directory.
- Manages the `/api/sync` endpoint: uses atomic counter bumping (`ctx.bump()`) so clients only receive payload updates when state actually changes.

### 4.2. `peakcut/jobs.py`
The execution orchestrator.
- Manages the job lifecycle: `queued` $\to$ `downloading` $\to$ `transcribing` $\to$ `analyzing` $\to$ `rendering` $\to$ `done` (or `failed`).
- Enforces concurrency limits to prevent CPU exhaustion during parallel FFmpeg rendering.
- Handles atomic cancellation signals: if a user cancels a job in the UI, child subprocesses (FFmpeg / yt-dlp) are terminated cleanly.

### 4.3. `peakcut/transcribe.py`
The local offline speech-to-text runner.
- Initializes the `sherpa-onnx` runtime using the NeMo Parakeet TDT INT8 model.
- Transcribes extracted audio chunks without network requests.
- Emits words with millisecond-accurate start and end timestamps (`[{word: "Hello", start: 0.12, end: 0.45}, ...]`).

### 4.4. `peakcut/brain.py` & `peakcut/ai.py`
The viral intelligence engine.
- Formulates multi-turn prompts containing full timestamped transcripts.
- Instructs the LLM to identify high-retention segments using Hook-Story-Payoff metrics.
- Enforces strict JSON schema validation on the AI response with automated syntactic auto-repair if the model outputs malformed JSON.

### 4.5. `peakcut/facecam.py`
The computer vision layout engine.
- Samples video frames across temporal intervals.
- Computes edge variance to detect static HUD boundaries (e.g., gamer facecam overlays).
- Verifies facial presence using lightweight Haar/YuNet cascades.
- Emits crop coordinates: top box (facecam) and bottom box (gameplay action).

### 4.6. `peakcut/render.py`
The FFmpeg composite builder.
- Generates subtitle overlays: uses Pillow to render high-DPI subtitle frames or compiles ASS subtitle scripts with word-level highlight tags (`\k`).
- Compiles complex FFmpeg filtergraphs: crops, aspect-ratio pads, overlays facecam and subtitles, and normalizes audio levels via `loudnorm`.
- Encodes the final MP4 using `libx264` and `aac`.

### 4.7. `peakcut/live.py`
The live stream monitoring daemon.
- Connects to ongoing live streams (Twitch, YouTube Live).
- Maintains a local rolling circular buffer of the last 15-30 minutes of video.
- Analyzes live chat velocity (spikes in messages per second) and audio decibel surges to auto-detect moments of peak excitement.

### 4.8. `peakcut/posting.py` & `peakcut/db.py`
Publishing and persistence.
- Handles OAuth2 token refresh workflows for YouTube, TikTok, and Instagram.
- Schedules uploads according to user-defined publishing windows.
- Manages SQLite database schema migrations and transactions.

---

## 5. End-to-End Pipeline Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Client
    participant Server as FastAPI Server
    participant Queue as Jobs Queue
    participant Media as yt-dlp / Ingest
    participant ASR as sherpa-onnx ASR
    participant AI as Gemini / LLM Brain
    participant CV as OpenCV Facecam
    participant FFmpeg as FFmpeg Render
    participant DB as SQLite Database

    User->>Server: POST /api/jobs (URL, clip target, layout)
    Server->>DB: Insert Job (status='queued')
    Server->>Queue: Submit Job Task
    Server-->>User: 200 OK (job_id, status='queued')

    Queue->>DB: Update Job (status='downloading')
    Queue->>Media: Download Video & Extract Audio (16kHz WAV)
    Media-->>Queue: Audio & Video files ready

    Queue->>DB: Update Job (status='transcribing')
    Queue->>ASR: Process 16kHz WAV
    ASR-->>Queue: Return Word-Level Timestamps

    Queue->>DB: Update Job (status='analyzing')
    Queue->>AI: Send Transcript & Scoring Rules
    AI-->>Queue: Return JSON Candidate Clips (Hook, Start, End, Score)

    loop For each Viral Candidate
        Queue->>CV: Check Frame Samples for Facecam
        CV-->>Queue: Return Layout Bounding Boxes (Facecam + Gameplay)
        Queue->>DB: Update Job (status='rendering', clip_index=i)
        Queue->>FFmpeg: Execute Filtergraph (Crop, Subtitle, Loudnorm)
        FFmpeg-->>Queue: Emitted Rendered MP4
        Queue->>DB: Insert Clip (path, viral_score, title, hook)
    end

    Queue->>DB: Update Job (status='done')
    User->>Server: GET /api/sync
    Server-->>User: State Updated: Job Complete, 5 Clips Ready
```

---

## 6. Database Entity-Relationship Diagram (ERD)

The SQLite relational schema (`data/peakcut.db`) governs jobs, generated clips, creator settings, and publishing logs:

```mermaid
erDiagram
    JOBS ||--o{ CLIPS : "generates"
    CREATORS ||--o{ JOBS : "owns"
    CREATORS ||--o{ ACCOUNTS : "links"
    CLIPS ||--o{ PUBLISH_LOGS : "publishes_to"

    JOBS {
        string id PK "UUID"
        string creator_id FK "Owner creator profile"
        string source_type "url | upload | live"
        string source_url "Original media URL"
        string source_path "Local downloaded media path"
        string status "queued | downloading | transcribing | analyzing | rendering | done | failed"
        float progress "0.0 to 1.0"
        string language "Detected or specified language"
        string layout_mode "center_crop | facecam_split | blur_pad"
        string error_message "Failure trace if failed"
        datetime created_at "Creation timestamp"
        datetime updated_at "Last update timestamp"
    }

    CLIPS {
        string id PK "UUID"
        string job_id FK "Parent job reference"
        string title "Catchy AI-generated Title"
        string hook "Spoken hook sentence"
        float start_time "Start offset in seconds"
        float end_time "End offset in seconds"
        float duration "Total clip duration"
        float viral_score "Computed score (1.0 to 10.0)"
        string file_path "Rendered MP4 filesystem path"
        string thumbnail_path "Rendered JPG thumbnail path"
        string transcript_snippet "Text of the clip"
        string status "draft | approved | scheduled | published"
        datetime created_at "Timestamp"
    }

    CREATORS {
        string id PK "UUID"
        string name "Channel / Creator Name"
        string default_subtitle_style "Subtitles preset"
        string default_aspect_ratio "9:16 | 1:1"
        string watermark_path "Optional logo watermark"
        string prompt_overrides "Custom LLM instructions"
    }

    ACCOUNTS {
        string id PK "UUID"
        string creator_id FK "Creator reference"
        string platform "youtube | tiktok | instagram"
        string account_name "Channel display handle"
        string access_token "Encrypted OAuth token"
        string refresh_token "Encrypted refresh token"
        datetime token_expires_at "Expiration timestamp"
        int daily_upload_limit "Max posts per day"
        int uploaded_today "Counter reset daily"
    }

    PUBLISH_LOGS {
        string id PK "UUID"
        string clip_id FK "Clip reference"
        string account_id FK "Account reference"
        string platform "youtube | tiktok | instagram"
        string platform_post_id "Remote post ID or URL"
        string status "pending | uploading | live | error"
        datetime published_at "Publish timestamp"
    }
```

---

## 7. Real-Time State Synchronization Mechanism

To maintain responsive UI state across browser tabs without WebSockets or server overhead:

```mermaid
sequenceDiagram
    autonumber
    participant Browser as Browser Client
    participant Server as FastAPI Server
    participant Context as In-Memory Context (ctx)
    participant Worker as Background Worker

    Browser->>Server: GET /api/sync?since=0
    Server-->>Browser: 200 OK {version: 1, jobs: [...], active: 1}

    Worker->>Context: ctx.bump() (Progress: 45% -> 50%)
    Note over Context: State version increments to 2

    Browser->>Server: GET /api/sync?since=1
    Server->>Context: Check version > 1
    Server-->>Browser: 200 OK {version: 2, delta: {job_id: 104, progress: 0.50}}

    Browser->>Server: GET /api/sync?since=2
    Note over Server: Version unchanged (2 == 2)
    Server-->>Browser: 200 OK {version: 2, delta: null} (Instant 304/empty payload)
```
