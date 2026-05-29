#!/usr/bin/env python3
"""One-off SMTP test — send to a given address using backend .env settings."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.config import get_settings
from app.services.mailer import send_html_email


def main() -> int:
    to = (sys.argv[1] if len(sys.argv) > 1 else "mohangola47@gmail.com").strip()
    settings = get_settings()
    html = f"""<html><body style="font-family:Arial,sans-serif;padding:20px">
<h2>Harish Critical Care Classes — SMTP test</h2>
<p>This is a test email from the FastAPI backend.</p>
<p>If you received this, registration and document-approval emails should work for users.</p>
<p style="color:#666;font-size:12px">From: {settings.smtp_from or 'n/a'}</p>
</body></html>"""
    send_html_email(
        to,
        "Test email — Harish Critical Care Classes",
        html,
        cc=settings.smtp_cc or None,
    )
    print(f"OK: test email sent to {to}")
    if settings.smtp_cc:
        print(f"CC: {settings.smtp_cc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
