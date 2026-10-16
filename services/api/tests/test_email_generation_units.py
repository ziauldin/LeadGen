from app.services.email_generation.personalisation import PersonalisationContext, render_template
from app.services.email_generation.templates import SYSTEM_BY_ID, get_template

INTRO = SYSTEM_BY_ID["system:intro"]


def test_system_template_contains_opt_out_line():
    context = PersonalisationContext(
        first_name="Alex",
        company="Example Foods",
        role="Quality Manager",
        industry="Food Manufacturing",
        pain_point="governance and operational pressure",
        sender_name="Sam Founder",
        sender_company="Acme Insights",
        unsubscribe_link="http://localhost:8000/unsubscribe/test-token",
    )
    body = render_template(INTRO.body, context)
    assert "not relevant" in body.lower()
    assert "unsubscribe/test-token" in body


def test_subject_renders_company_variable():
    context = PersonalisationContext(
        first_name="Alex",
        company="Example Foods",
        role="Quality Manager",
        industry="Food Manufacturing",
        pain_point="governance",
        sender_name="Sam",
        sender_company="Acme Insights",
        unsubscribe_link="http://localhost:8000/unsubscribe/token",
    )
    subject = render_template(INTRO.subject, context)
    assert subject == "Quick question about Example Foods"


def test_legacy_template_ids_resolve_to_the_system_template():
    assert get_template("wellpredict") is INTRO
    assert get_template("default") is INTRO
    assert "wellpredict" not in INTRO.body.lower()
