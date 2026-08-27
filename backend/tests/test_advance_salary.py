"""Backend tests for the new Advance Salary payslip system (dispatch module)."""
import os
import re
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def test_credentials():
    p = Path("/app/memory/test_credentials.md")
    if not p.exists():
        pytest.skip("missing test_credentials.md")
    c = p.read_text(encoding="utf-8")
    e = re.search(r'(?im)^\s*(?:[-*]\s*)?(?:\*\*)?email(?:\*\*)?\s*:\s*`?([^`\s]+)', c)
    pw = re.search(r'(?im)^\s*(?:[-*]\s*)?(?:\*\*)?password(?:\*\*)?\s*:\s*`?([^`\s]+)', c)
    if not e or not pw:
        pytest.skip("no creds")
    return {"email": e.group(1), "password": pw.group(1)}


@pytest.fixture(scope="session")
def client(test_credentials):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=test_credentials, timeout=60)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    elif not s.cookies:
        pytest.fail(f"no token/cookie in login response: {list(data.keys())}")
    return s


@pytest.fixture(scope="session")
def ids(client):
    """Resolve officer 'Abir Vai' and client 'Arseas' ids."""
    ro = client.get(f"{API}/dispatch/officers", params={"limit": 200}, timeout=60)
    assert ro.status_code == 200, ro.text[:300]
    ojson = ro.json()
    officers = ojson if isinstance(ojson, list) else ojson.get("items", [])
    officer = next((o for o in officers if "abir" in str(o.get("name", "")).lower()), None)
    rc = client.get(f"{API}/dispatch/clients", params={"limit": 200}, timeout=60)
    assert rc.status_code == 200, rc.text[:300]
    cjson = rc.json()
    clients = cjson if isinstance(cjson, list) else cjson.get("items", [])
    cl = next((c for c in clients if "arseas" in str(c.get("name", "")).lower()), None)
    if not officer or not cl:
        pytest.fail(f"seed data missing: officer={bool(officer)} client={bool(cl)}")
    return {"officer_id": officer.get("id"), "client_id": cl.get("id"),
            "officer_name": officer.get("name")}


@pytest.fixture
def cleanup(client):
    created = []
    yield created
    for eid in created:
        client.delete(f"{API}/dispatch/advance-salary/{eid}", timeout=60)


def _clear_ledger(client, ids):
    r = client.get(f"{API}/dispatch/advance-salary",
                   params={"officer_id": ids["officer_id"], "client_id": ids["client_id"]},
                   timeout=60)
    assert r.status_code == 200, r.text[:300]
    entries = r.json().get("entries", [])
    # delete repayments first so balance never goes negative
    for e in [x for x in entries if x.get("type") == "repayment"] + \
             [x for x in entries if x.get("type") == "advance"]:
        client.delete(f"{API}/dispatch/advance-salary/{e['id']}", timeout=60)


