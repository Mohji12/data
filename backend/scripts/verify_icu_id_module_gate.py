"""Quick verification for ICU-ID module exam gate (dev)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from app.models import FolderMaster, QuizExam, User, Video, UserVideoProgress
from app.services.module_exam_gate import (
    exam_module_unlocked,
    folder_id_for_exam,
    folder_video_completion,
)
from app.services.video_progress import WATCHED_THRESHOLD_SECONDS

BATCH = "ICU-ID Certification Course"


def main() -> None:
    db = SessionLocal()
    folders = (
        db.query(FolderMaster)
        .filter(FolderMaster.name.like("Module %"), FolderMaster.batch == BATCH)
        .count()
    )
    exams = db.query(QuizExam).filter(QuizExam.batch == BATCH).count()
    print(f"folders={folders} exams={exams}")
    assert folders == 10 and exams == 10, "expected 10 folders and 10 exams"

    e = db.query(QuizExam).filter(QuizExam.title == "Module 1 Test").first()
    assert e is not None
    fid = folder_id_for_exam(db, e.id)
    assert fid is not None
    print(f"Module 1 Test exam_id={e.id} folder_id={fid}")

    u = db.query(User).filter(User.subscription == BATCH).first()
    if not u:
        u = db.query(User).filter(User.subscription.like(f"%{BATCH}%")).first()
    if not u:
        u = db.query(User).order_by(User.id).first()
        if not u:
            print("No users in DB; seed folders/exams/map only.")
            db.close()
            print("verify_icu_id_module_gate: OK")
            return
        print(f"No ICU-ID subscription user; using user_id={u.id} with in-memory subscription={BATCH!r}.")
        u.subscription = BATCH

    print(f"user_id={u.id} subscription={u.subscription!r}")
    comp = folder_video_completion(db, u.id, fid)
    unlocked, reason, _folder_name = exam_module_unlocked(db, u, e)
    print(f"completion={comp} unlocked={unlocked} reason={reason!r}")

    # If Module 1 has videos, simulate full watch on first video only -> still locked if >1 video
    vids = (
        db.query(Video)
        .filter(Video.status == "1", Video.folder.contains(str(fid)))
        .limit(5)
        .all()
    )
    if vids:
        v = vids[0]
        prog = (
            db.query(UserVideoProgress)
            .filter(UserVideoProgress.user_id == u.id, UserVideoProgress.video_id == v.id)
            .first()
        )
        if not prog:
            prog = UserVideoProgress(user_id=u.id, video_id=v.id, watched_seconds=0)
            db.add(prog)
        prog.watched_seconds = WATCHED_THRESHOLD_SECONDS
        db.commit()
        comp2 = folder_video_completion(db, u.id, fid)
        unlocked2, _, _ = exam_module_unlocked(db, u, e)
        print(f"after 1 video at threshold: completion={comp2} unlocked={unlocked2}")
    else:
        print("No videos in Module 1 folder — creating ephemeral test video.")
        test_vid = Video(
            title="[verify] ICU-ID Module 1 gate",
            description="auto",
            image="",
            video_link="https://example.com/verify",
            folder=str(fid),
            batch=BATCH,
            status="1",
        )
        db.add(test_vid)
        db.flush()
        prog = UserVideoProgress(
            user_id=u.id,
            video_id=test_vid.id,
            watched_seconds=WATCHED_THRESHOLD_SECONDS,
        )
        db.add(prog)
        db.commit()
        comp3 = folder_video_completion(db, u.id, fid)
        unlocked3, _, _ = exam_module_unlocked(db, u, e)
        print(f"ephemeral video: completion={comp3} unlocked={unlocked3}")
        assert comp3["complete"] and unlocked3, "expected unlock after full watch"
        e2 = db.query(QuizExam).filter(QuizExam.title == "Module 2 Test").first()
        if e2:
            unlocked_m2, hint2, _ = exam_module_unlocked(db, u, e2)
            assert not unlocked_m2, "module 2 should stay locked without its videos"
            print(f"Module 2 Test unlocked={unlocked_m2} hint={hint2!r}")
        db.delete(prog)
        db.delete(test_vid)
        db.commit()
        print("cleaned up ephemeral video")

    db.close()
    print("verify_icu_id_module_gate: OK")


if __name__ == "__main__":
    main()
