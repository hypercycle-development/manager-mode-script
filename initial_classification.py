import json
from typing import Dict, Set, List

def read_addresses(filename: str) -> Set[str]:
    with open(filename, 'r') as f:
        return {line.strip() for line in f if line.strip() and not line.startswith('#')}

def read_hts_files(pattern: str, num_files: int) -> Dict[str, Set[str]]:
    licenses = {}
    for i in range(1, num_files + 1):
        try:
            with open(pattern.format(i), 'r') as f:
                next(f)  # Skip header
                for line in f:
                    if line.strip():
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            addr, lid = parts[0], parts[1]
                            licenses.setdefault(addr, set()).add(lid)
        except FileNotFoundError:
            continue
    return licenses

def generate_initial_classification(tranche_addrs: Set[str], 
                                  hts_licenses: Dict[str, Set[str]],
                                  issues_addrs: Set[str]) -> Dict:
    classification = {
        "direct_compensation": sorted(issues_addrs),
        "with_licenses": {},
        "without_licenses": sorted(tranche_addrs - hts_licenses.keys() - issues_addrs)
    }
    
    for addr in tranche_addrs:
        if addr in hts_licenses and addr not in issues_addrs:
            classification["with_licenses"][addr] = sorted(hts_licenses[addr])
    
    return classification

if __name__ == "__main__":
    # Read input files
    tranche_addrs = read_addresses("./data_tillers/tranche1_addresses.txt")
    issues_addrs = read_addresses("./data_tillers/hts_tilling_issues.txt")
    hts_licenses = read_hts_files("./data_tillers/merk_data/hts{}.txt", 6)
    
    # Generate classification
    report = generate_initial_classification(tranche_addrs, hts_licenses, issues_addrs)
    
    # Save output
    with open("initial_classification.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print("Initial classification saved to initial_classification.json")