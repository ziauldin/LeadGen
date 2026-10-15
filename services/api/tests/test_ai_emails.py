import json

import httpx
import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.email_message import EmailMessage
from app.models.enums import ReplyClassification
from app.models.llm_usage import LLMUsage
from app.models.workspace import Workspace
from app.services.billing.usage import current_usage
from app.services.email_generation.guardrails import check_draft
from app.services.inbound.normalize import InboundEmail
from app.services.inbound.processor import process_inbound_email
from app.services.llm.base import LLMError
from app.services.llm.gemini import GeminiProvider
from app.services.llm.mock import MOCK_LLM_CALLS, MOCK_LLM_QUEUE
from app.services.llm.openai_compat import OpenAICompatibleProvider
from tests.conftest import TestingSessionLocal, auth_headers, get_client
from tests.test_phase6 import _create_lead_with_email

GOOD = json.dumps(
    {
        "subject": "Question for Example Foods",
        "body": "Hi Alex,\n\nI saw Example Foods works in food manufacturing and wondered "
        "whether governance reporting is on your list this year.\n\nWould a short call help?",
    },
)
BAD = json.dumps(
    {
        "subject": "GUARANTEED RESULTS",
        "body": "Hi Alex, we cut costs by 340% for clients. Click here: https://x.io",
    },
)


def _db():
    db = TestingSessionLocal()
    db.info["tenant_bypass"] = True
    return db


def _setup(client, *, ai_mode="assist"):
    headers = auth_headers(client)
    niche_id, lead_id = _create_lead_with_email(client, headers)
    client.patch(
        "/settings",
        headers=headers,
        json={
            "ai_mode": ai_mode,
            "product_description": "Governance reporting for food manufacturers.",
            "tone_guidelines": "Warm, brief, British English.",
        },
    )
    return headers, niche_id, lead_id


def _generate(client, headers, lead_id, **extra):
    return client.post(
        "/emails/generate",
        headers=headers,
        json={"lead_id": lead_id, "mode": "ai", **extra},
    )


# --- guardrails -------------------------------------------------------------------------------


def test_guardrails_accept_a_plain_draft():
    data = json.loads(GOOD)
    assert check_draft(data["subject"], data["body"], facts_text="Example Foods") == []


@pytest.mark.parametrize(
    ("subject", "body", "expected"),
    [
        ("Hi", "Visit https://acme.io today", "URLs"),
        ("Hi", "We saw 47% growth at similar firms", "numbers"),
        ("Hi", "This offer is guaranteed", "phrases"),
        ("Hi", "Hello \U0001f680 friend", "emoji"),
        ("Hi", "Hello [First Name], thanks", "placeholder"),
        ("x" * 90, "Hello", "subject"),
        ("Hi", "word " * 200, "words"),
        ("Hi", "- point one\n- point two", "markdown"),
        ("Hi", "Reply STOP to unsubscribe", "unsubscribe"),
        ("Hi", "See acme-widgets.com for more", "web addresses"),
    ],
)
def test_guardrails_reject(subject, body, expected):
    problems = " ".join(check_draft(subject, body, facts_text="{}")).lower()
    assert expected.lower() in problems


# --- generation -------------------------------------------------------------------------------


def test_ai_draft_is_created_with_footer_and_usage_is_recorded():
    client = get_client()
    headers, _niche, lead_id = _setup(client)
    MOCK_LLM_QUEUE.append(GOOD)

    response = _generate(client, headers, lead_id)
    assert response.status_code == 201, response.text
    message = response.json()["message"]
    assert message["generation_mode"] == "ai"
    assert message["llm_model"] == "mock-1"
    assert message["subject"] == "Question for Example Foods"
    assert "Regards,\nSam Founder" in message["body"]
    assert "unsubscribe/" in message["body"]

    prompt = MOCK_LLM_CALLS[0]
    assert "not instructions" in prompt["system"]
    assert "<facts>" in prompt["user"] and "Example Foods" in prompt["user"]
    assert "Warm, brief, British English." in prompt["user"]

    db = _db()
    try:
        usage = db.scalars(select(LLMUsage)).all()
        assert len(usage) == 1
        assert usage[0].email_message_id == message["id"]
        assert usage[0].key_source == "platform"
        workspace_id = usage[0].workspace_id
        assert current_usage(db, workspace_id, "monthly_llm_tokens") == usage[0].input_tokens + (
            usage[0].output_tokens
        )
    finally:
        db.close()


