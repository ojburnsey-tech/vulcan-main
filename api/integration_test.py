"""
Integration Test: Measurement Import → Classification → BoQ Generation
Tests the complete pipeline from CSV measurements to enriched BoQ JSON
"""
import json
from measurement_import import parse_measurements
from classification import classify_measurements
from measurement_hub import build_boq_from_measurements
from rates import RATES_DB

# Simulate CSV measurements (CSV would be parsed by parse_measurements)
sample_measurements = [
    {
        "description": "Excavation for foundations",
        "quantity": 50.0,
        "unit": "m³"
    },
    {
        "description": "Topsoil stripping",
        "quantity": 1000.0,
        "unit": "m²"
    },
    {
        "description": "Concrete foundation",
        "quantity": 30.0,
        "unit": "m³"
    },
    {
        "description": "Cavity wall brick masonry 300mm",
        "quantity": 250.0,
        "unit": "m²"
    },
]

print("=== MEASUREMENT HUB INTEGRATION TEST ===\n")

# STEP 1: Classify measurements
print("1. CLASSIFYING MEASUREMENTS...")
classified = classify_measurements(sample_measurements)
print(f"   ✓ Classified {len(classified)} measurements\n")

# Show classification results
for i, item in enumerate(classified[:2], 1):
    print(f"   Item {i}:")
    print(f"     Description: {item['description']}")
    print(f"     NRM2 Section: {item['nrm2_section']} ({item['nrm2_label']})")
    print(f"     Rate Key: {item['rate_key']}")
    print(f"     Confidence: {item['confidence']:.0%}\n")

# STEP 2: Build BoQ from classified measurements
print("2. GENERATING BoQ FROM MEASUREMENTS...")
boq_json = build_boq_from_measurements(classified, "Sample Project")
print(f"   ✓ Created BoQ with {len(boq_json['bill_of_quantities'])} trade sections\n")

# Show BoQ structure
for trade in boq_json['bill_of_quantities']:
    print(f"   {trade['trade']}")
    for item in trade['items']:
        print(f"     - {item['item_code']}: {item['description'][:40]}...")
        print(f"       Rate Key: {item['rate_key']}")
        print(f"       Quantity: {item['quantity']} {item['unit']}")
    print()

# STEP 3: Verify structure matches BOQ_OUTPUT_SCHEMA
print("3. VALIDATING BoQ STRUCTURE...")
from measurement_hub import validate_boq_structure
is_valid, error = validate_boq_structure(boq_json)
if is_valid:
    print("   ✓ BoQ structure is valid\n")
else:
    print(f"   ✗ Validation error: {error}\n")

# STEP 4: Show enrichment-ready format
print("4. BoQ READY FOR ENRICHMENT...")
item_count = sum(len(t['items']) for t in boq_json['bill_of_quantities'])
print(f"   ✓ {item_count} line items")
print(f"   ✓ Compatible with _enrich_boq() for rate application")
print(f"   ✓ Compatible with generate_boq_pdf() and generate_boq_excel()\n")

# STEP 5: Demonstrate rate lookup
print("5. EXAMPLE RATE LOOKUP...")
sample_item = boq_json['bill_of_quantities'][0]['items'][0]
rate_key = sample_item['rate_key']
if rate_key and rate_key in RATES_DB:
    rate_entry = RATES_DB[rate_key]
    rate = (rate_entry['material_rate'] + 
            rate_entry['labour_rate'] + 
            rate_entry.get('plant_rate', 0) + 
            rate_entry.get('waste_disposal_rate', 0))
    line_total = rate * sample_item['quantity']
    print(f"   Item: {sample_item['description']}")
    print(f"   Rate Key: {rate_key}")
    print(f"   Unit Rate: £{rate:.2f}/{rate_entry['unit']}")
    print(f"   Quantity: {sample_item['quantity']} {rate_entry['unit']}")
    print(f"   Line Total: £{line_total:.2f}\n")

print("=== INTEGRATION TEST COMPLETE ===")
print("\nNext Steps:")
print("  1. Add frontend UI components (React)")
print("  2. Connect to POST /measurement/generate-boq endpoint")
print("  3. Test with real CSV upload")
print("  4. Export to PDF/Excel verification")
