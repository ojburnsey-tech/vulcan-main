# api/rates.py
# UK Residential Construction Rates Database 2025-2026
# Sources: Spon's Architects' & Builders' Price Book 2025 (AECOM, Sep 2024) [training-data estimates],
#          Checkatrade cost guides 2024-2026, Rated People Jun 2025, MyBuilder Dec 2025.
# All rates are UK national averages, exclusive of VAT.
# material_rate      : cost of materials per unit, £
# labour_rate        : all-in labour cost per unit, £
# plant_rate         : mechanical plant/equipment cost per unit, £ (0.00 where not applicable)
# waste_disposal_rate: tip/disposal charge per unit, £ (0.00 where not applicable)
# unit               : m (linear), m² (area), m³ (volume), nr (number/item)

RATES_DB = {

    # ── TRADE 1: GROUNDWORKS ────────────────────────────────────────────────
    # Excavation items: zero material_rate; plant costs in plant_rate.
    # Items supplying material (hardcore, DPC) retain material_rate.

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

    # ── TRADE 11: ELECTRICAL ─────────────────────────────────────────────────
    # Labour-biased: ~65% labour across M&E items.

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


LOCATION_FACTORS = {
    "uk_average": {"material": 1.00, "labour": 1.00},
    "london_se":  {"material": 1.05, "labour": 1.30},
    "n_ireland":  {"material": 1.02, "labour": 0.85},
    "scotland":   {"material": 1.00, "labour": 0.95},
    "midlands":   {"material": 1.00, "labour": 0.92},
    "north_eng":  {"material": 1.00, "labour": 0.90},
}


def get_localized_rate(rate_key: str, region: str = "uk_average") -> dict:
    if rate_key not in RATES_DB:
        raise ValueError(f"Rate key '{rate_key}' not found.")
    base = RATES_DB[rate_key]
    factor = LOCATION_FACTORS.get(region, LOCATION_FACTORS["uk_average"])
    mat   = base.get("material_rate", 0.0)      * factor["material"]
    lab   = base.get("labour_rate", 0.0)         * factor["labour"]
    plant = base.get("plant_rate", 0.0)          * factor["material"]
    waste = base.get("waste_disposal_rate", 0.0) * factor["material"]
    return {
        "unit": base["unit"],
        "material_cost":       round(mat, 2),
        "labour_cost":         round(lab, 2),
        "plant_or_waste_cost": round(plant + waste, 2),
        "total_unit_cost":     round(mat + lab + plant + waste, 2),
    }
