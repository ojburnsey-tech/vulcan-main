"""
Measurement Hub → BoQ Conversion Module

Converts classified measurements into BoQ (Bill of Quantities) JSON format.
Reuses existing rate engine and validation logic.

This module bridges the measurement import/classification pipeline with
the existing BoQ generation, export, and project storage infrastructure.
"""

from typing import List, Dict, Optional, Tuple
from rates import RATES_DB


# NRM2 Section order (canonical sorting)
_NRM2_SECTION_ORDER = {
    "5.1": 10, "5.4": 30, "5.8": 40, "5.9": 50,
    "5.11": 60, "5.12": 70, "5.14": 80, "5.15": 90,
    "5.18": 100, "5.21": 130, "5.23": 140, "5.24": 150,
    "5.28": 160, "5.29": 170, "5.31": 180, "5.35": 190
}

# NRM2 section labels (matching classification.py)
_NRM2_LABELS = {
    "5.1": "Groundworks",
    "5.4": "In-situ concrete",
    "5.8": "Masonry",
    "5.9": "Structural metalwork",
    "5.11": "Carpentry and joinery",
    "5.12": "Roofing",
    "5.14": "Mechanical services",
    "5.15": "Electrical services",
    "5.17": "Plastering and internal finishes",
    "5.18": "Roof coverings",
    "5.21": "Drainage below ground",
    "5.23": "Windows and external doors",
    "5.24": "Doors",
    "5.28": "Floor, wall and ceiling finishes",
    "5.29": "Decoration",
    "5.31": "Insulation",
    "5.35": "External works"
}


def _group_by_nrm2(classified_measurements: List[Dict]) -> Dict[str, List[Dict]]:
    """Group classified measurements by NRM2 section.
    
    Args:
        classified_measurements: List of measurements from /measurement/classify
        Each has 'nrm2_section' (e.g., '5.1'), 'description', 'quantity', 'unit', 'rate_key'
    
    Returns:
        Dict mapping section code (e.g., '5.1') to list of measurements in that section
    """
    grouped = {}
    for measurement in classified_measurements:
        section = measurement.get('nrm2_section', '5.1')  # Default to groundworks
        if section not in grouped:
            grouped[section] = []
        grouped[section].append(measurement)
    return grouped


def _create_item_from_measurement(measurement: Dict, sequence: int) -> Dict:
    """Convert a classified measurement into a BoQ line item.
    
    Args:
        measurement: Classified measurement dict
        sequence: Item sequence number within section (1, 2, 3, ...)
    
    Returns:
        BoQ item dict with all mandatory fields
    """
    nrm2_section = measurement.get('nrm2_section', '5.1')
    item_code = f"{nrm2_section}/{sequence:03d}"  # e.g., 5.1/001, 5.1/002
    
    return {
        "description": measurement.get('description', ''),
        "rate_key": measurement.get('rate_key'),  # None if no match (QS fills in manually)
        "quantity": measurement.get('quantity'),
        "unit": measurement.get('normalised_unit', measurement.get('unit', 'm')),
        "item_code": item_code,
        "dimension_string": "",  # Would be populated by QS in normal flow
        "drawing_ref": "",  # Optional; not in measurements
        "cdp": False,  # Default; QS can override
        "performance_requirement": "",  # Default; QS can override
        "measurement_confidence": measurement.get('confidence', 0.0),  # Informational
    }


def build_boq_from_measurements(
    classified_measurements: List[Dict],
    project_name: str = "Draft BoQ from Measurements"
) -> Dict:
    """Convert classified measurements into BoQ JSON format.
    
    This function:
    1. Groups measurements by NRM2 section
    2. Creates line items with mandatory fields
    3. Sequences item codes (5.X/001, 5.X/002, ...)
    4. Maintains NRM2 order (5.1 before 5.4 before 5.8, etc.)
    5. Returns JSON compatible with _enrich_boq() and export functions
    
    Args:
        classified_measurements: Output from /measurement/classify
        project_name: Project name (informational only)
    
    Returns:
        Dict matching BOQ_OUTPUT_SCHEMA (ready for enrichment via _enrich_boq)
        Structure:
        {
            "bill_of_quantities": [
                {
                    "trade": "5.1 Groundworks",
                    "items": [...]
                },
                ...
            ],
            "risk_schedule": [],
            "assumptions_register": []
        }
    """
    grouped = _group_by_nrm2(classified_measurements)
    
    # Build trades in NRM2 order
    bill_of_quantities = []
    for section_code in sorted(grouped.keys(), key=lambda s: _NRM2_SECTION_ORDER.get(s, 999)):
        measurements_in_section = grouped[section_code]
        section_label = _NRM2_LABELS.get(section_code, "Other")
        trade_name = f"{section_code} {section_label}"
        
        items = []
        for sequence, measurement in enumerate(measurements_in_section, start=1):
            item = _create_item_from_measurement(measurement, sequence)
            items.append(item)
        
        bill_of_quantities.append({
            "trade": trade_name,
            "items": items
        })
    
    # Return BoQ structure compatible with export functions
    return {
        "bill_of_quantities": bill_of_quantities,
        "risk_schedule": [],  # User can add later
        "assumptions_register": [],  # User can add later
    }


def validate_boq_structure(boq_json: Dict) -> Tuple[bool, Optional[str]]:
    """Quick validation that BoQ structure is valid for enrichment.
    
    Args:
        boq_json: BoQ dict from build_boq_from_measurements()
    
    Returns:
        (is_valid, error_message) tuple
    """
    if not isinstance(boq_json, dict):
        return False, "BoQ must be a dict"
    
    if 'bill_of_quantities' not in boq_json:
        return False, "Missing 'bill_of_quantities' key"
    
    if not isinstance(boq_json['bill_of_quantities'], list):
        return False, "bill_of_quantities must be a list"
    
    for trade in boq_json['bill_of_quantities']:
        if not isinstance(trade, dict):
            return False, "Each trade must be a dict"
        if 'trade' not in trade or 'items' not in trade:
            return False, f"Trade missing 'trade' or 'items' key: {trade}"
        if not isinstance(trade['items'], list):
            return False, f"Trade items must be a list: {trade}"
        
        for item in trade['items']:
            if not isinstance(item, dict):
                return False, "Each item must be a dict"
            for key in ['description', 'rate_key', 'quantity', 'unit', 'item_code']:
                if key not in item:
                    return False, f"Item missing required key: {key}"
    
    return True, None
