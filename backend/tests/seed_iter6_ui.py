"""Seed / cleanup temporary TEST_ data for the iteration-6 UI smoke test.

Usage:  python seed_iter6_ui.py seed   |   python seed_iter6_ui.py cleanup
Writes created ids to /tmp/iter6_ui_seed.json
"""
import json
import os
import sys
import uuid

import requests

STATE = "/tmp/iter6_ui_seed.json"


def base():
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise SystemExit("no backend url")


API = f"{base()}/api"


def login():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": "admin@example.com", "password": "admin123"}, timeout=30)
    r.raise_for_status()
    return s


def seed():
    s = login()
    tag = uuid.uuid4().hex[:5]
    created = {"tag": tag, "clients": [], "vendors": [], "officers": [], "post_sites": [], "schedules": []}

    def post(p, b):
        r = s.post(f"{API}{p}", json=b, timeout=30)
        assert r.status_code in (200, 201), f"{p} {r.status_code} {r.text[:200]}"
        return r.json()

    c = post("/dispatch/clients", {"name": f"TEST_UI_C_{tag}", "code": f"TUC{tag}", "accent_color": "#3B82F6"})
    v = post("/dispatch/vendors", {"name": f"TEST_UI_V_{tag}", "code": f"TUV{tag}"})
    o = post("/dispatch/officers", {"name": f"TEST_UI_O_{tag}", "contact_number": "0170000009"})
    created["clients"].append(c["id"]); created["vendors"].append(v["id"]); created["officers"].append(o["id"])
    sites = []
    for i, key in enumerate(["P", "Q"]):
        p = post("/dispatch/post-sites", {"post_pin": f"TU{key}{tag}", "name": f"TEST_UI_S_{key}_{tag}",
                                          "location": f"TESTUILOC_{key}_{tag}", "city": "Testville"})
        sites.append(p); created["post_sites"].append(p["id"])
        sc = post("/dispatch/schedules", {
            "date": f"2026-07-0{2 + i}", "shift_type": "Morning", "start_time": "08:00", "end_time": "16:00",
            "client_id": c["id"], "vendor_id": v["id"], "post_site_id": p["id"], "officer_id": o["id"],
            "work_order_number": f"WOUI-{tag}-{key}", "duty_rate": 10.0, "billing_rate": 30.0})
        created["schedules"].append(sc["id"])
        r = s.post(f"{API}/dispatch/schedules/{sc['id']}/status", json={"shift_status": "Complete"}, timeout=30)
        assert r.status_code == 200, r.text
    created["client_name"] = c["name"]
    created["vendor_name"] = v["name"]
    created["site_ids"] = [p["id"] for p in sites]
    with open(STATE, "w") as f:
        json.dump(created, f)
    print(json.dumps(created, indent=2))


def cleanup():
    if not os.path.exists(STATE):
        print("no state"); return
    s = login()
    st = json.load(open(STATE))
    invs = s.get(f"{API}/dispatch/invoices", params={"client_id": st["clients"][0]}, timeout=30).json()
    for inv in invs.get("items", []):
        s.delete(f"{API}/dispatch/invoices/{inv['id']}", timeout=30)
    for sid in st["schedules"]:
        s.delete(f"{API}/dispatch/schedules/{sid}", timeout=30)
    for pid in st["post_sites"]:
        s.delete(f"{API}/dispatch/post-sites/{pid}", timeout=30)
    for oid in st["officers"]:
        s.delete(f"{API}/dispatch/officers/{oid}", timeout=30)
    for cid in st["clients"]:
        s.delete(f"{API}/dispatch/clients/{cid}", timeout=30)
    for vid in st["vendors"]:
        s.delete(f"{API}/dispatch/vendors/{vid}", timeout=30)
    os.remove(STATE)
    print("cleaned")


if __name__ == "__main__":
    (seed if (len(sys.argv) > 1 and sys.argv[1] == "seed") else cleanup)()
