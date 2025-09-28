from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils.address import to_checksum_address
from aiohttp import ClientSession, ClientError
from typing import Optional, List, Dict, Any, Tuple
from common import MAX_BLOCK_NUMBER
from app_types import ProposalData
import json
import os
from pathlib import Path

# Subgraph endpoints
SUBGRAPHS = {
    "mainnet": {
        "ethereum": "https://api.studio.thegraph.com/query/90034/hypercycle-ethereum/v0.7.34",
        "base": "https://api.studio.thegraph.com/query/90034/hypercycle-base/v0.7.34",
    },
    "testnet": {
        "ethereum": "https://api.studio.thegraph.com/query/90034/hypercycle-ethereum-sepolia/v0.7.34",
        "base": "https://api.studio.thegraph.com/query/90034/hypercycle-base-sepolia/v0.7.34",
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


def build_query_for_licenses(ADDRESS: str, BLOCK_NUMBER: int = MAX_BLOCK_NUMBER) -> str:
    """Generate the GraphQL query"""
    return f"""
    {{
        shareProposalDatas(
            first: 1000
            orderBy: licenseId
            where: {{
                or: [
                    {{ rTokenHolders_: {{ holder: "{ADDRESS}", amount_gt: 0 }}, operatorString_not: "TO_BE_REPLACED", status_not: ENDED }}
                    {{ wTokenHolders_: {{ holder: "{ADDRESS}", amount_gt: 0 }}, operatorString_not: "TO_BE_REPLACED", status_not: ENDED }}
                    {{ operator: "{ADDRESS}", operatorString_not: "TO_BE_REPLACED", status_not: ENDED }}
                ]
            }}
            block: {{ number: {BLOCK_NUMBER} }}
        ) {{
            proposalId
            shareNumberId
            chypcId
            licenseId
            rTokenId
            wTokenId
            operator
            operatorString
            shareToken {{
                    shareMessage
                    messageChanged (orderBy: blockTimestamp, orderDirection: asc) {{
                    newMessage
                    blockTimestamp
                }}
            }}
        }}
    }}
    """


async def get_licenses_data(
    user_address: str, cache_dir: str = "licenses_data_cache"
) -> List[ProposalData]:

    # Create cache directory if it doesn't exist
    Path(cache_dir).mkdir(exist_ok=True)

    # Normalize address for filename
    normalized_address = user_address.lower()
    cache_file = os.path.join(cache_dir, f"{normalized_address}.json")

    # Check if cached data exists
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                cached_data = json.load(f)
            print(f"Loaded cached licenses data for {user_address}")
            return cached_data
        except Exception as e:
            print(f"Error loading cache for {user_address}: {e}")
            print("Fetching fresh data...")

    # Fetch fresh data if no cache or cache failed
    query = build_query_for_licenses(user_address)

    async with ClientSession() as session:
        res = await query_subgraph(
            session,
            SUBGRAPHS["mainnet"]["ethereum"],
            query,
        )

        if not res or res.get("data", None) is None:
            raise RuntimeError("Not valid subgrah response")

        # Results
        results = res["data"]["shareProposalDatas"]

        # Save to cache
        try:
            with open(cache_file, "w") as f:
                json.dump(results, f, indent=2)
            print(f"Cached user licenses data for {user_address}")
        except Exception as e:
            print(f"Error saving user licenses cache for {user_address}: {e}")

        return results
