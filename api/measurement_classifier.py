# api/measurement_classifier.py
# Measurement classification service that prioritizes direct spreadsheet mappings.
#
# This service looks up measurement descriptions against the Bluebeam Term Mapping
# spreadsheet. It does NOT use AI or Claude — only exact/case-insensitive matches
# against the loaded mappings.
#
# The mapping spreadsheet data takes absolute priority over any other method.

from typing import Dict, Optional
from mapping_loader import lookup_measurement


class MeasurementClassifier:
    """Service for classifying measurements based on the Bluebeam Term Mapping."""

    @staticmethod
    def classify(description: str) -> Dict:
        """Classify a measurement description.

        Args:
            description: The measurement description to classify (e.g., "Wall Area")

        Returns:
            dict with one of two shapes:

            Success (mapping found):
            {
                "matched": True,
                "description": str,  # Original input
                "trade_code": str,
                "trade_group": str,
                "csi_division": str,
                "unit": str,
                "takeoff_type": str,
            }

            Not found:
            {
                "matched": False,
                "description": str,  # Original input
            }

            No AI fallback is used. Only exact/case-insensitive spreadsheet matches.
        """
        if not description or not isinstance(description, str):
            return {
                "matched": False,
                "description": description,
            }

        # Trim whitespace
        clean_description = description.strip()
        if not clean_description:
            return {
                "matched": False,
                "description": description,
            }

        # Look up in mappings
        mapping = lookup_measurement(clean_description)

        if mapping:
            return {
                "matched": True,
                "description": clean_description,
                "trade_code": mapping.get("trade_code"),
                "trade_group": mapping.get("trade_group"),
                "csi_division": mapping.get("csi_division"),
                "unit": mapping.get("unit"),
                "takeoff_type": mapping.get("takeoff_type"),
            }
        else:
            return {
                "matched": False,
                "description": clean_description,
            }

    @staticmethod
    def batch_classify(descriptions: list) -> list:
        """Classify a batch of measurement descriptions.

        Args:
            descriptions: List of measurement description strings

        Returns:
            List of classification results (same shape as classify())
        """
        if not isinstance(descriptions, list):
            return []

        results = []
        for desc in descriptions:
            results.append(MeasurementClassifier.classify(desc))
        return results


# Convenience function
def classify_measurement(description: str) -> Dict:
    """Classify a single measurement description."""
    return MeasurementClassifier.classify(description)
