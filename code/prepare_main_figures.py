"""Prepare current main-figure data from manufacturing and deployment ledgers."""
from pathlib import Path
from dataclasses import asdict, replace
import json, inspect, time
import numpy as np
import pandas as pd
from numba import njit, prange
import model as m
from cohort_accounting import account, updated_cases, manufacturing_path

R=Path(__file__).resolve().parents[1]; O=R/'output'; D=O/'Main_Figure_Data'
D.mkdir(exist_ok=True)
CASES={'Low':updated_cases()[-2], 'Reference':updated_cases()[3], 'High':updated_cases()[-1]}
REF=CASES['Reference']

# The same physical kernel with one coverage per sample, for matched-energy solves.
# Source equivalence and fixed-coverage numerical equivalence are checked below.
src=inspect.getsource(m._evaluate.py_func).replace('cache=True','cache=False').replace('def _evaluate(', 'def _evaluate_coverages(').replace('paths=group_paths(p,final_cover,intensive,settings)','paths=group_paths(p,final_cover[s],intensive,settings)')
scope=dict(m.__dict__);exec(src,scope)
kernel=scope['_evaluate_coverages']
def evaluate_coverages(x,p,covers):
    return kernel(np.asarray(p[m.PNAMES],float),np.asarray(covers,float),x['cell'],x['group'],x['region_idx'],x['intensive'],len(x['regions']),np.array(list(asdict(m.Controls()).values()),float),False)[0]

def solve(x,p,target,mask,lo=50.,hi=75.):
    lower=np.full(len(p),lo); upper=np.full(len(p),hi)
    upper_a=evaluate_coverages(x,p,upper)
    assert np.all(upper_a[:,:,:,1][:,mask,:].sum((1,2))>=target), 'Infeasible target'
    for _ in range(36):
        c=(lower+upper)/2; a=evaluate_coverages(x,p,c)
        delivered=a[:,:,:,1][:,mask,:].sum((1,2)); error=delivered/target-1
        lower=np.where(error<0,c,lower);upper=np.where(error>=0,c,upper)
        if np.max(abs(error))<1e-10:break
    assert np.max(abs(error))<1e-10
    a[:,~mask]=0
    return c,a,error

def intensity_sensitivity():
    x=m.prepare_inputs();p=pd.read_csv(R/'input/parameters/scenario_parameters.csv').query('sample_id>0').sort_values('sample_id')
    u=pd.read_csv(D/'country_sensitivity.csv');wanted=u.country_tag.unique();parts=[]
    for start in range(0,len(p),128):
        batch=p.iloc[start:start+128];a=m.evaluate(x,batch,75)[0]
        for tag in wanted:
            ri=x['regions'].index(tag)
            parts.append(pd.DataFrame({'sample_id':batch.sample_id.to_numpy(),'country_tag':tag,'generation_twh':a[:,ri,:,0].sum(1)}))
    u=u.merge(pd.concat(parts),on=['sample_id','country_tag'],validate='one_to_one')
    u['net_g_co2e_kwh']=u.net_gt/u.generation_twh*1e6
    u.to_csv(D/'country_sensitivity_intensity.csv',index=False)

