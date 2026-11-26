# Clipper — Pipeline & Algorithm Deep-Dive

This document provides a technical deep-dive into the algorithms, mathematical models, computer vision heuristics, and video compositing pipelines powering **Clipper**.

---

## 1. End-to-End Pipeline Overview

The core Clipper processing pipeline transforms raw video input into high-engagement vertical clips through six sequential phases:

```mermaid
flowchart TD
    subgraph Phase1["1. Ingestion & Demuxing"]
        A["Source Video (URL/Upload)"] --> B["yt-dlp Format Extraction"]
        B --> C["Local MP4 Video Track"]
        B --> D["16kHz Mono WAV Audio Track"]
    end

    subgraph Phase2["2. Speech-to-Text & Alignment"]
        D --> E["sherpa-onnx NeMo Parakeet TDT"]
        E --> F["Word-Level Timestamps<br/>(start_ms, end_ms, token, confidence)"]
    end

    subgraph Phase3["3. Viral Intelligence Engine"]
        F --> G["Transcript Windowing & Tokenization"]
        G --> H["LLM Context Reasoning (Gemini)"]
        H --> I["3-Pillar Scoring Formula<br/>Hook (0-10) + Story (0-10) + Payoff (0-10)"]
        I --> J["Top N Candidate Time Intervals"]
    end

    subgraph Phase4["4. Spatial Layout & Facecam Detection"]
        C --> K["Temporal Video Frame Sampling"]
        K --> L["Edge-Variance HUD Boundary Search"]
        L --> M["Face Verification (YuNet / Haar)"]
        M --> N["Crop Coordinates<br/>(Facecam Box + Gameplay Box)"]
    end

    subgraph Phase5["5. Subtitle Typography Engine"]
        F --> O["Pillow High-DPI Text Render"]
        O --> P["Karaoke Word-Highlight Timing"]
        P --> Q["Alpha-Channel Subtitle PNG Overlay Stream"]
    end

    subgraph Phase6["6. FFmpeg Filtergraph Composition"]
        C --> R["FFmpeg Filtergraph Engine"]
        N --> R
        Q --> R
        R --> S["Final 9:16 H.264 / AAC Vertical Clip"]
    end

    Phase1 --> Phase2
    Phase2 --> Phase3
    Phase3 --> Phase4
    Phase3 --> Phase5
    Phase4 --> Phase6
    Phase5 --> Phase6
```

---

## 2. Audio Ingestion & Offline Speech-to-Text

### 2.1. Extraction & Conditioning
Raw audio is extracted using `ffmpeg` into a normalized format required for optimal ASR inference:
- **Sample Rate**: 16,000 Hz (16 kHz).
- **Channels**: 1 (Mono).
- **Bit Depth**: 16-bit Linear PCM.
- **Dynamic Range Compression**: Light normalization applied to equalize quiet speech and loud screams.

### 2.2. Offline ASR Engine (`sherpa-onnx`)
Clipper utilizes `sherpa-onnx` running the **NeMo Parakeet TDT 0.6B (INT8 quantized)** model:
- **Architecture**: Transducer with Token-and-Duration Transducer (TDT) decoding.
- **Model Size**: ~480 MB (stored locally in `data/models/`).
- **Inference Speed**: ~10x to 15x real-time speed on a modern multi-core CPU (a 60-minute podcast transcribes in ~4 to 5 minutes without needing an expensive GPU).
- **Output Structure**: Emits continuous tokens with word-level timestamps:
  ```json
  [
    {"word": "The", "start": 1.12, "end": 1.28, "prob": 0.98},
    {"word": "biggest", "start": 1.30, "end": 1.64, "prob": 0.99},
    {"word": "mistake", "start": 1.66, "end": 2.10, "prob": 0.95}
  ]
  ```

---

## 3. Viral Candidate Selection Algorithm

The transcript is evaluated by the generative AI engine (`peakcut/brain.py`) using structured prompts.

### 3.1. The 3-Pillar Virality Scoring Formula
Every candidate segment is evaluated against three core viewer retention metrics, yielding a composite Virality Score ($V$):

$$V = 0.40 \cdot H + 0.35 \cdot E + 0.25 \cdot P$$

