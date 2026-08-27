"""Iteration 4 backend regression tests.

Scope (from review request):
- Auth: admin login with seeded credentials
- Post Sites: `location` is mandatory on create
- Dispatch Invoice Locations filter: progressive narrowing by date range -> client -> vendor
- Dispatch Invoice preview: honours the post_site_id (location) filter
- Dispatch Invoice save: persists post_site_id and only that location's lines
"""
import os
import uuid

import pytest
import requests


def _base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    for p in ("/app/frontend/.env", "/app/OfficeFlowERP/frontend/.env"):
        if os.path.exists(p):
            with open(p) as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


BASE = _base()
API = f"{BASE}/api"
ADMIN = {"email": "admin@example.com", "password": "admin123"}

TAG = uuid.uuid4().hex[:6]
IN_RANGE = ("2026-03-01", "2026-03-31")


# ---------- Auth ----------

@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"admin login failed {r.status_code}: {r.text[:300]}")
    return s


def test_admin_login(admin):
    r = admin.get(f"{API}/auth/me", timeout=30)
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["email"] == ADMIN["email"]
    assert me["role"] == "super_admin"


# ---------- Seed data ----------

@pytest.fixture(scope="module")
def seed(admin):
    """Create two clients, two vendors, one officer, five post sites and
    schedules so the location narrowing logic can be asserted deterministically.
    """
    created = {"clients": [], "vendors": [], "officers": [], "post_sites": [],
               "schedules": [], "invoices": []}

    def post(path, body):
        r = admin.post(f"{API}{path}", json=body, timeout=30)
        assert r.status_code in (200, 201), f"{path} -> {r.status_code} {r.text[:300]}"
        return r.json()

    c1 = post("/dispatch/clients", {"name": f"TEST_C1_{TAG}", "code": f"TC1{TAG}"})
    c2 = post("/dispatch/clients", {"name": f"TEST_C2_{TAG}", "code": f"TC2{TAG}"})
    v1 = post("/dispatch/vendors", {"name": f"TEST_V1_{TAG}", "code": f"TV1{TAG}"})
    v2 = post("/dispatch/vendors", {"name": f"TEST_V2_{TAG}", "code": f"TV2{TAG}"})
    created["clients"] += [c1["id"], c2["id"]]
    created["vendors"] += [v1["id"], v2["id"]]

    off = post("/dispatch/officers", {"name": f"TEST_OFF_{TAG}", "contact_number": "0170000000",
                                     "status": "active"})
    created["officers"].append(off["id"])

    sites = {}
    for key in ["A", "B", "C", "D", "E"]:
        p = post("/dispatch/post-sites", {
            "post_pin": f"TP{key}{TAG}", "name": f"TEST_SITE_{key}_{TAG}",
            "location": f"TESTLOC_{key}_{TAG}", "city": "Testville", "status": "active",
        })
        sites[key] = p
        created["post_sites"].append(p["id"])

    def schedule(date, client, vendor, site, start, end, status="Complete"):
        s = post("/dispatch/schedules", {
            "date": date, "shift_type": "Morning", "start_time": start, "end_time": end,
            "client_id": client["id"], "vendor_id": vendor["id"],
            "post_site_id": sites[site]["id"], "officer_id": off["id"],
            "work_order_number": f"WO-{TAG}-{site}", "duty_rate": 10.0, "billing_rate": 20.0,
        })
        created["schedules"].append(s["id"])
        r = admin.post(f"{API}/dispatch/schedules/{s['id']}/status",
                       json={"shift_status": status}, timeout=30)
        assert r.status_code == 200, r.text
        return s

    # In-range schedules (different dates so the officer conflict check passes)
    s_a = schedule("2026-03-02", c1, v1, "A", "08:00", "16:00")
    s_b = schedule("2026-03-03", c1, v1, "B", "08:00", "16:00")
    s_c = schedule("2026-03-04", c1, v2, "C", "08:00", "16:00")
    s_d2 = schedule("2026-03-05", c2, v1, "D", "08:00", "16:00")
    # Out-of-range schedule at site E
    s_e = schedule("2026-09-10", c1, v1, "E", "08:00", "16:00")

    yield {
        "c1": c1, "c2": c2, "v1": v1, "v2": v2, "sites": sites, "officer": off,
        "created": created,
        "sched": {"A": s_a, "B": s_b, "C": s_c, "D": s_d2, "E": s_e},
    }

    # ---- teardown ----
    for inv in created["invoices"]:
        admin.delete(f"{API}/dispatch/invoices/{inv}", timeout=30)
    for sid in created["schedules"]:
        admin.delete(f"{API}/dispatch/schedules/{sid}", timeout=30)
    for pid in created["post_sites"]:
        admin.delete(f"{API}/dispatch/post-sites/{pid}", timeout=30)
    for oid in created["officers"]:
        admin.delete(f"{API}/dispatch/officers/{oid}", timeout=30)
    for cid in created["clients"]:
        admin.delete(f"{API}/dispatch/clients/{cid}", timeout=30)
    for vid in created["vendors"]:
        admin.delete(f"{API}/dispatch/vendors/{vid}", timeout=30)


