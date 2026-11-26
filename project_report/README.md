# Clipper — Master Project Report Index

Welcome to the comprehensive technical documentation and project report for **Clipper** (formerly PeakCut).

---

## Table of Contents

| Chapter | Document | Description | Key Topics |
| :---: | :--- | :--- | :--- |
| **01** | [01_PROJECT_OVERVIEW.md](file:///E:/YouTube/Automation/Clipper/project_report/01_PROJECT_OVERVIEW.md) | **Executive Overview & Value Proposition** | What Clipper is, target audience, core capabilities, competitive comparison with OpusClip/Klap. |
| **02** | [02_USER_GUIDE.md](file:///E:/YouTube/Automation/Clipper/project_report/02_USER_GUIDE.md) | **Operational Manual & User Guide** | Local startup (`dev.bat`, F5), web UI walkthrough, job submission, AI configuration, multi-platform OAuth. |
| **03** | [03_SYSTEM_ARCHITECTURE.md](file:///E:/YouTube/Automation/Clipper/project_report/03_SYSTEM_ARCHITECTURE.md) | **System Architecture & Technical Design** | Micro-kernel design, tech stack matrix, module-by-module breakdown, sequence diagrams, database ERD. |
| **04** | [04_PIPELINE_AND_ALGORITHMS.md](file:///E:/YouTube/Automation/Clipper/project_report/04_PIPELINE_AND_ALGORITHMS.md) | **Pipeline & Algorithm Deep-Dive** | Offline ASR (`sherpa-onnx`), Virality scoring formula, gaming facecam CV detection, live stream buffer, FFmpeg compositor. |
| **05** | [05_ENHANCEMENT_ROADMAP.md](file:///E:/YouTube/Automation/Clipper/project_report/05_ENHANCEMENT_ROADMAP.md) | **Local Enhancement Roadmap** | Hormozi/MrBeast subtitles, auto-emojis, long-video map-reduce, GPU acceleration (NVENC), active speaker tracking. |

---

## Quick Reference & Commands

### Starting the Project Locally
```cmd
# Using single-click batch runner
.\dev.bat

# Or direct Python uvicorn runner
.\.venv\Scripts\activate
python -m uvicorn peakcut.server:app --host 127.0.0.1 --port 8765 --reload
```

### Accessing the Web Dashboard
Open your browser to:
```
http://127.0.0.1:8765
```

### Git Fork Synchronization Strategy
To keep your customized code safely isolated from upstream changes:
1. Always work on the **`develop`** branch:
   ```bash
   git checkout develop
   ```
2. Keep the **`main`** branch completely clean.
3. When syncing upstream updates:
   ```bash
   git checkout main
   git pull origin main
   git checkout develop
   git merge main
   ```
