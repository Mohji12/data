from __future__ import annotations

import re
import uuid
from calendar import monthrange
from datetime import date, datetime
from typing import List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import Date, and_, cast, func, inspect, or_
from sqlalchemy.orm import Session, load_only

from app.models import (
    BatchMaster,
    CouponMaster,
    Country,
    Option,
    Package,
    RegistrationPaymentTxn,
    User,
    UserSubscription,
)
from app.schemas import (
    BatchDefinition,
    FeeStructureBlock,
    RegistrationCatalogItem,
    FeeStructureResponse,
    PayableAmountRequest,
    PayableAmountResponse,
    RegistrationInitRequest,
    RegistrationInitResponse,
)
from app.services.password_crypto import php_password_for_db

# ── Old student discount rates (matching PHP hardcoded values) ────────────
OLD_STUDENT_RATE_INR = {"gross": 18000, "gst_pct": 18, "gst_amt": 3240, "total": 21240}
OLD_STUDENT_RATE_USD = {"gross": 220, "gst_pct": 18, "gst_amt": 40, "total": 260}

# Calendar early-bird (server local date): inclusive day range in each month.
EARLY_BIRD_FIRST_DAY = 1
EARLY_BIRD_LAST_DAY = 10
EARLY_BIRD_DISCOUNT_PERCENT = 25.0


# Overrides keyed by slug (derived from batch_master.name) for coupon/doc flags when DB has no extra columns.
BATCH_DEFINITIONS: dict[str, BatchDefinition] = {
    "batch-14": BatchDefinition(slug="batch-14", title="Batch 14", registration_type="Batch", requires_document=True, coupon_enabled=True),
    "batch-15": BatchDefinition(slug="batch-15", title="Batch 15", registration_type="Batch", requires_document=True, coupon_enabled=True),
    "cp-8": BatchDefinition(slug="cp-8", title="Critical Pearls 8", registration_type="CP", requires_document=True, coupon_enabled=True),
    "cp-9": BatchDefinition(slug="cp-9", title="Critical Pearls 9", registration_type="CP", requires_document=True, coupon_enabled=True),
    "cp-10": BatchDefinition(slug="cp-10", title="Critical Pearls 10", registration_type="CP", requires_document=True, coupon_enabled=True),
    "edic-10": BatchDefinition(slug="edic-10", title="EDIC 10", registration_type="EDIC", requires_document=True, coupon_enabled=True),
    "ccm-2": BatchDefinition(slug="ccm-2", title="CCM 2", registration_type="CCM", requires_document=True, coupon_enabled=True),
}

# Alternate URL slugs from React routes → canonical slug used for matching batch_master rows.
REGISTRATION_SLUG_ALIASES: dict[str, str] = {
    "comprehensive-1": "comprehensive-course-1",
    "comprehensive-2": "comprehensive-course-2",
    "ccm-2": "ccm-batch-2",
    "ccm-practical-series": "ccm-batch-2",
    "ccm-practical-series-batch-3": "practical-series-batch-3",
    "ccm-3": "practical-series-batch-3",
    "ccm-batch-3": "practical-series-batch-3",
    "edic-10": "batch-10-edic-1",
}

# When `batch_master` label differs from `package.subscription` (PHP legacy names).
# Prefer `batch_master.package_subscription` in the database; these are fallbacks only.
BATCH_SLUG_TO_PACKAGE_SUBSCRIPTION: dict[str, str] = {
    "comprehensive-course-1": "CP 7",
    "comprehensive-1": "CP 7",
    "comprehensive-course-2": "CP 8",
    "comprehensive-2": "CP 8",
    "practical-series-batch-3": "PRACTICAL SERIES BATCH 3",
    "ccm-practical-series-batch-3": "PRACTICAL SERIES BATCH 3",
    "ccm-3": "PRACTICAL SERIES BATCH 3",
    "ccm-batch-3": "PRACTICAL SERIES BATCH 3",
    "batch-16-mccm": "BATCH 16-MCCM",
    "edic-10": "Batch EDIC 10",
    "batch-10-edic-1": "Batch EDIC 10",
}

# Legacy + current user.subscription values for the same CCM Batch 3 enrolment.
CCM_BATCH_3_USER_SUBSCRIPTIONS = ("CCM Batch 3", "PRACTICAL SERIES BATCH 3")


def expand_batch_user_subscription_filter(
    db: Session,
    filter_value: str,
) -> tuple[list[str], list[int]]:
    """
    Resolve admin batch filter to all user.subscription strings and package ids for that batch.
    Includes package_subscription from batch_master and CCM Batch 3 aliases.
    """
    raw = (filter_value or "").strip()
    if not raw:
        return [], []

    names: set[str] = {raw}
    row = (
        db.query(BatchMaster)
        .filter(
            or_(
                func.lower(func.trim(BatchMaster.name)) == raw.casefold(),
                func.lower(func.trim(BatchMaster.package_subscription)) == raw.casefold(),
            )
        )
        .first()
    )
    if row:
        if (row.name or "").strip():
            names.add((row.name or "").strip())
        pkg_sub = _row_package_subscription(row)
        if pkg_sub:
            names.add(pkg_sub)

    lowered = {n.casefold() for n in names}
    if lowered & {s.casefold() for s in CCM_BATCH_3_USER_SUBSCRIPTIONS}:
        names.update(CCM_BATCH_3_USER_SUBSCRIPTIONS)

    pkg_ids: set[int] = set()
    for sub_name in names:
        rows = (
            db.query(Package.id)
            .filter(_subscription_name_eq(Package.subscription, sub_name), Package.status == "1")
            .all()
        )
        pkg_ids.update(int(r[0]) for r in rows)

    return sorted(names), sorted(pkg_ids)


def apply_batch_subscription_filter_to_users(query, db: Session, filter_values: list[str]):
    """Narrow a User query to everyone enrolled under the given batch filter(s)."""
    all_names: set[str] = set()
    all_pkg_ids: set[int] = set()
    for fv in filter_values:
        if not (fv or "").strip():
            continue
        names, pkg_ids = expand_batch_user_subscription_filter(db, fv.strip())
        all_names.update(n.casefold() for n in names)
        all_pkg_ids.update(pkg_ids)

    if not all_names and not all_pkg_ids:
        return query

    clauses = []
    if all_names:
        clauses.append(func.lower(func.coalesce(User.subscription, "")).in_(list(all_names)))
    if all_pkg_ids:
        clauses.append(User.package_id.in_(list(all_pkg_ids)))
    return query.filter(or_(*clauses))


# Public fee/registration URL slug → exact `batch_master.name` (case-insensitive) when DB uses different labels.
REGISTRATION_FEE_SLUG_TO_BATCH_NAME: dict[str, str] = {}

# When `batch_master.name` slugifies differently from the public URL (extra words, punctuation).
FEE_PAGE_SLUG_NAME_PATTERNS: dict[str, re.Pattern[str]] = {
    "comprehensive-course-1": re.compile(
        r"(comprehensive\s+course\s+1|comprehensive\s+1)\b",
        re.IGNORECASE,
    ),
    "comprehensive-course-2": re.compile(
        r"(comprehensive\s+course\s+2|comprehensive\s+2)\b",
        re.IGNORECASE,
    ),
    "batch-10-edic-1": re.compile(
        r"(batch\s*)?10\s*[-]?\s*edic\s*1|batch\s*10\s*[-\s]*edic\s*1|edic\s*10",
        re.IGNORECASE,
    ),
}


def package_subscription_for_batch(batch: BatchDefinition) -> str:
    """Package lookup key: DB `package_subscription` when set, else legacy slug map, else display title."""
    stored = (batch.package_subscription or "").strip()
    if stored:
        return stored
    slug = (batch.slug or "").strip().lower()
    mapped = BATCH_SLUG_TO_PACKAGE_SUBSCRIPTION.get(slug)
    if mapped:
        return mapped.strip()
    return (batch.title or "").strip()


_CCM_PRACTICAL_BATCH_3_SLUGS = frozenset(
    {
        "practical-series-batch-3",
        "ccm-practical-series-batch-3",
        "ccm-3",
        "ccm-batch-3",
    }
)

_COMPREHENSIVE_COURSE_SLUGS = frozenset(
    {
        "comprehensive-course-1",
        "comprehensive-1",
        "cp-7",
        "comprehensive-course-2",
        "comprehensive-2",
        "cp-8",
    }
)

_COMPREHENSIVE_COURSE_SUBS = frozenset({"cp 7", "cp 8"})


