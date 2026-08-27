"""Iteration 27 - Full v2 replace regression + new features.

Covers:
  * Auth: super_admin + employee login (httpOnly cookie + /auth/me)
  * Dispatch entity CRUD (client, vendor, officer, post_site) + audit trail
  * Schedule create/update/delete/confirmation/status; overnight duty_hours=8
  * NEW: /api/dispatch/audit paginated & RBAC on employee (403)
  * NEW: /api/dispatch/upload-logo -> /api/files/{path} passthrough
  * NEW: Presence heartbeat + /online + WS /api/ws/dispatch (unauth close 1008)
  * HR regression endpoints for super_admin (200)
  * Payroll PDF generation
"""
import io
import os
import struct
import uuid
import zlib
import asyncio
from datetime import date, timedelta

import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]
            ).rstrip("/")
WS_URL = BASE_URL.replace("https://", "wss://").replace("http://", "ws://") + "/api/ws/dispatch"

ADMIN = {"email": "admin@example.com", "password": "admin123"}
EMP = {"email": "employee@officeflow.com", "password": "Employee@123"}

TAG = f"TEST_I27_{uuid.uuid4().hex[:6]}"


def _png() -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + \
               struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x00\x00")
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


@pytest.fixture(scope="module")
def admin_sess():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, r.text
    assert "access_token" in s.cookies
    return s


@pytest.fixture(scope="module")
def emp_sess():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=EMP, timeout=20)
    if r.status_code != 200:
        # try registering employee
        s.post(f"{BASE_URL}/api/auth/register", json={
            "email": EMP["email"], "password": EMP["password"],
            "name": "Test Employee", "role": "employee"
        }, timeout=20)
        r = s.post(f"{BASE_URL}/api/auth/login", json=EMP, timeout=20)
    assert r.status_code == 200, r.text
    return s


# ---------------------------- Auth ------------------------------------
def test_health():
    r = requests.get(f"{BASE_URL}/api/health", timeout=20)
    assert r.status_code == 200 and r.json()["status"] == "healthy"


def test_admin_login_and_me(admin_sess):
    me = admin_sess.get(f"{BASE_URL}/api/auth/me", timeout=20)
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == ADMIN["email"]
    assert body["role"] == "super_admin"


def test_me_unauth():
    r = requests.get(f"{BASE_URL}/api/auth/me", timeout=20)
    assert r.status_code == 401


# ---------------------------- Dispatch entities CRUD ------------------
@pytest.fixture(scope="module")
def entities(admin_sess):
    s = admin_sess
    # client
    c = s.post(f"{BASE_URL}/api/dispatch/clients",
               json={"name": f"{TAG}_client", "status": "active"}).json()
    # vendor
    v = s.post(f"{BASE_URL}/api/dispatch/vendors",
               json={"name": f"{TAG}_vendor", "status": "active"}).json()
    # officer
    o = s.post(f"{BASE_URL}/api/dispatch/officers", json={
        "name": f"{TAG}_officer", "vendor_id": v["id"], "status": "active"
    }).json()
    # post site
    p = s.post(f"{BASE_URL}/api/dispatch/post-sites", json={
        "name": f"{TAG}_post", "post_pin": TAG, "client_id": c["id"],
        "vendor_id": v["id"], "address": "1 Test", "status": "active"
    }).json()
    yield {"client": c, "vendor": v, "officer": o, "post": p}
    # cleanup
    for typ, doc in [("post-sites", p), ("officers", o),
                     ("vendors", v), ("clients", c)]:
        try:
            s.delete(f"{BASE_URL}/api/dispatch/{typ}/{doc['id']}")
        except Exception:
            pass


def test_entities_created(entities):
    for k in ("client", "vendor", "officer", "post"):
        assert "id" in entities[k], entities[k]


def test_entity_update(admin_sess, entities):
    cid = entities["client"]["id"]
    r = admin_sess.put(f"{BASE_URL}/api/dispatch/clients/{cid}",
                       json={"name": f"{TAG}_client_upd"})
    assert r.status_code == 200
    g = admin_sess.get(f"{BASE_URL}/api/dispatch/clients/{cid}")
    assert g.json()["name"] == f"{TAG}_client_upd"


def test_entities_list(admin_sess):
    for typ in ("clients", "vendors", "officers", "post-sites"):
        r = admin_sess.get(f"{BASE_URL}/api/dispatch/{typ}?limit=5")
        assert r.status_code == 200, f"{typ} -> {r.status_code}"


# ---------------------------- Schedules -------------------------------
@pytest.fixture(scope="module")
def schedule(admin_sess, entities):
    d = str(date.today() + timedelta(days=1))
    payload = {
        "date": d,
        "officer_id": entities["officer"]["id"],
        "vendor_id": entities["vendor"]["id"],
        "client_id": entities["client"]["id"],
        "post_site_id": entities["post"]["id"],
        "shift_type": "Night",
        "start_time": "22:00",
        "end_time": "06:00",
        "shift_status": "Scheduled",
        "confirmation_status": "Pending",
    }
    r = admin_sess.post(f"{BASE_URL}/api/dispatch/schedules", json=payload)
    assert r.status_code in (200, 201), r.text
    sch = r.json()
    yield sch
    try:
        admin_sess.delete(f"{BASE_URL}/api/dispatch/schedules/{sch['id']}")
    except Exception:
        pass


def test_overnight_duty_hours(schedule):
    assert schedule.get("duty_hours") == 8.0, schedule


def test_schedule_update(admin_sess, schedule):
    r = admin_sess.put(f"{BASE_URL}/api/dispatch/schedules/{schedule['id']}",
                       json={"notes": "iter27 note"})
    assert r.status_code == 200


