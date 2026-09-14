"""Model parameters and supporting functions."""
import numpy as np
import pandas as pd

AC_UNITS_PER_PERSON_DEFAULT = 0.4

AC_UNITS_PER_PERSON_BY_CLIMATE_ZONE = {'hot_arid_low_density': 0.85, 'hot_arid_sparse': 0.9, 'hot_arid_dense_riverine': 0.45, 'tropical_wet_dense': 0.45, 'humid_subtropical_dense': 0.55, 'humid_continental_temperate': 0.4}

COUNTRY_AC_OWNERSHIP_TRAJECTORY = {'usa': (0.9, 0.95), 'japan': (0.9, 0.95), 'south_korea': (0.86, 0.94), 'australia': (0.82, 0.9), 'saudi_arabia': (0.93, 0.96), 'uae': (0.95, 0.97), 'qatar': (0.95, 0.97), 'kuwait': (0.92, 0.96), 'israel': (0.85, 0.92), 'taiwan': (0.92, 0.95), 'singapore': (0.95, 0.97), 'china': (0.6, 0.88), 'india': (0.1, 0.55), 'indonesia': (0.16, 0.5), 'thailand': (0.4, 0.7), 'vietnam': (0.3, 0.65), 'philippines': (0.2, 0.55), 'malaysia': (0.4, 0.7), 'pakistan': (0.12, 0.4), 'bangladesh': (0.08, 0.4), 'sri_lanka': (0.15, 0.45), 'egypt': (0.4, 0.7), 'iran': (0.55, 0.8), 'turkey': (0.3, 0.6), 'nigeria': (0.06, 0.28), 'kenya': (0.04, 0.18), 'ethiopia': (0.02, 0.12), 'south_africa': (0.2, 0.45), 'brazil': (0.18, 0.5), 'mexico': (0.3, 0.55), 'argentina': (0.25, 0.5), 'peru': (0.1, 0.3), 'uk': (0.04, 0.25), 'germany': (0.05, 0.3), 'france': (0.08, 0.32), 'spain': (0.35, 0.6), 'italy': (0.3, 0.55), 'greece': (0.5, 0.75), 'russia': (0.1, 0.3), 'norway': (0.05, 0.15), 'sweden': (0.05, 0.15), 'switzerland': (0.06, 0.18), 'iceland': (0.02, 0.08), 'costa_rica': (0.2, 0.45), 'uruguay': (0.25, 0.5), 'paraguay': (0.22, 0.48), 'row': (0.25, 0.5)}

def country_ac_units_per_person(country: str, year: int, climate_zone: str='') -> float:
    """Per-person AC ownership: linear interp 2020-2050 from country trajectory."""
    traj = COUNTRY_AC_OWNERSHIP_TRAJECTORY.get(country)
    if traj is None:
        sat = AC_UNITS_PER_PERSON_BY_CLIMATE_ZONE.get(climate_zone, AC_UNITS_PER_PERSON_DEFAULT)
        return sat
    ac_2020, ac_2050 = traj
    t = (year - 2020) / (2050 - 2020)
    t = max(min(t, 1.0), 0.0)
    return ac_2020 + (ac_2050 - ac_2020) * t

BASELINE_PV_LCA = 41.0

BASELINE_BATTERY_LCA = 80.0

BASELINE_STORAGE_ONSET = 25.0

BASELINE_STORAGE_FULL = 75.0

BASELINE_CURTAILMENT_ONSET = 40.0

BASELINE_CURTAILMENT_MAX = 0.15

PARAMETERS = {'pv_lca_g_per_kwh': (41.0, 41.0), 'pv_lca_2050_multiplier': (1.0, 1.0), 'battery_lca_kg_per_kwh_capacity': (40.0, 120.0), 'battery_lca_2050_multiplier': (0.45, 1.0), 'manufacturing_path_exponent': (0.6, 1.6), 'battery_life_multiplier': (0.75, 1.5), 'grid_ef_2050_multiplier': (0.7, 1.15), 'grid_ef_path_exponent': (0.6, 1.6), 'displaced_ef_multiplier': (0.5, 1.5), 'cooling_demand_multiplier': (0.5, 1.5), 'roof_credit_multiplier': (0.5, 2.0), 'storage_onset_pct': (15.0, 50.0), 'storage_full_need_pct': (60.0, 90.0), 'storage_sizing_multiplier': (0.45, 1.4), 'direct_use_lift': (0.0, 0.2), 'curtailment_onset_pct': (30.0, 55.0), 'curtailment_max_fraction': (0.05, 0.25), 'deployment_path_exponent': (0.6, 1.6)}

def latin_hypercube(n: int, names: list[str], seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    columns: dict[str, np.ndarray] = {}
    for name in names:
        low, high = PARAMETERS[name]
        quantiles = (np.arange(n, dtype=float) + rng.random(n)) / n
        rng.shuffle(quantiles)
        columns[name] = low + quantiles * (high - low)
    out = pd.DataFrame(columns)
    out.insert(0, 'sample_id', np.arange(1, n + 1, dtype=int))
    out['is_baseline'] = False
    return out

def baseline_sample() -> pd.DataFrame:
    return pd.DataFrame([{'sample_id': 0, 'pv_lca_g_per_kwh': BASELINE_PV_LCA, 'pv_lca_2050_multiplier': 1.0, 'battery_lca_kg_per_kwh_capacity': BASELINE_BATTERY_LCA, 'battery_lca_2050_multiplier': 1.0, 'manufacturing_path_exponent': 1.0, 'battery_life_multiplier': 1.0, 'grid_ef_2050_multiplier': 1.0, 'grid_ef_path_exponent': 1.0, 'displaced_ef_multiplier': 1.0, 'cooling_demand_multiplier': 1.0, 'roof_credit_multiplier': 1.0, 'storage_onset_pct': BASELINE_STORAGE_ONSET, 'storage_full_need_pct': BASELINE_STORAGE_FULL, 'storage_sizing_multiplier': 1.0, 'direct_use_lift': 0.0, 'curtailment_onset_pct': BASELINE_CURTAILMENT_ONSET, 'curtailment_max_fraction': BASELINE_CURTAILMENT_MAX, 'deployment_path_exponent': 1.0, 'is_baseline': True}])