def _is_ccm_practical_batch_3(batch: BatchDefinition) -> bool:
    """PRACTICAL SERIES BATCH 3 and CCM Batch 3 share two legacy package.subscription names."""
    slug = (batch.slug or "").strip().lower()
    if slug in _CCM_PRACTICAL_BATCH_3_SLUGS:
        return True
    aliases = {s.casefold() for s in CCM_BATCH_3_USER_SUBSCRIPTIONS}
    title_cf = (batch.title or "").strip().casefold()
    if title_cf in aliases:
        return True
    return package_subscription_for_batch(batch).casefold() in aliases


def package_subscriptions_for_batch(batch: BatchDefinition) -> list[str]:
    """All package.subscription keys used for fee/registration lookup (usually one; two for CCM Batch 3)."""
    if _is_ccm_practical_batch_3(batch):
        return list(CCM_BATCH_3_USER_SUBSCRIPTIONS)
    primary = package_subscription_for_batch(batch)
    return [primary] if primary else []


def _is_comprehensive_course_batch(batch: BatchDefinition) -> bool:
    slug = (batch.slug or "").strip().lower()
    if slug in _COMPREHENSIVE_COURSE_SLUGS:
        return True
    title = (batch.title or "").strip().casefold()
    if "comprehensive course 1" in title or "comprehensive course 2" in title:
        return True
    return package_subscription_for_batch(batch).casefold() in _COMPREHENSIVE_COURSE_SUBS


def _shows_all_pricing_tiers(batch: BatchDefinition) -> bool:
    """Fee/register UI lists every active package tier (not only the current sale window)."""
    return _is_ccm_practical_batch_3(batch) or _is_comprehensive_course_batch(batch)


def _row_package_subscription(row: BatchMaster) -> Optional[str]:
    val = getattr(row, "package_subscription", None)
    if val is None:
        return None
    s = str(val).strip()
    return s or None


def _subscription_name_eq(column, subscription: str):
    target = (subscription or "").strip().casefold()
    return func.lower(func.trim(column)) == target


def _title_to_slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (name or "").strip().lower())
    return (s.strip("-") or "batch").lower()


def _infer_registration_flags(title: str) -> tuple[str, bool, bool]:
    """registration_type, requires_document, coupon_enabled — when not in BATCH_DEFINITIONS."""
    t = (title or "").lower()
    if "edic" in t:
        return "EDIC", True, True
    if "critical pearl" in t or re.search(r"\bcp\s*\d", t) or t.startswith("cp "):
        return "CP", True, True
    if "ccm" in t:
        return "CCM", True, True
    return "Batch", True, True


def batch_definition_from_master_row(row: BatchMaster) -> BatchDefinition:
    title = (row.name or "").strip()
    slug = _title_to_slug(title)
    override = BATCH_DEFINITIONS.get(slug)
    if override:
        return BatchDefinition(
            slug=override.slug,
            title=title,
            registration_type=override.registration_type,
            requires_document=override.requires_document,
            coupon_enabled=override.coupon_enabled,
            package_subscription=_row_package_subscription(row),
        )
    reg_type, req_doc, coupon = _infer_registration_flags(title)
    return BatchDefinition(
        slug=slug,
        title=title,
        registration_type=reg_type,
        requires_document=req_doc,
        coupon_enabled=coupon,
        package_subscription=_row_package_subscription(row),
    )


def _batch_has_column(db: Session, column_name: str) -> bool:
    bind = db.get_bind()
    cols = inspect(bind).get_columns("batch_master")
    return any((c.get("name") or "").lower() == column_name.lower() for c in cols)


def _batch_load_only(db: Session):
    fields = [
        BatchMaster.id,
        BatchMaster.name,
        BatchMaster.status,
        BatchMaster.display_order,
        BatchMaster.registration_fee_structure,
        BatchMaster.description,
        BatchMaster.video_url,
        BatchMaster.video_file,
        BatchMaster.brochure_file,
    ]
    if _batch_has_column(db, "package_subscription"):
        fields.append(BatchMaster.package_subscription)
    return load_only(*fields)


def _batch_query(db: Session):
    return db.query(BatchMaster).options(_batch_load_only(db))


def _brochure_option_key(batch_name: str) -> str:
    return f"batch_brochure::{(batch_name or '').strip().casefold()}"


def _coupon_has_column(db: Session, column_name: str) -> bool:
    bind = db.get_bind()
    cols = inspect(bind).get_columns("coupon_master")
    return any((c.get("name") or "").lower() == column_name.lower() for c in cols)


def _coupon_query(db: Session):
    cols = [CouponMaster.id, CouponMaster.code, CouponMaster.status]
    if _coupon_has_column(db, "discount_amount"):
        cols.append(CouponMaster.discount_amount)
    if _coupon_has_column(db, "discount_percent"):
        cols.append(CouponMaster.discount_percent)
    if _coupon_has_column(db, "subscriptions"):
        cols.append(CouponMaster.subscriptions)
    if _coupon_has_column(db, "assigned_email"):
        cols.append(CouponMaster.assigned_email)
    return db.query(CouponMaster).options(load_only(*cols))


def _package_end_open_on_or_after(day: date):
    """SQL filter: subscription plans, open-ended (null end_date), or end_date on/after day."""
    return or_(
        Package.plan_type == "subscription",
        Package.end_date.is_(None),
        cast(Package.end_date, Date) >= day,
    )


# Days after a tier ends before the next tier may start (admin extends early bird → following tiers shift).
PRICING_TIER_GAP_DAYS = 15
# Show upcoming tiers on fee/register UI when their start_date is within this many days ahead.
PRICING_TIER_UPCOMING_DAYS = 15
_DURATION_IN_NAME_RE = re.compile(r"\b\d+\s*months?\b", re.I)


def _as_date(val: object) -> date | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    return None


def _package_promo_discount_active(pkg: Package, today: Optional[date] = None) -> bool:
    """True when package.discount_* should reduce payable amount today (inclusive start/end dates)."""
    day = today or date.today()
    pct = float(pkg.discount_percentage or 0)
    disc_amt = float(pkg.discounted_amount or 0)
    if pct <= 0 and disc_amt < 0.5:
        return False
    start = _as_date(pkg.discount_start_date)
    end = _as_date(pkg.discount_end_date)
    if start and day < start:
        return False
    if end and day > end:
        return False
    return True


def _resolve_package_line_amounts(
    pkg: Package,
    *,
    today: Optional[date] = None,
) -> tuple[float, float, float, float]:
    """(gross, gst_percent, gst_amount, total) for registration, fee table, and payment."""
    gross = float(pkg.gross_amount or 0)
    gst_pct = float(pkg.gst_percentage or 18)
    naive_gst = round(gross * gst_pct / 100.0, 2)
    naive_total = round(gross + naive_gst, 2)

    if _package_promo_discount_active(pkg, today):
        pct_disc = float(pkg.discount_percentage or 0)
        disc_amt = float(pkg.discounted_amount or 0)
        if pct_disc > 0 and disc_amt < 0.5:
            disc_amt = round(gross * pct_disc / 100.0, 2)
        taxable = max(0.0, round(gross - disc_amt, 2))
        gst_amt = float(pkg.gst_amount or 0)
        if gst_amt < 0.5:
            gst_amt = round(taxable * gst_pct / 100.0, 2)
        total = float(pkg.total_amount or 0)
        if total < 0.5:
            total = round(taxable + gst_amt, 2)
        return gross, gst_pct, gst_amt, total

    # One-time tier rows (e.g. Batch EDIC 10) store the tier price in total_amount while
    # sharing the same gross; timed discount_* fields must not override that tier price.
    plan = (pkg.plan_type or "one_time").strip().lower()
    stored_total = float(pkg.total_amount or 0)
    if plan == "one_time" and stored_total >= 0.5 and abs(stored_total - naive_total) > 0.01:
        gst_amt = float(pkg.gst_amount or 0)
        if gst_amt < 0.5:
            disc_amt = float(pkg.discounted_amount or 0)
            taxable = max(0.0, round(gross - disc_amt, 2))
            gst_amt = round(taxable * gst_pct / 100.0, 2)
        return gross, gst_pct, gst_amt, stored_total

    return gross, gst_pct, naive_gst, naive_total


def _recompute_package_stored_amounts(pkg: Package) -> None:
    """Persist discounted_amount / gst_amount / total_amount from gross + discount_percentage."""
    gross = float(pkg.gross_amount or 0)
    gst_pct = float(pkg.gst_percentage or 18)
    pct = float(pkg.discount_percentage or 0)
    if pct > 0:
        disc_amt = round(gross * pct / 100.0, 2)
        taxable = max(0.0, round(gross - disc_amt, 2))
        gst_amt = round(taxable * gst_pct / 100.0, 2)
        total = round(taxable + gst_amt, 2)
        pkg.discounted_amount = disc_amt
        pkg.gst_amount = gst_amt
        pkg.total_amount = total
    else:
        gst_amt = round(gross * gst_pct / 100.0, 2)
        pkg.discounted_amount = 0.0
        pkg.gst_amount = gst_amt
        pkg.total_amount = round(gross + gst_amt, 2)


