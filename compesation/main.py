import asyncio
import time
from web3 import Web3
from web3.exceptions import BlockNotFound, TransactionNotFound
from typing import Literal
from gist_addresses import fetch_gist_addresses
from user_deposits import get_transfers, get_user_node_data
from order_data import (
    calculate_end_balance_per_node,
    calculate_total_balance,
    get_data_from_interactions,
)
from subgraph import get_licenses_data
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

    # transfer_txs = await get_transfers(address)
    # nodes_deposits_txs = transfer_txs["nodes"]
    # refunds_txs = transfer_txs["refunds"]

    # user_node_data = await get_user_node_data(address, nodes_deposits_txs)

    # calculated_balances = calculate_end_balance_per_node(user_node_data)

    # total_balance = calculate_total_balance(
    #     user_node_data, calculated_balances, refunds_txs
    # )

    # print(f"Total balance END: {total_balance}")
    # print("-" * 20)

    # licenses, tillers_created = get_data_from_interactions(user_node_data)

    # print("- LICENSES:")
    # print(sorted(licenses))
    # print(f"tillers_created: {tillers_created}")
    
    licenses_data = await get_licenses_data(address)
    
    print(json.dumps(licenses_data, indent=2))
    
    


if __name__ == "__main__":
    asyncio.run(main())
