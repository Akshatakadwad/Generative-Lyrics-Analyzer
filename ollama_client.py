import requests
import json
from typing import Optional, Dict, Any, List


class OllamaClient:
    def __init__(self, model: str = "qwen2.5:7b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.3) -> str:
        """
        Uses Ollama /api/chat (best for multi-turn + structured responses).
        """
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature}
        }
        r = requests.post(url, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        return data["message"]["content"].strip()

    def generate(self, prompt: str, temperature: float = 0.3) -> str:
        """
        Uses Ollama /api/generate (simple single prompt).
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature}
        }
        r = requests.post(url, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        return data["response"].strip()

