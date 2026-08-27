"""SMTP settings helpers.

- SMTP credentials are stored in the `app_settings` collection under key
  `smtp_settings`. The password is encrypted at rest with Fernet.
- The encryption key comes from APP_ENCRYPTION_KEY; if that is absent we derive
  a stable 32-byte key from JWT_SECRET so the app still works out of the box.
- send_password_reset_email currently runs as a DRY stub (no network call).
  When real sending is enabled, flip dry_run=False and aiosmtplib does the work.
"""
import os
import base64
import hashlib
import logging
from email.message import EmailMessage

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

SMTP_KEY = "smtp_settings"


def _fernet() -> Fernet:
    key = os.environ.get("APP_ENCRYPTION_KEY")
    if not key:
        # Deterministic fallback derived from JWT_SECRET (never printed/exposed).
        seed = (os.environ.get("JWT_SECRET") or "officeflow").encode()
        key = base64.urlsafe_b64encode(hashlib.sha256(seed).digest()).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except Exception:  # noqa: BLE001
        logger.warning("Failed to decrypt stored SMTP password")
        return ""


async def get_smtp_doc(db) -> dict | None:
    return await db.app_settings.find_one({"key": SMTP_KEY})


async def load_smtp_credentials(db) -> dict | None:
    """Return decrypted SMTP credentials from the DB, or None if not configured."""
    doc = await get_smtp_doc(db)
    if not doc or not doc.get("host") or not doc.get("password_enc"):
        return None
    return {
        "host": doc.get("host"),
        "port": int(doc.get("port") or 587),
        "username": doc.get("username"),
        "password": decrypt_secret(doc.get("password_enc")),
        "from_email": doc.get("from_email"),
    }


async def send_password_reset_email(db, *, recipient: str, reset_link: str, dry_run: bool = True) -> dict:
    """Prepare (and, when enabled, send) a password reset email using the SMTP
    credentials saved in Settings. Returns a status dict; never raises."""
    creds = await load_smtp_credentials(db)
    if not creds:
        logger.info("SMTP not configured — password reset email not sent to %s", recipient)
        return {"sent": False, "reason": "smtp_not_configured"}

    message = EmailMessage()
    message["From"] = creds["from_email"] or creds["username"]
    message["To"] = recipient
    message["Subject"] = "Reset your password"
    message.set_content(
        f"We received a request to reset your password.\n\n"
        f"Use the link below to set a new password (valid for 1 hour):\n{reset_link}\n\n"
        f"If you did not request this, you can safely ignore this email."
    )

    if dry_run:
        logger.info("DRY RUN: reset email prepared for %s via %s:%s (no email sent)",
                    recipient, creds["host"], creds["port"])
        return {"sent": False, "reason": "dry_run", "smtp_host": creds["host"]}

    try:
        import aiosmtplib
        port = creds["port"]
        kwargs = dict(hostname=creds["host"], port=port,
                      username=creds["username"], password=creds["password"], timeout=15)
        if port == 465:
            await aiosmtplib.send(message, use_tls=True, **kwargs)
        else:
            await aiosmtplib.send(message, start_tls=True, **kwargs)
        return {"sent": True, "reason": None}
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to send reset email to %s: %s", recipient, e)
        return {"sent": False, "reason": str(e)}
