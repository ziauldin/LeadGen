from dataclasses import dataclass


@dataclass(frozen=True)
class EmailTemplate:
    id: str
    name: str
    subject: str
    body: str


WELLPREDICT_TEMPLATE = EmailTemplate(
    id="wellpredict",
    name="WellPredict default",
    subject="Quick question about {{company}}",
    body="""Hi {{first_name}},

I came across {{company}} while looking at organisations where {{pain_point}} appear especially important.

I'm building WellPredict, a privacy-first governance evidence platform for regulated organisations. It helps teams turn operating signals, interventions and outcomes into audit-ready evidence without exposing individual employee data.

I thought it may be relevant to your role because the focus is not another wellbeing dashboard, but clearer evidence of what was noticed, what action was taken, and what changed afterwards.

Would it be unreasonable to ask whether this is something worth a brief conversation?

Regards,
{{sender_name}}

If this is not relevant, reply "not relevant" and I will not contact you again.

To opt out of future emails, use this link: {{unsubscribe_link}}""",
)

EMAIL_TEMPLATES: dict[str, EmailTemplate] = {
    WELLPREDICT_TEMPLATE.id: WELLPREDICT_TEMPLATE,
}


def get_template(template_id: str) -> EmailTemplate:
    template = EMAIL_TEMPLATES.get(template_id)
    if template is None:
        raise KeyError(f"Unknown template: {template_id}")
    return template


def list_templates() -> list[EmailTemplate]:
    return list(EMAIL_TEMPLATES.values())