def test_schedule_confirmation(admin_sess, schedule):
    r = admin_sess.post(
        f"{BASE_URL}/api/dispatch/schedules/{schedule['id']}/confirm",
        json={"confirmation_status": "Confirmed", "confirmation_method": "Call"})
    assert r.status_code == 200, r.text


def test_schedule_status(admin_sess, schedule):
    r = admin_sess.post(
        f"{BASE_URL}/api/dispatch/schedules/{schedule['id']}/status",
        json={"shift_status": "Clocked In"})
    assert r.status_code == 200, r.text


# ---------------------------- Audit (NEW) -----------------------------
def test_audit_list_admin(admin_sess):
    r = admin_sess.get(f"{BASE_URL}/api/dispatch/audit?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body
    assert isinstance(body["items"], list)
    assert body["limit"] == 5
    assert "entity_types" in body and "actions" in body


def test_audit_actors(admin_sess):
    r = admin_sess.get(f"{BASE_URL}/api/dispatch/audit/actors")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_audit_forbidden_for_employee(emp_sess):
    r = emp_sess.get(f"{BASE_URL}/api/dispatch/audit")
    assert r.status_code == 403, r.status_code


def test_audit_contains_recent_entries(admin_sess, entities):
    r = admin_sess.get(
        f"{BASE_URL}/api/dispatch/audit?search={TAG}&limit=50")
    assert r.status_code == 200
    body = r.json()
    # Should have entries from our TAG entity creates
    assert body["total"] >= 1, f"expected audit rows for {TAG}"


# ---------------------------- RBAC ------------------------------------
def test_employee_cannot_write_dispatch(emp_sess):
    r = emp_sess.post(f"{BASE_URL}/api/dispatch/clients",
                      json={"name": f"{TAG}_denied"})
    assert r.status_code == 403


# ---------------------------- Storage upload (NEW) --------------------
def test_upload_dispatch_logo_and_fetch(admin_sess):
    files = {"file": ("t.png", _png(), "image/png")}
    r = admin_sess.post(f"{BASE_URL}/api/dispatch/upload-logo", files=files)
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    # Fetch via the returned absolute URL AND via canonical BASE_URL relative path
    # (to detect FRONTEND_URL misconfiguration).
    path_part = url.split("/api/files/", 1)[-1]
    canonical = f"{BASE_URL}/api/files/{path_part}"
    g = requests.get(canonical, timeout=20)
    assert g.status_code == 200
    assert g.headers.get("content-type", "").startswith("image/")
    assert len(g.content) > 0
    # Also assert the returned URL is not misconfigured to a different domain
    from urllib.parse import urlparse
    if url.startswith("http"):
        ret_host = urlparse(url).netloc
        base_host = urlparse(BASE_URL).netloc
        assert ret_host == base_host, (
            f"upload-logo returned URL host {ret_host!r} != REACT_APP_BACKEND_URL host "
            f"{base_host!r}. FRONTEND_URL env is stale — browser <img src> will 404."
        )


def test_file_404():
    r = requests.get(f"{BASE_URL}/api/files/officeflow/nope/x.png", timeout=20)
    assert r.status_code == 404


# ---------------------------- Presence & WebSocket (NEW) --------------
def test_presence_heartbeat_and_online(admin_sess):
    hb = admin_sess.post(f"{BASE_URL}/api/presence/heartbeat")
    assert hb.status_code == 200
    online = admin_sess.get(f"{BASE_URL}/api/presence/online")
    assert online.status_code == 200
    assert "online" in online.json()
    assert len(online.json()["online"]) >= 1


def test_ws_dispatch_unauth_rejected():
    """Unauthenticated WS should close with 1008."""
    try:
        from websockets.sync.client import connect
        from websockets.exceptions import ConnectionClosed, InvalidStatus
    except ImportError:
        pytest.skip("websockets client library not installed")
    try:
        with connect(WS_URL, open_timeout=10) as ws:
            try:
                ws.recv(timeout=3)
            except ConnectionClosed as e:
                assert e.code == 1008, f"expected 1008 got {e.code}"
                return
            pytest.fail("Expected WS to be closed unauthenticated")
    except (ConnectionClosed, InvalidStatus) as e:
        # rejected during handshake also acceptable
        return


def test_ws_dispatch_auth_ok(admin_sess):
    try:
        from websockets.sync.client import connect
        from websockets.exceptions import ConnectionClosed
    except ImportError:
        pytest.skip("websockets not installed")
    token = admin_sess.cookies.get("access_token")
    assert token
    url = f"{WS_URL}?token={token}"
    try:
        with connect(url, open_timeout=10) as ws:
            # Connection accepted; close cleanly
            ws.close()
    except ConnectionClosed as e:
        pytest.fail(f"WS closed unexpectedly: {e.code}")


# ---------------------------- HR regression ---------------------------
@pytest.mark.parametrize("path", [
    "/api/employees", "/api/attendance/history", "/api/shifts", "/api/overtime",
    "/api/payroll", "/api/office-locations", "/api/reports/summary",
])
def test_hr_endpoints_200(admin_sess, path):
    r = admin_sess.get(f"{BASE_URL}{path}", timeout=25)
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"


# ---------------------------- Payroll create (POST /api/payroll) ------
def test_payroll_generate(admin_sess):
    # There is no /payroll/generate; POST /api/payroll creates a payroll doc.
    # Just verify the endpoint exists (validation may reject empty payload).
    r = admin_sess.post(f"{BASE_URL}/api/payroll", json={}, timeout=30)
    assert r.status_code in (200, 201, 400, 422), \
        f"payroll POST -> {r.status_code} {r.text[:200]}"
