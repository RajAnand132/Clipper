"""Persistent Character Vault and Episodic Memory Engine for PeakCut/Clipper.
Maintains ongoing Shows, Series, Character visual anchors, and Episode history
so the AI maintains 100% narrative and character continuity across episodes.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from studio import config

SERIES_DIR = config.DATA_DIR / "series"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", slug) or f"series-{int(time.time())}"


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_json(file_path: Path, default=None):
    if not file_path.is_file():
        return default
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(file_path: Path, data):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp = file_path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(file_path)


# ---------------------------------------------------------------- Series Management

def list_series() -> list[dict]:
    """Lists all registered series profiles with summary stats."""
    _ensure_dir(SERIES_DIR)
    results = []
    for d in sorted(SERIES_DIR.iterdir()):
        if d.is_dir():
            s_file = d / "series.json"
            data = _load_json(s_file)
            if data and "id" in data:
                episodes = data.get("episodes", [])
                results.append({
                    "id": data["id"],
                    "title": data.get("title", d.name),
                    "genre": data.get("genre", "3D Animation"),
                    "visual_style": data.get("visual_style", "3D Pixar CGI"),
                    "default_language": data.get("default_language", "en"),
                    "aspect_ratio": data.get("aspect_ratio", "16:9"),
                    "characters_count": len(data.get("characters", [])),
                    "episodes_count": len(episodes),
                    "latest_episode": episodes[-1] if episodes else None,
                    "updated_at": data.get("updated_at", "")
                })
    return results


def get_series(series_id: str) -> dict | None:
    """Returns the full series record, including character vault and episode logs."""
    s_file = SERIES_DIR / series_id / "series.json"
    data = _load_json(s_file)
    if not data:
        return None
    # Normalize characters if any id is missing
    chars = data.get("characters", [])
    changed = False
    for c in chars:
        if not c.get("id"):
            c["id"] = _slugify(c.get("name", "character"))
            changed = True
        if not c.get("avatar_url"):
            c["avatar_url"] = f"/api/series/{series_id}/characters/{c['id']}/avatar.jpg"
            changed = True
    if changed:
        _save_json(s_file, data)
    return data


def create_series(
    title: str,
    genre: str = "3D Cartoon Adventure",
    visual_style: str = "high-gloss 3D Pixar toy CGI, octane render, soft volumetric lighting, vibrant primary colors, 8k",
    aspect_ratio: str = "16:9",
    default_language: str = "en",
    characters: list[dict] | None = None,
    series_id: str | None = None
) -> dict:
    """Creates a new ongoing series workspace."""
    sid = series_id or _slugify(title)
    s_dir = _ensure_dir(SERIES_DIR / sid)
    s_file = s_dir / "series.json"
    
    existing = _load_json(s_file)
    if existing:
        return existing

    # Ensure each character has an id and avatar_url
    norm_chars = []
    for c in (characters or []):
        cid = c.get("id") or _slugify(c.get("name", "character"))
        norm_c = dict(c)
        norm_c["id"] = cid
        norm_c["avatar_url"] = f"/api/series/{sid}/characters/{cid}/avatar.jpg"
        norm_chars.append(norm_c)

    record = {
        "id": sid,
        "title": title.strip(),
        "genre": genre.strip(),
        "visual_style": visual_style.strip(),
        "default_language": default_language.strip().lower() or "en",
        "aspect_ratio": aspect_ratio if aspect_ratio in ("16:9", "9:16") else "16:9",
        "characters": norm_chars,
        "episodes": [],
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    _save_json(s_file, record)
    return record


def update_series(series_id: str, updates: dict) -> dict | None:
    """Updates high-level settings for a series (language, title, genre, style)."""
    series = get_series(series_id)
    if not series:
        return None
    allowed = ["title", "genre", "visual_style", "default_language", "aspect_ratio"]
    for k in allowed:
        if k in updates:
            series[k] = updates[k]
    series["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save_json(SERIES_DIR / series_id / "series.json", series)
    return series


# ---------------------------------------------------------------- Character Vault

def add_character(series_id: str, character: dict) -> dict | None:
    """Adds a character to the persistent character vault for this series."""
    series = get_series(series_id)
    if not series:
        return None
    
    char_id = character.get("id") or _slugify(character.get("name", "character"))
    chars = series.setdefault("characters", [])
    
    # Check if character already exists
    for i, c in enumerate(chars):
        if c.get("id") == char_id:
            chars[i].update(character)
            series["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            _save_json(SERIES_DIR / series_id / "series.json", series)
            return chars[i]
            
    char_record = {
        "id": char_id,
        "name": character.get("name", "Unnamed"),
        "species": character.get("species", "Character"),
        "visual_anchor": character.get("visual_anchor", ""),
        "voice_id": character.get("voice_id", "en-US-ChristopherNeural"),
        "personality": character.get("personality", ""),
        "avatar_url": f"/api/series/{series_id}/characters/{char_id}/avatar.jpg"
    }
    chars.append(char_record)
    series["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save_json(SERIES_DIR / series_id / "series.json", series)
    return char_record


def get_character_vault(series_id: str) -> list[dict]:
    """Returns all registered characters for this series."""
    series = get_series(series_id)
    return series.get("characters", []) if series else []


# ---------------------------------------------------------------- Episode History & Continuity

def add_episode(series_id: str, episode_data: dict) -> dict | None:
    """Logs a new episode (draft or completed) to the series history."""
    series = get_series(series_id)
    if not series:
        return None
    
    episodes = series.setdefault("episodes", [])
    ep_num = episode_data.get("episode_num") or (len(episodes) + 1)
    
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ep_record = {
        "episode_num": ep_num,
        "title": episode_data.get("title", f"Episode {ep_num}"),
        "summary": episode_data.get("summary", ""),
        "unresolved_hook": episode_data.get("unresolved_hook", ""),
        "featured_characters": episode_data.get("featured_characters", []),
        "status": episode_data.get("status", "draft"),  # draft, approved, rendering, completed
        "script": episode_data.get("script", []),
        "duration": episode_data.get("duration", 0),
        "video_file": episode_data.get("video_file", ""),
        "created_at": episode_data.get("created_at") or now_iso,
        "updated_at": now_iso
    }
    
    # Update existing episode if present
    for i, ep in enumerate(episodes):
        if ep.get("episode_num") == ep_num:
            if ep.get("created_at"):
                ep_record["created_at"] = ep["created_at"]
            episodes[i].update(ep_record)
            series["updated_at"] = now_iso
            _save_json(SERIES_DIR / series_id / "series.json", series)
            return episodes[i]
            
    episodes.append(ep_record)
    series["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save_json(SERIES_DIR / series_id / "series.json", series)
    return ep_record


def get_episode(series_id: str, ep_num: int) -> dict | None:
    """Returns a specific episode by number."""
    series = get_series(series_id)
    if not series:
        return None
    for ep in series.get("episodes", []):
        if ep.get("episode_num") == ep_num:
            return ep
    return None


def update_episode(series_id: str, ep_num: int, updates: dict) -> dict | None:
    """Updates metadata (title, summary, hook) for an existing episode."""
    series = get_series(series_id)
    if not series:
        return None
    episodes = series.setdefault("episodes", [])
    for ep in episodes:
        if ep.get("episode_num") == ep_num:
            for k in ["title", "summary", "unresolved_hook"]:
                if k in updates and updates[k] is not None:
                    ep[k] = str(updates[k]).strip()
            ep["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            series["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            _save_json(SERIES_DIR / series_id / "series.json", series)
            return ep
    return None


def delete_series(series_id: str) -> bool:
    """Permanently deletes a series folder and all its episodes/characters."""
    import shutil
    s_dir = SERIES_DIR / series_id
    if s_dir.is_dir():
        shutil.rmtree(s_dir, ignore_errors=True)
        return True
    return False


def delete_episode(series_id: str, ep_num: int) -> bool:
    """Deletes an episode and its rendered media assets from a series."""
    import shutil
    series = get_series(series_id)
    if not series:
        return False
    episodes = series.setdefault("episodes", [])
    before_len = len(episodes)
    series["episodes"] = [ep for ep in episodes if ep.get("episode_num") != ep_num]
    if len(series["episodes"]) == before_len:
        return False
    
    # Remove rendered episode media files if they exist
    ep_dir = SERIES_DIR / series_id / "episodes" / f"ep_{ep_num:03d}"
    if ep_dir.is_dir():
        shutil.rmtree(ep_dir, ignore_errors=True)
        
    series["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save_json(SERIES_DIR / series_id / "series.json", series)
    return True


def get_continuity_context(series_id: str) -> dict:
    """Aggregates series lore, character roster, and past episode arcs
    specifically formatted for Gemini to analyze before writing the next episode."""
    series = get_series(series_id)
    if not series:
        return {}
    
    episodes = series.get("episodes", [])
    past_summaries = []
    for ep in episodes:
        past_summaries.append({
            "episode_num": ep.get("episode_num"),
            "title": ep.get("title"),
            "summary": ep.get("summary"),
            "unresolved_hook": ep.get("unresolved_hook")
        })
        
    latest_hook = episodes[-1].get("unresolved_hook", "") if episodes else ""
    
    return {
        "series_id": series.get("id"),
        "title": series.get("title"),
        "genre": series.get("genre"),
        "visual_style": series.get("visual_style"),
        "default_language": series.get("default_language", "en"),
        "aspect_ratio": series.get("aspect_ratio", "16:9"),
        "characters": series.get("characters", []),
        "past_episodes": past_summaries,
        "latest_unresolved_hook": latest_hook,
        "next_episode_num": len(episodes) + 1
    }
