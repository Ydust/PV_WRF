# Python environment setup

Python: **3.12.14**. Platform: **Windows, 64-bit**.

## Installation

Open PowerShell in the project root:

```powershell
& '.\environment\setup.ps1'
```

This creates `environment/.venv`, installs the packages in `requirements-lock.txt`, and runs `check_environment.py` to check versions and imports.

## Execution

```powershell
& '.\environment\.venv\Scripts\python.exe' '.\code\run.py' baseline
& '.\environment\.venv\Scripts\python.exe' '.\code\run.py' full
```

The default directories are `input` and `output` in the project root. Optional overrides:

```powershell
$env:PV_WRF_DATA_ROOT = 'E:/custom_input'
$env:PV_WRF_OUTPUT_ROOT = 'E:/custom_output'
$env:NUMBA_NUM_THREADS = '8'
```

The input directory must contain `grids`, `parameters`, and `maps`. Use a new output directory when changing inputs to avoid reusing old working files.

The first execution includes Numba compilation. Plots use Arial with DejaVu Sans as a fallback.

## Notebook

Open `code/main_figures.ipynb` in a Jupyter-compatible editor, such as VS Code with the Jupyter extension. Select `environment/.venv/Scripts/python.exe` as the kernel and run all cells in order.
