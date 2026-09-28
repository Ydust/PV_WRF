"""Validate and combine native low/high manufacturing inventory outputs."""
from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
rows = []
for case in ('low_cost', 'high_cost'):
    path = root / 'output' / 'inventory' / f'greet_{case}_results.json'
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    expected = {(case, year) for year in range(2025, 2051)}
    actual = {(r['case'], r['production_year']) for r in data}
    if len(data) != 26 or actual != expected:
        raise ValueError(f'Incomplete or duplicated native inventory: {path.name}')
    rows.extend(data)
target = root / 'output' / 'inventory' / 'greet_side_results.json'
target.write_text(json.dumps(rows, indent=2), encoding='utf-8')
print(target)
