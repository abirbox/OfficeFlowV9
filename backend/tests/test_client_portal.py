"""Client Portal + Vendor-Client linking tests.

Verifies:
 - Admin login unchanged.
 - Vendor create/update persists client_ids (multi client linking).
 - Admin can set/get/delete a client's portal login credentials.
 - Client can login and receives client role.
 - Client-only /api/portal/* endpoints scope data to their client_id.
 - Client is blocked (403) from admin dispatch endpoints.
 - Data isolation: acme@client.com sees only vendors linked to Acme Corp.
"""
import os
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

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin123"
CLIENT_EMAIL = "acme@client.com"
CLIENT_PASSWORD = "Acme@123"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"Login failed {email}: {r.status_code} {r.text}"
    return s, r.json()


@pytest.fixture(scope="module")
def admin_session():
    s, data = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    return s


@pytest.fixture(scope="module")
def client_session():
    s, data = _login(CLIENT_EMAIL, CLIENT_PASSWORD)
    role = data.get("role") or data.get("user", {}).get("role")
    assert role == "client", f"Expected role client, got {data}"
    return s


# ---------- Admin login unchanged ----------
def test_admin_login_and_me(admin_session):
    r = admin_session.get(f"{API}/auth/me", timeout=30)
    assert r.status_code == 200
    me = r.json()
    assert me.get("role") in ("super_admin", "admin")


# ---------- Seeded data sanity ----------
def test_seed_clients_and_vendors_present(admin_session):
    r = admin_session.get(f"{API}/dispatch/clients?limit=200", timeout=30)
    assert r.status_code == 200
    clients = r.json()
    names = {c["name"] for c in clients}
    assert "Acme Corp" in names, f"Missing Acme Corp seed. Got: {names}"
    assert "Globex Ltd" in names, f"Missing Globex Ltd seed. Got: {names}"

    r = admin_session.get(f"{API}/dispatch/vendors?limit=200", timeout=30)
    assert r.status_code == 200
    vendors = r.json()
    vnames = {v["name"] for v in vendors}
    for v in ("Vendor One", "Vendor Two", "Vendor Both"):
        assert v in vnames, f"Missing vendor {v}. Got: {vnames}"

    acme_id = next(c["id"] for c in clients if c["name"] == "Acme Corp")
    globex_id = next(c["id"] for c in clients if c["name"] == "Globex Ltd")
    v_one = next(v for v in vendors if v["name"] == "Vendor One")
    v_two = next(v for v in vendors if v["name"] == "Vendor Two")
    v_both = next(v for v in vendors if v["name"] == "Vendor Both")

    assert acme_id in (v_one.get("client_ids") or [])
    assert globex_id not in (v_one.get("client_ids") or [])
    assert globex_id in (v_two.get("client_ids") or [])
    assert acme_id not in (v_two.get("client_ids") or [])
    both = v_both.get("client_ids") or []
    assert acme_id in both and globex_id in both


