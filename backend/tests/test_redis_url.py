from app.core.redis_url import normalize_redis_url


def test_upstash_redis_upgraded_to_rediss():
    url = normalize_redis_url(
        "redis://default:secret@literate-lion-231049.upstash.io:6379"
    )
    assert url.startswith("rediss://")
    assert "upstash.io" in url
