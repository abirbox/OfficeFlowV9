"""Iteration 5 — regression tests for dispatch report / payslip / invoice PDF exports.

Focus: build_officer_payslip_pdf was returning None (0-byte PDF) because it was
missing doc.build(story) + return buf.getvalue(). Verify the officer payslip PDF
is now a valid non-empty PDF and that no other export regressed.
"""
import os
import datetime as dt

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@example.com", "password": "admin123"}


# ---- fixtures --------------------------------------------------------------
@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=60)
    if r.status_code != 200:
        pytest.fail(f"Admin login failed {r.status_code}: {r.text[:300]}")
    return s


@pytest.fixture(scope="module")
def dates():
    today = dt.date.today()
    return {"from": (today - dt.timedelta(days=60)).isoformat(), "to": today.isoformat()}


@pytest.fixture(scope="module")
def officer_and_client(client):
    ro = client.get(f"{API}/dispatch/officers", timeout=60)
    assert ro.status_code == 200, ro.text[:300]
    officers = ro.json()
    officers = officers.get("items", officers) if isinstance(officers, dict) else officers
    assert officers, "No officers seeded — cannot test payslip PDF"

    rc = client.get(f"{API}/dispatch/clients", timeout=60)
    assert rc.status_code == 200, rc.text[:300]
    clients = rc.json()
    clients = clients.get("items", clients) if isinstance(clients, dict) else clients
    assert clients, "No clients seeded"
    return {"officer_id": officers[0]["id"], "client_id": clients[0]["id"]}


def assert_valid_pdf(resp, label):
    assert resp.status_code == 200, f"{label}: HTTP {resp.status_code} {resp.text[:300]}"
    ct = resp.headers.get("content-type", "")
    assert "application/pdf" in ct, f"{label}: content-type={ct}"
    body = resp.content
    assert len(body) > 0, f"{label}: 0-byte PDF body"
    assert body[:5] == b"%PDF-", f"{label}: bad magic bytes {body[:10]!r}"
    assert b"%%EOF" in body[-2048:], f"{label}: missing %%EOF trailer (truncated PDF)"
    return len(body)


# ---- Auth ------------------------------------------------------------------
class TestAuth:
    def test_login_and_me(self, client):
        r = client.get(f"{API}/auth/me", timeout=60)
        assert r.status_code == 200, r.text[:300]
        me = r.json()
        assert me.get("email") == ADMIN["email"]
        assert "_id" not in me


