from app.models.enums import EmailType
from app.services.enrichment.email_extractor import classify_email, extract_emails_from_html


def test_classify_email_types():
    generic_type, _, _, _ = classify_email("info@acme.co.uk")
    role_type, role_flag, _, _ = classify_email("quality@acme.co.uk")
    named_type, _, personal, _ = classify_email("jane.smith@acme.co.uk")

    assert generic_type == EmailType.GENERIC
    assert role_type == EmailType.ROLE_BASED
    assert role_flag is True
    assert named_type == EmailType.NAMED
    assert personal is True


def test_extract_emails_from_html_deduplicates():
    html = """
    <html>
      <body>
        <a href="mailto:info@acme.co.uk">Email us</a>
        <p>quality@acme.co.uk</p>
        <p>info@acme.co.uk</p>
      </body>
    </html>
    """
    emails = extract_emails_from_html(html, "https://acme.co.uk/contact")
    addresses = {item.email for item in emails}
    assert addresses == {"info@acme.co.uk", "quality@acme.co.uk"}
    assert all(item.source_url == "https://acme.co.uk/contact" for item in emails)
