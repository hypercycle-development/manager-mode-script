import asyncio
import time
from web3 import Web3
from web3.exceptions import BlockNotFound, TransactionNotFound
from typing import Literal
from gist_addresses import fetch_gist_addresses

USDC_CONTRACT_ADDRESS = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
tranche1_addresses_gist_id = "1d91a306014cab0eefea297feab97e54"


async def main():
    # Get all the HTS Tranche1 address
    t1_addresses = await fetch_gist_addresses(tranche1_addresses_gist_id)


if __name__ == "__main__":
    asyncio.run(main())
