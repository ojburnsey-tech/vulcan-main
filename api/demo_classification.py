# api/demo_classification.py
# Demo showing the measurement classification system in action

from mapping_loader import _loader, get_loader_status
from measurement_classifier import classify_measurement

# Initialize
print("=" * 80)
print("BLUEBEAM MEASUREMENT CLASSIFICATION ENGINE - DEMO")
print("=" * 80)

# Load mappings
print("\n1. LOADING MAPPINGS FROM SPREADSHEET")
print("-" * 80)
ok, msg = _loader.load()
print(f"   Result: {msg}")
status = get_loader_status()
print(f"   File: {status['file_path']}")
print(f"   Loaded: {status['count']} measurement mappings")

# Show sample classifications
print("\n2. EXAMPLE CLASSIFICATIONS")
print("-" * 80)

examples = [
    "Ceramic floor tile",
    "CERAMIC FLOOR TILE",
    "  Ceramic floor tile  ",
    "Reinforced concrete foundations",
    "LED ceiling luminaire downlight",
    "Unknown material type",
]

for i, desc in enumerate(examples, 1):
    result = classify_measurement(desc)
    print(f"\n   Example {i}:")
    print(f"   Input: '{desc}'")
    
    if result["matched"]:
        print(f"   Status: ✓ MATCHED")
        print(f"   Trade Code: {result['trade_code']}")
        print(f"   Trade Group: {result['trade_group']}")
        print(f"   CSI Division: {result['csi_division']}")
        print(f"   Unit: {result['unit']}")
        print(f"   Takeoff Type: {result['takeoff_type']}")
    else:
        print(f"   Status: ✗ NO MATCH - No mapping found for this description")

print("\n" + "=" * 80)
print("3. KEY FEATURES")
print("-" * 80)
print("   ✓ Loads spreadsheet once at startup (no reload on every request)")
print("   ✓ Fast lookup using in-memory index")
print("   ✓ Exact match (case-sensitive) with fallback to case-insensitive")
print("   ✓ Whitespace trimming")
print("   ✓ NO AI classification - only spreadsheet matches")
print("   ✓ Returns {matched: false} if no mapping exists")

print("\n" + "=" * 80)
print("END OF DEMO")
print("=" * 80)
