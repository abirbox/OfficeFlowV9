"""Email helper backed by Resend (managed if RESEND_API_KEY env is present).
Silently no-ops when the key is missing so payroll creation still succeeds."""
import os
import asyncio
import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def send_email_with_attachment(
    *,
    to: str,
    subject: str,
    html: str,
    attachment_bytes: Optional[bytes] = None,
    attachment_filename: Optional[str] = None,
    attachment_content_type: str = "application/pdf",
) -> dict:
    """Send an email via Resend. Returns {"sent": bool, "id": Optional[str], "reason": Optional[str]}.

    - If RESEND_API_KEY is not set, logs and returns sent=False without raising.
    - Uses asyncio.to_thread so the FastAPI event loop stays non-blocking.
    """
    api_key = os.environ.get("RESEND_API_KEY")
    sender = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
    if not api_key:
        logger.info("Resend disabled (no RESEND_API_KEY). Would send to %s: %s", to, subject)
        return {"sent": False, "id": None, "reason": "no_api_key"}

    try:
        import resend  # local import to avoid cost when disabled
    except ImportError:
        logger.warning("resend package not installed — skipping email")
        return {"sent": False, "id": None, "reason": "package_missing"}

    resend.api_key = api_key
    params: dict = {
        "from": sender,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if attachment_bytes and attachment_filename:
        params["attachments"] = [{
            "filename": attachment_filename,
            "content": base64.b64encode(attachment_bytes).decode("ascii"),
            "content_type": attachment_content_type,
        }]

    try:
        resp = await asyncio.to_thread(resend.Emails.send, params)
        return {"sent": True, "id": (resp or {}).get("id"), "reason": None}
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to send email to %s: %s", to, e)
        return {"sent": False, "id": None, "reason": str(e)}
