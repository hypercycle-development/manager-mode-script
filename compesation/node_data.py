import os
import asyncio
import json
from pathlib import Path
from aiohttp import ClientSession, ClientError, ServerTimeoutError
from common import HTS_NODES
from typing import Tuple, Optional, List
from datetime import datetime


def decode_message(message: str) -> Tuple[str, str, str, str, str, str, Optional[str]]:
    """Decode a signature message into its components."""
    parts = message.split(";")

    if len(parts) == 6:
        return (parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], None)
    elif len(parts) == 7:
        return (parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6])
    else:

        raise ValueError(
            f"Invalid message format: expected 6 or 7 fields, got {len(parts)} - {message}"
        )


class TillerMessageCache:
    """Cache individual tiller messages to disk."""

    def __init__(self, cache_dir: str = "node_hts_tiller_cache/messages"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, node_url: str, number: int) -> str:
        """Generate cache key from node URL and number."""
        # Clean node_url to make it filesystem-safe
        node_key = (
            node_url.replace("http://", "")
            .replace("https://", "")
            .replace(":", "_")
            .replace("/", "_")
        )
        return f"{node_key}__{number}.json"

    def get(self, node_url: str, number: int) -> Optional[str]:
        """Get cached public key if available."""
        cache_file = self.cache_dir / self._get_cache_key(node_url, number)

        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)
                return data.get("public_key")
            except Exception:

                return None
        return None

    def set(self, node_url: str, number: int, public_key: str):
        """Cache a public key."""
        cache_file = self.cache_dir / self._get_cache_key(node_url, number)

        try:
            with open(cache_file, "w") as f:
                json.dump(
                    {"public_key": public_key, "cached_at": datetime.now().isoformat()},
                    f,
                )
        except Exception as e:
            import traceback

            traceback.print_exc()
            print(f"Warning: Failed to cache message {number}: {e}")


async def get_all_hts_public_keys(use_cache: bool = True) -> List[str]:
    """
    Fetch ALL HTS tiller public keys as a single flat list.

    Args:
        use_cache: Whether to use cached data if available

    Returns:
        List of all public keys from all nodes
    """
    cache_dir: str = "node_hts_tiller_cache"
    Path(cache_dir).mkdir(exist_ok=True)

    final_cache_file = os.path.join(cache_dir, "all_public_keys.json")

    # Try to load final result from cache
    if use_cache and os.path.exists(final_cache_file):
        try:
            with open(final_cache_file, "r") as f:
                cache_data = json.load(f)

            print(f"Loaded {len(cache_data['public_keys'])} cached public keys")
            print(f"Cached at: {cache_data['cached_at']}")
            return cache_data["public_keys"]
        except Exception as e:
            print(f"Error loading final cache: {e}, fetching data...")

    # Initialize message cache
    message_cache = TillerMessageCache()

    # Fetch fresh data
    print("Fetching ALL HTS tiller public keys from all nodes...")
    all_public_keys = []

    for node_name, node_data in HTS_NODES.items():
        print(f"\nProcessing node: {node_name}")
        node_url = node_data["url"]

        try:
            public_keys = await fetch_node_tillers(
                node_url, node_name, message_cache, use_cache
            )
            all_public_keys.extend(public_keys)
            print(f"  Retrieved {len(public_keys)} public keys")
        except Exception as e:
            import traceback

            traceback.print_exc()
            print(f"  Failed - {e}")

    # Remove duplicates
    unique_public_keys = list(set(all_public_keys))

    print(f"\nTotal public keys: {len(all_public_keys)}")
    print(f"Unique public keys: {len(unique_public_keys)}")

    # Save final result to cache
    cache_data = {
        "cached_at": datetime.now().isoformat(),
        "total_count": len(unique_public_keys),
        "public_keys": unique_public_keys,
    }

    try:
        with open(final_cache_file, "w") as f:
            json.dump(cache_data, f, indent=2)
        print(f"Cached to {final_cache_file}")
    except Exception as e:
        print(f"Error saving final cache: {e}")

    return unique_public_keys


async def fetch_node_tillers(
    node_url: str, node_name: str, message_cache: TillerMessageCache, use_cache: bool
) -> List[str]:
    """Fetch all tiller public keys from a single node."""
    list_url = f"{node_url}/aim/0/list"

    async with ClientSession() as session:
        async with session.get(list_url, timeout=900) as response:
            response.raise_for_status()
            data = await response.json()

            available: int = data.get("available", 0)
            tillers = data.get("tillers", [])
            tillers_len = len(tillers)
            total = available + tillers_len

            print(f"  Total tillers: {total}")

            if total == 0:
                return []

            public_keys = await fetch_public_keys_batch(
                node_url, total, session, message_cache, use_cache, batch_size=5
            )

            return public_keys


async def fetch_public_keys_batch(
    node_url: str,
    total: int,
    session: ClientSession,
    message_cache: TillerMessageCache,
    use_cache: bool,
    batch_size: int = 5,
) -> List[str]:
    """Fetch public keys in batches with per-message caching."""
    public_keys = []
    cached_count = 0
    fetched_count = 0

    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch_numbers = range(batch_start + 1, batch_end + 1)

        # Check cache first and prepare fetch tasks
        tasks = []
        for number in batch_numbers:
            if use_cache:
                cached_pk = message_cache.get(node_url, number)
                if cached_pk:
                    public_keys.append(cached_pk)
                    cached_count += 1
                    continue  # Skip to next number

            # Not in cache, need to fetch
            tasks.append(get_tiller_message(node_url, number, session, message_cache))

        # Fetch uncached messages
        if tasks:
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if not isinstance(result, Exception) and result:
                    public_keys.append(result)
                    fetched_count += 1

        print(
            f"  Progress: {batch_end}/{total} (cached: {cached_count}, fetched: {fetched_count})",
            end="\r",
        )

        if batch_end < total and tasks:
            await asyncio.sleep(0.3)

    print(
        f"  Progress: {total}/{total} (cached: {cached_count}, fetched: {fetched_count}) ✓"
    )
    return public_keys


async def get_tiller_message(
    node_url: str,
    number: int,
    session: ClientSession,
    message_cache: TillerMessageCache,
) -> Optional[str]:
    """Get public key for a specific tiller number and cache it."""
    url = f"{node_url}/aim/0/get_message?is_share=1&license=0&chypc=0&number={number}"

    try:
        async with session.get(url, timeout=900) as response:
            response.raise_for_status()
            data = await response.json()

            message: str = data.get("message", "")
            if not message:
                print(f"    Warning: Empty message for number {number}")
                return None

            if message == "invalid number":
                print(f"    Error: Invalid number: {number} -  Probably not allocated")
                return None

            _, public_key, _, _, _, _, _ = decode_message(message)

            if not public_key:
                print(f"    Warning: No public key extracted for number {number}")
                return None

            # Cache the result
            message_cache.set(node_url, number, public_key)

            return public_key

    except ServerTimeoutError as e:
        print(f"    Error fetching number {number} - ServerTimeoutError: {e}")

    except ClientError as e:
        print(f"    Error fetching number {number} - ClientError: {e}")

    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"    Error fetching number {number}: {e}")
    return None
