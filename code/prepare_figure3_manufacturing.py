"""Compare manufacturing electricity pathways at identical physical deployment."""
from pathlib import Path
import numpy as np
import pandas as pd
import model as m
from cohort_accounting import account, updated_cases

ROOT=Path(__file__).resolve().parents[1]

def main():
    out=ROOT/'output/Main_Figure_Data'
    x=m.prepare_inputs();raw=np.load(ROOT/'output/reference_75.npy')
    cases=updated_cases();baseline=cases[3];frozen=cases[5]
    assert not baseline.hold_manufacturing_grid_2025
    assert frozen.hold_manufacturing_grid_2025 and not frozen.hold_technology_2025
    frames=[]
    for label,case in [('Evolving manufacturing grid',baseline),('Frozen 2025 manufacturing grid',frozen)]:
        a=account(raw,case)['service'];f=m.annual_frame(x,a,75);f['series']=label;frames.append(f)
    df=pd.concat(frames,ignore_index=True)
    base=df[df.series=='Evolving manufacturing grid'].set_index(['country_tag','year'])
    frozen_df=df[df.series=='Frozen 2025 manufacturing grid'].set_index(['country_tag','year'])
    for c in base.columns:
        if c.startswith(('annual_','cumulative_')) and c not in ['annual_net_gt','cumulative_net_gt','annual_pv_embodied_gt','cumulative_pv_embodied_gt','cumulative_gross_saving_gt']:
            np.testing.assert_allclose(base[c],frozen_df[c],rtol=1e-12,atol=1e-10,err_msg=c)
    existing=pd.read_csv(out/'annual_reference.csv').query('final_coverage_pct==75').set_index(['country_tag','year'])
    np.testing.assert_allclose(base.cumulative_net_gt,existing.loc[base.index,'cumulative_net_gt'],atol=1e-12)
    df[['country_tag','year','series','cumulative_net_gt','annual_net_gt','cumulative_pv_embodied_gt']].to_csv(out/'manufacturing_time_paths.csv',index=False)
    print(df[df.country_tag.isin(['sweden','france','germany'])&df.year.isin([2030,2050])][['country_tag','year','series','cumulative_net_gt']].to_string(index=False))
    print('Matched physical ledgers verified.')

if __name__=='__main__':main()
