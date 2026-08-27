"""Seed a plain employee (no dispatch permissions) for portal-gating UI tests."""
import os
import requests
from dotenv import dotenv_values

env = dotenv_values("/app/frontend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or env.get("REACT_APP_BACKEND_URL")).rstrip("/")

EMAIL = "test.plain@officeflow.com"
PASSWORD = "Test@123"

s = requests.Session()
r = s.post(f"{BASE}/api/auth/login", json={"email": "admin@example.com", "password": "admin123"})
print("admin login:", r.status_code)
token = r.json().get("access_token") or r.json().get("token")
s.headers.update({"Authorization": f"Bearer {token}"})

r = s.post(f"{BASE}/api/employees", json={
    "email": EMAIL,
    "name": "TEST Plain Employee",
    "password": PASSWORD,
    "role": "employee",
    "permissions": [],
})
print("create employee:", r.status_code, r.text[:300])

r = requests.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
print("employee login:", r.status_code, r.text[:400])
