import base64
import time
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient
from lxml import etree
from signxml import XMLSigner, methods
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.models.sso import ExternalIdentity, SsoLoginState
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.services.sso import http as sso_http
from app.services.sso import oidc
from tests.conftest import TestingSessionLocal, auth_headers, get_client

XRW = {"X-Requested-With": "fetch"}
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
KEY_PEM = KEY.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
)


def _cert() -> bytes:
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "idp.acme-test.co.uk")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(KEY.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(KEY, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM)


CERT_PEM = _cert()


class FakeIdp:
    """Discovery, JWKS and token endpoints for any issuer, signing with KEY."""

    def __init__(self):
        self.claims: dict = {}
        self.issuers: dict[str, str] = {}

    def get_json(self, url):
        if url.endswith("/.well-known/openid-configuration"):
            issuer = url.removesuffix("/.well-known/openid-configuration")
            stated = (
                "https://login.microsoftonline.com/{tenantid}/v2.0"
                if "microsoftonline" in issuer
                else issuer
            )
            return {
                "issuer": stated,
                "authorization_endpoint": f"{issuer}/authorize",
                "token_endpoint": f"{issuer}/token",
                "jwks_uri": f"{issuer}/jwks",
            }
        if url.endswith("/jwks"):
            jwk = jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key(), as_dict=True)
            return {"keys": [{**jwk, "kid": "k1", "use": "sig", "alg": "RS256"}]}
        raise AssertionError(url)

    def post_form(self, url, data):
        issuer = url.removesuffix("/token")
        now = int(time.time())
        claims = {
            "iss": issuer,
            "aud": data["client_id"],
            "iat": now,
            "exp": now + 300,
            **self.claims,
        }
        token = jwt.encode(claims, KEY_PEM, algorithm="RS256", headers={"kid": "k1"})
        return {"id_token": token, "access_token": "x"}


@pytest.fixture
def idp(monkeypatch):
    fake = FakeIdp()
    monkeypatch.setattr(sso_http, "transport", fake)
    oidc.clear_caches()
    monkeypatch.setattr(settings, "google_oauth_client_id", "google-client")
    monkeypatch.setattr(settings, "google_oauth_client_secret", "google-secret")
    monkeypatch.setattr(settings, "microsoft_oauth_client_id", "ms-client")
    monkeypatch.setattr(settings, "microsoft_oauth_client_secret", "ms-secret")
    return fake


def _api_path(url: str) -> str:
    """Generated URLs go through the web app's /api proxy; the test client talks to the API."""
    parsed = urlparse(url)
    return parsed.path.removeprefix("/api") + (f"?{parsed.query}" if parsed.query else "")


def _state_nonce(state_id: str) -> str:
    db = TestingSessionLocal()
    try:
        return db.get(SsoLoginState, state_id).nonce
    finally:
        db.close()


def _social_login(client, idp, provider, *, sub, email, verified=True, extra=None):
    start = client.get(f"/auth/oidc/{provider}/start?next=/leads", follow_redirects=False)
    assert start.status_code == 303, start.text
    params = parse_qs(urlparse(start.headers["location"]).query)
    state = params["state"][0]
    assert params["code_challenge_method"] == ["S256"]
    idp.claims = {
        "sub": sub,
        "email": email,
        "email_verified": verified,
        "name": "Sam Example",
        "nonce": params["nonce"][0],
        **(extra or {}),
    }
    return client.get(
        f"/auth/oidc/{provider}/callback?code=abc&state={state}", follow_redirects=False
    )


# --- social sign-in ----------------------------------------------------------------------------


def test_google_sign_up_creates_a_verified_account(idp):
    client = get_client()
    assert client.get("/auth/providers").json() == {"google": True, "microsoft": True, "sso": True}
    done = _social_login(client, idp, "google", sub="g-1", email="new@acme-test.co.uk")
    assert done.status_code == 303
    assert done.headers["location"].endswith("/auth/complete?next=%2Fleads")
    token = client.post("/auth/refresh", headers=XRW).json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["email"] == "new@acme-test.co.uk" and me["email_verified_at"]
    workspaces = client.get("/workspaces", headers={"Authorization": f"Bearer {token}"}).json()
    assert len(workspaces["items"]) == 1


