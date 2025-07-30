import json
import asyncio
from aiohttp import ClientSession
from typing import Dict, Set, List

MERKLIZER_URL = "http://18.216.251.149:8003"

async def check_license_status(session: ClientSession, license_id: str) -> str:
    try:
        async with session.get(f"{MERKLIZER_URL}/license_status?license={license_id}", timeout=10) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("status", "unknown")
    except Exception:
        return "error"
    return "unknown"

async def classify_licenses(addresses: Dict[str, List[str]]) -> Dict:
    async with ClientSession() as session:
        results = {}
        for addr, licenses in addresses.items():
            statuses = {}
            tasks = [check_license_status(session, lid) for lid in licenses]
            license_statuses = await asyncio.gather(*tasks)
            for lid, status in zip(licenses, license_statuses):
                statuses[lid] = status
            results[addr] = statuses
        return results

def determine_compensation(license_statuses: Dict) -> Dict:
    categories = {
        "valid_active": [],
        "all_unknown": [],
        "has_dead": [],
        "mixed_active_unknown": [],
        "no_licenses": []
    }
    
    compensation_addrs = []
    
    for addr, statuses in license_statuses.items():
        status_values = list(statuses.values())
        
        if not status_values:
            categories["no_licenses"].append(addr)
            compensation_addrs.append(addr)
        elif "dead" in status_values:
            categories["has_dead"].append(addr)
            compensation_addrs.append(addr)
        elif all(s == "unknown" for s in status_values):
            categories["all_unknown"].append(addr)
            compensation_addrs.append(addr)
        elif "unknown" in status_values:
            categories["mixed_active_unknown"].append(addr)
            compensation_addrs.append(addr)
        else:
            categories["valid_active"].append(addr)
    
    return {
        "detailed_categories": categories,
        "compensation_list": sorted(compensation_addrs)
    }

if __name__ == "__main__":
    # Load initial classification
    with open("initial_classification.json", "r") as f:
        data = json.load(f)
    
    # Process addresses with licenses
    license_statuses = asyncio.run(classify_licenses(data["with_licenses"]))
    
    # Add addresses without licenses
    for addr in data["without_licenses"]:
        license_statuses[addr] = {}
    
    # Add direct compensation addresses
    for addr in data["direct_compensation"]:
        license_statuses[addr] = {"direct_compensation": True}
    
    # Generate final reports
    reports = determine_compensation(license_statuses)
    
    # Save outputs
    with open("detailed_categories.json", "w") as f:
        json.dump(reports["detailed_categories"], f, indent=2)
    
    with open("compensation_list.json", "w") as f:
        json.dump(reports["compensation_list"], f, indent=2)
    
    print("Reports generated:")
    print("- detailed_categories.json")
    print("- compensation_list.json")