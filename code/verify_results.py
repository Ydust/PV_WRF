from analysis_runtime import *
import pandas as pd
import numpy as np
import json
from recalculate import compare
checks={}
for filename,keys,cols in [
 ('figure5_lmh_totals.csv',['sample_id','pv_factor','strategy'],['net_gt','gain_gt','delivered_twh','negative_regions']),
 ('figure5_lmh_country.csv',['sample_id','pv_factor','strategy','country_tag'],['net_gt']),
 ('model_signs_41.csv',['sample_id','country_tag'],['full_net_gt','reduced_net_gt']),
 ('structural_41.csv',['case'],['net_gt','negative_regions','shortfall_gt'])]:
    checks[filename]=compare(filename,pd.read_csv(D/filename),keys,cols)
(Q/'final_source_comparison.json').write_text(json.dumps(checks,indent=2),encoding='utf8')
print(json.dumps(checks,indent=2))
