from fastapi.testclient import TestClient


def _client(monkeypatch):
    # Force the REST builders to use the deterministic StubLLM (no network).
    import app.api.routes as routes
    from tests.conftest import StubLLM

    monkeypatch.setattr(routes, "_make_llm", lambda: StubLLM({}))
    routes.get_llm.cache_clear()
    routes._brief_cache.clear()
    from app.main import app

    return TestClient(app)


def test_health(monkeypatch):
    c = _client(monkeypatch)
    assert c.get("/api/health").json()["status"] == "ok"


def test_accounts_and_brief(monkeypatch):
    c = _client(monkeypatch)
    accts = c.get("/api/accounts").json()
    assert any(a["id"] == "ACC-1002" for a in accts)
    brief = c.get("/api/accounts/ACC-1002/brief").json()
    assert brief["headline"]
    assert any(f["id"] == "coverage" for f in brief["risk_flags"])


def test_participant(monkeypatch):
    c = _client(monkeypatch)
    card = c.get(
        "/api/participants/CON-2005/brief", params={"accountId": "ACC-1002"}
    ).json()
    assert card["contact"]["id"] == "CON-2005"
