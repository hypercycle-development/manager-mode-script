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


async def get_all_usdc_transactions(
    address: str, max_pages: int = 100
) -> List[Dict[str, Any]]:
    """Get all USDC transactions for an address with pagination"""
    all_transactions = []
    page = 1
    offset = 1000  # Max allowed by Etherscan is 10000, but 1000 is safer

    async with ClientSession() as session:
        while page <= max_pages:
            try:
                url = (
                    f"https://api.etherscan.io/api?module=account"
                    f"&action=tokentx"
                    f"&address={address}"
                    f"&contractaddress={USDC_CONTRACT_ADDRESS}"
                    f"&page={page}"
                    f"&offset={offset}"
                    f"&apikey={ETHERSCAN_API_KEY}"
                )

                async with session.get(url, timeout=30) as response:
                    response.raise_for_status()
                    data = await response.json()

                    if data.get("status") == "1":
                        transactions = data.get("result", [])
                        if not transactions:
                            break  # No more transactions

                        all_transactions.extend(transactions)

                        # If we got fewer than offset transactions, we've reached the end
                        if len(transactions) < offset:
                            break
                    else:
                        break

            except (ClientError, asyncio.TimeoutError) as e:
                print(f"Error fetching page {page} for {address}: {e}")
                break

            page += 1
            # Add a small delay to avoid rate limiting
            await asyncio.sleep(0.2)

    return all_transactions


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
