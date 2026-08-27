"""Iteration 6 backend tests — three new invoice features.

Scope (from review request):
- Auto invoice number: GET /dispatch/invoices/next-number (>=5250, increments,
  parses prefixed values like 'INV-5300' / '#5330')
- Client accent_color round-trip (POST/PUT/GET) + presence in client_snapshot
- Invoice PDF generation honouring accent_color (valid, missing, invalid)
- Multi-select locations: preview + save with post_site_ids (and legacy compat)
"""
import os
import uuid

import pytest
import requests


def _base():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


BASE = _base()
API = f"{BASE}/api"
ADMIN = {"email": "admin@example.com", "password": "admin123"}
TAG = uuid.uuid4().hex[:6]
PERIOD = ("2026-04-01", "2026-04-30")


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
    assert r.json()["email"] == ADMIN["email"]


# ---------- Seed data: client(+accent), vendor, 3 sites, 3 schedules ----------

@pytest.fixture(scope="module")
def seed(admin):
    created = {"clients": [], "vendors": [], "officers": [], "post_sites": [],
               "schedules": [], "invoices": []}

    def post(path, body):
        r = admin.post(f"{API}{path}", json=body, timeout=30)
        assert r.status_code in (200, 201), f"{path} -> {r.status_code} {r.text[:300]}"
        return r.json()

    client = post("/dispatch/clients", {"name": f"TEST_ACC_C_{TAG}", "code": f"TAC{TAG}",
                                        "accent_color": "#3B82F6"})
    plain_client = post("/dispatch/clients", {"name": f"TEST_NOACC_C_{TAG}", "code": f"TNC{TAG}"})
    vendor = post("/dispatch/vendors", {"name": f"TEST_ACC_V_{TAG}", "code": f"TAV{TAG}"})
    created["clients"] += [client["id"], plain_client["id"]]
    created["vendors"].append(vendor["id"])

    off = post("/dispatch/officers", {"name": f"TEST_OFF6_{TAG}", "contact_number": "0170000006",
                                      "status": "active"})
    created["officers"].append(off["id"])

    sites = {}
    for key in ["X", "Y", "Z"]:
        p = post("/dispatch/post-sites", {"post_pin": f"T6{key}{TAG}",
                                          "name": f"TEST_SITE6_{key}_{TAG}",
                                          "location": f"TESTLOC6_{key}_{TAG}",
                                          "city": "Testville", "status": "active"})
        sites[key] = p
        created["post_sites"].append(p["id"])

    def schedule(date, site, cl=client):
        s = post("/dispatch/schedules", {
            "date": date, "shift_type": "Morning", "start_time": "08:00", "end_time": "16:00",
            "client_id": cl["id"], "vendor_id": vendor["id"],
            "post_site_id": sites[site]["id"], "officer_id": off["id"],
            "work_order_number": f"WO6-{TAG}-{site}", "duty_rate": 10.0, "billing_rate": 25.0,
        })
        created["schedules"].append(s["id"])
        r = admin.post(f"{API}/dispatch/schedules/{s['id']}/status",
                       json={"shift_status": "Complete"}, timeout=30)
        assert r.status_code == 200, r.text
        return s

    sx = schedule("2026-04-02", "X")
    sy = schedule("2026-04-03", "Y")
    sz = schedule("2026-04-04", "Z")

    yield {"client": client, "plain_client": plain_client, "vendor": vendor, "sites": sites,
           "sched": {"X": sx, "Y": sy, "Z": sz}, "created": created}

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
        admire = admin.delete(f"{API}/dispatch/vendors/{vid}", timeout=30)
        assert admire.status_code in (200, 204, 404)


def _next_number(admin):
    r = admin.get(f"{API}/dispatch/invoices/next-number", timeout=30)
    assert r.status_code == 200, f"next-number -> {r.status_code} {r.text[:300]}"
    data = r.json()
    assert "invoice_number" in data, data
    assert isinstance(data["invoice_number"], str), data
    assert data["invoice_number"].isdigit(), data
    return int(data["invoice_number"])


