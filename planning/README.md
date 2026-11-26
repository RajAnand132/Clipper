# Clipper — Engineering Planning & Feature Blueprints

Welcome to the **Planning & Engineering Specifications** repository for Clipper.

This directory serves as the single source of truth for all proposed, planned, and approved features, architectural redesigns, and technical blueprints. Whenever we finalize any plan, a dedicated, numbered markdown file is created here with exact specifications, module targets, algorithmic designs, and code-level implementation steps.

---

## Master Plan Registry

| Plan ID | Title | Status | Target Modules | Primary Objective |
| :---: | :--- | :---: | :--- | :--- |
| **01** | [01_DESIGN_AND_VISUAL_ENHANCEMENTS.md](file:///E:/YouTube/Automation/Clipper/planning/01_DESIGN_AND_VISUAL_ENHANCEMENTS.md) | **Completed** | `studio/templates.py`<br/>`studio/render.py`<br/>`studio/brain.py` | Modern viral captions (Hormozi, MrBeast, One-Word), retention progress bar, auto-emojis, facecam rounded borders, and auto-fade hook cards. |
| **02** | [02_LONG_VIDEO_AND_PERFORMANCE.md](file:///E:/YouTube/Automation/Clipper/planning/02_LONG_VIDEO_AND_PERFORMANCE.md) | **Approved** | `studio/transcribe.py`<br/>`studio/jobs.py`<br/>`studio/brain.py`<br/>`studio/render.py` | Chunked map-reduce ASR for 2–4 hour long videos, 2-stage hierarchical LLM analysis, and NVENC/QSV GPU hardware acceleration. |
| **03** | [03_ACTIVE_SPEAKER_TRACKING.md](file:///E:/YouTube/Automation/Clipper/planning/03_ACTIVE_SPEAKER_TRACKING.md) | **Draft** | `studio/facecam.py`<br/>`studio/render.py` | OpenCV YuNet face detection, VAD speaker correlation, and smooth Exponential Moving Average (EMA) Pan & Scan for podcasts. |
| **04** | [04_MULTI_PLATFORM_DISTRIBUTION.md](file:///E:/YouTube/Automation/Clipper/planning/04_MULTI_PLATFORM_DISTRIBUTION.md) | **Draft** | `studio/posting.py`<br/>`studio/accounts.py`<br/>`studio/db.py` | Twitter/X video publishing, LinkedIn video publishing, webhook automation (Discord/Slack), and rate limiting. |
| **05** | [05_TEXT_TO_VIDEO_AND_COMPILATION_ENGINE.md](file:///E:/YouTube/Automation/Clipper/planning/05_TEXT_TO_VIDEO_AND_COMPILATION_ENGINE.md) | **Approved** | `studio/storyteller.py`<br/>`studio/concat.py`<br/>`studio/render.py`<br/>`web/index.html` | Text-to-Video AI Storyteller (Prompt -> 3D Cartoon / Anime -> Voiceover -> Subtitles) and 1-Click Clip Compilation Builder (Clubbing clips into long videos with crossfade transitions). |
| **06** | [06_EPISODIC_SERIES_AND_CONTINUITY_ENGINE.md](file:///E:/YouTube/Automation/Clipper/planning/06_EPISODIC_SERIES_AND_CONTINUITY_ENGINE.md) | **Approved** | `studio/series.py`<br/>`studio/memory.py`<br/>`studio/db.py`<br/>`studio/storyteller.py` | Episodic Series Management, Context Memory across episodes (character consistency, previous episode lore, "Previously On" recaps), and Automated Long-to-Short Cross-Repurposing flywheel. |
| **07** | [07_HINDI_LANGUAGE_MODELS_AND_ORGANIC_VOICE.md](file:///E:/YouTube/Automation/Clipper/planning/07_HINDI_LANGUAGE_MODELS_AND_ORGANIC_VOICE.md) | **Approved** | `studio/hindi.py`<br/>`studio/tts.py`<br/>`studio/roman.py`<br/>`studio/brain.py` | Organic Conversational Hindi & Hinglish scriptwriting, Indian Neural Voices (`hi-IN-MadhurNeural`, `hi-IN-SwaraNeural`), cartoon pitch modulation, and Devanagari bubble fonts (`Modak`). |

---

## Status Definitions

- **Draft**: Feature design is drafted and open for discussion and refinement.
- **Approved**: Technical design is finalized and ready for development.
- **In Development**: Feature is actively being implemented on the `develop` branch.
- **Completed**: Feature is merged, tested, and running in production.

---

## Plan Document Standard Format

Every plan document in this folder follows a rigorous engineering blueprint:

1. **Executive Summary & Goals**: What the feature does and why it matters.
2. **Architecture & Visual Workflow**: Mermaid diagrams illustrating dataflow and component interaction.
3. **Module Touchpoints**: Exact list of files and classes affected.
4. **Algorithmic & Mathematical Models**: Exact formulas, ASS subtitle tags, or FFmpeg filtergraphs.
5. **Step-by-Step Implementation Checklist**: Concrete tasks with code snippets.
6. **Verification & Testing Protocol**: Commands to validate the changes without regressions.
