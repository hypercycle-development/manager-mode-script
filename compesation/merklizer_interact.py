from common import MAX_TIMESTAMP_UTC, MERKLIZER_URL
import requests
import time
from typing import Dict, List, Optional, Tuple


class LicenseUptimeCalculator:
    def __init__(self, base_url: str = MERKLIZER_URL):
        self.base_url = base_url
        self.MAX_TIMESTAMP_UTC = MAX_TIMESTAMP_UTC  # August 1, 2025

    def get_all_uptime_data(
        self,
        license_number: int,
        batch_size: int = 5000,
        max_timestamp: Optional[int] = None,
    ) -> List[Dict]:
        """
        Retrieve all uptime data for a license by making multiple requests.

        Args:
            license_number: The license number to query
            batch_size: Number of updates to fetch per request (default: 5000)
            max_timestamp: Optional timestamp limit. If None, gets all data until today.
                         If provided, filters out updates newer than this timestamp.
        """
        all_updates = []
        skip = 0

        timestamp_limit = max_timestamp if max_timestamp is not None else float("inf")
        timestamp_str = (
            f" until {time.ctime(max_timestamp)}" if max_timestamp else " (no limit)"
        )

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
                    print(f"Error from AP (Merklizer): {data['error']}")
                    break

                updates = data.get("updates", [])

                if not updates:
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

                # If we got fewer updates than requested, we've reached the end
                if len(updates) < batch_size:
                    break

                # If we have a timestamp limit and the oldest update in this batch
                # is newer than our limit, we can stop (data is sorted newest first)
                if (
                    max_timestamp is not None
                    and updates
                    and min(update.get("ts", 0) for update in updates) > timestamp_limit
                ):
                    break

                skip += batch_size

                # Small delay to avoid overwhelming the server
                time.sleep(0.1)

            except requests.RequestException as e:
                print(f"Request failed (Merklizer): {e}")
                break
            except Exception as e:
                print(f"Error processing response (Merklizer): {e}")
                break

        return all_updates

    def calculate_uptime_metrics(
        self,
        updates: List[Dict],
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> Dict:
        """
        Calculate uptime metrics from a list of updates.
        This replicates the logic from the original code but fixes the end_time handling.
        """
        if not updates:
            return {
                "total_time": 0,
                "up_time": 0,
                "down_time": 0,
                "percent_up": 0,
                "update_count": 0,
            }

        # Sort updates by timestamp to ensure proper order
        sorted_updates = sorted(updates, key=lambda x: x.get("ts", 0))

        # Set default time range
        if start_time is None:
            start_time = sorted_updates[0].get("ts", 0)
        if end_time is None:
            # If no end_time specified, use the latest update timestamp or current time
            end_time = max(sorted_updates[-1].get("ts", 0), time.time())  # type: ignore

        # Filter updates within the time range and adjust boundaries
        filtered_updates = []
        for update in sorted_updates:
            ts = update.get("ts", 0)
            if start_time <= ts <= end_time:
                filtered_updates.append(update)

        if not filtered_updates:
            return {
                "total_time": 0,
                "up_time": 0,
                "down_time": 0,
                "percent_up": 0,
                "update_count": 0,
            }

        # Adjust first and last timestamps to match the requested range
        if filtered_updates[0]["ts"] < start_time:
            filtered_updates[0] = filtered_updates[0].copy()
            filtered_updates[0]["ts"] = start_time

        if filtered_updates[-1]["ts"] > end_time:
            filtered_updates[-1] = filtered_updates[-1].copy()
            filtered_updates[-1]["ts"] = end_time

        # Calculate uptime and downtime
        up_time = 0
        down_time = 0

        current_state = filtered_updates[0].get("status", "dead")
        current_time = filtered_updates[0]["ts"]

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
                "start": start_time,
                "end": end_time,
                "start_readable": time.ctime(start_time),
                "end_readable": time.ctime(end_time),
            },
        }

    def get_license_uptime_report(
        self,
        license_number: int,
        batch_size: int = 5000,
        max_timestamp: Optional[int] = None,
    ) -> Dict:
        """
        Main function to get complete uptime report for a license.

        Args:
            license_number: The license number to query
            batch_size: Number of updates to fetch per request (default: 5000)
            max_timestamp: Optional timestamp limit. If None, gets all data until today.


        Returns:
            Dictionary with license info, summary metrics, and metadata
        """

        # Get all uptime data
        all_updates = self.get_all_uptime_data(
            license_number, batch_size, max_timestamp
        )

        if not all_updates:
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
                },
            }

        # Calculate metrics
        metrics = self.calculate_uptime_metrics(all_updates, end_time=max_timestamp)

        return {
            "license": license_number,
            "summary": metrics,
            "max_timestamp_used": max_timestamp,
            "total_updates_found": len(all_updates),
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
