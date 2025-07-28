import asyncio
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
