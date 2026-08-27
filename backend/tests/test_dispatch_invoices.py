"""Iter32 regression tests for Dispatch → Invoices feature.

Covers:
- preview (with real Complete schedules) — lines, totals, in-words
- preview zero-line case
- save invoice, echo id + invoice_number + total_amount, persist schedule_ids
- duplicate invoice_number → 400
- list invoices
- download saved PDF → application/pdf, non-empty
- preview/pdf without saving
- RBAC — employee blocked (403) from every endpoint
- delete invoice hard-deletes
"""
import os
import io
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
ADMIN = {"email": "admin@example.com", "password": "admin123"}
EMP = {"email": "employee@officeflow.com", "password": "Employee@123"}


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def employee():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=EMP, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"employee login failed: {r.status_code} {r.text}")
    return s


@pytest.fixture(scope="module")
def real_triple(admin):
    """Find a (client_id, vendor_id, from, to) combination that has >=1
    Complete schedule with actual_duty_hours + billing_rate > 0."""
    r = admin.get(f"{BASE}/api/dispatch/schedules", timeout=60)
    assert r.status_code == 200
    data = r.json()
    items = data["items"] if isinstance(data, dict) else data
    complete = [s for s in items if s.get("shift_status") == "Complete"
                and s.get("client_id") and s.get("vendor_id")
                and (s.get("actual_duty_hours") or s.get("duty_hours"))
                and s.get("billing_rate")]
    if not complete:
        pytest.skip("no Complete schedule with billing data available for invoice test")
    # Pick first schedule and use its client/vendor
    s0 = complete[0]
    cid, vid = s0["client_id"], s0["vendor_id"]
    matches = [s for s in complete if s["client_id"] == cid and s["vendor_id"] == vid]
    dates = sorted(s["date"] for s in matches)
    return {"client_id": cid, "vendor_id": vid,
            "from": dates[0], "to": dates[-1], "matches": matches}


@pytest.fixture(scope="module")
def any_client_vendor(admin):
    """Any client + vendor id — used for zero-line preview cases."""
    c = admin.get(f"{BASE}/api/dispatch/clients", timeout=30).json()
    v = admin.get(f"{BASE}/api/dispatch/vendors", timeout=30).json()
    if not c or not v:
        pytest.skip("no client/vendor seeded")
    return c[0]["id"], v[0]["id"]


# ---------- Preview ----------

