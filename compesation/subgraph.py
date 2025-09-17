import argparse
import asyncio
import json
import sys
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils.address import to_checksum_address
from aiohttp import ClientSession, ClientError
from typing import Optional, List, Dict, Any, Tuple
from common import MAX_BLOCK_NUMBER
from app_types import ProposalData

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
                    {{ rTokenHolders_: {{ holder: "{ADDRESS}", amount_gt: 0 }} }}
                    {{ wTokenHolders_: {{ holder: "{ADDRESS}", amount_gt: 0 }} }}
                    {{ operator: "{ADDRESS}" }}
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


async def get_licenses_data(user_address: str) -> List[ProposalData]:
    query = build_query_for_licenses(user_address)

    async with ClientSession() as session:
        res = await query_subgraph(
            session,
            SUBGRAPHS["mainnet"]["ethereum"],
            query,
        )

        if not res or res.get("data", None) is None:
            raise RuntimeError("Not valid subgrah response")

        return res["data"]["shareProposalDatas"]
