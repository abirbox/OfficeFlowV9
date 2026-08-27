"""Backend tests for the new Email Settings (SMTP) endpoints and forgot-password wiring."""
import os
import time
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://office-flow-build.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@example.com", "password": "admin123"}
CLIENT = {"email": "acme@client.com", "password": "Acme@123"}


def _login(session, creds):
    r = session.post(f"{API}/auth/login", json=creds)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r


def admin_session():
    s = requests.Session()
    _login(s, ADMIN)
    return s


def client_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=CLIENT)
    if r.status_code != 200:
        return None
    return s


# -----------------------
# Access control
# -----------------------
def test_get_email_settings_requires_auth():
    r = requests.get(f"{API}/settings/email")
    assert r.status_code in (401, 403)


def test_client_forbidden_get():
    s = client_session()
    if not s:
        import pytest; pytest.skip("client user not seeded")
    r = s.get(f"{API}/settings/email")
    assert r.status_code == 403


def test_client_forbidden_put():
    s = client_session()
    if not s:
        import pytest; pytest.skip("client user not seeded")
    r = s.put(f"{API}/settings/email", json={"smtp_host": "x", "password": "y"})
    assert r.status_code == 403


# -----------------------
# Admin GET / PUT flows
# -----------------------
def test_admin_get_returns_masked_shape():
    s = admin_session()
    r = s.get(f"{API}/settings/email")
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ("smtp_host", "smtp_port", "username", "from_email", "has_password"):
        assert k in data, f"missing key {k}"
    # Password must never be returned
    assert "password" not in data
    assert "password_enc" not in data


def test_admin_save_and_update_preserves_password():
    s = admin_session()
    payload1 = {
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "username": "mailer@company.com",
        "password": "s3cret-pass-123",
        "from_email": "no-reply@company.com",
    }
    r = s.put(f"{API}/settings/email", json=payload1)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["smtp_host"] == payload1["smtp_host"]
    assert data["smtp_port"] == 587
    assert data["username"] == payload1["username"]
    assert data["from_email"] == payload1["from_email"]
    assert data["has_password"] is True
    assert "password" not in data and "password_enc" not in data

    # GET returns saved data, still masked
    r2 = s.get(f"{API}/settings/email")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["smtp_host"] == "smtp.gmail.com"
    assert d2["has_password"] is True
    assert "password" not in d2

    # Update host only, blank password -> preserved
    r3 = s.put(f"{API}/settings/email", json={
        "smtp_host": "smtp.sendgrid.net",
        "smtp_port": 587,
        "username": payload1["username"],
        "from_email": payload1["from_email"],
        # password intentionally omitted
    })
    assert r3.status_code == 200, r3.text
    d3 = r3.json()
    assert d3["smtp_host"] == "smtp.sendgrid.net"
    assert d3["has_password"] is True, "password should be preserved when blank"

    # Empty string password should also preserve
    r4 = s.put(f"{API}/settings/email", json={
        "smtp_host": "smtp.sendgrid.net",
        "smtp_port": 2525,
        "username": payload1["username"],
        "from_email": payload1["from_email"],
        "password": "",
    })
    assert r4.status_code == 200
    assert r4.json()["has_password"] is True
    assert r4.json()["smtp_port"] == 2525


# -----------------------
# Forgot-password dry-run wiring
# -----------------------
def test_forgot_password_dry_run_does_not_error():
    # ensure settings exist first (previous test saved them)
    s = admin_session()
    s.put(f"{API}/settings/email", json={
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "username": "mailer@company.com",
        "password": "s3cret-pass-123",
        "from_email": "no-reply@company.com",
    })
    r = requests.post(f"{API}/auth/forgot-password", json={"email": ADMIN["email"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "message" in body
    # generic response text
    assert "reset" in body["message"].lower() or "if the email" in body["message"].lower()


def test_forgot_password_nonexistent_email_generic_response():
    r = requests.post(f"{API}/auth/forgot-password", json={"email": "nobody-xyz@example.com"})
    assert r.status_code == 200
    assert "message" in r.json()


# -----------------------
# Regression: other settings still work
# -----------------------
def test_regression_get_public_settings():
    r = requests.get(f"{API}/settings/public")
    assert r.status_code == 200
    assert "brand_name" in r.json()


def test_regression_admin_get_settings():
    s = admin_session()
    r = s.get(f"{API}/settings")
    assert r.status_code == 200


def test_regression_theme():
    r = requests.get(f"{API}/settings/theme")
    assert r.status_code == 200
    assert "values" in r.json()
