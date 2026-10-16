"""Google Gemini (generateContent REST API). The key goes in a header, never in the URL."""

from __future__ import annotations

import httpx

from app.services.llm.base import LLMError, LLMResult, error_for_status

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._timeout = timeout
        self._client = client

    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 600,
        temperature: float = 0.4,
        json_mode: bool = False,
    ) -> LLMResult:
        generation: dict = {"maxOutputTokens": max_tokens, "temperature": temperature}
        if json_mode:
            generation["responseMimeType"] = "application/json"
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": generation,
        }
        client = self._client or httpx.Client(timeout=self._timeout)
        try:
            response = client.post(
                f"{BASE_URL}/models/{self.model}:generateContent",
                json=payload,
                headers={"x-goog-api-key": self._api_key},
            )
        except httpx.TimeoutException as exc:
            raise LLMError("gemini timed out", transient=True) from exc
        except httpx.HTTPError as exc:
            raise LLMError("Could not reach gemini", transient=True) from exc
        finally:
            if self._client is None:
                client.close()
        if response.status_code >= 400:
            raise error_for_status(self.name, response.status_code)
        try:
            data = response.json()
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(str(part.get("text") or "") for part in parts)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("gemini returned an unexpected response") from exc
        usage = data.get("usageMetadata") or {}
        return LLMResult(
            text=text,
            provider=self.name,
            model=self.model,
            input_tokens=int(usage.get("promptTokenCount") or 0),
            output_tokens=int(usage.get("candidatesTokenCount") or 0),
        )
