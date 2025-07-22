#!/usr/bin/env python3
import argparse
import asyncio
import json
from eth_account import Account
from eth_account.messages import encode_defunct
from aiohttp import ClientSession, ClientError
from typing import Optional, List, Dict, Any, Tuple


class ScriptArgs(argparse.Namespace):
    license_anfe: str
    node_url: str
    private_key: str
    testnet: bool


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


def build_query(token_id: str) -> str:
    """Generate the GraphQL query for license/anfe data"""
    return f"""
    {{
        anfetokens(where: {{tokenId: "{token_id}", isBurned: false }}) {{
            delegatedSigner
            owner {{
                id
            }}
            license {{
                hasRequiredBacking
                chypcTokensBacking {{
                    tokenId
                }}
            }}
        }}
        licenseToken(id: "{token_id}") {{
            owner {{
                id
            }}
            hasRequiredBacking
            chypcTokensBacking {{
                tokenId
            }}
        }}
    }}
    """


async def fetch_all_networks(
    session: ClientSession, networks: Dict[str, str], token_id: str
) -> List[Dict[str, Any]]:
    """Query multiple networks in parallel"""
    query = build_query(token_id)
    tasks = []

    for chain_name, url in networks.items():
        print(f"🔍 Querying {chain_name}...")
        tasks.append(query_subgraph(session, url, query))

    return await asyncio.gather(*tasks)


def sign_message(private_key: str, message: str) -> dict:
    """Secure message signing without Web3.py"""
    if not private_key.startswith("0x"):
        private_key = "0x" + private_key

    encoded_msg = encode_defunct(text=message)
    signed = Account.sign_message(encoded_msg, private_key)

    return {
        "message": message,
        "signature": signed.signature.hex(),
        "address": signed.address,
    }


def determine_valid_data(
    results: list, networks: Dict
) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Determine whether to use ANFE or License data based on priority rules.
    Returns (valid_data, chain_name) or (None, None)
    """
    # for chain_name, result in results:
    for chain_name, result in zip(networks.keys(), results):
        if not result or not result.get("data"):
            continue

        data = result["data"]

        # Priority 1: Use ANFE if exists
        if data["anfetokens"]:
            anfe = data["anfetokens"][0]
            return {
                "type": "ANFE",
                "owner": anfe["owner"]["id"],
                "delegated_signer": anfe["delegatedSigner"],
                "has_required_backing": anfe["license"]["hasRequiredBacking"],
                "backing_tokens": [
                    t["tokenId"] for t in anfe["license"]["chypcTokensBacking"]
                ],
            }, chain_name

        # Priority 2: Use License if exists
        if data["licenseToken"]:
            license = data["licenseToken"]
            return {
                "type": "LICENSE",
                "owner": license["owner"]["id"],
                "has_required_backing": license["hasRequiredBacking"],
                "backing_tokens": [t["tokenId"] for t in license["chypcTokensBacking"]],
            }, chain_name

    return None, None


async def main():
    parser = argparse.ArgumentParser(
        description="Node Interactor - Manager Mode",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--license-anfe", required=True, help="License or ANFE to assign"
    )
    parser.add_argument(
        "--node-url", required=True, help="Hypercycle node HTTP endpoint"
    )
    parser.add_argument(
        "--private-key", required=True, help="0x-prefixed hex private key"
    )
    parser.add_argument(
        "--testnet",
        action="store_true",
        help="Use testnet subgraphs",
    )

    # FIXME: Improve the type hinting
    args: ScriptArgs = parser.parse_args()  # type: ignore

    # Security warning
    print("⚠️ WARNING: Never expose private keys in production environments!")

    if not args.private_key.startswith("0x"):
        args.private_key = "0x" + args.private_key

    # Use networks based on flag
    networks = SUBGRAPHS["testnet"] if args.testnet else SUBGRAPHS["mainnet"]
    print(f"🌐 Using {'testnet' if args.testnet else 'mainnet'}")

    async with ClientSession() as session:
        results = await fetch_all_networks(session, networks, args.license_anfe)
        validated_data = determine_valid_data(results, networks)
        
    if not validated_data[0] or not validated_data[1]:
        print("❌ No valid data found for the provided ANFE or License.")
        return

    print("🔍 Validated data:")
    print(json.dumps(validated_data, indent=2))

    # # 1. Sign message
    # signed_data = sign_message(args.private_key, args.message)
    # print(f"✅ Signed message:\n{json.dumps(signed_data, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
