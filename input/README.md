# Model inputs

| Input | Contents and use |
| --- | --- |
| `grids/global_grid_feedback_*_high.csv` | Processed spatial inputs at 2021, 2030, 2040 and 2050; roof-reference area, population, generation coefficients, electricity factors and thermal fields |
| `parameters/scenario_parameters.csv` | One baseline plus 2,048 paired parameter draws; sixteen varying parameters |
| `parameters/grid_temperature.csv` | Grid identifiers and ERA5 temperature values used for Figure 1 climate summaries |
| `parameters/diagnostic_cells.csv` | Physical quantities used for the constant-grid supplementary diagnostic |
| `parameters/diagnostic_bins.csv` | Electricity-factor bin limits, cell counts and weighted centres for that diagnostic |
| `parameters/manufacturing_literature_factors.csv` | Published LCA scenario values converted to module-area units; source DOI, sheet and cell retained |
| `parameters/manufacturing_response.csv` | Effective electricity-response coefficients and residual burdens reconstructed from the published scenarios |
| `parameters/manufacturing_grid_continuations.csv` | China electricity ratios and alternative manufacturing-electricity scenarios |
| `parameters/manufacturing_subgrid_scenarios.csv` | Source-derived lower, reference and higher manufacturing-grid contrasts |
| `parameters/balance_of_system_2024.json` | Baseline combined BOS and inverter coefficients, units and derivation |
| `parameters/balance_of_system.json` | Reference freight coefficient and alternative equipment coefficients |
| `maps` | Natural Earth boundaries used by the map panels |

Module scenario values and electricity response derive from [Willis et al.](https://doi.org/10.1038/s41467-026-69165-x). Source cell references are included in the parameter tables. Baseline BOS and inverter coefficients derive from the [IEA-PVPS 2024 life-cycle assessment slides](https://iea-pvps.org/wp-content/uploads/2024/05/Slides_IEA-PVPS-T12_Fact-Sheet-update-2023_v2.0.pdf), with the lifetime-output conversion recorded in the JSON file. Alternative manufacturing-electricity paths use [Tang et al.](https://doi.org/10.1016/j.isci.2025.111963), Table S14. The baseline uses the supplied China grid trajectory rather than those alternative paths.

The processed parameters are sufficient to execute the model without downloading literature files. To independently reconstruct the manufacturing parameters from the recorded publisher workbooks, run:

```bash
python code/prepare_manufacturing_inputs.py
```

This optional command downloads sources into `input/literature`, verifies the recorded SHA-256 hashes, and reruns extraction and response calibration. URLs and source hashes are in `manufacturing_sources.json`. The command requires network access and stops if a publisher file differs from the recorded version. Downloaded publications are not included in the repository.

The spatial inputs are the processed inputs to this model. Building-footprint preprocessing and meteorological archive acquisition are outside the executable scope of this repository. The scientific input definitions and their limitations are described in the manuscript's supplementary methods. Natural Earth boundaries retain their original geographic coordinate information.
