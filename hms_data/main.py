import json
from collections import defaultdict

# Read data from license_register.json
with open('hms_data/license_register.json', 'r') as f:
    data = json.load(f)

# Group licenses by address
address_licenses = defaultdict(list)

for entry in data:
    address = entry.get("owner_address")
    license_id = entry.get("license_id")
    
    if address and license_id:
        address_licenses[address].append(license_id)

# Print results
print("Unique Addresses and Their Licenses:")
print("=" * 80)
for address, licenses in address_licenses.items():
    print(f"\nAddress: {address}")
    print(f"Licenses ({len(licenses)}):")
    for license_id in licenses:
        print(f"  - {license_id}")

# Alternative format: JSON output
print("\n\n" + "=" * 80)
print("JSON Format:")
print("=" * 80)
result = [
    {
        "address": address,
        # "licenses": licenses,
        # "license_count": len(licenses)
    }
    for address, licenses in address_licenses.items()
]
print(json.dumps(result, indent=2))