"""Apply Batch 15 post-course access options. Run from mock_test/backend with venv active."""
from __future__ import annotations

from app.db import SessionLocal
from app.models import Option


def upsert(db, name: str, value: str) -> None:
    row = db.query(Option).filter(Option.option_name == name).first()
    if row:
        row.option_value = value
    else:
        db.add(Option(option_name=name, option_value=value))


def append_batch(db, name: str, batch: str) -> None:
    row = db.query(Option).filter(Option.option_name == name).first()
    cur = (row.option_value if row else "") or ""
    if batch.lower() in cur.lower():
        return
    new = batch if not cur.strip() else cur.rstrip(",") + "," + batch
    upsert(db, name, new)


def main() -> None:
    db = SessionLocal()
    try:
        upsert(db, "batch_access_closed::batch-15", "1")
        upsert(db, "extension_base_date::batch-15", "2026-07-15")
        upsert(db, "certificate_enabled::batch-15", "1")
        upsert(db, "certificate_batch_label::batch-15", "Batch 15")
        upsert(db, "certificate_fixed_date::batch-15", "2026-07-15")
        upsert(
            db,
            "certificate_course_line::batch-15",
            "Online Master Classes in Critical Care Medicine",
        )
        upsert(
            db,
            "certificate_program_line::batch-15",
            "Dr Harish's Master Classes in Critical Care Medicine",
        )
        upsert(db, "certificate_show_date::batch-15", "1")
        upsert(db, "display_download_certificate", "1")
        append_batch(db, "access_download_certificate", "Batch 15")
        append_batch(db, "access_video_library_link", "Batch 15")
        append_batch(db, "access_quiz_link", "Batch 15")
        db.commit()
        print("Batch 15 post-course options applied successfully.")
    except Exception as exc:
        db.rollback()
        raise SystemExit(f"Failed: {exc}") from exc
    finally:
        db.close()


if __name__ == "__main__":
    main()
