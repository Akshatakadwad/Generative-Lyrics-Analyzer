# detector.py
"""
ReferenceDetector / Analyzer

Outputs (used by app.py):
{
  "song_summary": str | None,
  "sections": [
     {"label": str, "lyrics": str, "meaning": str | None, "key_lines": [str, ...]}
  ],
  "youtube": {
      "video_id": str,
      "video_url": str,
      "title": str,
      "video_type": str,        # Music Video / Official Audio / Lyric Video / Live / Other
      "embeddable": bool | None # None if not checked
  } | None
}
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from lyrics_explainer_local import LyricsExplainerLocal
from youtube_helper import YouTubeHelper


# -----------------------------
# Helpers
# -----------------------------
def clean_lyrics(text: str) -> str:
    """
    Clean Genius lyrics so section headers are detectable.
    Removes common Genius junk (language list, description, Read More, etc.)
    and normalizes newlines.
    """
    if not text:
        return ""

    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = [ln.strip() for ln in text.split("\n")]

    cleaned: List[str] = []
    started = False

    junk_exact = {
        "read more",
        "you might also like",
        "فارسی",
        "bahasa indonesia",
        "italiano",
        "česky",
        "magyar",
        "繁體中文 (traditional chinese)",
    }

    for ln in lines:
        if not ln:
            # keep blank lines once we've started (for fallback splitting)
            if started:
                cleaned.append("")
            continue

        low = ln.lower()
        if low in junk_exact:
            continue

        # Start once we see bracket header OR a typical lyric line
        # If it looks like long prose (Genius description), ignore until lyrics start.
        if (ln.startswith("[") and ln.endswith("]")):
            started = True
        if not started:
            # If it's a long prose-ish line, skip it
            if len(ln) >= 120 or ln.endswith("…"):
                continue
            started = True

        cleaned.append(ln)

    # collapse repeated blank lines
    out: List[str] = []
    prev_blank = False
    for ln in cleaned:
        blank = (ln == "")
        if blank and prev_blank:
            continue
        out.append(ln)
        prev_blank = blank

    return "\n".join(out).strip()


def split_into_sections(lyrics: str) -> List[Dict[str, str]]:
    """
    Splits lyrics into sections based on bracket headings like:
    [Verse 1], [Chorus], [Bridge], etc.

    If no headings exist, fallback to splitting by blank lines into Part 1/2/3...
    If still not possible, return one section.
    """
    lyrics = clean_lyrics(lyrics)
    if not lyrics:
        return []

    header_re = re.compile(r"^\s*\[(.+?)\]\s*$", re.MULTILINE)

    # Normal split if bracket headers exist
    if header_re.search(lyrics):
        lines = lyrics.split("\n")
        sections: List[Dict[str, str]] = []

        current_label = "Intro"
        current_lines: List[str] = []

        def flush():
            nonlocal current_lines, current_label
            txt = "\n".join(current_lines).strip()
            if txt:
                sections.append({"label": current_label, "text": txt})
            current_lines = []

        for line in lines:
            m = re.match(r"^\s*\[(.+?)\]\s*$", line)
            if m:
                flush()
                current_label = m.group(1).strip()
            else:
                current_lines.append(line)

        flush()
        return sections

    # Fallback: split by blank lines
    chunks = [c.strip() for c in re.split(r"\n\s*\n+", lyrics) if c.strip()]
    if len(chunks) <= 1:
        return [{"label": "Lyrics", "text": lyrics}]

    sections: List[Dict[str, str]] = []
    for i, ch in enumerate(chunks, 1):
        sections.append({"label": f"Part {i}", "text": ch})
    return sections


def guess_video_type(video_title: str) -> str:
    """Best-effort label for UI."""
    t = (video_title or "").lower()
    if "official audio" in t:
        return "Official Audio"
    if "lyric" in t or "lyrics" in t:
        return "Lyric Video"
    if "live" in t:
        return "Live Performance"
    if "official video" in t or "music video" in t:
        return "Music Video"
    if "audio" in t:
        return "Audio"
    return "Other"


# -----------------------------
# Main detector
# -----------------------------
class ReferenceDetector:
    def __init__(self, max_refs: int = 5, model: str = "qwen2.5:7b"):
        # max_refs kept for compatibility (even if not used in this file)
        self.max_refs = max_refs

        # Local explainer (Ollama)
        self.explainer = LyricsExplainerLocal(model=model)

        # YouTube helper (API key required)
        try:
            self.youtube = YouTubeHelper()
        except Exception as e:
            print("⚠️ YouTube helper disabled:", e)
            self.youtube = None

    def analyze_song(self, lyrics: str, song_meta: Dict[str, Any]) -> Dict[str, Any]:
        lyrics = clean_lyrics(lyrics)

        # --- Extract metadata safely ---
        meta = song_meta or {}
        artist = (meta.get("artist") or meta.get("artist_name") or "").strip()
        title = (meta.get("title") or meta.get("song") or meta.get("full_title") or "").strip()

        # --- YouTube lookup ---
        youtube_info: Optional[Dict[str, Any]] = None

        print("DEBUG YouTube artist/title:", repr(artist), repr(title))
        print("DEBUG self.youtube is:", type(self.youtube))

        if self.youtube and artist and title:
            try:
                # Expected dict: {"video_id","url","title","embeddable", ...}
                vid = self.youtube.search_video(artist, title)
                print("DEBUG search_video returned:", vid)

                if isinstance(vid, dict) and vid.get("video_id"):
                    youtube_info = {
                        "video_id": vid.get("video_id"),
                        "video_url": vid.get("url") or vid.get("video_url"),
                        "title": vid.get("title") or "",
                        "embeddable": vid.get("embeddable", None),
                        "video_type": vid.get("video_type") or guess_video_type(vid.get("title") or ""),
                    }
            except Exception as e:
                print("⚠️ YouTube search failed:", repr(e))
        else:
            print("DEBUG YouTube skipped (missing helper or artist/title).")

        print("DEBUG youtube_info FINAL:", youtube_info)

        # --- Split lyrics into sections ---
        print("🔍 Splitting lyrics into sections...")
        raw_sections = split_into_sections(lyrics)

        # --- Song summary ---
        song_summary = None
        try:
            if hasattr(self.explainer, "summarize_song"):
                song_summary = self.explainer.summarize_song(title, artist, lyrics)
        except Exception as e:
            print("⚠️ summarize_song failed:", e)
            song_summary = None

        # --- Explain each section ---
        analyzed_sections: List[Dict[str, Any]] = []

        print(f"🤖 Explaining {len(raw_sections)} sections (local model)...")
        for sec in raw_sections:
            section_label = sec.get("label", "Section")
            section_text = sec.get("text", "")

            meaning = None
            key_lines: List[str] = []

            try:
                # preferred keyword call
                out = self.explainer.explain_section(
                    title=title,
                    artist=artist,
                    section_label=section_label,
                    text=section_text,
                )
            except TypeError:
                # fallback positional call
                out = self.explainer.explain_section(title, artist, section_label, section_text)
            except Exception as e:
                print("⚠️ explain_section failed:", section_label, repr(e))
                out = None

            if isinstance(out, dict):
                meaning = out.get("meaning")
                kl = out.get("key_lines") or []
                if isinstance(kl, list):
                    key_lines = [str(x).strip() for x in kl if str(x).strip()]
                else:
                    key_lines = []

            analyzed_sections.append(
                {
                    "label": section_label,
                    "lyrics": section_text,
                    "meaning": meaning,
                    "key_lines": key_lines[:4],
                }
            )

        return {
            "song_summary": song_summary,
            "sections": analyzed_sections,
            "youtube": {
                "video_id": youtube_info.get("video_id"),
                "video_url": youtube_info.get("video_url"),
                "title": youtube_info.get("title"),
                "video_type": youtube_info.get("video_type"),
                "embeddable": youtube_info.get("embeddable"),
            } if youtube_info else None,
        }

