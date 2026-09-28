# Rooftop PV carbon accounting

Production-cohort accounting for rooftop PV deployment during 2025–2050, with separate manufacturing-region and deployment-region electricity pathways.

## Layout

- `code`: numerical model, inventory adapters and figure notebooks.
- `input`: processed spatial inputs, scenario vectors, electricity pathways and extracted inventory outputs.
- `output`: figure inputs and tabulated calculation results.
- `environment`: Python setup and exact package versions.

## Run

From the repository root, install the environment described in `environment/SETUP.md`.

```text
python code/run.py --mode baseline
python code/run.py --mode all
python code/run.py --mode figures
python code/run.py --mode supplementary-figures
```

The supplied outputs allow figure reproduction without recalculating the ensemble. All plotting is contained in the two notebooks. The full calculation uses 2,048 paired conditional draws plus the deterministic baseline. Run times depend on the processor and first-use Numba compilation.

## Inventory reproduction

The default calculation reads extracted GREET production outputs. To rerun the native inventory, obtain R&D GREET 2025 Rev.1 directly from Argonne (https://greet.anl.gov/) under its terms and place the energy and material workbooks in `input/GREET_2025_Rev1`. Microsoft Excel and trusted GREET VBA functions are required. Source workbooks are opened read-only. The workbooks are not redistributed in this archive.

```powershell
./code/run_greet_cases.ps1
./code/run_greet_cases.ps1 -InputName greet_low_cost_inputs.json -ResultName greet_low_cost_results
./code/run_greet_cases.ps1 -InputName greet_high_cost_inputs.json -ResultName greet_high_cost_results
python code/combine_inventory.py
```

The expected filenames are `R&D GREET1_2025_Rev1.xlsm` and `R&D GREET2_2025_Rev1.xlsm`. Rerun `python code/run.py --mode all` after generating all native inventory cases. Complete files in `output/inventory` take precedence over the supplied inventory extracts.

Reference results contain frozen supplies, regional transition and additional wind procurement. Low/high zero-carbon technology cost pathways are distinct from procurement. Native source supply regions are retained; the model does not treat every upstream input as Chinese electricity.

## Scope

Baseline final coverage is 75% of calibrated roof-reference area; deployment comparisons match cumulative electricity delivered by uniform 50% coverage. Export absorption is assumed. PV burdens are allocated to generation service; storage production is charged at installation or replacement, and auxiliary production only at capacity expansion. End-of-life treatment is excluded. Archived spatial inputs reproduce the reported analysis; they do not reconstruct missing product snapshots or projection metadata. Scenario percentiles are not confidence intervals.

The extracted inventory outputs replace aggregate carbon terms from the physical evaluator. Four inactive scalar dimensions in the input vectors are retained for numerical interface compatibility; only the fourteen active dimensions described in the manuscript affect the final results. The initial battery scalar divided by 80 rescales the GREET pack factor and does not rescale auxiliary infrastructure.

## Reference results

At 75% final roof-reference coverage, cumulative net mitigation is 120.02454030015716 Gt CO2e. Sweden, Norway, Paraguay, Switzerland and Iceland have cumulative net emissions totalling 46.0521924520253 Mt CO2e. The ensemble varies fourteen active parameters across 2,048 paired draws.

## Figure source data

`output/Source_Data/Main_Figure_Source_Data.xlsx` contains 18 worksheets for Figures 1–5. `output/Source_Data/Supplementary_Figure_Source_Data.xlsx` contains 12 worksheets for Figures S2–S9. Matching CSV files are stored alongside these workbooks. Figure S1 is a system schematic without numerical plotting data.
