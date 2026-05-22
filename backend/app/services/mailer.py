from __future__ import annotations

import smtplib
from collections.abc import Sequence
from email.message import EmailMessage

from fastapi import HTTPException

from app.core.config import get_settings


def _normalize_addr_list(value: str | Sequence[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [p.strip() for p in value.split(",") if p.strip()]
    return [str(p).strip() for p in value if str(p).strip()]


def send_html_email(
    to_email: str,
    subject: str,
    html: str,
    *,
    cc: str | Sequence[str] | None = None,
    bcc: str | Sequence[str] | None = None,
    reply_to: str | None = None,
) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        raise HTTPException(status_code=500, detail="SMTP is not configured")

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg["Subject"] = subject
    cc_list = _normalize_addr_list(cc)
    bcc_list = _normalize_addr_list(bcc)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    if bcc_list:
        msg["Bcc"] = ", ".join(bcc_list)
    if reply_to or settings.smtp_reply_to:
        msg["Reply-To"] = (reply_to or settings.smtp_reply_to).strip()
    msg.set_content("This email requires HTML support.")
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)

