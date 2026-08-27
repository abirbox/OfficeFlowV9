"""Iteration 30 — Dispatch schedule combined remarks (creation + status + confirm + inline)."""
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


def _creds():
    content = Path("/app/memory/test_credentials.md").read_text()
    e = re.search(r'(?im)^\s*[-*]?\s*Email:\s*`?([^`\s]+)', content)
    p = re.search(r'(?im)^\s*[-*]?\s*Password:\s*`?([^`\s]+)', content)
    return e.group(1), p.group(1)


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    email, pwd = _creds()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pwd})
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:300]}"
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    me = s.get(f"{API}/auth/me")
    assert me.status_code == 200, f"auth/me failed {me.status_code} {me.text[:200]}"
    return s


@pytest.fixture(scope="module")
def refs(client):
    out = {}
    for key, path in [("client", "clients"), ("vendor", "vendors"), ("officer", "officers"),
                      ("post_site", "post-sites")]:
        r = client.get(f"{API}/dispatch/{path}")
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        assert items, f"no {path} seeded"
        out[key] = items[0]
    return out


@pytest.fixture(scope="module")
def created(client):
    ids = []
    yield ids
    for sid in ids:
        client.delete(f"{API}/dispatch/schedules/{sid}")


import itertools
_day_counter = itertools.count(1)


def _create(client, refs, created, remark, date=None):
    date = date or "2026-09-%02d" % next(_day_counter)
    payload = {
        "schedule_mode": "once",
        "date": date,
        "shift_type": "Morning",
        "start_time": "08:00",
        "end_time": "16:00",
        "client_id": str(refs["client"].get("id") or refs["client"].get("_id")),
        "vendor_id": str(refs["vendor"].get("id") or refs["vendor"].get("_id")),
        "post_site_id": str(refs["post_site"].get("id") or refs["post_site"].get("_id")),
        "officer_id": str(refs["officer"].get("id") or refs["officer"].get("_id")),
        "remarks": remark,
    }
    r = client.post(f"{API}/dispatch/schedules", json=payload)
    assert r.status_code in (200, 201), f"create failed {r.status_code} {r.text[:400]}"
    body = r.json()
    doc = body[0] if isinstance(body, list) else (body.get("items", [body])[0] if isinstance(body, dict) and "items" in body else body)
    sid = str(doc.get("id") or doc.get("_id"))
    assert sid and sid != "None", f"no id in create response: {body}"
    created.append(sid)
    return sid


def _get(client, sid):
    r = client.get(f"{API}/dispatch/schedules/{sid}")
    assert r.status_code == 200, f"get {sid} -> {r.status_code} {r.text[:200]}"
    return r.json()


class TestCombinedRemarks:
    def test_creation_remark_stored(self, client, refs, created):
        sid = _create(client, refs, created, "TEST_creation_remark")
        doc = _get(client, sid)
        assert "TEST_creation_remark" in (doc.get("remarks") or "")

    def test_status_remark_appends(self, client, refs, created):
        sid = _create(client, refs, created, "TEST_r1_creation")
        r = client.post(f"{API}/dispatch/schedules/{sid}/status",
                        json={"shift_status": "Clocked In", "remarks": "TEST_r2_status"})
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        doc = _get(client, sid)
        remarks = doc.get("remarks") or ""
        assert "TEST_r1_creation" in remarks, f"creation remark lost: {remarks!r}"
        assert "TEST_r2_status" in remarks, f"status remark not appended: {remarks!r}"
        assert doc.get("shift_status") == "Clocked In"

    def test_confirm_remark_appends(self, client, refs, created):
        sid = _create(client, refs, created, "TEST_c1_creation")
        r = client.post(f"{API}/dispatch/schedules/{sid}/confirm",
                        json={"confirmation_status": "Confirmed", "confirmation_method": "Call",
                              "remarks": "TEST_c2_confirm"})
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        doc = _get(client, sid)
        remarks = doc.get("remarks") or ""
        assert "TEST_c1_creation" in remarks
        assert "TEST_c2_confirm" in remarks, f"confirm remark not appended: {remarks!r}"

    def test_inline_put_and_list_combined(self, client, refs, created):
        sid = _create(client, refs, created, "TEST_x1_creation", date="2026-09-20")
        client.post(f"{API}/dispatch/schedules/{sid}/status",
                    json={"shift_status": "Clocked Out", "remarks": "TEST_x2_status"})
        doc = _get(client, sid)
        combined = (doc.get("remarks") or "") + "\nTEST_x3_inline"
        r = client.put(f"{API}/dispatch/schedules/{sid}", json={"remarks": combined})
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        doc = _get(client, sid)
        lines = [l.strip() for l in (doc.get("remarks") or "").split("\n") if l.strip()]
        assert lines == ["TEST_x1_creation", "TEST_x2_status", "TEST_x3_inline"], lines

        # list endpoint returns combined remarks
        r = client.get(f"{API}/dispatch/schedules", params={"date_from": "2026-09-20", "date_to": "2026-09-20"})
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        row = next((i for i in items if str(i.get("id") or i.get("_id")) == sid), None)
        assert row is not None, "created schedule missing from list"
        for expect in ["TEST_x1_creation", "TEST_x2_status", "TEST_x3_inline"]:
            assert expect in (row.get("remarks") or ""), f"{expect} missing in list remarks {row.get('remarks')!r}"
        assert "_id" not in row

    def test_status_duplicate_remark_dedup(self, client, refs, created):
        sid = _create(client, refs, created, "TEST_dup")
        client.post(f"{API}/dispatch/schedules/{sid}/status",
                    json={"shift_status": "Clocked In", "remarks": "TEST_dup"})
        doc = _get(client, sid)
        lines = [l for l in (doc.get("remarks") or "").split("\n") if l.strip()]
        assert lines.count("TEST_dup") == 1, lines

    def test_status_without_remark_keeps_existing(self, client, refs, created):
        sid = _create(client, refs, created, "TEST_keep_me")
        r = client.post(f"{API}/dispatch/schedules/{sid}/status", json={"shift_status": "Clocked In"})
        assert r.status_code == 200
        doc = _get(client, sid)
        assert "TEST_keep_me" in (doc.get("remarks") or "")
