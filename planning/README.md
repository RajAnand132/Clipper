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
| **05** | [05_TEXT_TO_VIDEO_AND_COMPILATION_ENGINE.md](file:///E:/YouTube/Automation/Clipper/planning/05_TEXT_TO_VIDEO_AND_COMPILATION_ENGINE.md) | **Approved** | `studio/memory.py`<br/>`studio/storyteller.py`<br/>`studio/tts.py`<br/>`studio/visuals.py`<br/>`studio/concat.py`<br/>`web/index.html` | Autonomous 3D Episodic Series, Storyteller & Compilation Engine: AI previous-episode analysis, 3 smart next-episode suggestions, ensemble character memory vault, human-in-the-loop script approval gate, 3D character + background parallax motion, multi-voice neural TTS, and long/short video stitching. |
| **06** | [06_EPISODIC_SERIES_AND_CONTINUITY_ENGINE.md](file:///E:/YouTube/Automation/Clipper/planning/06_EPISODIC_SERIES_AND_CONTINUITY_ENGINE.md) | **Approved** | `studio/series.py`<br/>`studio/memory.py`<br/>`studio/db.py`<br/>`studio/storyteller.py` | Episodic Series Management, Context Memory across episodes (character consistency, previous episode lore, "Previously On" recaps), and Automated Long-to-Short Cross-Repurposing flywheel. |
| **07** | [07_HINDI_LANGUAGE_MODELS_AND_ORGANIC_VOICE.md](file:///E:/YouTube/Automation/Clipper/planning/07_HINDI_LANGUAGE_MODELS_AND_ORGANIC_VOICE.md) | **Approved** | `studio/hindi.py`<br/>`studio/tts.py`<br/>`studio/roman.py`<br/>`studio/brain.py` | Organic Conversational Hindi & Hinglish scriptwriting, Indian Neural Voices (`hi-IN-MadhurNeural`, `hi-IN-SwaraNeural`), cartoon pitch modulation, and Devanagari bubble fonts (`Modak`). |
| **08** | [08_UNIVERSAL_VIDEO_GENERATION_ENGINE.md](file:///E:/YouTube/Automation/Clipper/planning/08_UNIVERSAL_VIDEO_GENERATION_ENGINE.md) | **In Development** | `studio/formats.py`<br/>`studio/providers.py`<br/>`studio/production.py`<br/>`studio/soundtrack.py` | Any kind of video from a prompt: 20 format recipes (horror, anime, 2D, 3D, documentary...), pluggable image/motion providers (Pollinations, OpenAI-compatible, ComfyUI), multi-speaker multi-shot scenes, colour grades, music & ambience mixing, scene caching. |
| **09** | [09_REAL_3D_ANIMATION_ENGINE.md](file:///E:/YouTube/Automation/Clipper/planning/09_REAL_3D_ANIMATION_ENGINE.md) | **In Development** | `studio/anim3d/`<br/>`web/studio3d/`<br/>`tools/blender/` | Real animated episodes: rigged 3D characters that walk, talk (lip-sync), emote and act in 3D sets, with an auto camera. One scene file, rendered by Three.js (free, fast, live preview) or Blender (premium). |
| **10** | [10_PRODUCTION_PROGRESS.md](file:///E:/YouTube/Automation/Clipper/planning/10_PRODUCTION_PROGRESS.md) | **Built, in testing** | `studio/progress.py`<br/>`studio/production.py`<br/>`studio/series.py`<br/>`web/index.html` | Episode production panel: every scene and final step with its own progress, elapsed and time-left timers, render time kept per episode, survives reloads, resume after a restart; faster, smaller 3D finishing. |
| **11** | [11_SOUND_AND_STORY_VISUALS.md](file:///E:/YouTube/Automation/Clipper/planning/11_SOUND_AND_STORY_VISUALS.md) | **In Development** | `studio/soundtrack.py`<br/>`studio/sfx.py`<br/>`studio/anim3d/`<br/>`web/studio3d/` | Theme music per format and per scene with stingers, sound effects, and story visuals: things talked about appear on screen (in the set, in a thought bubble, as a cut-in or a card) at the exact word. |
| **12** | [12_SETS_AND_ENVIRONMENTS.md](file:///E:/YouTube/Automation/Clipper/planning/12_SETS_AND_ENVIRONMENTS.md) | **Built** | `studio/anim3d/sets.py`<br/>`studio/anim3d/director.py`<br/>`web/studio3d/` | Backgrounds that fit every scene: the script describes each set (place, era, culture, time, weather, landmarks), ~40 modular set kits, real skies and light, depth and atmosphere, and a Location Vault so returning places look the same. |
| **13** | [13_MULTIPLE_AI_KEYS.md](file:///E:/YouTube/Automation/Clipper/planning/13_MULTIPLE_AI_KEYS.md) | **Proposed** | `studio/ai.py`<br/>`studio/usage.py`<br/>`studio/brain.py`<br/>`web/index.html` | Several AI keys in a pool: each call uses the first key fit for it, a key that hits a limit rests and the next is used at once, refused keys are shown, usage per key, and a warning when keys share one project's quota. |

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
