from aiohttp import ClientSession, ClientError
from common import HTS_NODES, USDC_CONTRACT_ADDRESS, ETHERSCAN_API_KEY
from typing import List, Dict, Any
import asyncio


async def get_address_from_node(node_url: str) -> str:
    async with ClientSession() as session:
        try:
            async with session.get(node_url, timeout=30) as response:
                response.raise_for_status()
                node_data = await response.json()
                return (
                    node_data.get("tm", {}).get("address", "").lower()
                )  # Normalize to lowercase
        except (ClientError, asyncio.TimeoutError) as e:
            print(f"Error fetching node data from {node_url}: {e}")
            return ""


async def get_all_usdc_transactions(address: str) -> List[Dict[str, Any]]:
    """Get all USDC transactions for an address"""
    async with ClientSession() as session:
        try:
            url = f"https://api.etherscan.io/api?module=account&action=tokentx&address={address}&contractaddress={USDC_CONTRACT_ADDRESS}&apikey={ETHERSCAN_API_KEY}"
            async with session.get(url, timeout=30) as response:
                response.raise_for_status()
                data = await response.json()

                if data.get("status") == "1":
                    return data.get("result", [])
                else:
                    print(f"Etherscan API error: {data.get('message')}")
                    return []

        except (ClientError, asyncio.TimeoutError) as e:
            print(f"Error fetching transactions for {address}: {e}")
            return []


async def get_deposits(user_address: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Find all USDC deposits from user_address to any HTS node
    Returns: {node_name: [list_of_transaction_objects]}
    """
    # Normalize addresses for comparison
    user_address = user_address.lower()
    node_addresses = {
        node_data["address"].lower(): node_name
        for node_name, node_data in HTS_NODES.items()
    }

    # Get all USDC transactions for the user
    all_user_transactions = await get_all_usdc_transactions(user_address)

    if not all_user_transactions:
        print(f"No USDC transactions found for address: {user_address}")
        return {}

    # Filter for deposits to HTS nodes
    results = {}

    for transaction in all_user_transactions:
        # Normalize transaction addresses
        tx_from = transaction.get("from", "").lower()
        tx_to = transaction.get("to", "").lower()

        # Check if this is an OUTGOING transaction FROM user TO a known HTS node
        if tx_from == user_address and tx_to in node_addresses:
            node_name = node_addresses[tx_to]

            if node_name not in results:
                results[node_name] = []

            results[node_name].append(transaction)

    return results
