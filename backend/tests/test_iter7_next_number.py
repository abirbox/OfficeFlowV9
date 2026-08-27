"""Iteration-7 targeted re-verification of the alpha-prefix invoice-number parser fix.

Covers:
- GET /api/dispatch/invoices/next-number considers ALL digit runs of every
  invoice_number (e.g. 'INV-5301' then '#5330-A' -> '5331').
- plain numeric increments ('5410' -> '5411')
- floor behaviour (empty collection -> '5250'), verified by temporarily
  renaming the invoice docs into a scratch collection and restoring them.
"""
import os
import asyncio

import pytest
import requests
from dotenv import dotenv_values

fe = dotenv_values("/app/frontend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or fe.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE}/api"
PERIOD = ("2026-04-01", "2026-04-30")


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": "admin@example.com", "password": "admin123"}, timeout=30)
    assert r.status_code == 200, f"login -> {r.status_code} {r.text[:300]}"
    tok = (r.json() or {}).get("access_token") or (r.json() or {}).get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def ids(admin):
    created = {"clients": [], "vendors": [], "invoices": []}
    c = admin.post(f"{API}/dispatch/clients", json={"name": "TEST_iter7 Client", "accent_color": "#3B82F6"}, timeout=30)
    assert c.status_code in (200, 201), c.text
    created["clients"].append(c.json()["id"])
    v = admin.post(f"{API}/dispatch/vendors", json={"name": "TEST_iter7 Vendor"}, timeout=30)
    assert v.status_code in (200, 201), v.text
    created["vendors"].append(v.json()["id"])
    yield {"client": c.json()["id"], "vendor": v.json()["id"], "created": created}
    for i in created["invoices"]:
        admin.delete(f"{API}/dispatch/invoices/{i}", timeout=30)
    for i in created["clients"]:
        admin.delete(f"{API}/dispatch/clients/{i}", timeout=30)
    for i in created["vendors"]:
        admin.delete(f"{API}/dispatch/vendors/{i}", timeout=30)


def _next(admin):
    r = admin.get(f"{API}/dispatch/invoices/next-number", timeout=30)
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    n = r.json()["invoice_number"]
    assert isinstance(n, str) and n.isdigit(), n
    return n


def _save(admin, ids, number):
    r = admin.post(f"{API}/dispatch/invoices", json={
        "client_id": ids["client"], "vendor_id": ids["vendor"],
        "invoice_number": str(number), "invoice_date": "2026-05-01",
        "billing_period_from": PERIOD[0], "billing_period_to": PERIOD[1],
        "post_site_ids": [],
    }, timeout=60)
    assert r.status_code in (200, 201), f"save {number} -> {r.status_code} {r.text[:300]}"
    ids["created"]["invoices"].append(r.json()["id"])
    return r.json()


# --- exact iteration-6 defect reproduction ---
def test_alpha_then_hash_prefixed_sequence(admin, ids):
    base = int(_next(admin))
    a = base + 50            # e.g. 5301
    b = base + 79            # e.g. 5330
    _save(admin, ids, f"INV-{a}")
    assert _next(admin) == str(a + 1), "alpha-prefixed number ignored"
    _save(admin, ids, f"#{b}-A")
    got = _next(admin)
    assert got == str(b + 1), f"expected {b+1} after 'INV-{a}' + '#{b}-A', got {got}"


def test_plain_numeric_increments(admin, ids):
    n = int(_next(admin))
    _save(admin, ids, n)
    assert _next(admin) == str(n + 1)


def test_multiple_digit_runs_uses_max(admin, ids):
    n = int(_next(admin))
    big = n + 40
    _save(admin, ids, f"2026/{big}/07")
    got = _next(admin)
    assert got == str(big + 1), f"expected max digit-run {big} to win, got {got}"


def test_floor_when_no_invoices(admin):
    """With an empty dispatch_invoices collection the floor must be 5250."""
    from motor.motor_asyncio import AsyncIOMotorClient

    async def move(src, dst):
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        docs = await db[src].find({}).to_list(5000)
        if docs:
            await db[dst].insert_many(docs)
            await db[src].delete_many({})
        cli.close()
        return len(docs)

    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    moved = asyncio.get_event_loop().run_until_complete(move("dispatch_invoices", "iter7_backup_invoices"))
    try:
        assert _next(admin) == "5250"
    finally:
        asyncio.get_event_loop().run_until_complete(move("iter7_backup_invoices", "dispatch_invoices"))
        restored = moved
    assert restored == moved