def test_callback_rejects_forged_or_replayed_responses(idp):
    client = get_client()
    start = client.get("/auth/oidc/google/start", follow_redirects=False)
    params = parse_qs(urlparse(start.headers["location"]).query)
    state = params["state"][0]

    idp.claims = {
        "sub": "g-2",
        "email": "x@acme-test.co.uk",
        "email_verified": True,
        "nonce": "wrong",
    }
    bad_nonce = client.get(
        f"/auth/oidc/google/callback?code=a&state={state}", follow_redirects=False
    )
    assert "/login?error=" in bad_nonce.headers["location"]

    # The state was used up by that attempt.
    idp.claims["nonce"] = params["nonce"][0]
    replay = client.get(f"/auth/oidc/google/callback?code=a&state={state}", follow_redirects=False)
    assert "expired" in parse_qs(urlparse(replay.headers["location"]).query)["error"][0]

    other_browser = TestClient(app)
    fresh = client.get("/auth/oidc/google/start", follow_redirects=False)
    new_state = parse_qs(urlparse(fresh.headers["location"]).query)["state"][0]
    stolen = other_browser.get(
        f"/auth/oidc/google/callback?code=a&state={new_state}", follow_redirects=False
    )
    assert "browser" in parse_qs(urlparse(stolen.headers["location"]).query)["error"][0]


def test_google_links_existing_verified_account_but_microsoft_does_not(idp):
    client = get_client()
    auth_headers(client, "existing@acme-test.co.uk")
    linked = _social_login(client, idp, "google", sub="g-3", email="existing@acme-test.co.uk")
    assert "/auth/complete" in linked.headers["location"]

    ms = _social_login(
        client,
        idp,
        "microsoft",
        sub="m-1",
        email="existing@acme-test.co.uk",
        extra={"tid": "tenant-1", "iss": "https://login.microsoftonline.com/tenant-1/v2.0"},
    )
    assert "already exists" in parse_qs(urlparse(ms.headers["location"]).query)["error"][0]


def test_signed_in_user_can_link_microsoft(idp, monkeypatch):
    client = get_client()
    headers = auth_headers(client, "linker@acme-test.co.uk")
    url = client.post("/auth/oidc/microsoft/link", headers=headers).json()["url"]
    resume = client.get(_api_path(url), follow_redirects=False)
    params = parse_qs(urlparse(resume.headers["location"]).query)
    idp.claims = {
        "sub": "m-2",
        "email": "different@corp.example",
        "nonce": params["nonce"][0],
        "tid": "tenant-9",
    }
    original_post = idp.post_form

    def post_with_tenant_issuer(endpoint, data):
        result = original_post(endpoint, data)
        claims = jwt.decode(result["id_token"], options={"verify_signature": False})
        claims["iss"] = "https://login.microsoftonline.com/tenant-9/v2.0"
        result["id_token"] = jwt.encode(claims, KEY_PEM, algorithm="RS256", headers={"kid": "k1"})
        return result

    monkeypatch.setattr(idp, "post_form", post_with_tenant_issuer)
    done = client.get(
        f"/auth/oidc/microsoft/callback?code=c&state={params['state'][0]}", follow_redirects=False
    )
    assert done.headers["location"].endswith("/settings/security?linked=microsoft")
    identities = client.get("/auth/identities", headers=headers).json()
    assert [i["provider"] for i in identities] == ["microsoft"]


def test_two_factor_users_are_asked_for_a_code_after_google(idp):
    import pyotp

    client = get_client()
    headers = auth_headers(client, "mfa@acme-test.co.uk")
    setup = client.post("/auth/2fa/setup", headers=headers).json()
    client.post(
        "/auth/2fa/enable", headers=headers, json={"code": pyotp.TOTP(setup["secret"]).now()}
    )
    done = _social_login(client, idp, "google", sub="g-4", email="mfa@acme-test.co.uk")
    assert "/login?mfa_token=" in done.headers["location"]


# --- workspace identity providers ---------------------------------------------------------------


def _upgrade(plan: str, email: str):
    db = TestingSessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        workspace = db.get(Workspace, user.last_workspace_id)
        workspace.plan = plan
        db.commit()
        return workspace.id
    finally:
        db.close()


def _verified_domain(client, headers, monkeypatch, domain="acme-test.co.uk"):
    added = client.post("/sso/domains", headers=headers, json={"domain": domain})
    assert added.status_code == 201, added.text
    record = added.json()
    missing = client.post(f"/sso/domains/{record['id']}/verify", headers=headers)
    monkeypatch.setattr(
        "app.services.deliverability.dns_lookup",
        lambda name, rdtype: [record["txt_record"]] if name == domain else [],
    )
    assert missing.status_code in (400, 200)
    verified = client.post(f"/sso/domains/{record['id']}/verify", headers=headers)
    assert verified.json()["verified"] is True
    return record


def test_domain_rules(monkeypatch):
    client = get_client()
    headers = auth_headers(client, "admin@acme-test.co.uk")
    assert (
        client.post("/sso/domains", headers=headers, json={"domain": "gmail.com"}).status_code
        == 400
    )
    added = client.post("/sso/domains", headers=headers, json={"domain": "acme-test.co.uk"}).json()
    monkeypatch.setattr(
        "app.services.deliverability.dns_lookup", lambda name, rdtype: ["v=spf1 -all"]
    )
    not_yet = client.post(f"/sso/domains/{added['id']}/verify", headers=headers)
    assert not_yet.status_code == 400 and "TXT record" in not_yet.json()["detail"]