def test_ai_turned_off_is_a_clear_error():
    client = get_client()
    headers, _niche, lead_id = _setup(client, ai_mode="off")
    response = _generate(client, headers, lead_id)
    assert response.status_code == 400
    assert "turned off" in response.json()["detail"]
    assert MOCK_LLM_CALLS == []


def test_failed_guardrails_retry_once_then_fall_back_to_template():
    client = get_client()
    headers, _niche, lead_id = _setup(client)
    MOCK_LLM_QUEUE.extend([BAD, BAD])

    message = _generate(client, headers, lead_id).json()["message"]
    assert message["generation_mode"] == "template_fallback"
    assert "did not pass the checks" in message["generation_note"]
    assert message["subject"] == "Quick question about Example Foods"
    assert len(MOCK_LLM_CALLS) == 2
    assert "broke these rules" in MOCK_LLM_CALLS[1]["user"]


def test_second_attempt_can_fix_the_draft():
    client = get_client()
    headers, _niche, lead_id = _setup(client)
    MOCK_LLM_QUEUE.extend([BAD, GOOD])
    message = _generate(client, headers, lead_id).json()["message"]
    assert message["generation_mode"] == "ai"
    assert len(MOCK_LLM_CALLS) == 2


def test_provider_errors_and_bad_json_fall_back():
    client = get_client()
    headers, _niche, lead_id = _setup(client)
    MOCK_LLM_QUEUE.append(LLMError("provider rejected the API key"))
    message = _generate(client, headers, lead_id).json()["message"]
    assert message["generation_mode"] == "template_fallback"
    assert "rejected the API key" in message["generation_note"]

    MOCK_LLM_QUEUE.append("sorry, I can't do JSON")
    message = _generate(client, headers, lead_id).json()["message"]
    assert message["generation_mode"] == "template_fallback"
    assert "JSON" in message["generation_note"]


def test_token_quota_falls_back_to_template():
    client = get_client()
    headers, _niche, lead_id = _setup(client)
    db = _db()
    try:
        workspace = db.scalars(select(Workspace)).first()
        workspace.plan_overrides = {"monthly_llm_tokens": 10}
        db.commit()
    finally:
        db.close()
    message = _generate(client, headers, lead_id).json()["message"]
    assert message["generation_mode"] == "template_fallback"
    assert "allowance" in message["generation_note"]
    assert MOCK_LLM_CALLS == []


def test_workspace_key_is_used_and_not_counted_against_quota():
    client = get_client()
    headers, _niche, lead_id = _setup(client)
    credential = client.post(
        "/provider-settings",
        headers=headers,
        json={"provider_type": "llm", "provider_name": "mock", "config": {}},
    )
    assert credential.status_code == 200, credential.text
    credential_id = credential.json()["id"]
    client.patch(f"/provider-settings/{credential_id}/activate", headers=headers)
    tested = client.post(f"/provider-settings/{credential_id}/test", headers=headers)
    assert tested.json()["success"] is True

    MOCK_LLM_QUEUE.append(GOOD)
    _generate(client, headers, lead_id)
    db = _db()
    try:
        usage = db.scalars(select(LLMUsage).where(LLMUsage.purpose == "email_draft")).one()
        assert usage.key_source == "workspace"
        assert current_usage(db, usage.workspace_id, "monthly_llm_tokens") == 0
    finally:
        db.close()


def test_regenerate_a_draft_with_ai_and_reject_after_approval():
    client = get_client()
    headers, _niche, lead_id = _setup(client)
    draft = client.post("/emails/generate", headers=headers, json={"lead_id": lead_id}).json()[
        "message"
    ]
    assert draft["generation_mode"] == "template"

    MOCK_LLM_QUEUE.append(GOOD)
    regenerated = client.post(
        f"/emails/{draft['id']}/regenerate",
        headers=headers,
        json={"mode": "ai", "instructions": "Mention their QA team"},
    )
    assert regenerated.status_code == 200, regenerated.text
    body = regenerated.json()
    assert body["generation_mode"] == "ai"
    assert body["unsubscribe_token"] == draft["unsubscribe_token"]
    assert "Mention their QA team" in MOCK_LLM_CALLS[0]["user"]

    db = _db()
    try:
        assert db.scalar(select(AuditLog).where(AuditLog.action == "email.regenerated"))
    finally:
        db.close()

    client.post("/emails/approve", headers=headers, json={"email_message_id": draft["id"]})
    again = client.post(f"/emails/{draft['id']}/regenerate", headers=headers, json={})
    assert again.status_code == 400


