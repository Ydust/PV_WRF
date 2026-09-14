"""Calculate paired deployment scenarios for the IPCC rooftop-PV emission factors."""
from analysis_runtime import *
import json, inspect, time
from dataclasses import asdict
import numpy as np
import pandas as pd

import model as m

def main():
    start=time.time()
    m.ROOT=INPUT;m.DATA=D/'input_snapshot'
    inp=m.prepare_inputs();nreg=len(inp['regions'])
    p=pd.read_csv(D/'scenario_parameters.csv').sort_values('sample_id').reset_index(drop=True)
    assert len(p)==2049 and (p.pv_lca_g_per_kwh==41).all() and (p.pv_lca_2050_multiplier==1).all()
    rules=pd.read_csv(D/'figure5_rule_results.csv')
    screen=rules.query('rule=="FullSign"').sort_values('sample_id')
    membership=pd.read_csv(D/'figure5_rule_membership.csv')
    keep=membership.query('rule=="FullSign"').set_index('country_tag').loc[inp['regions'],'retained'].to_numpy(bool)
    assert keep.sum()==37
    src=inspect.getsource(m._evaluate.py_func).replace('@njit(cache=True, parallel=True)','@njit(cache=False, parallel=True)').replace('def _evaluate(','def _vector(')
    src=src.replace('group_paths(p,final_cover,intensive,settings)','group_paths(p,final_cover[s],intensive,settings)')
    scope=dict(vars(m));exec(compile(src,'<lmh-kernel>','exec'),scope);kernel=scope['_vector']
    def ev(c):
        return kernel(p[m.PNAMES].to_numpy(float),np.broadcast_to(np.asarray(c,float),(len(p),)).copy(),inp['cell'],inp['group'],inp['region_idx'],inp['intensive'],nreg,np.array(list(asdict(m.Controls()).values()),float),False)[0]
    uniform=ev(50);print('Uniform scenario completed:',time.time()-start,flush=True)
    selected=ev(screen.coverage_pct.to_numpy());selected[:,~keep]=0
    target=uniform[...,1].sum((1,2));base_net=uniform[...,14].sum((1,2))
    np.testing.assert_allclose(selected[...,1].sum((1,2)),target,rtol=1e-10)
    np.testing.assert_allclose(selected[...,14].sum((1,2)),screen.net_gt,rtol=1e-10,atol=1e-9)
    rows=[];country=[];validations=[]
    for factor,level in [(26,'Low'),(41,'Medium'),(60,'High')]:
        pp=p.copy();pp['pv_lca_g_per_kwh']=factor;pp.to_csv(D/f'scenario_parameters_{factor}.csv',index=False)
        for strategy,a in [('Uniform',uniform),('Screened',selected)]:
            net=a[...,14].sum(2)+(41-factor)*a[...,0].sum(2)*1e-6
            for si,sid in enumerate(p.sample_id):
                rows.append(dict(sample_id=int(sid),pv_factor=factor,pv_level=level,strategy=strategy,net_gt=net[si].sum(),gain_gt=net[si].sum()-base_net[si],delivered_twh=a[si,:,:,1].sum(),generation_twh=a[si,:,:,0].sum(),negative_regions=int((net[si]<-1e-12).sum())))
                country.extend(dict(sample_id=int(sid),pv_factor=factor,strategy=strategy,country_tag=tag,net_gt=float(net[si,ri])) for ri,tag in enumerate(inp['regions']))
            if factor!=41:
                for si in [0,512,2048]:
                    c=50 if strategy=='Uniform' else float(screen.coverage_pct.iloc[si])
                    test,_=m.evaluate(inp,pp.iloc[[si]],c)
                    if strategy=='Screened':test[:,~keep]=0
                    expected=a[[si],...,14]+(41-factor)*a[[si],...,0]*1e-6
                    np.testing.assert_allclose(test[...,14],expected,atol=1e-10,rtol=1e-10)
                    np.testing.assert_allclose(test[...,1],a[[si],...,1],atol=1e-10,rtol=1e-10)
                    validations.append(dict(factor=factor,strategy=strategy,sample_id=int(p.sample_id.iloc[si]),max_error=float(abs(test[...,14]-expected).max())))
        print('FACTOR',factor,'COMPLETE',time.time()-start,flush=True)
    totals=pd.DataFrame(rows);totals.to_csv(D/'figure5_lmh_totals.csv',index=False)
    pd.DataFrame(country).to_csv(D/'figure5_lmh_country.csv',index=False)
    # Calculate interventions at 75% deployment coverage.
    high=pd.read_csv(D/'country_endpoints.csv').query('final_coverage_pct==75').set_index('country_tag')
    tags=high.query('cumulative_net_gt<0').index
    old=-high.loc[tags].cumulative_net_gt.sum()
    net=high.cumulative_net_gt+15*high.cumulative_generation_twh*1e-6
    shortfall=-np.minimum(net.loc[tags],0).sum()
    levers=pd.read_csv(D/'figure4_interventions.csv');i=levers.index[levers.lever.str.startswith('PV ')][0]
    levers.loc[i,['lever','shortfall_gt','removed_pct','recovered','domain_net_gt']]=['PV 41 to 26 g/kWh',shortfall,(1-shortfall/old)*100,int((net.loc[tags]>=0).sum()),net.sum()]
    levers.to_csv(D/'figure4_interventions.csv',index=False)
    testp=p.iloc[[0]].copy();testp['pv_lca_g_per_kwh']=26
    direct,_=m.evaluate(inp,testp,75)
    np.testing.assert_allclose(direct[0,:,:,14].sum(1),net.loc[inp['regions']],atol=1e-10)
    qa=dict(factors=[26,41,60],source='IPCC AR5 WGIII Annex III Table A.III.2 (2014), rooftop-PV minimum/median/maximum',scenarios_per_combination=2048,baseline_rows_per_combination=1,combinations=6,retained_regions=int(keep.sum()),membership_reference=41,matched_service_relative_error=float(abs(selected[...,1].sum((1,2))/target-1).max()),direct_validation=validations,intervention=levers.loc[i].to_dict(),seconds=time.time()-start)
    (Q/'lmh_numerical_checks.json').write_text(json.dumps(qa,indent=2),encoding='utf8')
    print(json.dumps(qa,indent=2),flush=True)

if __name__=='__main__':main()
