import requests

BASE_URL = "https://git-preview-build-1.preview.emergentagent.com/api"
session = requests.Session()

# Login
session.post(f"{BASE_URL}/auth/login", json={"email": "admin@example.com", "password": "admin123"})

# Get all advance docs via the API
resp = session.get(f"{BASE_URL}/dispatch/advance-salary", params={
    "officer_id": "6a8f56b0e2cab8da51c4d461",
    "client_id": "6a8f55eae2cab8da51c4d45c"
})

data = resp.json()
print("All visible entries:")
for e in data['entries']:
    print(f"  {e['type']}: ${e['amount']} - {e.get('note', 'N/A')} - source: {e.get('source', 'N/A')}")

print(f"\nTotal advanced: ${data['total_advanced']}")
print(f"Total repaid: ${data['total_repaid']}")
print(f"Balance: ${data['remaining_balance']}")
print(f"\nExpected balance: ${data['total_advanced']} - ${data['total_repaid']} = ${data['total_advanced'] - data['total_repaid']}")
