from __future__ import annotations

from datetime import datetime
import re

from sqlalchemy.orm import Session

from app.models import Country, Option, Package, User, UserSubscription
from app.services.registration import _to_display_usd


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
    return {
        "enabled": get_option_value(db, enabled_key) if enabled_key else "",
        "batch_label": get_option_value(db, label_key) if label_key else "",
        "fixed_date": get_option_value(db, date_key) if date_key else "",
    }


def get_extension_batch_settings(db: Session, batch_name: str | None) -> dict[str, str]:
    enabled_key = extension_option_key("enabled", batch_name)
    gross_key = extension_option_key("gross_amount", batch_name)
    gst_pct_key = extension_option_key("gst_percentage", batch_name)
    gst_amt_key = extension_option_key("gst_amount", batch_name)
    total_key = extension_option_key("total_amount", batch_name)
    months_key = extension_option_key("months", batch_name)
    start_key = extension_option_key("start_date", batch_name)
    end_key = extension_option_key("end_date", batch_name)
    return {
        "enabled": get_option_value(db, enabled_key) if enabled_key else "",
        "gross_amount": get_option_value(db, gross_key) if gross_key else "",
        "gst_percentage": get_option_value(db, gst_pct_key) if gst_pct_key else "",
        "gst_amount": get_option_value(db, gst_amt_key) if gst_amt_key else "",
        "total_amount": get_option_value(db, total_key) if total_key else "",
        "months": get_option_value(db, months_key) if months_key else "",
        "start_date": get_option_value(db, start_key) if start_key else "",
        "end_date": get_option_value(db, end_key) if end_key else "",
    }


def has_active_subscription(db: Session, user: User, batch_name: str | None = None) -> bool:
    if not user:
        return False
    sub_name = (batch_name or user.subscription or "").strip().lower()
    if not sub_name:
        return False
    now = datetime.utcnow()
    row = (
        db.query(UserSubscription.id)
        .filter(
            UserSubscription.user_id == user.id,
            UserSubscription.batch_slug == sub_name,
            UserSubscription.status == "active",
            UserSubscription.start_at <= now,
            UserSubscription.end_at >= now,
        )
        .first()
    )
    return row is not None


def ensure_subscription_entitlement(db: Session, user: User, batch_name: str | None = None) -> tuple[bool, str | None]:
    # Backward compatibility: only enforce when user has subscription rows for this batch.
    sub_name = (batch_name or user.subscription or "").strip().lower()
    if not sub_name:
        return False, "No subscription assigned."
    has_any = (
        db.query(UserSubscription.id)
        .filter(
            UserSubscription.user_id == user.id,
            UserSubscription.batch_slug == sub_name,
        )
        .first()
    )
    if not has_any:
        return True, None
    if not has_active_subscription(db, user, sub_name):
        return False, "Your subscription plan has expired."
    return True, None


def can_access_video_library(db: Session, user: User) -> tuple[bool, str | None]:
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

    return True, None


def can_access_mock_test(db: Session, user: User) -> tuple[bool, str | None]:
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
    return True, None


def get_extension_offer(db: Session, user: User) -> dict:
    now = datetime.utcnow()
    sub_name = (user.subscription or "").strip().lower()
    if not sub_name:
        return {"enabled": False, "reason": "No subscription assigned.", "extension_months": 2}
    active_sub = (
        db.query(UserSubscription)
        .filter(
            UserSubscription.user_id == user.id,
            UserSubscription.batch_slug == sub_name,
            UserSubscription.status == "active",
        )
        .order_by(UserSubscription.end_at.desc())
        .first()
    )
    if not active_sub:
        return {"enabled": False, "reason": "No active subscription found.", "extension_months": 2}

    days_to_expiry = (active_sub.end_at.date() - now.date()).days
    result = {
        "enabled": False,
        "reason": None,
        "days_to_expiry": days_to_expiry,
        "current_end_at": active_sub.end_at,
        "extension_months": 2,
        "estimated_amount": None,
        "currency_name": None,
    }
    # Manual Admin Settings Check
    manual = get_extension_batch_settings(db, user.subscription)
    if (manual.get("enabled") or "").strip() == "1":
        # Check date window
        m_start = manual.get("start_date")
        m_end = manual.get("end_date")
        show_link = True
        try:
            if m_start:
                if now.date() < datetime.fromisoformat(m_start).date():
                    show_link = False
            if m_end:
                if now.date() > datetime.fromisoformat(m_end).date():
                    show_link = False
        except Exception:
            pass

        if show_link:
            try:
                m_amt = float(manual.get("total_amount") or 0)
                m_months = int(manual.get("months") or 2)
                if m_amt > 0:
                    result["enabled"] = True
                    result["extension_months"] = m_months
                    result["currency_name"] = "INR"
                    
                    # Line items (always in INR as base)
                    result["gross_amount"] = float(manual.get("gross_amount") or m_amt)
                    result["gst_percentage"] = float(manual.get("gst_percentage") or 0)
                    result["gst_amount"] = float(manual.get("gst_amount") or 0)

                    # Payment is always in INR (Razorpay)
                    result["payment_amount_inr"] = m_amt
                    result["estimated_amount"] = m_amt

                    # Currency handling for foreign students
                    country = db.query(Country).filter(Country.id == user.country_id).first() if user.country_id else None
                    if country and (country.name or "").strip().lower() != "india":
                        result["currency_name"] = "USD"
                        usd_rate = 85.0
                        row = db.query(Option).filter(Option.option_name == "usd_rate").first()
                        try:
                            usd_rate = float((row.option_value if row else "85") or "85")
                        except ValueError:
                            usd_rate = 85.0
                        result["estimated_amount"] = round(m_amt / usd_rate, 2)
                        result["display_amount_usd"] = result["estimated_amount"]
                    return result
            except Exception:
                pass

    # Fallback to automated pro-rata logic (Legacy)
    if days_to_expiry < 0:
        result["reason"] = "Subscription already expired."
        return result
    if days_to_expiry > 15:
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
