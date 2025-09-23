from common import MAX_TIMESTAMP_UTC, MERKLIZER_URL, seconds_to_months
import requests
import time
from typing import Dict, List, Optional, Tuple

import time
from typing import Dict, List, Optional, Tuple
import json
import os
from pathlib import Path


class LicenseUptimeCalculator:
    def __init__(self, base_url: str = "http://18.216.251.149:8003"):
        self.base_url = base_url
        self.MAX_TIMESTAMP_UTC = 1754006400  # August 1, 2025

    def get_all_uptime_data(
        self,
        license_number: int,
        batch_size: int = 5000,
        max_timestamp: Optional[int] = None,
        cache_dir: str = "license_uptime_cache",
    ) -> List[Dict]:
        """
        Retrieve all uptime data for a license by making multiple requests.

        Args:
            license_number: The license number to query
            batch_size: Number of updates to fetch per request (default: 5000)
            max_timestamp: Optional timestamp limit. If None, gets all data until today.
                         If provided, filters out updates newer than this timestamp.
        """
        # Create cache directory if it doesn't exist
        Path(cache_dir).mkdir(exist_ok=True)

        # Get the cache filename
        cache_file = os.path.join(cache_dir, f"{license_number}.json")

        # Check if cached data exists
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    cached_data = json.load(f)
                print(f"Loaded cached license uptime data for {license_number}")
                return cached_data
            except Exception as e:
                print(f"Error loading cache for license uptime {license_number}: {e}")
                print("Fetching fresh data...")

        all_updates = []
        skip = 0

        timestamp_limit = max_timestamp if max_timestamp is not None else float("inf")
        timestamp_str = (
            f" until {time.ctime(max_timestamp)}" if max_timestamp else " (no limit)"
        )

        print(f"Fetching uptime data for license {license_number}{timestamp_str}...")

        while True:
            # Make request to get batch of updates
            params = {
                "license": license_number,
                "use_cache": 0,  # Don't use cache to get fresh data
                "update_limit": batch_size,
                "update_skip": skip,
                "start_time": 0,  # Get from beginning
                # Don't set end_time in API call since it's buggy - we'll filter afterwards
            }

            try:
                response = requests.get(
                    f"{self.base_url}/uptime_report", params=params, timeout=30
                )
                response.raise_for_status()
                data = response.json()

                if "error" in data:
                    print(f"Error from API: {data['error']}")
                    break

                updates = data.get("updates", [])

                if not updates:
                    print(
                        f"No more updates found. Retrieved {len(all_updates)} total updates."
                    )
                    break

                # Filter out updates that are newer than the timestamp limit (if provided)
                if max_timestamp is not None:
                    filtered_updates = [
                        update
                        for update in updates
                        if update.get("ts", 0) <= timestamp_limit
                    ]
                else:
                    filtered_updates = updates

                all_updates.extend(filtered_updates)

                print(
                    f"Batch {skip//batch_size + 1}: Retrieved {len(filtered_updates)} updates "
                    f"(Total: {len(all_updates)})"
                )

                # If we got fewer updates than requested, we've reached the end
                if len(updates) < batch_size:
                    break

                # Check if we should continue based on timestamp filtering
                if max_timestamp is not None and updates:
                    min_ts_in_batch = min(update.get("ts", 0) for update in updates)
                    max_ts_in_batch = max(update.get("ts", 0) for update in updates)

                    # If ALL updates in this batch are newer than our limit,
                    # continue to next batch to find older data (data is sorted oldest first)
                    if min_ts_in_batch > timestamp_limit:
                        print(
                            f"Batch {skip//batch_size + 1}: All updates too recent, continuing to find older data..."
                        )
                        # Don't break - continue to find older historical data
                        pass  # Continue to next iteration
                    elif (
                        len(filtered_updates) == 0
                        and max_ts_in_batch <= timestamp_limit
                    ):
                        # All data in this batch is older than our limit, we're done
                        print(
                            f"Batch {skip//batch_size + 1}: All updates too old, stopping."
                        )
                        break
                    elif len(updates) == 0:
                        print(
                            f"Batch {skip//batch_size + 1}: Found timestamp boundary, stopping."
                        )
                        break

                skip += batch_size

                # Small delay to avoid overwhelming the server
                time.sleep(0.1)

            except requests.RequestException as e:
                print(f"Request failed: {e}")
                break
            except Exception as e:
                print(f"Error processing response: {e}")
                break

        sorted_updates = sorted(all_updates, key=lambda x: x.get("ts", 0))

        # Save to cache
        try:
            with open(cache_file, "w") as f:
                json.dump(sorted_updates, f, indent=2)
            print(f"Cached license uptime data for {license_number}")
        except Exception as e:
            print(f"Error saving license uptime cache for {license_number}: {e}")

        # Return it
        return sorted_updates

    def calculate_uptime_metrics(
        self,
        updates: List[Dict],
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        custom_start_time: Optional[int] = None,
    ) -> Dict:
        if not updates:
            # If we have a custom start time but no uptime data,
            # the entire period from custom_start to end_time is downtime
            if custom_start_time and end_time:
                total_downtime = end_time - custom_start_time
                return {
                    "total_time": total_downtime,
                    "up_time": 0,
                    "down_time": total_downtime,
                    "percent_up": 0,
                    "update_count": 0,
                    "custom_start_used": True,
                    "gap_downtime": total_downtime,
                    "time_range": {
                        "start": custom_start_time,
                        "end": end_time,
                        "start_readable": time.ctime(custom_start_time),
                        "end_readable": time.ctime(end_time),
                    },
                }

            return {
                "total_time": 0,
                "up_time": 0,
                "down_time": 0,
                "percent_up": 0,
                "update_count": 0,
                "custom_start_used": False,
                "gap_downtime": 0,
                "time_range": {
                    "start": 0,
                    "end": 0,
                    "start_readable": time.ctime(0),
                    "end_readable": time.ctime(0),
                },
            }

        # Sort updates by timestamp to ensure proper order
        sorted_updates = sorted(updates, key=lambda x: x.get("ts", 0))

        print(
            f"The updates start[0] ({sorted_updates[0]['ts']}): {time.ctime(sorted_updates[0]['ts'])}"
        )
        print(
            f"The updates start[last] ({sorted_updates[len(sorted_updates)-1]['ts']}): {time.ctime(sorted_updates[len(sorted_updates)-1]['ts'])}"
        )

        # Determine the actual start time for calculations
        first_uptime_timestamp = sorted_updates[0].get("ts", 0)
        actual_start_time = (
            start_time if start_time is not None else first_uptime_timestamp
        )

        # Handle custom start time logic
        gap_downtime = 0
        custom_start_used = False

        if custom_start_time is not None:
            custom_start_used = True
            if custom_start_time < first_uptime_timestamp:
                # There's a gap between custom start and first uptime - count as downtime
                gap_downtime = first_uptime_timestamp - custom_start_time
                actual_start_time = custom_start_time
            else:
                # Custom start is after first uptime, use custom start
                actual_start_time = custom_start_time

        # Set default end time
        if end_time is None:
            # If no end_time specified, use the latest update timestamp or current time
            end_time = max(sorted_updates[-1].get("ts", 0), time.time())

        # Filter updates within the time range
        filtered_updates = []
        for update in sorted_updates:
            ts = update.get("ts", 0)
            if actual_start_time <= ts <= end_time:
                filtered_updates.append(update)

        if not filtered_updates:
            # No updates in the specified range
            total_time = end_time - actual_start_time
            return {
                "total_time": total_time,
                "up_time": 0,
                "down_time": total_time,
                "percent_up": 0,
                "update_count": 0,
                "time_range": {
                    "start": actual_start_time,
                    "end": end_time,
                    "start_readable": time.ctime(actual_start_time),
                    "end_readable": time.ctime(end_time),
                },
                "custom_start_used": custom_start_used,
                "gap_downtime": gap_downtime,
            }

        # Handle the gap between custom start time and first uptime (if any)
        up_time = 0
        down_time = gap_downtime  # Start with any gap downtime

        # If there's a gap, we need to handle the period from actual_start_time to first update
        if gap_downtime > 0:
            # Gap already counted in down_time
            current_time = first_uptime_timestamp
            current_state = filtered_updates[0].get("status", "dead")
        else:
            # No gap, start from the actual start time
            current_time = actual_start_time
            # Find the first update to determine initial state
            if filtered_updates[0]["ts"] > actual_start_time:
                # There's a small gap between actual_start_time and first update
                gap_to_first_update = filtered_updates[0]["ts"] - actual_start_time
                down_time += gap_to_first_update  # Assume down until first update
            current_time = filtered_updates[0]["ts"]
            current_state = filtered_updates[0].get("status", "dead")

        # Process state changes
        for update in filtered_updates[1:]:
            next_time = update["ts"]
            time_diff = next_time - current_time

            if current_state == "alive":
                up_time += time_diff
            else:
                down_time += time_diff

            current_state = update.get("status", "dead")
            current_time = next_time

        # Handle the final state until end_time
        final_time_diff = end_time - current_time
        if final_time_diff > 0:
            if current_state == "alive":
                up_time += final_time_diff
            else:
                down_time += final_time_diff

        total_time = up_time + down_time
        percent_up = up_time / (total_time + 0.1) if total_time > 0 else 0

        return {
            "total_time": total_time,
            "up_time": up_time,
            "down_time": down_time,
            "percent_up": percent_up,
            "update_count": len(filtered_updates),
            "time_range": {
                "start": actual_start_time,
                "end": end_time,
                "start_readable": time.ctime(actual_start_time),
                "end_readable": time.ctime(end_time),
            },
            "custom_start_used": custom_start_used,
            "gap_downtime": gap_downtime,
        }

    def get_license_uptime_report(
        self,
        license_number: int,
        batch_size: int = 5000,
        max_timestamp: Optional[int] = None,
        custom_start_time: Optional[int] = None,
    ) -> Dict:

        timestamp_info = (
            f" up to {time.ctime(max_timestamp)}"
            if max_timestamp
            else " (all available data)"
        )
        custom_start_info = (
            f" with custom start {time.ctime(custom_start_time)}"
            if custom_start_time
            else ""
        )
        print(
            f"\n----- Generating uptime report for license {license_number}{timestamp_info}{custom_start_info}"
        )

        if max_timestamp:
            print(f"Max timestamp: {max_timestamp} ({time.ctime(max_timestamp)})")
        if custom_start_time:
            print(
                f"Custom start time: {custom_start_time} ({time.ctime(custom_start_time)})"
            )

        # Get all uptime data
        all_updates = self.get_all_uptime_data(
            license_number, batch_size, max_timestamp
        )

        print(f"all updates: {len(all_updates)}")

        if not all_updates and not custom_start_time:
            print("No uptime data found for this license.")
            return {
                "license": license_number,
                "error": "No uptime data found",
                "summary": {
                    "total_time": 0,
                    "up_time": 0,
                    "down_time": 0,
                    "percent_up": 0,
                    "update_count": 0,
                    "custom_start_used": False,
                    "gap_downtime": 0,
                },
            }

        # Calculate metrics (handles custom_start_time internally)
        metrics = self.calculate_uptime_metrics(
            all_updates, end_time=max_timestamp, custom_start_time=custom_start_time
        )

        print(f"Total updates processed: {metrics['update_count']}")
        print(
            f"Time range: {metrics['time_range']['start_readable']} to {metrics['time_range']['end_readable']}"
        )
        if metrics.get("custom_start_used", False):
            print(f"Custom start time used: Yes")
            if metrics.get("gap_downtime", 0) > 0:
                print(
                    f"Gap downtime (before first uptime): {metrics['gap_downtime']:.2f} seconds ({metrics['gap_downtime']/3600:.2f} hours)"
                )
        print(
            f"Total time: {metrics['total_time']:.2f} seconds ({metrics['total_time']/3600:.2f} hours)"
        )
        print(
            f"Up time: {metrics['up_time']:.2f} seconds ({metrics['up_time']/3600:.2f} hours)"
        )
        print(
            f"Down time: {metrics['down_time']:.2f} seconds ({metrics['down_time']/3600:.2f} hours)"
        )
        print(f"Uptime percentage: {metrics['percent_up']*100:.2f}%")

        return {
            "license": license_number,
            "summary": metrics,
            "max_timestamp_used": max_timestamp,
            "custom_start_time_used": custom_start_time,
            "total_updates_found": len(all_updates) if all_updates else 0,
        }

    def calculate_hts_compensation(
        self, licenses_data: List[Dict], wallet_address: str = None
    ) -> Dict:
        """
        Calculate HTS compensation for a wallet based on all its licenses.

        Args:
            licenses_data: List of license data from subgraph (ProposalData format)
            wallet_address: Optional wallet address for reporting

        Returns:
            Dictionary with compensation details
        """
        print(f"\n=== CALCULATING HTS COMPENSATION ===")
        if wallet_address:
            print(f"Wallet: {wallet_address}")
        print(f"Processing {len(licenses_data)} licenses...")

        total_wallet_downtime_seconds = 0
        total_wallet_downtime_hours = 0
        license_reports = []

        for i, license_data in enumerate(licenses_data):
            license_id = int(license_data["licenseId"])
            print(f"\n--- License {i+1}/{len(licenses_data)}: {license_id} ---")

            # Get first message timestamp (if exists)
            first_message_time = None
            message_changes = license_data.get("shareToken", {}).get(
                "messageChanged", []
            )
            if message_changes:
                # first_message_time = int(message_changes[0]["blockTimestamp"])
                first_message_time = int(
                    message_changes[len(message_changes) - 1]["blockTimestamp"]
                )
                # f"First message timestamp: {first_message_time} ({time.ctime(first_message_time)})"
                print(
                    f"Last message timestamp: {first_message_time} ({time.ctime(first_message_time)})"
                )
            else:
                print("No message changes found for this license")

            # Get uptime report with custom start time
            try:
                report = self.get_license_uptime_report(
                    license_id,
                    max_timestamp=self.MAX_TIMESTAMP_UTC,
                    custom_start_time=first_message_time,
                )

                if "error" not in report:
                    downtime_seconds = report["summary"]["down_time"]
                    downtime_hours = downtime_seconds / 3600
                    total_wallet_downtime_seconds += downtime_seconds
                    total_wallet_downtime_hours += downtime_hours

                    license_reports.append(
                        {
                            "license_id": license_id,
                            "downtime_seconds": downtime_seconds,
                            "downtime_hours": downtime_hours,
                            "uptime_hours": report["summary"]["up_time"] / 3600,
                            "total_hours": report["summary"]["total_time"] / 3600,
                            "uptime_percentage": report["summary"]["percent_up"] * 100,
                            "custom_start_used": report["summary"].get(
                                "custom_start_used", False
                            ),
                            "gap_downtime_hours": report["summary"].get(
                                "gap_downtime", 0
                            )
                            / 3600,
                            "first_message_time": first_message_time,
                        }
                    )

                    print(f"License {license_id} downtime: {downtime_seconds} seconds")
                    print(f"License {license_id} downtime: {downtime_hours:.2f} hours")
                else:
                    print(
                        f"Error processing license {license_id}: {report.get('error', 'Unknown error')}"
                    )
                    license_reports.append(
                        {
                            "license_id": license_id,
                            "downtime_seconds": 0,
                            "downtime_hours": 0,
                            "error": report.get("error", "Unknown error"),
                        }
                    )

            except Exception as e:
                print(f"Exception processing license {license_id}: {e}")
                license_reports.append(
                    {
                        "license_id": license_id,
                        "downtime_hours": 0,
                        "downtime_seconds": 0,
                        "error": str(e),
                    }
                )

        # Apply compensation formula
        print(f"\n=== COMPENSATION CALCULATION ===")
        print(
            f"Total downtime across all licenses: {total_wallet_downtime_seconds} seconds"
        )
        print(
            f"Total downtime across all licenses: {total_wallet_downtime_hours:.2f} hours"
        )

        # After formula: cast_to_month(total_downtime * 5) * 5$
        compensation_amount = seconds_to_months(total_wallet_downtime_seconds * 5) * 5

        print(f"Compensation amount: ${compensation_amount:.2f}")

        return {
            "wallet_address": wallet_address,
            "total_licenses_processed": len(licenses_data),
            "total_downtime_hours": total_wallet_downtime_hours,
            "compensation_amount_usd": compensation_amount,
            "license_reports": license_reports,
            "max_timestamp_used": self.MAX_TIMESTAMP_UTC,
            "calculation_timestamp": time.time(),
        }

    def compare_with_endpoint(self, license_number: int) -> Dict:
        """
        Compare our calculation with the endpoint's calculation to validate accuracy.
        This makes a direct call to the endpoint and compares the results.
        """
        print(f"\n=== COMPARISON WITH ENDPOINT ===")
        print(f"License: {license_number}")

        try:
            # Get data from the original endpoint (without our custom end_time)
            params = {
                "license": license_number,
                "use_cache": 0,
                "update_limit": 20,  # Match default
                "update_skip": 0,
            }

            response = requests.get(
                f"{self.base_url}/uptime_report", params=params, timeout=30
            )
            response.raise_for_status()
            endpoint_data = response.json()

            if "error" in endpoint_data:
                return {"error": f"Endpoint error: {endpoint_data['error']}"}

            # Get our calculation with all data (no timestamp limit)
            our_report = self.get_license_uptime_report(license_number)

            # Get our calculation with MAX_TIMESTAMP_UTC limit for comparison
            our_report_limited = self.get_license_uptime_report(
                license_number, max_timestamp=self.MAX_TIMESTAMP_UTC
            )

            endpoint_summary = endpoint_data.get("summary", {})
            our_summary = our_report["summary"]
            our_summary_limited = our_report_limited["summary"]

            print(f"\n--- ENDPOINT RESULTS ---")
            print(f"Total time: {endpoint_summary.get('total_time', 0):.2f} seconds")
            print(f"Up time: {endpoint_summary.get('up_time', 0):.2f} seconds")
            print(f"Down time: {endpoint_summary.get('down_time', 0):.2f} seconds")
            print(f"Percent up: {endpoint_summary.get('percent_up', 0)*100:.2f}%")
            print(f"Updates shown: {len(endpoint_data.get('updates', []))}")

            print(f"\n--- OUR RESULTS (ALL DATA) ---")
            print(f"Total time: {our_summary.get('total_time', 0):.2f} seconds")
            print(f"Up time: {our_summary.get('up_time', 0):.2f} seconds")
            print(f"Down time: {our_summary.get('down_time', 0):.2f} seconds")
            print(f"Percent up: {our_summary.get('percent_up', 0)*100:.2f}%")
            print(f"Updates processed: {our_summary.get('update_count', 0)}")

            print(f"\n--- OUR RESULTS (LIMITED TO AUG 1, 2025) ---")
            print(f"Total time: {our_summary_limited.get('total_time', 0):.2f} seconds")
            print(f"Up time: {our_summary_limited.get('up_time', 0):.2f} seconds")
            print(f"Down time: {our_summary_limited.get('down_time', 0):.2f} seconds")
            print(f"Percent up: {our_summary_limited.get('percent_up', 0)*100:.2f}%")
            print(f"Updates processed: {our_summary_limited.get('update_count', 0)}")

            # Calculate differences
            def calc_diff(our_val, endpoint_val):
                if endpoint_val == 0:
                    return float("inf") if our_val != 0 else 0
                return abs(our_val - endpoint_val) / endpoint_val * 100

            diff_total = calc_diff(
                our_summary.get("total_time", 0), endpoint_summary.get("total_time", 0)
            )
            diff_up = calc_diff(
                our_summary.get("up_time", 0), endpoint_summary.get("up_time", 0)
            )
            diff_percent = calc_diff(
                our_summary.get("percent_up", 0), endpoint_summary.get("percent_up", 0)
            )

            print(f"\n--- DIFFERENCES (Our ALL DATA vs Endpoint) ---")
            print(f"Total time difference: {diff_total:.2f}%")
            print(f"Up time difference: {diff_up:.2f}%")
            print(f"Percent up difference: {diff_percent:.2f}%")

            return {
                "endpoint": endpoint_data,
                "our_all_data": our_report,
                "our_limited_data": our_report_limited,
                "differences": {
                    "total_time_diff_percent": diff_total,
                    "up_time_diff_percent": diff_up,
                    "percent_up_diff_percent": diff_percent,
                },
            }

        except Exception as e:
            error_msg = f"Error during comparison: {e}"
            print(error_msg)
            return {"error": error_msg}
