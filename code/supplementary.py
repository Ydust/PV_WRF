from analysis_runtime import *
from dataclasses import replace
import model as m
import numpy as np
import pandas as pd
import json
m.ROOT=INPUT;m.DATA=D/'input_snapshot';m.DATA.mkdir(exist_ok=True)
inp=m.prepare_inputs();p=pd.read_csv(D/'scenario_parameters_41.csv').iloc[[0]].copy()
O=D
rows=[]; cr=[]
for name in ['Baseline','Installation-year PV allowance','Linear thermal exposure','Lossless storage','Zero thermal response','No storage','Fixed battery life 10 years','Constant sizing 0.003','No roof credit','Reduced PV-grid']:
 x={**inp,'cell':inp['cell'].copy(),'intensive':inp['intensive'].copy()}; ctl=m.Controls(); q=p.copy()
 if name=='Installation-year PV allowance':ctl=replace(ctl,pv_event_accounting=True)
 if name=='Linear thermal exposure':ctl=replace(ctl,cooling_linear_coverage=True)
 if name=='Lossless storage':ctl=replace(ctl,battery_rte=1)
 if name in ['Zero thermal response','Reduced PV-grid']:x['intensive'][:,:,3]=0
 if name in ['No storage','Reduced PV-grid']:x['cell'][:,3]=0
 if name=='Fixed battery life 10 years':x['cell'][:,4]=10
 if name=='Constant sizing 0.003':x['cell'][:,3]=.003
 if name in ['No roof credit','Reduced PV-grid']:ctl=replace(ctl,roof_kg_m2=0)
 a,_=m.evaluate(x,q,75,ctl);t=a[0].sum(1)
 np.testing.assert_allclose(a[...,14],a[...,8]-a[...,9]-a[...,10]-a[...,11]+a[...,12]-a[...,13],atol=1e-10)
 rows.append(dict(case=name,net_gt=t[:,14].sum(),negative_regions=int((t[:,14]<0).sum()),shortfall_gt=-np.minimum(t[:,14],0).sum(),delivered_twh=t[:,1].sum(),pv_burden_gt=t[:,9].sum()))
 cr.extend(dict(case=name,country_tag=tag,**dict(zip(m.FIELDS,t[j]))) for j,tag in enumerate(inp['regions']))
 print(name,rows[-1]['net_gt'],flush=True)
pd.DataFrame(rows).to_csv(O/'structural_41.csv',index=False);pd.DataFrame(cr).to_csv(O/'structural_country_41.csv',index=False)
end=pd.read_csv(D/'country_endpoints.csv').query('final_coverage_pct==75')
np.testing.assert_allclose(end.set_index('country_tag').loc[inp['regions'],'cumulative_net_gt'],pd.DataFrame(cr).query('case=="Baseline"').net_gt,atol=1e-9)
times=pd.read_csv(D/'figure3_time_paths.csv');trs=[]
for (model,tag),g in times.groupby(['model','country_tag']):
 g=g.sort_values('year');v=g.net_gt.to_numpy();y=g.year.to_numpy();j=np.where((v[:-1]>=0)&(v[1:]<0))[0]
 trs.append(dict(model=model,country_tag=tag,initial_negative=bool(v[0]<0),net_2050_gt=v[-1],first_downcrossing_year=float(y[j[0]]+v[j[0]]/(v[j[0]]-v[j[0]+1])) if len(j) else None))
pd.DataFrame(trs).to_csv(O/'temporal_41.csv',index=False)
z=pd.read_csv(D/'figure5_lmh_totals.csv');z=z[z.sample_id>0];risk=[]
for (factor,strategy),g in z.groupby(['pv_factor','strategy']):
 risk.append(dict(pv_factor=int(factor),strategy=strategy,n=len(g),any_negative=int((g.negative_regions>0).sum()),median_negative=float(g.negative_regions.median()),max_negative=int(g.negative_regions.max())))
pd.DataFrame(risk).to_csv(O/'risk_41_lmh.csv',index=False)
params=pd.read_csv(D/'scenario_parameters_41.csv');res=[]
for k in m.PNAMES:
 lo,hi=m.PARAMETERS[k]
 if k=='pv_lca_g_per_kwh':lo=hi=41
 if k=='pv_lca_2050_multiplier':lo=hi=1
 res.append(dict(parameter=k,baseline=float(params.loc[0,k]),lower=lo,upper=hi,status='fixed' if lo==hi else 'sampled'))
pd.DataFrame(res).to_csv(O/'parameters_41.csv',index=False)
summary={'structural':rows,'risks':risk,'source_factors':[26,41,60],'conditional_draws':2048,'sampled_dimensions':16,'baseline_regions':len(inp['regions'])}
(O/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
tests=[]
for label,changes in [('Displaced EF 0.5',{'displaced_ef_multiplier':.5}),('Displaced EF 0.75',{'displaced_ef_multiplier':.75}),('Displaced EF 1',{'displaced_ef_multiplier':1}),('Displaced EF 1.25',{'displaced_ef_multiplier':1.25}),('Displaced EF 1.5',{'displaced_ef_multiplier':1.5}),('Earlier storage',{'storage_onset_pct':15,'storage_full_need_pct':60,'storage_sizing_multiplier':1.4}),('Later storage',{'storage_onset_pct':50,'storage_full_need_pct':90,'storage_sizing_multiplier':.45}),('Higher direct use',{'direct_use_lift':.2})]:
 q=p.copy()
 for k,v in changes.items():q[k]=v
 a,_=m.evaluate(inp,q,75);v=a[0,:,:,14].sum(1)
 tests.append(dict(test=label,net_gt=v.sum(),negative_regions=int((v<0).sum()),shortfall_gt=-np.minimum(v,0).sum()))
pd.DataFrame(tests).to_csv(O/'grid_storage_41.csv',index=False)
# Evaluate the reduced model for the same parameter vectors and regions.
pp=pd.read_csv(D/'scenario_parameters_41.csv').query('sample_id>0')
x={**inp,'cell':inp['cell'].copy(),'intensive':inp['intensive'].copy()}
x['cell'][:,3]=0;x['intensive'][:,:,3]=0
print('Reduced conditional ensemble started',flush=True)
ar,_=m.evaluate(x,pp,75,replace(m.Controls(),roof_kg_m2=0))
red=ar[:,:,:,14].sum(2)
full=pd.read_csv(D/'figure4_country_scenarios.csv').query('sample_id>0').pivot(index='sample_id',columns='country_tag',values='net_gt').loc[pp.sample_id,inp['regions']].to_numpy()
dis=(full<0)!=(red<0)
stat=dict(pairs=int(dis.sum()),total_pairs=int(dis.size),pair_percent=float(dis.mean()*100),affected_scenarios=int(dis.any(1).sum()),scenarios=len(pp),full_negative_only=int(((full<0)&(red>=0)).sum()),reduced_negative_only=int(((full>=0)&(red<0)).sum()))
(O/'sign_disagreement_41.json').write_text(json.dumps(stat,indent=2),encoding='utf8')
pd.DataFrame([dict(sample_id=int(s),country_tag=c,full_net_gt=full[i,j],reduced_net_gt=red[i,j]) for i,s in enumerate(pp.sample_id) for j,c in enumerate(inp['regions'])]).to_csv(O/'model_signs_41.csv',index=False)
print(stat,flush=True)
