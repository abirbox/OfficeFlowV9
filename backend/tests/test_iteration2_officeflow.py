import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")


def test_health_and_root():
    assert BASE_URL
    session = requests.Session()
    health = session.get(f"{BASE_URL}/api/health", timeout=20)
    root = session.get(f"{BASE_URL}/api/", timeout=20)
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"
    assert root.status_code == 200
    assert root.json()["status"] == "running"


def test_admin_login_cookie_and_me():
    session = requests.Session()
    login = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@example.com", "password": "admin123"
    }, timeout=20)
    assert login.status_code == 200
    data = login.json()
    assert data["email"] == "admin@example.com"
    assert data["role"] == "super_admin"
    assert "access_token" in session.cookies
    me = session.get(f"{BASE_URL}/api/auth/me", timeout=20)
    assert me.status_code == 200
    assert me.json()["email"] == "admin@example.com"


def test_me_without_session_is_unauthorized():
    response = requests.get(f"{BASE_URL}/api/auth/me", timeout=20)
    assert response.status_code == 401