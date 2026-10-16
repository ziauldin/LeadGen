"""Public unsubscribe endpoints (no login).

GET only shows a confirmation page: mail security scanners follow links, and a GET that
unsubscribed people would silently opt them out. The form POST and the RFC 8058 one-click POST
(sent by Gmail/Yahoo "Unsubscribe" buttons with ``List-Unsubscribe=One-Click``) perform it.
"""

from html import escape

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.services.compliance.opt_out import (
    find_message_by_unsubscribe_token,
    process_unsubscribe_for_message,
)

router = APIRouter(tags=["compliance"])

_PAGE_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'",
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex",
}
_STYLE = (
    "body{font-family:Arial,Helvetica,sans-serif;max-width:480px;margin:64px auto;padding:0 16px;"
    "color:#1f2933;line-height:1.5}button{background:#1f2933;color:#fff;border:0;border-radius:6px;"
    "padding:10px 18px;font-size:15px;cursor:pointer}"
)


def _page(title: str, body: str, status_code: int = 200) -> HTMLResponse:
    html = (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(title)}</title><style>{_STYLE}</style></head>"
        f"<body><h1>{escape(title)}</h1>{body}</body></html>"
    )
    return HTMLResponse(content=html, status_code=status_code, headers=_PAGE_HEADERS)


def _invalid() -> HTMLResponse:
    return _page(
        "Link not recognised",
        "<p>This unsubscribe link is invalid or no longer active. If you keep receiving "
        "emails, reply to one of them and ask to be removed.</p>",
        status_code=404,
    )


@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
@limiter.limit("60/minute")
def unsubscribe_confirm(
    request: Request, token: str, db: Session = Depends(get_db)
) -> HTMLResponse:
    if find_message_by_unsubscribe_token(db, token) is None:
        return _invalid()
    safe_token = escape(token, quote=True)
    return _page(
        "Unsubscribe",
        "<p>Press the button below and you won't receive further emails from this sender.</p>"
        f'<form method="post" action="/unsubscribe/{safe_token}">'
        '<button type="submit">Unsubscribe</button></form>',
    )


@router.post("/unsubscribe/{token}", response_class=HTMLResponse)
@limiter.limit("60/minute")
def unsubscribe(request: Request, token: str, db: Session = Depends(get_db)) -> HTMLResponse:
    message = process_unsubscribe_for_message(db, token)
    if message is None:
        return _invalid()
    return _page(
        "You have been unsubscribed",
        "<p>You won't receive further emails from this sender. Sorry for the interruption.</p>",
    )
