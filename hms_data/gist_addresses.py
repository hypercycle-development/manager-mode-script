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

                return [addr.lower() for addr in tranche1_addresses_content.splitlines()]
                # return tranche1_addresses_content.splitlines()
        except ClientError as e:
            print(f"Error fetching gist: {e}")
            return []
