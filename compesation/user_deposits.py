from aiohttp import ClientSession, ClientError
from common import (
    HTS_NODES,
    USDC_CONTRACT_ADDRESS,
    HYPC_CONTRACT_ADDRESS,
    REFUND_WALLET_ADDRESSES_SET,
    ETHERSCAN_API_KEY,
    MAX_BLOCK_NUMBER,
)
from typing import List, Dict, Any
from app_types import (
    DepositResponse,
    GetTransferResponse,
    TransferTx,
    UserNodeData,
    Interaction,
)
import asyncio
import json
import os
from pathlib import Path
import hashlib

async def get_user_deposits_node(node_url: str, user_address: str) -> DepositResponse:
    async with ClientSession() as session:
        try:
            # It's very unlikely to have more than 100 deposits (atm)
            async with session.get(
                f"{node_url}/deposits?sender={user_address}&page_size=100", timeout=30
            ) as response:
                response.raise_for_status()
                return await response.json()
        except (ClientError, asyncio.TimeoutError) as e:
            print(f"Error fetching node data from {node_url}: {e}")
            return DepositResponse(data=[], total_count=0)


async def get_user_balance_node(
    node_url: str,
    user_address: str,
    cache_dir: str = "user_node_balance_cache",
) -> Dict[str, int]:
    # Normalize address for filename
    normalized_address = user_address.lower()
    
    # node_url_filename = str(hash(node_url.lower()))
    node_url_filename = hashlib.sha256(node_url.encode('utf-8')).hexdigest()
    cache_file = os.path.join(cache_dir, f"{normalized_address}_{node_url_filename}.json")

    # Check if cached data exists
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                cached_data = json.load(f)
            print(f"Loaded cached user node balance for {user_address}")
            return cached_data
        except Exception as e:
            print(f"Error loading user node balance cache for {user_address}: {e}")
            print("Fetching fresh user node balance...")

    async with ClientSession() as session:
        try:
            async with session.get(f"{node_url}/balances", timeout=30) as response:
                response.raise_for_status()
                data = await response.json()

                results = data.get("users_balance", {}).get(user_address, {})

                # Save to cache
                try:
                    with open(cache_file, "w") as f:
                        json.dump(results, f, indent=2)
                    print(f"Cached user node balance data for {user_address}")
                except Exception as e:
                    print(
                        f"Error saving user node balance cache for {user_address}: {e}"
                    )

                return results

        except (ClientError, asyncio.TimeoutError) as e:
            print(f"Error fetching balance from {node_url}: {e}")
            raise Exception(f"No response: {e}")


async def get_user_interactions(node_url: str, user_address: str) -> List[Interaction]:
    all_interactions = []
    page = 1
    page_size = 100

    async with ClientSession() as session:
        while page <= 10:
            try:
                async with session.get(
                    f"{node_url}/interactions?user_address={user_address}&page_size={page_size}&page={page}",
                    timeout=30,
                ) as response:
                    response.raise_for_status()
                    interactions = await response.json()

                    if not interactions or len(interactions) == 0:
                        break

                    # Add the fetched interactions to the main list
                    all_interactions.extend(interactions)

                    if len(interactions) < page_size:
                        break

            except (ClientError, asyncio.TimeoutError) as e:
                print(f"Error fetching interactions from {node_url}: {e}")
                return []

            page += 1
            await asyncio.sleep(0.2)

    return sorted(all_interactions, key=lambda x: x["timestamp"])


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
                    f"endblock={MAX_BLOCK_NUMBER}"
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


async def get_all_hypc_transactions(
    address: str, max_pages: int = 100
) -> List[Dict[str, Any]]:
    """Get all HyPC transactions for an address with pagination"""
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
                    f"&contractaddress={HYPC_CONTRACT_ADDRESS}"
                    f"&page={page}"
                    f"&offset={offset}"
                    f"endblock={MAX_BLOCK_NUMBER}"
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