# ---- Officer payslip PDF (the fix) ----------------------------------------
class TestOfficerPayslipPdf:
    def test_payslip_pdf_explicit_template(self, client, officer_and_client, dates):
        p = {
            "entity_type": "officer", "entity_id": officer_and_client["officer_id"],
            "client_id": officer_and_client["client_id"],
            "date_from": dates["from"], "date_to": dates["to"],
            "format": "pdf", "template": "payslip",
        }
        r = client.get(f"{API}/dispatch/reports/export/entity-detail", params=p, timeout=120)
        size = assert_valid_pdf(r, "officer payslip (template=payslip)")
        print(f"payslip explicit template size={size}")

    def test_payslip_pdf_auto_via_client_id(self, client, officer_and_client, dates):
        """template omitted but client_id supplied -> payslip layout auto-activates."""
        p = {
            "entity_type": "officer", "entity_id": officer_and_client["officer_id"],
            "client_id": officer_and_client["client_id"],
            "date_from": dates["from"], "date_to": dates["to"], "format": "pdf",
        }
        r = client.get(f"{API}/dispatch/reports/export/entity-detail", params=p, timeout=120)
        size = assert_valid_pdf(r, "officer payslip (auto)")
        print(f"payslip auto size={size}")

    def test_entity_detail_pdf_no_client(self, client, officer_and_client, dates):
        """Generic entity-detail PDF path (no client_id) must still work."""
        p = {
            "entity_type": "officer", "entity_id": officer_and_client["officer_id"],
            "date_from": dates["from"], "date_to": dates["to"], "format": "pdf",
        }
        r = client.get(f"{API}/dispatch/reports/export/entity-detail", params=p, timeout=120)
        assert_valid_pdf(r, "entity-detail pdf no client")

    def test_entity_detail_csv(self, client, officer_and_client, dates):
        p = {
            "entity_type": "officer", "entity_id": officer_and_client["officer_id"],
            "client_id": officer_and_client["client_id"],
            "date_from": dates["from"], "date_to": dates["to"], "format": "csv",
        }
        r = client.get(f"{API}/dispatch/reports/export/entity-detail", params=p, timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert "text/csv" in r.headers.get("content-type", "")
        assert len(r.content) > 0

    def test_invalid_format_rejected(self, client, officer_and_client, dates):
        p = {
            "entity_type": "officer", "entity_id": officer_and_client["officer_id"],
            "date_from": dates["from"], "date_to": dates["to"], "format": "xlsx",
        }
        r = client.get(f"{API}/dispatch/reports/export/entity-detail", params=p, timeout=60)
        assert r.status_code == 400, f"expected 400 got {r.status_code}"

    def test_requires_auth(self, officer_and_client, dates):
        anon = requests.Session()
        p = {
            "entity_type": "officer", "entity_id": officer_and_client["officer_id"],
            "date_from": dates["from"], "date_to": dates["to"], "format": "pdf",
        }
        r = anon.get(f"{API}/dispatch/reports/export/entity-detail", params=p, timeout=60)
        assert r.status_code in (401, 403), f"unauthenticated export returned {r.status_code}"


# ---- Aggregate report PDF exports (regression) ----------------------------
class TestAggregateExports:
    @pytest.mark.parametrize("rtype", ["schedules", "by-officer", "by-post-site", "by-client", "by-vendor"])
    def test_aggregate_pdf(self, client, dates, rtype):
        p = {"type": rtype, "format": "pdf", "date_from": dates["from"], "date_to": dates["to"]}
        r = client.get(f"{API}/dispatch/reports/export", params=p, timeout=120)
        size = assert_valid_pdf(r, f"aggregate pdf {rtype}")
        print(f"{rtype} pdf size={size}")

    @pytest.mark.parametrize("rtype", ["schedules", "by-officer", "by-client"])
    def test_aggregate_csv(self, client, dates, rtype):
        p = {"type": rtype, "format": "csv", "date_from": dates["from"], "date_to": dates["to"]}
        r = client.get(f"{API}/dispatch/reports/export", params=p, timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert "text/csv" in r.headers.get("content-type", "")

    def test_unknown_report_type(self, client, dates):
        p = {"type": "by-nothing", "format": "pdf", "date_from": dates["from"], "date_to": dates["to"]}
        r = client.get(f"{API}/dispatch/reports/export", params=p, timeout=60)
        assert r.status_code == 400


# ---- Invoice PDF (same module hosts build_invoice_pdf) --------------------
class TestInvoicePdf:
    def test_preview_pdf(self, client, dates):
        rv = client.get(f"{API}/dispatch/vendors", timeout=60)
        rc = client.get(f"{API}/dispatch/clients", timeout=60)
        assert rv.status_code == 200 and rc.status_code == 200
        vendors = rv.json();  vendors = vendors.get("items", vendors) if isinstance(vendors, dict) else vendors
        clients = rc.json();  clients = clients.get("items", clients) if isinstance(clients, dict) else clients
        if not vendors or not clients:
            pytest.skip("No vendors/clients seeded")
        payload = {
            "client_id": clients[0]["id"], "vendor_id": vendors[0]["id"],
            "invoice_number": "TEST_ITER5_001", "invoice_date": dates["to"],
            "billing_period_from": dates["from"], "billing_period_to": dates["to"],
        }
        r = client.post(f"{API}/dispatch/invoices/preview/pdf", json=payload, timeout=120)
        size = assert_valid_pdf(r, "invoice preview pdf")
        print(f"invoice preview pdf size={size}")

    def test_saved_invoice_pdf(self, client, dates):
        r = client.get(f"{API}/dispatch/invoices", timeout=60)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        if not items:
            pytest.skip("No saved invoices to export")
        inv_id = items[0]["id"]
        rp = client.get(f"{API}/dispatch/invoices/{inv_id}/pdf", timeout=120)
        assert_valid_pdf(rp, f"saved invoice pdf {inv_id}")
