from talk2dom.api.utils.ga4 import GA4


def test_ga4_send_returns_none_without_credentials(caplog):
    ga = GA4(measurement_id=None, api_secret=None)
    result = ga.send(user_id="u1", events=[{"name": "test"}])
    assert result is None


def test_ga4_send_posts_payload_and_returns_debug_json(monkeypatch):
    captured = {}

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"debug": True}

    def fake_post(url, params=None, json=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["json"] = json
        captured["timeout"] = timeout
        return DummyResponse()

    monkeypatch.setattr("talk2dom.api.utils.ga4.requests.post", fake_post)

    ga = GA4(measurement_id="G-TEST", api_secret="secret", debug=True, timeout=3)
    result = ga.send(
        user_id="u1",
        events=[{"name": "test", "params": {"a": 1}, "event_id": "evt"}],
        user_properties={"plan": "free"},
        timestamp_micros=123,
        non_personalized_ads=True,
    )

    assert result == {"debug": True}
    assert captured["params"] == {"measurement_id": "G-TEST", "api_secret": "secret"}
    assert captured["json"]["user_id"] == "u1"
    assert captured["json"]["events"][0]["event_id"] == "evt"
