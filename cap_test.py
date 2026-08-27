import requests

BASE_URL = "https://git-preview-build-1.preview.emergentagent.com/api"
session = requests.Session()

# Login
session.post(f"{BASE_URL}/auth/login", json={"email": "admin@example.com", "password": "admin123"})

officer_id = "6a8f56b0e2cab8da51c4d461"
client_id = "6a8f55eae2cab8da51c4d45c"
date_from = "2026-08-19"
date_to = "2026-08-26"

# Get current balance
resp = session.get(f"{BASE_URL}/dispatch/advance-salary", params={
    "officer_id": officer_id,
    "client_id": client_id
})
balance = resp.json()['remaining_balance']
print(f"Current balance: ${balance}")

# Try to deduct more than balance
excessive = balance + 100
print(f"\nTrying to deduct ${excessive} (more than balance)...")

resp = session.put(
    f"{BASE_URL}/dispatch/payslip-adjustment",
    params={
        "officer_id": officer_id,
        "client_id": client_id,
        "date_from": date_from,
        "date_to": date_to
    },
    json={
        "extra_payments": [],
        "deductions": [{"date": date_to, "purpose": "Excessive", "amount": excessive}]
    }
)

print(f"Response: {resp.status_code}")
if resp.status_code == 400:
    print(f"✓ Correctly rejected: {resp.json()}")
else:
    print(f"✗ Should have been rejected but got: {resp.json()}")
