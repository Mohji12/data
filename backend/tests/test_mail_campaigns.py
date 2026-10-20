"""Unit tests for campaign render, audience, tracking, timezone, and send idempotency."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.jobs import mail_campaign as mail_job
from app.models import (
    MailCampaign,
    MailCampaignRecipient,
    MailCampaignTemplate,
    MailClickEvent,
    MailProviderEvent,
    MailSuppression,
    User,
)
from app.services.mail_campaign_validate import classify_address, lookup_domain_status
from app.services.mail_suppression import should_skip_send, upsert_suppression
from app.routers import mail_track
from app.services.mail_campaign_audience import parse_pasted_list, resolve_audience
from app.services.mail_campaign_render import (
    dest_url_is_allowed,
    render_campaign_html,
    substitute_vars,
    wrap_links_for_tracking,
)
from app.services.mail_campaign_time import parse_ist_to_naive_utc


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    MailCampaignTemplate.__table__.create(bind=engine)
    MailCampaign.__table__.create(bind=engine)
    MailCampaignRecipient.__table__.create(bind=engine)
    MailClickEvent.__table__.create(bind=engine)
    MailSuppression.__table__.create(bind=engine)
    MailProviderEvent.__table__.create(bind=engine)
    User.__table__.create(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)()


def test_substitute_unknown_vars_blank():
    out = substitute_vars("Hi {{name}} {{unknown}} {{ email }}", {"name": "Ada", "email": "a@b.com"})
    assert out == "Hi Ada  a@b.com"


def test_render_sanitizes_and_tracks_links(monkeypatch):
    monkeypatch.setenv("API_PUBLIC_BASE_URL", "https://api.example.com")
    from app.core.config import get_settings

    get_settings.cache_clear()
    subj, html = render_campaign_html(
        subject="Hello {{name}}",
        preview_text="preview",
        hero_image="",
        body_html='<p>Hi {{name}}</p><script>alert(1)</script><a href="https://course.example/x">Go</a>',
        footer_html="<p>Bye {{unknown}}</p>",
        cta=[{"label": "Open", "url": "https://course.example/cta"}],
        values={"name": "Ada", "email": "ada@example.com", "batch": "Batch 15"},
        tracking_token="tok123",
    )
    get_settings.cache_clear()
    assert subj == "Hello Ada"
    assert "<script" not in html.lower()
    assert "alert(1)" in html
    assert "https://api.example.com/mail/t/tok123" in html
    assert "https://api.example.com/mail/u/tok123" in html
    assert "Unsubscribe" in html
    assert "Ada" in html


def test_render_embeds_hero_as_cid(tmp_path, monkeypatch):
    from app.services import uploads as uploads_mod
    from app.services.mail_campaign_render import HERO_CID, render_campaign_email

    img = tmp_path / "hero.jpg"
    img.write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(uploads_mod, "campaign_image_upload_dir", lambda: tmp_path)
    subj, html, inline = render_campaign_email(
        subject="Hi",
        preview_text="",
        hero_image="hero.jpg",
        body_html="<p>x</p>",
        footer_html="",
        cta=[],
        values={"name": "Ada"},
    )
    assert f"cid:{HERO_CID}" in html
    assert len(inline) == 1
    assert inline[0][2] == HERO_CID
    assert subj == "Hi"


def test_wrap_links_skips_already_tracked():
    html = '<a href="https://api.example.com/mail/t/abc?u=https://x.com">x</a>'
    assert wrap_links_for_tracking(html, "abc") == html


def test_dest_url_is_allowed():
    assert dest_url_is_allowed("https://criticalcareclasses.com/path")
    assert not dest_url_is_allowed("javascript:alert(1)")
    assert not dest_url_is_allowed("/relative")


def test_audience_dedupe_and_suppression():
    db = _session()
    db.add(User(email="one@ex.com", password="x", name="One", subscription="Batch 15", payment_status="Credit", approve="1"))
    db.add(User(email="unpaid@ex.com", password="x", name="No", subscription="Batch 15", payment_status="pending", approve="1"))
    db.add(User(email="blocked@ex.com", password="x", name="Block", subscription="Batch 15", payment_status="credit", approve="1"))
    db.add(MailSuppression(email="blocked@ex.com", reason="unsubscribe"))
    db.commit()
    # unique email on User will reject ONE@ex.com on some DBs; sqlite unique is case-sensitive
    out = resolve_audience(db, "batch", {"batches": ["Batch 15"]})
    emails = {r["email"] for r in out["recipients"]}
    assert "one@ex.com" in emails
    assert "blocked@ex.com" not in emails
    assert "unpaid@ex.com" not in emails

    extra: dict[str, int] = {}
    pasted, invalid, dupes = parse_pasted_list("a@b.com\na@b.com\nnot-an-email\nc@d.com,Ada,B15", extra)
    assert [r["email"] for r in pasted] == ["a@b.com", "c@d.com"]
    assert dupes == 1
    assert extra == {"a@b.com": 1}
    assert invalid == ["not-an-email"]

    listed_dupes = resolve_audience(db, "list", {"pasted": "keep@ex.com\nkeep@ex.com\nkeep@ex.com\nother@ex.com"})
    assert listed_dupes["duplicate_count"] == 2
    assert listed_dupes["duplicate_address_count"] == 1
    assert listed_dupes["duplicate_emails"][0]["email"] == "keep@ex.com"
    assert listed_dupes["duplicate_emails"][0]["total"] == 3

    bulk, bulk_invalid, bulk_dupes = parse_pasted_list("one@ex.com, two@ex.com; three@ex.com\nfour@ex.com")
    assert [r["email"] for r in bulk] == ["one@ex.com", "two@ex.com", "three@ex.com", "four@ex.com"]
    assert bulk_invalid == []
    assert bulk_dupes == 0

    listed = resolve_audience(db, "list", {"pasted": "blocked@ex.com\nnew@ex.com"})
    emails = {r["email"] for r in listed["recipients"]}
    assert "new@ex.com" in emails
    assert "blocked@ex.com" not in emails
    db.close()


def test_schedule_ist_to_utc():
    dt = parse_ist_to_naive_utc("2026-10-20T16:00")
    assert dt is not None
    # 16:00 IST is 10:30 UTC
    assert dt == datetime(2026, 10, 20, 10, 30, 0)
    aware = parse_ist_to_naive_utc("2026-10-20T10:30:00+00:00")
    assert aware == datetime(2026, 10, 20, 10, 30, 0)


def test_tracking_records_click_and_unsubscribe():
    db = _session()
    tpl = MailCampaignTemplate(name="t", subject="s", body_html="<p>x</p>")
    db.add(tpl)
    db.commit()
    camp = MailCampaign(name="c", template_id=tpl.id, audience_type="list", audience_json="{}", status="sent")
    db.add(camp)
    db.commit()
    rec = MailCampaignRecipient(
        campaign_id=camp.id,
        email="ada@example.com",
        name="Ada",
        batch="B15",
        status="accepted",
        tracking_token="token-ada",
    )
    db.add(rec)
    db.commit()

    class _Req:
        client = type("C", (), {"host": "1.2.3.4"})()
        headers = {"user-agent": "pytest"}

    resp = mail_track.mail_click_track("token-ada", _Req(), u="https://course.example/x", db=db)
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://course.example/x"
    clicks = db.query(MailClickEvent).all()
    assert len(clicks) == 1
    assert clicks[0].recipient_id == rec.id

    mail_track.mail_unsubscribe("token-ada", db)
    row = db.query(MailSuppression).filter(MailSuppression.email == "ada@example.com").first()
    assert row is not None
    db.close()


def test_send_skips_suppressed_and_does_not_double_send(monkeypatch):
    db = _session()
    tpl = MailCampaignTemplate(
        name="t",
        subject="Hello {{name}}",
        body_html="<p>Hi</p>",
        cta_json='[{"label":"Go","url":"https://example.com"}]',
    )
    db.add(tpl)
    db.commit()
    camp = MailCampaign(name="c", template_id=tpl.id, audience_type="list", audience_json="{}", status="queued")
    db.add(camp)
    db.commit()
    rec_ok = MailCampaignRecipient(
        campaign_id=camp.id, email="ok@ex.com", name="Ok", status="pending", tracking_token="t-ok"
    )
    rec_blocked = MailCampaignRecipient(
        campaign_id=camp.id, email="no@ex.com", name="No", status="pending", tracking_token="t-no"
    )
    rec_done = MailCampaignRecipient(
        campaign_id=camp.id, email="done@ex.com", name="Done", status="accepted", tracking_token="t-done"
    )
    db.add_all([rec_ok, rec_blocked, rec_done])
    db.add(MailSuppression(email="no@ex.com", reason="unsubscribe"))
    db.commit()
    cid = camp.id

    sent: list[str] = []

    def fake_send(to_email, subject, html, **kwargs):
        sent.append(to_email)

    class KeepOpen:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def close(self):
            return None

    monkeypatch.setattr(mail_job, "SessionLocal", lambda: KeepOpen(db))
    monkeypatch.setattr(mail_job, "send_html_email", fake_send)
    monkeypatch.setattr(mail_job, "pre_send_reject_reason", lambda _e: None)
    monkeypatch.setattr(mail_job.time, "sleep", lambda _s: None)

    first = mail_job.send_campaign(cid)
    assert first["ok"] is True
    assert sent == ["ok@ex.com"]
    db.refresh(rec_ok)
    db.refresh(rec_blocked)
    db.refresh(rec_done)
    assert rec_ok.status == "accepted"
    assert rec_blocked.status == "suppressed"
    assert rec_done.status == "accepted"

    second = mail_job.send_campaign(cid)
    assert second.get("already_sent") is True or second.get("status") == "sent"
    assert sent == ["ok@ex.com"]
    db.close()


def test_send_campaign_pauses_between_waves(monkeypatch):
    db = _session()
    tpl = MailCampaignTemplate(name="t", subject="Hello", body_html="<p>Hi</p>")
    db.add(tpl)
    db.commit()
    camp = MailCampaign(
        name="c",
        template_id=tpl.id,
        audience_type="list",
        audience_json="{}",
        status="queued",
        send_batch_size=2,
        send_pause_seconds=300,
    )
    db.add(camp)
    db.commit()
    recs = [
        MailCampaignRecipient(campaign_id=camp.id, email=f"u{i}@ex.com", name=f"U{i}", status="pending", tracking_token=f"t-{i}")
        for i in range(5)
    ]
    db.add_all(recs)
    db.commit()
    cid = camp.id
    sent: list[str] = []
    delayed: list[int] = []

    def fake_send(to_email, subject, html, **kwargs):
        sent.append(to_email)

    class KeepOpen:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def close(self):
            return None

    monkeypatch.setattr(mail_job, "SessionLocal", lambda: KeepOpen(db))
    monkeypatch.setattr(mail_job, "send_html_email", fake_send)
    monkeypatch.setattr(mail_job, "pre_send_reject_reason", lambda _e: None)
    monkeypatch.setattr(mail_job.time, "sleep", lambda _s: None)
    monkeypatch.setattr("app.core.job_queue.enqueue_mail_send", lambda campaign_id, delay_seconds=0: delayed.append(delay_seconds) or True)

    first = mail_job.send_campaign(cid)
    assert first["waiting_next_wave"] is True
    assert first["pending"] == 3
    assert sent == ["u0@ex.com", "u1@ex.com"]
    db.refresh(camp)
    assert camp.status == "sending"
    assert camp.next_wave_at is not None
    assert delayed == [300]

    early = mail_job.send_campaign(cid)
    assert early.get("waiting_next_wave") is True
    assert sent == ["u0@ex.com", "u1@ex.com"]

    camp.next_wave_at = datetime(2020, 1, 1)
    camp.lock_token = None
    db.commit()
    second = mail_job.send_campaign(cid)
    assert second["waiting_next_wave"] is True
    assert sent == ["u0@ex.com", "u1@ex.com", "u2@ex.com", "u3@ex.com"]

    camp.next_wave_at = datetime(2020, 1, 1)
    camp.lock_token = None
    db.commit()
    third = mail_job.send_campaign(cid)
    assert third.get("status") == "sent"
    assert sent[-1] == "u4@ex.com"
    db.refresh(camp)
    assert camp.status == "sent"
    assert camp.next_wave_at is None
    db.close()


def test_poll_due_sends_scheduled_campaign(monkeypatch):
    db = _session()
    tpl = MailCampaignTemplate(name="t", subject="Hello", body_html="<p>Hi</p>")
    db.add(tpl)
    db.commit()
    camp = MailCampaign(
        name="c",
        template_id=tpl.id,
        audience_type="list",
        audience_json="{}",
        status="scheduled",
        scheduled_at=datetime(2020, 1, 1),
        send_batch_size=10,
        send_pause_seconds=60,
    )
    db.add(camp)
    db.commit()
    rec = MailCampaignRecipient(
        campaign_id=camp.id, email="due@ex.com", name="Due", status="pending", tracking_token="t-due"
    )
    db.add(rec)
    db.commit()
    cid = camp.id
    sent: list[str] = []

    def fake_send(to_email, subject, html, **kwargs):
        sent.append(to_email)

    class KeepOpen:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def close(self):
            return None

    monkeypatch.setattr(mail_job, "SessionLocal", lambda: KeepOpen(db))
    monkeypatch.setattr(mail_job, "send_html_email", fake_send)
    monkeypatch.setattr(mail_job, "pre_send_reject_reason", lambda _e: None)
    monkeypatch.setattr(mail_job.time, "sleep", lambda _s: None)
    monkeypatch.setattr(mail_job, "_enqueue_self_poll", lambda: None)
    monkeypatch.setattr("app.core.job_queue.enqueue_mail_send", lambda *a, **k: True)

    out = mail_job.poll_due_campaigns(requeue=False)
    assert out["started"] == 1
    assert sent == ["due@ex.com"]
    db.refresh(camp)
    db.refresh(rec)
    assert rec.status == "accepted"
    assert camp.status == "sent"
    db.close()


def test_send_campaign_no_pause_sends_all(monkeypatch):
    db = _session()
    tpl = MailCampaignTemplate(name="t", subject="Hello", body_html="<p>Hi</p>")
    db.add(tpl)
    db.commit()
    camp = MailCampaign(
        name="c",
        template_id=tpl.id,
        audience_type="list",
        audience_json="{}",
        status="queued",
        send_batch_size=2,
        send_pause_seconds=0,
    )
    db.add(camp)
    db.commit()
    db.add_all(
        [
            MailCampaignRecipient(campaign_id=camp.id, email=f"u{i}@ex.com", name=f"U{i}", status="pending", tracking_token=f"n-{i}")
            for i in range(3)
        ]
    )
    db.commit()
    cid = camp.id
    sent: list[str] = []

    def fake_send(to_email, subject, html, **kwargs):
        sent.append(to_email)

    class KeepOpen:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def close(self):
            return None

    monkeypatch.setattr(mail_job, "SessionLocal", lambda: KeepOpen(db))
    monkeypatch.setattr(mail_job, "send_html_email", fake_send)
    monkeypatch.setattr(mail_job, "pre_send_reject_reason", lambda _e: None)
    monkeypatch.setattr(mail_job.time, "sleep", lambda _s: None)

    out = mail_job.send_campaign(cid)
    assert out["status"] == "sent"
    assert sent == ["u0@ex.com", "u1@ex.com", "u2@ex.com"]
    db.close()


def test_classify_syntax_and_disposable(monkeypatch):
    lookup_domain_status.cache_clear()
    monkeypatch.setattr("app.services.mail_campaign_validate.lookup_domain_status", lambda _d: "ok")
    bad = classify_address("not-an-email", check_dns=False)
    assert bad["flag"] == "invalid"
    disp = classify_address("a@mailinator.com", check_dns=False)
    assert disp["disposable"] is True
    role = classify_address("noreply@hospital.org", check_dns=False)
    assert role["role_warning"] is True
    assert role["flag"] == "invalid"


def test_dns_timeout_is_unverified(monkeypatch):
    lookup_domain_status.cache_clear()
    monkeypatch.setattr("app.services.mail_campaign_validate.lookup_domain_status", lambda _d: "unverified")
    out = classify_address("ada@example.com", check_dns=True)
    assert out["dns_status"] == "unverified"
    assert out["syntax_ok"] is True


def test_dns_nxdomain_is_invalid(monkeypatch):
    lookup_domain_status.cache_clear()
    monkeypatch.setattr("app.services.mail_campaign_validate.lookup_domain_status", lambda _d: "invalid")
    out = classify_address("ada@no-such-domain.invalid", check_dns=True)
    assert out["flag"] == "invalid"


def test_suppression_strength_and_skip_rules():
    db = _session()
    row = upsert_suppression(db, "a@ex.com", "hard_bounce", source="zepto_webhook")
    db.commit()
    assert should_skip_send(row, True) is True
    assert should_skip_send(row, False) is True
    upsert_suppression(db, "a@ex.com", "unsubscribe", source="unsubscribe_link")
    db.commit()
    row = db.query(MailSuppression).filter(MailSuppression.email == "a@ex.com").first()
    assert row.reason == "unsubscribe"
    upsert_suppression(db, "a@ex.com", "hard_bounce", source="zepto_webhook")
    db.commit()
    db.refresh(row)
    assert row.reason == "unsubscribe"
    assert should_skip_send(row, False) is True
    db.close()


def test_send_never_delivers_hard_bounce(monkeypatch):
    db = _session()
    tpl = MailCampaignTemplate(name="t", subject="Hello", body_html="<p>Hi</p>")
    db.add(tpl)
    db.commit()
    camp = MailCampaign(
        name="c",
        template_id=tpl.id,
        audience_type="list",
        audience_json="{}",
        status="queued",
        skip_previously_bounced=True,
    )
    db.add(camp)
    db.commit()
    rec = MailCampaignRecipient(campaign_id=camp.id, email="bounce@ex.com", name="B", status="pending", tracking_token="tb")
    db.add(rec)
    upsert_suppression(db, "bounce@ex.com", "hard_bounce", source="zepto_webhook")
    db.commit()
    sent: list[str] = []

    class KeepOpen:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def close(self):
            return None

    monkeypatch.setattr(mail_job, "SessionLocal", lambda: KeepOpen(db))
    monkeypatch.setattr(mail_job, "send_html_email", lambda *a, **k: sent.append(a[0]))
    monkeypatch.setattr(mail_job, "pre_send_reject_reason", lambda _e: None)
    monkeypatch.setattr(mail_job.time, "sleep", lambda _s: None)
    mail_job.send_campaign(camp.id)
    db.refresh(rec)
    assert rec.status == "suppressed"
    assert sent == []
    camp.skip_previously_bounced = False
    camp.status = "queued"
    camp.lock_token = None
    rec.status = "pending"
    db.commit()
    mail_job.send_campaign(camp.id)
    db.refresh(rec)
    assert rec.status == "suppressed"
    assert sent == []
    db.close()


def test_send_blocks_invalid_domain_and_smtp_5xx(monkeypatch):
    db = _session()
    tpl = MailCampaignTemplate(name="t", subject="Hello", body_html="<p>Hi</p>")
    db.add(tpl)
    db.commit()
    camp = MailCampaign(name="c", template_id=tpl.id, audience_type="list", audience_json="{}", status="queued")
    db.add(camp)
    db.commit()
    rec_bad = MailCampaignRecipient(
        campaign_id=camp.id, email="ghost@no-mx.invalid", name="G", status="pending", tracking_token="tbad"
    )
    rec_smtp = MailCampaignRecipient(
        campaign_id=camp.id, email="gone@ex.com", name="S", status="pending", tracking_token="tsmtp"
    )
    db.add_all([rec_bad, rec_smtp])
    db.commit()

    class KeepOpen:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def close(self):
            return None

    def fake_send(to_email, subject, html, **kwargs):
        if to_email == "gone@ex.com":
            raise RuntimeError("550 5.1.1 user unknown")

    monkeypatch.setattr(mail_job, "SessionLocal", lambda: KeepOpen(db))
    monkeypatch.setattr(mail_job, "send_html_email", fake_send)
    monkeypatch.setattr(mail_job, "pre_send_reject_reason", lambda email: "invalid" if email.endswith(".invalid") else None)
    monkeypatch.setattr(mail_job.time, "sleep", lambda _s: None)
    mail_job.send_campaign(camp.id)
    db.refresh(rec_bad)
    db.refresh(rec_smtp)
    assert rec_bad.status == "suppressed"
    assert rec_smtp.status == "suppressed"
    blocked = db.query(MailSuppression).filter(MailSuppression.email == "gone@ex.com").first()
    assert blocked is not None
    assert blocked.reason == "hard_bounce"
    assert blocked.source == "smtp_5xx"
    db.close()
