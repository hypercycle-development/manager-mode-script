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
        self.tracked_licenses: Dict[str, Set[str]] = {}  # Our tracked licenses
        self.subgraph_licenses: Dict[str, Set[str]] = {}  # All licenses from subgraph
        self.license_status: Dict[str, str] = {}  # Merklizer status for all licenses
        self.address_categories: Dict[str, Set[str]] = {
            "valid_active": set(),      # All licenses alive
            "compensation_needed": set() # Any license dead/unknown or discrepancies
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

    async def verify_with_subgraph(self, session: ClientSession) -> None:
        """Get ALL licenses for each address from subgraph"""
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
        
        for address, licenses in results:
            self.subgraph_licenses[address] = licenses

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
        """Check status of ALL licenses from subgraph (not just our tracked ones)"""
        all_licenses = set()
        for licenses in self.subgraph_licenses.values():
            all_licenses.update(licenses)
        
        # Also include our tracked licenses in case they're not in subgraph
        for licenses in self.tracked_licenses.values():
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
                    self.license_status[license_id] = data.get("status", "unknown")
                else:
                    self.license_status[license_id] = "error"
        except ClientError:
            self.license_status[license_id] = "error"

    def perform_final_classification(self) -> None:
        """Classify addresses based on ALL licenses from subgraph and their status"""
        for address in self.tranche_addresses:
            subgraph_licenses = self.subgraph_licenses.get(address, set())
            tracked_licenses = self.tracked_licenses.get(address, set())
            
            # Check if any license is dead/unknown
            has_bad_license = False
            for license_id in subgraph_licenses:
                status = self.license_status.get(license_id, "unknown")
                if status != "alive":
                    has_bad_license = True
                    break
            
            # Classification rules:
            # 1. If no licenses at all -> compensation
            # 2. If any license is dead/unknown -> compensation
            # 3. If our tracked licenses don't match subgraph -> compensation
            # 4. Only valid if all licenses are alive and our tracking matches subgraph
            if (not subgraph_licenses or 
                has_bad_license or
                not tracked_licenses.issubset(subgraph_licenses)):
                self.address_categories["compensation_needed"].add(address)
            else:
                self.address_categories["valid_active"].add(address)

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive report with all verification details"""
        report = {
            "summary": {
                "total_addresses": len(self.tranche_addresses),
                "valid_active": len(self.address_categories["valid_active"]),
                "compensation_needed": len(self.address_categories["compensation_needed"]),
            },
            "details": {
                "valid_active": sorted(self.address_categories["valid_active"]),
                "compensation_needed": sorted(self.address_categories["compensation_needed"]),
            },
            "verification_details": {}
        }
        
        # Add detailed verification info for each address
        for address in self.tranche_addresses:
            report["verification_details"][address] = {
                "tracked_licenses": sorted(self.tracked_licenses.get(address, [])),
                "subgraph_licenses": sorted(self.subgraph_licenses.get(address, [])),
                "license_statuses": {
                    lid: self.license_status.get(lid, "unknown")
                    for lid in self.subgraph_licenses.get(address, [])
                },
                "classification": ("valid_active" if address in self.address_categories["valid_active"]
                                 else "compensation_needed")
            }
        
        return report

async def main():
    classifier = AddressClassifier()
    
    # Load data files
    classifier.read_tranche_addresses("data_tillers/tranche1_addresses.txt")
    classifier.read_hts_files("data_tillers/merk_data/hts{}.txt")
    
    async with ClientSession() as session:
        # Verify with subgraph (get ALL licenses)
        print("Fetching all licenses from subgraph...")
        await classifier.verify_with_subgraph(session)
        
        # Check merklizer status for all licenses
        print("Checking license statuses with merklizer...")
        await classifier.check_merklizer_status(session)
    
    # Perform final classification
    classifier.perform_final_classification()
    
    # Generate and save report
    report = classifier.generate_report()
    with open("address_verification_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print("Verification complete. Report saved to address_verification_report.json")

if __name__ == "__main__":
    asyncio.run(main())