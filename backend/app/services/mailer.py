from __future__ import annotations

import logging
import smtplib
from collections.abc import Sequence
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_SMTP_TIMEOUT = 30  # seconds


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
        raise RuntimeError("SMTP is not configured (SMTP_HOST is empty)")

    from_addr = (settings.smtp_from or "").strip()
    if not from_addr and "@" in (settings.smtp_username or ""):
        from_addr = settings.smtp_username.strip()
    if not from_addr:
        raise RuntimeError(
            "SMTP_FROM is empty. Set SMTP_FROM to an email address verified in your mail provider "
            "(ZeptoMail: Mail Agents, or SMTP2GO: Verified Senders)."
        )

    msg = EmailMessage()
    msg["From"] = from_addr
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

    logger.debug("Sending email to=%s subject=%r via %s:%s", to_email, subject, settings.smtp_host, settings.smtp_port)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=_SMTP_TIMEOUT) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)
    logger.info("Email sent successfully to=%s subject=%r", to_email, subject)
