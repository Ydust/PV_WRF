# PV_WRF

```
code/          Calculation scripts and main_figures.ipynb
input/         Grid data, parameters and map resources
output/        Generated results, working files and checks
environment/   Python setup, dependency versions and configuration
```

## Setup and execution

Open PowerShell in the project root:

```powershell
& '.\environment\setup.ps1'
& '.\environment\.venv\Scripts\python.exe' '.\code\run.py' baseline
```

Use `full` instead of `baseline` to execute the complete pipeline.

| Mode | Operation |
|---|---|
| `baseline` | Baseline budgets, time series, interventions and diagnostics |
| `full` | Calculations, scenario ensembles, rule solving, sensitivity analysis, plots and comparisons |
| `figures` | Plot the working data |
| `rules` | Solve regional selection rules and equal-delivery coverage |
| `supplementary` | Run sensitivity calculations |
| `verify` | Compare existing working results with reference values |

The default input and output directories are `input` and `output`. When changing inputs, select a new output directory to avoid reusing old working files.

See [environment setup](environment/SETUP.md) and [package versions](environment/PACKAGES.md).

## Notebook

Open `code/main_figures.ipynb`, select the Python environment configured for this project, and run all cells. All plotting functions are included in the notebook.