def _create_invoice(admin, seed, number, site_ids=None, legacy_site=None, client=None):
    body = {
        "client_id": (client or seed["client"])["id"],
        "vendor_id": seed["vendor"]["id"],
        "invoice_number": str(number),
        "invoice_date": "2026-05-01",
        "billing_period_from": PERIOD[0],
        "billing_period_to": PERIOD[1],
    }
    if site_ids is not None:
        body["post_site_ids"] = site_ids
    if legacy_site is not None:
        body["post_site_id"] = legacy_site
    r = admin.post(f"{API}/dispatch/invoices", json=body, timeout=60)
    assert r.status_code in (200, 201), f"create invoice -> {r.status_code} {r.text[:400]}"
    inv = r.json()
    seed["created"]["invoices"].append(inv["id"])
    return inv


# ---------- Feature 2: auto invoice number ----------

class TestAutoInvoiceNumber:
    def test_next_number_min_start(self, admin):
        assert _next_number(admin) >= 5250

    def test_next_number_increments_after_save(self, admin, seed):
        n = _next_number(admin)
        _create_invoice(admin, seed, n, site_ids=[])
        assert _next_number(admin) == n + 1

    def test_next_number_parses_prefixed_values(self, admin, seed):
        n = _next_number(admin)
        big = n + 50
        _create_invoice(admin, seed, f"INV-{big}", site_ids=[])
        got = _next_number(admin)
        assert got == big + 1, f"expected {big + 1} after 'INV-{big}', got {got}"

    def test_next_number_parses_hash_prefixed(self, admin, seed):
        n = _next_number(admin)
        big = n + 30
        _create_invoice(admin, seed, f"#{big}", site_ids=[])
        got = _next_number(admin)
        assert got == big + 1, f"expected {big + 1} after '#{big}', got {got}"

    def test_duplicate_invoice_number_rejected(self, admin, seed):
        n = _next_number(admin)
        _create_invoice(admin, seed, n, site_ids=[])
        r = admin.post(f"{API}/dispatch/invoices", json={
            "client_id": seed["client"]["id"], "vendor_id": seed["vendor"]["id"],
            "invoice_number": str(n), "invoice_date": "2026-05-01",
            "billing_period_from": PERIOD[0], "billing_period_to": PERIOD[1],
        }, timeout=60)
        assert r.status_code == 400, f"expected 400 duplicate, got {r.status_code}"

    def test_next_number_requires_auth(self):
        r = requests.get(f"{API}/dispatch/invoices/next-number", timeout=30)
        assert r.status_code in (401, 403), r.status_code


# ---------- Feature 1: client accent_color ----------

