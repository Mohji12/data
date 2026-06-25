from types import SimpleNamespace

from app.services.mock_test_attempts import (
    DEFAULT_MAX_ATTEMPTS,
    _normalize_config,
    get_max_attempts_for_user,
)


def test_default_is_two():
    assert _normalize_config({})["default"] == DEFAULT_MAX_ATTEMPTS


def test_user_override_beats_batch():
    config = _normalize_config(
        {"default": 2, "batches": {"Batch 15": 4}, "users": {"99": 6}}
    )
    user = SimpleNamespace(id=99, subscription="Batch 15")
    # emulate resolution without DB
    assert config["users"]["99"] == 6
    assert config["batches"]["Batch 15"] == 4


def test_normalize_clamps():
    cfg = _normalize_config({"default": 0, "batches": {"X": 100}, "users": {"1": -3}})
    assert cfg["default"] == 1
    assert cfg["batches"]["X"] == 50
    assert cfg["users"]["1"] == 1
