"""Calculate baseline budgets, time series, interventions and scenario ensembles."""
from analysis_runtime import *
import json, argparse
from dataclasses import replace
import numpy as np
import pandas as pd
import model as m

def compare(filename,actual,keys,cols):
    ref=pd.read_csv(DATA_ROOT/'parameters'/filename)
    aa=actual.set_index(keys).sort_index();bb=ref.set_index(keys).sort_index()
    # Compare the coverage levels present in the current calculation.
    bb=bb.loc[aa.index]
    np.testing.assert_allclose(aa[cols].to_numpy(float),bb[cols].to_numpy(float),rtol=2e-9,atol=1e-8)
    return float(np.max(np.abs(aa[cols].to_numpy(float)-bb[cols].to_numpy(float))))

def main(ensemble=False):
    m.ROOT=INPUT;m.DATA=D/'input_snapshot'
    inp=m.prepare_inputs()
    p=pd.read_csv(D/'scenario_parameters_41.csv').sort_values('sample_id').reset_index(drop=True)
    base=p.iloc[[0]];assert base.sample_id.iloc[0]==0
    ledger=[];arrays={};checks={}
    for c in [0,25,50,75]:
        a,cells=m.evaluate(inp,base,c,collect_cells=(c==75));arrays[c]=a
        np.testing.assert_allclose(a[...,14],a[...,8]-a[...,9]-a[...,10]-a[...,11]+a[...,12]-a[...,13],atol=1e-10)
        ledger.append(m.annual_frame(inp,a[0],c))
        if c==75:
            grid=inp['meta'][['Id','lat_center','lon_center','country_tag','climate_zone','farea','people','battery_life']].copy()
            for j,k in enumerate(m.FIELDS):grid[('endpoint_' if j in (15,18) else 'cumulative_')+k]=cells[:,j]
            climate=pd.read_csv(DATA_ROOT/'parameters/figure1_cells.csv',usecols=['Id','era5_t2m_c'])
            grid=grid.merge(climate,on='Id',validate='one_to_one')
            grid['gross_gt']=grid.cumulative_displaced_grid_gt-grid.cumulative_pv_embodied_gt
            grid['feedback_gt']=grid.cumulative_cooling_gt+grid.cumulative_ac_gt-grid.cumulative_roof_credit_gt+grid.cumulative_battery_gt
            grid['offset_pct']=np.where(grid.gross_gt>0,100*grid.feedback_gt/grid.gross_gt,np.nan)
            checks['grid_error']=compare('figure1_cells.csv',grid,['Id'],['cumulative_net_gt','gross_gt','feedback_gt'])
            grid.to_csv(D/'figure1_cells.csv',index=False)
        print('Baseline coverage',c,'net Gt',a[...,14].sum(),flush=True)
    ledger=pd.concat(ledger,ignore_index=True);end=ledger.query('year==2050')
    checks['annual_error']=compare('annual_country_ledger.csv',ledger,['country_tag','year','final_coverage_pct'],[c for c in ledger if c.startswith(('annual_','cumulative_'))])
    ledger.to_csv(D/'annual_country_ledger.csv',index=False);end.to_csv(D/'country_endpoints.csv',index=False)
    reduced={**inp,'cell':inp['cell'].copy(),'intensive':inp['intensive'].copy()}
    reduced['cell'][:,3]=0;reduced['intensive'][:,:,3]=0
    red,_=m.evaluate(reduced,base,75,replace(m.Controls(),roof_kg_m2=0))
    rows=[]
    for label,a in [('Full',arrays[75]),('Reduced',red)]:
        for ri,tag in enumerate(inp['regions']):
            for ti,year in enumerate(m.YEARS):
                gen=a[0,ri,:ti+1,0].sum();net=a[0,ri,:ti+1,14].sum()
                rows.append(dict(model=label,country_tag=tag,year=int(year),generation_twh=gen,net_gt=net,net_g_kwh=net/gen*1e6))
    paths=pd.DataFrame(rows);checks['figure3_error']=compare('figure3_time_paths.csv',paths,['model','country_tag','year'],['net_gt','generation_twh'])
    paths.to_csv(D/'figure3_time_paths.csv',index=False)
    high=end.query('final_coverage_pct==75').set_index('country_tag');neg=high.query('cumulative_net_gt<0').index
    assert len(neg)==7
    idx=[inp['regions'].index(x) for x in neg];burden=-high.loc[neg].cumulative_net_gt.sum()
    levers=[('Coverage 75 to 25%',{},25),('PV 41 to 26 g/kWh',{'pv_lca_g_per_kwh':26},75),('Battery 80 to 40 kg/kWh',{'battery_lca_kg_per_kwh_capacity':40},75),('Battery life +50%',{'battery_life_multiplier':1.5},75),('Direct use +20 pp',{'direct_use_lift':.2},75),('Roof credit x2',{'roof_credit_multiplier':2},75),('Cooling x0.5',{'cooling_demand_multiplier':.5},75)]
    rows=[]
    for name,patch,c in levers:
        pp=base.copy()
        for k,v in patch.items():pp[k]=v
        a,_=m.evaluate(inp,pp,c);net=a[0,:,:,14].sum(1);shortfall=-np.minimum(net[idx],0).sum()
        rows.append(dict(lever=name,coverage_pct=c,shortfall_gt=shortfall,removed_pct=(1-shortfall/burden)*100,recovered=int((net[idx]>=0).sum()),delivered_twh=a[...,1].sum(),domain_net_gt=net.sum()))
    levers=pd.DataFrame(rows)
    checks['interventions_error']=compare('figure4_interventions.csv',levers,['lever'],['shortfall_gt','removed_pct','recovered','domain_net_gt'])
    levers.to_csv(D/'figure4_interventions.csv',index=False)
    # The constant-EF diagnostic uses its own physical input table.
    cells=pd.read_csv(D/'figure2_diagnostic_cells.csv');ef=cells.grid_ef_2050_g_per_kwh
    net=cells.cumulative_delivered_twh*ef/1e6-cells.cumulative_generation_twh*41/1e6-cells.cooling_kwh*ef/1e15-cells.cumulative_ac_gt+cells.cumulative_roof_credit_gt-cells.cumulative_battery_gt
    values=net/cells.cumulative_generation_twh*1e6
    np.testing.assert_allclose(values,cells.diagnostic_g_kwh,atol=1e-7,rtol=1e-10)
    checks['diagnostic_error']=float(abs(values-cells.diagnostic_g_kwh).max())
    cells['diagnostic_g_kwh']=values;cells.to_csv(D/'figure2_diagnostic_cells.csv',index=False)
    if ensemble:
        a,_=m.evaluate(inp,p,75);v=a.sum(2)
        rows=[dict(sample_id=int(sid),country_tag=tag,net_gt=v[si,ri,14],generation_twh=v[si,ri,0],net_g_kwh=v[si,ri,14]/v[si,ri,0]*1e6) for si,sid in enumerate(p.sample_id) for ri,tag in enumerate(inp['regions'])]
        joint=pd.DataFrame(rows);checks['ensemble_error']=compare('figure4_country_scenarios.csv',joint,['sample_id','country_tag'],['net_gt','generation_twh','net_g_kwh'])
        joint.to_csv(D/'figure4_country_scenarios.csv',index=False)
    checks.update(regions=len(inp['regions']),grid_cells=len(inp['cell']),net_gt=float(high.cumulative_net_gt.sum()),negative_regions=neg.tolist(),ensemble_rerun=ensemble)
    (Q/'recalculation.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    print(json.dumps(checks,indent=2),flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--ensemble',action='store_true');main(ap.parse_args().ensemble)
