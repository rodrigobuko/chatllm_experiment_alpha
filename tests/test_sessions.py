from __future__ import annotations

from fastapi.testclient import TestClient

from backend.models import Session as SessionModel


def _register_and_login(client: TestClient, email: str = "teste@teste.com", password: str = "senha123") -> str:
    client.post("/api/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


class TestSessionEndpoints:
    def test_create_session(self, client: TestClient):
        token = _register_and_login(client)
        response = client.post(
            "/api/sessions",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Nova conversa"
        assert "id" in data

    def test_list_sessions(self, client: TestClient):
        token = _register_and_login(client)
        client.post("/api/sessions", json={}, headers={"Authorization": f"Bearer {token}"})
        client.post("/api/sessions", json={}, headers={"Authorization": f"Bearer {token}"})

        response = client.get(
            "/api/sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_sessions_requires_auth(self, client: TestClient):
        response = client.get("/api/sessions")
        assert response.status_code == 401

    def test_rename_session(self, client: TestClient):
        token = _register_and_login(client)
        create_resp = client.post("/api/sessions", json={}, headers={"Authorization": f"Bearer {token}"})
        session_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/sessions/{session_id}",
            json={"title": "Minha conversa"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Minha conversa"

    def test_rename_nonexistent_session(self, client: TestClient):
        token = _register_and_login(client)
        response = client.patch(
            "/api/sessions/999",
            json={"title": "Teste"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    def test_delete_session(self, client: TestClient):
        token = _register_and_login(client)
        create_resp = client.post("/api/sessions", json={}, headers={"Authorization": f"Bearer {token}"})
        session_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/sessions/{session_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 204

    def test_delete_nonexistent_session(self, client: TestClient):
        token = _register_and_login(client)
        response = client.delete(
            "/api/sessions/999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    def test_sessions_isolated_per_user(self, client: TestClient):
        token1 = _register_and_login(client, "user1@teste.com", "senha123")
        token2 = _register_and_login(client, "user2@teste.com", "senha123")

        client.post("/api/sessions", json={}, headers={"Authorization": f"Bearer {token1}"})
        client.post("/api/sessions", json={}, headers={"Authorization": f"Bearer {token2}"})

        resp1 = client.get("/api/sessions", headers={"Authorization": f"Bearer {token1}"})
        resp2 = client.get("/api/sessions", headers={"Authorization": f"Bearer {token2}"})

        assert len(resp1.json()) == 1
        assert len(resp2.json()) == 1

    def test_cannot_access_other_user_session(self, client: TestClient):
        token1 = _register_and_login(client, "user3@teste.com", "senha123")
        token2 = _register_and_login(client, "user4@teste.com", "senha123")

        create_resp = client.post("/api/sessions", json={}, headers={"Authorization": f"Bearer {token1}"})
        session_id = create_resp.json()["id"]

        # user2 tenta renomear sessao do user1
        response = client.patch(
            f"/api/sessions/{session_id}",
            json={"title": "Hack"},
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert response.status_code == 404