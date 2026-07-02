from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models import Country, Option, Package, User, UserPackagePayment, UserSubscription
from app.services.registration import (
    BATCH_COURSE_MONTHS_DEFAULT,
    _add_months,
    _to_display_usd,
    course_end_from_batch_start,
)


def _csv_tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def get_option_value(db: Session, option_name: str) -> str:
    row = db.query(Option).filter(Option.option_name == option_name).first()
    return (row.option_value or "").strip() if row else ""


def subscription_allowed(option_value: str, subscription: str | None) -> bool:
    allowed = _csv_tokens(option_value)
    if not allowed:
        return False
    if "all" in allowed or "*" in allowed:
        return True
    sub = (subscription or "").strip().lower()
    return bool(sub and sub in allowed)


def bool_option(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def batch_slug(batch_name: str | None) -> str:
    raw = (batch_name or "").strip().lower()
    if not raw:
        return ""
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return slug


def subscription_batch_keys(batch_name: str | None) -> set[str]:
    """Match user.subscription to user_subscriptions.batch_slug (hyphen vs space variants)."""
    raw = (batch_name or "").strip()
    if not raw:
        return set()
    lowered = raw.lower()
    hyphen = batch_slug(raw)
    keys = {lowered, hyphen, lowered.replace(" ", "-"), lowered.replace("-", " ")}
    # Canonical aliases for noisy labels like "Batch 15 - master classes ..."
    m = re.search(r"\bbatch\s*[- ]*(\d+)\b", lowered)
    if m:
        n = m.group(1)
        keys.update({f"batch {n}", f"batch-{n}"})
    return {k for k in keys if k}


def find_active_user_subscription(db: Session, user: User) -> UserSubscription | None:
    keys = subscription_batch_keys(user.subscription)
    q = (
        db.query(UserSubscription)
        .filter(
            UserSubscription.user_id == user.id,
            UserSubscription.status == "active",
        )
        .order_by(UserSubscription.end_at.desc())
    )
    if keys:
        rows = q.all()
        for row in rows:
            if (row.batch_slug or "").strip().lower() in keys:
                return row
    return q.first()


def certificate_option_key(kind: str, batch_name: str | None) -> str:
    slug = batch_slug(batch_name)
    if not slug:
        return ""
    return f"certificate_{kind}::{slug}"


def extension_option_key(kind: str, batch_name: str | None) -> str:
    slug = batch_slug(batch_name)
    if not slug:
        return ""
    return f"extension_{kind}::{slug}"


def get_certificate_batch_settings(db: Session, batch_name: str | None) -> dict[str, str]:
    enabled_key = certificate_option_key("enabled", batch_name)
    label_key = certificate_option_key("batch_label", batch_name)
    date_key = certificate_option_key("fixed_date", batch_name)
    course_key = certificate_option_key("course_line", batch_name)
    program_key = certificate_option_key("program_line", batch_name)
    show_date_key = certificate_option_key("show_date", batch_name)
    name_size_key = certificate_option_key("name_size", batch_name)
    return {
        "enabled": get_option_value(db, enabled_key) if enabled_key else "",
        "batch_label": get_option_value(db, label_key) if label_key else "",
        "fixed_date": get_option_value(db, date_key) if date_key else "",
        "course_line": get_option_value(db, course_key) if course_key else "",
        "program_line": get_option_value(db, program_key) if program_key else "",
        "show_date": get_option_value(db, show_date_key) if show_date_key else "",
        "name_size": get_option_value(db, name_size_key) if name_size_key else "",
    }


def get_extension_batch_settings(db: Session, batch_name: str | None) -> dict[str, str]:
    slug_candidates: list[str] = []
    raw_slug = batch_slug(batch_name)
    if raw_slug:
        slug_candidates.append(raw_slug)
    for key in subscription_batch_keys(batch_name):
        s = batch_slug(key)
        if s and s not in slug_candidates:
            slug_candidates.append(s)

    fallback = {
        "enabled": "",
        "gross_amount": "",
        "gst_percentage": "",
        "gst_amount": "",
        "total_amount": "",
        "months": "",
        "start_date": "",
        "end_date": "",
        "base_date": "",
    }
    for slug in slug_candidates:
        out = {
            "enabled": get_option_value(db, f"extension_enabled::{slug}"),
            "gross_amount": get_option_value(db, f"extension_gross_amount::{slug}"),
            "gst_percentage": get_option_value(db, f"extension_gst_percentage::{slug}"),
            "gst_amount": get_option_value(db, f"extension_gst_amount::{slug}"),
            "total_amount": get_option_value(db, f"extension_total_amount::{slug}"),
            "months": get_option_value(db, f"extension_months::{slug}"),
            "start_date": get_option_value(db, f"extension_start_date::{slug}"),
            "end_date": get_option_value(db, f"extension_end_date::{slug}"),
            "base_date": get_option_value(db, f"extension_base_date::{slug}"),
        }
        if any((v or "").strip() for v in out.values()):
            return out
        fallback = out
    return fallback


def parse_iso_date(value: str | None) -> date | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        return None


def _user_has_extension_payment(db: Session, user: User) -> bool:
    user_keys = subscription_batch_keys(user.subscription)
    rows = (
        db.query(UserPackagePayment.subscription)
        .filter(
            UserPackagePayment.user_id == user.id,
            UserPackagePayment.payment_status == "Credit",
            UserPackagePayment.package_type.ilike("Topup Extension%"),
        )
        .all()
    )
    if not rows:
        return False
    if not user_keys:
        return True
    for (paid_sub,) in rows:
        paid_keys = subscription_batch_keys(paid_sub)
        if not paid_keys or (paid_keys & user_keys):
            return True
    return False


def _latest_user_subscription(db: Session, user: User) -> UserSubscription | None:
    keys = subscription_batch_keys(user.subscription)
    q = (
        db.query(UserSubscription)
        .filter(UserSubscription.user_id == user.id, UserSubscription.status == "active")
        .order_by(UserSubscription.end_at.desc())
    )
    if keys:
        for row in q.all():
            if (row.batch_slug or "").strip().lower() in keys:
                return row
    return q.first()


def _extension_batch_end_at(
    manual: dict[str, str],
    active_sub: UserSubscription | None,
) -> datetime | None:
    base_date = parse_iso_date(manual.get("base_date"))
    if base_date:
        return datetime.combine(base_date, datetime.max.time()).replace(microsecond=0)
    if active_sub and active_sub.end_at:
        return active_sub.end_at
    return None


def _format_extension_headline(
    batch_name: str,
    batch_end: datetime | None,
    extended_end: datetime | None,
    months: int,
    gross: float,
    total: float,
) -> str:
    def fmt(dt: datetime | None) -> str:
        if not dt:
            return ""
        d = dt.date()
        suffix = "th"
        if d.day in {1, 21, 31}:
            suffix = "st"
        elif d.day in {2, 22}:
            suffix = "nd"
        elif d.day in {3, 23}:
            suffix = "rd"
        month = d.strftime("%B")
        return f"{d.day}{suffix} {month} {d.year}"

    end_label = fmt(batch_end)
    ext_label = fmt(extended_end)
    gross_txt = f"Rs {int(gross):,}" if gross else ""
    total_txt = f"Rs {int(total):,}" if total else ""
    price = f"{gross_txt} plus GST ({total_txt})" if gross_txt and total_txt else total_txt
    label = (batch_name or "Your batch").strip()
    if end_label and ext_label:
        return (
            f"{label} officially ends on {end_label}; click here to continue your access "
            f"{months} more months (until {ext_label}). {price}."
        )
    return f"Extend your access by {months} months. {price}.".strip()


def has_active_subscription(db: Session, user: User, batch_name: str | None = None) -> bool:
    if not user:
        return False
    now = datetime.utcnow()
    if batch_name:
        keys = subscription_batch_keys(batch_name)
        row = (
            db.query(UserSubscription)
            .filter(
                UserSubscription.user_id == user.id,
                UserSubscription.status == "active",
                UserSubscription.start_at <= now,
                UserSubscription.end_at >= now,
            )
            .order_by(UserSubscription.end_at.desc())
            .all()
        )
        for sub in row:
            if (sub.batch_slug or "").strip().lower() in keys:
                return True
        return False
    active = find_active_user_subscription(db, user)
    if not active:
        return False
    return active.start_at <= now <= active.end_at


def _one_time_course_end_date(pkg: Package | None) -> date | None:
    """CCM-style one-time batches: access until batch_start_date + 6 months when batch_start is set."""
    if not pkg:
        return None
    if (pkg.plan_type or "one_time").strip().lower() == "subscription":
        return None
    start = _coerce_date(pkg.batch_start_date)
    if start:
        return course_end_from_batch_start(start, BATCH_COURSE_MONTHS_DEFAULT)
    return _coerce_date(pkg.end_date)


def _one_time_course_start_date(pkg: Package | None) -> date | None:
    if not pkg:
        return None
    if (pkg.plan_type or "one_time").strip().lower() == "subscription":
        return None
    return _coerce_date(pkg.batch_start_date)


def ensure_one_time_batch_access(db: Session, user: User) -> tuple[bool, str | None]:
    # Paid extension creates user_subscriptions — that window overrides one-time package dates.
    if has_active_subscription(db, user, user.subscription):
        return True, None
    if not user.package_id:
        return True, None
    pkg = db.query(Package).filter(Package.id == user.package_id).first()
    start = _one_time_course_start_date(pkg)
    end = _one_time_course_end_date(pkg)
    if not end:
        return True, None
    today = date.today()
    if start and today < start:
        return False, f"Your batch access starts on {start.strftime('%d %b %Y')}."
    if today > end:
        return False, "Your batch access period has ended."
    return True, None


def ensure_subscription_entitlement(db: Session, user: User, batch_name: str | None = None) -> tuple[bool, str | None]:
    # Backward compatibility: only enforce when user has subscription rows for this batch.
    sub_name = (batch_name or user.subscription or "").strip()
    if not sub_name:
        return False, "No subscription assigned."
    keys = subscription_batch_keys(sub_name)
    rows = (
        db.query(UserSubscription.batch_slug)
        .filter(UserSubscription.user_id == user.id)
        .all()
    )
    if not rows:
        return True, None
    if keys and not any((slug or "").strip().lower() in keys for (slug,) in rows):
        return True, None
    if not has_active_subscription(db, user, sub_name):
        return False, "Your subscription plan has expired."
    return True, None


def is_certificate_only_user(db: Session, user: User) -> bool:
    """Users who may log in only to download their completion certificate."""
    return subscription_allowed(
        get_option_value(db, "certificate_only_access"),
        user.subscription,
    )


def can_access_certificate(db: Session, user: User) -> tuple[bool, str | None]:
    if not bool_option(get_option_value(db, "display_download_certificate")):
        return False, "Certificate download is disabled by admin."
    allowed = get_option_value(db, "access_download_certificate")
    if allowed and not subscription_allowed(allowed, user.subscription):
        return False, "Your subscription does not include certificate download."
    batch_settings = get_certificate_batch_settings(db, user.subscription)
    if (batch_settings.get("enabled") or "").strip() != "1":
        return False, "Certificate download is disabled for your batch."
    if (user.payment_status or "").strip().lower() != "credit":
        return False, "Payment not completed."
    if (user.approve or "").strip() != "1":
        return False, "Account not approved."
    if is_certificate_only_user(db, user):
        return True, None
    ent_ok, ent_reason = ensure_subscription_entitlement(db, user)
    if not ent_ok:
        return False, ent_reason
    return True, None


def can_access_video_library(db: Session, user: User) -> tuple[bool, str | None]:
    if is_certificate_only_user(db, user):
        return False, "Your account is limited to certificate download only."
    if (user.payment_status or "").strip().lower() != "credit":
        return False, "Payment not completed."
    approve = (user.approve or "").strip()
    if approve not in {"1"}:
        return False, "Account not approved."

    display_video = bool_option(get_option_value(db, "display_video_library_link"))
    if not display_video:
        return False, "Video library disabled by admin option."

    allowed_subscriptions = get_option_value(db, "access_video_library_link")
    if allowed_subscriptions and not subscription_allowed(
        allowed_subscriptions, user.subscription
    ):
        return False, "Your subscription does not include video library."

    ent_ok, ent_reason = ensure_subscription_entitlement(db, user)
    if not ent_ok:
        return False, ent_reason
    batch_ok, batch_reason = ensure_one_time_batch_access(db, user)
    if not batch_ok:
        return False, batch_reason

    return True, None


def can_access_mock_test(db: Session, user: User) -> tuple[bool, str | None]:
    if is_certificate_only_user(db, user):
        return False, "Your account is limited to certificate download only."
    if (user.payment_status or "").strip().lower() != "credit":
        return False, "Payment not completed."
    if (user.approve or "").strip() != "1":
        return False, "Account not approved."
    allowed_subscriptions = get_option_value(db, "access_quiz_link")
    if allowed_subscriptions and not subscription_allowed(allowed_subscriptions, user.subscription):
        return False, "Your subscription does not include mock tests."
    ent_ok, ent_reason = ensure_subscription_entitlement(db, user)
    if not ent_ok:
        return False, ent_reason
    batch_ok, batch_reason = ensure_one_time_batch_access(db, user)
    if not batch_ok:
        return False, batch_reason
    return True, None


def get_subscription_period_for_profile(db: Session, user: User) -> dict | None:
    """Subscription window for profile UI; None when plan is not time-bound."""
    pkg = db.query(Package).filter(Package.id == user.package_id).first() if user.package_id else None
    plan_type = (pkg.plan_type or "one_time").strip().lower() if pkg else "one_time"
    if plan_type != "subscription":
        return None

    now = datetime.utcnow()
    active = find_active_user_subscription(db, user)
    if not active:
        expired = (
            db.query(UserSubscription)
            .filter(UserSubscription.user_id == user.id)
            .order_by(UserSubscription.end_at.desc())
            .first()
        )
        if not expired:
            return {
                "plan_type": "subscription",
                "status": "pending",
                "start_at": None,
                "end_at": None,
                "duration_months": int(pkg.duration_months or 0) if pkg and pkg.duration_months else None,
                "days_remaining": None,
                "extension_months": None,
                "end_at_if_extended": None,
            }
        active = expired
        status = "expired"
    else:
        status = "active" if active.start_at <= now <= active.end_at else "expired"

    days_remaining = (active.end_at.date() - now.date()).days if active.end_at else None
    duration = int(active.duration_months or 0) or (int(pkg.duration_months or 0) if pkg else 0) or None

    offer = get_extension_offer(db, user)
    ext_months = int(offer.get("extension_months") or 0) if offer.get("enabled") else None
    end_if_extended = None
    if ext_months and active.end_at:
        end_if_extended = _add_months(active.end_at, ext_months)

    return {
        "plan_type": "subscription",
        "status": status,
        "start_at": active.start_at,
        "end_at": active.end_at,
        "duration_months": duration,
        "days_remaining": days_remaining,
        "extension_months": ext_months,
        "end_at_if_extended": end_if_extended,
    }


def get_extension_offer(db: Session, user: User) -> dict:
    from app.services.payments import try_finalize_pending_extension_payment

    try_finalize_pending_extension_payment(db, user)
    now = datetime.utcnow()
    if not (user.subscription or "").strip():
        return {"enabled": False, "reason": "No subscription assigned.", "extension_months": 2}
    if (user.payment_status or "").strip().lower() != "credit":
        return {"enabled": False, "reason": "Complete your registration payment first.", "extension_months": 2}
    if (user.approve or "").strip() != "1":
        return {"enabled": False, "reason": "Your account is not approved yet.", "extension_months": 2}
    if _user_has_extension_payment(db, user):
        return {"enabled": False, "reason": "You have already purchased the extension.", "extension_months": 2}

    active_sub = _latest_user_subscription(db, user)
    batch_end = None
    days_to_expiry = None
    if active_sub and active_sub.end_at:
        batch_end = active_sub.end_at
        days_to_expiry = (active_sub.end_at.date() - now.date()).days

    result: dict[str, Any] = {
        "enabled": False,
        "reason": None,
        "days_to_expiry": days_to_expiry,
        "current_end_at": batch_end,
        "extension_months": 2,
        "estimated_amount": None,
        "currency_name": None,
    }

    manual = get_extension_batch_settings(db, user.subscription)
    if (manual.get("enabled") or "").strip() == "1":
        m_start = manual.get("start_date")
        m_end = manual.get("end_date")
        show_link = True
        if m_start and now.date() < (parse_iso_date(m_start) or now.date()):
            show_link = False
        if m_end and now.date() > (parse_iso_date(m_end) or now.date()):
            show_link = False

        configured_end = _extension_batch_end_at(manual, active_sub)
        if configured_end:
            batch_end = configured_end
            days_to_expiry = (configured_end.date() - now.date()).days
            result["current_end_at"] = configured_end
            result["days_to_expiry"] = days_to_expiry

        if show_link:
            try:
                m_amt = float(manual.get("total_amount") or 0)
                m_months = int(manual.get("months") or 2)
                m_gross = float(manual.get("gross_amount") or m_amt)
                m_gst_pct = float(manual.get("gst_percentage") or 0)
                m_gst_amt = float(manual.get("gst_amount") or 0)
                if m_amt > 0:
                    extended_end = _add_months(batch_end, m_months) if batch_end else None
                    result["enabled"] = True
                    result["extension_months"] = m_months
                    result["currency_name"] = "INR"
                    result["gross_amount"] = m_gross
                    result["gst_percentage"] = m_gst_pct
                    result["gst_amount"] = m_gst_amt
                    result["payment_amount_inr"] = m_amt
                    result["estimated_amount"] = m_amt
                    result["batch_end_date"] = batch_end.date().isoformat() if batch_end else None
                    result["extended_end_date"] = extended_end.date().isoformat() if extended_end else None
                    result["headline"] = _format_extension_headline(
                        (user.subscription or "").strip(),
                        batch_end,
                        extended_end,
                        m_months,
                        m_gross,
                        m_amt,
                    )

                    country = db.query(Country).filter(Country.id == user.country_id).first() if user.country_id else None
                    if country and (country.name or "").strip().lower() != "india":
                        result["currency_name"] = "USD"
                        usd_rate = 85.0
                        row = db.query(Option).filter(Option.option_name == "usd_rate").first()
                        try:
                            usd_rate = float((row.option_value if row else "85") or "85")
                        except ValueError:
                            usd_rate = 85.0
                        foreign_total = float(manual.get("foreign_total_amount") or 0)
                        if foreign_total > 0:
                            result["estimated_amount"] = foreign_total
                        else:
                            result["estimated_amount"] = round(m_amt / usd_rate, 2)
                        result["display_amount_usd"] = result["estimated_amount"]
                    return result
            except Exception:
                pass
        if not show_link:
            result["reason"] = "Extension payment is not open yet."
            return result

    if not active_sub:
        result["reason"] = "No active subscription found."
        return result

    days_to_expiry = (active_sub.end_at.date() - now.date()).days if active_sub.end_at else None
    result["days_to_expiry"] = days_to_expiry
    result["current_end_at"] = active_sub.end_at

    # Fallback to automated pro-rata logic (Legacy)
    if days_to_expiry is not None and days_to_expiry < 0:
        result["reason"] = "Subscription already expired."
        return result
    if days_to_expiry is not None and days_to_expiry > 15:
        result["reason"] = "Extension opens 15 days before expiry."
        return result

    pkg = db.query(Package).filter(Package.id == active_sub.package_id).first()
    if not pkg:
        result["reason"] = "Current package not found."
        return result
    duration = int(active_sub.duration_months or pkg.duration_months or 0)
    if duration <= 0:
        result["reason"] = "Current package has invalid duration."
        return result
    base_total = float(pkg.total_amount or (pkg.gross_amount or 0.0) + (pkg.gst_amount or 0.0))
    amount = round(base_total * (2.0 / float(duration)), 2)

    currency = "INR"
    country = db.query(Country).filter(Country.id == user.country_id).first() if user.country_id else None
    if country and (country.name or "").strip().lower() != "india":
        currency = "USD"
        usd_rate = 85.0
        row = db.query(Option).filter(Option.option_name == "usd_rate").first()
        try:
            usd_rate = float((row.option_value if row else "85") or "85")
        except ValueError:
            usd_rate = 85.0
        amount = _to_display_usd(amount, usd_rate)
    result["enabled"] = True
    result["estimated_amount"] = amount
    result["currency_name"] = currency
    return result


def _iso_optional(dt: datetime | date | None) -> str | None:
    return dt.isoformat() if dt else None


def _coerce_date(value: datetime | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _subscriptions_for_user_batch(user: User, subs: list[UserSubscription]) -> list[UserSubscription]:
    keys = subscription_batch_keys(user.subscription)
    if not keys:
        return subs
    matched = [s for s in subs if (s.batch_slug or "").strip().lower() in keys]
    return matched if matched else subs


def _pick_user_subscription_row(
    subs: list[UserSubscription], *, now: datetime
) -> tuple[UserSubscription | None, str]:
    if not subs:
        return None, "pending"
    active = [
        s
        for s in subs
        if (s.status or "").strip().lower() == "active" and s.start_at <= now <= s.end_at
    ]
    if active:
        return max(active, key=lambda s: s.end_at), "active"
    latest = max(subs, key=lambda s: s.end_at)
    if latest.end_at and latest.end_at < now:
        return latest, "expired"
    if latest.start_at and latest.start_at > now:
        return latest, "pending"
    return latest, "expired"


def admin_subscription_summary(
    user: User,
    *,
    pkg: Package | None = None,
    subs: list[UserSubscription] | None = None,
) -> dict[str, Any]:
    """Course access window for admin user list (subscription + one-time plans)."""
    now = datetime.utcnow()
    pay_ok = (user.payment_status or "").strip().lower() == "credit"
    plan_type = (pkg.plan_type or "one_time").strip().lower() if pkg else "one_time"
    package_name = (pkg.name or "").strip() if pkg else None
    duration = int(pkg.duration_months or 0) if pkg and pkg.duration_months else None

    if not pay_ok:
        return {
            "plan_type": plan_type,
            "plan_type_label": "Subscription" if plan_type == "subscription" else "One-time",
            "package_name": package_name,
            "duration_months": duration,
            "course_start_at": None,
            "course_end_at": None,
            "access_status": "no_payment",
            "days_remaining": None,
        }

    if plan_type == "subscription":
        user_subs = _subscriptions_for_user_batch(user, subs or [])
        row, access_status = _pick_user_subscription_row(user_subs, now=now)
        if row:
            days_remaining = (row.end_at.date() - now.date()).days if row.end_at else None
            dur = int(row.duration_months or 0) or duration
            label = f"Subscription ({dur}M)" if dur else "Subscription"
            return {
                "plan_type": "subscription",
                "plan_type_label": label,
                "package_name": package_name,
                "duration_months": dur,
                "course_start_at": _iso_optional(row.start_at),
                "course_end_at": _iso_optional(row.end_at),
                "access_status": access_status,
                "days_remaining": days_remaining,
            }
        label = f"Subscription ({duration}M)" if duration else "Subscription"
        return {
            "plan_type": "subscription",
            "plan_type_label": label,
            "package_name": package_name,
            "duration_months": duration,
            "course_start_at": None,
            "course_end_at": None,
            "access_status": "pending",
            "days_remaining": None,
        }

    start = None
    if pkg and pkg.batch_start_date:
        start = pkg.batch_start_date
    elif user.payment_date:
        start = user.payment_date
    elif user.created_at:
        start = user.created_at
    course_start = _one_time_course_start_date(pkg)
    if course_start:
        start = datetime.combine(course_start, datetime.min.time())
    end = _one_time_course_end_date(pkg)
    access_status = "active"
    today = now.date()
    if course_start and today < course_start:
        access_status = "pending"
    elif end and end < today:
        access_status = "expired"
    days_remaining = (end - today).days if end and today <= end else None
    return {
        "plan_type": "one_time",
        "plan_type_label": "One-time access",
        "package_name": package_name,
        "duration_months": duration,
        "course_start_at": _iso_optional(start),
        "course_end_at": _iso_optional(end),
        "access_status": access_status,
        "days_remaining": days_remaining,
    }


def batch_admin_subscription_summaries(db: Session, users: list[User]) -> dict[int, dict[str, Any]]:
    if not users:
        return {}
    user_ids = [u.id for u in users]
    package_ids = {u.package_id for u in users if u.package_id}
    packages: dict[int, Package] = {}
    if package_ids:
        packages = {p.id: p for p in db.query(Package).filter(Package.id.in_(package_ids)).all()}
    all_subs = (
        db.query(UserSubscription)
        .filter(UserSubscription.user_id.in_(user_ids))
        .order_by(UserSubscription.end_at.desc())
        .all()
    )
    subs_by_user: dict[int, list[UserSubscription]] = {}
    for sub in all_subs:
        subs_by_user.setdefault(sub.user_id, []).append(sub)
    return {
        u.id: admin_subscription_summary(
            u,
            pkg=packages.get(u.package_id) if u.package_id else None,
            subs=subs_by_user.get(u.id, []),
        )
        for u in users
    }
