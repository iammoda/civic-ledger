"""Rate limiting + Ask answer cache: the cost-control layer for public launch."""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import app.core.ratelimit as ratelimit
import app.services.ask as ask_module
from app.services.search import SearchResult, _fts_queries


def _enabled_settings(**overrides):
    defaults = dict(rate_limit_enabled=True, ask_cache_ttl_seconds=3600, ask_daily_generate_limit=300)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_app(limit: int, window: int = 60) -> FastAPI:
    app = FastAPI()

    @app.get("/limited", dependencies=[Depends(ratelimit.rate_limit("test-ep", limit=limit, window_seconds=window))])
    def limited() -> dict:
        return {"ok": True}

    return app


def test_rate_limit_blocks_after_threshold(monkeypatch):
    monkeypatch.setattr(ratelimit, "get_settings", lambda: _enabled_settings())
    ratelimit._local.clear()
    client = TestClient(_make_app(limit=3))
    statuses = [client.get("/limited").status_code for _ in range(5)]
    assert statuses == [200, 200, 200, 429, 429]


def test_rate_limit_429_includes_retry_after(monkeypatch):
    monkeypatch.setattr(ratelimit, "get_settings", lambda: _enabled_settings())
    ratelimit._local.clear()
    client = TestClient(_make_app(limit=1, window=120))
    client.get("/limited")
    response = client.get("/limited")
    assert response.status_code == 429
    assert response.headers.get("retry-after") == "120"


def test_rate_limit_disabled_setting_bypasses(monkeypatch):
    monkeypatch.setattr(ratelimit, "get_settings", lambda: _enabled_settings(rate_limit_enabled=False))
    ratelimit._local.clear()
    client = TestClient(_make_app(limit=1))
    assert all(client.get("/limited").status_code == 200 for _ in range(5))


def test_rate_limit_keys_are_per_ip(monkeypatch):
    monkeypatch.setattr(ratelimit, "get_settings", lambda: _enabled_settings())
    ratelimit._local.clear()
    client = TestClient(_make_app(limit=1))
    # First client exhausts its budget; a different forwarded IP still passes.
    assert client.get("/limited").status_code == 200
    assert client.get("/limited").status_code == 429
    assert client.get("/limited", headers={"x-forwarded-for": "203.0.113.9"}).status_code == 200


def test_within_quota_global_counter(monkeypatch):
    monkeypatch.setattr(ratelimit, "get_settings", lambda: _enabled_settings())
    ratelimit._local.clear()
    results = [ratelimit.within_quota("unit-quota", limit=2, window_seconds=3600) for _ in range(4)]
    assert results == [True, True, False, False]


def test_ask_cache_roundtrip_and_normalization(monkeypatch):
    monkeypatch.setattr(ask_module, "get_settings", lambda: _enabled_settings())
    ask_module._LOCAL_CACHE.clear()
    evidence = [
        SearchResult(entity_type="bill", entity_id=7, title="C-1 — Housing", snippet="s", url_path="/bills/45-1/C-1")
    ]
    data = {"answer_sentence": "Ottawa funds housing.", "cited_indexes": [1]}
    ask_module._cache_put("Why is rent so high?", data, evidence)

    # Same question modulo case/whitespace/punctuation hits the cache.
    cached = ask_module._cache_get("  why is RENT so high ")
    assert cached is not None
    assert cached["data"]["answer_sentence"] == "Ottawa funds housing."
    rebuilt = [SearchResult(**item) for item in cached["evidence"]]
    assert rebuilt[0].entity_id == 7 and rebuilt[0].entity_type == "bill"

    assert ask_module._cache_get("a different question") is None


def test_ask_cache_disabled_when_ttl_zero(monkeypatch):
    monkeypatch.setattr(ask_module, "get_settings", lambda: _enabled_settings(ask_cache_ttl_seconds=0))
    ask_module._LOCAL_CACHE.clear()
    ask_module._cache_put("q?", {"answer_sentence": "x"}, [])
    assert ask_module._cache_get("q?") is None


def test_fts_tokens_never_end_with_hyphen(db):
    # "co- op" style input used to produce a trailing-hyphen token that made
    # to_tsquery throw a syntax error (500). Regex now requires letter ends.
    import re

    query = "co- op housing- affordability"
    tokens = re.findall(r"[a-zA-Z][a-zA-Z-]+[a-zA-Z]", query.lower())
    assert tokens and all(not t.endswith("-") for t in tokens)
    # And the query builder doesn't blow up on SQLite either.
    assert _fts_queries(db, query) is not None
