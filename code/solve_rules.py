"""Select regions and solve deployment coverage for equal electricity delivery."""
from analysis_runtime import *
from dataclasses import asdict,replace
import inspect,json,argparse
import numpy as np
import pandas as pd
import model as m
from recalculate import compare

def main(smoke=False):
    m.ROOT=INPUT;m.DATA=D/'input_snapshot';inp=m.prepare_inputs();nreg=len(inp['regions'])
    p=pd.read_csv(D/'scenario_parameters_41.csv').sort_values('sample_id').reset_index(drop=True)
    if smoke:p=p[p.sample_id.isin([0,1,512,1024,2048])].reset_index(drop=True)
    src=inspect.getsource(m._evaluate.py_func).replace('@njit(cache=True, parallel=True)','@njit(cache=False, parallel=True)').replace('def _evaluate(','def _vector(')
    src=src.replace('group_paths(p,final_cover,intensive,settings)','group_paths(p,final_cover[s],intensive,settings)')
    scope=dict(vars(m));exec(compile(src,'<coverage-solver>','exec'),scope);kernel=scope['_vector']
    def ev(pp,c,x=inp,ctl=m.Controls()):
        return kernel(pp[m.PNAMES].to_numpy(float),np.broadcast_to(np.asarray(c,float),(len(pp),)).copy(),x['cell'],x['group'],x['region_idx'],x['intensive'],nreg,np.array(list(asdict(ctl).values()),float),False)[0]
    base=p.iloc[[0]];full=ev(base,50)[0]
    reduced={**inp,'cell':inp['cell'].copy(),'intensive':inp['intensive'].copy()};reduced['cell'][:,3]=0;reduced['intensive'][:,:,3]=0
    red=ev(base,50,reduced,replace(m.Controls(),roof_kg_m2=0))[0]
    meta=inp['meta'].copy();meta['roof_reference_m2']=inp['cell'][:,1]
    country=meta.groupby('country_tag').agg(gen=('annual_gen_kwh_realised','sum'),roof=('roof_reference_m2','sum')).loc[inp['regions']]
    ef=np.array([inp['intensive'][next(j for j,pair in enumerate(inp['pairs']) if pair[0]==r),0,0] for r in inp['regions']])
    fnet=full[:,:,14].sum(1);rnet=red[:,:,14].sum(1);delivery=red[:,:,1].sum(1)
    scores=pd.DataFrame(dict(country_tag=inp['regions'],reduced_margin=rnet/delivery,grid2025=ef,dynamic=red[:,:,8].sum(1)/delivery,yield_per_roof=country.gen.to_numpy()/country.roof.to_numpy(),total_pv=country.gen.to_numpy()))
    count=int((fnet>=0).sum())
    def top(key,k):return scores.country_tag.isin(scores.sort_values([key,'country_tag'],ascending=[False,True]).country_tag.iloc[:k]).to_numpy()
    masks={'FullSign':fnet>=0,'ReducedSign':rnet>=0}
    for prefix,key in [('Reduced','reduced_margin'),('Grid2025','grid2025'),('GridDynamic','dynamic'),('Yield','yield_per_roof'),('TotalPV','total_pv')]:
        masks[prefix+'TopK']=top(key,count);masks[prefix+'Top34']=top(key,34)
    refmem=pd.read_csv(DATA_ROOT/'parameters/figure5_rule_membership.csv')
    records=[]
    for label,mask in masks.items():
        rr=refmem.query('rule==@label').set_index('country_tag').loc[inp['regions'],'retained'].to_numpy(bool)
        np.testing.assert_array_equal(mask,rr)
        records.extend(dict(factor=41,rule=label,country_tag=tag,retained=bool(mask[i])) for i,tag in enumerate(inp['regions']))
    if not smoke:pd.DataFrame(records).to_csv(D/'figure5_rule_membership.csv',index=False)
    un=ev(p,50);target=un[...,1].sum((1,2));unet=un[...,14].sum((1,2));upper=ev(p,75);n=len(p)
    cache={};rows=[]
    for label,mask in masks.items():
        key=tuple(mask)
        if key not in cache:
            lo=np.zeros(n);hi=np.full(n,75.);flo=-target.copy();fhi=upper[...,1][:,mask,:].sum((1,2))-target
            feasible=fhi>=-1e-8;pending=np.flatnonzero(feasible);cover=np.full(n,np.nan)
            for it in range(60):
                if not len(pending):break
                c=lo[pending]-flo[pending]*(hi[pending]-lo[pending])/(fhi[pending]-flo[pending])
                if it>8 and it%4==0:c=(lo[pending]+hi[pending])/2
                a=ev(p.iloc[pending],c);f=a[...,1][:,mask,:].sum((1,2))-target[pending]
                done=abs(f)/target[pending]<1e-10;cover[pending[done]]=c[done]
                lower=f<0;lo[pending[lower]]=c[lower];flo[pending[lower]]=f[lower];hi[pending[~lower]]=c[~lower];fhi[pending[~lower]]=f[~lower]
                pending=pending[~done]
            assert not len(pending),'Equal-service coverage failed to converge'
            a=ev(p.loc[feasible],cover[feasible]);a[:,~mask]=0
            net=a[...,14].sum((1,2));served=a[...,1].sum((1,2));neg=(a[...,14].sum(2)<-1e-12).sum(1)
            np.testing.assert_allclose(served,target[feasible],rtol=1e-10,atol=1e-7)
            cache[key]=(feasible,cover,net,served,neg)
        feasible,cover,net,served,neg=cache[key];j=0
        for i,sid in enumerate(p.sample_id):
            row=dict(factor=41,rule=label,sample_id=int(sid),retained_count=int(mask.sum()),feasible=bool(feasible[i]),target_twh=float(target[i]),uniform_net_gt=float(unet[i]))
            if feasible[i]:row.update(coverage_pct=float(cover[i]),net_gt=float(net[j]),gain_vs_uniform_gt=float(net[j]-unet[i]),delivered_twh=float(served[j]),negative_regions=int(neg[j]));j+=1
            rows.append(row)
        print('Coverage rule solved:',label,flush=True)
    result=pd.DataFrame(rows)
    error=compare('figure5_rule_results.csv',result,['rule','sample_id'],['coverage_pct','net_gt','gain_vs_uniform_gt','delivered_twh','negative_regions'])
    result.to_csv((Q if smoke else D)/('rule_solver_smoke_results.csv' if smoke else 'figure5_rule_results.csv'),index=False)
    (Q/('rule_solver_smoke.json' if smoke else 'rule_solver.json')).write_text(json.dumps(dict(rules=len(masks),draws_including_baseline=n,unique_memberships=len(cache),max_absolute_error=error,coverage_solved_from_scratch=True,validation_sample_ids=p.sample_id.tolist(),full_ensemble=not smoke),indent=2),encoding='utf8')
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--smoke',action='store_true');main(ap.parse_args().smoke)
