import os
import json
from aiohttp import ClientSession, ClientError


async def fetch_gist_addresses(gist_id: str) -> list[str]:
    url = f"https://api.github.com/gists/{gist_id}"
    async with ClientSession() as session:
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                gist_data = await response.json()
                files = gist_data.get("files", {})
                addresses = []

                tranche1_addresses_content: str = files.get(
                    "tranche1_addresses.txt", {}
                ).get("content", "")

                return tranche1_addresses_content.splitlines()

        except ClientError as e:
            print(f"Error fetching gist: {e}")
            return []


async def get_tranche1_hms_addresses() -> list[str]:
    """
    Get Tranche 1 addresses from local cache or fetch from gist.
    """
    cache_file = "user_addresses_t1/hms_tranche1_addresses.json"

    # Try to load from local file
    try:
        with open(cache_file, "r") as f:
            data = json.load(f)
            addresses = data.get("addresses", [])
            if addresses:
                print(f"Loaded {len(addresses)} addresses from local cache")
                return addresses
            raise ValueError("No addresses found in local cache")
    except Exception as e:
        print(f"Error loading local file of hms addresses")
        raise e
