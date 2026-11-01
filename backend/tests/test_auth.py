import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import hash_password, verify_password
from app.core.test_safety import assert_safe_test_environment
from app.main import app
from app.models.user import User


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_users():
    assert_safe_test_environment()
    session = SessionLocal()
    try:
        session.query(User).delete()
        session.commit()
    finally:
        session.close()
    yield
    assert_safe_test_environment()
    session = SessionLocal()
    try:
        session.query(User).delete()
        session.commit()
    finally:
        session.close()


def test_argon2_password_hashing():
    """Verify Argon2 password hashing and verification."""
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert hashed.startswith("$argon2")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_user_registration_and_jwt_issuance(client):
    """Test user registration returns valid JWT access and refresh tokens."""
    payload = {
        "username": "alice_dev",
        "email": "alice@example.com",
        "password": "SecurePassword123!",
        "role": "DEVELOPER",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "alice_dev"
    assert data["user"]["email"] == "alice@example.com"
    # First user registered in empty DB becomes ADMIN
    assert data["user"]["role"] in ("ADMIN", "DEVELOPER")
    assert "password_hash" not in data["user"]


def test_duplicate_registration_rejection(client):
    """Test that duplicate usernames and emails are rejected."""
    payload = {
        "username": "bob_ops",
        "email": "bob@example.com",
        "password": "SecurePassword123!",
    }
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Duplicate username
    res_dup_user = client.post(
        "/api/v1/auth/register",
        json={**payload, "email": "other@example.com"},
    )
    assert res_dup_user.status_code == 400
    assert "already registered" in res_dup_user.json()["detail"]["error"]["message"]

    # Duplicate email
    res_dup_email = client.post(
        "/api/v1/auth/register",
        json={**payload, "username": "other_bob"},
    )
    assert res_dup_email.status_code == 400
    assert "already registered" in res_dup_email.json()["detail"]["error"]["message"]


def test_login_success_and_failure(client):
    """Test user login with valid and invalid credentials."""
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "carol_sre",
            "email": "carol@example.com",
            "password": "CorrectPassword123!",
        },
    )

    # Valid login with username
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "carol_sre", "password": "CorrectPassword123!"},
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()

    # Valid login with email
    email_login = client.post(
        "/api/v1/auth/login",
        json={"username": "carol@example.com", "password": "CorrectPassword123!"},
    )
    assert email_login.status_code == 200

    # Invalid password
    bad_pw = client.post(
        "/api/v1/auth/login",
        json={"username": "carol_sre", "password": "WrongPassword999!"},
    )
    assert bad_pw.status_code == 401

    # Nonexistent user
    not_found = client.post(
        "/api/v1/auth/login",
        json={"username": "nobody_exists", "password": "Password123!"},
    )
    assert not_found.status_code == 401


def test_refresh_token_exchange(client):
    """Test exchanging refresh token for a new access token."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": "dave_lead",
            "email": "dave@example.com",
            "password": "Password123!",
        },
    ).json()

    refresh_token = reg["refresh_token"]

    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    data = refresh_resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["username"] == "dave_lead"


def test_auth_me_and_logout(client):
    """Test /api/v1/auth/me profile retrieval and logout."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": "eve_viewer",
            "email": "eve@example.com",
            "password": "Password123!",
        },
    ).json()

    token = reg["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["username"] == "eve_viewer"

    # Logout
    logout_resp = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 200
    assert logout_resp.json()["status"] == "ok"


def test_admin_user_management(client):
    """Test admin list users and role update."""
    # First user is ADMIN
    admin_reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": "admin_root",
            "email": "admin@example.com",
            "password": "Password123!",
            "role": "ADMIN",
        },
    ).json()

    admin_headers = {"Authorization": f"Bearer {admin_reg['access_token']}"}

    # Second user is DEVELOPER
    dev_reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": "frank_dev",
            "email": "frank@example.com",
            "password": "Password123!",
            "role": "DEVELOPER",
        },
    ).json()
    dev_id = dev_reg["user"]["id"]

    # List users as admin
    users_resp = client.get("/api/v1/auth/users", headers=admin_headers)
    assert users_resp.status_code == 200
    assert users_resp.json()["total"] == 2

    # Update Frank's role to VIEWER
    patch_resp = client.patch(
        f"/api/v1/auth/users/{dev_id}/role",
        headers=admin_headers,
        json={"role": "VIEWER"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["role"] == "VIEWER"
