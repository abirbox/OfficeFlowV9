"""Seed/cleanup a TEST_ client with NO accent_color for the iter7 UI colour check."""
import os
import sys
import requests
from dotenv import dotenv_values

fe = dotenv_values("/app/frontend/.env")
API = (os.environ.get("REACT_APP_BACKEND_URL") or fe.get("REACT_APP_BACKEND_URL")).rstrip("/") + "/api"
NAME = "TEST_iter7 ColorClient"

s = requests.Session()
r = s.post(f"{API}/auth/login", json={"email": "admin@example.com", "password": "admin123"}, timeout=30)
r.raise_for_status()
tok = r.json().get("access_token") or r.json().get("token")
if tok:
    s.headers.update({"Authorization": f"Bearer {tok}"})

mode = sys.argv[1] if len(sys.argv) > 1 else "seed"
_raw = s.get(f"{API}/dispatch/clients", timeout=30).json()
_items = _raw if isinstance(_raw, list) else _raw.get("items", [])
existing = [c for c in _items if c.get("name") == NAME]

if mode == "seed":
    if existing:
        print("exists", existing[0]["id"])
    else:
        c = s.post(f"{API}/dispatch/clients", json={"name": NAME}, timeout=30)
        print(c.status_code, c.json().get("id"), c.json().get("accent_color"))
else:
    for c in existing:
        print("delete", s.delete(f"{API}/dispatch/clients/{c['id']}", timeout=30).status_code)
