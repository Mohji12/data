"""Cascade batch name changes across string-based DB references."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, inspect
from sqlalchemy.orm import Session

from app.models import (
    BatchMaster,
    CouponMaster,
    FolderMaster,
    Option,
    Package,
    QuizExam,
    RegistrationPaymentTxn,
    User,
    UserPackagePayment,
    UserSubscription,
    Video,
)
from app.services.access import (
    batch_slug,
    certificate_option_key,
    extension_option_key,
    get_option_value,
)
from app.services.batch_match import find_in_set_sql

logger = logging.getLogger(__name__)

GLOBAL_ACCESS_OPTIONS = (
    "access_quiz_link",
    "access_video_library_link",
    "access_download_certificate",
)

CERTIFICATE_OPTION_KINDS = ("enabled", "batch_label", "fixed_date", "course_line", "program_line", "show_date", "name_size")
EXTENSION_OPTION_KINDS = (
    "enabled",
    "gross_amount",
    "gst_percentage",
    "gst_amount",
    "total_amount",
    "months",
    "start_date",
    "end_date",
    "base_date",
)

BATCH_SLUG_ALIAS_PREFIX = "batch_slug_alias::"


def batch_slug_alias_option_key(slug: str) -> str:
    return f"{BATCH_SLUG_ALIAS_PREFIX}{(slug or '').strip().lower()}"


def brochure_option_key(batch_name: str) -> str:
    return f"batch_brochure::{(batch_name or '').strip().casefold()}"


def replace_csv_token(csv: str | None, old: str, new: str) -> str:
    """Replace one comma-separated token (case-insensitive exact match)."""
    old_cf = (old or "").strip().casefold()
    new_val = (new or "").strip()
    if not old_cf:
        return (csv or "").strip()
    parts = [(p or "").strip() for p in (csv or "").split(",")]
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.casefold() == old_cf:
            out.append(new_val)
        else:
            out.append(part)
    return ",".join(out)


def _csv_token_present(csv: str | None, token: str) -> bool:
    token_cf = (token or "").strip().casefold()
    if not token_cf:
        return False
    for part in (csv or "").split(","):
        if (part or "").strip().casefold() == token_cf:
            return True
    return False


def _coupon_has_subscriptions_column(db: Session) -> bool:
    bind = db.get_bind()
    cols = inspect(bind).get_columns("coupon_master")
    return any((c.get("name") or "").lower() == "subscriptions" for c in cols)


def _ensure_no_name_collision(db: Session, new_name: str, batch_id: int) -> None:
    target = (new_name or "").strip()
    if not target:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Batch name is required.")
    existing = (
        db.query(BatchMaster.id)
        .filter(
            func.lower(func.trim(BatchMaster.name)) == target.lower(),
            BatchMaster.id != batch_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Another batch already uses the name “{target}”.",
        )


def _upsert_option(db: Session, option_name: str, option_value: str, *, dry_run: bool) -> bool:
    row = db.query(Option).filter(Option.option_name == option_name).first()
    current = (row.option_value or "").strip() if row else ""
    if current == (option_value or "").strip():
        return False
    if not dry_run:
        if not row:
            row = Option(option_name=option_name, option_value=option_value)
        else:
            row.option_value = option_value
        db.add(row)
    return True


def _delete_option(db: Session, option_name: str, *, dry_run: bool) -> bool:
    row = db.query(Option).filter(Option.option_name == option_name).first()
    if not row:
        return False
    if not dry_run:
        db.delete(row)
    return True


def _migrate_option_key(
    db: Session,
    old_key: str,
    new_key: str,
    *,
    dry_run: bool,
) -> int:
    if not old_key or old_key == new_key:
        return 0
    old_row = db.query(Option).filter(Option.option_name == old_key).first()
    if not old_row:
        return 0
    value = old_row.option_value or ""
    changed = 0
    if _upsert_option(db, new_key, value, dry_run=dry_run):
        changed += 1
    if _delete_option(db, old_key, dry_run=dry_run):
        changed += 1
    return changed


def rename_batch_slug_options(
    db: Session,
    old_name: str,
    new_name: str,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    counts = {"brochure_options": 0, "certificate_options": 0, "extension_options": 0}
    old_brochure = brochure_option_key(old_name)
    new_brochure = brochure_option_key(new_name)
    counts["brochure_options"] += _migrate_option_key(db, old_brochure, new_brochure, dry_run=dry_run)

    for kind in CERTIFICATE_OPTION_KINDS:
        old_key = certificate_option_key(kind, old_name)
        new_key = certificate_option_key(kind, new_name)
        counts["certificate_options"] += _migrate_option_key(db, old_key, new_key, dry_run=dry_run)

    for kind in EXTENSION_OPTION_KINDS:
        old_key = extension_option_key(kind, old_name)
        new_key = extension_option_key(kind, new_name)
        counts["extension_options"] += _migrate_option_key(db, old_key, new_key, dry_run=dry_run)

    return counts


def register_slug_alias(db: Session, old_slug: str, batch_id: int, *, dry_run: bool = False) -> bool:
    slug = (old_slug or "").strip().lower()
    if not slug:
        return False
    key = batch_slug_alias_option_key(slug)
    current = get_option_value(db, key)
    target = str(batch_id)
    if current == target:
        return False
    if not dry_run:
        _upsert_option(db, key, target, dry_run=False)
    return True


def rename_batch_references(
    db: Session,
    old_name: str,
    new_name: str,
    batch_id: int,
    *,
    dry_run: bool = False,
    register_alias_only: bool = False,
) -> dict[str, Any]:
    old = (old_name or "").strip()
    new = (new_name or "").strip()
    counts: dict[str, Any] = {
        "users": 0,
        "packages": 0,
        "user_package_payments": 0,
        "quiz_exams": 0,
        "folder_master": 0,
        "videos": 0,
        "coupons": 0,
        "user_subscriptions": 0,
        "registration_payment_txn": 0,
        "global_access_options": 0,
        "brochure_options": 0,
        "certificate_options": 0,
        "extension_options": 0,
        "slug_aliases": 0,
        "dry_run": dry_run,
    }

    if old.casefold() == new.casefold():
        return counts

    _ensure_no_name_collision(db, new, batch_id)

    old_url_slug = batch_slug(old)
    new_url_slug = batch_slug(new)
    if old_url_slug != new_url_slug:
        if register_slug_alias(db, old_url_slug, batch_id, dry_run=dry_run):
            counts["slug_aliases"] += 1

    if register_alias_only:
        return counts

    old_sub_slug = old.lower()
    new_sub_slug = new.lower()

    # Exact string columns
    for model, col_name, count_key in (
        (User, "subscription", "users"),
        (Package, "subscription", "packages"),
        (UserPackagePayment, "subscription", "user_package_payments"),
    ):
        col = getattr(model, col_name)
        q = db.query(model).filter(func.lower(func.trim(col)) == old.lower())
        rows = q.all()
        counts[count_key] = len(rows)
        if not dry_run:
            for row in rows:
                setattr(row, col_name, new)
                db.add(row)

    # CSV token columns
    csv_updates = (
        (QuizExam, "batch", "quiz_exams"),
        (FolderMaster, "batch", "folder_master"),
        (Video, "batch", "videos"),
    )
    for model, col_name, count_key in csv_updates:
        col = getattr(model, col_name)
        rows = db.query(model).filter(find_in_set_sql(col, old) > 0).all()
        updated = 0
        for row in rows:
            current = getattr(row, col_name) or ""
            replaced = replace_csv_token(current, old, new)
            if replaced != current:
                updated += 1
                if not dry_run:
                    setattr(row, col_name, replaced)
                    db.add(row)
        counts[count_key] = updated

    if _coupon_has_subscriptions_column(db):
        rows = (
            db.query(CouponMaster)
            .filter(find_in_set_sql(CouponMaster.subscriptions, old) > 0)
            .all()
        )
        updated = 0
        for row in rows:
            current = row.subscriptions or ""
            replaced = replace_csv_token(current, old, new)
            if replaced != current:
                updated += 1
                if not dry_run:
                    row.subscriptions = replaced
                    db.add(row)
        counts["coupons"] = updated

    # user_subscriptions.batch_slug uses lowercase subscription name
    if old_sub_slug != new_sub_slug:
        sub_rows = (
            db.query(UserSubscription)
            .filter(func.lower(func.trim(UserSubscription.batch_slug)) == old_sub_slug)
            .all()
        )
        counts["user_subscriptions"] = len(sub_rows)
        if not dry_run:
            for row in sub_rows:
                row.batch_slug = new_sub_slug
                db.add(row)

    # registration_payment_txn uses URL slug
    if old_url_slug != new_url_slug:
        txn_rows = (
            db.query(RegistrationPaymentTxn)
            .filter(func.lower(func.trim(RegistrationPaymentTxn.batch_slug)) == old_url_slug)
            .all()
        )
        counts["registration_payment_txn"] = len(txn_rows)
        if not dry_run:
            for row in txn_rows:
                row.batch_slug = new_url_slug
                db.add(row)

    # Global access CSV options
    global_changed = 0
    for opt_name in GLOBAL_ACCESS_OPTIONS:
        current = get_option_value(db, opt_name)
        if not _csv_token_present(current, old):
            continue
        replaced = replace_csv_token(current, old, new)
        if replaced != current:
            global_changed += 1
            if not dry_run:
                _upsert_option(db, opt_name, replaced, dry_run=False)
    counts["global_access_options"] = global_changed

    slug_counts = rename_batch_slug_options(db, old, new, dry_run=dry_run)
    counts.update(slug_counts)

    if not dry_run:
        logger.info(
            "Batch rename cascade batch_id=%s %r -> %r counts=%s",
            batch_id,
            old,
            new,
            counts,
        )

    return counts