Where:
- **$H$ (Hook Strength, 0–10)**: Measures the captivating quality of the first 3 to 5 seconds. Does it provoke curiosity, shock, controversy, or ask an urgent question?
- **$E$ (Engagement & Pacing, 0–10)**: Measures informational density and narrative momentum. Does the speaker maintain interest without meandering filler?
- **$P$ (Payoff & Climax, 0–10)**: Measures the conclusion. Is there a punchline, valuable insight, counter-intuitive takeaway, or clear resolution?

### 3.2. Structural Constraints
- **Duration**: Constrained between $T_{\min} = 30\text{s}$ and $T_{\max} = 60\text{s}$.
- **Sentence Integrity**: Must start on a complete opening thought and terminate at a natural sentence boundary (avoiding abrupt mid-sentence cutoffs).
- **No Overlap**: Identified clips must not overlap by more than 15% to ensure diverse highlights.

```mermaid
flowchart TD
    A["Raw Word Timestamps"] --> B["Group into Sentence Windows"]
    B --> C["Filter Segments Between 30s and 60s"]
    C --> D["Evaluate Hook (First 5 seconds)"]
    D --> E["Evaluate Story Momentum"]
    E --> F["Evaluate Punchline / Payoff"]
    F --> G["Calculate Composite Virality Score"]
    G --> H["Rank Candidates & Select Top N"]
```

---

## 4. Computer Vision: Gaming Facecam & Layout Detection

When converting standard horizontal 16:9 gameplay streams into vertical 9:16 shorts, simply center-cropping the video cuts off either the player's facecam or the game action. Clipper solves this using automated computer vision (`peakcut/facecam.py`).

### 4.1. Temporal Edge Variance Algorithm
Webcams and streamer facecam boxes are typically static HUD overlays positioned in a fixed corner (top-left, top-right, bottom-left, or bottom-right).

1. **Frame Sampling**: Extract $K$ frames spaced across the video duration:
   $$F = \{f_1, f_2, \dots, f_K\} \quad (K \approx 10\text{ to }20)$$
2. **Canny Edge Detection**: Compute edge maps $E_i = \text{Canny}(f_i)$ for all sampled frames.
3. **Variance Accumulator**: Calculate pixel-wise temporal variance across the edge maps:
   $$\sigma^2(x, y) = \frac{1}{K} \sum_{i=1}^K \left(E_i(x, y) - \mu_E(x, y)\right)^2$$
   - The *inner content* of the webcam (the streamer moving) has high variance.
   - The *border box* of the webcam is a static edge with near-zero temporal variance.
   - By thresholding and finding contours on the static edge map, rectangular HUD candidate regions are isolated.

4. **Face Verification**:
   Crop candidate boxes and pass them through a lightweight OpenCV YuNet face detector to verify the presence of human facial landmarks.

```mermaid
flowchart TD
    A["Sample Video Frames (f1, f2, ... fK)"] --> B["Compute Canny Edge Maps"]
    B --> C["Calculate Pixel Temporal Variance"]
    C --> D["Isolate Low-Variance Rectangular HUD Borders"]
    D --> E["Extract Candidate Bounding Boxes"]
    E --> F["Run Face Verification (YuNet / Haar)"]
    F -->|Face Detected| G["Found Facecam Box (X, Y, W, H)"]
    F -->|No Face| H["Fallback: Dynamic Center Crop"]
```

### 4.2. Composite 9:16 Split Layout
Once the facecam rectangle is identified:
- **Upper Section (Top 35% of 9:16 frame)**: Facecam box cropped, scaled, and placed at top.
- **Lower Section (Bottom 65% of 9:16 frame)**: Gameplay center-cropped to 9:16 and placed below.

```
+---------------------------+  <-- 1080 x 1920 (9:16 Frame)
|                           |
|       STREAMER FACECAM    |  (Cropped from detected HUD box)
|          (Top 35%)        |
+---------------------------+
|                           |
|                           |
|       GAMEPLAY ACTION     |  (Center-cropped action area)
|         (Bottom 65%)      |
|                           |
|     [ SUBTITLES HERE ]    |
|                           |
+---------------------------+
```

---

## 5. Live Stream Circular Buffer & Chatter Velocity

For 24/7 stream monitoring (`peakcut/live.py`), Clipper continuously monitors incoming video and live chat feeds.

