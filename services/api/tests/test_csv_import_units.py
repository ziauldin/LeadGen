import csv
import io

from app.services.leads.csv_import import CSV_IMPORT_COLUMNS, import_leads_from_csv
from tests.conftest import TestingSessionLocal, auth_headers, get_client


def test_csv_import_parses_rows_and_creates_lead():
    client = get_client()
    headers = auth_headers(client)

    niche_id = client.post(
        "/niches",
        headers=headers,
        json={
            "name": "CSV Import Niche",
            "country": "UK",
            "industry": "Food Manufacturing",
            "target_roles": ["Quality Manager"],
            "keywords": ["governance"],
            "exclusion_keywords": [],
        },
    ).json()["id"]

    csv_content = (
        "full_name,job_title,company,website,linkedin_url,email,source_url,"
        "compliance_source_note,niche\n"
        "CSV Lead,Quality Manager,CSV Foods,https://csvfoods.co.uk,,"
        "lead@csvfoods.co.uk,https://example.com/listing,Public listing,CSV Import Niche\n"
    )

    result = client.post(
        "/leads/import-csv",
        headers=headers,
        files={"file": ("leads.csv", csv_content, "text/csv")},
    )
    assert result.status_code == 200
    payload = result.json()
    assert payload["created"] == 1
    assert payload["errors"] == []

    leads = client.get(f"/leads?niche_id={niche_id}", headers=headers).json()
    assert leads["items"][0]["full_name"] == "CSV Lead"
    assert leads["items"][0]["primary_email"] == "lead@csvfoods.co.uk"


def test_csv_import_reports_unknown_niche():
    db = TestingSessionLocal()
    try:
        from app.models.user import User

        user = User(
            name="CSV User",
            email="csv-user@example.com",
            hashed_password="hash",
        )
        db.add(user)
        db.commit()

        csv_content = io.StringIO()
        writer = csv.DictWriter(csv_content, fieldnames=CSV_IMPORT_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "full_name": "Bad Niche Lead",
                "job_title": "Manager",
                "company": "Acme",
                "website": "https://acme.example",
                "linkedin_url": "",
                "email": "a@acme.example",
                "source_url": "https://example.com",
                "compliance_source_note": "note",
                "niche": "Does Not Exist",
            },
        )

        result = import_leads_from_csv(db, user, csv_content.getvalue())
        assert result.created == 0
        assert any("niche" in err.lower() for err in result.errors)
    finally:
        db.rollback()
        db.close()