def _sync_timed_promo_discount_across_subscription_packages(db: Session, pkg: Package) -> int:
    """
    Mirror timed promo (%, start, end) to every subscription row for the same batch subscription
    (e.g. all BATCH 16-MCCM 6/9/12 × Indian/Foreign) so admin sets discount once.
    """
    if (pkg.plan_type or "").strip().lower() != "subscription":
        return 0
    sub = (pkg.subscription or "").strip()
    if not sub:
        return 0
    siblings = (
        db.query(Package)
        .filter(
            _subscription_name_eq(Package.subscription, sub),
            Package.status == "1",
            Package.id != pkg.id,
            func.lower(func.trim(Package.plan_type)) == "subscription",
        )
        .all()
    )
    touched = 0
    for row in siblings:
        row.discount_percentage = pkg.discount_percentage
        row.discount_start_date = pkg.discount_start_date
        row.discount_end_date = pkg.discount_end_date
        _recompute_package_stored_amounts(row)
        db.add(row)
        touched += 1
    return touched


def _tier_label_from_package(p: Package) -> str:
    name = (p.name or "").strip()
    stripped = _DURATION_IN_NAME_RE.sub("", name).strip(" -–—")
    if stripped:
        return stripped
    start = _as_date(p.start_date)
    end = _as_date(p.end_date)
    if start and end:
        return f"{start.strftime('%d %b %Y')} – {end.strftime('%d %b %Y')}"
    return name or "Offer"


def _pricing_window_key(p: Package) -> tuple:
    label = _tier_label_from_package(p).casefold()
    plan = (p.plan_type or "one_time").strip().lower()
    # Subscription 6/9/12 rows share one tier name but may have mixed null/start dates — group by label.
    if plan == "subscription":
        return (label,)
    return (_as_date(p.start_date), _as_date(p.end_date), label)


def _package_visible_for_registration(
    p: Package,
    today: date,
    *,
    include_upcoming: bool = True,
) -> bool:
    """True if this package row should appear on register/fee UI today."""
    if (p.status or "") != "1":
        return False
    start = _as_date(p.start_date)
    end = _as_date(p.end_date)
    if start and start > today:
        if not include_upcoming:
            return False
        horizon = today.toordinal() + PRICING_TIER_UPCOMING_DAYS
        if start.toordinal() > horizon:
            return False
    plan = (p.plan_type or "one_time").strip().lower()
    if plan == "subscription":
        return True
    if end is None:
        return True
    return end >= today


def _group_packages_by_pricing_window(packages: list[Package]) -> list[dict[str, object]]:
    """Group subscription (or one_time) rows that share the same sale window."""
    buckets: dict[tuple[date | None, date | None, str], list[Package]] = {}
    for p in packages:
        buckets.setdefault(_pricing_window_key(p), []).append(p)
    groups: list[dict[str, object]] = []
    for _key, rows in buckets.items():
        rows_sorted = sorted(rows, key=lambda x: (int(x.duration_months or 0), x.id))
        lead = rows_sorted[0]
        starts = [s for s in (_as_date(p.start_date) for p in rows_sorted) if s]
        ends = [e for e in (_as_date(p.end_date) for p in rows_sorted) if e]
        window_end = None if any(_as_date(p.end_date) is None for p in rows_sorted) else (max(ends) if ends else None)
        groups.append(
            {
                "label": _tier_label_from_package(lead),
                "start": min(starts) if starts else None,
                "end": window_end,
                "packages": rows_sorted,
            }
        )
    groups.sort(
        key=lambda g: (
            (g["start"] or date.min).toordinal(),
            (g["end"] or date.max).toordinal(),
        )
    )
    return groups


def _sync_tier_dates_across_delegate_categories(
    db: Session,
    pkg: Package,
    *,
    end_date: date | None = None,
    start_date: date | None = None,
) -> int:
    """Mirror start/end on the other delegate row for the same tier name (Indian ↔ Foreign)."""
    tier_name = (pkg.name or "").strip()
    sub = (pkg.subscription or "").strip()
    if not tier_name or not sub:
        return 0
    siblings = (
        db.query(Package)
        .filter(
            Package.subscription == sub,
            Package.name == tier_name,
            Package.status == "1",
            Package.id != pkg.id,
        )
        .all()
    )
    touched = 0
    for row in siblings:
        if end_date is not None:
            row.end_date = end_date
        if start_date is not None:
            row.start_date = start_date
        db.add(row)
        touched += 1
    return touched


def shift_following_package_windows_after_extension(
    db: Session,
    pkg: Package,
    old_end: date | None,
    new_end: date | None,
) -> int:
    """
    When admin extends a tier's end_date (e.g. Early Bird 15 Jun → 30 Jun), reposition later tiers
    for the same subscription + delegate category:
    - Next tier starts on new_end + PRICING_TIER_GAP_DAYS (e.g. 30 Jun + 15 → 15 Jul)
    - Window length (end − start) is preserved; prices on package rows are unchanged.
    """
    if old_end is None or new_end is None or new_end <= old_end:
        return 0
    from datetime import timedelta

    sub = (pkg.subscription or "").strip()
    cat = (pkg.category_name or "").strip()
    if not sub or not cat:
        return 0
    followers = (
        db.query(Package)
        .filter(
            Package.subscription == sub,
            Package.category_name == cat,
            Package.status == "1",
            Package.id != pkg.id,
            Package.start_date.isnot(None),
            cast(Package.start_date, Date) > old_end,
        )
        .order_by(Package.start_date.asc(), Package.id.asc())
        .all()
    )
    moved = 0
    cursor = new_end
    for row in followers:
        old_start = _as_date(row.start_date)
        old_end_row = _as_date(row.end_date)
        if old_start and old_end_row and old_end_row >= old_start:
            span_days = (old_end_row - old_start).days
        else:
            span_days = 14
        cursor = cursor + timedelta(days=PRICING_TIER_GAP_DAYS)
        row.start_date = cursor
        row.end_date = cursor + timedelta(days=span_days)
        cursor = _as_date(row.end_date) or cursor
        db.add(row)
        moved += 1
    return moved


def _has_registerable_package_today(db: Session, subscription_title: str) -> bool:
    """At least one package row open now or starting within PRICING_TIER_UPCOMING_DAYS (any category)."""
    today = date.today()
    rows = (
        db.query(Package)
        .filter(
            _subscription_name_eq(Package.subscription, subscription_title),
            Package.status == "1",
        )
        .all()
    )
    return any(_package_visible_for_registration(p, today) for p in rows)


def _has_registerable_package_for_batch(db: Session, batch: BatchDefinition) -> bool:
    return any(_has_registerable_package_today(db, sub) for sub in package_subscriptions_for_batch(batch))


def _count_current_packages_for_batch_delegate(
    db: Session,
    batch: BatchDefinition,
    delegate: str,
) -> int:
    total = 0
    for sub in package_subscriptions_for_batch(batch):
        total += _count_current_packages_for_delegate(db, sub, delegate)
    return total


def list_batches(db: Session) -> list[BatchDefinition]:
    """Active rows in batch_master (status=1) with a current package in `package` table — matches admin Batch Master."""
    rows = (
        _batch_query(db)
        .filter(BatchMaster.status == "1")
        .order_by(BatchMaster.display_order.desc(), BatchMaster.id.desc())
        .all()
    )
    out: list[BatchDefinition] = []
    for row in rows:
        title = (row.name or "").strip()
        if not title:
            continue
        bd = batch_definition_from_master_row(row)
        if not _has_registerable_package_for_batch(db, bd):
            continue
        out.append(bd)
    return out


def _count_current_packages_for_delegate(
    db: Session,
    subscription_title: str,
    delegate: str,
) -> int:
    today = date.today()
    return (
        db.query(Package.id)
        .filter(
            _subscription_name_eq(Package.subscription, subscription_title),
            Package.status == "1",
            Package.category_name.ilike(f"%{delegate}%"),
            or_(Package.start_date.is_(None), cast(Package.start_date, Date) <= today),
            _package_end_open_on_or_after(today),
        )
        .count()
    )


