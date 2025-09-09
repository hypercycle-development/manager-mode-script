import asyncio
import time
from web3 import Web3
from web3.exceptions import BlockNotFound, TransactionNotFound
from typing import Literal
from gist_addresses import fetch_gist_addresses
from user_deposits import get_transfers, get_user_node_data
from order_data import calculate_end_balance
from common import USDC_CONTRACT_ADDRESS, tranche1_addresses_gist_id
from datetime import datetime
import json

from typing import List, Dict, Any
from app_types import (
    DepositResponse,
    GetTransferResponse,
    TransferTx,
    UserNodeData,
    Interaction,
)

# from eth_utils import is_checksum_address, to_checksum_address

# TODO: At the end, should look for deposits after Jan 1, 2025 and count them as missing deposits for compensation (no multiplier for these)


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

    user_node_data = await get_user_node_data(address, nodes_deposits_txs)

    calculated_balances = calculate_end_balance(user_node_data)

    # Sum all the balances into just one. We only will take care of the USDC.
    # Only get the Max between the balances comming from the user node data and calculated balacnes for each node

    total_balance = 0

    for node_name in calculated_balances:
        user_calculated_balance = calculated_balances[node_name]["USDC"]

        user_balance_data = user_node_data[node_name]["user_balance"]
        user_node_balance = 0

        if user_balance_data is not None:
            user_balance_data.get("USDC", 0)

        total_balance += max(user_calculated_balance, user_node_balance)

    print(f"Total balance before refunds and tx no registered: {total_balance}")

    unregistered_deposits: List[TransferTx] = []

    for data in user_node_data.values():
        to_save = [
            tx for tx in data["unregistered_deposits"] if tx["tokenSymbol"] == "USDC"
        ]

        unregistered_deposits.extend(to_save)

    for deposit in unregistered_deposits:
        total_balance += int(deposit["value"])

    print(f"Total balance before refunds: {total_balance}")

    for refunds in refunds_txs:
        if refunds["tokenSymbol"] == "USDC":
            total_balance -= int(refunds["value"])

    print(f"Total balance END1: {total_balance}")


if __name__ == "__main__":
    asyncio.run(main())
