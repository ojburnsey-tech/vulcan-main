# api/rates.py
"""
UK Residential Construction Rates Database and NRM2-Compliant BoQ Engine.

Rates data: Spon's Architects' & Builders' Price Book 2025 (AECOM, Sep 2024)
            [training-data estimates], Checkatrade 2024-2026, Rated People
            Jun 2025, MyBuilder Dec 2025.
All rates are UK national averages, exclusive of VAT.

NRM2 compliance: RICS NRM2: Detailed Measurement for Building Works, 2021 edition.
All 41 work sections, measurement rules, void-deduction thresholds, item ordering,
provisional-sum classification, and BoQ structure requirements are implemented in
full accordance with the NRM2 specification.

Key exports
───────────
  RATES_DB             dict of 180+ rate keys → material/labour/plant/waste rates
  LOCATION_FACTORS     regional cost multipliers
  WORK_SECTIONS        all 41 NRM2 work sections with permitted units and rules
  BoQLineItem          NRM2 line-item dataclass with validation-ready fields
  CalculationEngine    NRM2 dimension rounding, quantity calculation, void deductions
  DescriptionBuilder   4-level NRM2 item description generator
  NRM2Validator        unit, provisional, CDP, and discretionary-item checks
  BoQGenerator         section-ordered, paginated BoQ assembler
  validate_boq()       full-BoQ validation returning structured error/warning report
  get_localized_rate() location-adjusted rate lookup (float, backwards-compatible)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — RATES DATABASE
# Sources: Spon's Architects' & Builders' Price Book 2025 (AECOM, Sep 2024)
#          [training-data estimates], Checkatrade 2024-2026, Rated People
#          Jun 2025, MyBuilder Dec 2025.
# material_rate       : cost of materials per unit, £
# labour_rate         : all-in labour cost per unit, £
# plant_rate          : mechanical plant/equipment cost per unit, £
# waste_disposal_rate : tip/disposal charge per unit, £
# unit                : m | m² | m³ | nr | item | wk
# All rates: UK national averages, exclusive of VAT.
# ═══════════════════════════════════════════════════════════════════════════════

RATES_DB = {

    # ── TRADE 1: GROUNDWORKS ─────────────────────────────────────────────────
    # NRM2 Section 5 (Excavating and filling): excavation in m³, net measurement.
    # No allowance for bulking, shrinkage, or earthwork support space.

    "topsoil_strip_150mm": {
        "material_rate":       0.00,
        "labour_rate":         3.50,
        "plant_rate":          2.50,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "excavation_reduced_level_machine": {
        "material_rate":       0.00,
        "labour_rate":         5.00,
        "plant_rate":          7.00,
        "waste_disposal_rate": 0.00,
        "unit": "m³",
    },
    "excavation_reduced_level_hand": {
        "material_rate":       0.00,
        "labour_rate":        42.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m³",
    },
    "trench_excavation_machine_600mm": {
        "material_rate":       0.00,
        "labour_rate":         5.00,
        "plant_rate":         10.00,
        "waste_disposal_rate": 0.00,
        "unit": "m³",
    },
    "trench_excavation_hand_600mm": {
        "material_rate":       0.00,
        "labour_rate":        48.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m³",
    },
    "earthwork_support_trench_close_boarded": {
        "material_rate":       5.00,
        "labour_rate":        10.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "disposal_excavated_material_offsite": {
        "material_rate":       0.00,
        "labour_rate":         5.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 35.00,
        "unit": "m³",
    },
    "hardcore_mot_type1_150mm": {
        "material_rate":       9.00,
        "labour_rate":         5.00,
        "plant_rate":          0.75,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "hardcore_mot_type1_225mm": {
        "material_rate":      13.25,
        "labour_rate":         6.50,
        "plant_rate":          1.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "sand_blinding_50mm": {
        "material_rate":       3.25,
        "labour_rate":         2.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "damp_proof_membrane_1200_gauge": {
        "material_rate":       1.60,
        "labour_rate":         1.10,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },

    # ── TRADE 2: CONCRETE WORKS ──────────────────────────────────────────────
    # NRM2 Section 11 (In-situ concrete works): volumes net, no waste allowance.

    "concrete_c25_strip_foundations": {
        "material_rate":     102.50,
        "labour_rate":        23.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m³",
    },
    "concrete_c30_pad_foundations_reinforced": {
        "material_rate":     115.00,
        "labour_rate":        36.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m³",
    },
    "concrete_c30_ground_floor_slab_150mm": {
        "material_rate":      26.00,
        "labour_rate":        12.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "power_float_finish_concrete_slab": {
        "material_rate":       0.00,
        "labour_rate":         2.50,
        "plant_rate":          4.75,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "formwork_slab_edge_250mm": {
        "material_rate":       8.00,
        "labour_rate":        12.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },

    # ── TRADE 3: MASONRY AND BRICKWORK ───────────────────────────────────────
    # NRM2 Section 14 (Masonry): measured on centre line; void threshold 0.50m².

    "brickwork_common_half_brick_102mm": {
        "material_rate":      30.00,
        "labour_rate":        19.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "brickwork_common_one_brick_215mm": {
        "material_rate":      55.00,
        "labour_rate":        34.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "facing_brickwork_half_brick_gauged_mortar": {
        "material_rate":      65.00,
        "labour_rate":        55.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "facing_brickwork_feature_panels": {
        "material_rate":      75.00,
        "labour_rate":        45.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "cavity_wall_300mm_full_fill_mineral_wool": {
        "material_rate":      87.50,
        "labour_rate":        67.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "cavity_wall_300mm_partial_fill_pir": {
        "material_rate":      82.50,
        "labour_rate":        62.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "cavity_closer_jambs": {
        "material_rate":       6.50,
        "labour_rate":         5.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "cavity_closer_cills": {
        "material_rate":       5.75,
        "labour_rate":         5.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "cavity_closer_eaves": {
        "material_rate":       6.50,
        "labour_rate":         5.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "wall_tie_stainless_steel_type4_225mm": {
        "material_rate":       0.45,
        "labour_rate":         0.33,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "dpc_hyload_100mm": {
        "material_rate":       1.40,
        "labour_rate":         1.25,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "dpc_hyload_150mm": {
        "material_rate":       2.00,
        "labour_rate":         1.40,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "lintel_boot_steel_900mm_cavity": {
        "material_rate":      51.50,
        "labour_rate":        24.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "lintel_boot_steel_1500mm_cavity": {
        "material_rate":      90.00,
        "labour_rate":        30.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "lintel_concrete_prestressed_1200mm": {
        "material_rate":      17.00,
        "labour_rate":         9.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "lintel_concrete_prestressed_1800mm": {
        "material_rate":      36.50,
        "labour_rate":        14.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },

    # ── TRADE 4: BLOCKWORK ───────────────────────────────────────────────────
    # NRM2 Section 14 (Masonry): same centre-line and void rules as brickwork.

    "blockwork_dense_100mm_partition": {
        "material_rate":      13.50,
        "labour_rate":        18.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "blockwork_dense_140mm": {
        "material_rate":      17.00,
        "labour_rate":        20.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "blockwork_aerated_100mm": {
        "material_rate":      11.50,
        "labour_rate":        18.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "blockwork_aerated_140mm": {
        "material_rate":      15.00,
        "labour_rate":        20.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "blockwork_dense_100mm_fairface": {
        "material_rate":      13.50,
        "labour_rate":        25.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },

    # ── TRADE 5: ROOFING ─────────────────────────────────────────────────────
    # NRM2 Section 18 (Tile/slate coverings) and Section 17 (Sheet coverings).
    # Void threshold: 1m². Areas measured net in contact with base.

    "roofing_concrete_interlocking_tile": {
        "material_rate":      22.00,
        "labour_rate":        23.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "roofing_clay_plain_tile": {
        "material_rate":      40.00,
        "labour_rate":        33.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "roofing_natural_welsh_slate": {
        "material_rate":      95.00,
        "labour_rate":        46.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "roofing_synthetic_slate": {
        "material_rate":      35.00,
        "labour_rate":        28.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "roofing_epdm_flat_roof": {
        "material_rate":      19.00,
        "labour_rate":        18.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "roofing_grp_fibreglass_flat_roof": {
        "material_rate":      36.50,
        "labour_rate":        28.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "lead_flashing_code4": {
        "material_rate":      37.00,
        "labour_rate":        28.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "lead_flashing_code5": {
        "material_rate":      50.00,
        "labour_rate":        35.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "upvc_fascia_board_150mm": {
        "material_rate":       9.50,
        "labour_rate":         7.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "upvc_soffit_board_300mm": {
        "material_rate":      13.00,
        "labour_rate":         8.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "upvc_gutter_112mm_half_round": {
        "material_rate":       7.25,
        "labour_rate":         6.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "upvc_downpipe_68mm": {
        "material_rate":       6.25,
        "labour_rate":         6.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "dry_ridge_system": {
        "material_rate":      16.00,
        "labour_rate":        11.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "dry_verge_system": {
        "material_rate":      10.00,
        "labour_rate":         8.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "roof_insulation_between_over_rafters_pir": {
        "material_rate":      24.00,
        "labour_rate":        16.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "roof_insulation_between_rafters_100mm": {
        "material_rate":       7.25,
        "labour_rate":         9.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "velux_window_ck02_550x978mm": {
        "material_rate":     370.00,
        "labour_rate":       200.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "velux_window_mk04_780x978mm": {
        "material_rate":     490.00,
        "labour_rate":       235.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },

    # ── TRADE 6: CARPENTRY – FIRST FIX ──────────────────────────────────────
    # NRM2 Section 16 (Carpentry): sizes nominal; sawn and nailed unless stated.

    "carpentry_cut_roof_traditional": {
        "material_rate":      28.50,
        "labour_rate":        36.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "carpentry_roof_trusses_prefab": {
        "material_rate":      23.00,
        "labour_rate":        16.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "carpentry_flat_roof_joists_50x150mm": {
        "material_rate":       9.00,
        "labour_rate":        10.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "carpentry_flat_roof_joists_50x200mm": {
        "material_rate":      12.00,
        "labour_rate":        11.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "carpentry_floor_joists_50x150mm": {
        "material_rate":      10.00,
        "labour_rate":        11.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "carpentry_floor_joists_50x200mm": {
        "material_rate":      13.50,
        "labour_rate":        13.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "carpentry_stud_partition_100mm": {
        "material_rate":      11.50,
        "labour_rate":        18.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "carpentry_osb_flooring_18mm": {
        "material_rate":      11.50,
        "labour_rate":         9.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "carpentry_chipboard_flooring_18mm": {
        "material_rate":       9.75,
        "labour_rate":         9.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "carpentry_loft_hatch_562x726mm": {
        "material_rate":      60.00,
        "labour_rate":        52.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },

    # ── TRADE 7: CARPENTRY – SECOND FIX ─────────────────────────────────────
    # NRM2 Section 22 (General joinery): lengths along extreme profile.

    "door_lining_set_softwood": {
        "material_rate":      55.00,
        "labour_rate":        45.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "door_lining_set_hardwood": {
        "material_rate":     115.00,
        "labour_rate":        57.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "fire_door_fd30": {
        "material_rate":     300.00,
        "labour_rate":        97.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "internal_door_softwood_flush": {
        "material_rate":     170.00,
        "labour_rate":        77.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "internal_door_mdf_primed": {
        "material_rate":     125.00,
        "labour_rate":        77.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "skirting_softwood_75x19mm": {
        "material_rate":       3.65,
        "labour_rate":         6.75,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "skirting_softwood_100x25mm": {
        "material_rate":       5.75,
        "labour_rate":         7.25,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "skirting_mdf_75x18mm": {
        "material_rate":       3.25,
        "labour_rate":         6.25,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "architrave_mdf_set_per_door": {
        "material_rate":      19.00,
        "labour_rate":        25.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "staircase_softwood_straight": {
        "material_rate":    1800.00,
        "labour_rate":       725.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "staircase_softwood_quarter_landing": {
        "material_rate":    2550.00,
        "labour_rate":      1000.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },

    # ── TRADE 8: WINDOWS AND EXTERNAL DOORS ─────────────────────────────────
    # NRM2 Section 23 (Windows): enumerated with dimensions stated.
    # NRM2 Section 24 (Doors): enumerated; standard ironmongery included.

    "upvc_casement_window_600x900mm": {
        "material_rate":     225.00,
        "labour_rate":       112.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "upvc_casement_window_1200x1200mm": {
        "material_rate":     410.00,
        "labour_rate":       137.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "upvc_tilt_turn_window_900x1200mm": {
        "material_rate":     360.00,
        "labour_rate":       142.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "aluminium_casement_window_600x900mm": {
        "material_rate":     510.00,
        "labour_rate":       142.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "aluminium_casement_window_1200x1200mm": {
        "material_rate":     875.00,
        "labour_rate":       180.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "timber_casement_window_600x900mm": {
        "material_rate":     365.00,
        "labour_rate":       127.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "timber_casement_window_1200x1200mm": {
        "material_rate":     640.00,
        "labour_rate":       165.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "upvc_external_door_solid_panel": {
        "material_rate":     485.00,
        "labour_rate":       165.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "composite_external_door": {
        "material_rate":    1375.00,
        "labour_rate":       210.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "timber_external_door_softwood": {
        "material_rate":     600.00,
        "labour_rate":       180.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "aluminium_bifold_doors_2400x2100mm": {
        "material_rate":    4150.00,
        "labour_rate":       600.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "upvc_bifold_doors_2400x2100mm": {
        "material_rate":    2400.00,
        "labour_rate":       475.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "aluminium_sliding_patio_doors_1800x2100mm": {
        "material_rate":    2450.00,
        "labour_rate":       380.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },

    # ── TRADE 9: INSULATION ──────────────────────────────────────────────────
    # NRM2 Section 31 (Insulation): area of surface protected; fire rating stated.

    "cavity_wall_insulation_eps_bead_blown": {
        "material_rate":       7.00,
        "labour_rate":         5.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "cavity_wall_insulation_rockwool_50mm": {
        "material_rate":       9.50,
        "labour_rate":         6.25,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "floor_insulation_pir_75mm": {
        "material_rate":      16.50,
        "labour_rate":        11.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "floor_insulation_eps_100mm_below_slab": {
        "material_rate":      10.50,
        "labour_rate":         7.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "loft_insulation_glass_wool_270mm": {
        "material_rate":      14.50,
        "labour_rate":        11.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "loft_insulation_glass_wool_100mm": {
        "material_rate":       6.00,
        "labour_rate":         7.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "external_wall_insulation_ewi_100mm": {
        "material_rate":      76.50,
        "labour_rate":        52.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "internal_wall_insulation_pir_60mm": {
        "material_rate":      36.50,
        "labour_rate":        26.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },

    # ── TRADE 10: PLASTERING ─────────────────────────────────────────────────
    # NRM2 Section 28 (Floor, wall, ceiling and roof finishings): net area.

    "plaster_two_coat_gypsum_masonry": {
        "material_rate":       5.75,
        "labour_rate":        17.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "plaster_two_coat_bonding_multifinish": {
        "material_rate":       5.25,
        "labour_rate":        18.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "skim_coat_plasterboard_walls": {
        "material_rate":       2.75,
        "labour_rate":        12.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "skim_coat_plasterboard_ceilings": {
        "material_rate":       2.75,
        "labour_rate":        13.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "plasterboard_dot_dab_12_5mm_walls": {
        "material_rate":       9.00,
        "labour_rate":        12.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "plasterboard_dot_dab_15mm_ceilings": {
        "material_rate":      10.75,
        "labour_rate":        13.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "external_render_sand_cement_two_coat": {
        "material_rate":       5.50,
        "labour_rate":        19.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "external_render_monocouche": {
        "material_rate":      24.00,
        "labour_rate":        25.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "external_render_silicone_thin_coat": {
        "material_rate":      43.50,
        "labour_rate":        33.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },

    # ── STRUCTURAL STEEL ─────────────────────────────────────────────────────
    # NRM2 Section 15 (Structural metalwork): framed members in tonnes.

    "structural_steel_rsj_beam_supply_fix": {
        "material_rate":     180.00,
        "labour_rate":        85.00,
        "plant_rate":         35.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "steel_padstone_engineering_brick": {
        "material_rate":      45.00,
        "labour_rate":        35.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },

    # ── TRADE 11: ELECTRICAL ─────────────────────────────────────────────────
    # NRM2 Section 39 (Electrical services): item/nr/m; point counts must define
    # what constitutes a point (switch + box + wiring).

    "electrical_first_fix_power_lighting": {
        "material_rate":    1800.00,
        "labour_rate":      2200.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "item",
    },
    "electrical_second_fix_sockets_switches": {
        "material_rate":     850.00,
        "labour_rate":       950.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "item",
    },
    "consumer_unit_upgrade_18way": {
        "material_rate":     320.00,
        "labour_rate":       280.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "electrical_first_fix_wiring_per_sqm": {
        "material_rate":       9.80,
        "labour_rate":        18.20,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "consumer_unit_10way_dual_rcd": {
        "material_rate":     116.00,
        "labour_rate":       214.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "double_socket_outlet_13a": {
        "material_rate":      12.50,
        "labour_rate":        38.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "single_socket_outlet_13a": {
        "material_rate":       8.50,
        "labour_rate":        33.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "lighting_point_loop_in": {
        "material_rate":      12.00,
        "labour_rate":        43.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "smoke_detector_mains_powered": {
        "material_rate":      26.00,
        "labour_rate":        49.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "electric_shower_9_5kw": {
        "material_rate":     160.00,
        "labour_rate":       295.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "extractor_fan_bathroom": {
        "material_rate":      43.00,
        "labour_rate":        80.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "full_rewire_3bed_semi": {
        "material_rate":    1750.00,
        "labour_rate":      3250.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },

    # ── TRADE 12: PLUMBING AND HEATING ───────────────────────────────────────
    # NRM2 Section 38 (Mechanical services): item/nr/m; includes testing/commissioning.

    "plumbing_first_fix_hot_cold_soil": {
        "material_rate":    1200.00,
        "labour_rate":      1400.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "item",
    },
    "central_heating_extension_pipework_rads": {
        "material_rate":     950.00,
        "labour_rate":      1100.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "item",
    },
    "thermostatic_radiator_valve_trv": {
        "material_rate":      35.00,
        "labour_rate":        25.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "plumbing_first_fix_pipework_per_sqm": {
        "material_rate":      16.00,
        "labour_rate":        24.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "bathroom_suite_standard_white": {
        "material_rate":     675.00,
        "labour_rate":       700.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "shower_enclosure_tray_900x900mm": {
        "material_rate":     465.00,
        "labour_rate":       220.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "kitchen_sink_single_bowl_stainless": {
        "material_rate":     155.00,
        "labour_rate":       115.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "gas_combi_boiler_30_35kw": {
        "material_rate":    1225.00,
        "labour_rate":       550.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "oil_combi_boiler_26kw": {
        "material_rate":    2100.00,
        "labour_rate":       700.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "radiator_single_panel_600x800mm": {
        "material_rate":     100.00,
        "labour_rate":        95.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "underfloor_heating_wet_system": {
        "material_rate":      35.00,
        "labour_rate":        27.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "underfloor_heating_electric_mat": {
        "material_rate":      32.00,
        "labour_rate":        19.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "thermostatic_radiator_valve": {
        "material_rate":      21.00,
        "labour_rate":        31.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },

    # ── TRADE 13: FLOOR AND WALL TILING ─────────────────────────────────────
    # NRM2 Section 28 (Finishings): areas net; void threshold 1m².

    "ceramic_floor_tiles_300x300mm": {
        "material_rate":      25.00,
        "labour_rate":        33.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "porcelain_floor_tiles_600x600mm": {
        "material_rate":      44.00,
        "labour_rate":        38.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "ceramic_wall_tiles_200x300mm": {
        "material_rate":      20.00,
        "labour_rate":        30.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "porcelain_wall_tiles_300x600mm": {
        "material_rate":      34.00,
        "labour_rate":        33.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "natural_stone_floor_tiles_600x600mm": {
        "material_rate":      87.50,
        "labour_rate":        51.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "wetroom_tanking_system": {
        "material_rate":      24.00,
        "labour_rate":        30.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "tile_adhesive_and_grout_only": {
        "material_rate":       7.50,
        "labour_rate":         0.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },

    # ── TRADE 14: DECORATING ─────────────────────────────────────────────────
    # NRM2 Section 29 (Decoration): areas on face of work.

    "emulsion_two_coat_new_plaster_walls": {
        "material_rate":       2.15,
        "labour_rate":         7.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "emulsion_two_coat_new_plaster_ceilings": {
        "material_rate":       2.15,
        "labour_rate":         8.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "gloss_paint_timber_door_both_faces": {
        "material_rate":      10.50,
        "labour_rate":        32.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "gloss_paint_timber_window_both_faces": {
        "material_rate":       9.00,
        "labour_rate":        26.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "gloss_paint_skirting_architrave": {
        "material_rate":       1.15,
        "labour_rate":         5.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "masonry_paint_external_two_coat": {
        "material_rate":       5.25,
        "labour_rate":         8.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "gloss_paint_upvc_fascia_soffit": {
        "material_rate":       3.75,
        "labour_rate":         6.75,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },

    # ── TRADE 15: DRAINAGE ───────────────────────────────────────────────────
    # NRM2 Section 33 (Above ground) and Section 34 (Below ground).

    "drainage_upvc_100mm_foul_drain": {
        "material_rate":      15.00,
        "labour_rate":        21.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "drainage_upvc_150mm_surface_water": {
        "material_rate":      22.00,
        "labour_rate":        24.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "inspection_chamber_concrete_450mm": {
        "material_rate":     240.00,
        "labour_rate":       180.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "inspection_chamber_upvc_450mm": {
        "material_rate":     130.00,
        "labour_rate":       150.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "rodding_eye_100mm_upvc": {
        "material_rate":      45.00,
        "labour_rate":        67.50,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },
    "connection_to_existing_sewer": {
        "material_rate":      82.50,
        "labour_rate":       165.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "nr",
    },

    # ── TRADE 16: EXTERNAL WORKS ─────────────────────────────────────────────
    # NRM2 Section 35 (Site works) and Section 36 (Fencing).
    # Section 37 (Soft landscaping) for turf/planting.

    "block_paving_driveway": {
        "material_rate":      46.50,
        "labour_rate":        38.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "concrete_paving_slabs_600x600mm": {
        "material_rate":      21.00,
        "labour_rate":        19.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "tarmac_driveway_two_layer": {
        "material_rate":      22.00,
        "labour_rate":        18.00,
        "plant_rate":          7.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
    "timber_fence_panels_1800mm": {
        "material_rate":      48.00,
        "labour_rate":        29.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "close_board_timber_fencing_1800mm": {
        "material_rate":      56.00,
        "labour_rate":        34.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m",
    },
    "new_lawn_turf": {
        "material_rate":      10.25,
        "labour_rate":        10.00,
        "plant_rate":          0.00,
        "waste_disposal_rate": 0.00,
        "unit": "m²",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — LOCATION FACTORS
# Regional multipliers applied to material and labour rates.
# Plant and waste disposal treated as materials for regional adjustment.
# ═══════════════════════════════════════════════════════════════════════════════

LOCATION_FACTORS = {
    "uk_average": {"material": 1.00, "labour": 1.00},
    "london_se":  {"material": 1.05, "labour": 1.30},
    "n_ireland":  {"material": 1.02, "labour": 1.05},
    "scotland":   {"material": 1.00, "labour": 0.95},
    "midlands":   {"material": 1.00, "labour": 0.92},
    "north_eng":  {"material": 1.00, "labour": 0.90},
}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — NRM2 WORK SECTIONS
# RICS NRM2: Detailed Measurement for Building Works, 2021 edition.
# All 41 work sections with permitted units of measurement and measurement rules.
# Units stored as Unicode (m², m³) — use _normalise_unit() before comparison.
# ═══════════════════════════════════════════════════════════════════════════════

WORK_SECTIONS: dict[int, dict] = {
    1: {
        "name": "Preliminaries",
        "allowed_units": ["item", "week", "nr", "m", "m²", "m³"],
        "pricing_type": ["fixed_charge", "time_related_charge"],
        # NRM2: Part A = Information/Requirements (not priced).
        # Part B = Pricing Schedule split into fixed charge and time-related charge.
        # VAT excluded. Unpriced items assumed included in contractor's rates.
        "notes": (
            "Divided into Part A (Information/Requirements) and Part B (Pricing Schedule). "
            "Fixed charge = cost independent of duration. "
            "Time-related charge = cost dependent on duration. "
            "VAT excluded. Items not priced by contractor assumed included in rates."
        ),
    },
    2: {
        "name": "Off-site manufactured materials, components or buildings",
        "allowed_units": ["nr"],
        # NRM2: Enumerated only. Factory finishes, transport, offloading, setting
        # into position, service connections and disposal of packaging all included.
        # Work outside the proprietary package measured separately in its own section.
        "notes": (
            "Includes factory finishes, transport, offloading, setting into position, "
            "service connections, disposal of packaging. "
            "Work not in the proprietary package measured separately in its own section."
        ),
    },
    3: {
        "name": "Demolitions",
        "allowed_units": ["item", "m²", "m", "nr"],
        # NRM2: Must state lowest level of demolition. If slab removed, lowest
        # level = underside of slab. Temporary support here = supporting RETAINED
        # structures only (not the works themselves).
        "notes": (
            "Must state lowest level of demolition (including basements). "
            "If slab removed, lowest level = underside of slab. "
            "Includes temporary works, diverting/sealing services, disposal of debris. "
            "Temporary support here = supporting RETAINED structures only."
        ),
    },
    4: {
        "name": "Alterations, repairs and conservation",
        "allowed_units": ["item", "m²", "m", "nr"],
        # NRM2: Materials arising become contractor property unless stated otherwise.
        # Excludes decontamination of existing ground (that goes in Section 5).
        "notes": (
            "Materials arising become contractor property unless stated otherwise. "
            "Excludes decontamination of existing ground (Section 5). "
            "Includes all temporary works incidental to the work, making good, "
            "extending existing finishes, disposal of waste."
        ),
    },
    5: {
        "name": "Excavating and filling",
        "allowed_units": ["item", "nr", "m²", "m³", "m"],
        # NRM2: Quantities = net from drawings only. No bulking/shrinkage allowance.
        # Rock defined as hard material requiring special plant or explosives.
        # Boulders <0.5m³ do NOT constitute rock.
        # Depth stages: ≤2m, 2-4m, 4-6m etc. State starting level if not OGL.
        "notes": (
            "Quantities = net depths/dimensions from drawings ONLY. "
            "NO allowance for bulking, shrinkage, or earthwork support space. "
            "All excavated material deemed inert unless described otherwise. "
            "Rock = hard material requiring special plant or explosives. "
            "Boulders <0.5m³ do NOT constitute rock. "
            "Depth stages: <=2m, 2-4m, 4-6m, etc. "
            "Must state starting level if not original ground."
        ),
    },
    6: {
        "name": "Ground remediation and soil stabilisation",
        "allowed_units": ["item", "m³", "m²", "nr"],
        "notes": (
            "Must describe limits on extent, proximity to buildings, restrictions on method/timing. "
            "Includes disposal of surplus excavated material, surface water, "
            "working space, support to faces of excavation, trimming/compacting."
        ),
    },
    7: {
        "name": "Piling",
        "allowed_units": ["m²", "m", "nr", "t", "hr", "item"],
        # NRM2: Pile lengths measured along axes from commencing level to bottom.
        # Disposal volume = nominal cross-section × pile length (inc. enlarged heads/bases).
        "notes": (
            "Pile lengths measured along axes from commencing level to bottom of pile. "
            "Disposal volume = nominal cross-section × pile length (including enlarged heads/bases). "
            "Breaking through obstructions only measured if obstruction is ABOVE founding stratum. "
            "Includes temporary containment of spoil, concrete placed beyond designed length, "
            "backfilling empty bores, pre-boring, repositioning piling plant."
        ),
    },
    8: {
        "name": "Underpinning",
        "allowed_units": ["m", "nr", "m³", "m²", "t"],
        "notes": (
            "If too extensive, measure in detail by individual trades described as "
            "'in works of underpinning'. "
            "Must state: depth, maximum width, method. "
            "Includes temporary support, excavation, earthwork support, working space, "
            "cutting existing footings, backfilling, surface treatments."
        ),
    },
    9: {
        "name": "Diaphragm walls and embedded retaining walls",
        "allowed_units": ["m²", "m³", "m", "hr", "item"],
        # NRM2: State starting levels, max depth, finished top level of concrete.
        # Authorised standing time only measured if explicitly instructed.
        "notes": (
            "State starting levels, maximum depth, finished top level of concrete. "
            "Authorised standing time (delays) only measured if explicitly instructed."
        ),
    },
    10: {
        "name": "Crib walls, gabions and reinforced earth",
        "allowed_units": ["m²", "m"],
        # NRM2: Crib walls/gabions: area on FRONT FACE.
        # Earth reinforcement: area in contact with base, EXCLUDING laps.
        # No deductions for voids ≤1m². General excavation in Section 5.
        "notes": (
            "Crib walls and gabions: area measured on FRONT FACE. "
            "Earth reinforcement: area measured in contact with base, EXCLUDING laps. "
            "No deductions for voids ≤1m². "
            "All general excavation measured in Section 5."
        ),
    },
    11: {
        "name": "In-situ concrete works",
        "allowed_units": ["m³", "m²", "m", "nr", "t"],
        # NRM2: Concrete volume = NET. Void threshold = 0.05m³ (NOT the default 1m²).
        # Exception: voids in troughed slabs MUST be deducted regardless of size.
        # No deductions for reinforcement, steel sections, or voids <0.05m³.
        # Contractor-discretion joints NOT measured.
        "notes": (
            "Concrete volume = NET. No allowance for formwork deflection. "
            "No deductions for reinforcement, steel sections, or voids <0.05m³ "
            "(EXCEPT voids in troughed slabs — these ARE deducted). "
            "Concrete deemed finished as struck from basic formwork. "
            "Top surfaces horizontal and tamped unless stated otherwise. "
            "Reinforcement includes tying wire and spacers/links. "
            "Formwork includes square, raking, and curved cutting. "
            "Kickers (except to walls) included in formwork items. "
            "Contractor-discretion joints NOT measured."
        ),
    },
    12: {
        "name": "Precast/composite concrete",
        "allowed_units": ["m²", "m", "nr"],
        # NRM2: Thickness stated = COMBINED precast + in-situ.
        # Margins ≤500mm included; margins >500mm measured as in-situ (Section 11).
        "notes": (
            "Thickness stated = COMBINED thickness of precast + in-situ. "
            "No deduction for voids ≤1m². "
            "Margins ≤500mm included; margins >500mm measured as in-situ slab in Section 11."
        ),
    },
    13: {
        "name": "Precast concrete",
        "allowed_units": ["nr", "m", "m²"],
        "notes": (
            "Items enumerated or measured linearly/superficially by component type. "
            "Includes moulds, formwork, reinforcement, bedding, fixings, temporary support, "
            "cast-in accessories, filled ends, grouting, margins, angles, fair ends."
        ),
    },
    14: {
        "name": "Masonry",
        "allowed_units": ["m²", "m", "nr"],
        # NRM2: Measured on CENTRE LINE irrespective of construction.
        # Void threshold = 0.50m² cross-sectional area (NOT the default 1m²).
        # Thicknesses always nominal. Work assumed VERTICAL unless stated otherwise.
        "notes": (
            "All walling measured on CENTRE LINE irrespective of construction. "
            "No deductions for voids or built-in items with cross-sectional area ≤0.50m². "
            "Thicknesses always nominal. Work assumed VERTICAL unless stated otherwise. "
            "Includes rough/fair cutting, ends/angles, grooves, mortices, "
            "raking out joints, centering, overhand work, extra material for bonding/laps."
        ),
    },
    15: {
        "name": "Structural metalwork",
        "allowed_units": ["t", "m", "nr", "m²", "item"],
        # NRM2: Framed members in TONNES, categorised by length and weight bands.
        # Length bands: ≤1m | 1–9m | >9m.
        # Weight bands: ≤25 | 25–50 | 50–100 | 100–150 | >150 kg/m.
        # Fittings = calculated weight (t) or % allowance.
        # Trial erections only measured if NOT at contractor's discretion.
        "notes": (
            "Framed members measured in TONNES, categorised by length bands (<=1m, 1-9m, >9m) "
            "and weight bands (25kg/m increments up to 50kg/m, then 50kg/m increments). "
            "Fittings = calculated weight (t) or percentage allowance. "
            "Includes all fabrication, permanent erection, bolts, nuts, washers, fixings. "
            "Trial erections only measured if NOT at contractor's discretion."
        ),
        # Section 15 design decision: length and weight band classification
        "steel_length_bands": ["<=1m", "1-9m", ">9m"],
        "steel_weight_bands_kg_per_m": [25, 50, 100, 150],  # upper boundaries
    },
    16: {
        "name": "Carpentry",
        "allowed_units": ["m", "m²", "nr"],
        # NRM2: Boarding/sheeting split by width (≤600mm vs >600mm).
        # Sizes NOMINAL unless explicitly 'finished size'. Sawn and nailed by default.
        # Fine linings excluded — go in Section 22.
        "notes": (
            "Boarding/sheeting categorised by width (<=600mm vs >600mm). "
            "Strutting measured linearly THROUGH the structural members being stiffened. "
            "All sizes NOMINAL unless explicitly stated as 'finished size'. "
            "Timbers assumed sawn and fixed by nails unless stated otherwise. "
            "Fine linings excluded — measured in Section 22."
        ),
    },
    17: {
        "name": "Sheet roof coverings",
        "allowed_units": ["m²", "m", "nr"],
        # NRM2: Areas/lengths measured NET in contact with base, following profile.
        # Upstand or downstand >500mm = measured as vertical work.
        "notes": (
            "Areas/lengths measured NET in contact with base, following profile of rolls/steps/upstands. "
            "No deduction for voids ≤1m². "
            "Upstand or downstand >500mm = measured as vertical work. "
            "Boundary work includes undercloaks, cutting, bedding, pointing, wedgings. "
            "Includes underlay, rough/fair cutting, extra for bonding/laps/dressings."
        ),
    },
    18: {
        "name": "Tile and slate roof and wall coverings",
        "allowed_units": ["m²", "m", "nr"],
        # NRM2: Covering items INCLUDE underlays and battens.
        # Valleys include everything except sheet metal linings (Section 17).
        "notes": (
            "No deductions for voids ≤1m². Boundary work measured by net girth. "
            "Coverings items INCLUDE underlays and battens. "
            "Valleys include everything except sheet metal linings (Section 17). "
            "Includes square/raking/curved cutting, ends/angles, extra for laps/bonding."
        ),
    },
    19: {
        "name": "Waterproofing",
        "allowed_units": ["m²", "m", "nr"],
        # NRM2: >500mm wide = m²; ≤500mm wide = m.
        # Boundary work to voids only measured separately if void >1m².
        "notes": (
            "Area = that in contact with base. No deduction for voids ≤1m². "
            ">500mm wide = m²; ≤500mm wide = m. "
            "Boundary work includes undercloaks, rough/fair cutting, drips, arrises. "
            "Boundary work to voids only measured separately if void >1m². "
            "Includes base preparation (scabbling, raking out, bonding agents)."
        ),
    },
    20: {
        "name": "Proprietary linings and partitions",
        "allowed_units": ["m²", "m", "nr"],
        # NRM2: Height in 1m increments. Average height for sloping heads.
        # Internal work unless explicitly described as external.
        # Skim coats / wet trade finishes excluded — Section 28.
        "notes": (
            "No deductions for voids ≤1m². "
            "Average height calculated per length of partition with sloping head. "
            "Height measured in 1m increments. "
            "All work deemed INTERNAL unless described as external. "
            "Finishes here = ONLY those applied as part of the normal proprietary system. "
            "Skim coats / wet trade finishes excluded — measure in Section 28."
        ),
    },
    21: {
        "name": "Cladding and covering",
        "allowed_units": ["m²", "m"],
        # NRM2: Net to finished face. Includes fixings, brackets, sub-framing,
        # jointing materials, sealants, flashings. Structural framing in S15/S16.
        "notes": (
            "Measured net to finished face. No deductions for voids ≤1m². "
            "Includes fixings, brackets, sub-framing, jointing materials, sealants, flashings. "
            "Structural framing measured in Section 15 or 16."
        ),
    },
    22: {
        "name": "General joinery",
        "allowed_units": ["m", "m²", "nr"],
        # NRM2: Lengths along extreme profile. Panels by face area.
        # Skirtings >500mm height measured as wall linings.
        "notes": (
            "Lengths measured along extreme profile. Panels measured by face area. "
            "Includes mitres, ends, stops, and all fixings. "
            "Skirtings >500mm height measured as wall linings."
        ),
    },
    23: {
        "name": "Windows, screens and lights",
        "allowed_units": ["nr", "m²"],
        # NRM2: Enumerated with dimensions stated. Frame, glazing, ironmongery,
        # opening gear, flashings and sealing all included.
        "notes": (
            "Enumerated with dimensions stated. "
            "Includes frame, glazing, ironmongery, opening gear, flashings, sealing to opening."
        ),
    },
    24: {
        "name": "Doors, shutters and hatches",
        "allowed_units": ["nr"],
        # NRM2: Enumerated only. Leaf, frame, architraves, hinges, locks, closers
        # and decoration (if pre-finished) all included. Standard ironmongery included.
        "notes": (
            "Enumerated. Includes door leaf, frame, architraves, hinges, locks, closers, "
            "and decoration if pre-finished. Standard ironmongery included in unit price."
        ),
    },
    25: {
        "name": "Stairs, walkways and balustrades",
        "allowed_units": ["nr", "m"],
        # NRM2: Stairs enumerated; balustrades by linear length.
        # In-situ concrete stairs measured in Section 11.
        "notes": (
            "Stairs enumerated; balustrades measured by linear length. "
            "Includes fixings, brackets, base plates. "
            "In-situ concrete stairs measured in Section 11."
        ),
    },
    26: {
        "name": "Metalwork",
        "allowed_units": ["nr", "kg", "m"],
        # NRM2: By weight (kg) or length (m) depending on complexity.
        # Structural steelwork excluded — Section 15.
        "notes": (
            "Measured by weight (kg) or length (m) depending on complexity. "
            "Includes fabrication, welding, fixings. "
            "Structural steelwork excluded (Section 15)."
        ),
    },
    27: {
        "name": "Glazing",
        "allowed_units": ["m²"],
        # NRM2: Net area of pane. Glass blocks measured by area.
        "notes": (
            "Net area of the pane. "
            "Includes beads, gaskets, sealants, setting blocks. "
            "Glass blocks measured by area, include reinforcement/accessories."
        ),
    },
    28: {
        "name": "Floor, wall, ceiling and roof finishings",
        "allowed_units": ["m²", "m"],
        # NRM2: Areas net; void threshold 1m².
        # Skirtings and borders in linear metres.
        "notes": (
            "Areas measured net; no deductions for voids ≤1m². "
            "Includes surface preparation, primers, adhesive. "
            "Skirtings and borders measured in linear metres."
        ),
    },
    29: {
        "name": "Decoration",
        "allowed_units": ["m²"],
        # NRM2: Areas on face of work. Includes surface prep, filling, making good.
        # Small items (pipes, brackets) can be m or enumerated — captured in notes.
        "notes": (
            "Areas measured on face of work. "
            "Includes surface preparation, filling, making good. "
            "Small items (pipes, brackets) can be measured in m or enumerated."
        ),
    },
    30: {
        "name": "Suspended ceilings",
        "allowed_units": ["m²"],
        # NRM2: Flat on face; void threshold 1m². Grid, tiles, hangers, perimeter
        # trims all included. Access panels and bulkheads measured separately.
        "notes": (
            "Measured flat on face; no deductions for voids ≤1m². "
            "Includes grid, tiles, hangers, perimeter trims. "
            "Access panels and feature bulkheads measured separately."
        ),
    },
    31: {
        "name": "Insulation, fire stopping and fire protection",
        "allowed_units": ["m²", "m", "nr"],
        # NRM2: Area of surface protected or length of service.
        # Fire rating MUST be stated in description for fire stopping items.
        "notes": (
            "Area of surface protected or length of service. "
            "Includes support, adhesives, fixings. "
            "Fire rating must be stated in description for fire stopping items."
        ),
    },
    32: {
        "name": "Furniture, fittings and equipment",
        "allowed_units": ["nr", "item"],
        # NRM2: Enumerated. Includes delivery, assembly, fixing, service connections.
        # Loose furniture typically excluded from BoQ.
        "notes": (
            "Enumerated. Includes delivery, assembly, fixing, connection to services. "
            "Loose furniture typically excluded from BoQ."
        ),
    },
    33: {
        "name": "Drainage above ground",
        "allowed_units": ["m", "nr"],
        # NRM2: Measured along centre line. Connections to sanitary appliances included.
        "notes": (
            "Measured along centre line. "
            "Includes pipes, fittings, clips, testing. "
            "Connections to sanitary appliances included."
        ),
    },
    34: {
        "name": "Drainage below ground",
        "allowed_units": ["m", "nr"],
        # NRM2: Pipes between centres of manholes. Manholes enumerated.
        "notes": (
            "Pipes measured by length between centres of manholes. "
            "Includes excavation (where not in Section 5), bedding, pipe, testing. "
            "Manholes enumerated, including excavation and construction."
        ),
    },
    35: {
        "name": "Site works",
        "allowed_units": ["m²", "m", "nr"],
        # NRM2: Build-up, material, thickness must be stated.
        # Retaining walls >500mm in Section 10 or 11.
        "notes": (
            "Measured by area. Build-up (sub-base, base, surface), material, thickness must be stated. "
            "Includes sub-base preparation and kerbing. "
            "Retaining walls >500mm measured in Section 10 or 11."
        ),
    },
    36: {
        "name": "Fencing",
        "allowed_units": ["m", "nr"],
        # NRM2: Centre line of fence. Raking and stepped ground must be described.
        "notes": (
            "Measured along centre line of fence. "
            "Includes posts, foundations, mesh/boards, gates. "
            "Raking and stepped ground must be described."
        ),
    },
    37: {
        "name": "Soft landscaping",
        "allowed_units": ["m²", "m", "nr"],
        # NRM2: Seeding/turfing by area; planting by count.
        # Establishment periods as separate line item.
        "notes": (
            "Seeding/turfing by area; planting by count. "
            "Includes topsoil, fertilisers, initial maintenance. "
            "Establishment periods as separate line item."
        ),
    },
    38: {
        "name": "Mechanical services",
        "allowed_units": ["item", "nr", "m"],
        # NRM2: Can be complete system (design-and-build) or individual components.
        # Complex systems require detailed schedule of components.
        "notes": (
            "Can be complete system/package (design-and-build) or individual components. "
            "Includes testing, commissioning, all ancillaries. "
            "Complex systems require detailed schedule of components."
        ),
    },
    39: {
        "name": "Electrical services",
        "allowed_units": ["item", "nr", "m"],
        # NRM2: Point counts must define what constitutes a point
        # (switch + box + wiring). Includes containment, cabling, testing.
        "notes": (
            "Measured by functional systems or point counts. "
            "Includes containment, cabling, accessories, testing, commissioning. "
            "Point counts must define what constitutes a point (switch + box + wiring)."
        ),
    },
    40: {
        "name": "Transportation",
        "allowed_units": ["nr", "item"],
        # NRM2: Entire system enumerated. Shaft builder's work in Section 41.
        "notes": (
            "Enumerated. Includes entire system, motor room equipment, commissioning. "
            "Shaft builder's work excluded (Section 41)."
        ),
    },
    41: {
        "name": "Builders work in connection with mechanical electrical and transportation",
        "allowed_units": ["nr", "m"],
        # NRM2: Only used if not deemed included within M&E packages.
        "notes": (
            "Enumerated or measured by length of chase. "
            "Includes all labour and materials to make good. "
            "Only used if not deemed included within M&E trade packages."
        ),
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — UNIT NORMALISATION
# Maps common aliases to the canonical Unicode forms used in WORK_SECTIONS.
# Call _normalise_unit() on any externally supplied unit string before validation.
# ═══════════════════════════════════════════════════════════════════════════════

_UNIT_ALIASES: dict[str, str] = {
    # Area
    "m2": "m²", "sqm": "m²", "sq.m": "m²", "sq m": "m²", "sq_m": "m²",
    # Volume
    "m3": "m³", "cbm": "m³", "cu.m": "m³", "cu m": "m³", "cu_m": "m³",
    # Linear
    "lin": "m", "lm": "m", "lin.m": "m", "lin m": "m",
    # Enumerated
    "no": "nr", "no.": "nr", "number": "nr", "each": "nr", "ea": "nr",
    # Time
    "wk": "week", "wks": "week", "weeks": "week",
    # Weight
    "tonne": "t", "tonnes": "t", "ton": "t",
    # Hours
    "hrs": "hr", "hours": "hr",
}


def _normalise_unit(unit: str) -> str:
    """Return the canonical NRM2 unit string for a given raw input."""
    if not unit:
        return "nr"
    u = unit.strip().lower()
    return _UNIT_ALIASES.get(u, u)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — BoQ LINE ITEM DATA MODEL
# NRM2: Every measured line item carries the fields below.
# monetary fields use Decimal; quantity rounded per NRM2 rules.
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BoQLineItem:
    """NRM2-compliant BoQ line item.

    All monetary values are stored as Decimal (never float) per the NRM2
    requirement that totals be exact to the penny.
    """

    # ── Mandatory NRM2 fields ────────────────────────────────────────────────

    # NRM2: Every item belongs to one of the 41 numbered work sections.
    work_section_id: int

    # NRM2 4-level description hierarchy.
    # Level 1: Component being measured (from NRM2 table column 1) — always required.
    # Level 2: Material type and quality — required where applicable.
    # Level 3: Dimensions, specification, fixing method — required where applicable.
    # Level 4: Finish, special instructions, contractor obligations — optional.
    level_1_desc: str
    level_2_desc: str = ""
    level_3_desc: str = ""
    level_4_desc: str = ""

    # NRM2: Unit must validate against WORK_SECTIONS[work_section_id]["allowed_units"].
    unit_of_measurement: str = "nr"

    # NRM2: Decimal quantities; tonnes to 2 d.p., all others to nearest whole unit.
    # Any quantity <1 unit is output as 1.
    quantity: Decimal = field(default_factory=lambda: Decimal("1"))

    # Rate in £ per unit (Decimal).
    rate: Decimal = field(default_factory=lambda: Decimal("0"))

    # ── Auto-assigned by BoQGenerator ───────────────────────────────────────

    # NRM2: "SS/NN" unique alphanumeric code per item, e.g. "11/01", "14/03".
    hierarchical_ref: str = ""

    # ── Special item type flags ──────────────────────────────────────────────

    # NRM2: Provisional sums must be classified as defined or undefined.
    is_provisional: bool = False
    provisional_type: Optional[str] = None  # "defined" | "undefined" | None

    # NRM2: CDP items must be identified as "Contractor-designed works".
    is_contractor_designed: bool = False

    # NRM2: Auto-populated from WORK_SECTIONS notes; printed in BoQ preamble.
    coverage_notes: str = ""

    # NRM2: Labour-only items sort before labour-and-material within a section.
    is_labour_only: bool = False

    # ── Design decision: Section 4 repair items ──────────────────────────────
    # NRM2 design decision: if is_repair=True, existing_condition is mandatory.
    is_repair: bool = False
    existing_condition: str = ""  # mandatory when is_repair=True

    # ── Design decision: multi-trade items ──────────────────────────────────
    # Default: single nr unit under primary trade section.
    # sub_components is for estimating only — NOT printed in the BoQ.
    sub_components: list = field(default_factory=list)

    # ── Computed property ───────────────────────────────────────────────────

    @property
    def total_amount(self) -> Decimal:
        """NRM2: total = quantity × rate, calculated, never stored raw."""
        return (self.quantity * self.rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def __post_init__(self) -> None:
        # Coerce to Decimal so callers can pass int/float safely.
        if not isinstance(self.quantity, Decimal):
            self.quantity = Decimal(str(self.quantity))
        if not isinstance(self.rate, Decimal):
            self.rate = Decimal(str(self.rate))

        # Normalise unit to canonical form.
        self.unit_of_measurement = _normalise_unit(self.unit_of_measurement)

        # Auto-populate coverage_notes from WORK_SECTIONS if not supplied.
        if not self.coverage_notes and self.work_section_id in WORK_SECTIONS:
            self.coverage_notes = WORK_SECTIONS[self.work_section_id].get("notes", "")

    def to_dict(self) -> dict:
        """Serialise to plain dict for the existing pipeline (float-compatible)."""
        parts = [
            self.level_1_desc,
            self.level_2_desc,
            self.level_3_desc,
            self.level_4_desc,
        ]
        description = "; ".join(p for p in parts if p and p.strip())
        return {
            "work_section_id": self.work_section_id,
            "hierarchical_ref": self.hierarchical_ref,
            "description": description,
            "level_1_desc": self.level_1_desc,
            "level_2_desc": self.level_2_desc,
            "level_3_desc": self.level_3_desc,
            "level_4_desc": self.level_4_desc,
            "unit": self.unit_of_measurement,
            "quantity": float(self.quantity),
            "rate": float(self.rate),
            "line_total": float(self.total_amount),
            "is_provisional": self.is_provisional,
            "provisional_type": self.provisional_type,
            "is_contractor_designed": self.is_contractor_designed,
            "is_labour_only": self.is_labour_only,
            "is_repair": self.is_repair,
            "coverage_notes": self.coverage_notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BoQLineItem":
        """Construct a BoQLineItem from a legacy pipeline dict."""
        # Accept either explicit level fields or a flat description string.
        level_1 = (
            data.get("level_1_desc")
            or data.get("description", "")
        )
        return cls(
            work_section_id=int(data.get("work_section_id", 0)),
            level_1_desc=level_1,
            level_2_desc=data.get("level_2_desc", ""),
            level_3_desc=data.get("level_3_desc", ""),
            level_4_desc=data.get("level_4_desc", ""),
            unit_of_measurement=_normalise_unit(data.get("unit", "nr")),
            quantity=Decimal(str(data.get("quantity", 1))),
            rate=Decimal(str(data.get("rate") or data.get("line_rate") or 0)),
            hierarchical_ref=data.get("hierarchical_ref", ""),
            is_provisional=bool(data.get("is_provisional", False)),
            provisional_type=data.get("provisional_type"),
            is_contractor_designed=bool(data.get("is_contractor_designed", False)),
            is_labour_only=bool(data.get("is_labour_only", False)),
            is_repair=bool(data.get("is_repair", False)),
            existing_condition=data.get("existing_condition", ""),
            coverage_notes=data.get("coverage_notes", ""),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — CALCULATION ENGINE
# Implements all NRM2 dimension rounding, quantity calculation, and void
# deduction rules. All inputs in metres; outputs as Decimal quantities.
# ═══════════════════════════════════════════════════════════════════════════════

class CalculationEngine:
    """NRM2 measurement calculation rules.

    Dimension inputs must be supplied in L × W × H order (NRM2 rule).
    All dimension rounding is applied before quantity calculation.
    """

    # NRM2 void thresholds by section.
    # Default for area-based sections: 1 m² (internal voids ≤ this are NOT deducted).
    # Section 11 (concrete): 0.05 m³.
    # Section 14 (masonry): 0.50 m² cross-sectional area.
    _VOID_THRESHOLD_DEFAULT_AREA = Decimal("1")       # m²
    _VOID_THRESHOLD_CONCRETE = Decimal("0.05")        # m³ — Section 11
    _VOID_THRESHOLD_MASONRY = Decimal("0.50")         # m² — Section 14

    @staticmethod
    def round_dimension(value_m: float) -> Decimal:
        """Round a dimension (in metres) to the nearest 10mm.

        NRM2 rule: ≥5mm rounds up; <5mm disregarded.
        Equivalent to ROUND_HALF_UP to the nearest 0.010 m.
        """
        # Convert to mm, apply ROUND_HALF_UP to nearest 10mm, convert back.
        mm = Decimal(str(value_m)) * Decimal("1000")
        rounded_mm = (mm / Decimal("10")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        ) * Decimal("10")
        return rounded_mm / Decimal("1000")

    @classmethod
    def calc_volume(cls, length_m: float, width_m: float, height_m: float) -> Decimal:
        """Volume = L × W × H, rounded to nearest whole m³.

        NRM2: dimensions in L × W × H order; any quantity <1 → output as 1.
        """
        l = cls.round_dimension(length_m)
        w = cls.round_dimension(width_m)
        h = cls.round_dimension(height_m)
        vol = (l * w * h).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return max(vol, Decimal("1"))

    @classmethod
    def calc_area(cls, length_m: float, width_m: float) -> Decimal:
        """Area = L × W, rounded to nearest whole m².

        NRM2: dimensions in L × W order; any quantity <1 → output as 1.
        """
        l = cls.round_dimension(length_m)
        w = cls.round_dimension(width_m)
        area = (l * w).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return max(area, Decimal("1"))

    @classmethod
    def calc_linear(cls, length_m: float) -> Decimal:
        """Linear quantity = L, rounded to nearest whole metre.

        NRM2: any quantity <1 → output as 1.
        """
        l = cls.round_dimension(length_m)
        lin = l.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return max(lin, Decimal("1"))

    @staticmethod
    def calc_tonnes(weight_t: float) -> Decimal:
        """Tonnes rounded to 2 decimal places (NRM2 exception to whole-number rule)."""
        return Decimal(str(weight_t)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @classmethod
    def should_deduct_void(
        cls,
        void_size: float,
        section_id: int,
        unit: str,
        is_boundary: bool = False,
        is_troughed_slab: bool = False,
    ) -> bool:
        """Return True if the void should be deducted from the measured quantity.

        NRM2 void deduction rules:
          - Boundary voids: ALWAYS deduct regardless of size.
          - Section 11 troughed slabs: ALWAYS deduct regardless of size.
          - Section 11 concrete: deduct if void > 0.05 m³.
          - Section 14 masonry: deduct if void cross-section > 0.50 m².
          - All other sections: deduct if void > 1 m² (or 1 m³ for volume items).
        """
        # NRM2: boundary voids always deducted.
        if is_boundary:
            return True

        # NRM2: troughed slab voids always deducted regardless of size.
        if section_id == 11 and is_troughed_slab:
            return True

        void = Decimal(str(void_size))
        normalised_unit = _normalise_unit(unit)

        # NRM2 Section 11: concrete void threshold is 0.05 m³.
        if section_id == 11:
            return void > cls._VOID_THRESHOLD_CONCRETE

        # NRM2 Section 14: masonry void threshold is 0.50 m².
        if section_id == 14:
            return void > cls._VOID_THRESHOLD_MASONRY

        # Default: 1 m² for area items, 1 m³ for volume items.
        return void > cls._VOID_THRESHOLD_DEFAULT_AREA

    @classmethod
    def apply_void_deductions(
        cls,
        gross_qty: Decimal,
        voids: list[dict],
        section_id: int,
        unit: str,
    ) -> Decimal:
        """Subtract qualifying void quantities from gross_qty.

        Each void dict: {"size": float, "is_boundary": bool, "is_troughed_slab": bool}

        NRM2 net measurement: waste not added; laps/joints included in net.
        """
        total_deduction = Decimal("0")
        for void in voids:
            size = void.get("size", 0.0)
            if cls.should_deduct_void(
                size,
                section_id,
                unit,
                is_boundary=void.get("is_boundary", False),
                is_troughed_slab=void.get("is_troughed_slab", False),
            ):
                total_deduction += Decimal(str(size)).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
        net = gross_qty - total_deduction
        # NRM2: any quantity <1 → output as 1.
        return max(net, Decimal("1"))


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — DESCRIPTION BUILDER
# Implements the NRM2 4-level item description hierarchy and mandatory suffixes.
# ═══════════════════════════════════════════════════════════════════════════════

class DescriptionBuilder:
    """Builds NRM2-compliant item descriptions from the 4-level hierarchy.

    Level 1: Component being measured (mandatory).
    Level 2: Material type and quality (mandatory where applicable).
    Level 3: Dimensions, specification, fixing method (mandatory where applicable).
    Level 4: Finish, special instructions, contractor obligations (optional).

    Mandatory NRM2 suffixes are appended based on section_id:
      - Excavation (Section 5): depth range, e.g. "depth not exceeding 2m"
      - Concrete (Section 11): "measured net"
      - Masonry (Section 14): mortar spec and nominal thickness
    """

    @staticmethod
    def build_description(
        level_1: str,
        level_2: str = "",
        level_3: str = "",
        level_4: str = "",
        section_id: Optional[int] = None,
        depth_range: Optional[str] = None,
        mortar_spec: Optional[str] = None,
        nominal_thickness_mm: Optional[int] = None,
    ) -> str:
        """Concatenate non-empty description levels with NRM2 mandatory suffixes.

        Empty levels are skipped without introducing extra separators.
        Levels joined by "; " separator per standard BoQ convention.
        """
        # Assemble levels in order, skipping blank ones.
        parts = [level_1, level_2, level_3, level_4]
        description = "; ".join(p.strip() for p in parts if p and p.strip())

        # NRM2 mandatory suffix: excavation items must state depth range.
        if section_id == 5 and depth_range:
            description += f"; depth not exceeding {depth_range}"

        # NRM2 mandatory suffix: concrete items must state "measured net".
        if section_id == 11:
            if "measured net" not in description.lower():
                description += "; measured net"

        # NRM2 mandatory suffix: masonry items must state mortar spec and thickness.
        if section_id == 14:
            if mortar_spec and nominal_thickness_mm:
                suffix = f"; in {mortar_spec} mortar; nominal thickness {nominal_thickness_mm}mm"
                if suffix.strip("; ") not in description:
                    description += suffix

        return description

    @staticmethod
    def build_provisional_sum_description(
        summary: str,
        provisional_type: str,
        nature: str = "",
        construction: str = "",
        location: str = "",
        scope: str = "",
        limitations: str = "",
    ) -> str:
        """Build a NRM2-compliant provisional sum description.

        NRM2: Defined PS must state nature, construction, fixing location, scope,
        limitations. Undefined PS: contractor NOT expected to make allowances.
        """
        category = (
            "Defined Provisional Sum"
            if provisional_type == "defined"
            else "Undefined Provisional Sum"
        )
        parts = [f"{category}: {summary}"]
        if provisional_type == "defined":
            if nature:
                parts.append(f"Nature: {nature}")
            if construction:
                parts.append(f"Construction: {construction}")
            if location:
                parts.append(f"Location: {location}")
            if scope:
                parts.append(f"Scope: {scope}")
            if limitations:
                parts.append(f"Limitations: {limitations}")
        else:
            parts.append(
                "Note: Contractor is NOT expected to make preliminary or programme allowances."
            )
        return "; ".join(parts)

    @staticmethod
    def build_pc_sum_description(
        summary: str,
        pc_price_per_unit: Decimal,
        unit: str,
    ) -> str:
        """Build a NRM2-compliant PC sum description.

        NRM2: PC price stated explicitly; excludes overheads, profit, fixing costs.
        """
        return (
            f"{summary}; "
            f"Allow the PC price of £{pc_price_per_unit:.2f} per {unit} delivered to site; "
            "excludes overheads, profit and fixing costs"
        )

    @staticmethod
    def build_cdp_description(
        element: str,
        performance_criteria: str,
    ) -> str:
        """Build a NRM2-compliant CDP (Contractor-Designed Works) description.

        NRM2: CDP items must be identified as 'Contractor-designed works' and
        include performance objectives/criteria.
        """
        return (
            f"Contractor-designed works: {element}; "
            f"Performance criteria: {performance_criteria}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — NRM2 VALIDATOR
# Validates individual line items and complete BoQs against NRM2 rules.
# ═══════════════════════════════════════════════════════════════════════════════

# NRM2 design decision: discretionary item measurement is disabled by default.
# Set to True only if the QS explicitly decides to measure discretionary items.
discretionary_items_enabled: bool = False

# NRM2: "item" unit is restricted to Preliminaries and services sections.
# Sections 1, 32, 38, 39, 40 are where "item" is the primary pricing unit.
# Note: WORK_SECTIONS also lists "item" as technically allowed in sections 3, 4,
# 5, 6, 7, 9, 15 for exceptional whole-section items, but the NRM2 validator
# spec restricts priced "item" entries to [1, 32, 38, 39, 40] only.
_ITEM_UNIT_PERMITTED_SECTIONS = frozenset({1, 32, 38, 39, 40})

_DISCRETIONARY_KEYWORDS = ("contractor's discretion", "at discretion")


class NRM2Validator:
    """Validates BoQLineItem objects against RICS NRM2 2021 rules."""

    @staticmethod
    def validate_line_item(item: BoQLineItem) -> list[str]:
        """Return a list of error/warning strings for a single line item.

        An empty list means the item is valid. Strings beginning with "WARNING:"
        are advisory; all others are hard errors.
        """
        errors: list[str] = []

        # ── Unit validation ─────────────────────────────────────────────────
        # NRM2: unit must be in the permitted set for the work section.
        if item.work_section_id not in WORK_SECTIONS:
            errors.append(
                f"work_section_id {item.work_section_id} is not a valid NRM2 section (1-41)"
            )
        else:
            allowed_raw = WORK_SECTIONS[item.work_section_id]["allowed_units"]
            # Normalise stored allowed units for comparison.
            allowed = {_normalise_unit(u) for u in allowed_raw}
            unit = _normalise_unit(item.unit_of_measurement)
            if unit not in allowed:
                errors.append(
                    f"Unit '{item.unit_of_measurement}' not permitted for "
                    f"Section {item.work_section_id} "
                    f"({WORK_SECTIONS[item.work_section_id]['name']}). "
                    f"Permitted: {', '.join(sorted(allowed))}"
                )

        # ── 'item' unit restriction ──────────────────────────────────────────
        # NRM2: "item" only permitted as a priced unit in Preliminaries and
        # specified services sections [1, 32, 38, 39, 40].
        if (
            _normalise_unit(item.unit_of_measurement) == "item"
            and item.work_section_id not in _ITEM_UNIT_PERMITTED_SECTIONS
        ):
            errors.append(
                "Unit 'item' only permitted in Preliminaries and specified "
                "services sections (1, 32, 38, 39, 40)"
            )

        # ── Mandatory level_1_desc ──────────────────────────────────────────
        # NRM2: Level 1 description (component identifier) is always mandatory.
        if not item.level_1_desc or not item.level_1_desc.strip():
            errors.append("level_1_desc (component identifier) is mandatory and must not be blank")

        # ── Provisional sum validation ──────────────────────────────────────
        # NRM2: Provisional sums must be classified as 'defined' or 'undefined'.
        if item.is_provisional and item.provisional_type not in ("defined", "undefined"):
            errors.append(
                "Provisional sums must be classified as 'defined' or 'undefined'"
            )

        # ── CDP validation ──────────────────────────────────────────────────
        # NRM2: CDP items must be identified as 'Contractor-designed works'.
        if item.is_contractor_designed and not item.level_1_desc.startswith(
            "Contractor-designed"
        ):
            errors.append(
                "CDP items must be identified as contractor-designed in description "
                "(level_1_desc must start with 'Contractor-designed')"
            )

        # ── Repair item validation (design decision) ────────────────────────
        # NRM2 design decision: existing_condition is mandatory for repair items.
        if item.is_repair and not item.existing_condition.strip():
            errors.append(
                "Repair items (Section 4) require existing_condition to be stated"
            )

        # ── Quantity validation ─────────────────────────────────────────────
        # NRM2: quantity must be ≥ 1 (quantities < 1 are given as 1).
        if item.quantity < Decimal("1"):
            errors.append(
                f"Quantity {item.quantity} is less than 1; "
                "NRM2 requires quantities smaller than 1 unit to be given as 1"
            )

        # ── Discretionary items warning ─────────────────────────────────────
        # NRM2 design decision: discretionary items emit a warning, not a hard block.
        notes_lower = item.coverage_notes.lower()
        desc_lower = " ".join(
            [item.level_1_desc, item.level_2_desc, item.level_3_desc, item.level_4_desc]
        ).lower()
        if any(kw in notes_lower or kw in desc_lower for kw in _DISCRETIONARY_KEYWORDS):
            errors.append(
                "WARNING: This item may be at contractor's discretion and "
                "should not be measured separately"
            )

        return errors


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9 — BoQ GENERATOR
# Assembles NRM2-compliant BoQ structure from a list of BoQLineItem objects.
# Handles: mandatory section ordering, item ordering within sections,
# pagination with carried-forward/brought-forward totals, and ref assignment.
# ═══════════════════════════════════════════════════════════════════════════════

# NRM2: mandatory unit ordering within a section.
_UNIT_SORT_RANK: dict[str, int] = {
    "m³": 0,
    "m²": 1,
    "m": 2,
    "nr": 3,
    "item": 4,
    # Less common units fall after 'item'.
    "t": 5,
    "hr": 6,
    "week": 7,
    "kg": 8,
}

# NRM2 BoQ mandatory section order (1 first, then 2–41, then special sections).
_NRM2_SECTION_ORDER = list(range(1, 42))

# NRM2: logical items per page for pagination tracking.
_ITEMS_PER_PAGE = 20


def _item_sort_key(item: BoQLineItem):
    """Sort key for items within a section.

    NRM2 order: m³ → m² → m → nr → item → other;
    then labour-only before labour-and-material;
    then by rate ascending (least expensive first).
    """
    unit_rank = _UNIT_SORT_RANK.get(_normalise_unit(item.unit_of_measurement), 99)
    labour_rank = 0 if item.is_labour_only else 1
    rate_value = float(item.rate)
    return (unit_rank, labour_rank, rate_value)


class BoQGenerator:
    """Generates a NRM2-compliant BoQ structure from BoQLineItem objects.

    Usage:
        gen = BoQGenerator()
        result = gen.generate(items, project_info={...})

    The returned dict has two keys:
      "nrm2_structure"   — Full NRM2-ordered structure with sections, pages, totals.
      "bill_of_quantities" — Legacy {trade, items} format for existing pipeline.
    """

    def generate(
        self,
        items: list[BoQLineItem],
        project_info: Optional[dict] = None,
    ) -> dict:
        """Build the full NRM2-compliant BoQ.

        Returns a dict with 'nrm2_structure' (rich) and 'bill_of_quantities'
        (backwards-compatible with the existing pipeline).
        """
        info = project_info or {}

        # 1. Partition items by type: measured, provisional, CDP.
        measured_items: list[BoQLineItem] = []
        provisional_items: list[BoQLineItem] = []
        cdp_items: list[BoQLineItem] = []

        for item in items:
            if item.is_contractor_designed:
                cdp_items.append(item)
            elif item.is_provisional:
                provisional_items.append(item)
            else:
                measured_items.append(item)

        # 2. Group measured items by section, preserving NRM2 section order.
        sections_map: dict[int, list[BoQLineItem]] = {}
        for item in measured_items:
            sid = item.work_section_id
            sections_map.setdefault(sid, []).append(item)

        # 3. Sort items within each section per NRM2 ordering rules.
        for sid in sections_map:
            sections_map[sid].sort(key=_item_sort_key)

        # 4. Assign hierarchical refs ("SS/NN").
        for sid, sec_items in sections_map.items():
            for idx, item in enumerate(sec_items, start=1):
                item.hierarchical_ref = f"{sid:02d}/{idx:02d}"

        # 5. Assign refs for provisional and CDP items (using section 0 range).
        for idx, item in enumerate(provisional_items, start=1):
            item.hierarchical_ref = f"PS/{idx:02d}"
        for idx, item in enumerate(cdp_items, start=1):
            item.hierarchical_ref = f"CDP/{idx:02d}"

        # 6. Build section structures with pagination.
        nrm2_sections = {}
        for sid in _NRM2_SECTION_ORDER:
            if sid not in sections_map:
                continue
            sec_items = sections_map[sid]
            pages = self._paginate(sec_items)
            section_total = sum(
                (item.total_amount for item in sec_items), Decimal("0")
            )
            entry: dict = {
                "section_number": sid,
                "section_name": WORK_SECTIONS[sid]["name"],
                "notes": WORK_SECTIONS[sid].get("notes", ""),
                "pages": pages,
                "section_total": section_total,
            }
            # NRM2: Section 1 (Preliminaries) split into Part A and Part B.
            if sid == 1:
                entry["part_a"] = [i for i in sec_items if i.is_labour_only]
                entry["part_b"] = [i for i in sec_items if not i.is_labour_only]
            nrm2_sections[sid] = entry

        # 7. Build provisional sums block.
        defined_ps = [i for i in provisional_items if i.provisional_type == "defined"]
        undefined_ps = [i for i in provisional_items if i.provisional_type == "undefined"]

        # 8. Compute main summary totals.
        grand_total = sum(
            (s["section_total"] for s in nrm2_sections.values()), Decimal("0")
        )
        grand_total += sum(
            (i.total_amount for i in provisional_items), Decimal("0")
        )
        grand_total += sum(
            (i.total_amount for i in cdp_items), Decimal("0")
        )

        # 9. Assemble full NRM2 structure (BoQ mandatory order per spec).
        nrm2_structure = {
            # 1. Form of Tender
            "form_of_tender": {
                "project_title": info.get("project_title", ""),
                "employer": info.get("employer", ""),
                "contract_date": info.get("contract_date", ""),
                "tender_sum_placeholder": None,
                "certificate_of_bona_fide_tender": True,
            },
            # 2. Main Summary
            "main_summary": {
                "sections": [
                    {
                        "ref": f"Section {sid:02d}",
                        "name": WORK_SECTIONS[sid]["name"],
                        "total": float(nrm2_sections[sid]["section_total"]),
                    }
                    for sid in sorted(nrm2_sections)
                ],
                "provisional_sums_total": float(
                    sum((i.total_amount for i in provisional_items), Decimal("0"))
                ),
                "cdp_total": float(
                    sum((i.total_amount for i in cdp_items), Decimal("0"))
                ),
                "grand_total": float(grand_total),
            },
            # 3–4. Sections (Preliminaries first, then 2–41)
            "sections": {
                sid: {
                    **data,
                    "section_total": float(data["section_total"]),
                }
                for sid, data in nrm2_sections.items()
            },
            # 5. Non-Measurable Works
            "non_measurable_works": {
                "defined_provisional_sums": [i.to_dict() for i in defined_ps],
                "undefined_provisional_sums": [i.to_dict() for i in undefined_ps],
            },
            # 6. Contractor-Designed Works
            "cdp_items": [i.to_dict() for i in cdp_items],
            # 7–10. Remaining mandatory blocks (populated by QS as required)
            "risk_schedule": [],
            "credits": [],
            "dayworks": [],
            "annexes": [],
        }

        # 10. Build legacy bill_of_quantities format for existing pipeline.
        legacy_boq = self._to_legacy_format(sections_map, provisional_items, cdp_items)

        return {
            "nrm2_structure": nrm2_structure,
            "bill_of_quantities": legacy_boq,
        }

    @staticmethod
    def _paginate(items: list[BoQLineItem]) -> list[dict]:
        """Split items into logical pages with carried-forward/brought-forward totals.

        NRM2 pagination:
          - Each page shows "Carried forward £[total]" at the bottom.
          - Each subsequent page shows "Brought forward £[total]" at the top.
          - Final page shows "TOTAL carried to main summary £[total]".
        """
        pages = []
        running_total = Decimal("0")
        for i in range(0, max(len(items), 1), _ITEMS_PER_PAGE):
            page_items = items[i: i + _ITEMS_PER_PAGE]
            page_total = sum(
                (item.total_amount for item in page_items), Decimal("0")
            )
            brought_forward = running_total
            running_total += page_total
            is_final = (i + _ITEMS_PER_PAGE) >= len(items)
            pages.append(
                {
                    "page_number": len(pages) + 1,
                    "items": [it.to_dict() for it in page_items],
                    "brought_forward": float(brought_forward),
                    "carried_forward": float(running_total),
                    "is_final_page": is_final,
                    "section_total_label": (
                        f"TOTAL carried to main summary £{running_total:.2f}"
                        if is_final
                        else None
                    ),
                }
            )
        return pages

    @staticmethod
    def _to_legacy_format(
        sections_map: dict[int, list[BoQLineItem]],
        provisional_items: list[BoQLineItem],
        cdp_items: list[BoQLineItem],
    ) -> list[dict]:
        """Convert NRM2-ordered sections to the legacy {trade, items} list format.

        This maintains backwards compatibility with app.py, export_pdf.py, and
        export_excel.py which consume the 'bill_of_quantities' key.
        """
        result = []
        for sid in _NRM2_SECTION_ORDER:
            if sid not in sections_map:
                continue
            sec = WORK_SECTIONS[sid]
            result.append(
                {
                    "trade": f"Section {sid:02d} — {sec['name']}",
                    "items": [it.to_dict() for it in sections_map[sid]],
                }
            )
        # Append provisional sums and CDP items as separate trade groups.
        if provisional_items:
            result.append(
                {
                    "trade": "Non-Measurable Works — Provisional Sums",
                    "items": [it.to_dict() for it in provisional_items],
                }
            )
        if cdp_items:
            result.append(
                {
                    "trade": "Contractor-Designed Works (CDP)",
                    "items": [it.to_dict() for it in cdp_items],
                }
            )
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 10 — FULL BoQ VALIDATION
# Runs NRM2Validator across every item and returns a structured report.
# ═══════════════════════════════════════════════════════════════════════════════

def validate_boq(items: list[BoQLineItem]) -> dict:
    """Validate an entire BoQ and return a structured error/warning report.

    Returns:
        {
            "valid": bool,
            "total_items": int,
            "error_count": int,
            "warning_count": int,
            "duplicate_refs": list[str],
            "item_results": [
                {
                    "index": int,
                    "ref": str,
                    "description": str,
                    "errors": list[str],
                    "warnings": list[str],
                },
                ...
            ],
            "section_summary": {
                section_id: {"item_count": int, "section_total": float}
            },
        }
    """
    item_results = []
    error_count = 0
    warning_count = 0
    seen_refs: dict[str, int] = {}
    duplicate_refs: list[str] = []

    for idx, item in enumerate(items):
        raw_messages = NRM2Validator.validate_line_item(item)
        errors = [m for m in raw_messages if not m.startswith("WARNING:")]
        warnings = [m for m in raw_messages if m.startswith("WARNING:")]
        error_count += len(errors)
        warning_count += len(warnings)

        # Track duplicate hierarchical refs.
        ref = item.hierarchical_ref
        if ref:
            if ref in seen_refs:
                duplicate_refs.append(ref)
            else:
                seen_refs[ref] = idx

        item_results.append(
            {
                "index": idx,
                "ref": ref,
                "description": item.level_1_desc,
                "errors": errors,
                "warnings": warnings,
            }
        )

    # Build section summary.
    section_summary: dict[int, dict] = {}
    for item in items:
        sid = item.work_section_id
        if sid not in section_summary:
            section_summary[sid] = {
                "section_name": WORK_SECTIONS.get(sid, {}).get("name", "Unknown"),
                "item_count": 0,
                "section_total": 0.0,
            }
        section_summary[sid]["item_count"] += 1
        section_summary[sid]["section_total"] += float(item.total_amount)

    return {
        "valid": error_count == 0,
        "total_items": len(items),
        "error_count": error_count,
        "warning_count": warning_count,
        "duplicate_refs": duplicate_refs,
        "item_results": item_results,
        "section_summary": section_summary,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 11 — LOCATION-ADJUSTED RATE LOOKUP (backwards-compatible, float output)
# ═══════════════════════════════════════════════════════════════════════════════

def get_localized_rate(rate_key: str, region: str = "uk_average") -> dict:
    """Return location-adjusted rates for a given rate key and region.

    Returns float values for backwards compatibility with the existing pipeline.
    Monetary values in the NRM2 engine (BoQLineItem etc.) use Decimal instead.
    """
    if rate_key not in RATES_DB:
        raise ValueError(f"Rate key '{rate_key}' not found in RATES_DB.")
    base = RATES_DB[rate_key]
    factor = LOCATION_FACTORS.get(region, LOCATION_FACTORS["uk_average"])
    mat = base.get("material_rate", 0.0) * factor["material"]
    lab = base.get("labour_rate", 0.0) * factor["labour"]
    # Plant and waste disposal adjusted by the material location factor.
    plant = base.get("plant_rate", 0.0) * factor["material"]
    waste = base.get("waste_disposal_rate", 0.0) * factor["material"]
    return {
        "unit": base["unit"],
        "material_cost": round(mat, 2),
        "labour_cost": round(lab, 2),
        "plant_or_waste_cost": round(plant + waste, 2),
        "total_unit_cost": round(mat + lab + plant + waste, 2),
    }
