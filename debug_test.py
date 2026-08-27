import requests

BASE_URL = "https://git-preview-build-1.preview.emergentagent.com/api"
session = requests.Session()

# Login
session.post(f"{BASE_URL}/auth/login", json={"email": "admin@example.com", "password": "admin123"})

# Get advance ledger
resp = session.get(f"{BASE_URL}/dispatch/advance-salary", params={
    "officer_id": "6a8f56b0e2cab8da51c4d461",
    "client_id": "6a8f55eae2cab8da51c4d45c"
})

data = resp.json()
print("=== Advance Ledger Debug ===")
print(f"Remaining balance: ${data['remaining_balance']}")
print(f"Total advanced: ${data['total_advanced']}")
print(f"Total repaid: ${data['total_repaid']}")
print(f"\nVisible entries ({len(data['entries'])}):")
for e in data['entries']:
    print(f"  {e['type']}: ${e['amount']} on {e['entry_date']} - {e.get('note', 'N/A')}")
