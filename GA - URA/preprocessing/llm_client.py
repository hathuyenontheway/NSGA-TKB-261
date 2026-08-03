from __future__ import annotations

import json
from typing import Any

from google import genai


class GeminiClient:
    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        project: str = "",
        location: str = "global",
    ) -> None:
        if not project:
            raise ValueError("Google Cloud project ID is required.")

        self.client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
        )

        self.model = model

        print("Backend: Vertex AI")
        print("Project:", project)
        print("Location:", location)

    def generate_json(
        self,
        prompt: str,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={
                "temperature": 0,
                "response_mime_type": "application/json",
            },
        )

        if not response.text:
            raise ValueError("Gemini returned an empty response.")

        return json.loads(response.text)