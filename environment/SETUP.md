# Python environment

Validated on Windows with Python 3.12.14 (64-bit).

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r environment/requirements-lock.txt
.venv/Scripts/python code/run.py --mode baseline
```

Run commands from the project root. Use `--mode all` for all numerical results, `--mode figures` for the five main figures and `--mode supplementary-figures` for supplementary figures S2–S9. The notebook runner executes the notebook cells directly; a Jupyter installation is not required. A notebook editor can be installed separately if desired.

The Python workflow uses supplied extracted inventory factors. Native GREET recalculation additionally requires Windows, Microsoft Excel and the original R&D GREET 2025 Rev.1 energy/material workbooks obtained from Argonne. The validated Excel version was 16.0, build 20326. The GREET workbooks and Microsoft Excel are not included.
