# Framework for Assessing the Persistence of Carbon Mitigation Benefits from Rooftop Photovoltaics

This release accompanies the 2025–2100 study of 231 countries and territories. The reference combines SSP2 rooftop deployment, SSP2-4.5 climate and five NGFS power-sector pathways. Country accounts carry the end-of-2024 balance into 2025. The first-loss year is the first positive year-end after a negative balance. Exact zeros do not change the last nonzero sign. Cases without an observed loss retain a missing event year.

The repository root retains the earlier 2025–2050 study. Its numerical entry points and figure notebooks belong to that historical version.

## Reproduce the main figures and check first loss

From the repository root, use Python 3.11, the versions in `persistence_20261109/requirements.txt`, and Node.js 24. The submission graphics were checked on Windows using Arial. Use an installed copy of Arial for the closest typography.

```text
python -m pip install -r persistence_20261109/requirements.txt
python persistence_20261109/run_figures.py
node persistence_20261109/check_reference.cjs
```

The figure script saves the English PNG, PDF, SVG and TIFF files to `persistence_20261109/build/figures`. Figure 1 is a schematic. Figures 2–6 use the processed inputs in `data/figure2` through `data/figure6`. The renderers reuse the repository's Natural Earth 1:50m boundaries and panel-alignment utility. The hashes in `manifest.json` record the exact local inputs, staged counterparts and six original PNGs embedded in the manuscript.

The reference check recalculates the outcome state and first-loss year for every country–pathway pair from its opening balance and 76 annual cumulative balances. It compares the sum across countries with each published global reference trajectory. The check starts from the provided processed accounts.

## Numerical source and full-input requirements

The JavaScript and Python under `model/` preserve the calculation code for the current paper. The file names identify the relevant steps:

| Analysis | Entry point under `model/research/outputs` |
| --- | --- |
| Opening balance and fixed country groups | `opening_balance_reference_cohorts_20261102/code/recompute_reference.cjs`, `audit_and_freeze.py` and `classify.cjs` |
| Main intervention accounts | `figures3_5_unified_time_metric_20261102/code/recompute.cjs` and `prepare_analysis.py` |
| Cost and export-condition comparison | `figure6_matched_config_export_20261102/code/replay.cjs` and `calculate.py` |
| Pathway-specific rooftop and climate sensitivity | `pathway_optimal_matched_ssp_20261105/code/run_model.cjs` and `prepare.py` |
| Annual-grid and joint uncertainty | `monte_carlo_persistence_pilot_20261105/code/simulate.py` and `monte_carlo_joint_uncertainty_20261105/code/simulate_joint.py` |

For a full rerun, the native inputs are needed alongside the corresponding `model/native` job directories, and the processed research inputs alongside the `model/research` job directories. The native inputs include the 1 km rooftop yield and utilization arrays, processed climate ratios, electricity pathways and installation stocks. The research inputs include the 2024 opening balances and component cohorts, frozen configuration registries, manufacturing factors, account manifests and financial inputs. Account manifests must refer to the mounted copies of the matching files. Rebuilding the native input arrays also requires the original source datasets and, for the native inventory, GREET from Argonne under its terms.

The repository includes the smaller processed inputs for figure rendering and the reference check. A full native rerun requires separate access to the native arrays, financial input archives, external model workbooks and full intermediate account collection. The verified replay starts from processed inputs.

[Repository](https://github.com/Ydust/PV_WRF)

