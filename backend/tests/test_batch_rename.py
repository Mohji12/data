"""Tests for batch rename cascade helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.batch_rename import (
    batch_slug_alias_option_key,
    brochure_option_key,
    register_slug_alias,
    rename_batch_references,
    replace_csv_token,
)
from app.services.registration import _resolve_batch_by_slug_alias


def test_replace_csv_token_single_match():
    assert replace_csv_token("Batch 15,CP 7", "Batch 15", "CCM Batch 15") == "CCM Batch 15,CP 7"


def test_replace_csv_token_case_insensitive():
    assert replace_csv_token("batch 15,CP 7", "Batch 15", "CCM Batch 15") == "CCM Batch 15,CP 7"


def test_replace_csv_token_no_match():
    assert replace_csv_token("CP 7,CP 8", "Batch 15", "CCM Batch 15") == "CP 7,CP 8"


def test_replace_csv_token_empty_and_whitespace():
    assert replace_csv_token("", "Batch 15", "New") == ""
    assert replace_csv_token("  Batch 15 , CP 7 ", "Batch 15", "New") == "New,CP 7"


def test_replace_csv_token_duplicate_tokens():
    assert replace_csv_token("Batch 15,Batch 15", "Batch 15", "New") == "New,New"


def test_batch_slug_alias_option_key():
    assert batch_slug_alias_option_key("Batch-15") == "batch_slug_alias::batch-15"


def test_brochure_option_key_casefold():
    assert brochure_option_key("Batch 15") == "batch_brochure::batch 15"


def test_rename_batch_references_noop_same_name():
    db = MagicMock()
    counts = rename_batch_references(db, "Batch 15", "batch 15", 1, dry_run=True)
    assert counts["users"] == 0
    db.query.assert_not_called()


def test_rename_batch_references_collision_raises():
    db = MagicMock()
    conflict = MagicMock()
    conflict.first.return_value = (99,)
    db.query.return_value.filter.return_value = conflict

    with pytest.raises(HTTPException) as exc:
        rename_batch_references(db, "Batch 15", "CCM Batch 15", 1, dry_run=True)
    assert exc.value.status_code == 409


def test_register_slug_alias_dry_run():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    changed = register_slug_alias(db, "batch-15", 42, dry_run=True)
    assert changed is True
    db.add.assert_not_called()


def test_resolve_batch_by_slug_alias_returns_none_when_missing():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    assert _resolve_batch_by_slug_alias(db, "batch-15") is None


def test_resolve_batch_by_slug_alias_resolves_batch():
    from app.models import BatchMaster

    db = MagicMock()
    opt = MagicMock()
    opt.option_value = "7"
    row = BatchMaster(id=7, name="CCM Batch 15", status="1", display_order=0)

    query_mock = MagicMock()
    db.query.return_value = query_mock

    def query_side_effect(model):
        m = MagicMock()
        if model.__name__ == "Option":
            m.filter.return_value.first.return_value = opt
        elif model.__name__ == "BatchMaster":
            m.filter.return_value.first.return_value = row
        return m

    db.query.side_effect = query_side_effect

    result = _resolve_batch_by_slug_alias(db, "batch-15")
    assert result is not None
    resolved_row, bd = result
    assert resolved_row.id == 7
    assert bd.title == "CCM Batch 15"
