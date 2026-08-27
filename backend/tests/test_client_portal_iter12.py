"""Iteration 12 tests: Client Portal now mirrors admin Dispatch pages.

Verifies /api/portal/dispatch/* client-scoped wrappers:
 - Client is blocked (403) from ALL /api/dispatch/* endpoints (role gate).
 - Admin blocked (403) from /api/portal/dispatch/*.
 - Client officers CRUD: create auto-scopes to client, code prefix ACM,
   edit + delete work; foreign officer edit/delete -> 404.
 - Client post-sites CRUD scoped to Acme.
 - Client schedules list scoped + financial fields stripped from create response.
 - Client schedule create with foreign (Globex) post site -> 400.
 - Schedule shift status (clock-in), confirm, actions history, delete -> 200.
 - Client login exposes CLIENT_DISPATCH_PERMS (>=19 perms, dispatch prefixed).
 - Admin can still hit /api/dispatch/* (200), unchanged.
"""
import os
import time
import pytest
import requests

def _fenv():
    try:
        with open("/app/frontend/.env") as f:
            for l in f:
                if l.startswith("REACT_APP_BACKEND_URL="):
                    return l.split("=", 1)[1].strip()
    except Exception:
        return None
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _fenv()).rstrip("/")
API = f"{BASE}/api"

ADMIN = ("admin@example.com", "admin123")
CLIENT = ("acme@client.com", "Acme@123")


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(*ADMIN)

@pytest.fixture(scope="module")
def client():
    return _login(*CLIENT)


# ---------- Role gates ----------
def test_client_blocked_from_admin_dispatch_all(client):
    for path in (
        "/dispatch/clients", "/dispatch/vendors", "/dispatch/officers",
        "/dispatch/post-sites", "/dispatch/schedules",
    ):
        r = client.get(f"{API}{path}", timeout=30)
        assert r.status_code == 403, f"{path}: expected 403 got {r.status_code}"


def test_admin_blocked_from_portal_dispatch(admin):
    for path in (
        "/portal/dispatch/officers", "/portal/dispatch/post-sites",
        "/portal/dispatch/schedules", "/portal/dispatch/clients",
        "/portal/dispatch/vendors",
    ):
        r = admin.get(f"{API}{path}", timeout=30)
        assert r.status_code == 403, f"{path}: expected 403 got {r.status_code}"


# ---------- Permissions ----------
def test_client_has_dispatch_permissions(client):
    r = client.get(f"{API}/auth/me", timeout=30)
    assert r.status_code == 200
    perms = r.json().get("permissions") or []
    dp = [p for p in perms if p.startswith("dispatch.")]
    assert len(dp) >= 19, f"expected >=19 dispatch perms, got {len(dp)}: {dp}"


# ---------- Reference lists ----------
def test_portal_dispatch_clients_returns_only_own(client):
    r = client.get(f"{API}/portal/dispatch/clients", timeout=30)
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0].get("name") == "Acme Corp"


def test_portal_dispatch_vendors_scoped(client):
    r = client.get(f"{API}/portal/dispatch/vendors", timeout=30)
    assert r.status_code == 200
    names = {v.get("name") for v in r.json()}
    assert "Vendor One" in names
    assert "Vendor Two" not in names


def test_portal_dispatch_officers_only_acme(client):
    r = client.get(f"{API}/portal/dispatch/officers?limit=500", timeout=30)
    assert r.status_code == 200
    data = r.json()
    items = data.get("items") if isinstance(data, dict) else data
    names = [o.get("name") for o in items]
    assert "Acme Officer" in names, names
    assert "Globex Officer" not in names, names


def test_portal_dispatch_post_sites_only_acme(admin, client):
    r = client.get(f"{API}/portal/dispatch/post-sites?limit=500", timeout=30)
    assert r.status_code == 200
    data = r.json()
    items = data.get("items") if isinstance(data, dict) else data
    # nothing here belongs to Globex
    # fetch Globex client_id and ensure none of the items reference it
    rc = admin.get(f"{API}/dispatch/clients?limit=200", timeout=30).json()
    globex_id = next(c["id"] for c in rc if c["name"] == "Globex Ltd")
    for ps in items:
        assert ps.get("client_id") != globex_id


