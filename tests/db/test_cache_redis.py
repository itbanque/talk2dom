from talk2dom.db import cache


def test_redis_set_and_get_locator(monkeypatch):
    stored = {}

    class DummyRedis:
        def hset(self, key, mapping=None):
            stored[key] = dict(mapping or {})

        def hgetall(self, key):
            return stored.get(key, {})

        def expire(self, key, ttl):
            stored[f"{key}:ttl"] = ttl

    monkeypatch.setattr(cache, "_redis", lambda: DummyRedis())
    monkeypatch.setattr(cache, "_TTL_SECONDS", 10)
    monkeypatch.setattr(cache, "_NS", "test")

    cache._redis_set_locator("loc", "css", "#id", "click")
    t, v, a = cache._redis_get_locator("loc")

    assert t == "css"
    assert v == "#id"
    assert a == "click"
