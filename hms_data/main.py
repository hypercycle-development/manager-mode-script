import json
import asyncio
import time
from collections import defaultdict
from typing import List, Set
from gist_addresses import fetch_gist_addresses
from common import tranche1_addresses_gist_id
from subgraph import get_license


async def main():
    t1_addresses = await fetch_gist_addresses(tranche1_addresses_gist_id)

    # Read data from license_register.json
    # The owners are wrong because they are Share contract, so we need the subgraph to get the real owner
    with open("hms_data/license_register.json", "r") as f:
        data = json.load(f)

    # All the licenses in HMS registry
    licenses: Set[str] = set()

    # Set of addresses that are on HMS and are in tranche1
    addresses: Set[str] = set()

    # Mapping of address to their licenses
    address_licenses = defaultdict(list)

    # First we get all the licenses in HMS registry
    for entry in data:
        # License ID
        license_id = entry.get("license_id")

        # Add it to the set of licenses
        if license_id:
            licenses.add(license_id)

    print(f"Total licenses in HMS registry: {len(licenses)}")

    # Now we fetch the licenses from the Subgrap and check who is the license owner of each license
    for license_id in licenses:
        try:
            print(f"license_id: {license_id}")
            license_data, is_cached = await get_license(license_id)
        except Exception as e:
            print(f"Error fetching license {license_id}: {e}")
            continue

        if not license_data:
            print(f"No data found for license {license_id}")
            continue

        owner: str | None = license_data.get("licenseOwner")
        if owner and owner in t1_addresses:
            addresses.add(owner)
            address_licenses[owner].append(license_id)
            print(f"License {license_id} is owned by {owner}")

        if not is_cached:
            time.sleep(2)  # To avoid overwhelming the subgraph

    print(f"Total unique addresses in tranche1 with licenses: {len(addresses)}")

    # Now, the addresses into hms_data/hms_tranche1_addresses.json
    with open("hms_data/hms_tranche1_addresses.json", "w") as f:
        json.dump(list(addresses), f, indent=2)

    # And the mapping of address to their licenses into hms_data/hms_tranche1_address_licenses.json
    with open("hms_data/hms_tranche1_address_licenses.json", "w") as f:
        json.dump(address_licenses, f, indent=2)


if __name__ == "__main__":
    asyncio.run(main())

# Print results
# print("Unique Addresses and Their Licenses:")
# print("=" * 80)
# for address, licenses in address_licenses.items():
#     print(f"\nAddress: {address}")
#     print(f"Licenses ({len(licenses)}):")
#     for license_id in licenses:
#         print(f"  - {license_id}")

# # Alternative format: JSON output
# print("\n\n" + "=" * 80)
# print("JSON Format:")
# print("=" * 80)
# result = [
#     {
#         "address": address,
#         # "licenses": licenses,
#         # "license_count": len(licenses)
#     }
#     for address, licenses in address_licenses.items()
# ]
# print(json.dumps(result, indent=2))
