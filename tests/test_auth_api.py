import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db.session import get_session
from app.main import app


@pytest.fixture()
def client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _register(
    client: TestClient,
    email: str = "juan@example.com",
    document_number: str = "12345678",
) -> dict:
    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "full_name": "Juan Perez",
            "document_number": document_number,
            "phone": "1122334455",
            "password": "secret123",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_register_login_and_me(client: TestClient) -> None:
    data = _register(client)

    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["user"]["email"] == "juan@example.com"
    assert "password_hash" not in data["user"]

    login = client.post(
        "/api/auth/login",
        json={"email": "JUAN@example.com", "password": "secret123"},
    )
    assert login.status_code == 200

    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["document_number"] == "12345678"


def test_register_rejects_duplicate_email_and_dni(client: TestClient) -> None:
    _register(client)

    duplicate_email = client.post(
        "/api/auth/register",
        json={
            "email": "juan@example.com",
            "full_name": "Otro",
            "document_number": "99999999",
            "phone": "1122334455",
            "password": "secret123",
        },
    )
    assert duplicate_email.status_code == 409

    duplicate_dni = client.post(
        "/api/auth/register",
        json={
            "email": "otro@example.com",
            "full_name": "Otro",
            "document_number": "12345678",
            "phone": "1122334455",
            "password": "secret123",
        },
    )
    assert duplicate_dni.status_code == 409


def test_login_rejects_wrong_password_and_me_requires_token(client: TestClient) -> None:
    _register(client)

    login = client.post(
        "/api/auth/login",
        json={"email": "juan@example.com", "password": "wrong"},
    )
    assert login.status_code == 401

    me = client.get("/api/auth/me")
    assert me.status_code == 401


def test_conversations_are_scoped_to_authenticated_user(client: TestClient) -> None:
    user_a = _register(client, "a@example.com", "11111111")
    user_b = _register(client, "b@example.com", "22222222")
    headers_a = {"Authorization": f"Bearer {user_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {user_b['access_token']}"}

    created = client.post("/api/conversations", json={"channel": "web_chat"}, headers=headers_a)
    assert created.status_code == 200
    conversation_id = created.json()["id"]
    assert created.json()["user_id"] == user_a["user"]["id"]

    list_a = client.get("/api/conversations", headers=headers_a)
    list_b = client.get("/api/conversations", headers=headers_b)
    assert [item["id"] for item in list_a.json()] == [conversation_id]
    assert list_b.json() == []

    foreign_message = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"message": "hola", "input_mode": "text"},
        headers=headers_b,
    )
    assert foreign_message.status_code == 404

    foreign_delete = client.delete(f"/api/conversations/{conversation_id}", headers=headers_b)
    assert foreign_delete.status_code == 404

    own_delete = client.delete(f"/api/conversations/{conversation_id}", headers=headers_a)
    assert own_delete.status_code == 204
    assert client.get("/api/conversations", headers=headers_a).json() == []


def test_conversation_retention_keeps_two_latest_per_user(client: TestClient) -> None:
    user_a = _register(client, "a@example.com", "11111111")
    user_b = _register(client, "b@example.com", "22222222")
    headers_a = {"Authorization": f"Bearer {user_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {user_b['access_token']}"}

    first = client.post("/api/conversations", json={"channel": "web_chat"}, headers=headers_a)
    second = client.post("/api/conversations", json={"channel": "web_chat"}, headers=headers_a)
    b_conversation = client.post("/api/conversations", json={"channel": "web_chat"}, headers=headers_b)
    third = client.post("/api/conversations", json={"channel": "web_chat"}, headers=headers_a)

    assert first.status_code == second.status_code == third.status_code == 200
    ids_a = [item["id"] for item in client.get("/api/conversations", headers=headers_a).json()]
    assert ids_a == [third.json()["id"], second.json()["id"]]

    old_messages = client.get(f"/api/conversations/{first.json()['id']}/messages", headers=headers_a)
    assert old_messages.status_code == 404
    ids_b = [item["id"] for item in client.get("/api/conversations", headers=headers_b).json()]
    assert ids_b == [b_conversation.json()["id"]]


def test_visible_conversation_messages_are_persisted(client: TestClient, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "groq_api_key", "")
    user = _register(client)
    headers = {"Authorization": f"Bearer {user['access_token']}"}
    created = client.post("/api/conversations", json={"channel": "web_chat"}, headers=headers)
    conversation_id = created.json()["id"]

    response = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"message": "Hola", "input_mode": "text"},
        headers=headers,
    )
    assert response.status_code == 200

    messages = client.get(f"/api/conversations/{conversation_id}/messages", headers=headers)
    assert messages.status_code == 200
    payload = messages.json()
    assert [message["role"] for message in payload] == ["user", "assistant"]
    assert payload[0]["content"] == "Hola"
    assert "Groq" in payload[1]["content"]


def test_websocket_requires_auth_and_ownership(client: TestClient) -> None:
    user_a = _register(client, "a@example.com", "11111111")
    user_b = _register(client, "b@example.com", "22222222")
    created = client.post(
        "/api/conversations",
        json={"channel": "web_chat"},
        headers={"Authorization": f"Bearer {user_a['access_token']}"},
    )
    conversation_id = created.json()["id"]

    with client.websocket_connect(f"/api/ws/conversations/{conversation_id}") as websocket:
        websocket.send_json({"type": "user_message", "text": "hola"})
        assert websocket.receive_json()["type"] == "error"

    with client.websocket_connect(f"/api/ws/conversations/{conversation_id}") as websocket:
        websocket.send_json({"type": "auth", "token": user_b["access_token"]})
        message = websocket.receive_json()
        assert message["type"] == "error"
