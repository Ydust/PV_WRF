"""Freeze input records for the historical-opening reference cohort decision."""
import os, json, hashlib
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[4]

JOB=Path(__file__).resolve().parents[1]
P=ROOT/'research/outputs/baseline_replacement_package_20261031'
D=P/'source_data'
def load(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
op=pd.read_csv(D/'country_opening_231.csv').fillna('')
components=pd.read_csv(D/'opening_component_cohorts.csv').fillna('')
events=pd.read_csv(D/'future_opening_events_REF.csv').fillna('')
history=pd.read_csv(D/'opening_historical_balances_231.csv').fillna('')
assert len(op)==231 and len(history[history['case']=='CENTRAL'])==231
assert set(components.code).issubset(set(op.code))
files=[D/n for n in ['country_opening_231.csv','opening_component_cohorts.csv','future_opening_events_REF.csv','opening_historical_balances_231.csv','candidate_parent_opening_interfaces.npz','references.json','unit_contract.csv','known_installation_zero_conflicts.csv','candidate_value_trace_register.csv']]
old=ROOT/'research/outputs/figure3_large_median_triangles_20261031/source_data/reference_cohorts.json'
files.append(old)
value={'opening':op.to_dict('records'),'components':components.to_dict('records'),'events':events.to_dict('records'),'history':history.to_dict('records'),'references':load(D/'references.json'),'source_hashes':{str(p):sha(p) for p in files}}
(JOB/'source_data/frozen_inputs.json').write_text(json.dumps(value,ensure_ascii=False,allow_nan=False),encoding='utf-8')
(JOB/'source_data/old_reference_cohorts_SNAPSHOT_NOT_ACTIVE.json').write_bytes(old.read_bytes())
print(json.dumps({'countries':len(op),'opening_components':len(components),'future_events':len(events),'history_cases':history['case'].nunique(),'source_files':len(files)}))
