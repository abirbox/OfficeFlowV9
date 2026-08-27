"""Smoke coverage for restored OfficeFlow health and authentication endpoints."""
import os
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


def test_health_and_root():
    client = requests.Session()
    health = client.get(f"{BASE_URL}/api/health", timeout=20)
    root = client.get(f"{BASE_URL}/api/", timeout=20)
    assert health.status_code == 200 and health.json()["status"] == "healthy"
    assert root.status_code == 200 and root.json()["status"] == "running"


def test_admin_login_cookie_and_me():
    client = requests.Session()
    login = client.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@example.com", "password": "admin123"}, timeout=20)
    assert login.status_code == 200, login.text
    assert login.json()["email"] == "admin@example.com"
    assert "access_token" in client.cookies and "refresh_token" in client.cookies
    me = client.get(f"{BASE_URL}/api/auth/me", timeout=20)
    assert me.status_code == 200 and me.json()["email"] == "admin@example.com"


def test_me_requires_session():
    response = requests.get(f"{BASE_URL}/api/auth/me", timeout=20)
    assert response.status_code == 401