def build_registration_catalog(
    db: Session,
    *,
    include_inactive: bool = False,
) -> list[RegistrationCatalogItem]:
    has_brochure = _batch_has_column(db, "brochure_file")
    rows = _batch_query(db).order_by(BatchMaster.display_order.desc(), BatchMaster.id.desc()).all()
    brochure_map: dict[str, str] = {}
    if not has_brochure:
        keys = [_brochure_option_key((r.name or "").strip()) for r in rows if (r.name or "").strip()]
        if keys:
            opt_rows = db.query(Option).filter(Option.option_name.in_(keys)).all()
            brochure_map = {str(o.option_name): str(o.option_value or "").strip() for o in opt_rows}
    out: list[RegistrationCatalogItem] = []

    def _brochure_url(filename: Optional[str]) -> Optional[str]:
        value = (filename or "").strip()
        if not value:
            return None
        return f"/upload/brochures/{value}"

    for row in rows:
        bd = batch_definition_from_master_row(row)
        name = (row.name or "").strip()
        if not name:
            continue
        indian_count = _count_current_packages_for_batch_delegate(db, bd, "Indian")
        foreign_count = _count_current_packages_for_batch_delegate(db, bd, "Foreign")
        has_indian = indian_count > 0
        has_foreign = foreign_count > 0
        active_flag = (row.status or "0") == "1"
        issues: list[str] = []
        if not active_flag:
            issues.append("Batch is inactive in batch_master.")
        if not has_indian:
            issues.append("No active current package for Indian Delegates.")
        if not has_foreign:
            issues.append("No active current package for Foreign Delegates.")
        launch_ready = active_flag and has_indian and has_foreign
        if not include_inactive and not launch_ready:
            continue
        brochure_file = (
            getattr(row, "brochure_file", None)
            if has_brochure
            else brochure_map.get(_brochure_option_key(name))
        )
        out.append(
            RegistrationCatalogItem(
                batch_id=row.id,
                batch_slug=bd.slug,
                batch_name=name,
                registration_type=bd.registration_type,
                status=row.status or "0",
                brochure_url=_brochure_url(brochure_file),
                notice=(row.registration_fee_structure or "").strip() or None,
                description=(row.description or "").strip() or None,
                video_url=(row.video_url or "").strip() or None,
                video_resolved_url=(
                    f"/upload/batch_videos/{row.video_file}" if (row.video_file or "").strip() else None
                ),
                has_indian_package=has_indian,
                has_foreign_package=has_foreign,
                indian_package_count=indian_count,
                foreign_package_count=foreign_count,
                launch_ready=launch_ready,
                launch_issues=issues,
            )
        )
    return out


def _resolve_batch_by_slug_alias(db: Session, slug: str) -> Optional[Tuple[BatchMaster, BatchDefinition]]:
    """Map a legacy registration URL slug to batch_master after a batch rename."""
    key = f"batch_slug_alias::{(slug or '').strip().lower()}"
    opt = db.query(Option).filter(Option.option_name == key).first()
    if not opt or not (opt.option_value or "").strip().isdigit():
        return None
    row = db.query(BatchMaster).filter(BatchMaster.id == int(opt.option_value.strip())).first()
    if not row:
        return None
    return row, batch_definition_from_master_row(row)


def _find_registration_batch_row(
    db: Session, batch_slug: str
) -> Optional[Tuple[BatchMaster, BatchDefinition]]:
    raw = (batch_slug or "").strip().lower()
    wanted = REGISTRATION_SLUG_ALIASES.get(raw, raw)

    for slug in (wanted, raw):
        aliased = _resolve_batch_by_slug_alias(db, slug)
        if aliased:
            return aliased

    rows = _batch_query(db).filter(BatchMaster.status == "1").all()

    batch_name_for_slug = REGISTRATION_FEE_SLUG_TO_BATCH_NAME.get(wanted) or REGISTRATION_FEE_SLUG_TO_BATCH_NAME.get(raw)
    if batch_name_for_slug:
        target = batch_name_for_slug.strip().casefold()
        for row in rows:
            if (row.name or "").strip().casefold() == target:
                return row, batch_definition_from_master_row(row)

    for row in rows:
        bd = batch_definition_from_master_row(row)
        if bd.slug == wanted or bd.slug == raw:
            return row, bd
    pat = FEE_PAGE_SLUG_NAME_PATTERNS.get(wanted) or FEE_PAGE_SLUG_NAME_PATTERNS.get(raw)
    if pat:
        for row in rows:
            if pat.search(row.name or ""):
                return row, batch_definition_from_master_row(row)
    return None


def _get_batch_or_400(db: Session, batch_slug: str) -> BatchDefinition:
    found = _find_registration_batch_row(db, batch_slug)
    if not found:
        slugs = sorted(
            {batch_definition_from_master_row(r).slug for r in _batch_query(db).filter(BatchMaster.status == "1").all()}
        )
        raise HTTPException(
            status_code=400,
            detail=f"Unknown or inactive batch '{batch_slug}'. Active batch slugs: {slugs}",
        )
    _row, bd = found
    if not _has_registerable_package_for_batch(db, bd):
        raise HTTPException(
            status_code=400,
            detail="No active registration package for this batch at this time.",
        )
    return bd


def get_registration_batch(db: Session, batch_slug: str) -> BatchDefinition:
    """Public alias for routers (active batch_master row + slug match + package window)."""
    return _get_batch_or_400(db, batch_slug)


def _get_usd_rate(db: Session) -> float:
    row = db.query(Option).filter(Option.option_name == "usd_rate").first()
    try:
        return float((row.option_value if row else "85") or "85")
    except ValueError:
        return 85.0


def _is_india_country(db: Session, country_id: int) -> bool:
    row = db.query(Country).filter(Country.id == country_id).first()
    if not row:
        return True
    return (row.name or "").strip().lower() == "india"


def _registration_category_name(db: Session, country_id: int) -> str:
    """PHP register forms use category_name Indian Delegates / Foreign Delegates."""
    return "Indian Delegates" if _is_india_country(db, country_id) else "Foreign Delegates"


def _registration_category_for_packages(
    db: Session,
    country_id: int,
    registration_type: Optional[str] = None,
) -> str:
    """Delegate category for package list — prefer explicit registration_type over country row."""
    rt = (registration_type or "").strip().lower()
    if "indian" in rt:
        return "Indian Delegates"
    if "foreign" in rt:
        return "Foreign Delegates"
    return _registration_category_name(db, country_id)


def _attach_subscription_duration_siblings(
    db: Session,
    visible: list[Package],
    pkg_sub: str,
    category: str,
) -> list[Package]:
    """
    Batch 16-style subscription sales: when 6-month is on sale, also list 9- and 12-month
    rows for the same tier (same pricing window label), even if their start_date differs.
    """
    visible_sub = [p for p in visible if (p.plan_type or "").strip().lower() == "subscription"]
    if not visible_sub:
        return visible
    tier_keys = {_pricing_window_key(p) for p in visible_sub}
    by_id = {p.id: p for p in visible}
    siblings = (
        db.query(Package)
        .filter(
            _subscription_name_eq(Package.subscription, pkg_sub),
            Package.status == "1",
            Package.category_name == category,
        )
        .all()
    )
    for p in siblings:
        if (p.plan_type or "").strip().lower() != "subscription":
            continue
        if not int(p.duration_months or 0):
            continue
        if _pricing_window_key(p) not in tier_keys:
            continue
        by_id[p.id] = p
    return list(by_id.values())


def _resolve_package_or_400(db: Session, package_id: int) -> Package:
    pkg = db.query(Package).filter(Package.id == package_id).first()
    if not pkg:
        raise HTTPException(status_code=400, detail="Package not found")
    return pkg


def _assert_package_eligible_for_batch(
    db: Session,
    pkg: Package,
    batch: BatchDefinition,
    country_id: int,
) -> None:
    """Match Register.php save(): subscription, category_name, date window, status."""
    today = date.today()
    expected_cat = _registration_category_name(db, country_id)
    allowed_subs = {s.casefold() for s in package_subscriptions_for_batch(batch)}
    if (pkg.subscription or "").strip().casefold() not in allowed_subs:
        raise HTTPException(
            status_code=400,
            detail="Selected package does not match this batch.",
        )
    if (pkg.category_name or "").strip().casefold() != expected_cat.casefold():
        raise HTTPException(
            status_code=400,
            detail="Selected package does not match your country (Indian vs Foreign delegates).",
        )
    if (pkg.status or "") != "1":
        raise HTTPException(status_code=400, detail="Package is not active.")
    def _as_date(val: object) -> date:
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, date):
            return val
        raise HTTPException(status_code=400, detail="Invalid package date in database.")
    if pkg.start_date is not None:
        start_d = _as_date(pkg.start_date)
        if start_d is not None and start_d > today and not _shows_all_pricing_tiers(batch):
            raise HTTPException(
                status_code=400,
                detail="This package is not yet active.",
            )
    # Subscription plans are time-bound by user registration date + duration_months.
    # For one-time plans, package end_date still controls sale-window expiry.
    if (pkg.plan_type or "one_time").strip().lower() != "subscription":
        if pkg.end_date is not None:
            end_d = _as_date(pkg.end_date)
            if end_d < today:
                raise HTTPException(
                    status_code=400,
                    detail="This package has expired.",
                )