def test_preview_real_data(admin, real_triple):
    body = {
        "client_id": real_triple["client_id"],
        "vendor_id": real_triple["vendor_id"],
        "invoice_number": f"TEST-PREV-{uuid.uuid4().hex[:6]}",
        "invoice_date": "2026-01-15",
        "billing_period_from": real_triple["from"],
        "billing_period_to": real_triple["to"],
        "notes": "prev",
    }
    r = admin.post(f"{BASE}/api/dispatch/invoices/preview", json=body, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert isinstance(j["lines"], list) and len(j["lines"]) >= 1
    assert isinstance(j["total_hours"], (int, float)) and j["total_hours"] > 0
    assert isinstance(j["total_amount"], (int, float)) and j["total_amount"] > 0
    assert isinstance(j["amount_in_words"], str) and "Dollar" in j["amount_in_words"]
    # Rate*hours = total for each line
    for ln in j["lines"]:
        assert ln["rate"] is not None
        assert abs(ln["actual_hours"] * ln["rate"] - ln["total_amount"]) < 0.01


def test_preview_zero_lines(admin, any_client_vendor):
    cid, vid = any_client_vendor
    body = {
        "client_id": cid, "vendor_id": vid,
        "invoice_number": f"TEST-ZERO-{uuid.uuid4().hex[:6]}",
        "invoice_date": "2026-01-15",
        # dates far in the past so no matches
        "billing_period_from": "1990-01-01",
        "billing_period_to": "1990-01-02",
    }
    r = admin.post(f"{BASE}/api/dispatch/invoices/preview", json=body, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["lines"] == []
    assert j["total_hours"] == 0
    assert j["total_amount"] == 0


# ---------- Save ----------

_saved = {}


def test_save_invoice(admin, real_triple):
    invnum = f"TEST-INV-{uuid.uuid4().hex[:8]}"
    body = {
        "client_id": real_triple["client_id"],
        "vendor_id": real_triple["vendor_id"],
        "invoice_number": invnum,
        "invoice_date": "2026-01-15",
        "billing_period_from": real_triple["from"],
        "billing_period_to": real_triple["to"],
    }
    r = admin.post(f"{BASE}/api/dispatch/invoices", json=body, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["id"] and j["invoice_number"] == invnum
    assert isinstance(j["total_amount"], (int, float)) and j["total_amount"] > 0
    assert isinstance(j["schedule_ids"], list) and len(j["schedule_ids"]) >= 1
    _saved["id"] = j["id"]
    _saved["number"] = invnum
    _saved["body"] = body


def test_duplicate_invoice_number(admin):
    body = dict(_saved["body"])
    r = admin.post(f"{BASE}/api/dispatch/invoices", json=body, timeout=30)
    assert r.status_code == 400, r.text
    detail = r.json().get("detail", "")
    assert "already exists" in detail and _saved["number"] in detail


def test_list_invoices(admin):
    r = admin.get(f"{BASE}/api/dispatch/invoices", timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert "items" in j and "total" in j
    assert any(x["id"] == _saved["id"] for x in j["items"])


def test_download_saved_pdf(admin):
    r = admin.get(f"{BASE}/api/dispatch/invoices/{_saved['id']}/pdf", timeout=30)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert len(r.content) > 500
    assert r.content[:4] == b"%PDF"


def test_preview_pdf_no_save(admin, real_triple):
    body = {
        "client_id": real_triple["client_id"],
        "vendor_id": real_triple["vendor_id"],
        "invoice_number": f"TEST-PREVPDF-{uuid.uuid4().hex[:6]}",
        "invoice_date": "2026-01-15",
        "billing_period_from": real_triple["from"],
        "billing_period_to": real_triple["to"],
    }
    r = admin.post(f"{BASE}/api/dispatch/invoices/preview/pdf", json=body, timeout=30)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content[:4] == b"%PDF"
    # Confirm not persisted
    lst = admin.get(f"{BASE}/api/dispatch/invoices", timeout=30).json()
    assert not any(x["invoice_number"] == body["invoice_number"] for x in lst["items"])


# ---------- RBAC ----------

def test_employee_blocked_everywhere(employee, real_triple):
    body = {
        "client_id": real_triple["client_id"],
        "vendor_id": real_triple["vendor_id"],
        "invoice_number": "TEST-EMP",
        "invoice_date": "2026-01-15",
        "billing_period_from": real_triple["from"],
        "billing_period_to": real_triple["to"],
    }
    checks = [
        ("GET", "/api/dispatch/invoices", None),
        ("POST", "/api/dispatch/invoices/preview", body),
        ("POST", "/api/dispatch/invoices", body),
        ("POST", "/api/dispatch/invoices/preview/pdf", body),
        ("GET", f"/api/dispatch/invoices/{_saved['id']}", None),
        ("GET", f"/api/dispatch/invoices/{_saved['id']}/pdf", None),
        ("DELETE", f"/api/dispatch/invoices/{_saved['id']}", None),
    ]
    failures = []
    for method, path, payload in checks:
        if method == "GET":
            r = employee.get(f"{BASE}{path}", timeout=20)
        elif method == "POST":
            r = employee.post(f"{BASE}{path}", json=payload, timeout=20)
        else:
            r = employee.delete(f"{BASE}{path}", timeout=20)
        if r.status_code != 403:
            failures.append(f"{method} {path} → {r.status_code}")
    assert not failures, f"employee not properly blocked: {failures}"


# ---------- Delete ----------

def test_delete_invoice(admin):
    r = admin.delete(f"{BASE}/api/dispatch/invoices/{_saved['id']}", timeout=30)
    assert r.status_code == 200, r.text
    # Confirm gone
    r2 = admin.get(f"{BASE}/api/dispatch/invoices/{_saved['id']}", timeout=15)
    assert r2.status_code == 404