def main():
    start=time.time(); x=m.prepare_inputs(); regions=np.array(x['regions']);ci=x['regions'].index('china')
    p=pd.read_csv(R/'input/parameters/scenario_parameters.csv').sort_values('sample_id')
    a50=np.load(O/'reference_50.npy');a75,cells=m.evaluate(x,collect_cells=True);a75=a75[0]
    ref75=account(a75,REF)['service'];ref50=account(a50,REF)['service']
    np.testing.assert_allclose(ref75[:,:,14].sum(),117.61190473366243,atol=1e-10)
    np.testing.assert_allclose(evaluate_coverages(x,p.iloc[:2],np.full(2,50.)),m.evaluate(x,p.iloc[:2],50.)[0],rtol=1e-12,atol=1e-10)
    frames=[]
    for cov in [25,50,75]:
        a=m.evaluate(x,final_coverage=cov)[0][0] if cov==25 else {50:a50,75:a75}[cov]
        z=account(a,REF)['service'];f=m.annual_frame(x,z,cov);frames.append(f)
    annual=pd.concat(frames,ignore_index=True);annual.to_csv(D/'annual_reference.csv',index=False)
    ep=annual.query('year==2050');ep.to_csv(D/'country_endpoints.csv',index=False)
    tags=regions[ref75[:,:,14].sum(1)<0];print('Negative countries',tags,flush=True)
    grid=x['meta'][['Id','lat_center','lon_center','country_tag','climate_zone','battery_life']].copy()
    area=x['cell'][:,1];totarea=np.bincount(x['region_idx'],weights=area)
    newpv=ref75[:,:,9].sum(1)[x['region_idx']]*area/totarea[x['region_idx']]
    cells[:,14]+=cells[:,9]-newpv;cells[:,9]=newpv
    for j,field in enumerate(m.FIELDS):grid[field]=cells[:,j]
    for ri in range(len(regions)):
        np.testing.assert_allclose(grid.loc[x['region_idx']==ri,'net_gt'].sum(),ref75[ri,:,14].sum(),atol=1e-10)
    grid['gross_gt']=grid.displaced_grid_gt-grid.pv_embodied_gt
    grid['feedback_gt']=grid.cooling_gt+grid.ac_gt+grid.battery_gt-grid.roof_credit_gt
    grid['offset_pct']=100*grid.feedback_gt/grid.gross_gt
    temp=pd.read_csv(R/'input/parameters/grid_temperature.csv',usecols=['Id','era5_t2m_c'])
    grid=grid.merge(temp,on='Id',validate='one_to_one');grid.to_csv(D/'grid_reference.csv',index=False)
    paths=[]
    for label,case in CASES.items():
        module,freight=manufacturing_path(case)
        paths.extend(dict(scenario=label,year=int(y),module_kg_co2e_m2=float(v)) for y,v in zip(m.YEARS,module))
    fixed=manufacturing_path(updated_cases()[0])[0]
    paths.extend(dict(scenario='Frozen 2025',year=int(y),module_kg_co2e_m2=float(v)) for y,v in zip(m.YEARS,fixed))
    pd.DataFrame(paths).to_csv(D/'manufacturing_paths.csv',index=False)
    # The reduced physical model omits storage, cooling, AC and roof feedback.
    reduced_input={**x,'cell':x['cell'].copy(),'intensive':x['intensive'].copy()}
    reduced_input['cell'][:,3]=0;reduced_input['intensive'][:,:,3]=0
    reduced75=account(m.evaluate(reduced_input,final_coverage=75,controls=replace(m.Controls(),roof_kg_m2=0))[0][0],REF)['service']
    reduced_frame=m.annual_frame(x,reduced75,75).set_index(['country_tag','year'])
    f=annual.query('final_coverage_pct==75').copy()
    f['cumulative_reduced_net_gt']=[reduced_frame.loc[(r.country_tag,r.year),'cumulative_net_gt'] for r in f.itertuples()]
    f.to_csv(D/'time_paths.csv',index=False)
    # Individual interventions are conditional changes for the six reference-negative countries.
    base_negative=-np.minimum(ref75[:,:,14].sum(1),0).sum();negative_mask=np.isin(regions,tags)
    specs=[('Coverage 75 to 25%',{},25,REF),('Low-emission manufacturing',{},75,CASES['Low']),
        ('Battery footprint halved',{'battery_lca_kg_per_kwh_capacity':40},75,REF),
        ('Direct use +20 pp',{'direct_use_lift':.2},75,REF),
        ('Roof credit doubled',{'roof_credit_multiplier':2},75,REF),
        ('Battery life +50%',{'battery_life_multiplier':1.5},75,REF),
        ('Cooling demand halved',{'cooling_demand_multiplier':.5},75,REF)]
    interventions=[]
    for label,changes,cov,case in specs:
        sample=pd.DataFrame([{**m.BASE,**changes}]);a=m.evaluate(x,sample,cov)[0][0];v=account(a,case)['service'][:,:,14].sum(1)
        residual=-np.minimum(v[negative_mask],0).sum()
        interventions.append(dict(intervention=label,reduction_pct=100*(base_negative-residual)/base_negative,residual_net_emissions_mt=residual*1000))
    pd.DataFrame(interventions).to_csv(D/'interventions.csv',index=False)
    # Baseline comparisons of independently ranked sets, retaining the full rule's count.
    mask=ref50[:,:,14].sum(1)>=0;k=int(mask.sum());target=a50[:,:,1].sum()
    reduced={**x,'cell':x['cell'].copy(),'intensive':x['intensive'].copy()};reduced['cell'][:,3]=0;reduced['intensive'][:,:,3]=0
    red=account(m.evaluate(reduced,final_coverage=50,controls=replace(m.Controls(),roof_kg_m2=0))[0][0],REF)['service']
    scores={'Reduced sign':red[:,:,14].sum(1), 'Reduced rank':red[:,:,14].sum(1)/red[:,:,1].sum(1),
        'Dynamic grid':red[:,:,8].sum(1)/red[:,:,1].sum(1),'2025 grid':red[:,0,8]/red[:,0,1],
        'Yield per roof':a50[:,:,0].sum(1)/a50[:,-1,18],'Total generation':a50[:,:,0].sum(1)}
    ranks=[];baseline_selected=None
    c,aa,err=solve(x,p.iloc[:1],np.array([target]),mask)
    baseline_selected=account(aa[0],REF)['service'][:,:,14].sum()
    for label,score in scores.items():
        selected=score>=0 if label=='Reduced sign' else np.isin(np.arange(len(regions)),np.argsort(-score,kind='stable')[:k])
        c,aa,err=solve(x,p.iloc[:1],np.array([target]),selected)
        val=account(aa[0],REF)['service'][:,:,14].sum()
        ranks.append(dict(rule=label,retained_regions=int(selected.sum()),coverage_pct=float(c[0]),net_gt=val,full_minus_alternative_gt=baseline_selected-val,matches_full=bool(np.array_equal(mask,selected))))
    pd.DataFrame(ranks).to_csv(D/'ranking_comparisons.csv',index=False)
    # All parameter draws, fixed reference membership and matched delivered electricity.
    rows=[];country=[];maxerror=0
    for start_i in range(0,len(p),128):
        batch=p.iloc[start_i:start_i+128];raw=m.evaluate(x,batch,50)[0];targets=raw[:,:,:,1].sum((1,2))
        cover,screen,error=solve(x,batch,targets,mask);maxerror=max(maxerror,float(abs(error).max()))
        for j,(_,sample) in enumerate(batch.iterrows()):
            ef=raw[j,ci,:,8]/raw[j,ci,:,1];ratio=ef/ef[9]
            for label,case in CASES.items():
                for strategy,a in [('Uniform',raw[j]),('Screened',screen[j])]:
                    z=account(a,case,exponent=sample.deployment_path_exponent,production_grid_ratio=ratio)['service'];v=z[:,:,14].sum(1)
                    rows.append(dict(sample_id=int(sample.sample_id),scenario=label,strategy=strategy,coverage_pct=50 if strategy=='Uniform' else cover[j],target_twh=targets[j],delivered_twh=z[:,:,1].sum(),net_gt=v.sum(),negative_countries=int(((v<0)&(regions!='row')).sum()),displaced_ef_multiplier=sample.displaced_ef_multiplier))
        print('Matched draws',start_i+len(batch),'/',len(p),'elapsed',round(time.time()-start,1),flush=True)
    pd.DataFrame(rows).to_csv(D/'matched_scenarios.csv',index=False)
    u=pd.read_csv(O/'uncertainty_countries.csv')
    u=u[(u.case==REF.name)&(u.accounting=='service')&(u.sample_id>0)&u.country_tag.isin(tags)]
    u[['sample_id','country_tag','net_gt']].to_csv(D/'country_sensitivity.csv',index=False)
    intensity_sensitivity()
    from prepare_figure3_manufacturing import main as prepare_manufacturing_comparison
    prepare_manufacturing_comparison()
    checks=dict(reference_net_gt=float(ref75[:,:,14].sum()),negative_countries=tags.tolist(),net_emissions_mt=float(base_negative*1000),
        matched_draws=len(p)-1,retained_regions=k,maximum_relative_delivery_error=maxerror,
        spatial_allocation='PV service burden by roof reference area within each deployment region; all other terms evaluated per cell',
        kernel_fixed_coverage_equivalence=True,elapsed_seconds=time.time()-start)
    (R/'output/checks/main_figure_data.json').write_text(json.dumps(checks,indent=2),encoding='utf8')
    print(json.dumps(checks,indent=2),flush=True)

if __name__=='__main__':main()
