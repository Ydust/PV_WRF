"""Evaluate paired parameter draws with cohort-specific PV manufacturing."""
from pathlib import Path
import time
import numpy as np
import pandas as pd
import model as m
from cohort_accounting import account,updated_cases

ROOT=Path(__file__).resolve().parents[1]

def main():
    x=m.prepare_inputs();ci=x['regions'].index('china');case=updated_cases()[3]
    p=pd.read_csv(ROOT/'input/parameters/scenario_parameters.csv').sort_values('sample_id')
    rows=[];start=time.time()
    for offset in range(0,len(p),64):
        batch=p.iloc[offset:offset+64];raw=m.evaluate(x,batch,75)[0]
        for j,sample in enumerate(batch.itertuples()):
            grid=raw[j,ci,:,8]/raw[j,ci,:,1]
            result=account(raw[j],case,exponent=sample.deployment_path_exponent,production_grid_ratio=grid/grid[9])['service']
            rows.extend(dict(sample_id=int(sample.sample_id),case=case.name,accounting='service',country_tag=tag,net_gt=float(v)) for tag,v in zip(x['regions'],result[:,:,14].sum(1)))
        print(f'Parameter draws: {min(offset+64,len(p))}/{len(p)} ({time.time()-start:.1f} s)',flush=True)
    pd.DataFrame(rows).to_csv(ROOT/'output/uncertainty_countries.csv',index=False)

if __name__=='__main__':main()