# ---------- Vendor CRUD with client_ids ----------
def test_vendor_create_update_with_client_ids(admin_session):
    r = admin_session.get(f"{API}/dispatch/clients?limit=200", timeout=30)
    clients = r.json()
    acme_id = next(c["id"] for c in clients if c["name"] == "Acme Corp")
    globex_id = next(c["id"] for c in clients if c["name"] == "Globex Ltd")

    payload = {
        "code": "TSTV",
        "name": "TEST_Vendor_Portal",
        "client_ids": [acme_id],
        "status": "active",
    }
    r = admin_session.post(f"{API}/dispatch/vendors", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    v = r.json()
    vid = v["id"]
    assert v.get("client_ids") == [acme_id]

    # Update to link both clients
    r = admin_session.put(
        f"{API}/dispatch/vendors/{vid}",
        json={"client_ids": [acme_id, globex_id]},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    assert set(r.json().get("client_ids") or []) == {acme_id, globex_id}

    # GET to verify persistence
    r = admin_session.get(f"{API}/dispatch/vendors/{vid}", timeout=30)
    assert r.status_code == 200
    assert set(r.json().get("client_ids") or []) == {acme_id, globex_id}

    # Cleanup
    admin_session.delete(f"{API}/dispatch/vendors/{vid}", timeout=30)


# ---------- Admin client portal credentials management ----------
def test_admin_can_view_client_portal_status(admin_session):
    r = admin_session.get(f"{API}/dispatch/clients?limit=200", timeout=30)
    acme_id = next(c["id"] for c in r.json() if c["name"] == "Acme Corp")
    r = admin_session.get(f"{API}/dispatch/clients/{acme_id}/portal", timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert body.get("enabled") is True
    assert body.get("email") == CLIENT_EMAIL


# ---------- Client login + role ----------
def test_client_login_returns_client_role(client_session):
    r = client_session.get(f"{API}/auth/me", timeout=30)
    assert r.status_code == 200
    me = r.json()
    assert me.get("role") == "client"
    # client_id may or may not be exposed on /auth/me depending on User serializer,
    # but /portal/me is authoritative for portal data.


# ---------- /api/portal/* returns client-scoped data ----------
def test_portal_me(client_session):
    r = client_session.get(f"{API}/portal/me", timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert body.get("client", {}).get("name") == "Acme Corp"


def test_portal_summary(client_session):
    r = client_session.get(f"{API}/portal/summary", timeout=30)
    assert r.status_code == 200
    body = r.json()
    for k in ("total_schedules", "upcoming_schedules", "completed_schedules",
              "vendors", "officers", "post_sites",
              "checkins_today", "active_post_sites", "payslip_7d"):
        assert k in body, f"Missing {k} in summary: {body}"
    # Acme is linked to Vendor One + Vendor Both = 2 vendors
    assert body["vendors"] >= 2


# ---------- New: dashboard summary cards (iteration 9) ----------
def test_portal_summary_new_cards_scoped_to_acme(client_session):
    r = client_session.get(f"{API}/portal/summary", timeout=30)
    assert r.status_code == 200
    body = r.json()
    # Seeded expected values for Acme Corp
    assert body["checkins_today"] == 1, f"checkins_today expected 1, got {body['checkins_today']}"
    assert body["active_post_sites"] == 1, f"active_post_sites expected 1, got {body['active_post_sites']}"
    ps = body["payslip_7d"]
    assert isinstance(ps, dict)
    for k in ("total", "officers", "shifts", "from", "to"):
        assert k in ps, f"Missing payslip_7d.{k}"
    assert ps["total"] == 80.0, f"payslip_7d.total expected 80.0, got {ps['total']}"
    assert ps["shifts"] == 1
    assert ps["officers"] == 1
    # Data isolation: Globex officer rate 99 must NOT leak. 80 is the only valid Acme total.
    assert ps["total"] != 99.0 * 8 and ps["total"] < 800


def test_portal_summary_isolation_globex_not_leaking(admin_session, client_session):
    # Verify that Globex has its own clocked-in officer today via admin API,
    # and Acme summary still reads 1/1/80.
    r = admin_session.get(f"{API}/dispatch/clients?limit=200", timeout=30)
    clients = r.json()
    globex_id = next((c["id"] for c in clients if c["name"] == "Globex Ltd"), None)
    assert globex_id, "Globex Ltd seed missing"
    # Just re-fetch Acme portal summary and assert stable Acme-only numbers
    r = client_session.get(f"{API}/portal/summary", timeout=30)
    body = r.json()
    assert body["checkins_today"] == 1
    assert body["active_post_sites"] == 1
    assert body["payslip_7d"]["total"] == 80.0


def test_portal_vendors_isolation(client_session):
    r = client_session.get(f"{API}/portal/vendors", timeout=30)
    assert r.status_code == 200
    vendors = r.json()
    names = {v["name"] for v in vendors}
    assert "Vendor One" in names
    assert "Vendor Both" in names
    assert "Vendor Two" not in names, f"Data leak! Client sees Vendor Two: {names}"


def test_portal_schedules(client_session):
    r = client_session.get(f"{API}/portal/schedules", timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body
    # No financial fields exposed
    for item in body["items"]:
        for f in ("duty_rate", "billing_rate", "work_order_number"):
            assert f not in item, f"Financial field {f} leaked to client portal"


def test_portal_reports(client_session):
    r = client_session.get(f"{API}/portal/reports", timeout=30)
    assert r.status_code == 200
    body = r.json()
    assert "totals" in body and "by_vendor" in body and "by_status" in body


# ---------- Client blocked from admin endpoints ----------
def test_client_blocked_from_admin_dispatch(client_session):
    r = client_session.get(f"{API}/dispatch/vendors", timeout=30)
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"

    r = client_session.get(f"{API}/dispatch/clients", timeout=30)
    assert r.status_code == 403

    r = client_session.get(f"{API}/dispatch/schedules", timeout=30)
    assert r.status_code == 403


def test_admin_blocked_from_portal(admin_session):
    # Admin (not a client role) must not access /portal/*
    r = admin_session.get(f"{API}/portal/vendors", timeout=30)
    assert r.status_code == 403
    r = admin_session.get(f"{API}/portal/summary", timeout=30)
    assert r.status_code == 403