def test_free_plan_cannot_add_a_connection():
    client = get_client()
    headers = auth_headers(client, "admin@acme-test.co.uk")
    response = client.post(
        "/sso/connections", headers=headers, json={"protocol": "oidc", "display_name": "Okta"}
    )
    assert response.status_code == 400
    assert "plan" in response.json()["detail"]


def test_enterprise_oidc_provisions_members_and_can_be_enforced(idp, monkeypatch):
    client = get_client()
    owner = auth_headers(client, "owner@acme-test.co.uk")
    workspace_id = _upgrade("pro", "owner@acme-test.co.uk")
    _verified_domain(client, owner, monkeypatch)
    created = client.post(
        "/sso/connections",
        headers=owner,
        json={
            "protocol": "oidc",
            "display_name": "Acme Okta",
            "oidc_issuer": "https://acme.okta-test.example",
            "oidc_client_id": "okta-client",
            "oidc_client_secret": "okta-secret",
            "is_active": True,
        },
    )
    assert created.status_code == 201, created.text
    connection = created.json()
    assert connection["has_client_secret"] is True

    employee = TestClient(app)
    found = employee.post("/auth/sso/discover", json={"email": "jo@acme-test.co.uk"}).json()
    assert found["display_name"] == "Acme Okta"
    start = employee.get(_api_path(found["url"]), follow_redirects=False)
    params = parse_qs(urlparse(start.headers["location"]).query)
    assert params["login_hint"] == ["jo@acme-test.co.uk"]
    idp.claims = {"sub": "okta-jo", "email": "jo@acme-test.co.uk", "nonce": params["nonce"][0]}
    done = employee.get(
        f"/auth/sso/{connection['id']}/callback?code=c&state={params['state'][0]}",
        follow_redirects=False,
    )
    assert "/auth/complete" in done.headers["location"], done.headers["location"]

    db = TestingSessionLocal()
    try:
        jo = db.scalar(select(User).where(User.email == "jo@acme-test.co.uk"))
        member = db.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.user_id == jo.id, WorkspaceMember.workspace_id == workspace_id
            )
        )
        assert member.role == "member"
        assert (
            db.scalar(select(ExternalIdentity.provider).where(ExternalIdentity.user_id == jo.id))
            == f"sso:{connection['id']}"
        )
        jo.hashed_password = __import__("app.core.security", fromlist=["x"]).get_password_hash(
            "jo-password-1"
        )
        db.commit()
    finally:
        db.close()

    client.patch(f"/sso/connections/{connection['id']}", headers=owner, json={"enforce": True})
    blocked = TestClient(app).post(
        "/auth/login", json={"email": "jo@acme-test.co.uk", "password": "jo-password-1"}
    )
    assert blocked.status_code == 401 and blocked.json()["code"] == "sso_required"
    # The owner keeps password access as a break-glass route.
    assert (
        TestClient(app)
        .post("/auth/login", json={"email": "owner@acme-test.co.uk", "password": "testpass12"})
        .status_code
        == 200
    )


# --- SAML ---------------------------------------------------------------------------------------

SAML_NS = "urn:oasis:names:tc:SAML:2.0:assertion"
SAMLP_NS = "urn:oasis:names:tc:SAML:2.0:protocol"


def _saml_response(*, request_id, acs, audience, issuer, email, sign=True) -> str:
    now = datetime.now(UTC)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    later = (now + timedelta(minutes=5)).strftime(fmt)
    xml = f"""<samlp:Response xmlns:samlp="{SAMLP_NS}" xmlns:saml="{SAML_NS}" ID="_r{uuid.uuid4().hex}" Version="2.0" IssueInstant="{now.strftime(fmt)}" Destination="{acs}" InResponseTo="{request_id}">
<saml:Issuer>{issuer}</saml:Issuer>
<samlp:Status><samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/></samlp:Status>
<saml:Assertion ID="_a{uuid.uuid4().hex}" Version="2.0" IssueInstant="{now.strftime(fmt)}">
<saml:Issuer>{issuer}</saml:Issuer>
<saml:Subject><saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">{email}</saml:NameID>
<saml:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer"><saml:SubjectConfirmationData InResponseTo="{request_id}" Recipient="{acs}" NotOnOrAfter="{later}"/></saml:SubjectConfirmation></saml:Subject>
<saml:Conditions NotBefore="{(now - timedelta(minutes=1)).strftime(fmt)}" NotOnOrAfter="{later}"><saml:AudienceRestriction><saml:Audience>{audience}</saml:Audience></saml:AudienceRestriction></saml:Conditions>
<saml:AttributeStatement><saml:Attribute Name="email"><saml:AttributeValue>{email}</saml:AttributeValue></saml:Attribute><saml:Attribute Name="name"><saml:AttributeValue>Robin Saml</saml:AttributeValue></saml:Attribute></saml:AttributeStatement>
</saml:Assertion></samlp:Response>"""
    root = etree.fromstring(xml.encode())
    assertion = root.find(f"{{{SAML_NS}}}Assertion")
    if sign:
        signed = XMLSigner(
            method=methods.enveloped, signature_algorithm="rsa-sha256", digest_algorithm="sha256"
        ).sign(assertion, key=KEY_PEM, cert=CERT_PEM)
        root.replace(assertion, signed)
    return base64.b64encode(etree.tostring(root)).decode()


