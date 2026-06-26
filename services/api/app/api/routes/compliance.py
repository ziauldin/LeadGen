from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.compliance.opt_out import process_unsubscribe_for_message

router = APIRouter(tags=["compliance"])


@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe(token: str, db: Session = Depends(get_db)) -> str:
    message = process_unsubscribe_for_message(db, token)
    if message is None:
        raise HTTPException(status_code=404, detail="Invalid unsubscribe link")

    return """
    <!DOCTYPE html>
    <html lang="en">
      <head><title>Unsubscribed</title></head>
      <body>
        <h1>You have been unsubscribed</h1>
        <p>You will not receive further emails from this campaign.</p>
      </body>
    </html>
    """
