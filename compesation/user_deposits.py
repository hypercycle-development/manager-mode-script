from aiohttp import ClientSession, ClientError
from common import (
    HTS_NODES,
    USDC_CONTRACT_ADDRESS,
    HYPC_CONTRACT_ADDRESS,
    REFUND_WALLET_ADDRESS,
    ETHERSCAN_API_KEY,
)
from typing import List, Dict, Any
from app_types import DepositResponse, GetTransferResponse, TransferTx
import asyncio


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


async def get_user_balance_node(node_url: str, user_address: str) -> int | None:
    async with ClientSession() as session:
        try:
            async with session.get(f"{node_url}/balances", timeout=30) as response:
                response.raise_for_status()
                data = await response.json()

                return data.get("users_balance", {}).get(user_address, None)

        except (ClientError, asyncio.TimeoutError) as e:
            print(f"Error fetching balance from {node_url}: {e}")
            return 0


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


async def get_transfers(user_address: str) -> GetTransferResponse:
    """
    Find all USDC deposits from user_address to any HTS node
    And organize it between nodes and the type: To Node, Refund
    """
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

        # Check if this is a REFUND transaction (from refund wallet to user)
        elif tx_from == REFUND_WALLET_ADDRESS.lower() and tx_to == user_address:
            if "refunds" not in results:
                results["refunds"] = []

            results["refunds"].append(TransferTx(**transaction))

    return results


async def get_user_node_data(user_address: str, transfers: Dict[str, List[TransferTx]]):
    user_deposits = {"confirmed": [], "missing": []}
    results = {}
    import json

    print("\n === CHECKING NODE DEPOSITS ===")
    for node_name, transactions in sorted(transfers.items()):
        # Individual node URL
        node_url = HTS_NODES[node_name]["url"]

        # Initialize results for this node
        results[node_name] = {}

        print(f" \n --- Fetching data from {node_name} at {node_url}...")

        # Get user balance on the node
        user_balance = await get_user_balance_node(node_url, user_address)
        results[node_name]["user_balance"] = user_balance

        print(f"User balance on {node_name}: {json.dumps(user_balance, indent=2)}")

        user_deposits = await get_user_deposits_node(node_url, user_address)

        total_registered = len(user_deposits["data"])

        if total_registered == len(transactions):
            results[node_name]["registered_deposits"] = user_deposits["data"]
            print(f"All deposits already recorded on {node_name}.")
            continue
        else:
            # TODO: If there are missing deposits, should be counted and added as compensation
            print(
                f"Deposits on {node_name} differ: {total_registered} recorded vs {len(transactions)} found."
            )

            # Extract recorded transaction hashes
            recorded_hashes = {tx["_id"].lower() for tx in user_deposits["data"]}

            # Filter out transactions that are not recorded
            unrecorded_transactions = [
                tx for tx in transactions if tx["hash"].lower() not in recorded_hashes
            ]

            print(f"Total recorded txs: {(recorded_hashes)}")
            print(f"Total not recorded: {len(unrecorded_transactions)}")
            print(f"txs not recorded: {json.dumps(unrecorded_transactions, indent=2)}")

        # if response["total_count"] == 0:
        #     print(f"No deposits found on {node_name}.")
        #     continue

        print(f"Deposits found on {node_name}: {total_registered}")
        for deposit in user_deposits["data"]:
            print(
                f"  Deposit ID: {deposit['_id']}, Amount: {int(deposit['value']) / 10**6} {deposit['currency_type']}, Status: {deposit['status']}"
            )

    pass
