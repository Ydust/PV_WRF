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

The processed inputs for [main figure reproduction](data/) and the [country reference accounts](data/reference/) are available in this repository. The verified replay uses those processed inputs. Use the manuscript's [pinned code and processed-data snapshot](https://github.com/Ydust/PV_WRF/tree/cc28138c789b21964317dbc61034f285aed0d707/persistence_20261109) to match the submitted figures and first-loss checks.

## Obtain inputs for a full 1 km rerun

A full rerun uses the study's original 1 km model inputs and the matching intermediate accounts. During peer review, request these files through the journal's editorial office from the corresponding authors. Outside peer review, send the request to [Qingbin Yuan](mailto:yuanqb0@126.com) or [Yufeng Wu](mailto:wuyufeng3r@126.com). Use **PV_WRF full-rerun inputs** as the subject. Include the pinned commit, the analysis step in the table above, and the pathway and configuration needed. Ask for the matching input or account files, their SHA-256 checksums, and the archive-to-directory mapping. Access to third-party originals follows the providers' terms.

| Study-generated files to request | Where the calculation expects them |
| --- | --- |
| Spatial inputs and 1 km yield, utilization and opening-stock arrays, including `parent_inputs.npz`, `native_yield.npz`, `native_rho.npz`, `native_opening.npz` and `native_util0_joint.npz` | `model/native/multiscale_full_resolution_20261024/source_data/` and the matching job files under `model/native/` |
| Climate response arrays and scenario inputs, including `MPI_SSP245.npz` and any other arrays needed for the requested sensitivity case | `model/native/ssp_physical_extensions_20261027/source_data/` and the matching native job directories |
| End-of-2024 balance and component cohorts in `frozen_inputs.json`, and the grid-to-stock interface in `candidate_parent_opening_interfaces.npz` | `model/research/outputs/opening_balance_reference_cohorts_20261102/source_data/` and `model/research/outputs/baseline_replacement_package_20261031/source_data/`, respectively |
| Matched country manufacturing factors and intervention accounts with their account manifests | `model/research/outputs/country_manufacturing_recalculation_20261028/source_data/` and the analysis job directories under `model/research/outputs/` |
| Financial inputs and annual ledgers for the cost comparison | The matching job directories under `model/research/outputs/`, including `figure6_matched_config_export_20261102` and the financial inputs it reads |

Use the archive mapping to mount the matching files beside the code. If an account manifest contains paths from the original machine, point those entries to the mounted copies and check their recorded hashes before running the analysis.

### Third-party source data

| Input | Provider and release used |
| --- | --- |
| Rooftop area and growth | [Global Rooftop Area Dataset (2020)](https://doi.org/10.11888/HumanNat.tpdc.302010), 1 km, and the published decadal SSP2 rooftop-area curve in [Chen et al.](https://doi.org/10.59717/j.xinn-geo.2026.100222). |
| Climate | [ESGF CMIP6 ScenarioMIP MPI-ESM1-2-LR SSP2-4.5](https://doi.org/10.22033/ESGF/CMIP6.6693). Select monthly `Amon` `rsds`, `tas` and `sfcWind` for member `r1i1p1f1` on the native `gn` grid. The author-provided arrays contain the study's processed response for the 1 km calculation. |
| Power-sector transitions | [NGFS Phase V data and resources](https://www.ngfs.net/ngfs-scenarios-portal/data-resources/). Download the REMIND–MAgPIE 3.3–4.8 transition series for Current Policies, NDCs, Below 2°C, Net Zero 2050 and Low Demand from the linked IIASA Scenario Explorer. |
| Historical PV capacity and grid intensities | [IRENASTAT Electricity Statistics, 2026 H2](https://pxweb.irena.org/pxweb/en/IRENASTAT/IRENASTAT__Power%20Capacity%20and%20Generation/Country_ELECSTAT_2026_H2_PX.px/) and [Ember Yearly Electricity Data](https://ember-energy.org/data/yearly-electricity-data/). The analysis used an Ember snapshot dated 31 October 2026. Supplementary Note 1 lists the rooftop-specific sources used in the opening balance. |
| Manufacturing inventory | Obtain [R&D GREET 2025 Rev. 1](https://greet.anl.gov/) directly from Argonne under its terms to reproduce the native inventory. For the carbon-accounting runs, request the study's extracted and matched manufacturing factors in the table above. |
| Cost inputs | [Q1-2025 Solar Photovoltaic System Cost Benchmarks](https://data.nlr.gov/submissions/304) and the archived [2025 Annual Technology Baseline](https://data.openei.org/submissions/8759). Supplementary Note 3 identifies the country tariff and finance sources. Request the matched financial inputs and ledgers for the exact cost run. |

[Repository](https://github.com/Ydust/PV_WRF)

