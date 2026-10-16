"""Gmail API and Microsoft Graph clients for connected mailboxes: send and sync new mail."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from app.core.security import encrypt_secret_payload
from app.models.provider_credential import ProviderCredential
from app.services.mailboxes import oauth
from app.services.provider_credentials.service import _as_str, decrypt_provider_config


class MailboxError(Exception):
    def __init__(self, message: str, *, transient: bool = True) -> None:
        super().__init__(message)
        self.transient = transient


class MailboxClient(Protocol):
    def profile_email(self) -> str: ...
    def send_raw(self, raw: bytes) -> str | None: ...
    def fetch_new(self, cursor: str | None) -> tuple[list[bytes], str]: ...


def _check(response: httpx.Response) -> dict[str, Any]:
    if response.status_code == 401:
        raise oauth.MailboxAuthError("The mailbox's access was revoked or expired")
    if response.status_code == 429 or response.status_code >= 500:
        raise MailboxError(f"Provider busy ({response.status_code})", transient=True)
    if response.status_code >= 400:
        try:
            detail = response.json().get("error", {})
            message = detail.get("message") if isinstance(detail, dict) else str(detail)
        except ValueError:
            message = response.text[:200]
        raise MailboxError(message or f"Provider error {response.status_code}", transient=False)
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return {}


class GmailClient:
    BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

    def __init__(self, access_token: str) -> None:
        self.headers = {"Authorization": f"Bearer {access_token}"}

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        with oauth.http_client() as client:
            return _check(client.get(f"{self.BASE}{path}", params=params, headers=self.headers))

    def profile_email(self) -> str:
        return str(self._get("/profile")["emailAddress"]).lower()

    def send_raw(self, raw: bytes) -> str | None:
        body = {"raw": base64.urlsafe_b64encode(raw).decode()}
        with oauth.http_client() as client:
            data = _check(
                client.post(f"{self.BASE}/messages/send", json=body, headers=self.headers)
            )
        return data.get("id")

    def fetch_new(self, cursor: str | None) -> tuple[list[bytes], str]:
        if not cursor:
            # First sync: start from now, don't import the existing inbox.
            return [], str(self._get("/profile")["historyId"])
        ids: list[str] = []
        page: str | None = None
        latest = cursor
        while True:
            params: dict[str, Any] = {
                "startHistoryId": cursor,
                "historyTypes": "messageAdded",
                "labelId": "INBOX",
            }
            if page:
                params["pageToken"] = page
            try:
                data = self._get("/history", params)
            except MailboxError as exc:
                if "404" in str(exc) or "not found" in str(exc).lower():
                    return [], str(self._get("/profile")["historyId"])  # cursor too old: restart
                raise
            latest = str(data.get("historyId", latest))
            for item in data.get("history", []):
                for added in item.get("messagesAdded", []):
                    message_id = added.get("message", {}).get("id")
                    if message_id and message_id not in ids:
                        ids.append(message_id)
            page = data.get("nextPageToken")
            if not page:
                break
        raw = [
            base64.urlsafe_b64decode(self._get(f"/messages/{mid}", {"format": "raw"})["raw"])
            for mid in ids
        ]
        return raw, latest


class GraphClient:
    BASE = "https://graph.microsoft.com/v1.0/me"

    def __init__(self, access_token: str) -> None:
        self.headers = {"Authorization": f"Bearer {access_token}"}

    def profile_email(self) -> str:
        with oauth.http_client() as client:
            data = _check(client.get(self.BASE, headers=self.headers))
        return str(data.get("mail") or data.get("userPrincipalName") or "").lower()

    def send_raw(self, raw: bytes) -> str | None:
        # Graph accepts a base64 MIME message, which keeps our Message-ID and threading headers.
        with oauth.http_client() as client:
            _check(
                client.post(
                    f"{self.BASE}/sendMail",
                    content=base64.b64encode(raw),
                    headers={**self.headers, "Content-Type": "text/plain"},
                )
            )
        return None

    def fetch_new(self, cursor: str | None) -> tuple[list[bytes], str]:
        url = cursor or f"{self.BASE}/mailFolders/inbox/messages/delta?$select=id"
        first_sync = cursor is None
        ids: list[str] = []
        delta_link = cursor or ""
        with oauth.http_client() as client:
            while url:
                data = _check(client.get(url, headers=self.headers))
                ids.extend(item["id"] for item in data.get("value", []) if "@removed" not in item)
                url = str(data.get("@odata.nextLink") or "")
                delta_link = str(data.get("@odata.deltaLink") or delta_link)
            if first_sync:
                return [], delta_link
            raw = []
            for message_id in ids:
                response = client.get(
                    f"{self.BASE}/messages/{message_id}/$value", headers=self.headers
                )
                if response.status_code == 404:
                    continue
                if response.status_code >= 400:
                    _check(response)
                raw.append(response.content)
        return raw, delta_link


def config_of(credential: ProviderCredential) -> dict[str, Any]:
    return decrypt_provider_config(credential)


def save_config(credential: ProviderCredential, config: dict[str, Any]) -> None:
    credential.encrypted_config_json = encrypt_secret_payload(json.dumps(config))


def client_for(credential: ProviderCredential) -> MailboxClient:
    """A client with a valid access token, refreshing (and saving) it when needed."""
    name = _as_str(credential.provider_name)
    config = config_of(credential)
    expires = config.get("expires_at")
    fresh = expires and datetime.fromisoformat(expires) > datetime.now(UTC)
    if not fresh:
        if not config.get("refresh_token"):
            raise oauth.MailboxAuthError("No refresh token: reconnect the mailbox")
        tokens = oauth.refresh(name, config["refresh_token"])
        config["access_token"] = tokens["access_token"]
        config["expires_at"] = oauth.expires_at(tokens)
        if tokens.get("refresh_token"):  # Microsoft rotates refresh tokens
            config["refresh_token"] = tokens["refresh_token"]
        save_config(credential, config)
    token = str(config["access_token"])
    return GmailClient(token) if name == "gmail" else GraphClient(token)


def summary(config: dict[str, Any]) -> str:
    return json.dumps({"email": config.get("from_email")})
