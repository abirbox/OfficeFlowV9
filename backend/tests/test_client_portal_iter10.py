"""Iteration 10 tests: Client Portal - Officers, Post-Sites, Schedule CRUD isolation.

Verifies:
 - GET /api/portal/officers scoped to Acme only (no Globex officer).
 - GET /api/portal/post-sites scoped to Acme only (no Globex site).
 - POST /api/portal/schedules with own site+officer+vendor succeeds; PUT then DELETE works.
 - POST with foreign (Globex) post_site_id -> 400.
 - POST with foreign (Globex) officer_id -> 400.
 - PUT/DELETE on a Globex-owned schedule -> 404.
 - Client cannot access /api/dispatch/*; admin cannot access /api/portal/*.
 - Financial fields never present in returned schedule payload.
"""
import os
from datetime import date, timedelta
import pytest
import requests


def _read_frontend_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        return None
    return None


BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env()).rstrip("/")
API = f"{BASE}/api"

ADMIN = ("admin@example.com", "admin123")
CLIENT = ("acme@client.com", "Acme@123")


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, f"{email} login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def client():
    return _login(*CLIENT)


@pytest.fixture(scope="module")
def seed_ids(admin):
    r = admin.get(f"{API}/dispatch/clients?limit=200", timeout=30)
    clients = r.json()
    acme = next(c for c in clients if c["name"] == "Acme Corp")
    globex = next(c for c in clients if c["name"] == "Globex Ltd")

    r = admin.get(f"{API}/dispatch/post-sites?limit=500", timeout=30)
    posts = r.json()
    acme_site = next((p for p in posts if p.get("client_id") == acme["id"] and p.get("status") == "active"), None)
    globex_site = next((p for p in posts if p.get("client_id") == globex["id"]), None)

    r = admin.get(f"{API}/dispatch/officers?limit=500", timeout=30)
    offs = r.json()
    acme_officer = next((o for o in offs if o.get("client_id") == acme["id"]), None)
    globex_officer = next((o for o in offs if o.get("client_id") == globex["id"]), None)

    r = admin.get(f"{API}/dispatch/vendors?limit=200", timeout=30)
    vendors = r.json()
    acme_vendor = next((v for v in vendors if acme["id"] in (v.get("client_ids") or [])), None)
    globex_only_vendor = next((v for v in vendors if globex["id"] in (v.get("client_ids") or []) and acme["id"] not in (v.get("client_ids") or [])), None)

    assert acme_site and globex_site and acme_officer and globex_officer and acme_vendor
    return {
        "acme_id": acme["id"], "globex_id": globex["id"],
        "acme_site": acme_site, "globex_site": globex_site,
        "acme_officer": acme_officer, "globex_officer": globex_officer,
        "acme_vendor": acme_vendor,
        "globex_only_vendor": globex_only_vendor,
    }


# ---------- Officers scoping ----------
def test_portal_officers_scoped_to_acme(client, seed_ids):
    r = client.get(f"{API}/portal/officers", timeout=30)
    assert r.status_code == 200, r.text
    officers = r.json()
    names = {o["name"] for o in officers}
    assert seed_ids["acme_officer"]["name"] in names
    assert seed_ids["globex_officer"]["name"] not in names, f"Globex officer leaked: {names}"
    for o in officers:
        assert o.get("client_id") == seed_ids["acme_id"]


# ---------- Post sites scoping ----------
def test_portal_post_sites_scoped_to_acme(client, seed_ids):
    r = client.get(f"{API}/portal/post-sites", timeout=30)
    assert r.status_code == 200, r.text
    sites = r.json()
    names = {s["name"] for s in sites}
    assert seed_ids["acme_site"]["name"] in names
    assert seed_ids["globex_site"]["name"] not in names, f"Globex site leaked: {names}"


