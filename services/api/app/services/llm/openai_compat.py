"""Chat-completions providers that speak the OpenAI wire format (OpenAI and Groq)."""

from __future__ import annotations

import httpx

from app.services.llm.base import LLMError, LLMResult, error_for_status


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self._base_url = base_url.rstrip("/")
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
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        client = self._client or httpx.Client(timeout=self._timeout)
        try:
            response = client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
        except httpx.TimeoutException as exc:
            raise LLMError(f"{self.name} timed out", transient=True) from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Could not reach {self.name}", transient=True) from exc
        finally:
            if self._client is None:
                client.close()
        if response.status_code >= 400:
            raise error_for_status(self.name, response.status_code)
        try:
            data = response.json()
            text = data["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"{self.name} returned an unexpected response") from exc
        usage = data.get("usage") or {}
        return LLMResult(
            text=text,
            provider=self.name,
            model=str(data.get("model") or self.model),
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
        )
