from __future__ import annotations

import json
from typing import Any

import requests


class OllamaClient:
    def __init__(
        self,
        model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
        timeout: int = 120,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate_json(
        self,
        prompt: str,
    ) -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0,
                },
            },
            timeout=self.timeout,
        )

        response.raise_for_status()

        payload = response.json()
        raw_output = payload.get("response", "")

        try:
            result = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"LLM returned invalid JSON: {raw_output!r}"
            ) from exc

        if not isinstance(result, dict):
            raise ValueError(
                f"LLM output must be a JSON object: {result!r}"
            )

        return result