"""Tests for local-filesystem image uploads (iteration 5)."""
import io
import os
import struct
import zlib
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
    open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]


def _tiny_png() -> bytes:
    """Return a valid 1x1 red PNG (raw bytes)."""
    sig = b"\x89PNG\r\n\x1a\n"
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + \
               struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x00\x00")
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "admin@example.com", "password": "admin123"})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


def _upload(session, url, field="file", filename="test.png"):
    files = {field: (filename, _tiny_png(), "image/png")}
    return session.post(url, files=files)


def _fetch_url(session, url):
    # url is /api/files/... — resolve against BASE_URL
    full = url if url.startswith("http") else f"{BASE_URL}{url}"
    return session.get(full)


# --- Settings: brand logo -----------------------------------------------------
def test_upload_brand_logo(session):
    r = _upload(session, f"{BASE_URL}/api/settings/logo")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "brand_logo_url" in data and data["brand_logo_url"]
    assert data["brand_logo_url"].startswith("/api/files/") or "/api/files/" in data["brand_logo_url"]

    f = _fetch_url(session, data["brand_logo_url"])
    assert f.status_code == 200
    assert f.headers.get("content-type", "").startswith("image/")
    assert len(f.content) > 0

    # persisted via public settings
    p = session.get(f"{BASE_URL}/api/settings/public")
    assert p.status_code == 200
    assert p.json().get("brand_logo_url") == data["brand_logo_url"]


# --- Settings: favicon --------------------------------------------------------
def test_upload_favicon(session):
    r = _upload(session, f"{BASE_URL}/api/settings/favicon", filename="fav.png")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("favicon_url")
    f = _fetch_url(session, data["favicon_url"])
    assert f.status_code == 200
    assert f.headers.get("content-type", "").startswith("image/")

    p = session.get(f"{BASE_URL}/api/settings/public").json()
    assert p.get("favicon_url") == data["favicon_url"]


# --- Dispatch upload-logo (client / vendor) -----------------------------------
def test_upload_dispatch_logo(session):
    r = _upload(session, f"{BASE_URL}/api/dispatch/upload-logo", filename="client.png")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("url")
    f = _fetch_url(session, data["url"])
    assert f.status_code == 200
    assert f.headers.get("content-type", "").startswith("image/")


# --- Company logo -------------------------------------------------------------
def test_company_logo_flow(session):
    # Create a company
    cname = f"TEST_upload_{uuid.uuid4().hex[:8]}"
    c = session.post(f"{BASE_URL}/api/companies",
                     json={"name": cname, "email": "u@u.com"})
    assert c.status_code in (200, 201), c.text
    cid = c.json()["id"]

    # Upload logo
    r = _upload(session, f"{BASE_URL}/api/companies/{cid}/logo",
                filename="cologo.png")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("logo_path")

    # Fetchable
    f = _fetch_url(session, body["logo_path"])
    assert f.status_code == 200
    assert f.headers.get("content-type", "").startswith("image/")

    # Persisted on company doc
    g = session.get(f"{BASE_URL}/api/companies/{cid}")
    assert g.status_code == 200
    assert g.json().get("logo_path") == body["logo_path"]

    # Cleanup
    session.delete(f"{BASE_URL}/api/companies/{cid}")


# --- File 404 -----------------------------------------------------------------
def test_file_not_found(session):
    r = session.get(f"{BASE_URL}/api/files/officeflow/nope/does-not-exist.png")
    assert r.status_code == 404