# --- Advance Salary CRUD + math ---
class TestAdvanceSalaryCRUD:
    def test_ledger_math_and_over_repayment(self, client, ids, cleanup):
        _clear_ledger(client, ids)
        base = {"officer_id": ids["officer_id"], "client_id": ids["client_id"]}

        # $400 advance
        r = client.post(f"{API}/dispatch/advance-salary",
                        json={**base, "type": "advance", "amount": 400,
                              "entry_date": "2026-08-20", "note": "TEST_adv"}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        cleanup.append(d["id"])
        assert "_id" not in d, "MongoDB _id leaked in response"
        assert d["type"] == "advance" and d["amount"] == 400
        assert d["balance_after"] == 400

        # $100 repayment -> balance 300
        r = client.post(f"{API}/dispatch/advance-salary",
                        json={**base, "type": "repayment", "amount": 100,
                              "entry_date": "2026-08-22"}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        rep = r.json()
        cleanup.append(rep["id"])
        assert rep["balance_after"] == 300

        g = client.get(f"{API}/dispatch/advance-salary",
                       params={**base, "date_from": "2026-08-01", "date_to": "2026-08-31"},
                       timeout=60)
        assert g.status_code == 200
        gd = g.json()
        assert gd["remaining_balance"] == 300
        assert gd["total_advanced"] == 400
        assert gd["total_repaid"] == 100
        assert gd["period_taken"] == 400
        assert gd["period_repaid"] == 100
        assert [e["balance_after"] for e in gd["entries"]] == [400, 300]

        # over-repayment rejected
        r = client.post(f"{API}/dispatch/advance-salary",
                        json={**base, "type": "repayment", "amount": 500,
                              "entry_date": "2026-08-23"}, timeout=60)
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:300]}"

        # further $200 advance -> 500
        r = client.post(f"{API}/dispatch/advance-salary",
                        json={**base, "type": "advance", "amount": 200,
                              "entry_date": "2026-08-24"}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d2 = r.json()
        cleanup.append(d2["id"])
        assert d2["balance_after"] == 500

        g = client.get(f"{API}/dispatch/advance-salary", params=base, timeout=60)
        assert g.json()["remaining_balance"] == 500

    def test_period_filter_excludes_out_of_range(self, client, ids, cleanup):
        _clear_ledger(client, ids)
        base = {"officer_id": ids["officer_id"], "client_id": ids["client_id"]}
        r = client.post(f"{API}/dispatch/advance-salary",
                        json={**base, "type": "advance", "amount": 150,
                              "entry_date": "2025-01-05"}, timeout=60)
        assert r.status_code == 200
        cleanup.append(r.json()["id"])
        g = client.get(f"{API}/dispatch/advance-salary",
                       params={**base, "date_from": "2026-08-01", "date_to": "2026-08-31"},
                       timeout=60)
        gd = g.json()
        assert gd["remaining_balance"] == 150
        assert gd["period_taken"] == 0
        assert gd["period_repaid"] == 0

    def test_validation_errors(self, client, ids):
        base = {"officer_id": ids["officer_id"], "client_id": ids["client_id"]}
        cases = [
            ({**base, "type": "bogus", "amount": 10, "entry_date": "2026-08-20"}, "bad type"),
            ({**base, "type": "advance", "amount": 0, "entry_date": "2026-08-20"}, "zero amount"),
            ({**base, "type": "advance", "amount": -5, "entry_date": "2026-08-20"}, "negative"),
            ({**base, "type": "advance", "amount": 10, "entry_date": ""}, "no date"),
            ({"client_id": ids["client_id"], "type": "advance", "amount": 10,
              "entry_date": "2026-08-20"}, "no officer"),
            ({"officer_id": ids["officer_id"], "type": "advance", "amount": 10,
              "entry_date": "2026-08-20"}, "no client"),
        ]
        for payload, label in cases:
            r = client.post(f"{API}/dispatch/advance-salary", json=payload, timeout=60)
            assert r.status_code == 400, f"{label}: got {r.status_code} {r.text[:200]}"

    def test_get_requires_officer_id(self, client):
        r = client.get(f"{API}/dispatch/advance-salary", timeout=60)
        assert r.status_code == 400

    def test_delete_entry_and_dependency_guard(self, client, ids, cleanup):
        _clear_ledger(client, ids)
        base = {"officer_id": ids["officer_id"], "client_id": ids["client_id"]}
        a = client.post(f"{API}/dispatch/advance-salary",
                        json={**base, "type": "advance", "amount": 300,
                              "entry_date": "2026-08-10"}, timeout=60).json()
        cleanup.append(a["id"])
        rep = client.post(f"{API}/dispatch/advance-salary",
                          json={**base, "type": "repayment", "amount": 250,
                                "entry_date": "2026-08-12"}, timeout=60).json()
        cleanup.append(rep["id"])

        # deleting the advance would make balance negative -> rejected
        d = client.delete(f"{API}/dispatch/advance-salary/{a['id']}", timeout=60)
        assert d.status_code == 400, f"expected 400 got {d.status_code}: {d.text[:300]}"

        # deleting the repayment is fine
        d = client.delete(f"{API}/dispatch/advance-salary/{rep['id']}", timeout=60)
        assert d.status_code == 200, d.text[:300]
        g = client.get(f"{API}/dispatch/advance-salary", params=base, timeout=60)
        assert g.json()["remaining_balance"] == 300
        # now advance can be deleted
        d = client.delete(f"{API}/dispatch/advance-salary/{a['id']}", timeout=60)
        assert d.status_code == 200
        g = client.get(f"{API}/dispatch/advance-salary", params=base, timeout=60)
        assert g.json()["remaining_balance"] == 0
        assert g.json()["entries"] == []

    def test_delete_invalid_and_missing_id(self, client):
        assert client.delete(f"{API}/dispatch/advance-salary/not-an-oid",
                             timeout=60).status_code == 400
        assert client.delete(f"{API}/dispatch/advance-salary/64c000000000000000000000",
                             timeout=60).status_code == 404

    def test_requires_auth(self, ids):
        r = requests.get(f"{API}/dispatch/advance-salary",
                         params={"officer_id": ids["officer_id"]}, timeout=60)
        assert r.status_code in (401, 403), r.status_code


# --- Old advance ledger endpoints must be gone ---
class TestOldLedgerRemoved:
    def test_old_endpoints_404(self, client, ids):
        g = client.get(f"{API}/dispatch/payslip-advance-ledger",
                       params={"officer_id": ids["officer_id"]}, timeout=60)
        assert g.status_code == 404, f"GET still exists: {g.status_code}"
        p = client.post(f"{API}/dispatch/payslip-advance-ledger", json={}, timeout=60)
        assert p.status_code == 404, f"POST still exists: {p.status_code}"
        d = client.delete(f"{API}/dispatch/payslip-advance-ledger/abc", timeout=60)
        assert d.status_code == 404, f"DELETE still exists: {d.status_code}"


# --- Payslip adjustment (addition / deduction only) ---
class TestPayslipAdjustment:
    def test_save_and_read_back(self, client, ids):
        params = {"officer_id": ids["officer_id"], "client_id": ids["client_id"],
                  "date_from": "2026-08-01", "date_to": "2026-08-31"}
        r = client.put(f"{API}/dispatch/payslip-adjustment", params=params,
                       json={"addition": 50, "deduction": 25}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert "advance" not in body, f"old 'advance' field still present: {body}"
        g = client.get(f"{API}/dispatch/payslip-adjustment", params=params, timeout=60)
        assert g.status_code == 200
        gd = g.json()
        assert float(gd.get("addition")) == 50
        assert float(gd.get("deduction")) == 25
        assert "advance" not in gd, f"old 'advance' field still present: {gd}"
        # reset
        client.put(f"{API}/dispatch/payslip-adjustment", params=params,
                   json={"addition": 0, "deduction": 0}, timeout=60)

    def test_negative_rejected(self, client, ids):
        params = {"officer_id": ids["officer_id"], "client_id": ids["client_id"],
                  "date_from": "2026-08-01", "date_to": "2026-08-31"}
        r = client.put(f"{API}/dispatch/payslip-adjustment", params=params,
                       json={"addition": -10, "deduction": 0}, timeout=60)
        assert r.status_code == 400, r.status_code


# --- Entity detail report net payment math + PDF export ---
class TestEntityDetailAndPdf:
    def test_net_payment_math(self, client, ids, cleanup):
        _clear_ledger(client, ids)
        base = {"officer_id": ids["officer_id"], "client_id": ids["client_id"]}
        params = {**base, "date_from": "2026-08-01", "date_to": "2026-08-31"}

        client.put(f"{API}/dispatch/payslip-adjustment", params=params,
                   json={"addition": 40, "deduction": 15}, timeout=60)
        a = client.post(f"{API}/dispatch/advance-salary",
                        json={**base, "type": "advance", "amount": 400,
                              "entry_date": "2026-08-20"}, timeout=60)
        assert a.status_code == 200, a.text[:300]
        cleanup.append(a.json()["id"])
        rep = client.post(f"{API}/dispatch/advance-salary",
                          json={**base, "type": "repayment", "amount": 100,
                                "entry_date": "2026-08-21"}, timeout=60)
        assert rep.status_code == 200
        cleanup.append(rep.json()["id"])

        r = client.get(f"{API}/dispatch/reports/entity-detail",
                       params={"entity_type": "officer", "entity_id": ids["officer_id"],
                               "client_id": ids["client_id"],
                               "date_from": "2026-08-01", "date_to": "2026-08-31"},
                       timeout=60)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        for k in ["net_payment", "advance_remaining_balance", "advance_taken_period",
                  "advance_repaid_period", "extra_payments", "deductions"]:
            assert k in d, f"missing field {k} in entity-detail: {list(d.keys())}"
        total_cost = float(d.get("summary", {}).get("cost_amount") or 0)
        assert total_cost > 0, f"expected seeded payout, summary={d.get('summary')}"
        assert d["extra_payments"] == 40
        assert d["deductions"] == 15
        assert d["advance_taken_period"] == 400
        assert d["advance_repaid_period"] == 100
        assert d["advance_remaining_balance"] == 300
        expected = round(total_cost + 40 - 15 + 400 - 100, 2)
        assert round(float(d["net_payment"]), 2) == expected, \
            f"net_payment {d['net_payment']} != expected {expected} (total_cost={total_cost})"

    def test_payslip_pdf_export(self, client, ids):
        r = client.get(f"{API}/dispatch/reports/export/entity-detail",
                       params={"entity_type": "officer", "entity_id": ids["officer_id"],
                               "date_from": "2026-08-01", "date_to": "2026-08-31",
                               "client_id": ids["client_id"], "format": "pdf",
                               "template": "payslip"}, timeout=120)
        assert r.status_code == 200, r.text[:400]
        assert "application/pdf" in r.headers.get("content-type", ""), r.headers
        assert r.content[:4] == b"%PDF", r.content[:20]
        assert len(r.content) > 1000

    def test_cleanup_ledger(self, client, ids):
        _clear_ledger(client, ids)
        params = {"officer_id": ids["officer_id"], "client_id": ids["client_id"],
                  "date_from": "2026-08-01", "date_to": "2026-08-31"}
        client.put(f"{API}/dispatch/payslip-adjustment", params=params,
                   json={"addition": 0, "deduction": 0}, timeout=60)
        g = client.get(f"{API}/dispatch/advance-salary", params=params, timeout=60)
        assert g.json()["remaining_balance"] == 0
