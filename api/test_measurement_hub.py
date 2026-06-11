"""Unit tests for measurement_hub.py integration module
Tests the measurement → BoQ conversion pipeline with various scenarios
"""
import unittest
import sys
import os

# Add parent directory to path so imports work
sys.path.insert(0, os.path.dirname(__file__))

from measurement_hub import (
    build_boq_from_measurements,
    validate_boq_structure,
    _group_by_nrm2,
    _create_item_from_measurement,
)


class TestMeasurementHubConversion(unittest.TestCase):
    """Test measurement to BoQ conversion"""

    def test_empty_measurements(self):
        """Converting empty measurement list should create empty BoQ"""
        result = build_boq_from_measurements([])
        self.assertIsInstance(result, dict)
        self.assertEqual(result['bill_of_quantities'], [])
        self.assertEqual(result['risk_schedule'], [])
        self.assertEqual(result['assumptions_register'], [])

    def test_single_measurement_single_section(self):
        """Single measurement should create single trade with one item"""
        measurements = [
            {
                "description": "Excavation for foundations",
                "quantity": 50.0,
                "unit": "m³",
                "normalised_unit": "m³",
                "nrm2_section": "5.1",
                "rate_key": "excavation_reduced_level_machine",
                "confidence": 0.95,
            }
        ]
        result = build_boq_from_measurements(measurements)
        
        self.assertEqual(len(result['bill_of_quantities']), 1)
        trade = result['bill_of_quantities'][0]
        self.assertEqual(trade['trade'], "5.1 Groundworks")
        self.assertEqual(len(trade['items']), 1)
        
        item = trade['items'][0]
        self.assertEqual(item['description'], "Excavation for foundations")
        self.assertEqual(item['quantity'], 50.0)
        self.assertEqual(item['unit'], "m³")
        self.assertEqual(item['item_code'], "5.1/001")
        self.assertEqual(item['rate_key'], "excavation_reduced_level_machine")

    def test_multiple_measurements_same_section(self):
        """Multiple measurements in same section should sequence item codes"""
        measurements = [
            {
                "description": "Excavation",
                "quantity": 50.0,
                "unit": "m³",
                "normalised_unit": "m³",
                "nrm2_section": "5.1",
                "rate_key": "excavation_reduced_level_machine",
                "confidence": 0.95,
            },
            {
                "description": "Topsoil stripping",
                "quantity": 1000.0,
                "unit": "m²",
                "normalised_unit": "m²",
                "nrm2_section": "5.1",
                "rate_key": "topsoil_strip_150mm",
                "confidence": 0.88,
            },
        ]
        result = build_boq_from_measurements(measurements)
        
        self.assertEqual(len(result['bill_of_quantities']), 1)
        trade = result['bill_of_quantities'][0]
        self.assertEqual(len(trade['items']), 2)
        
        # Verify sequential item codes
        self.assertEqual(trade['items'][0]['item_code'], "5.1/001")
        self.assertEqual(trade['items'][1]['item_code'], "5.1/002")

    def test_measurements_multiple_sections(self):
        """Multiple sections should be grouped and sorted in NRM2 order"""
        measurements = [
            {
                "description": "Masonry",
                "quantity": 100.0,
                "unit": "m²",
                "normalised_unit": "m²",
                "nrm2_section": "5.8",
                "rate_key": "brick_wall",
                "confidence": 0.85,
            },
            {
                "description": "Excavation",
                "quantity": 50.0,
                "unit": "m³",
                "normalised_unit": "m³",
                "nrm2_section": "5.1",
                "rate_key": "excavation_reduced_level_machine",
                "confidence": 0.95,
            },
            {
                "description": "Concrete",
                "quantity": 30.0,
                "unit": "m³",
                "normalised_unit": "m³",
                "nrm2_section": "5.4",
                "rate_key": "concrete_standard",
                "confidence": 0.90,
            },
        ]
        result = build_boq_from_measurements(measurements)
        
        # Should have 3 trades
        self.assertEqual(len(result['bill_of_quantities']), 3)
        
        # Verify NRM2 order: 5.1 < 5.4 < 5.8
        self.assertIn("5.1", result['bill_of_quantities'][0]['trade'])
        self.assertIn("5.4", result['bill_of_quantities'][1]['trade'])
        self.assertIn("5.8", result['bill_of_quantities'][2]['trade'])

    def test_section_labels_preserved(self):
        """NRM2 section labels should match reference"""
        measurements = [
            {
                "description": "Test item",
                "quantity": 1.0,
                "unit": "item",
                "normalised_unit": "item",
                "nrm2_section": "5.14",
                "rate_key": None,
                "confidence": 0.0,
            }
        ]
        result = build_boq_from_measurements(measurements)
        trade = result['bill_of_quantities'][0]
        self.assertEqual(trade['trade'], "5.14 Mechanical services")

    def test_missing_rate_key_allowed(self):
        """Items with no rate_key should be created (QS fills in manually)"""
        measurements = [
            {
                "description": "Unknown item",
                "quantity": 10.0,
                "unit": "nr",
                "normalised_unit": "nr",
                "nrm2_section": "5.1",
                "rate_key": None,  # No match
                "confidence": 0.0,
            }
        ]
        result = build_boq_from_measurements(measurements)
        item = result['bill_of_quantities'][0]['items'][0]
        self.assertIsNone(item['rate_key'])
        self.assertEqual(item['description'], "Unknown item")


class TestMeasurementHubValidation(unittest.TestCase):
    """Test BoQ structure validation"""

    def test_valid_boq_structure(self):
        """Valid BoQ should pass validation"""
        boq = {
            "bill_of_quantities": [
                {
                    "trade": "5.1 Groundworks",
                    "items": [
                        {
                            "description": "Test",
                            "rate_key": "test",
                            "quantity": 1.0,
                            "unit": "m",
                            "item_code": "5.1/001",
                        }
                    ]
                }
            ]
        }
        is_valid, error = validate_boq_structure(boq)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_invalid_not_dict(self):
        """Non-dict input should fail"""
        is_valid, error = validate_boq_structure([])
        self.assertFalse(is_valid)
        self.assertIn("must be a dict", error)

    def test_invalid_missing_bill_of_quantities(self):
        """Missing bill_of_quantities key should fail"""
        boq = {"risk_schedule": []}
        is_valid, error = validate_boq_structure(boq)
        self.assertFalse(is_valid)
        self.assertIn("bill_of_quantities", error)


if __name__ == '__main__':
    unittest.main()