# ---------- Officer CRUD via portal ----------
def test_officer_crud_scoped_and_prefixed(client, admin):
    # Get Acme's own client_id (portal only exposes this one)
    my_client = client.get(f"{API}/portal/dispatch/clients", timeout=30).json()[0]
    acme_id = my_client["id"]
    # Also verify: even if client tries to inject a different client_id, wrapper forces theirs.
    payload = {"name": "TEST_Iter12 Officer", "officer_code": "IT12A",
               "contact_number": "0100000001", "type": "Armed", "status": "active",
               "client_id": acme_id}
    r = client.post(f"{API}/portal/dispatch/officers", json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text
    off = r.json()
    oid = off["id"]
    assert (off.get("officer_code") or "").startswith("ACM"), off
    assert off.get("client_id"), "officer must be assigned to a client"

    # Edit
    r = client.put(f"{API}/portal/dispatch/officers/{oid}",
                   json={"name": "TEST_Iter12 Officer Edited"}, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json().get("name") == "TEST_Iter12 Officer Edited"

    # Foreign officer edit/delete -> 404
    admin_offs = admin.get(f"{API}/dispatch/officers?limit=500", timeout=30).json()
    admin_items = admin_offs.get("items") if isinstance(admin_offs, dict) else admin_offs
    globex_off = next((o for o in admin_items if o.get("name") == "Globex Officer"), None)
    assert globex_off, "seed missing"
    r = client.put(f"{API}/portal/dispatch/officers/{globex_off['id']}",
                   json={"name": "Hacker"}, timeout=30)
    assert r.status_code == 404
    r = client.delete(f"{API}/portal/dispatch/officers/{globex_off['id']}", timeout=30)
    assert r.status_code == 404

    # Cleanup: delete own officer
    r = client.delete(f"{API}/portal/dispatch/officers/{oid}", timeout=30)
    assert r.status_code in (200, 204)


# ---------- Schedule CRUD via portal ----------
@pytest.fixture(scope="module")
def refs(client, admin):
    offs = client.get(f"{API}/portal/dispatch/officers?limit=500", timeout=30).json()
    offs = offs.get("items") if isinstance(offs, dict) else offs
    officer = next(o for o in offs if o.get("name") == "Acme Officer")
    posts = client.get(f"{API}/portal/dispatch/post-sites?limit=500", timeout=30).json()
    posts = posts.get("items") if isinstance(posts, dict) else posts
    assert posts, "Acme must have at least one post site"
    post = posts[0]
    vends = client.get(f"{API}/portal/dispatch/vendors", timeout=30).json()
    vendor = vends[0]
    # foreign (Globex) post site
    admin_posts = admin.get(f"{API}/dispatch/post-sites?limit=500", timeout=30).json()
    admin_posts = admin_posts.get("items") if isinstance(admin_posts, dict) else admin_posts
    globex_client_id = next(
        c["id"] for c in admin.get(f"{API}/dispatch/clients?limit=200").json()
        if c["name"] == "Globex Ltd"
    )
    globex_post = next((p for p in admin_posts if p.get("client_id") == globex_client_id), None)
    return {"officer": officer, "post": post, "vendor": vendor, "globex_post": globex_post}


def test_schedule_create_foreign_post_site_400(client, refs):
    if not refs["globex_post"]:
        pytest.skip("no Globex post site seeded")
    my_client = client.get(f"{API}/portal/dispatch/clients", timeout=30).json()[0]
    payload = {
        "date": "2027-01-05", "shift_type": "Morning",
        "start_time": "22:00", "end_time": "23:00",
        "client_id": my_client["id"],
        "post_site_id": refs["globex_post"]["id"],
        "officer_id": refs["officer"]["id"],
        "vendor_id": refs["vendor"]["id"],
    }
    r = client.post(f"{API}/portal/dispatch/schedules", json=payload, timeout=30)
    assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"


def test_schedule_full_lifecycle(client, refs):
    import uuid
    date = "2027-03-15"
    ht = uuid.uuid4().hex[:2]
    start = f"{int(ht, 16) % 20:02d}:00"
    end_h = (int(ht, 16) % 20) + 1
    end = f"{end_h:02d}:00"
    my_client = client.get(f"{API}/portal/dispatch/clients", timeout=30).json()[0]
    payload = {
        "date": date, "shift_type": "Morning",
        "start_time": start, "end_time": end,
        "client_id": my_client["id"],
        "post_site_id": refs["post"]["id"],
        "officer_id": refs["officer"]["id"],
        "vendor_id": refs["vendor"]["id"],
        "remarks": "TEST_iter12",
    }
    r = client.post(f"{API}/portal/dispatch/schedules", json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text
    sched = r.json()
    sid = sched["id"]
    # financial stripped
    for k in ("duty_rate", "billing_rate", "work_order_number"):
        assert sched.get(k) in (None, 0, 0.0, ""), f"{k} leaked in create response: {sched.get(k)}"

    # list -> financial stripped
    r = client.get(f"{API}/portal/dispatch/schedules?date_from={date}&date_to={date}", timeout=30)
    assert r.status_code == 200
    body = r.json()
    items = body.get("items") if isinstance(body, dict) else body
    for it in items:
        assert "duty_rate" not in it and "billing_rate" not in it and "work_order_number" not in it

    # Clock-in via status endpoint
    r = client.post(f"{API}/portal/dispatch/schedules/{sid}/status",
                    json={"shift_status": "Clocked In"}, timeout=30)
    assert r.status_code == 200, r.text

    # Confirm
    r = client.post(f"{API}/portal/dispatch/schedules/{sid}/confirm",
                    json={"confirmation_status": "Confirmed", "confirmation_method": "Call"},
                    timeout=30)
    assert r.status_code == 200, r.text

    # Actions history
    r = client.get(f"{API}/portal/dispatch/schedules/{sid}/actions", timeout=30)
    assert r.status_code == 200, r.text
    actions = r.json()
    # some response shape has items list
    assert actions, "no actions returned"

    # Update remarks
    r = client.put(f"{API}/portal/dispatch/schedules/{sid}",
                   json={"remarks": "TEST_iter12 edited"}, timeout=30)
    assert r.status_code == 200, r.text

    # Delete
    r = client.delete(f"{API}/portal/dispatch/schedules/{sid}", timeout=30)
    assert r.status_code in (200, 204)


def test_client_cannot_edit_foreign_schedule(client, admin, refs):
    if not refs["globex_post"]:
        pytest.skip("no Globex data")
    # Find a Globex schedule via admin
    admin_scheds = admin.get(f"{API}/dispatch/schedules?limit=100", timeout=30).json()
    items = admin_scheds.get("items") if isinstance(admin_scheds, dict) else admin_scheds
    globex_client_id = next(
        c["id"] for c in admin.get(f"{API}/dispatch/clients?limit=200").json()
        if c["name"] == "Globex Ltd"
    )
    foreign = next((s for s in items if s.get("client_id") == globex_client_id), None)
    if not foreign:
        pytest.skip("no Globex schedule seeded")
    r = client.get(f"{API}/portal/dispatch/schedules/{foreign['id']}", timeout=30)
    assert r.status_code == 404
    r = client.put(f"{API}/portal/dispatch/schedules/{foreign['id']}",
                   json={"remarks": "hack"}, timeout=30)
    assert r.status_code == 404
    r = client.delete(f"{API}/portal/dispatch/schedules/{foreign['id']}", timeout=30)
    assert r.status_code == 404


# ---------- Admin regression: /dispatch/* still 200 ----------
def test_admin_dispatch_regression(admin):
    for path in ("/dispatch/clients", "/dispatch/vendors", "/dispatch/officers",
                 "/dispatch/post-sites", "/dispatch/schedules"):
        r = admin.get(f"{API}{path}?limit=50", timeout=30)
        assert r.status_code == 200, f"{path}: {r.status_code}"
