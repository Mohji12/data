#!/usr/bin/env python3
"""Seed ICU-ID Certification Course for public registration (/register/icu-id-certification-course).

Creates or updates batch_master, Indian + Foreign packages, description, brochure PDF,
and fee notice. Safe to re-run.

Usage (from backend/):
  python scripts/seed_icu_id_certification_course.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.db import SessionLocal  # noqa: E402
from app.models import BatchMaster, FolderMaster, Option, Package, QuizExam, QuizSection  # noqa: E402
from app.services.access import get_option_value, subscription_allowed  # noqa: E402
from app.services.module_exam_gate import MODULE_EXAM_MAP_OPTION  # noqa: E402

BATCH_NAME = "ICU-ID Certification Course"
MODULE_COUNT = 10
PACKAGE_SUBSCRIPTION = "ICU-ID Certification Course"
BROCHURE_FILENAME = "icu-id-certification-course-brochure.pdf"

DESCRIPTION = """## ICU-ID Certification Course

A focused online programme on **infection prevention, diagnosis, and management in the ICU** — designed for clinicians who want structured, evidence-based training with Dr. Harish Critical Care Classes.

### What you will learn
- Approach to fever and new infection in critically ill patients
- Antimicrobial stewardship and resistance patterns in ICU
- Device-related infections (CLABSI, VAP, CAUTI) and bundles
- Sepsis, tropical infections, and source control in critical care
- Infection control practices for ICU teams

### Programme format
- Recorded lectures available on your dashboard after registration
- Module-wise access for the full course tenure
- Mock assessments and MCQ-based revision (as configured for the batch)
- Certificate of completion on fulfilling course requirements

### Who should register
- Postgraduate trainees in critical care, medicine, pulmonology, and anaesthesia
- Practising intensivists and ICU consultants
- Clinicians preparing for EDIC / critical care examinations with an ID focus