### 5.1. Rolling Circular Video Buffer
- Ingests incoming HLS/DASH streams into rotating 60-second `.ts` segments on disk.
- Retains a sliding window of the last 30 minutes of video. Segments older than 30 minutes are automatically pruned to prevent disk overflow.

### 5.2. Chatter Velocity & Excitement Trigger
The system tracks chat message velocity ($C_v$) measured in messages per second (MPS) over a sliding 10-second window:

$$C_v(t) = \frac{N_{\text{messages}}(t - 10\text{s}, t)}{10}$$

When $C_v(t)$ exceeds 2.5 times the rolling 10-minute baseline average:

$$C_v(t) > 2.5 \cdot \mu_{\text{baseline}}$$

An excitement trigger fires:
1. The system marks a trigger timestamp $t_{\text{spike}}$.
2. Clipper captures the segment $[t_{\text{spike}} - 40\text{s}, t_{\text{spike}} + 20\text{s}]$.
3. The 60-second clip is queued into the transcription and rendering pipeline automatically.

```mermaid
flowchart TD
    A["Live Stream Feed (Twitch / YouTube)"] --> B["Rolling Circular Buffer<br/>(Last 30 Min Video TS Segments)"]
    A --> C["Live Chat Stream (IRC / Live Chat API)"]
    C --> D["Sliding Window Message Velocity<br/>(MPS: Messages Per Second)"]
    D --> E{"Velocity Spike?<br/>Cv > 2.5 * Baseline"}
    E -->|No| D
    E -->|Yes Spike Detected!| F["Trigger Highlight Window<br/>[Spike - 40s to Spike + 20s]"]
    F --> G["Stitch TS Segments from Buffer"]
    G --> H["Queue Clip into Rendering Pipeline"]
```

---

## 6. Subtitle Typography & FFmpeg Filtergraph

### 6.1. Word-by-Word Karaoke Highlighting
To maximize viewer retention, subtitles are displayed 2 to 4 words at a time with the currently spoken word highlighted in bright yellow/green with an active scale pop.

1. **Windowing**: Group adjacent words into 1.5-second readable visual clusters.
2. **Typography Engine**:
   - Subtitles are rasterized with high-DPI anti-aliasing via Pillow using bold geometric sans-serif fonts (e.g., *Montserrat ExtraBold* or *Impact*).
   - A thick outer black border (stroke width: 8–12px) and drop-shadow are applied to guarantee legibility over any background.
3. **Word Timing**: Each word in the cluster turns yellow during its exact $[t_{\text{start}}, t_{\text{end}}]$ duration.

### 6.2. Complex FFmpeg Filtergraph Construction
The entire video composition is rendered in a single-pass FFmpeg process to avoid lossy multi-generation encoding:

```bash
ffmpeg -y -ss 00:01:15.000 -to 00:02:05.000 -i input.mp4 \
  -filter_complex "
    [0:v]split=2[cam][game];
    [cam]crop=480:360:1440:0,scale=1080:672:flags=lanczos[top];
    [game]crop=1080:1248:420:300[bottom];
    [top][bottom]vstack[stacked];
    [stacked]subtitles=captions.ass:force_style='FontName=Montserrat,FontSize=28,PrimaryColour=&H0000FFFF'[vfinal];
    [0:a]loudnorm=I=-14:LRA=11:TP=-1.5[afinal]
  " \
  -map "[vfinal]" -map "[afinal]" \
  -c:v libx264 -preset fast -crf 20 -c:a aac -b:a 192k \
  output_clip.mp4
```

```mermaid
flowchart LR
    In["Input Video Track"] --> Split["split=2"]
    Split -->|Stream 1| CropCam["crop facecam<br/>scale to 1080x672"]
    Split -->|Stream 2| CropGame["crop gameplay<br/>1080x1248"]
    CropCam --> VStack["vstack"]
    CropGame --> VStack
    VStack --> Subs["subtitles filter<br/>(Word Highlight ASS)"]
    Subs --> OutV["Final Video Stream"]

    InA["Input Audio Track"] --> LoudNorm["loudnorm filter<br/>(EBU R128)"]
    LoudNorm --> OutA["Final Audio Stream"]
```
