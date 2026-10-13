from __future__ import annotations

import fakeredis
import pytest

from app.core import redis_client
from app.services.cache import cache_delete, cache_get, cache_set, invalidate_option_cache
from app.services.rate_limit import _check_limit


@pytest.fixture
def fake_redis(monkeypatch):
    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server, decode_responses=True)
    monkeypatch.setenv("REDIS_ENABLED", "true")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    get_settings = __import__("app.core.config", fromlist=["get_settings"]).get_settings
    get_settings.cache_clear()
    redis_client.reset_redis_client_for_tests()
    monkeypatch.setattr(redis_client, "redis_enabled", lambda: True)
    monkeypatch.setattr(redis_client, "get_redis", lambda: client)
    import app.services.cache as cache_mod
    import app.services.rate_limit as rate_mod

    monkeypatch.setattr(cache_mod, "get_redis", lambda: client)
    monkeypatch.setattr(rate_mod, "get_redis", lambda: client)
    yield client
    redis_client.reset_redis_client_for_tests()
    get_settings.cache_clear()


def test_cache_round_trip(fake_redis):
    cache_set("k1", {"a": 1}, ttl_sec=60)
    assert cache_get("k1") == {"a": 1}
    cache_delete("k1")
    assert cache_get("k1") is None


def test_rate_limit_blocks_after_threshold(fake_redis):
    assert _check_limit("rl:test:1", limit=2, window_sec=60) is True
    assert _check_limit("rl:test:1", limit=2, window_sec=60) is True
    assert _check_limit("rl:test:1", limit=2, window_sec=60) is False


def test_invalidate_option_cache(fake_redis):
    from app.services.access import clear_local_option_cache, get_option_value
    from app.models import Option
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine, tables=[Option.__table__])
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(Option(option_name="site_title", option_value="Hello"))
    db.commit()

    cache_set("opt:site_title", "stale", ttl_sec=60)
    clear_local_option_cache()
    invalidate_option_cache("site_title")
    value = get_option_value(db, "site_title")
    assert value == "Hello"
