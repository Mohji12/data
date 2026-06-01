from __future__ import annotations
import csv
from datetime import date, datetime
import io
import secrets
import string
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, model_validator
from sqlalchemy import inspect
from sqlalchemy.orm import Session, load_only

from app.admin_security import get_current_admin, require_admin_type
from app.db import get_db
from app.models import BatchMaster, CouponMaster, Option, Package
from app.services.access import (
    certificate_option_key,
    get_certificate_batch_settings,
    extension_option_key,
    get_extension_batch_settings,
)

router = APIRouter(prefix="/admin/commerce", tags=["admin-commerce"], dependencies=[Depends(get_current_admin)])


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


class OptionPayload(BaseModel):
    option_name: str
    option_value: str


def _upsert_option(db: Session, option_name: str, option_value: str) -> None:
    row = db.query(Option).filter(Option.option_name == option_name).first()
    if not row:
        row = Option(option_name=option_name, option_value=option_value)
    else:
        row.option_value = option_value
    db.add(row)


@router.get("/options")
def list_options(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(Option).order_by(Option.option_name.asc()).all()
    return [{"id": o.id, "option_name": o.option_name, "option_value": o.option_value} for o in rows]


@router.post("/options", dependencies=[Depends(require_admin_type("techadmin"))])
def upsert_option(payload: OptionPayload, db: Session = Depends(get_db)) -> dict:
    _upsert_option(db, payload.option_name, payload.option_value)
    db.commit()
    return {"status": "ok"}


class CertificateBatchSettingPayload(BaseModel):
    batch_name: Optional[str] = None
    batch_names: Optional[list[str]] = None
    enabled: bool = False
    certificate_batch_label: Optional[str] = None
    certificate_fixed_date: Optional[str] = None
    certificate_course_line: Optional[str] = None
    certificate_program_line: Optional[str] = None
    certificate_show_date: bool = False
    certificate_name_size: Optional[int] = None

    @model_validator(mode="after")
    def validate_name_size(self) -> "CertificateBatchSettingPayload":
        if self.certificate_name_size is not None:
            size = int(self.certificate_name_size)
            if size < 12 or size > 48:
                raise ValueError("certificate_name_size must be between 12 and 48")
            self.certificate_name_size = size
        return self

    @model_validator(mode="after")
    def validate_date(self) -> "CertificateBatchSettingPayload":
        raw = (self.certificate_fixed_date or "").strip()
        if raw:
            try:
                date.fromisoformat(raw)
            except ValueError as exc:
                raise ValueError("certificate_fixed_date must be YYYY-MM-DD") from exc
        return self


@router.get("/certificate-batch-settings")
def list_certificate_batch_settings(db: Session = Depends(get_db)) -> list[dict]:
    batches = (
        db.query(BatchMaster)
        .options(load_only(BatchMaster.id, BatchMaster.name, BatchMaster.status, BatchMaster.display_order))
        .order_by(BatchMaster.display_order.desc(), BatchMaster.id.desc())
        .all()
    )
    out: list[dict] = []
    for batch in batches:
        settings = get_certificate_batch_settings(db, batch.name)
        out.append(
            {
                "batch_id": batch.id,
                "batch_name": batch.name,
                "status": batch.status,
                "enabled": (settings.get("enabled") or "").strip() == "1",
                "certificate_batch_label": settings.get("batch_label") or "",
                "certificate_fixed_date": settings.get("fixed_date") or "",
                "certificate_course_line": settings.get("course_line") or "",
                "certificate_program_line": settings.get("program_line") or "",
                "certificate_show_date": (settings.get("show_date") or "").strip() == "1",
                "certificate_name_size": (settings.get("name_size") or "").strip(),
            }
        )
    return out


@router.post("/certificate-batch-settings", dependencies=[Depends(require_admin_type("techadmin"))])
def upsert_certificate_batch_settings(
    payload: CertificateBatchSettingPayload,
    db: Session = Depends(get_db),
) -> dict:
    names = payload.batch_names or []
    if payload.batch_name:
        names.append(payload.batch_name)
    
    names = [n.strip() for n in names if n.strip()]
    if not names:
        raise HTTPException(status_code=422, detail="batch_name or batch_names is required")

    for batch_name in names:
        # Check if batch exists (optional, but good for validation)
        batch = (
            db.query(BatchMaster)
            .options(load_only(BatchMaster.id))
            .filter(BatchMaster.name == batch_name)
            .first()
        )
        if not batch:
            continue

        enabled_key = certificate_option_key("enabled", batch_name)
        label_key = certificate_option_key("batch_label", batch_name)
        date_key = certificate_option_key("fixed_date", batch_name)
        course_key = certificate_option_key("course_line", batch_name)
        program_key = certificate_option_key("program_line", batch_name)
        show_date_key = certificate_option_key("show_date", batch_name)
        name_size_key = certificate_option_key("name_size", batch_name)

        if enabled_key and label_key and date_key:
            _upsert_option(db, enabled_key, "1" if payload.enabled else "0")
            _upsert_option(db, label_key, (payload.certificate_batch_label or "").strip())
            _upsert_option(db, date_key, (payload.certificate_fixed_date or "").strip())
            if course_key:
                _upsert_option(db, course_key, (payload.certificate_course_line or "").strip())
            if program_key:
                _upsert_option(db, program_key, (payload.certificate_program_line or "").strip())
            if show_date_key:
                _upsert_option(db, show_date_key, "1" if payload.certificate_show_date else "0")
            if name_size_key and payload.certificate_name_size is not None:
                _upsert_option(db, name_size_key, str(payload.certificate_name_size))

    db.commit()
    return {"status": "ok"}


class ExtensionBatchSettingPayload(BaseModel):
    batch_name: Optional[str] = None
    batch_names: Optional[list[str]] = None
    enabled: bool = False
    gross_amount: float = 0.0
    gst_percentage: float = 0.0
    gst_amount: float = 0.0
    total_amount: float = 0.0
    months: int = 2
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    base_date: Optional[str] = None

    @model_validator(mode="after")
    def validate_dates(self) -> "ExtensionBatchSettingPayload":
        for field in ["start_date", "end_date", "base_date"]:
            val = getattr(self, field)
            if val and val.strip():
                try:
                    date.fromisoformat(val.strip())
                except ValueError as exc:
                    raise ValueError(f"{field} must be YYYY-MM-DD") from exc
        return self


@router.get("/extension-batch-settings")
def list_extension_batch_settings(db: Session = Depends(get_db)) -> list[dict]:
    batches = (
        db.query(BatchMaster)
        .options(load_only(BatchMaster.id, BatchMaster.name, BatchMaster.status, BatchMaster.display_order))
        .order_by(BatchMaster.display_order.desc(), BatchMaster.id.desc())
        .all()
    )
    out: list[dict] = []
    for batch in batches:
        settings = get_extension_batch_settings(db, batch.name)
        out.append(
            {
                "batch_id": batch.id,
                "batch_name": batch.name,
                "status": batch.status,
                "enabled": (settings.get("enabled") or "").strip() == "1",
                "gross_amount": float(settings.get("gross_amount") or 0.0),
                "gst_percentage": float(settings.get("gst_percentage") or 0.0),
                "gst_amount": float(settings.get("gst_amount") or 0.0),
                "total_amount": float(settings.get("total_amount") or 0.0),
                "months": int(settings.get("months") or 2),
                "start_date": settings.get("start_date") or "",
                "end_date": settings.get("end_date") or "",
                "base_date": settings.get("base_date") or "",
            }
        )
    return out


@router.post("/extension-batch-settings", dependencies=[Depends(require_admin_type("techadmin"))])
def upsert_extension_batch_settings(
    payload: ExtensionBatchSettingPayload,
    db: Session = Depends(get_db),
) -> dict:
    names = payload.batch_names or []
    if payload.batch_name:
        names.append(payload.batch_name)
    
    names = [n.strip() for n in names if n.strip()]
    if not names:
        raise HTTPException(status_code=422, detail="batch_name or batch_names is required")

    for batch_name in names:
        enabled_key = extension_option_key("enabled", batch_name)
        gross_key = extension_option_key("gross_amount", batch_name)
        gst_pct_key = extension_option_key("gst_percentage", batch_name)
        gst_amt_key = extension_option_key("gst_amount", batch_name)
        total_key = extension_option_key("total_amount", batch_name)
        months_key = extension_option_key("months", batch_name)
        start_key = extension_option_key("start_date", batch_name)
        end_key = extension_option_key("end_date", batch_name)
        base_key = extension_option_key("base_date", batch_name)
        
        _upsert_option(db, enabled_key, "1" if payload.enabled else "0")
        _upsert_option(db, gross_key, str(payload.gross_amount))
        _upsert_option(db, gst_pct_key, str(payload.gst_percentage))
        _upsert_option(db, gst_amt_key, str(payload.gst_amount))
        _upsert_option(db, total_key, str(payload.total_amount))
        _upsert_option(db, months_key, str(payload.months))
        _upsert_option(db, start_key, (payload.start_date or "").strip())
        _upsert_option(db, end_key, (payload.end_date or "").strip())
        _upsert_option(db, base_key, (payload.base_date or "").strip())

    db.commit()
    return {"status": "ok"}


class PackagePayload(BaseModel):
    name: str
    subscription: Optional[str] = None
    category_name: Optional[str] = None
    gross_amount: float = 0.0
    gst_percentage: float = 0.0
    gst_amount: float = 0.0
    total_amount: float = 0.0
    plan_type: Optional[str] = "one_time"
    duration_months: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    batch_start_date: Optional[str] = None
    with_topup: str = "0"
    discount_percentage: float = 0.0
    discounted_amount: float = 0.0
    discount_start_date: Optional[str] = None
    discount_end_date: Optional[str] = None
    sync_promo_discount: bool = True
    status: str = "1"


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    # Accept YYYY-MM-DD and legacy MySQL/datetime strings (2026-05-31T00:00:00).
    try:
        return date.fromisoformat(raw[:10])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid date format: {value}. Use YYYY-MM-DD.") from exc


def _normalize_plan_type(value: Optional[str]) -> str:
    v = (value or "one_time").strip().lower()
    if v not in {"one_time", "subscription"}:
        raise HTTPException(status_code=422, detail="plan_type must be one of: one_time, subscription")
    return v


def _normalize_duration_months(plan_type: str, duration_months: Optional[int]) -> Optional[int]:
    if plan_type == "subscription":
        if duration_months is None or int(duration_months) <= 0:
            raise HTTPException(status_code=422, detail="duration_months must be a positive integer for subscription plans")
        return int(duration_months)
    return None


def _date_to_iso(value: object) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        raw = value.strip()
        return raw[:10] if raw else None
    return None


@router.get("/packages")
def list_packages(
    q: Optional[str] = Query(None),
    sort_by: str = Query("id"),
    order: str = Query("desc"),
    db: Session = Depends(get_db),
) -> list[dict]:
    query = db.query(Package)
    if q:
        query = query.filter(Package.name.ilike(f"%{q}%"))

    if order.lower() == "asc":
        query = query.order_by(getattr(Package, sort_by).asc())
    else:
        query = query.order_by(getattr(Package, sort_by).desc())

    rows = query.all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "subscription": p.subscription,
            "category_name": p.category_name,
            "gross_amount": p.gross_amount,
            "gst_percentage": p.gst_percentage,
            "gst_amount": p.gst_amount,
            "total_amount": p.total_amount,
            "plan_type": (p.plan_type or "one_time"),
            "duration_months": p.duration_months,
            "start_date": _date_to_iso(p.start_date),
            "end_date": _date_to_iso(p.end_date),
            "batch_start_date": _date_to_iso(p.batch_start_date),
            "with_topup": p.with_topup,
            "discount_percentage": p.discount_percentage,
            "discounted_amount": p.discounted_amount,
            "discount_start_date": _date_to_iso(p.discount_start_date),
            "discount_end_date": _date_to_iso(p.discount_end_date),
            "status": p.status,
        }
        for p in rows
    ]


