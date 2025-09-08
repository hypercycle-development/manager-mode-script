import asyncio
import time
from web3 import Web3
from web3.exceptions import BlockNotFound, TransactionNotFound
from typing import Literal
from gist_addresses import fetch_gist_addresses
from user_deposits import get_transfers, get_user_node_data
from common import USDC_CONTRACT_ADDRESS, tranche1_addresses_gist_id
from datetime import datetime

# from eth_utils import is_checksum_address, to_checksum_address


async def main():
    # # Get all the HTS Tranche1 address
    # t1_addresses = await fetch_gist_addresses(tranche1_addresses_gist_id)
    # address = "0x7b724C7cF60d4CEddAc00BE64f23E0c97C170182"
    address = "0x181615a6889e7cCD2DD4bf4375836351060704Db"
    # address = "0xA2Ace3F96851B825af9dcca4b19d648742bBddC6"
    # address = "0xDf16f62824Ad0373DBb271FF7C3b81a6Ce119dEd"

    transfer_txs = await get_transfers(address)
    nodes_deposits_txs = transfer_txs["nodes"]
    refunds_txs = transfer_txs["refunds"]
    
    print(f"Refunds found: {len(refunds_txs)}")
    import json
    print(f"Refunds: {json.dumps(refunds_txs, indent=2)}")
    
    # print(json.dumps(transfer_txs, indent=4))

    response = await get_user_node_data(address, nodes_deposits_txs)

    # total_deposits = 0
    # print(f"\n=== DEPOSITS FOUND ===")
    # # Sort by node name for consistent ordering
    # for node_name in sorted(nodes_transfers["nodes"].keys()):
    #     transactions = nodes_transfers["nodes"][node_name]
    #     print(f"\n{node_name}: {len(transactions)} deposit(s)")
    #     total_deposits += len(transactions)

    #     for i, tx in enumerate(transactions, 1):
    #         amount = int(tx["value"]) / 10**6
    #         timestamp = int(tx.get("timeStamp", 0))

    #         # Convert Unix timestamp to human-readable date
    #         if timestamp:
    #             date_str = datetime.fromtimestamp(timestamp).strftime(
    #                 "%Y-%m-%d %H:%M:%S UTC"
    #             )
    #         else:
    #             date_str = "N/A"

    #         print(f"  {i}. TX Hash: {tx['hash']}")
    #         print(f"     Block: {tx['blockNumber']}")
    #         print(f"     Amount: {amount:,.2f} USDC")
    #         print(f"     Date: {date_str}")
    #         print(f"     From: {Web3.to_checksum_address(tx['from'])}")
    #         print(f"     To: {Web3.to_checksum_address(tx['to'])}")
    #         print()

    # print(f"Total deposits across all HTS nodes: {total_deposits}")

    # print(f"Total refunds: {len(refunds)}")


if __name__ == "__main__":
    asyncio.run(main())
