"""
E2E: start MOCK TEST _3 (exam 290), answer all questions, finish, report scoring.

Uses a minted JWT (no password) against local FastAPI with production DB.
Does not use the complaining student's account unless E2E_USER_EMAIL is set.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine
from app.models import Question, User
from app.security import create_access_token, create_session_id
from app.services.access import can_access_mock_test
from app.services.mock_test_attempts import get_max_attempts_for_user

EXAM_ID = int(os.getenv("E2E_EXAM_ID", "290"))
BASE_URL = os.getenv("E2E_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
USER_EMAIL = (os.getenv("E2E_USER_EMAIL") or "").strip().lower()
CLEANUP = os.getenv("E2E_CLEANUP", "1").strip().lower() in {"1", "true", "yes"}


def _pick_user(db: Session) -> User:
    if USER_EMAIL:
        user = db.query(User).filter(User.email == USER_EMAIL).first()
        if not user:
            raise SystemExit(f"User not found: {USER_EMAIL}")
        ok, reason = can_access_mock_test(db, user)
        if not ok:
            raise SystemExit(f"User cannot access mock tests: {reason}")
        return user

    # Prefer users who can access mock tests and still have attempt room.
    rows = db.execute(
        text(
            """
            SELECT u.id,
              (SELECT COUNT(*) FROM user_exam ue WHERE ue.user_id=u.id AND ue.exam_id=:e) AS attempts
            FROM users u
            WHERE u.approve = '1'
              AND LOWER(COALESCE(u.payment_status,'')) = 'credit'
              AND (
                u.subscription LIKE :edic
                OR u.subscription LIKE :ccm
                OR u.subscription LIKE :batch
              )
            ORDER BY attempts ASC, u.id DESC
            LIMIT 120
            """
        ),
        {"e": EXAM_ID, "edic": "%EDIC%", "ccm": "%CCM%", "batch": "Batch%"},
    ).fetchall()
    for uid, attempts in rows:
        user = db.query(User).filter(User.id == int(uid)).first()
        if not user:
            continue
        ok, _ = can_access_mock_test(db, user)
        if not ok:
            continue
        max_attempts = get_max_attempts_for_user(db, user)
        if int(attempts or 0) < int(max_attempts):
            return user
    raise SystemExit("No eligible user with remaining attempts found")


def _mint_token(db: Session, user: User) -> str:
    sid = create_session_id()
    user.login_token = sid
    user.is_login = "Yes"
    db.add(user)
    db.commit()
    return create_access_token(user_id=user.id, email=user.email, session_id=sid)


def _correct_letters(answer: str | None) -> list[str]:
    if not answer:
        return ["A"]
    parts = [p.strip().upper() for p in str(answer).split(",") if p.strip()]
    return parts or ["A"]


def _wrong_letters(question: Question, correct: list[str]) -> list[str]:
    opts = []
    for key in ["A", "B", "C", "D", "E"]:
        if getattr(question, f"option_{key.lower()}", None):
            opts.append(key)
    wrong = [k for k in opts if k not in set(correct)]
    if not wrong:
        return correct[:1] or ["A"]
    # Single wrong for R; one wrong pick for multi
    if (question.answer_type or "R").upper() == "R":
        return [wrong[0]]
    return [wrong[0]]


def main() -> int:
    report: dict[str, Any] = {
        "started_at": datetime.utcnow().isoformat() + "Z",
        "base_url": BASE_URL,
        "exam_id": EXAM_ID,
        "steps": [],
        "pass": False,
    }

    def step(name: str, ok: bool, detail: Any = None) -> None:
        report["steps"].append({"step": name, "ok": ok, "detail": detail})
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}" + (f" — {detail}" if detail is not None else ""))

    db = SessionLocal()
    created_ue_id: int | None = None
    try:
        # Health
        with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
            try:
                r = client.get("/docs")
                step("API reachable", r.status_code == 200, r.status_code)
            except Exception as exc:
                step("API reachable", False, str(exc))
                _write_report(report)
                return 1

            user = _pick_user(db)
            token = _mint_token(db, user)
            headers = {"Authorization": f"Bearer {token}"}
            report["user"] = {
                "id": user.id,
                "email": user.email,
                "subscription": user.subscription,
            }
            step("Mint session token", True, f"user_id={user.id} email={user.email}")

            # Remove any stray open attempt so start is clean (do NOT finish them —
            # finishing would consume an attempt slot).
            open_rows = db.execute(
                text(
                    """
                    SELECT id FROM user_exam
                    WHERE user_id=:u AND exam_id=:e AND is_finish_exam <> '1'
                    """
                ),
                {"u": user.id, "e": EXAM_ID},
            ).fetchall()
            for (ueid,) in open_rows:
                db.execute(text("DELETE FROM user_answer WHERE user_exam_id=:id"), {"id": int(ueid)})
                db.execute(text("DELETE FROM user_exam WHERE id=:id"), {"id": int(ueid)})
            if open_rows:
                db.commit()
                step("Removed leftover open attempts", True, len(open_rows))

            # Ensure attempt room for the e2e run without deleting real student history.
            used = db.execute(
                text("SELECT COUNT(*) FROM user_exam WHERE user_id=:u AND exam_id=:e"),
                {"u": user.id, "e": EXAM_ID},
            ).scalar()
            max_attempts = get_max_attempts_for_user(db, user)
            if int(used or 0) >= int(max_attempts):
                empty = db.execute(
                    text(
                        """
                        SELECT ue.id
                        FROM user_exam ue
                        LEFT JOIN user_answer ua ON ua.user_exam_id = ue.id
                        WHERE ue.user_id=:u AND ue.exam_id=:e
                        GROUP BY ue.id
                        HAVING COUNT(ua.id) = 0
                        ORDER BY ue.id DESC
                        LIMIT 1
                        """
                    ),
                    {"u": user.id, "e": EXAM_ID},
                ).scalar()
                if empty:
                    db.execute(text("DELETE FROM user_exam WHERE id=:id"), {"id": int(empty)})
                    db.commit()
                    step("Removed empty leftover attempt", True, int(empty))
                else:
                    step("No attempt slot available (avoid deleting real history)", False)
                    _write_report(report)
                    return 1

            # Start
            start = client.post(f"/exams/{EXAM_ID}/start?user_id={user.id}", headers=headers)
            if start.status_code >= 400:
                step("Start exam", False, f"{start.status_code} {start.text[:300]}")
                _write_report(report)
                return 1
            start_data = start.json()
            step(
                "Start exam",
                True,
                {
                    "attempt_no": start_data.get("attempt", {}).get("attempt_no"),
                    "remaining_seconds": start_data.get("attempt", {}).get("remaining_seconds"),
                },
            )

            # End any open ORM transaction so we can see the API's committed attempt.
            db.rollback()

            # Resolve user_exam id
            ue = db.execute(
                text(
                    """
                    SELECT id, exam_question_id, is_finish_exam FROM user_exam
                    WHERE user_id=:u AND exam_id=:e
                    ORDER BY id DESC LIMIT 1
                    """
                ),
                {"u": user.id, "e": EXAM_ID},
            ).mappings().first()
            if not ue:
                step("Locate active user_exam", False, "no rows")
                _write_report(report)
                return 1
            created_ue_id = int(ue["id"])
            if str(ue["is_finish_exam"]) == "1":
                step("Locate active user_exam", False, dict(ue))
                _write_report(report)
                return 1
            qids = [int(x) for x in str(ue["exam_question_id"] or "").split(",") if x.strip().isdigit()]
            step("Active attempt", True, {"user_exam_id": created_ue_id, "question_count": len(qids)})

            # Load questions from API
            bundle = client.get(f"/exams/{EXAM_ID}/all-questions?user_id={user.id}", headers=headers)
            if bundle.status_code >= 400:
                step("Fetch all-questions", False, f"{bundle.status_code} {bundle.text[:300]}")
                _write_report(report)
                return 1
            questions = bundle.json().get("questions") or []
            step("Fetch all-questions", True, {"api_count": len(questions)})

            if len(questions) != 100:
                step("Expect 100 questions", False, len(questions))
            else:
                step("Expect 100 questions", True, 100)

            # Build answers: first 70 correct, next 20 wrong, last 10 correct
            # (gives predictable correct/wrong stats)
            db_questions = {
                q.id: q
                for q in db.query(Question).filter(Question.id.in_([qq["id"] for qq in questions])).all()
            }
            bulk_items = []
            expected_correct = 0
            expected_wrong = 0
            for idx, qp in enumerate(questions, start=1):
                qobj = db_questions.get(int(qp["id"]))
                correct = _correct_letters(qobj.answer if qobj else None)
                if idx <= 70 or idx > 90:
                    chosen = correct
                    expected_correct += 1
                else:
                    chosen = _wrong_letters(qobj, correct) if qobj else ["Z"]
                    # if forced same as correct (no wrong option), count as correct
                    if set(chosen) == set(correct):
                        expected_correct += 1
                    else:
                        expected_wrong += 1
                bulk_items.append({"question_id": int(qp["id"]), "answers": chosen})

            # Also exercise single-answer path for first 5, then bulk for all 100
            single_ok = 0
            single_fail = 0
            t0 = time.perf_counter()
            for i, item in enumerate(bulk_items[:5], start=1):
                resp = client.post(
                    f"/exams/{EXAM_ID}/answer",
                    headers=headers,
                    json={
                        "user_id": user.id,
                        "question_id": item["question_id"],
                        "display_question_id": i,
                        "answers": item["answers"],
                        "is_last_question": False,
                    },
                )
                if resp.status_code < 400:
                    single_ok += 1
                else:
                    single_fail += 1
            step(
                "Single-answer saves (first 5)",
                single_fail == 0,
                {"ok": single_ok, "fail": single_fail},
            )

            bulk = client.post(
                f"/exams/{EXAM_ID}/answers/bulk",
                headers=headers,
                json={"user_id": user.id, "answers": bulk_items},
            )
            save_ms = int((time.perf_counter() - t0) * 1000)
            if bulk.status_code >= 400:
                step("Bulk save 100 answers", False, f"{bulk.status_code} {bulk.text[:400]}")
                _write_report(report)
                return 1
            bulk_data = bulk.json()
            step(
                "Bulk save 100 answers",
                int(bulk_data.get("saved") or 0) == 100,
                {**bulk_data, "elapsed_ms": save_ms},
            )

            # DB verification before finish
            db.rollback()
            db_stats = db.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT question_id) AS answered,
                           SUM(CASE WHEN is_correct_answer='1' THEN 1 ELSE 0 END) AS correct,
                           SUM(CASE WHEN is_correct_answer='0' THEN 1 ELSE 0 END) AS incorrect,
                           COALESCE(SUM(marks - negative_mark),0) AS marks
                    FROM user_answer
                    WHERE user_exam_id=:ue AND is_attempt_question='1'
                    """
                ),
                {"ue": created_ue_id},
            ).mappings().one()
            step(
                "DB answer rows after bulk",
                int(db_stats["answered"] or 0) == 100,
                dict(db_stats),
            )

            finish = client.post(f"/exams/{EXAM_ID}/finish?user_id={user.id}", headers=headers)
            if finish.status_code >= 400:
                step("Finish exam", False, f"{finish.status_code} {finish.text[:400]}")
                _write_report(report)
                return 1
            result = finish.json()
            step(
                "Finish exam / result payload",
                True,
                {
                    "attempt_no": result.get("attempt_no"),
                    "total_questions": result.get("total_questions"),
                    "total_answered": result.get("total_answered"),
                    "total_correct": result.get("total_correct"),
                    "total_wrong": result.get("total_wrong"),
                    "total_marks": result.get("total_marks"),
                    "reviews": len(result.get("reviews") or []),
                },
            )

            # Assertions for the report
            checks = [
                ("total_questions == 100", int(result.get("total_questions") or 0) == 100),
                ("total_answered == 100", int(result.get("total_answered") or 0) == 100),
                (
                    "correct + wrong == answered",
                    int(result.get("total_correct") or 0) + int(result.get("total_wrong") or 0)
                    == int(result.get("total_answered") or 0),
                ),
                ("reviews == 100", len(result.get("reviews") or []) == 100),
                (
                    "marks within 0..100",
                    0 <= float(result.get("total_marks") or 0) <= 100,
                ),
            ]
            all_ok = True
            for name, ok in checks:
                step(f"Assert: {name}", ok)
                all_ok = all_ok and ok

            report["result"] = {
                "total_questions": result.get("total_questions"),
                "total_answered": result.get("total_answered"),
                "total_correct": result.get("total_correct"),
                "total_wrong": result.get("total_wrong"),
                "total_marks": result.get("total_marks"),
                "expected_correct_approx": expected_correct,
                "expected_wrong_approx": expected_wrong,
            }
            report["pass"] = all_ok and int(result.get("total_answered") or 0) == 100
            report["finished_at"] = datetime.utcnow().isoformat() + "Z"

            print("\n========== MOCK TEST E2E REPORT ==========")
            print(f"User: {user.email} (id={user.id})")
            print(f"Exam: {result.get('exam_title')} (id={EXAM_ID})")
            print(f"Attempt: {result.get('attempt_no')}  user_exam_id={created_ue_id}")
            print(f"Total questions: {result.get('total_questions')}")
            print(f"Answered:         {result.get('total_answered')}")
            print(f"Correct:          {result.get('total_correct')}")
            print(f"Incorrect:        {result.get('total_wrong')}")
            print(f"Marks:            {result.get('total_marks')} / {result.get('total_questions')}")
            print(f"Overall:          {'PASS' if report['pass'] else 'FAIL'}")
            print("==========================================\n")

            _write_report(report)
            return 0 if report["pass"] else 1
    finally:
        if CLEANUP and created_ue_id:
            try:
                db.execute(text("DELETE FROM user_answer WHERE user_exam_id=:id"), {"id": created_ue_id})
                db.execute(text("DELETE FROM user_exam WHERE id=:id"), {"id": created_ue_id})
                db.commit()
                print(f"Cleanup: removed user_exam {created_ue_id} and its answers")
            except Exception as exc:
                print(f"Cleanup failed: {exc}")
                db.rollback()
        db.close()


def _write_report(report: dict[str, Any]) -> None:
    out_dir = os.path.join(os.path.dirname(__file__), "..", "exports")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "e2e_mock_test_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Wrote {path}")


if __name__ == "__main__":
    sys.exit(main())
