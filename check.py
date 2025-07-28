import asyncio
import os
import json
from aiohttp import ClientSession, ClientError
from typing import Optional, List, Dict, Set, Tuple, Any

# Configuration
MERKLIZER_URL = "http://18.216.251.149:8003"
SUBGRAPHS = {
    "mainnet": {
        "ethereum": "https://api.studio.thegraph.com/query/90034/hypercycle-ethereum/v0.7.26",
        "base": "https://api.studio.thegraph.com/query/90034/hypercycle-base/v0.7.26",
    },
    "testnet": {
        "ethereum": "https://api.studio.thegraph.com/query/90034/hypercycle-ethereum-sepolia/v0.7.26",
        "base": "https://api.studio.thegraph.com/query/90034/hypercycle-base-sepolia/v0.7.26",
    },
}

class AddressClassifier:
    def __init__(self):
        self.tranche_addresses: Set[str] = set()
        self.activity_data: Dict[str, Set[str]] = {}
        self.active_addresses: Dict[str, Set[str]] = {}
        self.inactive_addresses: Set[str] = set()
        self.subgraph_verified: Dict[str, Set[str]] = {}
        self.merklizer_status: Dict[str, str] = {}
        self.address_categories: Dict[str, Set[str]] = {
            "valid_active": set(),
            "invalid_active": set(),
            "compensation_needed": set()
        }

    def read_tranche_addresses(self, filename: str) -> None:
        """Read addresses from tranche file"""
        with open(filename, 'r') as file:
            self.tranche_addresses = {
                line.strip() for line in file 
                if line.strip() and not line.startswith('#')
            }

    def read_hts_files(self, file_pattern: str, num_files: int = 6) -> None:
        """Read all hts files and build activity data"""
        self.activity_data = {}
        
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
                    if address not in self.activity_data:
                        self.activity_data[address] = set()
                    self.activity_data[address].add(license_id)

    def classify_addresses(self) -> None:
        """Initial classification based on hts files"""
        for address in self.tranche_addresses:
            if address in self.activity_data:
                self.active_addresses[address] = self.activity_data[address]
            else:
                self.inactive_addresses.add(address)

    async def verify_with_subgraph(self, session: ClientSession) -> None:
        """Verify licenses with subgraph data"""
        query_template = """
        {{
            shareProposalDatas(
                first: 1000
                orderBy: proposalId
                where: {{ operator_contains: "{address}" }}
            ) {{
                licenseId
            }}
        }}
        """
        
        tasks = []
        for address in self.tranche_addresses:
            query = query_template.format(address=address)
            tasks.append(self._query_all_networks(session, query, address))
        
        results = await asyncio.gather(*tasks)
        
        for address, subgraph_licenses in results:
            self.subgraph_verified[address] = subgraph_licenses

    async def _query_all_networks(self, session: ClientSession, query: str, address: str) -> Tuple[str, Set[str]]:
        """Query all networks for a single address"""
        tasks = []
        for url in SUBGRAPHS["mainnet"].values():
            tasks.append(self._query_subgraph(session, url, query))
        
        results = await asyncio.gather(*tasks)
        all_licenses = set()
        
        for result in results:
            if result and "data" in result:
                for item in result["data"].get("shareProposalDatas", []):
                    if "licenseId" in item:
                        all_licenses.add(item["licenseId"])
        
        return (address, all_licenses)

    async def _query_subgraph(self, session: ClientSession, url: str, query: str) -> Optional[Dict]:
        """Execute GraphQL query against subgraph"""
        payload = {"query": query}
        try:
            async with session.post(url, json=payload) as resp:
                resp.raise_for_status()
                return await resp.json()
        except ClientError as e:
            print(f"⚠️ Subgraph query failed: {e}")
            return None

    async def check_merklizer_status(self, session: ClientSession) -> None:
        """Check license status with merklizer"""
        all_licenses = set()
        for licenses in self.activity_data.values():
            all_licenses.update(licenses)
        
        tasks = []
        for license_id in all_licenses:
            tasks.append(self._check_single_license(session, license_id))
        
        await asyncio.gather(*tasks)

    async def _check_single_license(self, session: ClientSession, license_id: str) -> None:
        """Check status of a single license"""
        url = f"{MERKLIZER_URL}/license_status?license={license_id}"
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.merklizer_status[license_id] = data.get("status", "unknown")
                else:
                    self.merklizer_status[license_id] = "error"
        except ClientError:
            self.merklizer_status[license_id] = "error"

    def perform_final_classification(self) -> None:
        """Perform final classification based on all checks"""
        for address in self.tranche_addresses:
            # Get all licenses we found for this address
            our_licenses = self.activity_data.get(address, set())
            
            # Get licenses from subgraph
            subgraph_licenses = self.subgraph_verified.get(address, set())
            
            # Check merklizer status for our licenses
            valid_licenses = set()
            invalid_licenses = set()
            
            for license_id in our_licenses:
                status = self.merklizer_status.get(license_id, "unknown")
                if status == "alive":
                    valid_licenses.add(license_id)
                else:
                    invalid_licenses.add(license_id)
            
            # Classification logic
            if not our_licenses and not subgraph_licenses:
                # No licenses found anywhere - compensation needed
                self.address_categories["compensation_needed"].add(address)
            elif our_licenses and subgraph_licenses and our_licenses.issubset(subgraph_licenses):
                # All our licenses are verified in subgraph
                if all(self.merklizer_status.get(lid, "") == "alive" for lid in our_licenses):
                    self.address_categories["valid_active"].add(address)
                else:
                    self.address_categories["invalid_active"].add(address)
            else:
                # Discrepancy between our data and subgraph
                self.address_categories["compensation_needed"].add(address)

    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive report"""
        report = {
            "summary": {
                "total_addresses": len(self.tranche_addresses),
                "valid_active": len(self.address_categories["valid_active"]),
                "invalid_active": len(self.address_categories["invalid_active"]),
                "compensation_needed": len(self.address_categories["compensation_needed"]),
            },
            "details": {
                "valid_active": sorted(self.address_categories["valid_active"]),
                "invalid_active": sorted(self.address_categories["invalid_active"]),
                "compensation_needed": sorted(self.address_categories["compensation_needed"]),
            }
        }
        
        # Add license status details
        report["license_status"] = {}
        for address in self.active_addresses:
            report["license_status"][address] = {
                "our_licenses": sorted(self.activity_data.get(address, [])),
                "subgraph_licenses": sorted(self.subgraph_verified.get(address, [])),
                "merklizer_status": {
                    lid: self.merklizer_status.get(lid, "unknown")
                    for lid in self.activity_data.get(address, [])
                }
            }
        
        return report

async def main():
    classifier = AddressClassifier()
    
    # Load data files
    classifier.read_tranche_addresses("data_tillers/tranche1_addresses.txt")
    classifier.read_hts_files("data_tillers/merk_data/hts{}.txt")
    classifier.classify_addresses()
    
    async with ClientSession() as session:
        # Verify with subgraph
        print("Verifying licenses with subgraph...")
        await classifier.verify_with_subgraph(session)
        
        # Check merklizer status
        print("Checking license status with merklizer...")
        await classifier.check_merklizer_status(session)
    
    # Perform final classification
    classifier.perform_final_classification()
    
    # Generate and save report
    report = classifier.generate_report()
    with open("address_classification_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print("Classification complete. Report saved to address_classification_report.json")

if __name__ == "__main__":
    asyncio.run(main())