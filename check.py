import asyncio
import os
import json
from aiohttp import ClientSession, ClientError
from typing import Optional, List, Dict, Any

# Subgraph endpoints
SUBGRAPHS = {
    "mainnet": {
        "ethereum": "https://api.studio.thegraph.com/query/90034/hypercycle-ethereum/v0.7.26",
        "base": "https://api.studio.thegraph.com/query/90034/hypercycle-base/v0.7.26",
    },
    "testnet": {
        "ethereum": "https://api.studio.thegraph.com/query/90034/hypercycle-ethereum-sepolia/v0.7.26",
        "base": "https://api.studio.thegraph.com/query/90034/hypercycle-base-sepolia/v0.7.26",
    },
}


async def query_subgraph(
    session: ClientSession, url: str, query: str
) -> Optional[Dict]:
    """Execute GraphQL query against subgraph"""
    payload = {"query": query}
    try:
        async with session.post(url, json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()
    except ClientError as e:
        print(f"⚠️ Subgraph query failed: {e}")
        return None


def build_query(account_address: str) -> str:
    """Generate the GraphQL query for license/anfe data"""
    return f"""
    {{
        shareProposalDatas(
            first: 1000
            orderBy: proposalId
            where: {{ operator_contains: "{account_address}" }}
        ) {{
            proposalId
            shareNumberId
            chypcId
            licenseId
            rTokenId
            wTokenId
            operator
        }}
    }}
    """


async def fetch_all_networks(
    session: ClientSession, networks: Dict[str, str], account_address: str
) -> List[Dict[str, Any]]:
    """Query multiple networks in parallel"""
    query = build_query(account_address)
    tasks = []

    for chain_name, url in networks.items():
        print(f"🔍 Querying data from {chain_name}...")
        tasks.append(query_subgraph(session, url, query))

    return await asyncio.gather(*tasks)

# http
merklizer_url = "18.216.251.149:8003"

share_token_v2 = "0x4BFbA79CF232361a53eDdd17C67C6c77A6F00379"
share_manager_v2 = "0xc5d5B9F30AA674aA210a0ec24941bAd7D8b42069"
share_manager_legacy = "0x5A3591001DfB63FAc81d2976C150BB38df2cd71C"


def read_tranche_addresses(filename):
    """Read addresses from tranche file, ignoring comments and empty lines"""
    with open(filename, "r") as file:
        addresses = [
            line.strip() for line in file if line.strip() and not line.startswith("#")
        ]
    return set(addresses)  # Using set for faster lookups


def read_hts_files(file_pattern, num_files=6):
    """Read all hts files and return a dictionary of address to license IDs"""
    activity_data = {}  # {address: set(license_ids)}

    for i in range(1, num_files + 1):
        filename = file_pattern.format(i)
        if not os.path.exists(filename):
            continue

        with open(filename, "r") as file:
            # Skip header line
            next(file, None)

            for line in file:
                if not line.strip():
                    continue

                parts = line.strip().split()
                if len(parts) < 2:
                    continue

                address = parts[0]
                license_id = parts[1]

                if address not in activity_data:
                    activity_data[address] = set()
                activity_data[address].add(license_id)

    return activity_data


def classify_addresses(tranche_addresses, activity_data):
    """Classify addresses into different categories"""
    active_addresses = {}
    inactive_addresses = set()

    for address in tranche_addresses:
        if address in activity_data:
            active_addresses[address] = activity_data[address]
        else:
            inactive_addresses.add(address)

    return active_addresses, inactive_addresses


async def main():
    networks = SUBGRAPHS["mainnet"]

    # Read the tranche addresses
    tranche_file = "data_tillers/tranche1_addresses.txt"
    tranche_addresses = read_tranche_addresses(tranche_file)

    # Read all hts files
    activity_data = read_hts_files("data_tillers/merk_data/hts{}.txt")

    # Classify the addresses
    active_addresses, inactive_addresses = classify_addresses(
        tranche_addresses, activity_data
    )

    async with ClientSession() as session:
        # Fetch data for each address in the tranche
        data = await fetch_all_networks(
            session, networks, "0x1Eb5AF9DE17437552B526946116c0bDCFCAb60bC"
        )
        print(f"Fetched data from {(data)} networks.")

    # results = await fetch_all_networks(session, networks, args.license_anfe)

    # # Print results
    # print("\n=== Addresses with activity ===")
    # for address, licenses in active_addresses.items():
    #     print(f"{address} - {len(licenses)} license(s): {', '.join(licenses)}")

    # print("\n=== Addresses without activity ===")
    # for address in inactive_addresses:
    #     print(address)

    # # Print summary statistics
    # print("\n=== Summary ===")
    # print(f"Total addresses in tranche: {len(tranche_addresses)}")
    # print(f"activity_data: {len(activity_data)}")
    # print(f"Addresses with activity: {len(active_addresses)}")
    # print(f"{active_addresses}")
    # print(f"-- Addresses without activity: {len(inactive_addresses)}")
    # print(f"{inactive_addresses}")
    # print(
    #     f"Addresses with multiple licenses: {sum(1 for licenses in active_addresses.values() if len(licenses) > 1)}"
    # )


if __name__ == "__main__":
    asyncio.run(main())
