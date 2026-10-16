"""SAML 2.0 service provider (SP-initiated, HTTP-Redirect request, HTTP-POST response).

Only the part of the response covered by a valid signature from the configured IdP
certificate is trusted, which defends against XML signature wrapping.
"""

from __future__ import annotations

import base64
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from lxml import etree
from signxml import XMLVerifier
from signxml.exceptions import InvalidInput, InvalidSignature

from app.services.sso.http import SsoError

NS = {
    "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
    "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
}
SUCCESS = "urn:oasis:names:tc:SAML:2.0:status:Success"
CLOCK_SKEW = timedelta(minutes=3)
EMAIL_ATTRIBUTES = (
    "email",
    "mail",
    "emailaddress",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
    "urn:oid:0.9.2342.19200300.100.1.3",
)
NAME_ATTRIBUTES = (
    "name",
    "displayname",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
    "http://schemas.microsoft.com/identity/claims/displayname",
)


@dataclass(frozen=True)
class SamlIdentity:
    subject: str
    email: str
    name: str | None


def _now() -> datetime:
    return datetime.now(UTC)


def authn_request_url(
    *,
    idp_sso_url: str,
    sp_entity_id: str,
    acs_url: str,
    request_id: str,
    relay_state: str,
) -> str:
    issued = _now().strftime("%Y-%m-%dT%H:%M:%SZ")
    xml = (
        f'<samlp:AuthnRequest xmlns:samlp="{NS["samlp"]}" xmlns:saml="{NS["saml"]}" '
        f'ID="{request_id}" Version="2.0" IssueInstant="{issued}" '
        f'Destination="{idp_sso_url}" AssertionConsumerServiceURL="{acs_url}" '
        'ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">'
        f"<saml:Issuer>{sp_entity_id}</saml:Issuer>"
        '<samlp:NameIDPolicy Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress" '
        'AllowCreate="true"/>'
        "</samlp:AuthnRequest>"
    )
    compressor = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -15)
    deflated = compressor.compress(xml.encode()) + compressor.flush()
    query = urlencode(
        {"SAMLRequest": base64.b64encode(deflated).decode(), "RelayState": relay_state}
    )
    separator = "&" if "?" in idp_sso_url else "?"
    return f"{idp_sso_url}{separator}{query}"


def sp_metadata(*, sp_entity_id: str, acs_url: str) -> str:
    return (
        '<?xml version="1.0"?>'
        '<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata" '
        f'entityID="{sp_entity_id}">'
        '<md:SPSSODescriptor AuthnRequestsSigned="false" WantAssertionsSigned="true" '
        'protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">'
        "<md:NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</md:NameIDFormat>"
        '<md:AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST" '
        f'Location="{acs_url}" index="0" isDefault="true"/>'
        "</md:SPSSODescriptor></md:EntityDescriptor>"
    )


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _text(element: etree._Element | None) -> str:
    return (element.text or "").strip() if element is not None else ""


def parse_response(
    saml_response: str,
    *,
    idp_entity_id: str,
    idp_certificate: str,
    sp_entity_id: str,
    acs_url: str,
    expected_request_id: str,
) -> SamlIdentity:
    try:
        raw = base64.b64decode(saml_response, validate=True)
    except ValueError as exc:
        raise SsoError("The sign-in response wasn't valid") from exc
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    try:
        document = etree.fromstring(raw, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise SsoError("The sign-in response wasn't valid XML") from exc

    status = document.find("samlp:Status/samlp:StatusCode", NS)
    if status is not None and status.get("Value") != SUCCESS:
        raise SsoError("Your identity provider refused the sign-in")

    try:
        verified = XMLVerifier().verify(
            raw, x509_cert=idp_certificate, ignore_ambiguous_key_info=True
        )
    except (InvalidSignature, InvalidInput) as exc:
        raise SsoError("The sign-in response's signature couldn't be verified") from exc
    signed = verified.signed_xml if not isinstance(verified, list) else verified[0].signed_xml
    if signed is None:
        raise SsoError("The sign-in response wasn't signed")
    assertion = (
        signed
        if etree.QName(signed).localname == "Assertion"
        else signed.find("saml:Assertion", NS)
    )
    if assertion is None:
        raise SsoError("The signed part of the response has no assertion")

    if _text(assertion.find("saml:Issuer", NS)) != idp_entity_id:
        raise SsoError("The sign-in response came from an unexpected identity provider")

    now = _now()
    conditions = assertion.find("saml:Conditions", NS)
    if conditions is not None:
        not_before = _parse_time(conditions.get("NotBefore"))
        not_after = _parse_time(conditions.get("NotOnOrAfter"))
        if not_before and now + CLOCK_SKEW < not_before:
            raise SsoError("The sign-in response isn't valid yet. Check the server clocks.")
        if not_after and now - CLOCK_SKEW >= not_after:
            raise SsoError("The sign-in response has expired. Please try again.")
        audiences = [_text(a) for a in conditions.iterfind(".//saml:Audience", NS)]
        if audiences and sp_entity_id not in audiences:
            raise SsoError("The sign-in response was meant for a different application")

    confirmation = assertion.find(
        "saml:Subject/saml:SubjectConfirmation/saml:SubjectConfirmationData", NS
    )
    if confirmation is None:
        raise SsoError("The sign-in response is missing subject confirmation")
    if confirmation.get("Recipient") and confirmation.get("Recipient") != acs_url:
        raise SsoError("The sign-in response was sent to the wrong address")
    if confirmation.get("InResponseTo") != expected_request_id:
        raise SsoError("The sign-in response doesn't match a sign-in started here")
    expires = _parse_time(confirmation.get("NotOnOrAfter"))
    if expires and now - CLOCK_SKEW >= expires:
        raise SsoError("The sign-in response has expired. Please try again.")

    subject = _text(assertion.find("saml:Subject/saml:NameID", NS))
    attributes: dict[str, str] = {}
    for attribute in assertion.iterfind(".//saml:Attribute", NS):
        value = _text(attribute.find("saml:AttributeValue", NS))
        if value:
            attributes[(attribute.get("Name") or "").lower()] = value
    email = next((attributes[k] for k in EMAIL_ATTRIBUTES if k in attributes), "")
    if not email and "@" in subject:
        email = subject
    if "@" not in email:
        raise SsoError("Your identity provider didn't share an email address")
    name = next((attributes[k] for k in NAME_ATTRIBUTES if k in attributes), None)
    return SamlIdentity(subject=subject or email, email=email.strip().lower(), name=name)