# ---------- Post Sites: mandatory location ----------

def test_post_site_missing_location_rejected(admin):
    r = admin.post(f"{API}/dispatch/post-sites", json={
        "post_pin": f"TPX{TAG}", "name": f"TEST_NOLOC_{TAG}",
    }, timeout=30)
    assert r.status_code in (400, 422), f"expected validation error, got {r.status_code}: {r.text[:300]}"


def test_post_site_blank_location_rejected(admin):
    r = admin.post(f"{API}/dispatch/post-sites", json={
        "post_pin": f"TPY{TAG}", "name": f"TEST_BLANKLOC_{TAG}", "location": "",
    }, timeout=30)
    assert r.status_code in (400, 422), f"expected validation error, got {r.status_code}: {r.text[:300]}"


def test_post_site_with_location_created(admin):
    body = {"post_pin": f"TPZ{TAG}", "name": f"TEST_OKLOC_{TAG}",
            "location": f"TESTLOC_OK_{TAG}", "city": "Testville"}
    r = admin.post(f"{API}/dispatch/post-sites", json=body, timeout=30)
    assert r.status_code in (200, 201), r.text
    j = r.json()
    assert j["location"] == body["location"]
    assert "_id" not in j and j.get("id")
    # verify persistence
    lst = admin.get(f"{API}/dispatch/post-sites", timeout=30).json()
    items = lst["items"] if isinstance(lst, dict) else lst
    match = [p for p in items if p["id"] == j["id"]]
    assert match and match[0]["location"] == body["location"]
    admin.delete(f"{API}/dispatch/post-sites/{j['id']}", timeout=30)


# ---------- Invoice locations filter ----------