def test_sequence_step_with_use_ai_drafts_with_ai():
    client = get_client()
    headers, niche_id, lead_id = _setup(client)
    campaign_id = client.post(
        "/campaigns",
        headers=headers,
        json={
            "niche_id": niche_id,
            "name": "AI campaign",
            "steps": [
                {
                    "step_number": 1,
                    "template_id": "system:intro",
                    "use_ai": True,
                    "ai_instructions": "Keep it under 80 words",
                },
            ],
        },
    ).json()["id"]
    MOCK_LLM_QUEUE.append(GOOD)
    added = client.post(
        f"/campaigns/{campaign_id}/add-leads",
        headers=headers,
        json={"lead_ids": [lead_id]},
    ).json()
    db = _db()
    try:
        message = db.get(EmailMessage, added["message_ids"][0])
        assert message.generation_mode == "ai"
        assert message.status == "pending_approval" or message.status == "draft"
        assert db.scalar(select(LLMUsage.email_message_id)) == message.id
    finally:
        db.close()
    assert "Keep it under 80 words" in MOCK_LLM_CALLS[0]["user"]


def test_preview_in_ai_mode_reports_generation_details():
    client = get_client()
    headers, _niche, lead_id = _setup(client)
    MOCK_LLM_QUEUE.append(GOOD)
    preview = client.post(
        "/emails/preview",
        headers=headers,
        json={"lead_id": lead_id, "mode": "ai"},
    ).json()
    assert preview["generation_mode"] == "ai"
    assert preview["can_send"] is True


# --- reply classification ---------------------------------------------------------------------


def _workspace_id() -> int:
    db = _db()
    try:
        return db.scalars(select(Workspace.id)).first()
    finally:
        db.close()


def test_llm_labels_replies_the_rules_cannot():
    client = get_client()
    _setup(client)
    MOCK_LLM_QUEUE.append(json.dumps({"classification": "positive", "confidence": 0.82}))
    db = _db()
    try:
        reply = process_inbound_email(
            db,
            _workspace_id(),
            InboundEmail(
                from_email="alex@example-foods.co.uk",
                to=["sam@acme.example"],
                subject="Re: hello",
                text="Who else in our sector do you work with?",
                message_id="ambiguous@x",
            ),
        )
        assert reply.classification == ReplyClassification.POSITIVE
        assert reply.classified_by == "llm"
        assert reply.classification_confidence == pytest.approx(0.82)
    finally:
        db.close()


def test_rules_win_for_opt_outs_and_llm_off_keeps_rules():
    client = get_client()
    _setup(client, ai_mode="off")
    db = _db()
    try:
        reply = process_inbound_email(
            db,
            _workspace_id(),
            InboundEmail(
                from_email="alex@example-foods.co.uk",
                to=["sam@acme.example"],
                subject="Re: hello",
                text="Who else do you work with?",
                message_id="ambiguous-2@x",
            ),
        )
        assert reply.classified_by == "rule"
        assert MOCK_LLM_CALLS == []
    finally:
        db.close()


# --- providers --------------------------------------------------------------------------------


def _transport(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_openai_compatible_provider_parses_and_maps_errors():
    seen = {}

    def ok(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "llama-3.3-70b-versatile",
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3},
            },
        )

    provider = OpenAICompatibleProvider(
        name="groq",
        base_url="https://api.groq.com/openai/v1",
        api_key="gsk_secret",
        model="llama-3.3-70b-versatile",
        client=_transport(ok),
    )
    result = provider.complete(system="s", user="u", json_mode=True)
    assert result.text == '{"ok": true}'
    assert (result.input_tokens, result.output_tokens) == (12, 3)
    assert seen["auth"] == "Bearer gsk_secret"
    assert seen["body"]["response_format"] == {"type": "json_object"}

    for status, transient in ((429, True), (503, True), (401, False)):
        failing = OpenAICompatibleProvider(
            name="openai",
            base_url="https://api.openai.com/v1",
            api_key="sk-secret",
            model="gpt-4.1-mini",
            client=_transport(lambda _r, s=status: httpx.Response(s, text="sk-secret leaked?")),
        )
        with pytest.raises(LLMError) as info:
            failing.complete(system="s", user="u")
        assert info.value.transient is transient
        assert "sk-secret" not in str(info.value)


def test_gemini_sends_key_in_header_not_url():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-goog-api-key")
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "hello"}]}}],
                "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 1},
            },
        )

    provider = GeminiProvider(
        api_key="AIza-secret", model="gemini-2.5-flash", client=_transport(handler)
    )
    result = provider.complete(system="s", user="u")
    assert result.text == "hello"
    assert seen["key"] == "AIza-secret"
    assert "AIza-secret" not in seen["url"]
