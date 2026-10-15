from app.core.config import settings
from app.services.common.csv_safety import safe_cell
from tests.conftest import auth_headers, get_client

HEADER = "full_name,job_title,company,website,linkedin_url,email,source_url,compliance_source_note,niche\n"


def _niche(client, headers):
    client.post(
        "/niches",
        headers=headers,
        json={
            "name": "N",
            "country": "UK",
            "industry": "Legal",
            "target_roles": [],
            "keywords": [],
        },
    )


def _upload(client, headers, body):
    return client.post(
        "/leads/import-csv", headers=headers, files={"file": ("l.csv", body, "text/csv")}
    )


def test_oversized_csv_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "csv_max_bytes", 200)
    client = get_client()
    headers = auth_headers(client)
    _niche(client, headers)
    body = HEADER + ("Jo Bloggs,CEO,Acme,,,,https://s.example,n,N\n" * 20)
    assert _upload(client, headers, body).status_code == 413


def test_row_limit_stops_import(monkeypatch):
    monkeypatch.setattr(settings, "csv_max_rows", 2)
    client = get_client()
    headers = auth_headers(client)
    _niche(client, headers)
    rows = "".join(f"Person {i},CEO,Acme {i},,,,https://s.example,n,N\n" for i in range(5))
    response = _upload(client, headers, HEADER + rows)
    assert response.status_code == 200
    assert response.json()["created"] == 2
    assert any("only the first 2 rows" in error for error in response.json()["errors"])


def test_non_utf8_csv_is_rejected():
    client = get_client()
    headers = auth_headers(client)
    _niche(client, headers)
    assert _upload(client, headers, b"full_name\n\xff\xfe\xfa").status_code == 400


def test_formula_cells_are_neutralised_on_export():
    assert safe_cell("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert safe_cell("+44 20 7946 0000") == "'+44 20 7946 0000"
    assert safe_cell("Jane") == "Jane"
    assert safe_cell(42) == 42

    client = get_client()
    headers = auth_headers(client)
    _niche(client, headers)
    _upload(client, headers, HEADER + "=cmd|calc,CEO,Acme,,,,https://s.example,n,N\n")
    exported = client.get("/leads/export-csv", headers=headers).text
    assert "'=cmd|calc" in exported