def _locations(admin, **params):
    r = admin.get(f"{API}/dispatch/invoices/locations", params=params, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    return {o["id"]: o for o in data}


def test_locations_unfiltered_includes_all_seeded(admin, seed):
    got = _locations(admin)
    for key in ["A", "B", "C", "D", "E"]:
        assert seed["sites"][key]["id"] in got, f"site {key} missing from unfiltered locations"
    sample = got[seed["sites"]["A"]["id"]]
    assert sample["location"] == seed["sites"]["A"]["location"]
    assert "post_pin" in sample and "name" in sample


def test_locations_narrow_by_date_range(admin, seed):
    got = _locations(admin, date_from=IN_RANGE[0], date_to=IN_RANGE[1])
    for key in ["A", "B", "C", "D"]:
        assert seed["sites"][key]["id"] in got, f"site {key} should be in date range"
    assert seed["sites"]["E"]["id"] not in got, "out-of-range site E leaked into date-filtered locations"


def test_locations_narrow_by_client(admin, seed):
    got = _locations(admin, date_from=IN_RANGE[0], date_to=IN_RANGE[1],
                     client_id=seed["c1"]["id"])
    for key in ["A", "B", "C"]:
        assert seed["sites"][key]["id"] in got, f"site {key} should be present for client c1"
    assert seed["sites"]["D"]["id"] not in got, "client filter did not exclude other client's site D"
    assert seed["sites"]["E"]["id"] not in got


def test_locations_narrow_by_vendor(admin, seed):
    got = _locations(admin, date_from=IN_RANGE[0], date_to=IN_RANGE[1],
                     client_id=seed["c1"]["id"], vendor_id=seed["v1"]["id"])
    for key in ["A", "B"]:
        assert seed["sites"][key]["id"] in got, f"site {key} should be present for c1+v1"
    assert seed["sites"]["C"]["id"] not in got, "vendor filter did not exclude v2 site C"
    assert seed["sites"]["D"]["id"] not in got


def test_locations_sorted_and_no_duplicates(admin, seed):
    r = admin.get(f"{API}/dispatch/invoices/locations",
                  params={"date_from": IN_RANGE[0], "date_to": IN_RANGE[1]}, timeout=30)
    data = r.json()
    ids = [o["id"] for o in data]
    assert len(ids) == len(set(ids)), "duplicate location options returned"
    keys = [(o.get("location") or o.get("city") or o.get("name") or "").lower() for o in data]
    assert keys == sorted(keys), "locations are not sorted by location name"


def test_locations_requires_auth():
    r = requests.get(f"{API}/dispatch/invoices/locations", timeout=30)
    assert r.status_code in (401, 403), f"unauthenticated access returned {r.status_code}"


def test_locations_excludes_cancelled_only_site(admin, seed):
    """A location whose only schedule in the period is Cancelled would produce an
    empty invoice, so it should not be offered as a filter option."""
    site = seed["sites"]["A"]
    # Cancel the single in-range schedule for site A, then re-check options
    sid = seed["sched"]["A"]["id"]
    r = admin.post(f"{API}/dispatch/schedules/{sid}/cancel", timeout=30)
    assert r.status_code == 200, r.text
    try:
        got = _locations(admin, date_from=IN_RANGE[0], date_to=IN_RANGE[1],
                         client_id=seed["c1"]["id"], vendor_id=seed["v1"]["id"])
        assert site["id"] not in got, (
            "location endpoint offers a site whose only schedule is Cancelled — "
            "selecting it produces an empty invoice (endpoint does not filter shift_status=Complete)")
    finally:
        admin.post(f"{API}/dispatch/schedules/{sid}/status",
                   json={"shift_status": "Complete"}, timeout=30)


# ---------- Preview honours location filter ----------

def test_preview_without_location_returns_all_sites(admin, seed):
    body = {
        "client_id": seed["c1"]["id"], "vendor_id": seed["v1"]["id"],
        "invoice_number": f"TEST-PREV-ALL-{TAG}", "invoice_date": "2026-04-01",
        "billing_period_from": IN_RANGE[0], "billing_period_to": IN_RANGE[1],
    }
    r = admin.post(f"{API}/dispatch/invoices/preview", json=body, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    locs = {ln["location"] for ln in j["lines"]}
    assert seed["sites"]["A"]["location"] in locs
    assert seed["sites"]["B"]["location"] in locs
    assert len(j["lines"]) == 2, f"expected 2 lines for c1+v1 in range, got {len(j['lines'])}"
    assert j["total_hours"] == 16.0
    assert j["total_amount"] == 320.0
    assert "Dollar" in j["amount_in_words"]


def test_preview_with_location_filter(admin, seed):
    body = {
        "client_id": seed["c1"]["id"], "vendor_id": seed["v1"]["id"],
        "post_site_id": seed["sites"]["A"]["id"],
        "invoice_number": f"TEST-PREV-LOC-{TAG}", "invoice_date": "2026-04-01",
        "billing_period_from": IN_RANGE[0], "billing_period_to": IN_RANGE[1],
    }
    r = admin.post(f"{API}/dispatch/invoices/preview", json=body, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert len(j["lines"]) == 1, f"location filter should return only 1 line, got {len(j['lines'])}"
    ln = j["lines"][0]
    assert ln["location"] == seed["sites"]["A"]["location"]
    assert ln["shift_date"] == "2026-03-02"
    assert ln["actual_hours"] == 8.0 and ln["rate"] == 20.0 and ln["total_amount"] == 160.0
    assert j["total_hours"] == 8.0 and j["total_amount"] == 160.0
    assert j["post_site_id"] == seed["sites"]["A"]["id"]


def test_preview_location_of_other_client_returns_empty(admin, seed):
    body = {
        "client_id": seed["c1"]["id"], "vendor_id": seed["v1"]["id"],
        "post_site_id": seed["sites"]["D"]["id"],  # site D belongs to c2 schedule
        "invoice_number": f"TEST-PREV-X-{TAG}", "invoice_date": "2026-04-01",
        "billing_period_from": IN_RANGE[0], "billing_period_to": IN_RANGE[1],
    }
    r = admin.post(f"{API}/dispatch/invoices/preview", json=body, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["lines"] == []
    assert j["total_amount"] == 0


# ---------- Save honours location filter ----------

def test_save_invoice_with_location(admin, seed):
    invnum = f"TEST-INV-LOC-{TAG}"
    body = {
        "client_id": seed["c1"]["id"], "vendor_id": seed["v1"]["id"],
        "post_site_id": seed["sites"]["B"]["id"],
        "invoice_number": invnum, "invoice_date": "2026-04-01",
        "billing_period_from": IN_RANGE[0], "billing_period_to": IN_RANGE[1],
        "notes": "iter4",
    }
    r = admin.post(f"{API}/dispatch/invoices", json=body, timeout=30)
    assert r.status_code in (200, 201), r.text
    j = r.json()
    seed["created"]["invoices"].append(j["id"])
    assert "_id" not in j
    assert j["post_site_id"] == seed["sites"]["B"]["id"]
    assert len(j["lines"]) == 1
    assert j["lines"][0]["location"] == seed["sites"]["B"]["location"]
    assert j["schedule_ids"] == [seed["sched"]["B"]["id"]]
    assert j["total_amount"] == 160.0

    # GET to verify persistence
    g = admin.get(f"{API}/dispatch/invoices/{j['id']}", timeout=30)
    assert g.status_code == 200, g.text
    saved = g.json()
    assert saved["post_site_id"] == seed["sites"]["B"]["id"]
    assert len(saved["lines"]) == 1
    assert saved["lines"][0]["location"] == seed["sites"]["B"]["location"]
    assert saved["total_hours"] == 8.0 and saved["total_amount"] == 160.0
    assert saved["invoice_number"] == invnum


def test_save_duplicate_invoice_number_rejected(admin, seed):
    body = {
        "client_id": seed["c1"]["id"], "vendor_id": seed["v1"]["id"],
        "post_site_id": seed["sites"]["B"]["id"],
        "invoice_number": f"TEST-INV-LOC-{TAG}", "invoice_date": "2026-04-01",
        "billing_period_from": IN_RANGE[0], "billing_period_to": IN_RANGE[1],
    }
    r = admin.post(f"{API}/dispatch/invoices", json=body, timeout=30)
    assert r.status_code == 400, r.text
    assert "already exists" in r.json().get("detail", "")


def test_invalid_client_id_returns_4xx(admin, seed):
    body = {
        "client_id": "not-an-objectid", "vendor_id": seed["v1"]["id"],
        "invoice_number": f"TEST-BAD-{TAG}", "invoice_date": "2026-04-01",
        "billing_period_from": IN_RANGE[0], "billing_period_to": IN_RANGE[1],
    }
    r = admin.post(f"{API}/dispatch/invoices/preview", json=body, timeout=30)
    assert r.status_code in (400, 404, 422), f"got {r.status_code}: {r.text[:200]}"


def test_delete_saved_invoice(admin, seed):
    if not seed["created"]["invoices"]:
        pytest.skip("no invoice saved")
    inv_id = seed["created"]["invoices"][0]
    r = admin.delete(f"{API}/dispatch/invoices/{inv_id}", timeout=30)
    assert r.status_code == 200, r.text
    seed["created"]["invoices"].remove(inv_id)
    assert admin.get(f"{API}/dispatch/invoices/{inv_id}", timeout=30).status_code == 404
