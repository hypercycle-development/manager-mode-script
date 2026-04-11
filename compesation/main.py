import asyncio
import time
import json
import os
import sys
import requests
from datetime import datetime
from typing import Dict, List, Union
from web3 import Web3
from web3.exceptions import BlockNotFound, TransactionNotFound
from gist_addresses import fetch_gist_addresses, get_tranche1_hms_addresses
from user_deposits import get_transfers, get_user_node_data
from order_data import (
    calculate_end_balance_per_node,
    calculate_total_balance,
    calculate_end_balance_by_node_real,
    calculate_total_balance_real,
    get_data_from_interactions,
)
from subgraph import get_licenses_data, get_anfes_data, ProposalData
from common import USDC_CONTRACT_ADDRESS, tranche1_addresses_gist_id, MAX_TIMESTAMP_UTC
from app_types import (
    DepositResponse,
    GetTransferResponse,
    TransferTx,
    UserNodeData,
    Interaction,
)
from merklizer_interact import LicenseUptimeCalculator
from node_data import get_all_hts_public_keys


def check_public_key_in_message_optimized(
    message, json_file_path="node_hts_tiller_cache/all_public_keys.json"
):
    """
    Optimized version using any() for early termination.
    """
    try:
        with open(json_file_path, "r") as file:
            data = json.load(file)

        public_keys = data.get("public_keys", [])

        # Using any() with generator expression for early termination
        return any(public_key in message for public_key in public_keys)

    except FileNotFoundError:
        print(f"Error: File {json_file_path} not found")
        return False
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {json_file_path}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def check_licenses(licenses_data: List[ProposalData]) -> List[ProposalData]:
    licenses: List[ProposalData] = []
    if "--testing" in sys.argv:
        print("NOT CHECKING LICENSES WARNING")
        return licenses_data
    
       
    for license in licenses_data:

        messages = license["shareToken"]["messageChanged"]
        print("="*60)
        print(license)
        print(messages)
        if len(messages) > 0:
            message = messages[len(messages) - 1]["newMessage"]

        if message:
            if check_public_key_in_message_optimized(message):
                licenses.append(license)

    return licenses


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
            "total_creadit_bonus": 0.0,
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
        total_credit_bonus_amount: float,
        total_balance: float,
        final_balance: float,
        error: Union[str, None] = None,
        license_count: int = 0,
        processing_time: float = 0,
    ):
        """Add address processing result to cache"""
        self.results_cache["processed_addresses"][address.lower()] = {
            "address": address,
            "compensation_amount_usd": compensation_amount,
            "total_credit_bonus_amount": total_credit_bonus_amount,
            "total_balance_usdc": total_balance,
            "final_balance": round(final_balance, 2),
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
        total_credit_bonus = 0.0
        for addr_data in self.results_cache["processed_addresses"].values():
            if addr_data.get("error") is None:
                total += addr_data.get("compensation_amount_usd", 0)
                total_hms += addr_data.get("final_balance", 0)
                total_credit_bonus += addr_data.get("total_credit_bonus_amount", 0)
        self.results_cache["total_compensation"] = total
        self.results_cache["total_balance_to_hms"] = total_hms
        self.results_cache["total_creadit_bonus"] = total_credit_bonus

    async def process_address(self, address: str) -> Union[Dict, None]:
        """Process a single address and return compensation data"""
        start_time = time.time()

        try:
            print(f"\n{'='*60}")
            print(f"Processing address: {address}")

            # Get licenses from subgraph
            licenses_data = await get_licenses_data(address)

            licenses_data = check_licenses(licenses_data)
            # print(f"filtered_licenses LENGTH: {len(filtered_licenses)}")

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
            real_end_balances, total_credit_bonus_amount = (
                calculate_end_balance_by_node_real(user_node_data, licenses_data)
            )
            print(f"real_end_balances: {real_end_balances}")
            total_balance_real = calculate_total_balance_real(
                real_end_balances, refunds_txs
            )
            print(f"total_balance_real: {total_balance_real}")

            if not licenses_data:
                print(f"No licenses found for {address}")
                return {
                    "compensation_amount_usd": 0.0,
                    "total_credit_bonus_amount": total_credit_bonus_amount / 1_000_000,
                    "total_balance_usdc": total_balance_real / 1_000_000,
                    "final_balance": (
                        (total_balance_real * 1.5) + total_credit_bonus_amount
                    )
                    / 1_000_000,
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
                "total_credit_bonus_amount": total_credit_bonus_amount / 1_000_000,
                "total_balance_usdc": total_balance_real / 1_000_000,
                # The compensation calculated (using ERC20 with 6 decimals). Mainly because the Node balances comes like that
                "final_balance": (
                    (
                        total_balance_real * 1.5
                        + compensation_report["compensation_amount_usd"] * 1_000_000
                        + total_credit_bonus_amount
                    )
                )
                / 1_000_000,
                "license_count": len(licenses_data),
                "processing_time": processing_time,
                "error": None,
                "detailed_report": compensation_report,
            }

            print(f"✅ Address {address} processed successfully")
            print(f"   Compensation: ${result['compensation_amount_usd']:.2f}")
            print(
                f"   Credit bonus (all nodes): ${result['total_credit_bonus_amount']:.2f}"
            )
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
        # t1_addresses = await fetch_gist_addresses(tranche1_addresses_gist_id)
        t1_addresses = await get_tranche1_hms_addresses()
        # t1_addresses = ["0x007a1f3821ab1ed0f8e12678b600dc6dce74b8da"]
        # t1_addresses = [
        #     "0x5E258aff4f59fb5300Dc377C001D361E52a91894",
        #     # "0x891110E8A0b02D006c33DFADf7aed7081b63c8EA",
        #     # "0xcf30Cc6F9D67f21ef8ae5E5271Caf90F3e423ADF",
        # ]
        # t1_addresses = [
        #     "0x4da687250556cBD563459E422477dB2b0779A123",
        #     "0xa4868fdF30EF3aBa7Ccc2EE0dEEe128fC4f4798B",
        #     "0x3fD7Df71ec4482457d80D546Ba6f943302D8181B",
        #     "0x2B8604c98b8c4Ae226c92C8375893CE35f7e437C",
        #     "0xb7131B4158E597C6adD4cc40D3aE850EE20a8941",
        #     "0xE90C0c4Aae378aa9bB8ff74f3636D1DdA484105a",
        #     "0xCB456ADaE87589539c5c4Bb67BFF7696B4933b0E",
        #     "0x78Ab96f92858D59A946D0B442Fb97d88833e1442",
        #     "0x9eF6d86fb32e4d656579fe645F0E09D20C30A788",
        #     "0x2491e32Db833007bFc50b5e73347bf8343C406cD",
        #     "0x76493C787F6b6E8acfa719ea26130E7671a34307",
        # ]

        # t1_addresses = [t1_addresses[0]]
        # t1_addresses = ["0x029e40e8d0c181BA7445B2c27060386e45A63F85"]
        # t1_addresses = ["0x7f5B0C324EbA0D2Af713B06c960b332DD5e03621"]

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
                    total_credit_bonus_amount=result["total_credit_bonus_amount"],
                    total_balance=result["total_balance_usdc"],
                    final_balance=result["final_balance"],
                    error=result["error"],
                    license_count=result["license_count"],
                    processing_time=result["processing_time"],
                )
            else:
                raise Exception(f"Failed in some point: {result}")

            # Save cache every 10 addresses
            # if i % 10 == 0:
            if i % 5 == 0:
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
        print(f"Current bonus credit: ${self.results_cache['total_creadit_bonus']:.2f}")
        print(
            f"Current total to HMS: ${self.results_cache['total_balance_to_hms']:.2f}"
        )

    def print_final_summary(self):
        """Print final processing summary"""
        stats = self.results_cache["processing_stats"]

        print(f"\n{'='*60}")
        print("FINAL HTS COMPENSATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total addresses: {stats['total_addresses']}")
        print(f"Total addresses successfull: {stats['successful']}")
        print(f"Addresses with errors: {stats['errors']}")
        print(
            f"Total compensation amount: ${self.results_cache['total_compensation']:.2f}"
        )
        print(f"Total bonus credit: ${self.results_cache['total_creadit_bonus']:.2f}")
        print(
            f"Final total balance to HMS: ${self.results_cache['total_balance_to_hms']:.2f}"
        )

        # Top compensations
        successful_addresses = [
            data
            for data in self.results_cache["processed_addresses"].values()
            # if data.get("error") is None and data.get("compensation_amount_usd", 0) > 0
        ]

        if successful_addresses:
            top_compensations = sorted(
                successful_addresses,
                key=lambda x: x.get("final_balance", 0),
                # key=lambda x: x.get("compensation_amount_usd", 0),
                reverse=True,
            )
            # )[:50]

            # print(f"\nAll compensations:")
            print(f"\nAll final balances:")
            for i, addr_data in enumerate(top_compensations, 1):
                # print(
                #     f"{i:2d}. {addr_data['address']}: ${addr_data['compensation_amount_usd']:.2f}"
                # )
                print(
                    f"{i:2d}. {addr_data['address']}: ${addr_data['final_balance']:.2f}"
                )

    def export_results(self, filename: Union[str, None] = None):
        """Export results to a CSV file"""
        if filename is None:
            filename = f"hts_compensation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        import csv

        with open(filename, "w", newline="") as csvfile:
            fieldnames = [
                "address",
                "compensation_amount_usd",
                "total_credit_bonus_amount",
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
    # Only to fetch HTS public keys (commented out to avoid accidental runs)
    # await get_all_hts_public_keys()

    """Main processing function"""
    processor = HTSCompensationProcessor()

    # Process all addresses (will resume from cache by default)
    await processor.process_all_addresses(resume_from_cache=True)

    # Export results to CSV
    processor.export_results()


def get_tilling_data(lic):
    def is_entry_hts(entry):
        if "HTS" in entry.get('data',{}).get("name",""):
            return True
        return True
    data = []
    skip = 0
    failures = 0
    while True:
      try:
        url = f"http://18.216.251.149:8003/uptime_report?license={lic}&update_limit=20&update_skip={skip}&use_cache=0"
        ss = time.time()
        res = requests.get(url).json()
        failures = 0
        updates = res['updates']
        data.extend(updates)
        if len(updates) >= 20:
            skip+=20
        else:
            break
        print(lic, len(data), time.time()-ss, failures)
        time.sleep(0.5)
      except:
        import traceback
        traceback.print_exc()
        failures += 1
        if failures > 100:
            return
        time.sleep(20)
    data.sort(key=lambda x: x['ts'])

    #first timestamp for HTS, HMS:
    cutoff_ts = 1754031600
    start_time = 0
    last_time = 0
    total_uptime = 0
    total_downtime = 0
    breakout = False

    #handle case of long-lasting last tiller:
    if data:
        data.append({"ts": time.time(), "status": data[-1]['status']})

    for entry in data:
        if is_entry_hts(entry):
            valid_hts.append(entry)

            if entry['ts'] > cutoff_ts:
                entry['ts'] = cutoff_ts
                breakout = True

            if start_time == 0:
                start_time = entry['ts']
            else:
                if entry['status'] == "alive":
                    total_uptime += entry['ts']-last_time
                else:
                    total_downtime += entry['ts']-last_time
           
        if breakout:
            break
        last_time = entry['ts']
    print(data)
    import pdb
    pdb.set_trace()
      




async def compute_hts_credits(address):
    print("main2()")
    start_time = time.time()
    print(f"\n{'='*60}")
    print(f"Processing address: {address}")

    #get the license information first:
    licenses_ethereum = []
    licenses_base = []

    # Get licenses from subgraph (eth)
    licenses_data = await get_licenses_data(address, use_cache = False)
    licenses_data = check_licenses(licenses_data)
    for entry in licenses_data:
        licenses_ethereum.append(int(entry['licenseId']))
    # Get anfes from subgraph (base)
    anfes_data = await get_anfes_data(address, use_cache = False)
    licenses_base = [int(x['id'],16) for x in anfes_data]

    # print(f"filtered_licenses LENGTH: {len(filtered_licenses)}")
    
    # Get transfer data
    transfer_txs = await get_transfers(address, use_cache=False)
    nodes_deposits_txs = transfer_txs["nodes"]
    refunds_txs = transfer_txs["refunds"]

    # Get node tilling data:
    lic_tilling = dict()
    for lic in licenses_ethereum+licenses_base:
        lic = 70373039145623
        #get node lic from tilling service
        lic_tilling[lic] = get_tilling_data(lic)

    import pdb
    pdb.set_trace()


    #now, for each license+anfe, compute the first tilling entry on HTS, and
    #then compare the uptime/downtime from the first tilling entry to the cutoff time.


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
    real_end_balances, total_credit_bonus_amount = (
        calculate_end_balance_by_node_real(user_node_data, licenses_data)
    )
    print(f"real_end_balances: {real_end_balances}")
    total_balance_real = calculate_total_balance_real(
        real_end_balances, refunds_txs
    )
    print(f"total_balance_real: {total_balance_real}")

    if not licenses_data:
        print(f"No licenses found for {address}")
        return {
            "compensation_amount_usd": 0.0,
            "total_credit_bonus_amount": total_credit_bonus_amount / 1_000_000,
            "total_balance_usdc": total_balance_real / 1_000_000,
            "final_balance": (
                (total_balance_real * 1.5) + total_credit_bonus_amount
            )
            / 1_000_000,
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
        "total_credit_bonus_amount": total_credit_bonus_amount / 1_000_000,
        "total_balance_usdc": total_balance_real / 1_000_000,
        # The compensation calculated (using ERC20 with 6 decimals). Mainly because the Node balances comes like that
        "final_balance": (
            (
                total_balance_real * 1.5
                + compensation_report["compensation_amount_usd"] * 1_000_000
                + total_credit_bonus_amount
            )
        )
        / 1_000_000,
        "license_count": len(licenses_data),
        "processing_time": processing_time,
        "error": None,
        "detailed_report": compensation_report,
    }

    print(f"✅ Address {address} processed successfully")
    print(f"   Compensation: ${result['compensation_amount_usd']:.2f}")
    print(
          f"   Credit bonus (all nodes): ${result['total_credit_bonus_amount']:.2f}"
    )
    print(f"   Balance (all nodes): ${result['total_balance_usdc']:.2f}")
    print(f"   Final balance (to HMS): ${result['final_balance']:.2f}")
    print(f"   Licenses: {result['license_count']}")
    print(f"   Time: {processing_time:.1f}s")
    print(result())
    return result

if __name__ == "__main__":
    asyncio.run(compute_hts_credits("0xf48CaB1007F389e68cEFFe7778E6dBde14d41745"))
