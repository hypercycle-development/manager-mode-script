import asyncio
import os
import json
from aiohttp import ClientSession, ClientError
from typing import Dict, Set, List, Any

# Configuration
MERKLIZER_URL = "http://18.216.251.149:8003"

class LicenseChecker:
    def __init__(self):
        self.tranche_addresses: Set[str] = set()
        self.tracked_licenses: Dict[str, Set[str]] = {}  # Address -> license IDs
        self.license_status: Dict[str, str] = {}  # License ID -> status
        self.address_categories: Dict[str, Set[str]] = {
            "valid_active": set(),      # All licenses alive
            "needs_compensation": set() # Any license dead/unknown or no licenses
        }

    def read_tranche_addresses(self, filename: str) -> None:
        """Read addresses from tranche file"""
        with open(filename, 'r') as file:
            self.tranche_addresses = {
                line.strip() for line in file 
                if line.strip() and not line.startswith('#')
            }

    def read_hts_files(self, file_pattern: str, num_files: int = 6) -> None:
        """Read all hts files with our tracked licenses"""
        self.tracked_licenses = {}
        
        for i in range(1, num_files + 1):
            filename = file_pattern.format(i)
            if not os.path.exists(filename):
                continue
                
            with open(filename, 'r') as file:
                next(file, None)  # Skip header
                
                for line in file:
                    if not line.strip():
                        continue
                        
                    parts = line.strip().split()
                    if len(parts) < 2:
                        continue
                        
                    address, license_id = parts[0], parts[1]
                    if address not in self.tracked_licenses:
                        self.tracked_licenses[address] = set()
                    self.tracked_licenses[address].add(license_id)

    async def check_license_statuses(self, session: ClientSession) -> None:
        """Check status of all tracked licenses"""
        all_licenses = set()
        for licenses in self.tracked_licenses.values():
            all_licenses.update(licenses)
        
        # Process in batches to avoid overwhelming the endpoint
        BATCH_SIZE = 20
        licenses_list = list(all_licenses)
        
        for i in range(0, len(licenses_list), BATCH_SIZE):
            batch = licenses_list[i:i+BATCH_SIZE]
            tasks = [self._check_single_license(session, lid) for lid in batch]
            await asyncio.gather(*tasks)
            await asyncio.sleep(0.5)  # Rate limiting

    async def _check_single_license(self, session: ClientSession, license_id: str) -> None:
        """Check status of a single license"""
        url = f"{MERKLIZER_URL}/license_status?license={license_id}"
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.license_status[license_id] = data.get("status", "unknown")
                else:
                    self.license_status[license_id] = "error"
        except ClientError:
            self.license_status[license_id] = "error"

    def classify_addresses(self) -> None:
        """Classify addresses based on license statuses"""
        for address in self.tranche_addresses:
            licenses = self.tracked_licenses.get(address, set())
            
            # If no licenses at all, needs compensation
            if not licenses:
                self.address_categories["needs_compensation"].add(address)
                continue
                
            # Check status of all licenses
            all_alive = True
            for license_id in licenses:
                status = self.license_status.get(license_id, "unknown")
                if status != "alive":
                    all_alive = False
                    break
                    
            if all_alive:
                self.address_categories["valid_active"].add(address)
            else:
                self.address_categories["needs_compensation"].add(address)

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive report"""
        report = {
            "summary": {
                "total_addresses": len(self.tranche_addresses),
                "valid_active": len(self.address_categories["valid_active"]),
                "needs_compensation": len(self.address_categories["needs_compensation"]),
            },
            "details": {
                "valid_active": sorted(self.address_categories["valid_active"]),
                "needs_compensation": sorted(self.address_categories["needs_compensation"]),
            },
            "license_details": {}
        }
        
        # Add license status info for each address
        for address in self.tranche_addresses:
            report["license_details"][address] = {
                "licenses": sorted(self.tracked_licenses.get(address, [])),
                "statuses": {
                    lid: self.license_status.get(lid, "unknown")
                    for lid in self.tracked_licenses.get(address, [])
                },
                "classification": ("valid_active" if address in self.address_categories["valid_active"]
                                 else "needs_compensation")
            }
        
        return report

async def main():
    checker = LicenseChecker()
    
    # Load data files
    checker.read_tranche_addresses("data_tillers/tranche1_addresses.txt")
    checker.read_hts_files("data_tillers/merk_data/hts{}.txt")
    
    async with ClientSession() as session:
        # Check license statuses
        print("Checking license statuses with merklizer...")
        await checker.check_license_statuses(session)
    
    # Perform classification
    checker.classify_addresses()
    
    # Generate and save report
    report = checker.generate_report()
    with open("license_check_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print("Verification complete. Report saved to license_check_report.json")

if __name__ == "__main__":
    asyncio.run(main())