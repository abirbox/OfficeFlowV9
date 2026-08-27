"""Iteration 11 tests: Client Portal - Payment (SO) + Wage Report.

Verifies:
 - GET /api/portal/payments returns only Acme officers (Acme total 650, no Globex 9999).
 - GET /api/portal/payments/officer/{acme}  -> 200 with dated entries.
 - GET /api/portal/payments/officer/{globex} -> 404 (isolation).
 - GET /api/portal/payments/report/{pdf,xlsx} -> file streams.
 - GET /api/portal/payments/officer/{acme}/report/{pdf,xlsx} -> file streams.
 - GET /api/portal/wage-report?2026-08-01..2026-08-31 -> Acme 8h/80 wage.
 - GET /api/portal/officers/{acme}/payslip?format=pdf  -> application/pdf.
 - GET /api/portal/officers/{acme}/payslip?format=xlsx -> xlsx.
 - GET /api/portal/officers/{globex}/payslip -> 404.
 - Admin 403 on /api/portal/payments, /portal/wage-report. Client 403 on /api/so-payments/*.
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
def ids(admin):
    r = admin.get(f"{API}/dispatch/officers?limit=500", timeout=30)
    offs = r.json()
    acme = next((o for o in offs if o.get("name") == "Acme Officer"), None)
    globex = next((o for o in offs if o.get("name") == "Globex Officer"), None)
    assert acme and globex, f"Missing seeded officers: acme={acme}, globex={globex}"
    return {"acme_officer_id": acme["id"], "globex_officer_id": globex["id"]}


# -------- Payment SO listing --------
def test_portal_payments_lists_only_acme(client, ids):
    r = client.get(f"{API}/portal/payments", timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    rows = body.get("rows") or []
    names = [row.get("officer_name") for row in rows]
    assert "Acme Officer" in names, f"Acme officer missing: {names}"
    assert "Globex Officer" not in names, f"Globex leaked: {names}"
    acme_row = next(r for r in rows if r["officer_name"] == "Acme Officer")
    assert round(float(acme_row.get("total") or 0), 2) == 650.00, acme_row
    # Grand total should equal 650 (only Acme)
    totals = body.get("totals") or {}
    assert round(float(totals.get("grand_total") or 0), 2) == 650.00, totals


def test_portal_payments_officer_detail_acme(client, ids):
    r = client.get(f"{API}/portal/payments/officer/{ids['acme_officer_id']}", timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("officer", {}).get("name") == "Acme Officer"
    records = body.get("records") or []
    assert len(records) >= 1


def test_portal_payments_officer_detail_globex_404(client, ids):
    r = client.get(f"{API}/portal/payments/officer/{ids['globex_officer_id']}", timeout=30)
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


# -------- Payment SO reports --------
def test_portal_payments_report_pdf(client):
    r = client.get(f"{API}/portal/payments/report/pdf", timeout=60)
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content[:4] == b"%PDF"


def test_portal_payments_report_xlsx(client):
    r = client.get(f"{API}/portal/payments/report/xlsx", timeout=60)
    assert r.status_code == 200, r.text
    ct = r.headers.get("content-type", "")
    assert "spreadsheetml" in ct or "excel" in ct, ct
    assert r.content[:2] == b"PK"


def test_portal_payments_officer_report_pdf(client, ids):
    r = client.get(f"{API}/portal/payments/officer/{ids['acme_officer_id']}/report/pdf", timeout=60)
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"


def test_portal_payments_officer_report_globex_404(client, ids):
    r = client.get(f"{API}/portal/payments/officer/{ids['globex_officer_id']}/report/pdf", timeout=30)
    assert r.status_code == 404


# -------- Wage Report --------
def test_portal_wage_report_aug_2026(client, ids):
    r = client.get(f"{API}/portal/wage-report", params={"date_from": "2026-08-01", "date_to": "2026-08-31"}, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    items = body.get("items") or []
    names = [i.get("officer_name") for i in items]
    assert "Acme Officer" in names, f"Acme missing: {names}"
    assert "Globex Officer" not in names, f"Globex leaked: {names}"
    acme = next(i for i in items if i["officer_name"] == "Acme Officer")
    assert acme.get("total_hours") == 8 or acme.get("total_hours") == 8.0, acme
    assert round(float(acme.get("wage") or 0), 2) == 80.00, acme


def test_portal_wage_report_defaults_to_current_month(client):
    r = client.get(f"{API}/portal/wage-report", timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("date_from") and body.get("date_to")
    # both should be same month
    assert body["date_from"][:7] == body["date_to"][:7]


# -------- Payslip download --------
def test_portal_payslip_pdf_acme(client, ids):
    r = client.get(f"{API}/portal/officers/{ids['acme_officer_id']}/payslip",
                   params={"date_from": "2026-08-01", "date_to": "2026-08-31", "format": "pdf"}, timeout=60)
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content[:4] == b"%PDF"


def test_portal_payslip_xlsx_acme(client, ids):
    r = client.get(f"{API}/portal/officers/{ids['acme_officer_id']}/payslip",
                   params={"date_from": "2026-08-01", "date_to": "2026-08-31", "format": "xlsx"}, timeout=60)
    assert r.status_code == 200, r.text
    assert r.content[:2] == b"PK"


def test_portal_payslip_globex_404(client, ids):
    r = client.get(f"{API}/portal/officers/{ids['globex_officer_id']}/payslip",
                   params={"format": "pdf"}, timeout=30)
    assert r.status_code == 404


# -------- Role gates --------
def test_admin_forbidden_from_payments_and_wage(admin):
    for path in ("/portal/payments", "/portal/wage-report", "/portal/payments/report/pdf"):
        r = admin.get(f"{API}{path}", timeout=30)
        assert r.status_code == 403, f"{path}: expected 403 got {r.status_code}"


def test_client_forbidden_from_so_payments(client):
    r = client.get(f"{API}/so-payments/clients", timeout=30)
    assert r.status_code == 403, f"expected 403 got {r.status_code}"
