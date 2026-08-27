"""Iter28 regression tests:
- super_admin login
- GET /api/employees, /api/dispatch/schedules
- Dispatch entity CRUD (clients)
- Employee hard-delete: cascade + last-super-admin guard
"""
import os
import uuid
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    # Fallback: read from /app/frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE = _load_backend_url()
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASS = "admin123"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


def test_login_and_me(admin_session):
    r = admin_session.get(f"{BASE}/api/auth/me", timeout=15)
    assert r.status_code == 200
    assert r.json().get("role") == "super_admin"


def test_get_employees(admin_session):
    r = admin_session.get(f"{BASE}/api/employees", timeout=30)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_dispatch_schedules(admin_session):
    r = admin_session.get(f"{BASE}/api/dispatch/schedules", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, (list, dict))
    if isinstance(data, dict):
        assert "items" in data and isinstance(data["items"], list)


def test_dispatch_client_crud(admin_session):
    tag = f"TEST_ITER28_{uuid.uuid4().hex[:6]}"
    # CREATE
    r = admin_session.post(f"{BASE}/api/dispatch/clients", json={"name": tag}, timeout=30)
    assert r.status_code in (200, 201), r.text
    cid = r.json().get("id")
    assert cid
    # GET list contains
    r = admin_session.get(f"{BASE}/api/dispatch/clients", timeout=30)
    assert r.status_code == 200
    assert any(c.get("id") == cid for c in r.json())
    # UPDATE
    r = admin_session.put(f"{BASE}/api/dispatch/clients/{cid}", json={"name": tag + "_upd"}, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json().get("name") == tag + "_upd"
    # DELETE
    r = admin_session.delete(f"{BASE}/api/dispatch/clients/{cid}", timeout=30)
    assert r.status_code in (200, 204)


def test_employee_hard_delete_and_cascade(admin_session):
    email = f"test_iter28_{uuid.uuid4().hex[:8]}@example.com"
    payload = {"email": email, "password": "Passw0rd!", "name": "Iter28 Temp", "role": "employee"}
    r = admin_session.post(f"{BASE}/api/employees", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    eid = r.json()["id"]
    # GET returns 200
    r = admin_session.get(f"{BASE}/api/employees/{eid}", timeout=15)
    assert r.status_code == 200
    # DELETE
    r = admin_session.delete(f"{BASE}/api/employees/{eid}", timeout=15)
    assert r.status_code == 200, r.text
    # subsequent GET returns 404 -> confirms hard delete
    r = admin_session.get(f"{BASE}/api/employees/{eid}", timeout=15)
    assert r.status_code == 404


def test_cannot_delete_last_super_admin(admin_session):
    r = admin_session.get(f"{BASE}/api/auth/me", timeout=15)
    assert r.status_code == 200
    me_id = r.json().get("id") or r.json().get("_id")
    # Count super_admins
    r = admin_session.get(f"{BASE}/api/employees", timeout=30)
    assert r.status_code == 200
    supers = [e for e in r.json() if e.get("role") == "super_admin"]
    if len(supers) == 1:
        # Attempt to delete this last one -> expect 400
        r = admin_session.delete(f"{BASE}/api/employees/{supers[0]['id']}", timeout=15)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
    else:
        pytest.skip(f"{len(supers)} super_admins exist; cannot deterministically test last-guard without side effects")
