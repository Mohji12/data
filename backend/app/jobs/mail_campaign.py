"""RQ jobs: poll due campaigns and send in batches."""

from __future__ import annotations

import logging
import smtplib
import time
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, or_

from app.db import SessionLocal
from app.models import MailCampaign, MailCampaignRecipient, MailCampaignTemplate
from app.services.mail_campaign_render import parse_cta_list, render_campaign_email
from app.services.mail_suppression import lookup_suppression, should_skip_send
from app.services.mailer import send_html_email

logger = logging.getLogger(__name__)

BATCH_SIZE = 25
SEND_DELAY_SEC = 0.1
DEFAULT_WAVE_SIZE = 100
DEFAULT_PAUSE_SEC = 300


def _wave_settings(camp: MailCampaign) -> tuple[int, int]:
    size_raw = getattr(camp, "send_batch_size", None)
    pause_raw = getattr(camp, "send_pause_seconds", None)
    size = int(size_raw) if size_raw is not None else DEFAULT_WAVE_SIZE
    pause = int(pause_raw) if pause_raw is not None else DEFAULT_PAUSE_SEC
    return max(1, min(size, 5000)), max(0, min(pause, 86400))


def _is_transient_smtp(exc: Exception) -> bool:
    if isinstance(exc, (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, TimeoutError, ConnectionError)):
        return True
    msg = str(exc).lower()
    return any(token in msg for token in ("timeout", "temporarily", "connection", "421", "450", "451", "452"))


def _deliver(to_email: str, subject: str, html: str, inline_images=None, extra_headers=None) -> None:
    try:
        send_html_email(to_email, subject, html, inline_images=inline_images, extra_headers=extra_headers)
    except Exception as exc:
        if not _is_transient_smtp(exc):
            raise
        time.sleep(0.4)
        send_html_email(to_email, subject, html, inline_images=inline_images, extra_headers=extra_headers)


def _enqueue_self_poll() -> None:
    try:
        from app.core.job_queue import enqueue_mail_poll

        enqueue_mail_poll(delay_seconds=60)
    except Exception as exc:
        logger.warning("Could not requeue mail poller: %s", exc)


def poll_due_campaigns(requeue: bool = True) -> dict:
    db = SessionLocal()
    started = 0
    try:
        now = datetime.utcnow()
        due = (
            db.query(MailCampaign)
            .filter(MailCampaign.status == "scheduled", MailCampaign.scheduled_at <= now)
            .all()
        )
        due += (
            db.query(MailCampaign)
            .filter(
                MailCampaign.status == "sending",
                MailCampaign.next_wave_at.isnot(None),
                MailCampaign.next_wave_at <= now,
            )
            .all()
        )
        seen: set[int] = set()
        for camp in due:
            if camp.id in seen:
                continue
            seen.add(camp.id)
            updated = (
                db.query(MailCampaign)
                .filter(
                    MailCampaign.id == camp.id,
                    MailCampaign.status.in_(["scheduled", "sending"]),
                    MailCampaign.lock_token.is_(None),
                )
                .update({"status": "queued", "lock_token": None, "next_wave_at": None}, synchronize_session=False)
            )
            db.commit()
            if not updated:
                continue
            from app.core.job_queue import enqueue_mail_send

            enqueue_mail_send(camp.id)
            send_campaign(camp.id)
            started += 1
        return {"started": started}
    finally:
        db.close()
        if requeue:
            _enqueue_self_poll()


def _pending_count(db, campaign_id: int) -> int:
    return (
        db.query(func.count(MailCampaignRecipient.id))
        .filter(
            MailCampaignRecipient.campaign_id == campaign_id,
            MailCampaignRecipient.status.in_(["pending", "queued"]),
        )
        .scalar()
        or 0
    )


def _refresh_counts(db, camp: MailCampaign) -> None:
    campaign_id = camp.id
    camp.accepted_count = (
        db.query(func.count(MailCampaignRecipient.id))
        .filter(MailCampaignRecipient.campaign_id == campaign_id, MailCampaignRecipient.status == "accepted")
        .scalar()
        or 0
    )
    camp.failed_count = (
        db.query(func.count(MailCampaignRecipient.id))
        .filter(MailCampaignRecipient.campaign_id == campaign_id, MailCampaignRecipient.status == "failed")
        .scalar()
        or 0
    )
    camp.suppressed_count = (
        db.query(func.count(MailCampaignRecipient.id))
        .filter(MailCampaignRecipient.campaign_id == campaign_id, MailCampaignRecipient.status == "suppressed")
        .scalar()
        or 0
    )