def _saml_setup(monkeypatch):
    client = get_client()
    owner = auth_headers(client, "owner@acme-test.co.uk")
    _upgrade("enterprise", "owner@acme-test.co.uk")
    _verified_domain(client, owner, monkeypatch)
    connection = client.post(
        "/sso/connections",
        headers=owner,
        json={
            "protocol": "saml",
            "display_name": "Acme Entra",
            "saml_idp_entity_id": "https://sts.acme-test.example/",
            "saml_idp_sso_url": "https://sts.acme-test.example/saml2",
            "saml_idp_certificate": CERT_PEM.decode(),
            "is_active": True,
        },
    )
    assert connection.status_code == 201, connection.text
    return client, connection.json()


def _saml_start(client, connection):
    start = client.get(f"/auth/sso/{connection['id']}/start", follow_redirects=False)
    params = parse_qs(urlparse(start.headers["location"]).query)
    assert "SAMLRequest" in params
    relay = params["RelayState"][0]
    return relay, f"_{_state_nonce(relay)}"


def test_saml_sign_in_works_and_rejects_tampering(monkeypatch):
    client, connection = _saml_setup(monkeypatch)
    metadata = client.get(f"/auth/saml/{connection['id']}/metadata")
    assert connection["acs_url"] in metadata.text

    relay, request_id = _saml_start(client, connection)
    good = _saml_response(
        request_id=request_id,
        acs=connection["acs_url"],
        audience=connection["sp_entity_id"],
        issuer="https://sts.acme-test.example/",
        email="robin@acme-test.co.uk",
    )
    done = client.post(
        f"/auth/saml/{connection['id']}/acs",
        data={"SAMLResponse": good, "RelayState": relay},
        follow_redirects=False,
    )
    assert "/auth/complete" in done.headers["location"], done.headers["location"]

    # Replaying the same response fails (the RelayState was used up).
    replay = client.post(
        f"/auth/saml/{connection['id']}/acs",
        data={"SAMLResponse": good, "RelayState": relay},
        follow_redirects=False,
    )
    assert "/login?error=" in replay.headers["location"]

    # Changing the signed email breaks the signature.
    relay2, request_id2 = _saml_start(client, connection)
    tampered = base64.b64decode(
        _saml_response(
            request_id=request_id2,
            acs=connection["acs_url"],
            audience=connection["sp_entity_id"],
            issuer="https://sts.acme-test.example/",
            email="robin@acme-test.co.uk",
        )
    ).replace(b"robin@acme-test.co.uk</saml:NameID>", b"ceo@acme-test.co.uk</saml:NameID>")
    rejected = client.post(
        f"/auth/saml/{connection['id']}/acs",
        data={"SAMLResponse": base64.b64encode(tampered).decode(), "RelayState": relay2},
        follow_redirects=False,
    )
    assert "signature" in parse_qs(urlparse(rejected.headers["location"]).query)["error"][0]


def test_saml_rejects_wrong_audience_and_unsigned(monkeypatch):
    client, connection = _saml_setup(monkeypatch)
    relay, request_id = _saml_start(client, connection)
    wrong_audience = _saml_response(
        request_id=request_id,
        acs=connection["acs_url"],
        audience="https://some-other-app.example",
        issuer="https://sts.acme-test.example/",
        email="robin@acme-test.co.uk",
    )
    response = client.post(
        f"/auth/saml/{connection['id']}/acs",
        data={"SAMLResponse": wrong_audience, "RelayState": relay},
        follow_redirects=False,
    )
    assert (
        "different application"
        in parse_qs(urlparse(response.headers["location"]).query)["error"][0]
    )

    relay2, request_id2 = _saml_start(client, connection)
    unsigned = _saml_response(
        request_id=request_id2,
        acs=connection["acs_url"],
        audience=connection["sp_entity_id"],
        issuer="https://sts.acme-test.example/",
        email="robin@acme-test.co.uk",
        sign=False,
    )
    response = client.post(
        f"/auth/saml/{connection['id']}/acs",
        data={"SAMLResponse": unsigned, "RelayState": relay2},
        follow_redirects=False,
    )
    assert "/login?error=" in response.headers["location"]
