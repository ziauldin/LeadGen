from app.services.email_generation.personalisation import PersonalisationContext, render_template
from app.services.email_generation.templates import WELLPREDICT_TEMPLATE


def test_wellpredict_template_contains_opt_out_line():
    context = PersonalisationContext(
        first_name="Alex",
        company="Example Foods",
        role="Quality Manager",
        industry="Food Manufacturing",
        pain_point="governance and operational pressure",
        sender_name="Sam Founder",
        sender_company="WellPredict",
        unsubscribe_link="http://localhost:8000/unsubscribe/test-token",
    )
    body = render_template(WELLPREDICT_TEMPLATE.body, context)
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
        sender_company="WellPredict",
        unsubscribe_link="http://localhost:8000/unsubscribe/token",
    )
    subject = render_template(WELLPREDICT_TEMPLATE.subject, context)
    assert subject == "Quick question about Example Foods"