def _finish_or_pause(db, camp: MailCampaign, pause_sec: int) -> dict:
    _refresh_counts(db, camp)
    pending_left = _pending_count(db, camp.id)
    fail_n = int(camp.failed_count or 0)
    ok_n = int(camp.accepted_count or 0)
    if pending_left > 0:
        if pause_sec > 0:
            camp.status = "sending"
            camp.next_wave_at = datetime.utcnow() + timedelta(seconds=pause_sec)
            camp.lock_token = None
            db.commit()
            from app.core.job_queue import enqueue_mail_send

            enqueue_mail_send(camp.id, delay_seconds=pause_sec)
            return {
                "ok": True,
                "status": "sending",
                "waiting_next_wave": True,
                "next_wave_at": camp.next_wave_at.isoformat() + "Z" if camp.next_wave_at else None,
                "accepted": camp.accepted_count,
                "failed": camp.failed_count,
                "pending": pending_left,
            }
        return {"continue": True, "pending": pending_left}

    camp.lock_token = None
    camp.next_wave_at = None
    if fail_n and ok_n:
        camp.status = "partially_failed"
    elif fail_n and not ok_n:
        camp.status = "failed"
    else:
        camp.status = "sent"
        camp.sent_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "status": camp.status, "accepted": camp.accepted_count, "failed": camp.failed_count}


def send_campaign(campaign_id: int) -> dict:
    db = SessionLocal()
    try:
        camp = db.query(MailCampaign).filter(MailCampaign.id == campaign_id).first()
        if not camp:
            return {"ok": False, "error": "campaign not found"}
        if camp.status == "cancelled":
            return {"ok": True, "cancelled": True}
        if camp.status == "sent":
            return {"ok": True, "already_sent": True}
        if camp.status == "draft":
            return {"ok": False, "error": "campaign not confirmed"}
        if camp.status == "failed":
            return {"ok": True, "status": "failed"}

        now = datetime.utcnow()
        token = uuid.uuid4().hex
        claimed = (
            db.query(MailCampaign)
            .filter(
                MailCampaign.id == campaign_id,
                MailCampaign.status.in_(["queued", "sending", "partially_failed", "scheduled"]),
                MailCampaign.lock_token.is_(None),
            )
            .filter(or_(MailCampaign.next_wave_at.is_(None), MailCampaign.next_wave_at <= now))
            .update(
                {"status": "sending", "lock_token": token, "next_wave_at": None},
                synchronize_session=False,
            )
        )
        db.commit()
        if not claimed:
            db.refresh(camp)
            if camp.next_wave_at and camp.next_wave_at > now:
                return {"ok": True, "waiting_next_wave": True, "status": camp.status}
            return {"ok": True, "skipped": True, "status": camp.status}

        db.refresh(camp)
        try:
            return _send_claimed_campaign(db, camp)
        except Exception:
            try:
                db.refresh(camp)
                if camp.lock_token:
                    camp.lock_token = None
                    db.commit()
            except Exception:
                db.rollback()
            raise
    finally:
        db.close()


def _send_claimed_campaign(db, camp: MailCampaign) -> dict:
    campaign_id = camp.id
    tpl = db.query(MailCampaignTemplate).filter(MailCampaignTemplate.id == camp.template_id).first()
    if not tpl:
        camp.status = "failed"
        camp.lock_token = None
        db.commit()
        return {"ok": False, "error": "template missing"}

    subject = (camp.subject_override or tpl.subject or "").strip()
    preview = (camp.preview_text_override or tpl.preview_text or "").strip()
    cta = parse_cta_list(tpl.cta_json)
    skip_bounced = bool(getattr(camp, "skip_previously_bounced", True))
    wave_size, pause_sec = _wave_settings(camp)

    while True:
        processed_this_wave = 0
        while processed_this_wave < wave_size:
            db.refresh(camp)
            if camp.status == "cancelled":
                camp.lock_token = None
                db.commit()
                return {"ok": True, "cancelled": True}

            rec = (
                db.query(MailCampaignRecipient)
                .filter(
                    MailCampaignRecipient.campaign_id == campaign_id,
                    MailCampaignRecipient.status.in_(["pending", "queued"]),
                )
                .order_by(MailCampaignRecipient.id.asc())
                .first()
            )
            if not rec:
                break
            processed_this_wave += 1
            email = (rec.email or "").strip().lower()
            if should_skip_send(lookup_suppression(db, email), skip_bounced):
                rec.status = "suppressed"
                db.add(rec)
                _refresh_counts(db, camp)
                db.commit()
                continue
            rec.attempt_count = int(rec.attempt_count or 0) + 1
            rec.status = "queued"
            db.add(rec)
            db.flush()
            _, html, inline = render_campaign_email(
                subject=subject,
                preview_text=preview,
                hero_image=tpl.hero_image or "",
                body_html=tpl.body_html or "",
                footer_html=tpl.footer_html or "",
                cta=cta,
                values={"name": rec.name or "", "email": rec.email or "", "batch": rec.batch or ""},
                tracking_token=rec.tracking_token,
            )
            try:
                _deliver(
                    rec.email,
                    subject,
                    html,
                    inline,
                    extra_headers={"X-TM-CLIENT-REF": f"{campaign_id}:{rec.id}"},
                )
                rec.status = "accepted"
                rec.accepted_at = datetime.utcnow()
                rec.last_error = None
            except Exception as exc:
                rec.status = "failed"
                rec.last_error = str(exc)[:2000]
                logger.warning("campaign %s send failed %s: %s", campaign_id, rec.email, exc)
            db.add(rec)
            _refresh_counts(db, camp)
            db.commit()
            time.sleep(SEND_DELAY_SEC)

        outcome = _finish_or_pause(db, camp, pause_sec)
        if outcome.get("continue"):
            continue
        return outcome
