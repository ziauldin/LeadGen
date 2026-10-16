"""HubSpot and Pipedrive API clients behind one small interface.

Only fixed API hosts are called: HubSpot's, and ``<company>.pipedrive.com`` where the company
domain is validated to be a plain subdomain label.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx

from app.core.config import settings

HUBSPOT_API = "https://api.hubapi.com"
HUBSPOT_AUTHORIZE = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_SCOPES = (
    "oauth",
    "crm.objects.contacts.read",
    "crm.objects.contacts.write",
    "crm.objects.deals.read",
    "crm.objects.deals.write",
)
# HubSpot's default pipeline stages for new deals, by local stage kind.
HUBSPOT_STAGE = {"open": "appointmentscheduled", "won": "closedwon", "lost": "closedlost"}
HUBSPOT_DEAL_TO_CONTACT = 3  # HUBSPOT_DEFINED association type id
PIPEDRIVE_DOMAIN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class IntegrationError(Exception):
    def __init__(self, message: str, *, auth: bool = False) -> None:
        super().__init__(message)
        self.auth = auth  # the connection must be reconnected


@dataclass(frozen=True)
class ContactData:
    email: str
    full_name: str
    job_title: str | None = None
    company: str | None = None

    @property
    def first_name(self) -> str:
        return self.full_name.split(" ", 1)[0]

    @property
    def last_name(self) -> str:
        parts = self.full_name.split(" ", 1)
        return parts[1] if len(parts) > 1 else ""


@dataclass(frozen=True)
class DealData:
    title: str
    value: float
    currency: str
    kind: str  # open | won | lost
    close_date: str | None = None


class CrmClient(Protocol):
    def account_label(self) -> str: ...

    def upsert_contact(self, contact: ContactData, remote_id: str | None) -> str: ...

    def upsert_deal(self, deal: DealData, contact_id: str | None, remote_id: str | None) -> str: ...

    def deal_statuses(self, remote_ids: list[str]) -> dict[str, str]: ...


def http_client() -> httpx.Client:
    """Overridden in tests with a mock transport."""
    return httpx.Client(timeout=20.0, headers={"User-Agent": "LeadsGen-Integrations/1.0"})


def _raise_for(response: httpx.Response, what: str) -> None:
    if response.status_code in (401, 403):
        raise IntegrationError(f"{what}: access was refused. Reconnect the account.", auth=True)
    if response.status_code == 429:
        raise IntegrationError(f"{what}: rate limited, will retry later")
    if response.status_code >= 400:
        detail = ""
        try:
            body = response.json()
            detail = str(body.get("message") or body.get("error") or "")[:200]
        except ValueError:
            pass
        raise IntegrationError(f"{what} failed ({response.status_code}) {detail}".strip())


# --- HubSpot ---------------------------------------------------------------------------------


def hubspot_configured() -> bool:
    return bool(settings.hubspot_client_id and settings.hubspot_client_secret)


def hubspot_redirect_uri() -> str:
    return f"{settings.frontend_url.rstrip('/')}/api/integrations/oauth/hubspot/callback"


def hubspot_authorize_url(state: str) -> str:
    params = {
        "client_id": settings.hubspot_client_id,
        "redirect_uri": hubspot_redirect_uri(),
        "scope": " ".join(HUBSPOT_SCOPES),
        "state": state,
    }
    return f"{HUBSPOT_AUTHORIZE}?{urlencode(params)}"


def _hubspot_token(data: dict[str, str]) -> dict[str, Any]:
    with http_client() as client:
        response = client.post(
            f"{HUBSPOT_API}/oauth/v1/token",
            data={
                "client_id": settings.hubspot_client_id,
                "client_secret": settings.hubspot_client_secret,
                **data,
            },
        )
    if response.status_code == 400:
        raise IntegrationError(
            "HubSpot refused the authorization. Reconnect the account.", auth=True
        )
    _raise_for(response, "HubSpot sign-in")
    body = response.json()
    expires = datetime.now(UTC) + timedelta(seconds=max(60, int(body.get("expires_in", 1800)) - 60))
    return {
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token") or data.get("refresh_token", ""),
        "expires_at": expires.isoformat(),
    }


def hubspot_exchange_code(code: str) -> dict[str, Any]:
    return _hubspot_token(
        {"grant_type": "authorization_code", "code": code, "redirect_uri": hubspot_redirect_uri()}
    )


class HubSpotClient:
    def __init__(
        self,
        config: dict[str, Any],
        on_tokens: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.config = dict(config)
        self.on_tokens = on_tokens

    def _token(self) -> str:
        expires = self.config.get("expires_at")
        if not expires or datetime.fromisoformat(expires) <= datetime.now(UTC):
            if not self.config.get("refresh_token"):
                raise IntegrationError("HubSpot needs to be reconnected", auth=True)
            self.config.update(
                _hubspot_token(
                    {"grant_type": "refresh_token", "refresh_token": self.config["refresh_token"]}
                )
            )
            if self.on_tokens:
                self.on_tokens(self.config)
        return str(self.config["access_token"])

    def _request(self, method: str, path: str, what: str, **kwargs: Any) -> dict[str, Any]:
        with http_client() as client:
            response = client.request(
                method,
                f"{HUBSPOT_API}{path}",
                headers={"Authorization": f"Bearer {self._token()}"},
                **kwargs,
            )
        _raise_for(response, what)
        return response.json() if response.content else {}

    def account_label(self) -> str:
        body = self._request("GET", f"/oauth/v1/access-tokens/{self._token()}", "HubSpot account")
        return str(body.get("hub_domain") or body.get("user") or "HubSpot")

    def upsert_contact(self, contact: ContactData, remote_id: str | None) -> str:
        properties = {
            "email": contact.email,
            "firstname": contact.first_name,
            "lastname": contact.last_name,
            "jobtitle": contact.job_title or "",
            "company": contact.company or "",
        }
        if not remote_id:
            found = (
                self._request(
                    "POST",
                    "/crm/v3/objects/contacts/search",
                    "HubSpot contact search",
                    json={
                        "filterGroups": [
                            {
                                "filters": [
                                    {
                                        "propertyName": "email",
                                        "operator": "EQ",
                                        "value": contact.email,
                                    }
                                ]
                            }
                        ],
                        "limit": 1,
                    },
                ).get("results")
                or []
            )
            remote_id = str(found[0]["id"]) if found else None
        if remote_id:
            self._request(
                "PATCH",
                f"/crm/v3/objects/contacts/{remote_id}",
                "HubSpot contact update",
                json={"properties": properties},
            )
            return remote_id
        created = self._request(
            "POST", "/crm/v3/objects/contacts", "HubSpot contact", json={"properties": properties}
        )
        return str(created["id"])

    def upsert_deal(self, deal: DealData, contact_id: str | None, remote_id: str | None) -> str:
        properties: dict[str, Any] = {
            "dealname": deal.title,
            "amount": f"{deal.value:.2f}",
            "deal_currency_code": deal.currency,
        }
        if deal.close_date:
            properties["closedate"] = deal.close_date
        if remote_id:
            # Open deals keep whatever stage they have in HubSpot; closing is pushed.
            if deal.kind != "open":
                properties["dealstage"] = HUBSPOT_STAGE[deal.kind]
            self._request(
                "PATCH",
                f"/crm/v3/objects/deals/{remote_id}",
                "HubSpot deal update",
                json={"properties": properties},
            )
            return remote_id
        body: dict[str, Any] = {
            "properties": {
                **properties,
                "pipeline": "default",
                "dealstage": HUBSPOT_STAGE[deal.kind],
            }
        }
        if contact_id:
            body["associations"] = [
                {
                    "to": {"id": contact_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": HUBSPOT_DEAL_TO_CONTACT,
                        }
                    ],
                }
            ]
        created = self._request("POST", "/crm/v3/objects/deals", "HubSpot deal", json=body)
        return str(created["id"])

    def deal_statuses(self, remote_ids: list[str]) -> dict[str, str]:
        statuses: dict[str, str] = {}
        for start in range(0, len(remote_ids), 100):
            body = self._request(
                "POST",
                "/crm/v3/objects/deals/batch/read",
                "HubSpot deal status",
                json={
                    "properties": ["dealstage", "hs_is_closed", "hs_is_closed_won"],
                    "inputs": [{"id": rid} for rid in remote_ids[start : start + 100]],
                },
            )
            for row in body.get("results") or []:
                props = row.get("properties") or {}
                if str(props.get("hs_is_closed_won")).lower() == "true":
                    status = "won"
                elif str(props.get("hs_is_closed")).lower() == "true":
                    status = "lost"
                else:
                    status = "open"
                statuses[str(row["id"])] = status
        return statuses


# --- Pipedrive -------------------------------------------------------------------------------


def normalize_pipedrive_domain(value: str) -> str:
    domain = value.strip().lower()
    domain = re.sub(r"^https?://", "", domain).split("/", 1)[0]
    domain = domain.removesuffix(".pipedrive.com")
    if not PIPEDRIVE_DOMAIN.fullmatch(domain):
        raise IntegrationError(
            "Enter your Pipedrive company domain, e.g. acme for acme.pipedrive.com"
        )
    return domain


class PipedriveClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self.token = str(config["api_token"])
        self.base = (
            f"https://{normalize_pipedrive_domain(config['company_domain'])}.pipedrive.com/api/v1"
        )

    def _request(self, method: str, path: str, what: str, **kwargs: Any) -> Any:
        with http_client() as client:
            response = client.request(
                method, f"{self.base}{path}", headers={"x-api-token": self.token}, **kwargs
            )
        _raise_for(response, what)
        body = response.json() if response.content else {}
        if isinstance(body, dict) and body.get("success") is False:
            raise IntegrationError(f"{what} failed: {str(body.get('error') or '')[:200]}")
        return body.get("data") if isinstance(body, dict) else None

    def account_label(self) -> str:
        me = self._request("GET", "/users/me", "Pipedrive account") or {}
        return str(me.get("company_name") or me.get("company_domain") or "Pipedrive")

    def upsert_contact(self, contact: ContactData, remote_id: str | None) -> str:
        if not remote_id:
            found = (
                self._request(
                    "GET",
                    "/persons/search",
                    "Pipedrive person search",
                    params={
                        "term": contact.email,
                        "fields": "email",
                        "exact_match": "true",
                        "limit": 1,
                    },
                )
                or {}
            )
            items = found.get("items") or []
            remote_id = str(items[0]["item"]["id"]) if items else None
        payload = {
            "name": contact.full_name,
            "email": [{"value": contact.email, "primary": True, "label": "work"}],
        }
        if remote_id:
            self._request("PUT", f"/persons/{remote_id}", "Pipedrive person update", json=payload)
            return remote_id
        created = self._request("POST", "/persons", "Pipedrive person", json=payload) or {}
        return str(created["id"])

    def upsert_deal(self, deal: DealData, contact_id: str | None, remote_id: str | None) -> str:
        payload: dict[str, Any] = {
            "title": deal.title,
            "value": round(deal.value, 2),
            "currency": deal.currency,
        }
        if deal.close_date:
            payload["expected_close_date"] = deal.close_date
        if remote_id:
            if deal.kind != "open":
                payload["status"] = deal.kind
            self._request("PUT", f"/deals/{remote_id}", "Pipedrive deal update", json=payload)
            return remote_id
        payload["status"] = deal.kind
        if contact_id:
            payload["person_id"] = int(contact_id)
        created = self._request("POST", "/deals", "Pipedrive deal", json=payload) or {}
        return str(created["id"])

    def deal_statuses(self, remote_ids: list[str]) -> dict[str, str]:
        statuses: dict[str, str] = {}
        for remote_id in remote_ids:
            data = self._request("GET", f"/deals/{remote_id}", "Pipedrive deal status") or {}
            status = str(data.get("status") or "open")
            statuses[remote_id] = status if status in ("open", "won", "lost") else "open"
        return statuses
