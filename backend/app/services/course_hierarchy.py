"""Batch → packages → modules → videos, read in a few queries."""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import BatchMaster, CouponMaster, FolderMaster, Package, QuizExam, User, UserExam, UserVideoProgress, Video
from app.services.batch_match import find_in_set_sql
from app.services.registration import expand_batch_user_subscription_filter
from app.services.video_progress import WATCHED_THRESHOLD_SECONDS

_VIDEO_CAP = 5


def _date(value: datetime | None) -> str:
    if value is None:
        return "not set"
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y")
    return str(value)[:10]


def _money(amount: float | None) -> str:
    return f"₹{float(amount or 0):,.0f}"


def _in_folder(folder_csv: str | None, folder_id: int) -> bool:
    return str(folder_id) in {part.strip() for part in (folder_csv or "").split(",") if part.strip()}


def _tokens(value: str | None) -> list[str]:
    return re.findall(r"[a-z0-9]+", (value or "").lower())


def _contains_tokens(haystack: list[str], needle: list[str]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    width = len(needle)
    return any(haystack[index : index + width] == needle for index in range(len(haystack) - width + 1))


def _csv_matches_batch(column, labels: set[str]):
    clauses = [find_in_set_sql(column, label) for label in labels if label]
    if not clauses:
        return column.is_(None)
    return or_(*clauses)


def _same_batch_label(value: str | None, labels: set[str]) -> bool:
    raw = (value or "").strip().casefold()
    if not raw:
        return False
    for label in labels:
        if raw == label or raw.startswith(f"{label}-") or raw.startswith(f"{label} "):
            return True
    return False


def match_batch_name(db: Session, text: str) -> str | None:
    """Longest batch name contained as whole words in the question.

    "Batch 15" matches BATCH 15 and does not match Batch 1. "Batch 1" still
    matches when that is the batch the user named. Package keys such as "CP 7"
    resolve to the batch that owns them.
    """
    from app.services.registration import CCM_BATCH_3_USER_SUBSCRIPTIONS

    batches = db.query(BatchMaster.name, BatchMaster.package_subscription).all()
    by_key: dict[str, str] = {}
    for name, package_key in batches:
        if name:
            by_key[name.strip().casefold()] = name
        if package_key and name:
            by_key[package_key.strip().casefold()] = name
    ccm_keys = {item.casefold() for item in CCM_BATCH_3_USER_SUBSCRIPTIONS}
    ccm_batch = next((name for key, name in by_key.items() if key in ccm_keys), None)
    if ccm_batch:
        for key in ccm_keys:
            by_key.setdefault(key, ccm_batch)

    candidates: list[tuple[list[str], str]] = []
    seen: set[tuple[str, str]] = set()

    def add(label: str | None, target: str | None) -> None:
        if not label or not target:
            return
        needle = _tokens(label)
        if len(needle) == 1 and len(needle[0]) < 3:
            return
        if not needle:
            return
        marker = (" ".join(needle), target)
        if marker in seen:
            return
        seen.add(marker)
        candidates.append((needle, target))
        glued = "".join(needle)
        if len(needle) > 1 and (glued, target) not in seen:
            seen.add((glued, target))
            candidates.append(([glued], target))

    for name, package_key in batches:
        add(name, name)
        add(package_key, name if name else None)
    for (subscription,) in db.query(Package.subscription).distinct().all():
        cleaned = (subscription or "").strip()
        if not cleaned:
            continue
        add(cleaned, by_key.get(cleaned.casefold(), cleaned))

    query = _tokens(text)
    best_name: str | None = None
    best_len = 0
    for needle, target in candidates:
        if len(needle) <= best_len or not _contains_tokens(query, needle):
            continue
        best_name = target
        best_len = len(needle)
    return best_name


def list_batches(db: Session) -> str:
    batches = (
        db.query(BatchMaster.name, BatchMaster.status)
        .order_by(BatchMaster.display_order.asc(), BatchMaster.id.asc())
        .all()
    )
    packages = (
        db.query(Package.subscription, Package.name, Package.total_amount, Package.plan_type, Package.status)
        .order_by(Package.id.asc())
        .all()
    )
    if not batches:
        return "No batches are stored."
    lines = ["Batches"]
    for index, (name, status) in enumerate(batches, start=1):
        state = "active" if str(status) == "1" else "inactive"
        lines.append(f"{index}. {name} ({state})")
        own = [pkg for pkg in packages if (pkg[0] or "").strip().lower() == (name or "").strip().lower()]
        if not own:
            lines.append("   Packages: none")
            continue
        lines.append("   Packages:")
        for pkg_sub, pkg_name, amount, plan, pkg_status in own:
            pkg_state = "active" if str(pkg_status) == "1" else "inactive"
            lines.append(f"   - {pkg_name} — {plan or 'one_time'} — {_money(amount)} — {pkg_state}")
    lines.append("Say a batch name, for example “Batch 15”, to see every learner, package, module, video, and mock test for that batch.")
    return "\n".join(lines)


def describe_batch(db: Session, batch_name: str, *, user_id: int | None = None, for_admin: bool = False) -> str:
    name = (batch_name or "").strip()
    if not name:
        return "No batch is assigned."

    batch = (
        db.query(BatchMaster)
        .filter(func.lower(func.trim(BatchMaster.name)) == name.lower())
        .first()
    )
    alias_names, _alias_package_ids = expand_batch_user_subscription_filter(db, name)
    labels = {(item or "").strip().casefold() for item in alias_names if (item or "").strip()}
    labels.add(name.casefold())
    packages = [
        package
        for package in db.query(Package).order_by(Package.id.asc()).all()
        if _same_batch_label(package.subscription, labels)
    ]
    folders = (
        db.query(FolderMaster.id, FolderMaster.name)
        .filter(FolderMaster.status == "1", _csv_matches_batch(FolderMaster.batch, labels))
        .order_by(FolderMaster.display_order.asc(), FolderMaster.id.asc())
        .all()
    )
    videos = (
        db.query(Video.id, Video.title, Video.folder)
        .filter(Video.status == "1", _csv_matches_batch(Video.batch, labels))
        .order_by(Video.title.asc())
        .all()
    )
    exams = (
        db.query(QuizExam.title, QuizExam.total_questions)
        .filter(QuizExam.status == "1", _csv_matches_batch(QuizExam.batch, labels))
        .order_by(QuizExam.id.asc())
        .all()
    )
    watched: set[int] = set()
    if user_id is not None and videos:
        rows = (
            db.query(UserVideoProgress.video_id, UserVideoProgress.watched_seconds)
            .filter(UserVideoProgress.user_id == user_id)
            .all()
        )
        video_ids = {row.id for row in videos}
        watched = {
            video_id
            for video_id, seconds in rows
            if video_id in video_ids and int(seconds or 0) >= WATCHED_THRESHOLD_SECONDS
        }
    lines = [f"Batch: {batch.name if batch else name}"]
    if batch is not None:
        lines.append(f"Status: {'active' if str(batch.status) == '1' else 'inactive'}")
    if for_admin:
        user_clauses = []
        for label in labels:
            column = func.lower(func.trim(func.coalesce(User.subscription, "")))
            user_clauses.append(column == label)
            user_clauses.append(column.like(f"{label}-%"))
            user_clauses.append(column.like(f"{label} %"))
        learners = (
            db.query(User)
            .filter(or_(*user_clauses))
            .order_by(User.name.asc(), User.id.asc())
            .all()
        )
        paid = [learner for learner in learners if (learner.payment_status or "").strip().lower() == "credit"]
        revenue = sum(float(learner.total_amount or 0) for learner in paid)
        learner_ids = [learner.id for learner in learners]
        finished_tests = 0
        if learner_ids:
            finished_tests = (
                db.query(func.count(UserExam.id))
                .filter(UserExam.user_id.in_(learner_ids), UserExam.is_finish_exam == "1")
                .scalar()
                or 0
            )
        coupon_filters = [find_in_set_sql(CouponMaster.subscriptions, label) for label in labels]
        coupons = (
            db.query(CouponMaster.code, CouponMaster.discount_percent, CouponMaster.discount_amount, CouponMaster.status)
            .filter(or_(*coupon_filters))
            .order_by(CouponMaster.id.asc())
            .all()
        ) if coupon_filters else []
        seen_codes: set[str] = set()
        unique_coupons = []
        for coupon in coupons:
            if coupon[0] in seen_codes:
                continue
            seen_codes.add(coupon[0])
            unique_coupons.append(coupon)
        lines.append(
            f"Learners: {len(learners)} total, {len(paid)} paid, revenue {_money(revenue)}"
        )
        lines.append(f"Finished mock-test attempts: {int(finished_tests)}")
        package_names = {package.id: package.name for package in packages}
        lines.append("Users:")
        if not learners:
            lines.append("- none")
        for learner in learners:
            pkg = package_names.get(learner.package_id) or "no package"
            lines.append(
                f"- {learner.name or 'Unnamed'} ({learner.email})"
                f" — payment {learner.payment_status or 'unknown'}"
                f" — {_money(learner.total_amount)}"
                f" — {pkg}"
            )
        lines.append("Coupons:")
        if not unique_coupons:
            lines.append("- none")
        for code, percent, amount, coupon_status in unique_coupons:
            discount = f"{float(percent or 0):.0f}%" if percent else _money(amount)
            state = "active" if str(coupon_status) == "1" else "inactive"
            lines.append(f"- {code} — {discount} — {state}")

    learner_counts: dict[int, int] = {}
    if for_admin and packages:
        package_ids = [package.id for package in packages]
        counted = (
            db.query(User.package_id, func.count(User.id))
            .filter(User.package_id.in_(package_ids))
            .group_by(User.package_id)
            .all()
        )
        learner_counts = {package_id: int(total) for package_id, total in counted if package_id is not None}

    lines.append("Packages:")
    if not packages:
        lines.append("- none stored for this batch")
    for package in packages:
        plan = package.plan_type or "one_time"
        if package.duration_months:
            plan = f"{plan}, {int(package.duration_months)} months"
        fee = f"gross {_money(package.gross_amount)}, GST {float(package.gst_percentage or 0):.0f}% {_money(package.gst_amount)}, total {_money(package.total_amount)}"
        discount = ""
        if float(package.discount_percentage or 0) or float(package.discounted_amount or 0):
            discount = f" — discount {float(package.discount_percentage or 0):.0f}% ({_money(package.discounted_amount)})"
        enrolled = ""
        if for_admin:
            enrolled = f" — {learner_counts.get(package.id, 0)} learners"
        category = f"{package.category_name} — " if (package.category_name or "").strip() else ""
        lines.append(
            f"- {category}{package.name}"
            f" — {plan}"
            f" — {fee}"
            f"{discount}"
            f" — {_date(package.batch_start_date or package.start_date)} to {_date(package.end_date)}"
            f" — {'active' if str(package.status) == '1' else 'inactive'}"
            f"{enrolled}"
        )

    lines.append("Modules:")
    if not folders:
        loose = [row for row in videos if not (row.folder or "").strip()]
        lines.append("- none")
        if loose:
            lines.append(f"Videos not in a module: {len(loose)}")
    for folder_id, folder_name in folders:
        in_folder = [row for row in videos if _in_folder(row.folder, folder_id)]
        done = sum(1 for row in in_folder if row.id in watched)
        progress = f"{done} of {len(in_folder)} watched" if user_id is not None else f"{len(in_folder)} videos"
        lines.append(f"- {folder_name} — {progress}")
        shown = in_folder if for_admin else in_folder[:_VIDEO_CAP]
        for video in shown:
            if user_id is None:
                lines.append(f"  - {video.title}")
            else:
                state = "watched" if video.id in watched else "not completed"
                lines.append(f"  - {video.title} — {state}")
        if not for_admin:
            extra = len(in_folder) - _VIDEO_CAP
            if extra > 0:
                lines.append(f"  - and {extra} more videos")

    lines.append("Mock tests:")
    if not exams:
        lines.append("- none")
    for title, total_q in exams:
        lines.append(f"- {title} — {int(total_q or 0)} questions")
    return "\n".join(lines)
