import json

from fastapi.testclient import TestClient

from config.runtime import RuntimeSettings
from database.database_manager import DatabaseManager
from services.application_service import ApplicationService
from connectors.hai_bridge import sync_feed
from web_api import create_app


TOKEN = "test-token-with-at-least-thirty-two-characters"


def build_service(tmp_path):
    database = DatabaseManager(str(tmp_path / "data" / "web.db"))
    service = ApplicationService(database, RuntimeSettings(environment="test"))
    assert database.add_volunteer({
        "volunteer_id": "candidate-1",
        "name": "Private Candidate Name",
        "location": "Arnhem",
        "categories": "maatjes",
    })
    campaign_id = service.create_campaign({
        "name": "Web campaign",
        "target_location": "Arnhem",
        "target_categories": "maatjes",
        "message_template": "Private message for {name}",
    })
    service.create_drafts(campaign_id)
    return service, campaign_id


def test_web_api_requires_bearer_auth_and_exposes_health(tmp_path):
    service, _ = build_service(tmp_path)
    client = TestClient(create_app(service, api_token=TOKEN, static_root=tmp_path / "missing"))
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/api/v1/status").status_code == 401
    response = client.get("/api/v1/status", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    assert response.json()["database"]["ready"] is True
    assert response.headers["content-security-policy"].startswith("default-src 'self'")
    assert response.headers["x-frame-options"] == "DENY"
    assert client.get("/healthz", headers={"host": "localhost"}).status_code == 200
    assert client.get("/healthz", headers={"host": "attacker.example"}).status_code == 400


def test_web_campaign_and_import_use_shared_database(tmp_path):
    service, _ = build_service(tmp_path)
    headers = {"Authorization": f"Bearer {TOKEN}"}
    client = TestClient(create_app(service, api_token=TOKEN, static_root=tmp_path / "missing"))
    created = client.post("/api/v1/campaigns", headers=headers, json={
        "name": "Second campaign",
        "description": "",
        "target_categories": "taal",
        "target_location": "Utrecht",
        "target_distance": 20,
        "message_template": "Beste {name}",
    })
    assert created.status_code == 201
    assert len(client.get("/api/v1/campaigns", headers=headers).json()["items"]) == 2

    imported = client.post(
        "/api/v1/volunteers/import",
        headers=headers,
        files={"file": ("candidates.csv", b"volunteer_id,name,location\ncandidate-2,Sam,Utrecht\n", "text/csv")},
    )
    assert imported.status_code == 200
    assert imported.json()["imported"] == 1
    assert len(service.list_volunteers()) == 2


def test_safety_stop_is_durable_across_application_instances(tmp_path):
    service, _ = build_service(tmp_path)
    headers = {"Authorization": f"Bearer {TOKEN}"}
    client = TestClient(create_app(service, api_token=TOKEN, static_root=tmp_path / "missing"))
    response = client.put("/api/v1/operations/safety-stop", headers=headers, json={"active": True})
    assert response.status_code == 200
    second_process = ApplicationService(
        DatabaseManager(service.database.db_path),
        RuntimeSettings(environment="test"),
    )
    assert second_process.safety_stop_active() is True
    assert any(
        event["action"] == "runtime_control_updated"
        for event in second_process.database.get_audit_events(limit=20)
    )


def test_hai_feed_matches_generic_contract_without_personal_content(tmp_path):
    service, _ = build_service(tmp_path)
    headers = {"Authorization": f"Bearer {TOKEN}"}
    client = TestClient(create_app(service, api_token=TOKEN, static_root=tmp_path / "missing"))
    response = client.get("/api/v1/hai/feed", headers=headers)
    assert response.status_code == 200
    feed = response.json()
    assert len(feed["cursor"]) == 64
    assert feed["items"]
    item = feed["items"][0]
    assert item["provider"] == "generic_json_feed"
    assert item["itemType"] == "card"
    assert item["metadata"]["executionAuthority"] == "none"
    serialized = json.dumps(feed)
    assert "Private Candidate Name" not in serialized
    assert "Private message for" not in serialized


def test_hai_bridge_uses_bearer_header_and_atomic_output(tmp_path, monkeypatch):
    class Response:
        status_code = 200
        content = b'{"cursor":"abc","items":[]}'

        def __enter__(self):
            return self

        def __exit__(self, *unused):
            return None

        def iter_content(self, chunk_size=1):
            for offset in range(0, len(self.content), chunk_size):
                yield self.content[offset : offset + chunk_size]

        @staticmethod
        def json():
            return {"cursor": "abc", "items": []}

    calls = {}

    def fake_get(url, **kwargs):
        calls["url"] = url
        calls.update(kwargs)
        return Response()

    monkeypatch.setattr("connectors.hai_bridge.requests.get", fake_get)
    destination = tmp_path / "feeds" / "nlve.json"
    result = sync_feed("https://reachout.example.com", TOKEN, str(destination), 50)
    assert result["items"] == 0
    assert calls["headers"]["Authorization"] == f"Bearer {TOKEN}"
    assert "token" not in calls["url"].lower()
    assert json.loads(destination.read_text(encoding="utf-8"))["items"] == []


def test_web_operator_workflows_are_wired_end_to_end(tmp_path):
    service, campaign_id = build_service(tmp_path)
    headers = {"Authorization": f"Bearer {TOKEN}"}
    client = TestClient(create_app(service, api_token=TOKEN, static_root=tmp_path / "missing"))

    draft = client.get("/api/v1/messages/review", headers=headers).json()["items"][0]
    approved = client.post(
        f"/api/v1/messages/{draft['id']}/approve",
        headers=headers,
        json={"reason": "Reviewed for tone and relevance"},
    )
    assert approved.status_code == 200
    queue = client.get(
        "/api/v1/messages?message_status=approved",
        headers=headers,
    ).json()["items"]
    assert [item["id"] for item in queue] == [draft["id"]]
    sent = client.post(
        f"/api/v1/messages/{draft['id']}/confirm-manual-send",
        headers=headers,
        json={"evidence": "Operator confirmed provider receipt at 10:30"},
    )
    assert sent.status_code == 200

    recorded = client.post(
        "/api/v1/responses",
        headers=headers,
        json={
            "volunteer_id": "candidate-1",
            "campaign_id": campaign_id,
            "content": "Interested, please follow up next week.",
        },
    )
    assert recorded.status_code == 201
    assert client.get("/api/v1/responses", headers=headers).json()["items"][0]["id"] == recorded.json()["id"]

    with service.database.get_connection() as connection:
        connection.execute("UPDATE volunteers SET updated_at = datetime('now', '-500 days')")
        connection.execute("UPDATE contacts SET contact_date = datetime('now', '-500 days')")
        connection.execute("UPDATE volunteer_responses SET received_at = datetime('now', '-500 days')")
        connection.commit()
    candidates = client.get("/api/v1/privacy/retention?days=365", headers=headers).json()["items"]
    assert candidates[0]["volunteer_id"] == "candidate-1"
    archived = client.post(
        "/api/v1/privacy/retention/candidate-1/archive",
        headers=headers,
        json={"reason": "Retention review completed"},
    )
    assert archived.json() == {"archived": True}
    assert service.list_volunteers()[0]["retention_status"] == "archived"


def test_web_api_rejects_unsupported_message_status(tmp_path):
    service, _ = build_service(tmp_path)
    client = TestClient(create_app(service, api_token=TOKEN, static_root=tmp_path / "missing"))
    response = client.get(
        "/api/v1/messages?message_status=unknown",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_operation"


def test_spa_fallback_never_reads_a_request_derived_path(tmp_path):
    service, _ = build_service(tmp_path)
    static_root = tmp_path / "static"
    (static_root / "assets").mkdir(parents=True)
    (static_root / "index.html").write_text("safe-index", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("must-not-be-served", encoding="utf-8")
    client = TestClient(create_app(service, api_token=TOKEN, static_root=static_root))

    response = client.get("/..%2Fsecret.txt")
    assert response.status_code == 200
    assert response.text == "safe-index"
