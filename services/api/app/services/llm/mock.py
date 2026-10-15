"""Deterministic offline provider for local development and tests.

Tests can queue exact responses (or exceptions) in ``MOCK_LLM_QUEUE``; every call is recorded
in ``MOCK_LLM_CALLS``. Without a queued response it writes a plain email from the ``<facts>``
block, or a neutral classification.
"""

from __future__ import annotations

import json
import re

from app.services.llm.base import LLMResult

MOCK_LLM_QUEUE: list[str | Exception] = []
MOCK_LLM_CALLS: list[dict[str, str]] = []

_FACTS = re.compile(r"<facts>\s*(\{.*?\})\s*</facts>", re.S)


def reset_mock_llm() -> None:
    MOCK_LLM_QUEUE.clear()
    MOCK_LLM_CALLS.clear()


def _default_reply(user: str) -> str:
    if "TASK: classify_reply" in user:
        return json.dumps({"classification": "neutral", "confidence": 0.6})
    facts: dict = {}
    match = _FACTS.search(user)
    if match:
        try:
            facts = json.loads(match.group(1))
        except ValueError:
            facts = {}
    lead = facts.get("lead") or {}
    company = (facts.get("company") or {}).get("name") or "your team"
    first_name = lead.get("first_name") or "there"
    return json.dumps(
        {
            "subject": f"A question for {company}",
            "body": (
                f"Hi {first_name},\n\n"
                f"I noticed {company} and wondered whether a short conversation could be "
                "useful for your team.\n\n"
                "Would you be open to a quick call next week?"
            ),
        },
    )


class MockLLMProvider:
    name = "mock"

    def __init__(self, model: str = "mock-1") -> None:
        self.model = model

    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 600,
        temperature: float = 0.4,
        json_mode: bool = False,
    ) -> LLMResult:
        MOCK_LLM_CALLS.append({"system": system, "user": user})
        if MOCK_LLM_QUEUE:
            queued = MOCK_LLM_QUEUE.pop(0)
            if isinstance(queued, Exception):
                raise queued
            text = queued
        else:
            text = _default_reply(user)
        return LLMResult(
            text=text,
            provider=self.name,
            model=self.model,
            input_tokens=max(1, (len(system) + len(user)) // 4),
            output_tokens=max(1, len(text) // 4),
        )
