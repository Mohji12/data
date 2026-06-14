"""Send a test WhatsApp message via Meta Cloud API or /admin/whatsapp/bulk-send.

Usage (direct Meta API — uses backend/.env):
  set TEST_WHATSAPP_TO=919876543210
  python scripts/test_whatsapp_send.py

Usage (via deployed FastAPI admin API):
  set API_BASE=https://krintixsample.site
  set ADMIN_USERNAME=your_techadmin
  set ADMIN_PASSWORD=your_password
  set TEST_WHATSAPP_TO=919876543210
  python scripts/test_whatsapp_send.py --via-api
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib import error, request

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.services.whatsapp import normalize_phone, send_whatsapp_template


def _http_json(method: str, url: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    req = request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return getattr(resp, "status", 200), json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else {"detail": str(exc)}
        except json.JSONDecodeError:
            payload = {"detail": raw or str(exc)}
        return getattr(exc, "code", 500), payload


def send_via_api() -> int:
    base = os.getenv("API_BASE", "https://krintixsample.site").rstrip("/")
    username = os.getenv("ADMIN_USERNAME", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    to_phone = os.getenv("TEST_WHATSAPP_TO", "").strip()
    template_name = os.getenv("WHATSAPP_TEST_TEMPLATE", "hello_world").strip()
    template_language = os.getenv("WHATSAPP_TEST_TEMPLATE_LANG", "en").strip()

    if not username or not password:
        print("FAILED: set ADMIN_USERNAME and ADMIN_PASSWORD for --via-api mode")
        return 1
    if not to_phone:
        print("FAILED: set TEST_WHATSAPP_TO (e.g. 919876543210)")
        return 1

    phone = normalize_phone(to_phone)
    print(f"API base: {base}")
    print(f"Admin login as: {username}")

    status, login = _http_json(
        "POST",
        f"{base}/admin/auth/login",
        {"username": username, "password": password},
    )
    if status != 200 or not login.get("access_token"):
        print(f"Login failed ({status}): {login}")
        return 1

    token = login["access_token"]
    print(f"Logged in as {login.get('username')} ({login.get('user_type')})")

    payload = {
        "send_mode": "template",
        "template_name": template_name,
        "template_language": template_language,
        "template_body_params": [],
        "recipients": [{"user_id": None, "name": "Test", "phone": phone}],
        "dedupe": True,
    }
    status, result = _http_json(
        "POST",
        f"{base}/admin/whatsapp/bulk-send",
        payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    print(f"Bulk send HTTP {status}")
    print(json.dumps(result, indent=2))

    if status == 200 and int(result.get("sent", 0)) >= 1:
        print(f"SUCCESS: WhatsApp test message sent to {phone}")
        return 0
    print("FAILED: message was not sent")
    return 1


def send_direct() -> int:
    settings = get_settings()
    to_phone = os.getenv("TEST_WHATSAPP_TO", "").strip()
    template_name = os.getenv("WHATSAPP_TEST_TEMPLATE", "hello_world").strip()
    template_language = os.getenv("WHATSAPP_TEST_TEMPLATE_LANG", "en").strip()

    if not settings.whatsapp_api_key or not settings.whatsapp_phone_number_id:
        print("FAILED: WHATSAPP_API_KEY and WHATSAPP_PHONE_NUMBER_ID must be set in backend/.env")
        return 1
    if not to_phone:
        print("FAILED: set TEST_WHATSAPP_TO (e.g. 919876543210)")
        return 1

    phone = normalize_phone(to_phone)
    print(f"Phone number ID: {settings.whatsapp_phone_number_id}")
    print(f"Sending template '{template_name}' ({template_language}) to {phone}...")

    result = send_whatsapp_template(phone, template_name, template_language)
    if result.success:
        print(f"SUCCESS: provider_message_id={result.provider_message_id}")
        return 0

    print(f"FAILED ({result.status_code}): {result.error}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Test WhatsApp send")
    parser.add_argument("--via-api", action="store_true", help="Use /admin/whatsapp/bulk-send on API_BASE")
    args = parser.parse_args()
    get_settings.cache_clear()
    return send_via_api() if args.via_api else send_direct()


if __name__ == "__main__":
    raise SystemExit(main())
