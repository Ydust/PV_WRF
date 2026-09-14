from pathlib import Path
import importlib,importlib.metadata as md,json,sys
r=Path(__file__).resolve().parent
expected=json.loads((r/'observed_environment.json').read_text())
errors=[]
for name,version in expected['packages'].items():
    try:
        actual=md.version(name)
        print(f'{name}: {actual} (expected {version})')
        if actual!=version:errors.append(name)
    except md.PackageNotFoundError:errors.append(name)
for name in ['numpy','pandas','scipy','numba','llvmlite','matplotlib','PIL','cartopy','shapely','pyproj','shapefile','ipykernel','nbformat','nbclient']:
    try:importlib.import_module(name)
    except Exception as e:errors.append(name+': '+str(e))
if sys.version_info[:2]!=(3,12):errors.append('Python must be 3.12 for this locked profile')
print('PASS' if not errors else 'FAILED: '+repr(errors))
raise SystemExit(bool(errors))