class TestClientAccentColor:
    def test_accent_color_on_create_and_get(self, admin, seed):
        r = admin.get(f"{API}/dispatch/clients/{seed['client']['id']}", timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("accent_color") == "#3B82F6"

    def test_accent_color_update_round_trip(self, admin, seed):
        r = admin.put(f"{API}/dispatch/clients/{seed['client']['id']}",
                      json={"accent_color": "#10B981"}, timeout=30)
        assert r.status_code == 200, r.text
        r2 = admin.get(f"{API}/dispatch/clients/{seed['client']['id']}", timeout=30)
        assert r2.json().get("accent_color") == "#10B981"
        # restore
        admin.put(f"{API}/dispatch/clients/{seed['client']['id']}",
                  json={"accent_color": "#3B82F6"}, timeout=30)

    def test_accent_color_in_preview_client(self, admin, seed):
        r = admin.post(f"{API}/dispatch/invoices/preview", json={
            "client_id": seed["client"]["id"], "vendor_id": seed["vendor"]["id"],
            "invoice_number": "PREVIEW-ACC", "invoice_date": "2026-05-01",
            "billing_period_from": PERIOD[0], "billing_period_to": PERIOD[1],
        }, timeout=60)
        assert r.status_code == 200, r.text
        assert r.json()["client"].get("accent_color") == "#3B82F6"

    def test_accent_color_in_saved_client_snapshot(self, admin, seed):
        n = _next_number(admin)
        inv = _create_invoice(admin, seed, n, site_ids=[])
        r = admin.get(f"{API}/dispatch/invoices/{inv['id']}", timeout=30)
        assert r.status_code == 200, r.text
        snap = r.json().get("client_snapshot") or {}
        assert snap.get("accent_color") == "#3B82F6", snap


# ---------- PDF with accent colour ----------

def _assert_pdf(resp):
    assert resp.status_code == 200, f"{resp.status_code} {resp.text[:300]}"
    assert "application/pdf" in resp.headers.get("content-type", "")
    assert len(resp.content) > 1000, len(resp.content)
    assert resp.content.startswith(b"%PDF-")


class TestInvoicePdfAccent:
    def test_preview_pdf_with_accent(self, admin, seed):
        r = admin.post(f"{API}/dispatch/invoices/preview/pdf", json={
            "client_id": seed["client"]["id"], "vendor_id": seed["vendor"]["id"],
            "invoice_number": "5250", "invoice_date": "2026-05-01",
            "billing_period_from": PERIOD[0], "billing_period_to": PERIOD[1],
        }, timeout=90)
        _assert_pdf(r)

    def test_preview_pdf_without_accent_defaults_gold(self, admin, seed):
        r = admin.post(f"{API}/dispatch/invoices/preview/pdf", json={
            "client_id": seed["plain_client"]["id"], "vendor_id": seed["vendor"]["id"],
            "invoice_number": "5251", "invoice_date": "2026-05-01",
            "billing_period_from": PERIOD[0], "billing_period_to": PERIOD[1],
        }, timeout=90)
        _assert_pdf(r)

    def test_preview_pdf_with_invalid_accent(self, admin, seed):
        cid = seed["plain_client"]["id"]
        assert admin.put(f"{API}/dispatch/clients/{cid}",
                         json={"accent_color": "not-a-color"}, timeout=30).status_code == 200
        r = admin.post(f"{API}/dispatch/invoices/preview/pdf", json={
            "client_id": cid, "vendor_id": seed["vendor"]["id"],
            "invoice_number": "5252", "invoice_date": "2026-05-01",
            "billing_period_from": PERIOD[0], "billing_period_to": PERIOD[1],
        }, timeout=90)
        _assert_pdf(r)
        admin.put(f"{API}/dispatch/clients/{cid}", json={"accent_color": None}, timeout=30)

    def test_saved_invoice_pdf_with_accent(self, admin, seed):
        n = _next_number(admin)
        inv = _create_invoice(admin, seed, n, site_ids=[])
        r = admin.get(f"{API}/dispatch/invoices/{inv['id']}/pdf", timeout=90)
        _assert_pdf(r)


# ---------- Feature 3: multi-select locations ----------

class TestMultiSelectLocations:
    def test_preview_two_of_three_locations(self, admin, seed):
        ids = [seed["sites"]["X"]["id"], seed["sites"]["Y"]["id"]]
        r = admin.post(f"{API}/dispatch/invoices/preview", json={
            "client_id": seed["client"]["id"], "vendor_id": seed["vendor"]["id"],
            "post_site_ids": ids,
            "invoice_number": "PREVIEW-MULTI", "invoice_date": "2026-05-01",
            "billing_period_from": PERIOD[0], "billing_period_to": PERIOD[1],
        }, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        got = {ln["schedule_id"] for ln in data["lines"]}
        assert got == {seed["sched"]["X"]["id"], seed["sched"]["Y"]["id"]}, got
        assert set(data.get("post_site_ids") or []) == set(ids)
        assert data["total_hours"] == 16.0, data["total_hours"]

    def test_preview_single_id_in_list(self, admin, seed):
        r = admin.post(f"{API}/dispatch/invoices/preview", json={
            "client_id": seed["client"]["id"], "vendor_id": seed["vendor"]["id"],
            "post_site_ids": [seed["sites"]["Z"]["id"]],
            "invoice_number": "PREVIEW-ONE", "invoice_date": "2026-05-01",
            "billing_period_from": PERIOD[0], "billing_period_to": PERIOD[1],
        }, timeout=60)
        assert r.status_code == 200, r.text
        got = {ln["schedule_id"] for ln in r.json()["lines"]}
        assert got == {seed["sched"]["Z"]["id"]}, got

    def test_preview_empty_list_includes_all(self, admin, seed):
        r = admin.post(f"{API}/dispatch/invoices/preview", json={
            "client_id": seed["client"]["id"], "vendor_id": seed["vendor"]["id"],
            "post_site_ids": [],
            "invoice_number": "PREVIEW-ALL", "invoice_date": "2026-05-01",
            "billing_period_from": PERIOD[0], "billing_period_to": PERIOD[1],
        }, timeout=60)
        assert r.status_code == 200, r.text
        got = {ln["schedule_id"] for ln in r.json()["lines"]}
        assert got == {seed["sched"][k]["id"] for k in "XYZ"}, got

    def test_preview_omitted_includes_all(self, admin, seed):
        r = admin.post(f"{API}/dispatch/invoices/preview", json={
            "client_id": seed["client"]["id"], "vendor_id": seed["vendor"]["id"],
            "invoice_number": "PREVIEW-NONE", "invoice_date": "2026-05-01",
            "billing_period_from": PERIOD[0], "billing_period_to": PERIOD[1],
        }, timeout=60)
        assert r.status_code == 200, r.text
        got = {ln["schedule_id"] for ln in r.json()["lines"]}
        assert got == {seed["sched"][k]["id"] for k in "XYZ"}, got

    def test_preview_legacy_single_field(self, admin, seed):
        r = admin.post(f"{API}/dispatch/invoices/preview", json={
            "client_id": seed["client"]["id"], "vendor_id": seed["vendor"]["id"],
            "post_site_id": seed["sites"]["Y"]["id"],
            "invoice_number": "PREVIEW-LEGACY", "invoice_date": "2026-05-01",
            "billing_period_from": PERIOD[0], "billing_period_to": PERIOD[1],
        }, timeout=60)
        assert r.status_code == 200, r.text
        got = {ln["schedule_id"] for ln in r.json()["lines"]}
        assert got == {seed["sched"]["Y"]["id"]}, got

    def test_save_with_multi_locations(self, admin, seed):
        n = _next_number(admin)
        ids = [seed["sites"]["X"]["id"], seed["sites"]["Z"]["id"]]
        inv = _create_invoice(admin, seed, n, site_ids=ids)
        assert set(inv.get("post_site_ids") or []) == set(ids)
        assert inv.get("post_site_id") is None
        assert set(inv["schedule_ids"]) == {seed["sched"]["X"]["id"], seed["sched"]["Z"]["id"]}
        # verify persistence
        r = admin.get(f"{API}/dispatch/invoices/{inv['id']}", timeout=30)
        assert r.status_code == 200, r.text
        saved = r.json()
        assert set(saved["post_site_ids"]) == set(ids)
        assert set(saved["schedule_ids"]) == {seed["sched"]["X"]["id"], seed["sched"]["Z"]["id"]}
        assert saved["total_hours"] == 16.0
        assert saved["total_amount"] == 400.0
        assert "_id" not in saved

    def test_save_with_legacy_single_location(self, admin, seed):
        n = _next_number(admin)
        inv = _create_invoice(admin, seed, n, legacy_site=seed["sites"]["Y"]["id"])
        assert inv["post_site_id"] == seed["sites"]["Y"]["id"]
        assert inv["post_site_ids"] == [seed["sites"]["Y"]["id"]]
        assert set(inv["schedule_ids"]) == {seed["sched"]["Y"]["id"]}

    def test_locations_endpoint_lists_seeded_sites(self, admin, seed):
        r = admin.get(f"{API}/dispatch/invoices/locations", params={
            "client_id": seed["client"]["id"], "vendor_id": seed["vendor"]["id"],
            "date_from": PERIOD[0], "date_to": PERIOD[1]}, timeout=30)
        assert r.status_code == 200, r.text
        ids = {o["id"] for o in r.json()}
        assert ids == {seed["sites"][k]["id"] for k in "XYZ"}, ids

    def test_delete_invoice(self, admin, seed):
        n = _next_number(admin)
        inv = _create_invoice(admin, seed, n, site_ids=[])
        r = admin.delete(f"{API}/dispatch/invoices/{inv['id']}", timeout=30)
        assert r.status_code == 200, r.text
        assert admin.get(f"{API}/dispatch/invoices/{inv['id']}", timeout=30).status_code == 404
        seed["created"]["invoices"].remove(inv["id"])
