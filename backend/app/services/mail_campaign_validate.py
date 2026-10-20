"""Pre-send audience hygiene: syntax, disposable domains, MX, role warnings."""

from __future__ import annotations

import functools
import re
from pathlib import Path
from typing import Any, Literal

from app.core.config import get_settings

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(normalize_email(email)))

DnsStatus = Literal["ok", "invalid", "unverified"]

ROLE_LOCAL_PARTS = frozenset(
    {
        "noreply",
        "no-reply",
        "no_reply",
        "donotreply",
        "do-not-reply",
        "test",
        "testing",
        "mailer-daemon",
        "postmaster",
        "webmaster",
        "admin",
        "administrator",
        "root",
        "abuse",
        "spam",
    }
)
HIGH_RISK_ROLE_LOCAL_PARTS = frozenset(
    {
        "noreply",
        "no-reply",
        "no_reply",
        "donotreply",
        "do-not-reply",
        "test",
        "testing",
        "mailer-daemon",
        "postmaster",
        "abuse",
        "spam",
    }
)

_DOMAIN_FILE = Path(__file__).resolve().parent.parent / "data" / "disposable_email_domains.txt"


@functools.lru_cache(maxsize=1)
def disposable_domains() -> frozenset[str]:
    if not _DOMAIN_FILE.exists():
        return frozenset()
    out = set()
    for line in _DOMAIN_FILE.read_text(encoding="utf-8").splitlines():
        item = line.strip().lower()
        if item and not item.startswith("#"):
            out.add(item)
    return frozenset(out)


def is_disposable(email: str) -> bool:
    key = normalize_email(email)
    if "@" not in key:
        return False
    domain = key.rsplit("@", 1)[-1]
    return domain in disposable_domains()


def is_role_address(email: str) -> bool:
    key = normalize_email(email)
    if "@" not in key:
        return False
    local = key.split("@", 1)[0]
    return local in ROLE_LOCAL_PARTS


def is_high_risk_role(email: str) -> bool:
    key = normalize_email(email)
    if "@" not in key:
        return False
    local = key.split("@", 1)[0]
    return local in HIGH_RISK_ROLE_LOCAL_PARTS


@functools.lru_cache(maxsize=2048)
def lookup_domain_status(domain: str) -> DnsStatus:
    host = (domain or "").strip().lower().rstrip(".")
    if not host or "." not in host:
        return "invalid"
    timeout = get_settings().mail_dns_timeout_sec
    try:
        import dns.exception
        import dns.resolver
    except Exception:
        return "unverified"
    resolver = dns.resolver.Resolver(configure=True)
    resolver.lifetime = timeout
    resolver.timeout = timeout

    def _has(rrtype: str) -> DnsStatus | None:
        try:
            answers = resolver.resolve(host, rrtype)
            if answers:
                return "ok"
            return None
        except dns.resolver.NXDOMAIN:
            return "invalid"
        except dns.resolver.NoAnswer:
            return None
        except dns.resolver.NoNameservers:
            return "unverified"
        except dns.exception.Timeout:
            return "unverified"
        except Exception:
            return "unverified"

    mx = _has("MX")
    if mx == "ok":
        return "ok"
    if mx == "unverified":
        return "unverified"
    a_rec = _has("A")
    if a_rec == "ok":
        return "ok"
    aaaa = _has("AAAA")
    if aaaa == "ok":
        return "ok"
    if "unverified" in {mx, a_rec, aaaa}:
        return "unverified"
    return "invalid"


def classify_address(email: str, *, check_dns: bool = True) -> dict[str, Any]:
    key = normalize_email(email)
    result: dict[str, Any] = {
        "email": key,
        "syntax_ok": is_valid_email(key),
        "disposable": False,
        "role_warning": False,
        "dns_status": "unverified" if check_dns else "ok",
        "flag": "",
    }
    if not result["syntax_ok"]:
        result["flag"] = "invalid"
        result["dns_status"] = "invalid"
        return result
    result["disposable"] = is_disposable(key)
    result["role_warning"] = is_role_address(key)
    if result["disposable"]:
        result["flag"] = "disposable"
    elif is_high_risk_role(key):
        result["flag"] = "invalid"
    domain = key.rsplit("@", 1)[-1]
    if check_dns:
        result["dns_status"] = lookup_domain_status(domain)
        if result["dns_status"] == "invalid" and result["flag"] not in {"disposable"}:
            result["flag"] = "invalid"
        elif result["dns_status"] == "unverified" and not result["flag"]:
            result["flag"] = "unverified"
    return result


def pre_send_reject_reason(email: str) -> str | None:
    """Never attempt SMTP for addresses that commonly hard-bounce on ZeptoMail."""
    classified = classify_address(email, check_dns=True)
    flag = classified.get("flag") or ""
    if not classified.get("syntax_ok") or flag == "invalid" or classified.get("dns_status") == "invalid":
        return "invalid"
    if classified.get("disposable") or flag == "disposable":
        return "disposable"
    return None
