"""Regression tests for the Invoice `pin_display` removal + Location = Post Site Name fix.

- Invoice preview lines must have location == post_site_name and pin_display None.
- Invoice PDF must not contain any '# <pin>' string.
- Even when caller supplies a post_pin via override lines, response must strip pin_display.
- Schedules must still expose post_pin_display (unaffected).
- Reports endpoint by-officer must still function.
"""
import io
import os
import re
import pytest
import requests
import pdfplumber

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://officeflow-v3.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def ctx(session):
    # find client + vendor
    cr = session.get(f"{API}/dispatch/clients", timeout=30)
    assert cr.status_code == 200, cr.text
    cj = cr.json()
    clients = cj.get("items") if isinstance(cj, dict) else cj
    assert clients, "No clients seeded"
    client_id = clients[0]["id"]

    vr = session.get(f"{API}/dispatch/vendors", timeout=30)
    assert vr.status_code == 200
    vj = vr.json()
    vendors = vj.get("items") if isinstance(vj, dict) else vj
    assert vendors, "No vendors seeded"
    vendor_id = vendors[0]["id"]

    return {"client_id": client_id, "vendor_id": vendor_id}


def _preview_payload(ctx, lines=None):
    return {
        "client_id": ctx["client_id"],
        "vendor_id": ctx["vendor_id"],
        "invoice_number": "TEST-9001",
        "invoice_date": "2026-08-31",
        "billing_period_from": "2026-01-01",
        "billing_period_to": "2026-12-31",
        "notes": "test",
        **({"lines": lines} if lines is not None else {}),
    }


def test_preview_location_equals_post_site_name_and_pin_display_null(session, ctx):
    r = session.post(f"{API}/dispatch/invoices/preview", json=_preview_payload(ctx), timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    lines = data.get("lines") or []
    assert lines, "Expected at least one line for the broad billing period; check seeded shift"
    for ln in lines:
        assert ln.get("pin_display") is None, f"pin_display leaked: {ln}"
        assert ln.get("location") == ln.get("post_site_name"), (
            f"location != post_site_name: location={ln.get('location')!r} vs post_site_name={ln.get('post_site_name')!r}"
        )


def test_preview_pdf_has_no_post_pin_string_and_expected_headers(session, ctx):
    r = session.post(f"{API}/dispatch/invoices/preview/pdf", json=_preview_payload(ctx), timeout=90)
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("application/pdf")
    pdf_bytes = r.content
    assert pdf_bytes[:4] == b"%PDF", "Not a PDF"

    # Fetch known post_pin from preview lines to know exact pin we should NOT see
    preview = session.post(f"{API}/dispatch/invoices/preview", json=_preview_payload(ctx), timeout=60).json()
    known_pins = {str(ln.get("post_pin")) for ln in preview.get("lines", []) if ln.get("post_pin")}

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join((page.extract_text() or "") for page in pdf.pages)

    # Expected headers
    for h in ["Shift Date", "Location", "Work Order", "Actual Hour", "Rate", "Total Amount"]:
        assert h in text, f"PDF missing header {h!r}. Text was:\n{text[:800]}"

    # No known pin (e.g. '123') as a standalone '# 123' or 'PTS # 123' pattern
    for pin in known_pins:
        assert f"# {pin}" not in text, f"Found '# {pin}' in invoice PDF text"
        assert f"#{pin}" not in text, f"Found '#{pin}' in invoice PDF text"

    # Generic pin-display pattern like "PTS # 123" should not appear
    pin_pattern = re.compile(r"\b[A-Z]{2,6}\s*#\s*\d+\b")
    m = pin_pattern.search(text)
    assert m is None, f"Found pin_display pattern in PDF: {m.group(0)}"

    # Client / vendor names should be present
    assert preview["client"]["name"].split()[0] in text, "Client name missing from PDF"


def test_preview_strips_pin_display_from_override_lines(session, ctx):
    override_lines = [
        {
            "schedule_id": None,
            "shift_date": "2026-08-23",
            "location": "Komlapur",
            "post_pin": "123",
            "pin_display": "PTS # 123",  # attempt to smuggle it back in
            "post_site_name": "Komlapur",
            "work_order": "WO-1",
            "actual_hours": 8,
            "rate": 25,
        }
    ]
    r = session.post(f"{API}/dispatch/invoices/preview", json=_preview_payload(ctx, lines=override_lines), timeout=60)
    assert r.status_code == 200, r.text
    lines = r.json().get("lines") or []
    assert lines, "Override lines should be echoed back"
    for ln in lines:
        assert ln.get("pin_display") is None, f"Backend did not strip pin_display: {ln}"


def test_schedules_still_have_post_pin_display(session):
    r = session.get(f"{API}/dispatch/schedules", params={"limit": 3}, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    items = body.get("items") if isinstance(body, dict) else body
    assert items, "No schedules returned"
    # At least one item should carry post_pin_display key (VENDOR # PIN)
    have_key = [("post_pin_display" in it) for it in items]
    assert any(have_key), f"post_pin_display missing from schedules: {items[0].keys()}"
    # value should look like 'PTS # 123' when present
    for it in items:
        if it.get("post_pin_display"):
            assert re.match(r"^[A-Z0-9]+\s*#\s*\S+", it["post_pin_display"]), it["post_pin_display"]
            break


def test_reports_by_officer_regression(session):
    r = session.get(
        f"{API}/dispatch/reports/by-officer",
        params={"date_from": "2026-06-01", "date_to": "2026-08-31"},
        timeout=60,
    )
    assert r.status_code == 200, r.text
