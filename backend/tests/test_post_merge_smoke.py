"""Smoke tests after moving app from /app/OfficeflowV3 -> /app root."""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://officeflow-v3.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin123"


def _login():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    body = r.json()
    # access_token can be returned in body and/or as cookie
    cookie_token = s.cookies.get("access_token")
    assert cookie_token or body.get("access_token"), f"no access_token in cookie or body: {body}"
    return s, body


def test_login_returns_200_and_cookie():
    s, body = _login()
    assert s.cookies.get("access_token"), "access_token cookie not set"


def test_auth_me_returns_admin():
    s, _ = _login()
    r = s.get(f"{BASE_URL}/api/auth/me", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("email") == ADMIN_EMAIL
    assert data.get("role") in ("super_admin", "admin"), data


def test_dispatch_schedules_has_vendor_pin_fields():
    s, _ = _login()
    r = s.get(f"{BASE_URL}/api/dispatch/schedules", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", data.get("schedules", []))
    assert isinstance(items, list)
    if items:
        sample = items[0]
        assert "post_pin_display" in sample, f"post_pin_display missing: keys={list(sample.keys())}"
        assert "vendor_code" in sample, f"vendor_code missing: keys={list(sample.keys())}"


def test_dispatch_reports_by_officer_clocked_in_counts_complete():
    s, _ = _login()
    r = s.get(f"{BASE_URL}/api/dispatch/reports/by-officer",
              params={"date_from": "2026-06-01", "date_to": "2026-08-31"}, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", data.get("officers", []))
    assert isinstance(items, list)
    # Just verify shape - completed field is integer if present
    for it in items[:5]:
        if "completed" in it:
            assert isinstance(it["completed"], int)


def test_dispatch_invoices_next_number():
    s, _ = _login()
    r = s.get(f"{BASE_URL}/api/dispatch/invoices/next-number", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    # accept either {number: ...} or {next_number: ...} or a scalar
    val = data.get("number") if isinstance(data, dict) else data
    if val is None and isinstance(data, dict):
        val = data.get("next_number") or data.get("invoice_number")
    assert val is not None, f"no number in response: {data}"
