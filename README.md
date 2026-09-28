# PV_WRF

Annual rooftop photovoltaic energy and carbon accounting for 2025–2050, with separate manufacturing-cohort burdens and deployment-region electricity displacement.

```
code/          Calculation scripts and plotting notebooks
input/         Processed grid data, model parameters and map boundaries
output/        Main-figure source data; calculated results are generated here
environment/   Python setup and package versions
```

## Run

Use Python 3.12 (64-bit). From the repository root on Windows:

```powershell
.\environment\setup.ps1
.\environment\.venv\Scripts\python.exe code/run.py all
```

On Linux or macOS:

```bash
python3.12 -m venv environment/.venv
environment/.venv/bin/python -m pip install -r environment/requirements-lock.txt
environment/.venv/bin/python code/run.py all
```

The complete pipeline calculates the baseline, 2,048 paired parameter draws, matched-electricity comparisons and supplementary analyses, then executes both plotting notebooks and verifies the results. No downloads are required during calculation. Runtime depends on the machine and includes numerical compilation on the first run.

| Stage | Operation |
| --- | --- |
| `baseline` | Physical ledgers at 50% and 75% final coverage and baseline cohort accounting |
| `uncertainty` | Parameter sensitivity at 75% coverage |
| `main-data` | Main-figure calculations and matched-electricity comparisons |
| `selection` | Alternative regional selection rules and grid diagnostic |
| `supplementary-data` | Structural sensitivities, coverage scans and national milestones |
| `figures` | Execute `code/main_figures.ipynb` |
| `supplementary-figures` | Execute `code/supplementary_figures.ipynb` |
| `verify` | Check accounting invariants and main-figure source data |

Stages run in this order with `all`. Individual plotting stages require the preceding calculation outputs. The notebooks can also be run interactively in a notebook-capable editor using the configured Python environment. Figure S1 is a system schematic and is not produced by the numerical plotting notebooks.

## Accounting

The baseline uses China as the manufacturing reference and couples its electricity trajectory to module production by installation year. An existing installation retains its original manufacturing burden. Manufacturing burdens include upstream life-cycle processes and are not a territorial emissions inventory for China. Source technology coefficients are interpolated through 2034 and then held; the manufacturing electricity trajectory continues through 2050. Freight, balance-of-system equipment and inverter production coefficients remain fixed unless varied explicitly.

PV production burdens are allocated over generation service; batteries are accounted for at production and replacement events. The raw physical kernel retains two inactive aggregate-PV fields for its parameter-array interface. Its aggregate PV burden is replaced by the cohort account before results are reported; neither field is an additional final-model emission term. Sixteen parameters vary across the supplied draws. Positive net balances indicate mitigation. Quantiles describe parameter sensitivity, not statistical confidence intervals.

At 75% final roof-reference coverage, the baseline produces 117.6119047 Gt CO₂e of cumulative net mitigation and six net-emitting countries with combined net emissions of 75.6457542 Mt CO₂e.

The model starts from the processed grid inputs under `input/grids`. It does not download or reconstruct the original building polygons or meteorological archives. Source provenance and parameter definitions are recorded in [input documentation](input/README.md). Main-figure plotting values are provided as 17 CSV tables and one matching Excel workbook under `output/Source_Data`.

See [environment setup](environment/SETUP.md) and [package versions](environment/PACKAGES.md).