### Registration
Choose your delegate category (Indian or Foreign) in the fee table below, then complete registration with your documents and payment details.
"""

NOTICE = (
    "Registration is open for the ICU-ID Certification Course. "
    "Fees shown are exclusive of applicable taxes as per the table. "
    "Contact support@harishcriticalcareclasses.com for payment or document queries."
)


def _money_inr(gross: float, gst_pct: float = 18.0) -> tuple[float, float, float]:
    gst_amt = round(gross * gst_pct / 100.0, 2)
    total = round(gross + gst_amt, 2)
    return gross, gst_amt, total


def _money_usd(gross: float, gst_pct: float = 18.0) -> tuple[float, float, float]:
    gst_amt = round(gross * gst_pct / 100.0, 2)
    total = round(gross + gst_amt, 2)
    return gross, gst_amt, total


def _pdf_ascii(text: str) -> str:
    return "".join(ch if ord(ch) < 128 else " " for ch in text)


def _write_brochure_pdf(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 8, _pdf_ascii("ICU-ID Certification Course"))
    pdf.set_font("Helvetica", "", 11)
    for paragraph in [
        "Dr. Harish Critical Care Classes - ICU infection and antimicrobial training for critical care teams.",
        "Evidence-based lectures, dashboard access for the course tenure, and certificate on completion.",
        "Register at harishcriticalcareclasses.com",
        "Seed brochure - upload the final PDF from Admin when ready.",
    ]:
        pdf.ln(3)
        pdf.multi_cell(0, 6, _pdf_ascii(paragraph))
    pdf.output(str(target))


def _upsert_package(
    db,
    *,
    name: str,
    category_name: str,
    gross: float,
    is_inr: bool,
    start: datetime,
    end: datetime,
) -> Package:
    row = (
        db.query(Package)
        .filter(
            Package.subscription == PACKAGE_SUBSCRIPTION,
            Package.category_name == category_name,
            Package.name == name,
        )
        .first()
    )
    gst_pct = 18.0
    gross_amt, gst_amt, total = _money_inr(gross, gst_pct) if is_inr else _money_usd(gross, gst_pct)
    if row is None:
        row = Package(
            name=name,
            subscription=PACKAGE_SUBSCRIPTION,
            category_name=category_name,
            plan_type="one_time",
            with_topup="0",
            status="1",
        )
        db.add(row)
    row.gross_amount = gross_amt
    row.gst_percentage = gst_pct
    row.gst_amount = gst_amt
    row.total_amount = total
    row.start_date = start
    row.end_date = end
    row.batch_start_date = start
    row.status = "1"
    row.with_topup = "0"
    return row


def _split_csv(raw: str) -> list[str]:
    return [p.strip() for p in (raw or "").split(",") if p.strip()]


def _upsert_option(db, option_name: str, option_value: str) -> None:
    row = db.query(Option).filter(Option.option_name == option_name).first()
    if row:
        row.option_value = option_value
    else:
        db.add(Option(option_name=option_name, option_value=option_value))


def _ensure_batch_in_option(db, option_name: str, batch_name: str) -> bool:
    current = get_option_value(db, option_name)
    if subscription_allowed(current, batch_name):
        return False
    parts = _split_csv(current)
    parts.append(batch_name)
    _upsert_option(db, option_name, ",".join(parts))
    return True


def _seed_modules(db, batch_name: str, now: datetime) -> dict[str, int]:
    """Module folders, quiz sections, exams, and folder→exam option map."""
    exam_start = now - timedelta(days=1)
    exam_end = now + timedelta(days=3650)
    folder_exam_map: dict[str, int] = {}

    for index in range(1, MODULE_COUNT + 1):
        folder_name = f"Module {index}"
        section_label = f"ICU-ID Module {index}"
        exam_title = f"Module {index} Test"

        folder = (
            db.query(FolderMaster)
            .filter(FolderMaster.name == folder_name, FolderMaster.batch == batch_name)
            .first()
        )
        if folder is None:
            folder = FolderMaster(
                name=folder_name,
                batch=batch_name,
                status="1",
                display_order=index,
            )
            db.add(folder)
            db.flush()
        else:
            folder.batch = batch_name
            folder.status = "1"
            folder.display_order = index

        section = (
            db.query(QuizSection)
            .filter(QuizSection.name == section_label)
            .first()
        )
        if section is None:
            section = QuizSection(name=section_label, display_order=index, status="1")
            db.add(section)
            db.flush()
        else:
            section.display_order = index
            section.status = "1"

        exam = (
            db.query(QuizExam)
            .filter(QuizExam.title == exam_title, QuizExam.batch == batch_name)
            .first()
        )
        if exam is None:
            exam = QuizExam(
                title=exam_title,
                description=f"60-question assessment for {folder_name}.",
                section_id=str(section.id),
                batch=batch_name,
                timer_time=90,
                total_questions=60,
                start_date=exam_start,
                end_date=exam_end,
                status="1",
                is_display_result="1",
                is_display_correct_answer="0",
            )
            db.add(exam)
            db.flush()
        else:
            exam.section_id = str(section.id)
            exam.batch = batch_name
            exam.timer_time = 90
            exam.total_questions = 60
            exam.start_date = exam_start
            exam.end_date = exam_end
            exam.status = "1"

        folder_exam_map[str(folder.id)] = int(exam.id)

    _upsert_option(db, MODULE_EXAM_MAP_OPTION, json.dumps(folder_exam_map, sort_keys=True))
    _ensure_batch_in_option(db, "access_video_library_link", batch_name)
    _ensure_batch_in_option(db, "access_quiz_link", batch_name)
    return {"folders": MODULE_COUNT, "exams": MODULE_COUNT}


def main() -> int:
    brochure_path = _ROOT / "uploads" / "brochures" / BROCHURE_FILENAME
    if not brochure_path.is_file():
        _write_brochure_pdf(brochure_path)
        print(f"Wrote brochure: {brochure_path}")

    now = datetime.utcnow()
    start = now - timedelta(days=7)
    end = now + timedelta(days=365)

    db = SessionLocal()
    try:
        batch = db.query(BatchMaster).filter(BatchMaster.name == BATCH_NAME).first()
        if batch is None:
            batch = BatchMaster(
                name=BATCH_NAME,
                status="1",
                display_order=120,
            )
            db.add(batch)
            db.flush()
            print(f"Created batch_master id={batch.id}")
        else:
            batch.status = "1"
            batch.display_order = max(int(batch.display_order or 0), 120)
            print(f"Updated batch_master id={batch.id}")

        if hasattr(batch, "package_subscription"):
            batch.package_subscription = PACKAGE_SUBSCRIPTION
        batch.description = DESCRIPTION.strip()
        batch.registration_fee_structure = NOTICE
        if hasattr(batch, "brochure_file"):
            batch.brochure_file = BROCHURE_FILENAME

        _upsert_package(
            db,
            name="Standard (Indian)",
            category_name="Indian Delegates",
            gross=15000.0,
            is_inr=True,
            start=start,
            end=end,
        )
        _upsert_package(
            db,
            name="Standard (Foreign)",
            category_name="Foreign Delegates",
            gross=350.0,
            is_inr=False,
            start=start,
            end=end,
        )

        module_stats = _seed_modules(db, BATCH_NAME, now)

        db.commit()
        print("Seed complete.")
        print(f"  Public URL: /register/icu-id-certification-course")
        print(f"  API: /registration/fee-structure?batch_slug=icu-id-certification-course")
        print(f"  Modules: {module_stats['folders']} folders, {module_stats['exams']} exams (60 questions each — add questions in Admin)")
        print(f"  Option map: {MODULE_EXAM_MAP_OPTION}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
