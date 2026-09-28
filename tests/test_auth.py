from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.models import User
from backend.services.auth import hash_password, verify_password, create_access_token, decode_token


class TestAuthService:
    def test_hash_and_verify_password(self):
        """Senha deve ser hasheada e verificada corretamente."""
        hashed = hash_password("minha_senha")
        assert hashed != "minha_senha"
        assert verify_password("minha_senha", hashed) is True
        assert verify_password("outra_senha", hashed) is False

    def test_create_and_decode_access_token(self):
        """Token JWT deve ser criado e decodificado."""
        token = create_access_token(data={"sub": "42"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_decode_invalid_token(self):
        """Token invalido deve retornar None."""
        assert decode_token("token_invalido") is None


class TestAuthEndpoints:
    def test_register_success(self, client: TestClient):
        """Registro com dados validos deve retornar 201."""
        response = client.post(
            "/api/auth/register",
            json={"email": "novo@teste.com", "password": "senha123"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "novo@teste.com"
        assert data["is_active"] is True
        assert "id" in data
        # Senha nunca deve ser retornada
        assert "password" not in data
        assert "hashed_password" not in data

    def test_register_duplicate_email(self, client: TestClient):
        """Email duplicado deve retornar 409."""
        client.post(
            "/api/auth/register",
            json={"email": "dup@teste.com", "password": "senha123"},
        )
        response = client.post(
            "/api/auth/register",
            json={"email": "dup@teste.com", "password": "outrasenha"},
        )
        assert response.status_code == 409

    def test_register_invalid_email(self, client: TestClient):
        """Email invalido deve retornar 422."""
        response = client.post(
            "/api/auth/register",
            json={"email": "invalido", "password": "senha123"},
        )
        assert response.status_code == 422

    def test_register_short_password(self, client: TestClient):
        """Senha com menos de 6 caracteres deve retornar 422."""
        response = client.post(
            "/api/auth/register",
            json={"email": "teste@teste.com", "password": "123"},
        )
        assert response.status_code == 422

    def test_login_success(self, client: TestClient):
        """Login com credenciais validas deve retornar tokens."""
        client.post(
            "/api/auth/register",
            json={"email": "login@teste.com", "password": "senha123"},
        )
        response = client.post(
            "/api/auth/login",
            json={"email": "login@teste.com", "password": "senha123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client: TestClient):
        """Senha incorreta deve retornar 401."""
        client.post(
            "/api/auth/register",
            json={"email": "wrong@teste.com", "password": "senha123"},
        )
        response = client.post(
            "/api/auth/login",
            json={"email": "wrong@teste.com", "password": "senha_errada"},
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client: TestClient):
        """Usuario inexistente deve retornar 401."""
        response = client.post(
            "/api/auth/login",
            json={"email": "naoexiste@teste.com", "password": "senha123"},
        )
        assert response.status_code == 401

    def test_me_with_valid_token(self, client: TestClient):
        """GET /me com token valido deve retornar dados do usuario."""
        client.post(
            "/api/auth/register",
            json={"email": "me@teste.com", "password": "senha123"},
        )
        login_resp = client.post(
            "/api/auth/login",
            json={"email": "me@teste.com", "password": "senha123"},
        )
        token = login_resp.json()["access_token"]

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me@teste.com"

    def test_me_without_token(self, client: TestClient):
        """GET /me sem token deve retornar 401."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_me_with_invalid_token(self, client: TestClient):
        """GET /me com token invalido deve retornar 401."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer token_invalido"},
        )
        assert response.status_code == 401

    def test_logout(self, client: TestClient):
        """Logout deve retornar 204."""
        client.post(
            "/api/auth/register",
            json={"email": "logout@teste.com", "password": "senha123"},
        )
        login_resp = client.post(
            "/api/auth/login",
            json={"email": "logout@teste.com", "password": "senha123"},
        )
        token = login_resp.json()["access_token"]

        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 204

    def test_refresh_token(self, client: TestClient):
        """Refresh token deve gerar novos tokens."""
        client.post(
            "/api/auth/register",
            json={"email": "refresh@teste.com", "password": "senha123"},
        )
        login_resp = client.post(
            "/api/auth/login",
            json={"email": "refresh@teste.com", "password": "senha123"},
        )
        refresh_token = login_resp.json()["refresh_token"]

        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_with_invalid_token(self, client: TestClient):
        """Refresh com token invalido deve retornar 401."""
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": "token_invalido"},
        )
        assert response.status_code == 401