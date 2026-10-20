"""Render and sanitize campaign HTML; wrap links for click tracking."""

from __future__ import annotations

import json
import re
from html import escape
from typing import Any
from urllib.parse import quote, urlencode, urlparse

import bleach

from app.core.config import get_settings
from app.services.uploads import campaign_image_public_url, load_campaign_hero_bytes

HERO_CID = "campaign-hero"

_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
_HREF_RE = re.compile(r"""href\s*=\s*(['"])(https?://[^'"]+)\1""", re.I)

ALLOWED_TAGS = [
    "p",
    "br",
    "a",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "img",
    "span",
    "div",
]
ALLOWED_ATTRS = {
    "a": ["href", "title", "target"],
    "img": ["src", "alt", "width", "height"],
}


def parse_cta_list(raw: str | None) -> list[dict[str, str]]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        url = str(item.get("url") or "").strip()
        if label and url:
            out.append({"label": label, "url": url})
    return out


def substitute_vars(text: str, values: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1).lower()
        return values.get(key, "")

    return _VAR_RE.sub(repl, text or "")


def sanitize_html(html: str) -> str:
    return bleach.clean(
        html or "",
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=["http", "https", "mailto"],
        strip=True,
    )


def _public_base() -> str:
    return (get_settings().api_public_base_url or "").strip().rstrip("/")


def tracking_click_url(token: str, dest: str) -> str:
    base = _public_base() or "http://127.0.0.1:8000"
    qs = urlencode({"u": dest})
    return f"{base}/mail/t/{quote(token)}?{qs}"


def unsubscribe_url(token: str) -> str:
    base = _public_base() or "http://127.0.0.1:8000"
    return f"{base}/mail/u/{quote(token)}"


def wrap_links_for_tracking(html: str, token: str | None) -> str:
    if not token:
        return html

    def repl(match: re.Match[str]) -> str:
        quote_ch = match.group(1)
        dest = match.group(2)
        if "/mail/t/" in dest or "/mail/u/" in dest:
            return match.group(0)
        tracked = tracking_click_url(token, dest)
        return f"href={quote_ch}{escape(tracked, quote=True)}{quote_ch}"

    return _HREF_RE.sub(repl, html)


def render_campaign_html(
    *,
    subject: str,
    preview_text: str,
    hero_image: str,
    body_html: str,
    footer_html: str,
    cta: list[dict[str, str]],
    values: dict[str, str],
    tracking_token: str | None = None,
    embed_hero: bool = False,
) -> tuple[str, str]:
    vals = {
        "name": values.get("name") or "Doctor",
        "email": values.get("email") or "",
        "batch": values.get("batch") or "",
    }
    subj = substitute_vars(subject or "", vals)
    preview = substitute_vars(preview_text or "", vals)
    body = sanitize_html(substitute_vars(body_html or "", vals))
    footer = sanitize_html(substitute_vars(footer_html or "", vals))
    if tracking_token:
        body = wrap_links_for_tracking(body, tracking_token)
        footer = wrap_links_for_tracking(footer, tracking_token)

    hero_src = ""
    if (hero_image or "").strip():
        raw = hero_image.strip()
        if embed_hero:
            hero_src = f"cid:{HERO_CID}"
        elif raw.lower().startswith("http://") or raw.lower().startswith("https://"):
            hero_src = raw
        else:
            hero_src = campaign_image_public_url(raw)

    cta_html_parts: list[str] = []
    for item in cta:
        url = substitute_vars(item["url"], vals)
        label = escape(substitute_vars(item["label"], vals))
        if tracking_token and dest_url_is_allowed(url):
            href = tracking_click_url(tracking_token, url)
        else:
            href = url
        cta_html_parts.append(
            f'<a href="{escape(href, quote=True)}" style="display:inline-block;background:#24628d;color:#ffffff;'
            f'text-decoration:none;padding:12px 20px;border-radius:4px;font-weight:600;margin:6px 8px 6px 0;">{label}</a>'
        )
    cta_block = "".join(cta_html_parts)

    unsub = ""
    if tracking_token:
        u = unsubscribe_url(tracking_token)
        unsub = (
            f'<p style="font-size:12px;color:#6b7280;margin-top:24px;">'
            f'<a href="{escape(u, quote=True)}" style="color:#6b7280;">Unsubscribe</a></p>'
        )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{escape(subj)}</title></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{escape(preview)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;max-width:600px;width:100%;">
<tr><td style="padding:0;">
{"<img src='" + escape(hero_src, quote=True) + "' alt='' width='600' style='display:block;width:100%;max-width:600px;height:auto;border:0;' />" if hero_src else ""}
</td></tr>
<tr><td style="padding:28px 28px 8px;color:#1a2332;font-size:15px;line-height:1.6;">
{body}
</td></tr>
<tr><td style="padding:8px 28px 16px;">{cta_block}</td></tr>
<tr><td style="padding:8px 28px 28px;color:#4b5563;font-size:13px;line-height:1.5;">
{footer}
{unsub}
</td></tr>
</table>
</td></tr>
</table>
</body></html>"""
    return subj, html


def render_campaign_email(
    *,
    subject: str,
    preview_text: str,
    hero_image: str,
    body_html: str,
    footer_html: str,
    cta: list[dict[str, str]],
    values: dict[str, str],
    tracking_token: str | None = None,
) -> tuple[str, str, list[tuple[bytes, str, str]]]:
    """Render HTML and attach a local hero image as an inline CID part when present."""
    from pathlib import Path as _Path

    raw = (hero_image or "").strip()
    loaded = load_campaign_hero_bytes(_Path(raw).name if raw else "")
    subj, html = render_campaign_html(
        subject=subject,
        preview_text=preview_text,
        hero_image=hero_image,
        body_html=body_html,
        footer_html=footer_html,
        cta=cta,
        values=values,
        tracking_token=tracking_token,
        embed_hero=loaded is not None,
    )
    inline: list[tuple[bytes, str, str]] = []
    if loaded is not None:
        content, subtype = loaded
        inline.append((content, subtype, HERO_CID))
    return subj, html, inline


def dest_url_is_allowed(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
