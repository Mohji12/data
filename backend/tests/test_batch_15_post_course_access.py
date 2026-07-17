"""Batch 15 post-course access: video/mock closed, certificates for non-extension users."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.access import (
    can_access_certificate,
    can_access_mock_test,
    can_access_video_library,
    ensure_one_time_batch_access,
    is_certificate_only_user,
)

BATCH = "Batch 15"


def _user(**kwargs):
    defaults = {
        "id": 1,
        "subscription": BATCH,
        "payment_status": "Credit",
        "approve": "1",
        "package_id": 10,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _options(**overrides):
    base = {
        "batch_access_closed::batch-15": "1",
        "extension_base_date::batch-15": "2026-07-15",
        "display_download_certificate": "1",
        "access_download_certificate": BATCH,
        "certificate_enabled::batch-15": "1",
        "certificate_batch_label::batch-15": BATCH,
        "display_video_library_link": "1",
        "access_video_library_link": BATCH,
        "access_quiz_link": BATCH,
        "certificate_only_access": "",
    }
    base.update(overrides)
    return base


def _option_getter(options: dict):
    def _get(_db, key: str) -> str:
        return options.get(key, "")

    return _get


@patch("app.services.access.has_active_subscription")
@patch("app.services.access._user_has_extension_payment")
@patch("app.services.access.get_option_value")
def test_standard_user_blocked_from_video_and_mock_when_batch_closed(
    mock_get_option, mock_has_ext_payment, mock_has_active_sub
):
    mock_get_option.side_effect = _option_getter(_options())
    mock_has_ext_payment.return_value = False
    mock_has_active_sub.return_value = True
    db = MagicMock()
    user = _user()

    ok, reason = ensure_one_time_batch_access(db, user)
    assert ok is False
    assert "ended" in (reason or "").lower()

    video_ok, _ = can_access_video_library(db, user)
    mock_ok, _ = can_access_mock_test(db, user)
    assert video_ok is False
    assert mock_ok is False


@patch("app.services.access.has_active_subscription")
@patch("app.services.access._user_has_extension_payment")
@patch("app.services.access.get_option_value")
def test_extension_user_keeps_video_and_mock_while_extended(
    mock_get_option, mock_has_ext_payment, mock_has_active_sub
):
    mock_get_option.side_effect = _option_getter(_options())
    mock_has_ext_payment.return_value = True
    mock_has_active_sub.return_value = True
    db = MagicMock()
    user = _user()

    ok, _ = ensure_one_time_batch_access(db, user)
    assert ok is True

    video_ok, _ = can_access_video_library(db, user)
    mock_ok, _ = can_access_mock_test(db, user)
    assert video_ok is True
    assert mock_ok is True


@patch("app.services.access.has_active_subscription")
@patch("app.services.access._user_has_extension_payment")
@patch("app.services.access.get_option_value")
def test_extension_user_certificate_blocked_until_extension_ends(
    mock_get_option, mock_has_ext_payment, mock_has_active_sub
):
    mock_get_option.side_effect = _option_getter(_options())
    mock_has_ext_payment.return_value = True
    mock_has_active_sub.return_value = True
    db = MagicMock()
    user = _user()

    cert_ok, reason = can_access_certificate(db, user)
    assert cert_ok is False
    assert "extended" in (reason or "").lower()


@patch("app.services.access.has_active_subscription")
@patch("app.services.access._user_has_extension_payment")
@patch("app.services.access.get_option_value")
def test_standard_user_gets_certificate_after_batch_closed(
    mock_get_option, mock_has_ext_payment, mock_has_active_sub
):
    mock_get_option.side_effect = _option_getter(_options())
    mock_has_ext_payment.return_value = False
    mock_has_active_sub.return_value = False
    db = MagicMock()
    user = _user()

    cert_ok, reason = can_access_certificate(db, user)
    assert cert_ok is True
    assert reason is None


@patch("app.services.access.has_active_subscription")
@patch("app.services.access._user_has_extension_payment")
@patch("app.services.access.get_option_value")
def test_extension_user_gets_certificate_after_extension_window(
    mock_get_option, mock_has_ext_payment, mock_has_active_sub
):
    mock_get_option.side_effect = _option_getter(_options())
    mock_has_ext_payment.return_value = True
    mock_has_active_sub.return_value = False
    db = MagicMock()
    user = _user()

    cert_ok, _ = can_access_certificate(db, user)
    assert cert_ok is True

    video_ok, _ = can_access_video_library(db, user)
    assert video_ok is False


@patch("app.services.access.has_active_subscription")
@patch("app.services.access._user_has_extension_payment")
@patch("app.services.access.get_option_value")
def test_extension_user_not_certificate_only_even_when_batch_listed(
    mock_get_option, mock_has_ext_payment, mock_has_active_sub
):
    """certificate_only_access must not block users with an active 2-month extension."""
    mock_get_option.side_effect = _option_getter(
        _options(certificate_only_access=BATCH)
    )
    mock_has_ext_payment.return_value = True
    mock_has_active_sub.return_value = True
    db = MagicMock()
    user = _user()

    assert is_certificate_only_user(db, user) is False

    video_ok, _ = can_access_video_library(db, user)
    mock_ok, _ = can_access_mock_test(db, user)
    assert video_ok is True
    assert mock_ok is True