async def get_transfers(
    user_address: str, cache_dir: str = "transfer_cache"
) -> GetTransferResponse:
    """
    Find all USDC deposits from user_address to any HTS node
    And organize it between nodes and the type: To Node, Refund
    """
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
            print(f"Loaded cached transfer data for {user_address}")
            return GetTransferResponse(**cached_data)
        except Exception as e:
            print(f"Error loading cache for {user_address}: {e}")
            print("Fetching fresh data...")

    # Fetch fresh data if no cache or cache failed
    # Normalize addresses for comparison
    user_address = user_address.lower()
    node_addresses = {
        node_data["address"].lower(): node_name
        for node_name, node_data in HTS_NODES.items()
    }

    # Get all USDC and HyPC transactions for the user
    all_user_usdc_transactions = await get_all_usdc_transactions(user_address)
    all_user_hypc_transactions = await get_all_hypc_transactions(user_address)

    all_user_transactions = all_user_usdc_transactions + all_user_hypc_transactions

    if not all_user_transactions:
        print(f"No USDC-HyPC transactions found for address: {user_address}")

    # Filter for deposits to HTS nodes
    results = GetTransferResponse(nodes={}, refunds=[])

    for transaction in all_user_transactions:
        # Normalize transaction addresses
        tx_from = transaction.get("from", "").lower()
        tx_to = transaction.get("to", "").lower()

        # Check if this is an OUTGOING transaction FROM user TO a known HTS node
        if tx_from == user_address and tx_to in node_addresses:
            node_name = node_addresses[tx_to]

            if node_name not in results["nodes"]:
                results["nodes"][node_name] = []

            results["nodes"][node_name].append(TransferTx(**transaction))

        # Check if this is a REFUND transaction (from any refund wallet to user)
        elif tx_from in REFUND_WALLET_ADDRESSES_SET and tx_to == user_address:
            if "refunds" not in results:
                results["refunds"] = []

            results["refunds"].append(TransferTx(**transaction))

    # Save to cache
    try:
        with open(cache_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Cached transfer data for {user_address}")
    except Exception as e:
        print(f"Error saving cache for {user_address}: {e}")

    return results


async def get_user_node_data(
    user_address: str,
    transfers: Dict[str, List[TransferTx]],
    cache_dir: str = "user_node_cache",
) -> Dict[str, UserNodeData]:
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
            print(f"Loaded cached user node data for {user_address}")
            return cached_data
        except Exception as e:
            print(f"Error loading user node cache for {user_address}: {e}")
            print("Fetching fresh user node data...")

    # Fetch fresh data if no cache or cache failed
    results = {}

    for node_name, transactions in sorted(transfers.items()):
        # Individual node URL
        node_url = HTS_NODES[node_name]["url"]

        # Initialize results for this node
        results[node_name] = {}

        # Get user balance on the node
        user_balance = await get_user_balance_node(node_url, user_address)
        results[node_name]["user_balance"] = user_balance

        # Get user interactions on the node
        user_interactions = await get_user_interactions(node_url, user_address)
        results[node_name]["user_interactions"] = user_interactions

        # Get the user deposits
        user_deposits = await get_user_deposits_node(node_url, user_address)

        total_registered = len(user_deposits["data"])

        if total_registered == len(transactions):
            results[node_name]["registered_deposits"] = transactions
            results[node_name]["unregistered_deposits"] = []
            continue
        else:

            # Extract recorded transaction hashes
            recorded_hashes = {tx["_id"].lower() for tx in user_deposits["data"]}

            # Filter out transactions that are not recorded
            unrecorded_transactions = [
                tx for tx in transactions if tx["hash"].lower() not in recorded_hashes
            ]

            recorded_transactions = [
                tx for tx in transactions if tx["hash"].lower() in recorded_hashes
            ]

            results[node_name]["registered_deposits"] = recorded_transactions
            results[node_name]["unregistered_deposits"] = unrecorded_transactions

    # Save to cache
    try:
        with open(cache_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Cached user node data for {user_address}")
    except Exception as e:
        print(f"Error saving user node cache for {user_address}: {e}")

    return results
