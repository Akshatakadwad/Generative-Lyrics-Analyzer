"""
Local Lyrics Explainer using Ollama
- Generates: song summary + section-wise meaning + key lines
- Uses Ollama HTTP API: http://localhost:11434
"""

from __future__ import annotations

import json
import re
import requests
from typing import Any, Dict, Optional, List


class LyricsExplainerLocal:
    def __init__(self, model: str = "qwen2.5:7b", timeout_s: int = 180):
        self.model = model
        self.timeout_s = timeout_s

    def _ollama_generate(self, prompt: str) -> str:
        """
        Stable Ollama call (stream=False).
        """
        r = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.35,
                    "num_predict": 700,  # increase length a bit more
                },
            },
            timeout=self.timeout_s,
        )
        r.raise_for_status()
        data = r.json()
        return (data.get("response") or "").strip()

    def _safe_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Ollama sometimes wraps JSON in extra text.
        Try direct json, else extract first {...} block.
        """
        if not text:
            return None

        # direct parse
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

        # extract JSON object
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None

        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    def summarize_song(self, title: str, artist: str, lyrics: str) -> Optional[str]:
        """
        Returns bullet summary as a string (3-6 bullets).
        """
        if not lyrics or len(lyrics.strip()) < 80:
            return None

        prompt = f"""
You are a music analyst.
Summarize the overall meaning/story of the song using ONLY the lyrics.
Write 3-6 bullet points, plain text (NOT JSON).
Be specific (mention recurring images/ideas from the lyrics).

Song: {title} — {artist}

Lyrics:
{lyrics[:5000]}
"""
        try:
            out = self._ollama_generate(prompt)
            return out.strip() if out else None
        except Exception as e:
            print("❌ Ollama summary error:", e)
            return None

    def explain_section(self, title: str, artist: str, section_label: str, text: str) -> Dict[str, Any]:
        """
        Returns:
        { "meaning": "...", "key_lines": ["...", "...", "..."] }
        """
        if not text or len(text.strip()) < 20:
            return {"meaning": None, "key_lines": []}

        prompt = f"""
You are a music analyst.
Explain THIS section in a helpful, detailed way.

Rules:
- Meaning: 6-10 sentences, specific to these lines (no generic filler).
- Keep it easy to understand.
- Pick 2-4 key lines EXACTLY from the section (copy/paste exact lines).
- Do NOT invent lyrics or facts not present in the text.

Return JSON ONLY:
{{
  "meaning": "6-10 sentences explanation",
  "key_lines": ["line 1", "line 2", "line 3"]
}}

Song: {title} — {artist}
Section: {section_label}

Section lyrics:
{text}
"""
        try:
            out = self._ollama_generate(prompt)
            js = self._safe_json(out)

            if not js:
                # fallback (still show something)
                return {"meaning": out.strip() if out else None, "key_lines": []}

            meaning = js.get("meaning")
            key_lines = js.get("key_lines") or []

            if not isinstance(key_lines, list):
                key_lines = []

            # clean key lines and cap to 4
            key_lines = [str(x).strip() for x in key_lines if str(x).strip()]
            key_lines = key_lines[:4]

            # meaning should be a string
            if meaning is not None:
                meaning = str(meaning).strip()

            return {"meaning": meaning, "key_lines": key_lines}

        except Exception as e:
            print("❌ Ollama section explain error:", e)
            return {"meaning": None, "key_lines": []}

