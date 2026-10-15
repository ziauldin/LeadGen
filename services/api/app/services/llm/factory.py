"""Pick the LLM for a workspace and run calls with usage tracking and quotas.

Order: the workspace's own active "llm" credential, then the platform key (counted against the
plan's monthly token quota), otherwise no LLM and callers fall back to templates.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import ProviderType
from app.models.llm_usage import LLMUsage
from app.models.provider_credential import ProviderCredential
from app.models.workspace import Workspace
from app.services.billing.usage import check_quota, record_usage
from app.services.llm.base import LLMError, LLMProvider, LLMResult
from app.services.llm.gemini import GeminiProvider
from app.services.llm.mock import MockLLMProvider
from app.services.llm.openai_compat import OpenAICompatibleProvider
from app.services.llm.pricing import estimate_cost_usd
from app.services.provider_credentials.service import (
    _as_str,
    decrypt_provider_config,
    get_active_credential,
)

logger = logging.getLogger(__name__)

DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "openai": "gpt-4.1-mini",
    "gemini": "gemini-2.5-flash",
    "mock": "mock-1",
}
BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "openai": "https://api.openai.com/v1",
}

KeySource = Literal["workspace", "platform"]


@dataclass
class ResolvedLLM:
    provider: LLMProvider
    key_source: KeySource


def build_provider(name: str, config: dict[str, Any]) -> LLMProvider:
    name = name.lower()
    model = str(config.get("model") or DEFAULT_MODELS.get(name, ""))
    timeout = settings.llm_timeout_seconds
    if name == "mock":
        return MockLLMProvider(model)
    api_key = str(config.get("api_key") or "")
    if not api_key:
        raise LLMError(f"No API key configured for {name}")
    if name in BASE_URLS:
        return OpenAICompatibleProvider(
            name=name,
            base_url=str(config.get("base_url") or BASE_URLS[name]),
            api_key=api_key,
            model=model,
            timeout=timeout,
        )
    if name == "gemini":
        return GeminiProvider(api_key=api_key, model=model, timeout=timeout)
    raise LLMError(f"Unsupported LLM provider: {name}")


def resolve_llm(db: Session, workspace_id: int) -> ResolvedLLM | None:
    credential = get_active_credential(db, workspace_id, ProviderType.LLM)
    if credential is not None:
        try:
            provider = build_provider(
                _as_str(credential.provider_name), decrypt_provider_config(credential)
            )
            return ResolvedLLM(provider, "workspace")
        except LLMError:
            logger.warning("LLM credential %s is unusable; trying the platform key", credential.id)
    if settings.platform_llm_provider:
        try:
            provider = build_provider(
                settings.platform_llm_provider,
                {"api_key": settings.platform_llm_api_key, "model": settings.platform_llm_model},
            )
            return ResolvedLLM(provider, "platform")
        except LLMError:
            logger.warning("Platform LLM is misconfigured")
    return None


def llm_available(db: Session, workspace_id: int) -> bool:
    return resolve_llm(db, workspace_id) is not None


PENDING_USAGE_KEY = "llm_usage_pending"


def _track(db: Session, row: LLMUsage) -> None:
    """Add a usage row and remember it so the draft it produced can be linked later."""
    db.add(row)
    if row.email_message_id is None:
        db.info.setdefault(PENDING_USAGE_KEY, []).append(row)


def take_pending_usage(db: Session) -> list[LLMUsage]:
    return db.info.pop(PENDING_USAGE_KEY, [])


def run_llm(
    db: Session,
    workspace: Workspace,
    *,
    purpose: str,
    system: str,
    user: str,
    max_tokens: int = 600,
    temperature: float = 0.4,
    json_mode: bool = True,
    user_id: int | None = None,
    email_message_id: int | None = None,
    resolved: ResolvedLLM | None = None,
) -> LLMResult:
    """Call the workspace's LLM and record the usage (flushes, does not commit).

    Platform-key calls are checked against, and counted towards, the monthly token quota.
    Calls on a workspace's own key are recorded for visibility but not capped.
    """
    resolved = resolved or resolve_llm(db, workspace.id)
    if resolved is None:
        raise LLMError("No AI provider is configured for this workspace")
    if resolved.key_source == "platform":
        estimate = (len(system) + len(user)) // 4 + max_tokens
        check_quota(db, workspace, "monthly_llm_tokens", estimate)

    provider = resolved.provider
    try:
        result = provider.complete(
            system=system,
            user=user,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=json_mode,
        )
    except LLMError:
        _track(
            db,
            LLMUsage(
                workspace_id=workspace.id,
                user_id=user_id,
                email_message_id=email_message_id,
                purpose=purpose,
                provider=provider.name,
                model=provider.model,
                key_source=resolved.key_source,
                succeeded=False,
            ),
        )
        db.flush()
        raise

    _track(
        db,
        LLMUsage(
            workspace_id=workspace.id,
            user_id=user_id,
            email_message_id=email_message_id,
            purpose=purpose,
            provider=result.provider,
            model=result.model,
            key_source=resolved.key_source,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=estimate_cost_usd(result.model, result.input_tokens, result.output_tokens),
        ),
    )
    if resolved.key_source == "platform":
        record_usage(db, workspace.id, "monthly_llm_tokens", result.total_tokens)
    db.flush()
    return result


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from a model reply, tolerating code fences and surrounding prose."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise LLMError("The AI reply was not valid JSON")
    try:
        value = json.loads(cleaned[start : end + 1])
    except ValueError as exc:
        raise LLMError("The AI reply was not valid JSON") from exc
    if not isinstance(value, dict):
        raise LLMError("The AI reply was not a JSON object")
    return value


def test_llm_credential(credential: ProviderCredential) -> tuple[bool, str]:
    try:
        provider = build_provider(
            _as_str(credential.provider_name), decrypt_provider_config(credential)
        )
        result = provider.complete(
            system='Reply with the JSON object {"ok": true}.',
            user="ping",
            max_tokens=10,
            temperature=0,
            json_mode=True,
        )
    except LLMError as exc:
        return False, str(exc)
    return True, f"Connected to {result.provider} ({result.model})"
