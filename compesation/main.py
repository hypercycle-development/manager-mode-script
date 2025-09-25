import asyncio
import time
import json
import os
from datetime import datetime
from typing import Dict, List, Union
from web3 import Web3
from web3.exceptions import BlockNotFound, TransactionNotFound
from gist_addresses import fetch_gist_addresses
from user_deposits import get_transfers, get_user_node_data
from order_data import (
    calculate_end_balance_per_node,
    calculate_total_balance,
    calculate_end_balance_by_node_real,
    calculate_total_balance_real,
    get_data_from_interactions,
)
from subgraph import get_licenses_data
from common import USDC_CONTRACT_ADDRESS, tranche1_addresses_gist_id, MAX_TIMESTAMP_UTC
from app_types import (
    DepositResponse,
    GetTransferResponse,
    TransferTx,
    UserNodeData,
    Interaction,
)
from merklizer_interact import LicenseUptimeCalculator


class HTSCompensationProcessor:
    def __init__(self, cache_file: str = "hts_compensation_cache.json"):
        self.cache_file = cache_file
        self.results_cache = self.load_cache()

    def load_cache(self) -> Dict:
        """Load existing results from JSON cache file"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    cache = json.load(f)
                    print(
                        f"Loaded cache with {len(cache.get('processed_addresses', {}))} previously processed addresses"
                    )
                    return cache
            except Exception as e:
                print(f"Error loading cache: {e}")
                return self._create_empty_cache()
        else:
            print("No cache file found, starting fresh")
            return self._create_empty_cache()

    def _create_empty_cache(self) -> Dict:
        """Create empty cache structure"""
        return {
            "processed_addresses": {},
            "total_compensation": 0.0,
            "total_balance_to_hms": 0.0,
            "last_updated": None,
            "processing_stats": {
                "total_addresses": 0,
                "successful": 0,
                "errors": 0,
                "skipped": 0,
            },
        }

    def save_cache(self):
        """Save current results to JSON cache file"""
        self.results_cache["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.results_cache, f, indent=2)
            print(f"Cache saved to {self.cache_file}")
        except Exception as e:
            print(f"Error saving cache: {e}")

    def is_address_processed(self, address: str) -> bool:
        """Check if address was already processed successfully"""
        return address.lower() in self.results_cache["processed_addresses"]

    def add_address_result(
        self,
        address: str,
        compensation_amount: float,
        total_balance: float,
        final_balance: str,
        error: str = None,
        license_count: int = 0,
        processing_time: float = 0,
    ):
        """Add address processing result to cache"""
        self.results_cache["processed_addresses"][address.lower()] = {
            "address": address,
            "compensation_amount_usd": compensation_amount,
            "total_balance_usdc": str(total_balance),
            "final_balance": str(final_balance),
            "license_count": license_count,
            "processing_time_seconds": processing_time,
            "processed_at": datetime.now().isoformat(),
            "error": error,
        }

        # Update total compensation (only if no error)
        if error is None:
            self.recalculate_totals()

        # Update stats
        if error is None:
            self.results_cache["processing_stats"]["successful"] += 1
        else:
            self.results_cache["processing_stats"]["errors"] += 1

    def recalculate_totals(self):
        """Recalculate total compensation from all successful entries"""
        total = 0.0
        total_hms = 0.0
        for addr_data in self.results_cache["processed_addresses"].values():
            if addr_data.get("error") is None:
                total += addr_data.get("compensation_amount_usd", 0)
                total_hms += float(addr_data.get("final_balance", 0))
        self.results_cache["total_compensation"] = total
        self.results_cache["total_balance_to_hms"] = total_hms

    async def process_address(self, address: str) -> Union[Dict, None]:
        """Process a single address and return compensation data"""
        start_time = time.time()

        try:
            print(f"\n{'='*60}")
            print(f"Processing address: {address}")

            # Get transfer data
            transfer_txs = await get_transfers(address)
            nodes_deposits_txs = transfer_txs["nodes"]
            refunds_txs = transfer_txs["refunds"]

            # User node data
            user_node_data = await get_user_node_data(address, nodes_deposits_txs)

            # # Old calculated
            # calculated_balances = calculate_end_balance_per_node(user_node_data)
            # print(f"calculated_balances: {calculated_balances}")

            # total_balance = calculate_total_balance(
            #     user_node_data, calculated_balances, refunds_txs
            # )
            # print(f"total_balance: {total_balance}")

            # New calculated
            real_end_balances = calculate_end_balance_by_node_real(user_node_data)
            print(f"real_end_balances: {real_end_balances}")
            total_balance_real = calculate_total_balance_real(
                real_end_balances, refunds_txs
            )
            print(f"total_balance_real: {total_balance_real}")

            # Get licenses from subgraph
            licenses_data = await get_licenses_data(address)

            if not licenses_data:
                print(f"No licenses found for {address}")
                return {
                    "compensation_amount_usd": 0.0,
                    "total_balance_usdc": total_balance_real / 1_000_000,
                    "final_balance": total_balance_real / 1_000_000,
                    "license_count": 0,
                    "processing_time": time.time() - start_time,
                    "error": None,
                }

            # Calculate HTS compensation
            calculator = LicenseUptimeCalculator()
            compensation_report = calculator.calculate_hts_compensation(
                licenses_data, address
            )

            processing_time = time.time() - start_time

            result = {
                "compensation_amount_usd": compensation_report[
                    "compensation_amount_usd"
                ],
                "total_balance_usdc": total_balance_real / 1_000_000,
                # The compensation calculated (using ERC20 with 6 decimals). Mainly because the Node balances comes like that
                "final_balance": (
                    total_balance_real
                    + compensation_report["compensation_amount_usd"] * 1_000_000
                )
                / 1_000_000,
                "license_count": len(licenses_data),
                "processing_time": processing_time,
                "error": None,
                "detailed_report": compensation_report,
            }

            print(f"✅ Address {address} processed successfully")
            print(f"   Compensation: ${result['compensation_amount_usd']:.2f}")
            print(f"   Balance (all nodes): ${result['total_balance_usdc']:.2f}")
            print(f"   Final balance (to HMS): ${result['final_balance']:.2f}")
            print(f"   Licenses: {result['license_count']}")
            print(f"   Time: {processing_time:.1f}s")

            return result

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Error processing {address}: {str(e)}"
            import traceback

            traceback.print_exc()
            print(f"❌ {error_msg}")
            return None

            return {
                "compensation_amount_usd": 0.0,
                "total_balance_usdc": 0.0,
                "license_count": 0,
                "processing_time": processing_time,
                "error": error_msg,
            }

    async def process_all_addresses(self, resume_from_cache: bool = True):
        """Process all HTS Tranche1 addresses with caching"""

        # Get all addresses
        print("Fetching HTS Tranche1 addresses...")
        t1_addresses = await fetch_gist_addresses(tranche1_addresses_gist_id)

        # t1_addresses = [t1_addresses[0]]
        # t1_addresses = ["0x029e40e8d0c181BA7445B2c27060386e45A63F85"]

        self.results_cache["processing_stats"]["total_addresses"] = len(t1_addresses)

        print(f"\nFound {len(t1_addresses)} addresses to process")
        if resume_from_cache:
            already_processed = sum(
                1 for addr in t1_addresses if self.is_address_processed(addr)
            )
            print(f"Already processed: {already_processed}")
            print(f"Remaining: {len(t1_addresses) - already_processed}")

        # Process each address
        for i, address in enumerate(t1_addresses, 1):
            print(f"\n[{i}/{len(t1_addresses)}] ", end="")

            # Skip if already processed (unless resume_from_cache is False)
            if resume_from_cache and self.is_address_processed(address):
                print(f"Skipping {address} (already processed)")
                self.results_cache["processing_stats"]["skipped"] += 1
                continue

            # Process the address
            result = await self.process_address(address)

            if result is not None:
                # Add to cache
                self.add_address_result(
                    address=address,
                    compensation_amount=result["compensation_amount_usd"],
                    total_balance=result["total_balance_usdc"],
                    final_balance=result["final_balance"],
                    error=result["error"],
                    license_count=result["license_count"],
                    processing_time=result["processing_time"],
                )

            # Save cache every 10 addresses
            if i % 10 == 0:
                self.save_cache()
                self.print_progress_summary()

        # Final save
        self.save_cache()
        self.print_final_summary()

    def print_progress_summary(self):
        """Print current progress summary"""
        stats = self.results_cache["processing_stats"]
        print(f"\n--- PROGRESS SUMMARY ---")
        print(f"Total addresses: {stats['total_addresses']}")
        print(f"Successful: {stats['successful']}")
        print(f"Errors: {stats['errors']}")
        print(f"Skipped (cached): {stats['skipped']}")
        print(
            f"Current total compensation: ${self.results_cache['total_compensation']:.2f}"
        )
        print(
            f"Current total to HMS: ${self.results_cache['total_balance_to_hms']:.2f}"
        )

    def print_final_summary(self):
        """Print final processing summary"""
        stats = self.results_cache["processing_stats"]

        print(f"\n{'='*60}")
        print("FINAL HTS COMPENSATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total addresses processed: {stats['successful']}")
        print(f"Addresses with errors: {stats['errors']}")
        print(
            f"Total compensation amount: ${self.results_cache['total_compensation']:.2f}"
        )
        print(
            f"Current total to HMS: ${self.results_cache['total_balance_to_hms']:.2f}"
        )

        # Top compensations
        successful_addresses = [
            data
            for data in self.results_cache["processed_addresses"].values()
            if data.get("error") is None and data.get("compensation_amount_usd", 0) > 0
        ]

        if successful_addresses:
            top_compensations = sorted(
                successful_addresses,
                key=lambda x: x.get("compensation_amount_usd", 0),
                reverse=True,
            )[:50]

            print(f"\nTop 10 compensations:")
            for i, addr_data in enumerate(top_compensations, 1):
                print(
                    f"{i:2d}. {addr_data['address']}: ${addr_data['compensation_amount_usd']:.2f}"
                )

    def export_results(self, filename: str = None):
        """Export results to a CSV file"""
        if filename is None:
            filename = f"hts_compensation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        import csv

        with open(filename, "w", newline="") as csvfile:
            fieldnames = [
                "address",
                "compensation_amount_usd",
                "total_balance_usdc",
                "final_balance",
                "license_count",
                "processing_time_seconds",
                "processed_at",
                "error",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for addr_data in self.results_cache["processed_addresses"].values():
                writer.writerow(addr_data)

        print(f"Results exported to {filename}")


async def main():
    """Main processing function"""
    processor = HTSCompensationProcessor()

    # Process all addresses (will resume from cache by default)
    await processor.process_all_addresses(resume_from_cache=True)

    # Export results to CSV
    processor.export_results()


if __name__ == "__main__":
    asyncio.run(main())