def _package_date_value(val: object) -> date:
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    raise TypeError("package start/end must be date-like")


def _to_display_usd(amount: float, usd_rate: float) -> float:
    """
    Normalize foreign amount for UI/payment responses.
    - Some legacy rows store foreign pricing in INR-equivalent (large numbers).
    - Newer rows store foreign pricing directly in USD (small numbers like 260/365).
    """
    value = float(amount or 0.0)
    if value <= 0:
        return 0.0
    if value >= 1000:
        return round(value / usd_rate, 2)
    return round(value, 2)


def _add_months(dt: datetime, months: int) -> datetime:
    year = dt.year + (dt.month - 1 + months) // 12
    month = (dt.month - 1 + months) % 12 + 1
    day = min(dt.day, monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def build_subscription_window(start_at: datetime, duration_months: Optional[int]) -> tuple[datetime, datetime]:
    months = int(duration_months or 0)
    if months <= 0:
        months = 12
    end_at = _add_months(start_at, months)
    return start_at, end_at


def activate_user_subscription(
    db: Session,
    *,
    user_id: int,
    batch_slug: str,
    package_id: int,
    duration_months: Optional[int],
    activated_at: datetime,
) -> UserSubscription:
    # Keep one active entitlement per user+batch.
    rows = (
        db.query(UserSubscription)
        .filter(
            UserSubscription.user_id == user_id,
            UserSubscription.batch_slug == (batch_slug or ""),
            UserSubscription.status == "active",
        )
        .all()
    )
    for row in rows:
        row.status = "expired"
        db.add(row)
    start_at, end_at = build_subscription_window(activated_at, duration_months)
    sub = UserSubscription(
        user_id=user_id,
        batch_slug=(batch_slug or ""),
        package_id=package_id,
        duration_months=int(duration_months or 0) or None,
        start_at=start_at,
        end_at=end_at,
        status="active",
        auto_renew="0",
    )
    db.add(sub)
    return sub


def extend_active_subscription(
    db: Session,
    *,
    user_id: int,
    batch_slug: str,
    extend_months: int,
    activated_at: datetime,
    extension_base_date: datetime | None = None,
    package_id: int | None = None,
) -> UserSubscription:
    active = (
        db.query(UserSubscription)
        .filter(
            UserSubscription.user_id == user_id,
            UserSubscription.batch_slug == (batch_slug or ""),
            UserSubscription.status == "active",
        )
        .order_by(UserSubscription.end_at.desc())
        .first()
    )
    months = int(extend_months or 0)
    if extension_base_date:
        new_end = _add_months(extension_base_date, months)
    elif active and active.end_at:
        base = active.end_at if active.end_at > activated_at else activated_at
        new_end = _add_months(base, months)
    else:
        new_end = _add_months(activated_at, months)

    if not active:
        sub = UserSubscription(
            user_id=user_id,
            batch_slug=(batch_slug or ""),
            package_id=package_id,
            duration_months=months or None,
            start_at=activated_at,
            end_at=new_end,
            status="active",
            auto_renew="0",
        )
        db.add(sub)
        return sub

    active.end_at = new_end
    if active.duration_months:
        active.duration_months = int(active.duration_months) + months
    else:
        active.duration_months = months
    db.add(active)
    return active


def _narrow_packages_to_single_pricing_tier(packages: list[Package]) -> list[Package]:
    """Return one row when several `package` windows overlap the same calendar day.

    Tier rows should use non-overlapping [start_date, end_date] per subscription/category.
    If two rows both contain *today* (e.g. Extended row shares the same open-ended window),
    pick the row that **ends soonest** first (the current short discount window, e.g. Early Bird
    through 15 Apr vs Extended through a later date), then **latest start_date**, then **lowest id**.
    """
    if len(packages) <= 1:
        return packages

    def sort_key(p: Package) -> tuple:
        s = _package_date_value(p.start_date)
        e = _package_date_value(p.end_date)
        return (e.toordinal(), -s.toordinal(), p.id)

    return [min(packages, key=sort_key)]


def query_active_packages_for_registration(
    db: Session,
    batch: BatchDefinition,
    country_id: int,
    *,
    registration_type: Optional[str] = None,
) -> list[Package]:
    """Packages in active (or soon-starting) pricing windows — all tiers, not only 6/9/12 subscription rows."""
    today = date.today()
    category = _registration_category_for_packages(db, country_id, registration_type)
    by_id: dict[int, Package] = {}
    for pkg_sub in package_subscriptions_for_batch(batch):
        q = (
            db.query(Package)
            .filter(
                _subscription_name_eq(Package.subscription, pkg_sub),
                Package.status == "1",
                Package.category_name == category,
            )
            .order_by(Package.start_date.asc(), Package.id.asc())
        )
        pkgs_raw = q.all()
        if _shows_all_pricing_tiers(batch):
            visible = list(pkgs_raw)
        else:
            visible = [p for p in pkgs_raw if _package_visible_for_registration(p, today)]
        visible = _attach_subscription_duration_siblings(db, visible, pkg_sub, category)
        for p in visible:
            by_id[p.id] = p
    pkgs = sorted(by_id.values(), key=lambda p: (_as_date(p.start_date) or date.min, p.id))
    if not pkgs:
        return []

    sub_rows = [p for p in pkgs if (p.plan_type or "").strip().lower() == "subscription"]
    tier_rows = sub_rows if sub_rows else pkgs
    windows = _group_packages_by_pricing_window(tier_rows)
    out: list[Package] = []
    for group in windows:
        out.extend(group["packages"])  # type: ignore[arg-type]
    if out:
        return sorted(out, key=lambda p: (_as_date(p.start_date) or date.min, p.id))
    if sub_rows:
        return sorted(sub_rows, key=lambda x: (int(x.duration_months or 0), x.id))
    if _shows_all_pricing_tiers(batch) and len(pkgs) > 1:
        return _sort_fee_table_columns(pkgs)
    return _narrow_packages_to_single_pricing_tier(pkgs)


def _calendar_early_bird_active(today: Optional[date] = None) -> bool:
    d = today or date.today()
    return EARLY_BIRD_FIRST_DAY <= d.day <= EARLY_BIRD_LAST_DAY


def _subscription_allowed_for_coupon(subscriptions_field: Optional[str], subscription: str) -> bool:
    raw = (subscriptions_field or "").strip()
    if not raw:
        return True
    allowed = {x.strip().casefold() for x in raw.split(",") if x.strip()}
    return (subscription or "").strip().casefold() in allowed


def _assigned_email_matches(assigned: Optional[str], email: Optional[str]) -> bool:
    want = (assigned or "").strip()
    if not want:
        return True
    if not (email or "").strip():
        return False
    return email.strip().casefold() == want.casefold()


def _validate_coupon_row(
    db: Session,
    coupon_code: Optional[str],
    batch: BatchDefinition,
    *,
    email: Optional[str],
    subscription: str,
) -> Optional[CouponMaster]:
    code = (coupon_code or "").strip()
    if not code:
        return None
    has_pct = _coupon_has_column(db, "discount_percent")
    has_amt = _coupon_has_column(db, "discount_amount")
    has_email = _coupon_has_column(db, "assigned_email")
    coupon = _coupon_query(db).filter(CouponMaster.code == code, CouponMaster.status == "0").first()
    if not coupon:
        raise HTTPException(status_code=400, detail="Invalid or already-used coupon")
    pct = float(getattr(coupon, "discount_percent", 0.0) if has_pct else 0.0)
    amt = float(getattr(coupon, "discount_amount", 0.0) if has_amt else 0.0)
    if (pct > 0 and amt > 0) or (pct <= 0 and amt <= 0):
        raise HTTPException(status_code=400, detail="Coupon has invalid discount configuration")
    assigned_email = (coupon.assigned_email if has_email else None)
    if not _assigned_email_matches(assigned_email, email):
        raise HTTPException(status_code=400, detail="This coupon is not valid for this email address")
    return coupon


def _scale_line_items(
    gross: float, gst_percent: float, gst_amount: float, total: float, factor: float
) -> tuple[float, float, float, float]:
    f = max(0.0, min(1.0, float(factor)))
    g = round(gross * f, 2)
    ga = round(gst_amount * f, 2)
    t = round(total * f, 2)
    return g, gst_percent, ga, t


def compute_registration_amount(
    db: Session,
    package: Package,
    batch: BatchDefinition,
    country_id: int,
    *,
    coupon_code: Optional[str] = None,
    email: Optional[str] = None,
    subscription: str,
    reserve_coupon: bool = False,
) -> PayableAmountResponse:
    sub = (subscription or "").strip() or (package.subscription or batch.title or "").strip()
    gross, gst_percent, gst_amount, total = _resolve_package_line_amounts(package)
    is_india = _is_india_country(db, country_id)

    is_old_student = False
    if email and sub:
        old = (
            db.query(User.id)
            .filter(
                User.email == email.strip().lower(),
                User.subscription != sub,
                User.payment_status == "Credit",
            )
            .first()
        )
        if old:
            is_old_student = True

    promo_active = _package_promo_discount_active(package)
    early_bird_applied = promo_active and float(package.discount_percentage or 0) > 0
    early_bird_percent = float(package.discount_percentage or 0) if early_bird_applied else 0.0
    discount_percent_used = 0.0
    coupon_applied = False
    coupon_row: Optional[CouponMaster] = None
    monetary_discount = 0.0

    if is_old_student:
        rate = OLD_STUDENT_RATE_INR if is_india else OLD_STUDENT_RATE_USD
        gross = float(rate["gross"])
        gst_percent = float(rate["gst_pct"])
        gst_amount = float(rate["gst_amt"])
        total = float(rate["total"])
        if (coupon_code or "").strip():
            raise HTTPException(status_code=400, detail="Coupons are not applicable with old-student pricing")
    else:
        # Package rows now carry the final payable slab amount; do not auto-apply
        # package/calendar discounts again during registration.
        coupon_row = _validate_coupon_row(
            db, coupon_code, batch, email=email, subscription=sub
        )
        if coupon_row:
            pct = float(getattr(coupon_row, "discount_percent", 0.0) or 0.0)
            amt = float(getattr(coupon_row, "discount_amount", 0.0) or 0.0)
            if pct > 0:
                discount_percent_used = pct
                f = 1.0 - pct / 100.0
                before = total
                gross, gst_percent, gst_amount, total = _scale_line_items(
                    gross, gst_percent, gst_amount, total, f
                )
                monetary_discount = max(0.0, round(before - total, 2))
            else:
                before_total = total
                total = max(total - amt, 0.0)
                monetary_discount = max(0.0, round(before_total - total, 2))
            coupon_applied = True
            if reserve_coupon:
                coupon_row.status = "1"
                db.add(coupon_row)

    if is_india:
        currency = "INR"
    else:
        if not is_old_student:
            usd_rate = _get_usd_rate(db)
            currency = "USD"
            gross = _to_display_usd(gross, usd_rate)
            gst_amount = _to_display_usd(gst_amount, usd_rate)
            total = _to_display_usd(total, usd_rate)
            monetary_discount = _to_display_usd(monetary_discount, usd_rate)
        else:
            currency = "USD"

    return PayableAmountResponse(
        currency_name=currency,
        gross_amount=gross,
        gst_percentage=gst_percent,
        gst_amount=gst_amount,
        discount_amount=float(monetary_discount if not is_old_student else 0.0),
        total_amount=total,
        coupon_applied=coupon_applied,
        coupon_code=(coupon_row.code if coupon_row and coupon_applied else None),
        early_bird_applied=early_bird_applied,
        early_bird_percent=early_bird_percent,
        discount_percent_used=discount_percent_used,
    )


def get_payable_amount(db: Session, payload: PayableAmountRequest) -> PayableAmountResponse:
    batch = _get_batch_or_400(db, payload.batch_slug)
    package = _resolve_package_or_400(db, payload.package_id)
    _assert_package_eligible_for_batch(db, package, batch, payload.country_id)
    sub = (payload.subscription or "").strip() or (package.subscription or batch.title or "").strip()
    return compute_registration_amount(
        db,
        package,
        batch,
        payload.country_id,
        coupon_code=payload.coupon_code,
        email=(payload.email or "").strip() or None,
        subscription=sub,
        reserve_coupon=False,
    )


def _user_exists_by_email(db: Session, email: str) -> bool:
    normalized = (email or "").strip().lower()
    if not normalized:
        return False
    row = (
        db.query(User.id)
        .filter(func.lower(func.trim(User.email)) == normalized)
        .first()
    )
    return row is not None


def check_registration_identity(db: Session, email: str, contact_number: str) -> dict:
    """Return whether email is free for a new registration (phone may be reused)."""
    _ = contact_number  # kept for API compatibility; phone duplicates are allowed
    email_taken = _user_exists_by_email(db, email)
    if email_taken:
        message = "This email is already registered. Please log in or use a different email."
    else:
        message = None
    return {
        "available": not email_taken,
        "email_taken": email_taken,
        "phone_taken": False,
        "message": message,
    }


def assert_registration_identity_available(db: Session, email: str, contact_number: str) -> None:
    result = check_registration_identity(db, email, contact_number)
    if not result["available"]:
        raise HTTPException(status_code=409, detail=result["message"] or "Identity already registered")


def check_old_student_discount(
    db: Session, email: str, subscription: str
) -> object:
    """Check if user previously paid for a different batch (PHP parity)."""
    from app.routers.registration import OldStudentCheckResponse

    exists = (
        db.query(User.id)
        .filter(
            User.email == email.strip().lower(),
            User.subscription != subscription,
            User.payment_status == "Credit",
        )
        .first()
    )
    if exists:
        return OldStudentCheckResponse(
            is_old_student=True,
            discount_inr=OLD_STUDENT_RATE_INR["total"],
            discount_usd=OLD_STUDENT_RATE_USD["total"],
        )
    return OldStudentCheckResponse(is_old_student=False)


def _validate_registration_payload(db: Session, payload: RegistrationInitRequest) -> BatchDefinition:
    batch = _get_batch_or_400(db, payload.batch_slug)
    if batch.requires_document and not (payload.document_file or "").strip():
        raise HTTPException(status_code=400, detail="Document is required for this batch.")
    if len((payload.contact_number or "").strip()) < 10:
        raise HTTPException(status_code=400, detail="Invalid contact number")
    # Password must be exactly 8 characters (PHP parity)
    if len(payload.password or "") != 8:
        raise HTTPException(status_code=400, detail="Password must be exactly 8 characters")

    assert_registration_identity_available(db, payload.email, payload.contact_number)
    return batch


def initialize_registration(
    db: Session, payload: RegistrationInitRequest
) -> RegistrationInitResponse:
    batch = _validate_registration_payload(db, payload)
    batch_row, _ = get_batch_master_row_by_slug(db, payload.batch_slug)
    package = _resolve_package_or_400(db, payload.package_id)
    _assert_package_eligible_for_batch(db, package, batch, payload.country_id)

    # Always store canonical batch_master.name on users.subscription (matches PHP hidden fields).
    canonical_subscription = (batch_row.name or "").strip() or package_subscription_for_batch(batch)

    # Auto-set registration_type based on country (PHP parity)
    if _is_india_country(db, payload.country_id):
        reg_type = "Indian Delegates"
    else:
        reg_type = "Foreign Delegates"

    amount = compute_registration_amount(
        db,
        package,
        batch,
        payload.country_id,
        coupon_code=payload.coupon_code,
        email=payload.email.strip().lower(),
        subscription=payload.subscription.strip(),
        reserve_coupon=True,
    )
    request_id = uuid.uuid4().hex
    # Razorpay order should always be in INR; keep USD display amounts on user rows.
    payable_for_gateway = float(amount.total_amount or 0.0)
    gateway_currency = (amount.currency_name or "INR").upper()
    if gateway_currency == "USD":
        usd_rate = _get_usd_rate(db)
        payable_for_gateway = round(payable_for_gateway * float(usd_rate or 1.0), 2)
        gateway_currency = "INR"

    # DB column is NOT NULL; admin UI uses '0'=pending, '1'=approved, '2'=deny (see Users.php).
    doc_status = 0 if batch.requires_document else 1

    applied_code = amount.coupon_code if amount.coupon_applied else None

    user = User(
        registration_type=reg_type,
        subscription=canonical_subscription,
        title=payload.title,
        name=payload.name,
        email=payload.email.strip().lower(),
        password=php_password_for_db(payload.password),
        contact_number=payload.contact_number,
        hospital=payload.hospital,
        qualification=payload.qualification,
        speciality=payload.speciality,
        country_id=payload.country_id,
        state=payload.state,
        city=payload.city,
        pin_code=payload.pin_code,
        document_file=payload.document_file,
        document_file_2="",
        document_file_status=doc_status,
        package_id=payload.package_id,
        currency_name=amount.currency_name,
        gross_amount=amount.gross_amount,
        gst_percentage=amount.gst_percentage,
        gst_amount=amount.gst_amount,
        total_amount=amount.total_amount,
        coupon_code=applied_code,
        payment_request_id=request_id,
        payment_status="Pending",
        payment_type="Online",
        approve="0",
        verify="1",
        is_login="0",
        login_token="",
        password_hash="",
        role="",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(user)
    db.flush()

    txn = RegistrationPaymentTxn(
        request_id=request_id,
        user_id=user.id,
        batch_slug=batch.slug,
        package_id=payload.package_id,
        amount=payable_for_gateway,
        currency=gateway_currency,
        coupon_code=applied_code,
        gateway_status="created",
        is_finalized="0",
    )
    db.add(txn)
    db.commit()

    return RegistrationInitResponse(
        registration_id=user.id,
        request_id=request_id,
        payment_status="Pending",
        amount=amount,
    )


# ── Fee structure for public registration info pages (all tiers from `package`) ──


def _scale_pkg_for_fee_display(pkg: Package, usd_rate: float, is_inr: bool) -> Tuple[float, float, float]:
    gross, _gst_pct, gst_amt, total = _resolve_package_line_amounts(pkg)
    if not is_inr:
        gross = _to_display_usd(gross, usd_rate)
        gst_amt = _to_display_usd(gst_amt, usd_rate)
        total = _to_display_usd(total, usd_rate)
    return gross, gst_amt, total


def _fee_table_tier_rank(p: Package) -> int:
    """Consistent column order: Early Bird → Early Bird Extended → Regular."""
    n = (p.name or "").strip().lower()
    if "early bird extended" in n or ("early" in n and "extended" in n):
        return 2
    if "early bird" in n:
        return 0
    if "regular" in n:
        return 3
    return 1


def _sort_fee_table_columns(columns: list[Package]) -> list[Package]:
    def sort_key(p: Package) -> tuple[int, int, int]:
        start = _as_date(p.start_date) or date.min
        return (_fee_table_tier_rank(p), start.toordinal(), p.id)

    return sorted(columns, key=sort_key)


BATCH_COURSE_MONTHS_DEFAULT = 6


def course_end_from_batch_start(batch_start: date, months: int = BATCH_COURSE_MONTHS_DEFAULT) -> date:
    """Last calendar day of batch access (batch_start + N months, same day-of-month rules as subscriptions)."""
    dt = datetime.combine(batch_start, datetime.min.time())
    return _add_months(dt, months).date()


def set_batch_course_access_dates(
    db: Session,
    subscription: str,
    course_start: date,
    course_months: int = BATCH_COURSE_MONTHS_DEFAULT,
) -> dict:
    """
    Set batch_start_date on all active packages for video/mock access (batch_start + course_months).
    Does not change registration tier start_date / end_date (Early Bird / Regular sale windows).
    """
    sub = (subscription or "").strip()
    if not sub:
        raise HTTPException(status_code=422, detail="subscription is required")
    rows = (
        db.query(Package)
        .filter(_subscription_name_eq(Package.subscription, sub), Package.status == "1")
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"No active packages for subscription {sub!r}")

    course_end = course_end_from_batch_start(course_start, course_months)
    start_dt = datetime.combine(course_start, datetime.min.time())
    for p in rows:
        p.batch_start_date = start_dt
        db.add(p)
    db.commit()
    return {
        "subscription": sub,
        "course_start": course_start.isoformat(),
        "course_end": course_end.isoformat(),
        "course_months": course_months,
        "packages_updated": len(rows),
    }


def apply_batch_course_window(
    db: Session,
    subscription: str,
    batch_start: date,
    course_months: int = BATCH_COURSE_MONTHS_DEFAULT,
) -> dict:
    """
    Set batch_start_date on all active packages for a batch subscription and extend the Regular tier
    registration window through batch_start + course_months (CCM one-time batches).
    """
    from datetime import timedelta

    sub = (subscription or "").strip()
    if not sub:
        raise HTTPException(status_code=422, detail="subscription is required")
    rows = (
        db.query(Package)
        .filter(_subscription_name_eq(Package.subscription, sub), Package.status == "1")
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"No active packages for subscription {sub!r}")

    batch_end = course_end_from_batch_start(batch_start, course_months)
    tier_ends: list[date] = []
    for p in rows:
        p.batch_start_date = datetime.combine(batch_start, datetime.min.time())
        db.add(p)
        name = (p.name or "").strip().lower()
        if "regular" not in name:
            end = _as_date(p.end_date)
            if end:
                tier_ends.append(end)

    latest_non_regular = max(tier_ends) if tier_ends else batch_start
    regular_start = latest_non_regular + timedelta(days=PRICING_TIER_GAP_DAYS)
    if regular_start < batch_start:
        regular_start = batch_start

    regular_rows = [p for p in rows if "regular" in (p.name or "").strip().lower()]
    for p in regular_rows:
        p.start_date = regular_start
        p.end_date = datetime.combine(batch_end, datetime.min.time())
        db.add(p)
        _sync_tier_dates_across_delegate_categories(
            db, p, start_date=regular_start, end_date=batch_end
        )

    db.commit()
    return {
        "subscription": sub,
        "batch_start": batch_start.isoformat(),
        "batch_end": batch_end.isoformat(),
        "regular_tier_start": regular_start.isoformat(),
        "packages_updated": len(rows),
        "regular_tiers_updated": len(regular_rows),
        "course_months": course_months,
    }


def sync_package_tiers_from_reference(
    db: Session,
    *,
    reference_subscription: str,
    target_subscription: str,
    tier_names: tuple[str, ...] = ("Early Bird", "Early Bird Extended", "Regular"),
) -> int:
    """
    Copy gross/GST/discount/date fields from reference batch packages to target (same tier + category).
    Used to keep CCM Batch 3 aligned with CCM Batch 2.
    """
    updated = 0
    ref_sub = reference_subscription.strip()
    tgt_sub = target_subscription.strip()
    for tier in tier_names:
        for category in ("Indian Delegates", "Foreign Delegates"):
            ref_pkg = (
                db.query(Package)
                .filter(
                    _subscription_name_eq(Package.subscription, ref_sub),
                    Package.status == "1",
                    Package.category_name == category,
                    Package.name == tier,
                )
                .first()
            )
            if not ref_pkg:
                continue
            tgt_pkg = (
                db.query(Package)
                .filter(
                    _subscription_name_eq(Package.subscription, tgt_sub),
                    Package.status == "1",
                    Package.category_name == category,
                    Package.name == tier,
                )
                .first()
            )
            if not tgt_pkg:
                continue
            for field in (
                "gross_amount",
                "gst_percentage",
                "gst_amount",
                "total_amount",
                "discount_percentage",
                "discounted_amount",
                "start_date",
                "end_date",
                "discount_start_date",
                "discount_end_date",
                "plan_type",
                "duration_months",
            ):
                setattr(tgt_pkg, field, getattr(ref_pkg, field))
            db.add(tgt_pkg)
            updated += 1
    return updated


def _package_for_fee_table_column(p: Package, today: date) -> bool:
    """Include active tiers on the public fee page (current, upcoming, not expired)."""
    end = _as_date(p.end_date)
    if end is not None and end < today:
        return False
    return True


def _query_packages_for_fee_table(
    db: Session,
    subscription: str,
    *,
    indian: bool,
    subscriptions: Optional[list[str]] = None,
    batch: Optional[BatchDefinition] = None,
) -> List[Package]:
    """
    Fee table columns: one_time → one column per pricing tier (Early Bird, Regular, …).
    subscription → one column per duration (6 / 9 / 12 months) so Batch 16 shows all plans.
    """
    needle = "Indian" if indian else "Foreign"
    today = date.today()
    subs = subscriptions if subscriptions else [subscription.strip()]
    by_id: dict[int, Package] = {}
    for sub in subs:
        sub = (sub or "").strip()
        if not sub:
            continue
        for p in (
            db.query(Package)
            .filter(
                _subscription_name_eq(Package.subscription, sub),
                Package.status == "1",
                Package.category_name.ilike(f"%{needle}%"),
            )
            .order_by(Package.start_date.asc(), Package.id.asc())
            .all()
        ):
            by_id[p.id] = p
    rows = sorted(by_id.values(), key=lambda p: (_as_date(p.start_date) or date.min, p.id))
    category = "Indian Delegates" if indian else "Foreign Delegates"
    columns: list[Package] = []
    seen: set[int] = set()
    for sub in subs:
        sub = (sub or "").strip()
        if not sub:
            continue
        tier_rows = [p for p in rows if (p.subscription or "").strip().casefold() == sub.casefold()]
        if not (batch and _shows_all_pricing_tiers(batch)):
            tier_rows = [p for p in tier_rows if _package_for_fee_table_column(p, today)]
        tier_rows = _attach_subscription_duration_siblings(db, tier_rows, sub, category)
        for p in tier_rows:
            if p.id not in seen:
                seen.add(p.id)
                columns.append(p)
    columns = sorted(columns, key=lambda p: (_as_date(p.start_date) or date.min, p.id))
    if not columns:
        return []

    sub_rows = [p for p in columns if (p.plan_type or "").strip().lower() == "subscription"]
    if sub_rows:
        return sorted(sub_rows, key=lambda p: (int(p.duration_months or 0), p.id))

    if len(columns) > 1:
        return _sort_fee_table_columns(columns)
    return columns


def _fee_column_header(p: Package) -> str:
    """Column title on public fee page."""
    plan = (p.plan_type or "one_time").strip().lower()
    if plan == "subscription":
        months = int(p.duration_months or 0)
        if months == 12:
            title = "12 Months (1 Year)"
        elif months > 0:
            title = f"{months} Months"
        else:
            title = "Subscription"
        tier = _tier_label_from_package(p)
        if tier and tier.casefold() != title.casefold():
            return f"{title}\n{tier}"
        return title
    return _tier_header_from_package(p)


def _format_money_fee_cell(amount: float, is_inr: bool) -> str:
    if is_inr:
        return f"{int(round(amount)):,}"
    x = round(amount, 2)
    if abs(x - round(x)) < 1e-6:
        return str(int(round(x)))
    return f"{x:.2f}"


def _tier_header_from_package(p: Package) -> str:
    name = (p.name or "").strip()
    discount_pct = float(p.discount_percentage or 0) if _package_promo_discount_active(p) else 0.0
    pct_str = (
        f"{int(discount_pct)}"
        if discount_pct == int(discount_pct)
        else f"{discount_pct:g}"
    )
    if name and discount_pct > 0:
        # Override the percentage in the stored name with the live `discount_percentage`
        # value so admin edits to the discount field flow into the column header.
        if re.search(r"\d+(?:\.\d+)?\s*%", name):
            name = re.sub(r"\d+(?:\.\d+)?\s*%", f"{pct_str}%", name, count=1)
        else:
            # Name has no percent token — append the live discount so foreign-only
            # rows (e.g. "Early bird extend") still surface their actual discount.
            name = f"{name} - {pct_str}% DISCOUNT"
    if len(name) >= 4:
        return name
    try:
        s = _package_date_value(p.start_date)
        e = _package_date_value(p.end_date)
        return f"{s.strftime('%d %b %Y')} – {e.strftime('%d %b %Y')}"
    except (TypeError, ValueError):
        return "Tier"


def _plan_badge_from_package(p: Package) -> str:
    plan = (p.plan_type or "one_time").strip().lower()
    if plan == "subscription":
        months = int(p.duration_months or 0)
        if months > 0:
            return f"Subscription ({months}M)"
        return "Subscription"
    return "One-time"


def get_batch_master_row_by_slug(db: Session, batch_slug: str) -> Tuple[BatchMaster, BatchDefinition]:
    found = _find_registration_batch_row(db, batch_slug)
    if not found:
        rows = _batch_query(db).filter(BatchMaster.status == "1").all()
        slugs = sorted({batch_definition_from_master_row(r).slug for r in rows})
        raise HTTPException(
            status_code=404,
            detail=(
                f"Batch not found for slug '{batch_slug}'. "
                f"Check batch_master.name (or add a pattern in FEE_PAGE_SLUG_NAME_PATTERNS). Active slugs: {slugs}"
            ),
        )
    return found


def build_fee_structure_response(db: Session, batch_slug: str) -> FeeStructureResponse:
    """Build fee table from all active `package` rows (any date window)."""
    row, bd = get_batch_master_row_by_slug(db, batch_slug)
    subs = package_subscriptions_for_batch(bd)
    primary_sub = package_subscription_for_batch(bd)
    usd_rate = _get_usd_rate(db)
    ind_pkgs = _query_packages_for_fee_table(db, primary_sub, indian=True, subscriptions=subs, batch=bd)
    for_pkgs = _query_packages_for_fee_table(db, primary_sub, indian=False, subscriptions=subs, batch=bd)
    if not ind_pkgs and not for_pkgs:
        raise HTTPException(
            status_code=404,
            detail="No fee packages found for this batch (check subscription name on package rows).",
        )

    n_cols = max(len(ind_pkgs), len(for_pkgs))

    headers: List[str] = []
    for i in range(n_cols):
        p = ind_pkgs[i] if i < len(ind_pkgs) else (for_pkgs[i] if i < len(for_pkgs) else None)
        headers.append(_fee_column_header(p) if p else "—")

    def build_block(pkgs: List[Package], is_inr: bool, group_label: str) -> FeeStructureBlock:
        if not pkgs:
            dash = ["—"] * n_cols
            return FeeStructureBlock(
                group_label=group_label,
                registration_fee=dash,
                discount=dash,
                total=dash,
                total_payable=dash,
                package_ids=[],
                plan_badges=dash,
                column_headers=[""] * n_cols,
            )
        scaled: List[Tuple[Package, float, float, float]] = [
            (p, *_scale_pkg_for_fee_display(p, usd_rate, is_inr)) for p in pkgs
        ]
        reg: List[str] = []
        disc: List[str] = []
        tot: List[str] = []
        pay: List[str] = []
        package_ids: List[int] = []
        plan_badges: List[str] = []
        col_headers: List[str] = []
        for p, g, _gst_amt, total in scaled:
            base = float(g)
            gst_pct = int(float(p.gst_percentage or 18))
            if _package_promo_discount_active(p):
                pct_disc = float(p.discount_percentage or 0)
                disc_amt = float(p.discounted_amount or 0)
                if pct_disc > 0 and disc_amt < 0.5:
                    disc_amt = round(base * pct_disc / 100.0, 2)
                taxable = max(0.0, round(base - disc_amt, 2))
            else:
                disc_amt = 0.0
                taxable = base

            reg.append(_format_money_fee_cell(base, is_inr))
            disc.append("0" if disc_amt < 0.5 else _format_money_fee_cell(disc_amt, is_inr))
            tot.append(f"{_format_money_fee_cell(taxable, is_inr)} + {gst_pct}% GST")
            pay.append(_format_money_fee_cell(total, is_inr))
            package_ids.append(int(p.id))
            plan_badges.append(_plan_badge_from_package(p))
            col_headers.append(_fee_column_header(p))
        while len(reg) < n_cols:
            reg.append("—")
            disc.append("—")
            tot.append("—")
            pay.append("—")
            package_ids.append(0)
            plan_badges.append("—")
            col_headers.append("")
        return FeeStructureBlock(
            group_label=group_label,
            registration_fee=reg,
            discount=disc,
            total=tot,
            total_payable=pay,
            package_ids=package_ids,
            plan_badges=plan_badges,
            column_headers=col_headers,
        )

    notice = (row.registration_fee_structure or "").strip() or None
    batch_name = (row.name or bd.title or "").strip()
    page_title = f"{batch_name} Registration"
    brochure_value = (getattr(row, "brochure_file", None) or "").strip()
    if not brochure_value:
        opt = (
            db.query(Option)
            .filter(Option.option_name == _brochure_option_key(batch_name))
            .first()
        )
        brochure_value = (str(opt.option_value).strip() if opt and opt.option_value else "")
    brochure_url = f"/upload/brochures/{brochure_value}" if brochure_value else None

    return FeeStructureResponse(
        batch_slug=batch_slug,
        batch_name=batch_name,
        page_title=page_title,
        breadcrumb_tail=batch_name,
        notice=notice,
        description=(row.description or "").strip() or None,
        brochure_url=brochure_url,
        video_url=(row.video_url or "").strip() or None,
        video_resolved_url=(
            f"/upload/batch_videos/{row.video_file}" if (row.video_file or "").strip() else None
        ),
        column_headers=headers,
        indian=build_block(ind_pkgs, True, "Indian Delegates (INR)"),
        foreign=build_block(for_pkgs, False, "Foreign Delegates (USD)"),
    )
