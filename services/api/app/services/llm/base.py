"""LLM provider interface. Providers return text plus token counts; callers handle the rest."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMResult:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMError(Exception):
    """A provider call failed. ``transient`` errors (rate limits, timeouts, 5xx) may be retried."""

    def __init__(self, message: str, *, transient: bool = False) -> None:
        super().__init__(message)
        self.transient = transient


class LLMProvider(Protocol):
    name: str
    model: str

    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 600,
        temperature: float = 0.4,
        json_mode: bool = False,
    ) -> LLMResult: ...


def error_for_status(provider: str, status_code: int) -> LLMError:
    """Map an HTTP status to an error without echoing the response (it can contain the key)."""
    if status_code == 429 or status_code >= 500:
        return LLMError(f"{provider} is busy or unavailable (HTTP {status_code})", transient=True)
    if status_code in (401, 403):
        return LLMError(f"{provider} rejected the API key (HTTP {status_code})")
    return LLMError(f"{provider} rejected the request (HTTP {status_code})")