@router.post("/packages", dependencies=[Depends(require_admin_type("techadmin"))])
def create_package(payload: PackagePayload, db: Session = Depends(get_db)) -> dict:
    plan_type = _normalize_plan_type(payload.plan_type)
    duration_months = _normalize_duration_months(plan_type, payload.duration_months)
    p = Package(
        name=payload.name,
        subscription=payload.subscription,
        category_name=payload.category_name,
        gross_amount=payload.gross_amount,
        gst_percentage=payload.gst_percentage,
        gst_amount=payload.gst_amount,
        total_amount=payload.total_amount,
        plan_type=plan_type,
        duration_months=duration_months,
        start_date=_parse_iso_date(payload.start_date),
        end_date=_parse_iso_date(payload.end_date),
        batch_start_date=_parse_iso_date(payload.batch_start_date),
        with_topup=payload.with_topup,
        discount_percentage=payload.discount_percentage,
        discounted_amount=payload.discounted_amount,
        discount_start_date=_parse_iso_date(payload.discount_start_date),
        discount_end_date=_parse_iso_date(payload.discount_end_date),
        status=payload.status,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"id": p.id}


@router.put("/packages/{package_id}", dependencies=[Depends(require_admin_type("techadmin"))])
def update_package(package_id: int, payload: PackagePayload, db: Session = Depends(get_db)) -> dict:
    from app.services.registration import (
        shift_following_package_windows_after_extension,
        _recompute_package_stored_amounts,
        _sync_timed_promo_discount_across_subscription_packages,
        _sync_tier_dates_across_delegate_categories,
        _package_promo_discount_active,
    )

    p = db.query(Package).filter(Package.id == package_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Package not found")
    old_end = p.end_date.date() if isinstance(p.end_date, datetime) else p.end_date
    plan_type = _normalize_plan_type(payload.plan_type)
    duration_months = _normalize_duration_months(plan_type, payload.duration_months)
    p.name = payload.name
    p.subscription = payload.subscription
    p.category_name = payload.category_name
    p.gross_amount = payload.gross_amount
    p.gst_percentage = payload.gst_percentage
    p.gst_amount = payload.gst_amount
    p.total_amount = payload.total_amount
    p.plan_type = plan_type
    p.duration_months = duration_months
    p.start_date = _parse_iso_date(payload.start_date)
    p.end_date = _parse_iso_date(payload.end_date)
    p.batch_start_date = _parse_iso_date(payload.batch_start_date)
    p.with_topup = payload.with_topup
    p.discount_percentage = payload.discount_percentage
    p.discounted_amount = payload.discounted_amount
    p.discount_start_date = _parse_iso_date(payload.discount_start_date)
    p.discount_end_date = _parse_iso_date(payload.discount_end_date)
    p.status = payload.status
    _recompute_package_stored_amounts(p)
    new_end = p.end_date.date() if isinstance(p.end_date, datetime) else p.end_date
    new_start = p.start_date.date() if isinstance(p.start_date, datetime) else p.start_date
    db.add(p)
    promo_synced = 0
    if payload.sync_promo_discount:
        promo_synced = _sync_timed_promo_discount_across_subscription_packages(db, p)
    synced = _sync_tier_dates_across_delegate_categories(
        db, p, end_date=new_end, start_date=new_start
    )
    shifted = 0
    if old_end and new_end and new_end > old_end:
        shifted += shift_following_package_windows_after_extension(db, p, old_end, new_end)
        # Shift later tiers for the paired delegate category (Indian / Foreign).
        tier_name = (p.name or "").strip()
        sub = (p.subscription or "").strip()
        if tier_name and sub:
            twin = (
                db.query(Package)
                .filter(
                    Package.subscription == sub,
                    Package.name == tier_name,
                    Package.status == "1",
                    Package.id != p.id,
                )
                .first()
            )
            if twin:
                shifted += shift_following_package_windows_after_extension(
                    db, twin, old_end, new_end
                )
    db.commit()
    return {
        "status": "ok",
        "delegate_rows_synced": synced,
        "promo_discount_rows_synced": promo_synced,
        "promo_discount_active_today": _package_promo_discount_active(p),
        "following_tiers_shifted": shifted,
        "gap_days_after_tier_end": 15,
    }


@router.delete("/packages/{package_id}", dependencies=[Depends(require_admin_type("techadmin"))])
def delete_package(package_id: int, db: Session = Depends(get_db)) -> dict:
    p = db.query(Package).filter(Package.id == package_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Package not found")
    db.delete(p)
    db.commit()
    return {"status": "ok"}


@router.post("/packages/{package_id}/copy", dependencies=[Depends(require_admin_type("techadmin"))])
def copy_package(package_id: int, db: Session = Depends(get_db)) -> dict:
    p = db.query(Package).filter(Package.id == package_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Package not found")
    clone = Package(
        name=f"{p.name} (copy)",
        subscription=p.subscription,
        category_name=p.category_name,
        gross_amount=p.gross_amount,
        gst_percentage=p.gst_percentage,
        gst_amount=p.gst_amount,
        total_amount=p.total_amount,
        plan_type=(p.plan_type or "one_time"),
        duration_months=p.duration_months,
        start_date=p.start_date,
        end_date=p.end_date,
        batch_start_date=p.batch_start_date,
        with_topup=p.with_topup,
        discount_percentage=p.discount_percentage,
        discounted_amount=p.discounted_amount,
        discount_start_date=p.discount_start_date,
        discount_end_date=p.discount_end_date,
        status=p.status,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return {"id": clone.id}


class CouponPayload(BaseModel):
    code: str
    status: str = "0"
    discount_amount: float = 0.0
    discount_percent: float = 0.0
    assigned_email: Optional[str] = None
    subscriptions: Optional[str] = None

    @model_validator(mode="after")
    def at_most_one_discount(self) -> "CouponPayload":
        amt = float(self.discount_amount or 0) > 0
        pct = float(self.discount_percent or 0) > 0
        if amt and pct:
            raise ValueError("Provide at most one of discount_amount or discount_percent (cannot provide both)")
        return self


@router.get("/coupons")
def list_coupons(
    q: Optional[str] = Query(None),
    sort_by: str = Query("id"),
    order: str = Query("desc"),
    db: Session = Depends(get_db),
) -> list[dict]:
    has_amt = _coupon_has_column(db, "discount_amount")
    has_pct = _coupon_has_column(db, "discount_percent")
    has_sub = _coupon_has_column(db, "subscriptions")
    has_email = _coupon_has_column(db, "assigned_email")
    
    query = _coupon_query(db)
    if q:
        query = query.filter(CouponMaster.code.ilike(f"%{q}%"))

    if order.lower() == "asc":
        query = query.order_by(getattr(CouponMaster, sort_by).asc())
    else:
        query = query.order_by(getattr(CouponMaster, sort_by).desc())

    rows = query.all()
    return [
        {
            "id": c.id,
            "code": c.code,
            "status": c.status,
            "discount_amount": (getattr(c, "discount_amount", 0.0) if has_amt else 0.0),
            "discount_percent": (getattr(c, "discount_percent", 0.0) if has_pct else 0.0),
            "subscriptions": (c.subscriptions if has_sub else None),
            "assigned_email": (c.assigned_email if has_email else None),
        }
        for c in rows
    ]


_COUPON_ALPHABET = string.ascii_uppercase + string.digits


def _random_coupon_code(length: int = 8) -> str:
    return "".join(secrets.choice(_COUPON_ALPHABET) for _ in range(length))


@router.post("/coupons/generate", dependencies=[Depends(require_admin_type("techadmin"))])
def generate_coupons(
    count: int = Query(10, ge=1, le=100, description="Number of unique codes to create (PHP default: 10)"),
    discount_amount: float = Query(0.0),
    discount_percent: float = Query(0.0),
    db: Session = Depends(get_db),
) -> dict:
    """Bulk-generate unused coupon codes (parity with PHP admin Coupon::generate)."""
    has_amt = _coupon_has_column(db, "discount_amount")
    has_pct = _coupon_has_column(db, "discount_percent")
    created: list[str] = []
    max_attempts = count * 50
    attempts = 0
    while len(created) < count and attempts < max_attempts:
        attempts += 1
        code = _random_coupon_code()
        exists = db.query(CouponMaster.id).filter(CouponMaster.code == code).first()
        if exists:
            continue
        row = CouponMaster(code=code, status="1")
        if has_amt:
            row.discount_amount = discount_amount
        if has_pct:
            row.discount_percent = discount_percent
        
        db.add(row)
        created.append(code)
    
    db.commit()
    return {"created": len(created), "codes": created}


@router.post("/coupons", dependencies=[Depends(require_admin_type("techadmin"))])
def create_coupon(payload: CouponPayload, db: Session = Depends(get_db)) -> dict:
    exists = db.query(CouponMaster.id).filter(CouponMaster.code == payload.code).first()
    if exists:
        raise HTTPException(status_code=409, detail="Coupon already exists")
    amt = float(payload.discount_amount or 0)
    pct = float(payload.discount_percent or 0)
    has_amt = _coupon_has_column(db, "discount_amount")
    has_pct = _coupon_has_column(db, "discount_percent")
    if amt > 0 and not has_amt:
        raise HTTPException(status_code=422, detail="This database schema does not support amount-based coupons")
    if pct > 0 and not has_pct:
        raise HTTPException(status_code=422, detail="This database schema does not support percent-based coupons")
    c = CouponMaster(
        code=payload.code,
        status=payload.status,
    )
    if _coupon_has_column(db, "subscriptions"):
        c.subscriptions = (payload.subscriptions or "").strip() or None
    if _coupon_has_column(db, "assigned_email"):
        c.assigned_email = (payload.assigned_email or "").strip() or None
    if has_amt:
        c.discount_amount = amt if amt > 0 else 0.0
    if has_pct:
        c.discount_percent = pct if pct > 0 else 0.0
    db.add(c)
    db.flush()
    new_id = c.id
    db.commit()
    return {"id": new_id}


@router.delete("/coupons/{coupon_id}", dependencies=[Depends(require_admin_type("techadmin"))])
def delete_coupon(coupon_id: int, db: Session = Depends(get_db)) -> dict:
    c = _coupon_query(db).filter(CouponMaster.id == coupon_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Coupon not found")
    db.delete(c)
    db.commit()
    return {"status": "ok"}


@router.get("/coupons/export.csv")
def export_coupons(db: Session = Depends(get_db)) -> Response:
    has_amt = _coupon_has_column(db, "discount_amount")
    has_pct = _coupon_has_column(db, "discount_percent")
    has_sub = _coupon_has_column(db, "subscriptions")
    has_email = _coupon_has_column(db, "assigned_email")
    rows = _coupon_query(db).order_by(CouponMaster.id.desc()).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "code", "status", "discount_amount", "discount_percent", "subscriptions", "assigned_email"])
    for c in rows:
        w.writerow(
            [
                c.id,
                c.code,
                c.status,
                (getattr(c, "discount_amount", 0) if has_amt else 0),
                (getattr(c, "discount_percent", 0) if has_pct else 0),
                (c.subscriptions if has_sub else "") or "",
                (c.assigned_email if has_email else "") or "",
            ]
        )
    return Response(content=buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=coupons.csv"})