# ---------- Schedule CRUD (own refs) ----------
@pytest.fixture(scope="module")
def created_schedule(client, seed_ids):
    # Pick a date well in future to avoid conflicts with today's seeded schedule.
    target = (date.today() + timedelta(days=30)).isoformat()
    payload = {
        "date": target, "shift_type": "Morning",
        "start_time": "09:00", "end_time": "13:00",
        "post_site_id": seed_ids["acme_site"]["id"],
        "officer_id": seed_ids["acme_officer"]["id"],
        "vendor_id": seed_ids["acme_vendor"]["id"],
        "remarks": "TEST_iter10",
    }
    r = client.post(f"{API}/portal/schedules", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    for f in ("duty_rate", "billing_rate", "work_order_number"):
        # Financial fields must not be exposed
        assert f not in body or body[f] is None, f"Financial field leaked: {f}={body.get(f)}"
    yield body
    # cleanup
    try:
        client.delete(f"{API}/portal/schedules/{body['id']}", timeout=30)
    except Exception:
        pass


def test_portal_create_schedule_success(created_schedule, seed_ids):
    assert created_schedule["client_id"] == seed_ids["acme_id"]
    assert created_schedule["shift_status"] == "Not Started"
    assert created_schedule["duty_hours"] == 4.0


def test_portal_update_schedule_success(client, created_schedule):
    sid = created_schedule["id"]
    r = client.put(f"{API}/portal/schedules/{sid}",
                   json={"end_time": "14:00", "remarks": "TEST_iter10_edited"}, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["end_time"] == "14:00"
    assert body["duty_hours"] == 5.0
    assert body["remarks"] == "TEST_iter10_edited"


# ---------- Foreign refs blocked ----------
def test_create_with_foreign_post_site_returns_400(client, seed_ids):
    payload = {
        "date": (date.today() + timedelta(days=31)).isoformat(),
        "shift_type": "Morning", "start_time": "09:00", "end_time": "13:00",
        "post_site_id": seed_ids["globex_site"]["id"],  # foreign
        "officer_id": seed_ids["acme_officer"]["id"],
        "vendor_id": seed_ids["acme_vendor"]["id"],
    }
    r = client.post(f"{API}/portal/schedules", json=payload, timeout=30)
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"


def test_create_with_foreign_officer_returns_400(client, seed_ids):
    payload = {
        "date": (date.today() + timedelta(days=32)).isoformat(),
        "shift_type": "Morning", "start_time": "09:00", "end_time": "13:00",
        "post_site_id": seed_ids["acme_site"]["id"],
        "officer_id": seed_ids["globex_officer"]["id"],  # foreign
        "vendor_id": seed_ids["acme_vendor"]["id"],
    }
    r = client.post(f"{API}/portal/schedules", json=payload, timeout=30)
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"


def test_create_with_foreign_vendor_returns_400(client, seed_ids):
    if not seed_ids.get("globex_only_vendor"):
        pytest.skip("No Globex-only vendor seeded")
    payload = {
        "date": (date.today() + timedelta(days=33)).isoformat(),
        "shift_type": "Morning", "start_time": "09:00", "end_time": "13:00",
        "post_site_id": seed_ids["acme_site"]["id"],
        "officer_id": seed_ids["acme_officer"]["id"],
        "vendor_id": seed_ids["globex_only_vendor"]["id"],
    }
    r = client.post(f"{API}/portal/schedules", json=payload, timeout=30)
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"


# ---------- PUT/DELETE on foreign schedule -> 404 ----------
@pytest.fixture(scope="module")
def globex_schedule(admin, seed_ids):
    """Create a schedule owned by Globex via admin API for the isolation test."""
    target = (date.today() + timedelta(days=40)).isoformat()
    payload = {
        "date": target, "shift_type": "Morning",
        "start_time": "09:00", "end_time": "13:00",
        "client_id": seed_ids["globex_id"],
        "post_site_id": seed_ids["globex_site"]["id"],
        "officer_id": seed_ids["globex_officer"]["id"],
        "vendor_id": seed_ids["globex_only_vendor"]["id"] if seed_ids.get("globex_only_vendor") else None,
    }
    if not payload["vendor_id"]:
        pytest.skip("No Globex vendor available to create foreign schedule")
    r = admin.post(f"{API}/dispatch/schedules", json=payload, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Could not seed Globex schedule via admin: {r.status_code} {r.text}")
    sid = r.json()["id"]
    yield sid
    try:
        admin.delete(f"{API}/dispatch/schedules/{sid}", timeout=30)
    except Exception:
        pass


def test_client_cannot_edit_foreign_schedule_404(client, globex_schedule):
    r = client.put(f"{API}/portal/schedules/{globex_schedule}",
                   json={"remarks": "attack"}, timeout=30)
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


def test_client_cannot_delete_foreign_schedule_404(client, globex_schedule):
    r = client.delete(f"{API}/portal/schedules/{globex_schedule}", timeout=30)
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


# ---------- Regression: role gates ----------
def test_client_forbidden_from_dispatch(client):
    for path in ("/dispatch/officers", "/dispatch/post-sites", "/dispatch/schedules"):
        r = client.get(f"{API}{path}", timeout=30)
        assert r.status_code == 403, f"{path}: expected 403 got {r.status_code}"


def test_admin_forbidden_from_portal(admin):
    for path in ("/portal/officers", "/portal/post-sites", "/portal/schedules"):
        r = admin.get(f"{API}{path}", timeout=30)
        assert r.status_code == 403, f"{path}: expected 403 got {r.status_code}"


# ---------- Delete own schedule works ----------
def test_portal_delete_own_schedule(client, seed_ids):
    target = (date.today() + timedelta(days=50)).isoformat()
    payload = {
        "date": target, "shift_type": "Evening",
        "start_time": "18:00", "end_time": "22:00",
        "post_site_id": seed_ids["acme_site"]["id"],
        "officer_id": seed_ids["acme_officer"]["id"],
        "vendor_id": seed_ids["acme_vendor"]["id"],
        "remarks": "TEST_iter10_del",
    }
    r = client.post(f"{API}/portal/schedules", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    r = client.delete(f"{API}/portal/schedules/{sid}", timeout=30)
    assert r.status_code == 200, r.text
    # PUT after delete -> 404
    r = client.put(f"{API}/portal/schedules/{sid}", json={"remarks": "x"}, timeout=30)
    assert r.status_code == 404
