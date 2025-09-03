import asyncio
import time
from web3 import Web3
from web3.exceptions import BlockNotFound, TransactionNotFound
from typing import Literal
from gist_addresses import fetch_gist_addresses
from user_deposits import get_transfers, get_node_deposits
from common import USDC_CONTRACT_ADDRESS, tranche1_addresses_gist_id
from datetime import datetime

# from eth_utils import is_checksum_address, to_checksum_address


async def main():
    # # Get all the HTS Tranche1 address
    # t1_addresses = await fetch_gist_addresses(tranche1_addresses_gist_id)
    address = "0x7b724C7cF60d4CEddAc00BE64f23E0c97C170182"
    # address = "0xA2Ace3F96851B825af9dcca4b19d648742bBddC6"

    nodes_transfers = await get_transfers(address)

    print(f"\n=== DEPOSITS FOUND ===")
    total_deposits = 0

    # Sort by node name for consistent ordering
    for node_name in sorted(nodes_transfers.keys()):
        transactions = nodes_transfers[node_name]
        print(f"\n{node_name}: {len(transactions)} deposit(s)")
        total_deposits += len(transactions)

        for i, tx in enumerate(transactions, 1):
            amount = int(tx["value"]) / 10**6
            timestamp = int(tx.get("timeStamp", 0))

            # Convert Unix timestamp to human-readable date
            if timestamp:
                date_str = datetime.fromtimestamp(timestamp).strftime(
                    "%Y-%m-%d %H:%M:%S UTC"
                )
            else:
                date_str = "N/A"

            print(f"  {i}. TX Hash: {tx['hash']}")
            print(f"     Block: {tx['blockNumber']}")
            print(f"     Amount: {amount:,.2f} USDC")
            print(f"     Date: {date_str}")
            print(f"     From: {Web3.to_checksum_address(tx['from'])}")
            print(f"     To: {Web3.to_checksum_address(tx['to'])}")
            print()

    print(f"Total deposits across all HTS nodes: {total_deposits}")


if __name__ == "__main__":
    asyncio.run(main())
