"""Recompute figure inputs using common GREET production inventories."""
from pathlib import Path
from dataclasses import asdict,replace
import os,sys,json,time,inspect,argparse
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT
PREVIEW=ROOT
D=PREVIEW/'output/Main_Figure_Data';D.mkdir(parents=True,exist_ok=True)
CACHE=PREVIEW/'checks/cache';CACHE.mkdir(parents=True,exist_ok=True)
os.environ['PV_WRF_DATA_ROOT']=str(OLD/'input')
os.environ['PV_WRF_OUTPUT_ROOT']=str(PREVIEW/'checks/physical_model')
sys.path.insert(0,str(OLD/'code'))
import model as m
from figure_accounting import service_account
from vintage_accounting import ProductionFactors,allocate

def factor_table():
    rows=[]
    for filename in ['greet_case_results.json','greet_side_results.json']:
        source=ROOT/'output/inventory'/filename
        if not source.exists():source=ROOT/'input/inventory'/filename
        if not source.exists():continue
        native=json.loads(source.read_text(encoding='utf-8-sig'))
        if filename=='greet_side_results.json':
            assert len(native)==52 and {(r['case'],r['production_year']) for r in native}=={(c,y) for c in ['low_cost','high_cost'] for y in range(2025,2051)}
        for r in native:
            correction=r['CI423']*r['DR289']*(1-1e-6)
            rows.append(dict(case=r['case'],year=r['production_year'],
                module=r['BV476']/1000,mounting=(r['CI476']+correction)/1000/r['B66'],
                electrical=r['CG476']/1000/r['B54'],inverter=r['CM476']/1000/r['B106']/r['B54'],
                battery=r['D209']/1000/(1+r['D161'])/r['D157'],housing=r['B254']/1000/r['D157']))
    return pd.DataFrame(rows)

def matrices(table):
    freight=json.loads((OLD/'input/parameters/balance_of_system.json').read_text())['freight_kg_co2e_m2']
    out={}
    for label,case in {'Reference':'regional_transition','Low':'low_cost','High':'high_cost','Frozen':'frozen','Procurement':'regional_transition_procurement'}.items():
        q=table.query('case==@case').sort_values('year')
        if q.empty:continue
        if case=='frozen':q=pd.concat([q]*26,ignore_index=True)
        assert len(q)==26
        out[label]=np.column_stack([q.module+q.mounting+freight,q.electrical,q.inverter,q.battery,q.housing])
    return out

src=inspect.getsource(m._evaluate.py_func).replace('cache=True','cache=False').replace('def _evaluate(', 'def _evaluate_coverages(').replace('paths=group_paths(p,final_cover,intensive,settings)','paths=group_paths(p,final_cover[s],intensive,settings)')
scope=dict(m.__dict__);exec(src,scope)
kernel=scope['_evaluate_coverages']
def evaluate_coverages(x,p,covers):
    return kernel(np.asarray(p[m.PNAMES],float),np.asarray(covers,float),x['cell'],x['group'],x['region_idx'],x['intensive'],len(x['regions']),np.array(list(asdict(m.Controls()).values()),float),False)[0]

def solve(x,p,target,mask):
    lower=np.full(len(p),50.);upper=np.full(len(p),75.)
    al=evaluate_coverages(x,p,lower);ah=evaluate_coverages(x,p,upper)
    fl=al[:,:,:,1][:,mask,:].sum((1,2));fh=ah[:,:,:,1][:,mask,:].sum((1,2))
    assert np.all(fl<=target*(1+1e-10)) and np.all(fh>=target*(1-1e-10)),'Infeasible matched target'
    for k in range(32):
        fraction=np.divide(target-fl,fh-fl,out=np.full_like(target,.5),where=fh>fl)
        covers=lower+np.clip(fraction,1e-8,1-1e-8)*(upper-lower)
        a=evaluate_coverages(x,p,covers);energy=a[:,:,:,1][:,mask,:].sum((1,2));error=energy/target-1
        if abs(error).max()<1e-10:break
        left=error<0;lower=np.where(left,covers,lower);fl=np.where(left,energy,fl)
        upper=np.where(left,upper,covers);fh=np.where(left,fh,energy)
        if k%8==7:
            covers=(lower+upper)/2;a=evaluate_coverages(x,p,covers);energy=a[:,:,:,1][:,mask,:].sum((1,2));error=energy/target-1
            left=error<0;lower=np.where(left,covers,lower);fl=np.where(left,energy,fl);upper=np.where(left,upper,covers);fh=np.where(left,fh,energy)
    assert abs(error).max()<1e-10,abs(error).max()
    a[:,~mask]=0
    return covers,a,error

def physical_cache():
    start=time.time();x=m.prepare_inputs();p=pd.read_csv(OLD/'input/parameters/scenario_parameters.csv').sort_values('sample_id')
    for first in range(0,len(p),128):
        path=CACHE/f'physical_{first:04d}.npz'
        if path.exists():continue
        batch=p.iloc[first:first+128]
        np.savez_compressed(path,uniform50=m.evaluate(x,batch,50)[0],uniform75=m.evaluate(x,batch,75)[0])
        print('Physical draws',min(first+128,len(p)), '/',len(p),'seconds',round(time.time()-start,1),flush=True)

def procurement_contrasts():
    """Apply the Figure 4 procurement pathway to paired Figure 5 deployments."""
    import hashlib
    factors=matrices(factor_table())['Procurement']
    p=pd.read_csv(OLD/'input/parameters/scenario_parameters.csv').sort_values('sample_id')
    membership=pd.read_csv(D/'ranking_membership.csv')
    regions=membership.country_tag.to_numpy()
    mask=membership.Full.to_numpy(dtype=bool)
    key=f'{int.from_bytes(hashlib.sha256(mask.tobytes()).digest()[:6],"big"):012x}'
    existing=pd.read_csv(D/'matched_scenarios.csv').query('scenario=="Reference"').set_index(['sample_id','strategy'])
    rows=[]
    for first in range(0,len(p),128):
        with np.load(CACHE/f'physical_{first:04d}.npz') as cache:raw=cache['uniform50']
        with np.load(CACHE/f'matched_{first:04d}_{key}.npz') as cache:
            screen=cache['annual'];covers=cache['covers']
        for j,(_,sample) in enumerate(p.iloc[first:first+128].iterrows()):
            for strategy,physical in [('Uniform',raw[j]),('Screened',screen[j])]:
                z=service_account(physical,factors,sample.battery_lca_kg_per_kwh_capacity/80.)
                v=z[:,:,14].sum(1);reference=existing.loc[(int(sample.sample_id),strategy)]
                np.testing.assert_allclose(z[:,:,1].sum(),reference.target_twh,rtol=1e-10)
                assert v.sum()>=reference.net_gt-1e-10
                if sample.sample_id==0:
                    table=factor_table().query('case=="regional_transition_procurement"').sort_values('year')
                    freight=json.loads((OLD/'input/parameters/balance_of_system.json').read_text())['freight_kg_co2e_m2']
                    ff=ProductionFactors({'module':table.module.to_numpy(),'mounting':table.mounting.to_numpy(),'freight':np.full(26,freight),'electrical':table.electrical.to_numpy(),'inverter':table.inverter.to_numpy()},table.battery.to_numpy(),storage_auxiliary=table.housing.to_numpy())
                    np.testing.assert_allclose(z,allocate(physical,ff)['service'],rtol=2e-11,atol=1e-11)
                rows.append(dict(sample_id=int(sample.sample_id),scenario='Procurement',strategy=strategy,
                    coverage_pct=50 if strategy=='Uniform' else covers[j],target_twh=reference.target_twh,
                    delivered_twh=z[:,:,1].sum(),net_gt=v.sum(),
                    negative_countries=int(((v<0)&(regions!='row')).sum()),
                    displaced_ef_multiplier=sample.displaced_ef_multiplier))
    result=pd.DataFrame(rows)
    assert len(result)==2049*2 and not result.duplicated(['sample_id','strategy']).any()
    result.to_csv(D/'matched_procurement.csv',index=False)
    check=json.loads((PREVIEW/'checks/data_validation.json').read_text())
    check['figure5_combined']='Screened deployment plus reference regional transition and additional wind procurement (0% in 2025 to 50% in 2050), identical to Figure 4 procurement'
    check['figure5_procurement_rows']=len(result)
    check['procurement_independent_adapter_check']=True
    (PREVIEW/'checks/data_validation.json').write_text(json.dumps(check,indent=2),encoding='utf-8')
    print('Matched procurement:',len(result),'rows; all delivery and independent adapter checks passed',flush=True)

def strategy_tradeoffs():
    """Compare total mitigation with unoffset national net-emission burdens."""
    import hashlib
    factors=matrices(factor_table())
    p=pd.read_csv(OLD/'input/parameters/scenario_parameters.csv').sort_values('sample_id')
    membership=pd.read_csv(D/'ranking_membership.csv')
    named=membership.country_tag.to_numpy()!='row'
    masks={label:membership[label].to_numpy(dtype=bool) for label in ['Full','Yield per roof']}
    keys={label:f'{int.from_bytes(hashlib.sha256(mask.tobytes()).digest()[:6],"big"):012x}' for label,mask in masks.items()}
    existing=pd.concat([pd.read_csv(D/'matched_scenarios.csv'),pd.read_csv(D/'matched_procurement.csv')]).set_index(['sample_id','scenario','strategy'])
    ranking=pd.read_csv(D/'ranking_scenarios.csv').query('rule=="Yield per roof"').set_index('sample_id')
    specs=[('Uniform','Reference',None),('Screened','Reference','Full'),('Yield per roof','Reference','Yield per roof'),('Procurement','Procurement',None),('Combined','Procurement','Full')]
    rows=[];country=[]
    for first in range(0,len(p),128):
        with np.load(CACHE/f'physical_{first:04d}.npz') as cache:uniform=cache['uniform50']
        physical={None:uniform};coverage={None:np.full(len(uniform),50.)}
        for label,key in keys.items():
            with np.load(CACHE/f'matched_{first:04d}_{key}.npz') as cache:
                physical[label]=cache['annual'];coverage[label]=cache['covers']
        for j,(_,sample) in enumerate(p.iloc[first:first+128].iterrows()):
            sid=int(sample.sample_id);baseline=existing.loc[(sid,'Reference','Uniform')]
            for strategy,factor,selection in specs:
                z=service_account(physical[selection][j],factors[factor],sample.battery_lca_kg_per_kwh_capacity/80.)
                net=z[:,:,14].sum(1);delivered=z[:,:,1].sum()
                np.testing.assert_allclose(delivered,baseline.target_twh,rtol=1e-10)
                expected=(existing.loc[(sid,'Reference','Screened')].net_gt-ranking.loc[sid].full_minus_alternative_gt) if strategy=='Yield per roof' else existing.loc[(sid,factor,'Uniform' if selection is None else 'Screened')].net_gt
                np.testing.assert_allclose(net.sum(),expected,atol=1e-10)
                rows.append(dict(sample_id=sid,strategy=strategy,coverage_pct=coverage[selection][j],delivered_twh=delivered,
                    gain_gt=net.sum()-baseline.net_gt,national_net_emissions_mt=-np.minimum(net[named],0).sum()*1000))
                if sid==0:
                    country.extend(dict(strategy=strategy,country_tag=tag,net_mt=value*1000) for tag,value in zip(membership.country_tag,net))
    result=pd.DataFrame(rows)
    assert len(result)==2049*5 and not result.duplicated(['sample_id','strategy']).any()
    assert (result.national_net_emissions_mt>=0).all()
    result.to_csv(D/'strategy_tradeoffs.csv',index=False)
    pd.DataFrame(country).to_csv(D/'strategy_country_baseline.csv',index=False)
    print(result.query('sample_id>0').groupby('strategy')[['gain_gt','national_net_emissions_mt']].quantile([.05,.5,.95]).to_string(),flush=True)

def main(baseline_only=False):
    begin=time.time();x=m.prepare_inputs();regions=np.array(x['regions'])
    p=pd.read_csv(OLD/'input/parameters/scenario_parameters.csv').sort_values('sample_id')
    table=factor_table();F=matrices(table);table.to_csv(D/'component_factors.csv',index=False)
    if not baseline_only:assert 'Low' in F and 'High' in F,'Side scenarios must finish before complete figure calculation'
    for values in F.values():
        assert np.isfinite(values).all() and (values>=0).all()
        np.testing.assert_allclose(values[0],F['Reference'][0],rtol=1e-7)
    raw75=np.load(OLD/'output/reference_75.npy');ref=service_account(raw75,F['Reference'])
    # Independently implemented adapter equality for both baseline and varying physics.
    freight=json.loads((OLD/'input/parameters/balance_of_system.json').read_text())['freight_kg_co2e_m2']
    for case,label in [('regional_transition','Reference'),('low_cost','Low'),('high_cost','High')]:
        if label not in F:continue
        q=table.query('case==@case').sort_values('year')
        ff=ProductionFactors({'module':q.module.to_numpy(),'mounting':q.mounting.to_numpy(),'freight':np.full(26,freight),'electrical':q.electrical.to_numpy(),'inverter':q.inverter.to_numpy()},q.battery.to_numpy(),storage_auxiliary=q.housing.to_numpy())
        for a in [raw75,m.evaluate(x,p.iloc[5:6],50)[0][0]]:
            np.testing.assert_allclose(service_account(a,F[label]),allocate(a,ff)['service'],rtol=2e-11,atol=1e-11)
    expected=120.02454030015716
    np.testing.assert_allclose(ref[:,:,14].sum(),expected,atol=1e-10)
    annual=[]
    for cov in [25,50,75]:
        raw=m.evaluate(x,final_coverage=cov)[0][0]
        annual.append(m.annual_frame(x,service_account(raw,F['Reference']),cov))
    annual=pd.concat(annual,ignore_index=True);annual.to_csv(D/'annual_reference.csv',index=False)
    annual.query('year==2050').to_csv(D/'country_endpoints.csv',index=False)
    paths=[]
    for label in ['Reference','Frozen']:
        z=m.annual_frame(x,service_account(raw75,F[label]),75)
        z['series']='Evolving manufacturing grid' if label=='Reference' else 'Frozen 2025 manufacturing grid'
        paths.append(z)
    pd.concat(paths).to_csv(D/'manufacturing_time_paths.csv',index=False)
    negative=ref[:,:,14].sum(1)<0;tags=regions[negative]
    # Preserve country-area allocation of PV service; resolve battery production per cell.
    cellx={**x,'region_idx':np.arange(len(x['cell'])),'regions':list(range(len(x['cell'])))}
    cellraw=m.evaluate(cellx)[0][0];cellnew=service_account(cellraw,F['Reference']);cells=cellnew.sum(1)
    area=x['cell'][:,1];totalarea=np.bincount(x['region_idx'],weights=area)
    newpv=ref[:,:,9].sum(1)[x['region_idx']]*area/totalarea[x['region_idx']]
    cells[:,14]+=cells[:,9]-newpv;cells[:,9]=newpv
    grid=x['meta'][['Id','lat_center','lon_center','country_tag','climate_zone','battery_life']].copy()
    for k,field in enumerate(m.FIELDS):grid[field]=cells[:,k]
    for ri in range(len(regions)):
        np.testing.assert_allclose(grid.loc[x['region_idx']==ri,'net_gt'].sum(),ref[ri,:,14].sum(),atol=1e-10)
    grid['gross_gt']=grid.displaced_grid_gt-grid.pv_embodied_gt
    grid['feedback_gt']=grid.cooling_gt+grid.ac_gt+grid.battery_gt-grid.roof_credit_gt
    grid['offset_pct']=100*grid.feedback_gt/grid.gross_gt
    temp=pd.read_csv(ROOT/'input/parameters/grid_temperature.csv')
    grid.merge(temp,on='Id',validate='one_to_one').to_csv(D/'grid_reference.csv',index=False)
    if baseline_only:
        print('Baseline and grid reconciled:',ref[:,:,14].sum(),'Gt; negative countries:',tags.tolist(),flush=True)
        return
    base_negative=-np.minimum(ref[:,:,14].sum(1),0).sum()
    specs=[('Coverage 75 to 25%',{},25,'Reference',1.),('Low-emission manufacturing',{},75,'Low',1.),
      ('Battery footprint halved',{},75,'Reference',.5),('Direct use +20 pp',{'direct_use_lift':.2},75,'Reference',1.),
      ('Roof credit doubled',{'roof_credit_multiplier':2},75,'Reference',1.),('Battery life +50%',{'battery_life_multiplier':1.5},75,'Reference',1.),
      ('Cooling demand halved',{'cooling_demand_multiplier':.5},75,'Reference',1.),('Manufacturing renewable procurement',{},75,'Procurement',1.)]
    interventions=[]
    for label,changes,cov,factor,bscale in specs:
        raw=m.evaluate(x,pd.DataFrame([{**m.BASE,**changes}]),cov)[0][0]
        vv=service_account(raw,F[factor],bscale)[:,:,14].sum(1)
        residual=-np.minimum(vv[negative],0).sum()
        interventions.append(dict(intervention=label,reduction_pct=100*(base_negative-residual)/base_negative,residual_net_emissions_mt=residual*1000))
    pd.DataFrame(interventions).to_csv(D/'interventions.csv',index=False)
    raw50=np.load(OLD/'output/reference_50.npy');ref50=service_account(raw50,F['Reference'])
    mask=ref50[:,:,14].sum(1)>=0;k=int(mask.sum())
    reduced={**x,'cell':x['cell'].copy(),'intensive':x['intensive'].copy()};reduced['cell'][:,3]=0;reduced['intensive'][:,:,3]=0
    red=service_account(m.evaluate(reduced,final_coverage=50,controls=replace(m.Controls(),roof_kg_m2=0))[0][0],F['Reference'])
    scores={'Reduced sign':red[:,:,14].sum(1),'Reduced rank':red[:,:,14].sum(1)/red[:,:,1].sum(1),
        'Dynamic grid':red[:,:,8].sum(1)/red[:,:,1].sum(1),'2025 grid':red[:,0,8]/red[:,0,1],
        'Yield per roof':raw50[:,:,0].sum(1)/raw50[:,-1,18],'Total generation':raw50[:,:,0].sum(1)}
    masks={'Full':mask}
    for label,score in scores.items():masks[label]=score>=0 if label=='Reduced sign' else np.isin(np.arange(len(regions)),np.argsort(-score,kind='stable')[:k])
    membership=pd.DataFrame({'country_tag':regions,**masks});membership.to_csv(D/'ranking_membership.csv',index=False)
    rows=[];ranks=[];rankbase=[];country=[];maxerr=0.
    for first in range(0,len(p),128):
        batch=p.iloc[first:first+128];path=CACHE/f'physical_{first:04d}.npz'
        if path.exists():
            with np.load(path) as cache:raw=cache['uniform50'];a75=cache['uniform75']
        else:raw=m.evaluate(x,batch,50)[0];a75=m.evaluate(x,batch,75)[0]
        if first==0:
            np.testing.assert_allclose(raw[0],raw50,rtol=1e-12,atol=1e-10)
            np.testing.assert_allclose(a75[0],raw75,rtol=1e-12,atol=1e-10)
        targets=raw[:,:,:,1].sum((1,2));solved={}
        for label,selection in masks.items():
            key=selection.tobytes()
            if key not in solved:
                ck=CACHE/f'matched_{first:04d}_{int.from_bytes(__import__("hashlib").sha256(key).digest()[:6],"big"):012x}.npz'
                if ck.exists():
                    with np.load(ck) as cache:covers,aa,error=cache['covers'],cache['annual'],cache['error']
                else:
                    covers,aa,error=solve(x,batch,targets,selection);np.savez_compressed(ck,covers=covers,annual=aa,error=error)
                maxerr=max(maxerr,float(abs(error).max()));solved[key]=(covers,aa)
        cover,screen=solved[mask.tobytes()]
        for j,(_,sample) in enumerate(batch.iterrows()):
            # Absolute battery footprint uncertainty becomes a relative pack factor;
            # the additional terminal-decline multiplier is not applied a second time.
            bscale=sample.battery_lca_kg_per_kwh_capacity/80.
            full=service_account(screen[j],F['Reference'],bscale)[:,:,14].sum()
            for label,selection in masks.items():
                if label=='Full':continue
                cv,aa=solved[selection.tobytes()];value=service_account(aa[j],F['Reference'],bscale)[:,:,14].sum()
                ranks.append(dict(sample_id=int(sample.sample_id),rule=label,full_minus_alternative_gt=full-value))
                if sample.sample_id==0:rankbase.append(dict(rule=label,retained_regions=int(selection.sum()),coverage_pct=cv[j],net_gt=value,full_minus_alternative_gt=full-value,matches_full=bool(np.array_equal(mask,selection))))
            for label in ['Low','Reference','High']:
                for strategy,aa in [('Uniform',raw[j]),('Screened',screen[j])]:
                    z=service_account(aa,F[label],bscale);v=z[:,:,14].sum(1)
                    rows.append(dict(sample_id=int(sample.sample_id),scenario=label,strategy=strategy,coverage_pct=50 if strategy=='Uniform' else cover[j],target_twh=targets[j],delivered_twh=z[:,:,1].sum(),net_gt=v.sum(),negative_countries=int(((v<0)&(regions!='row')).sum()),displaced_ef_multiplier=sample.displaced_ef_multiplier))
            if sample.sample_id>0:
                z=service_account(a75[j],F['Reference'],bscale)
                for ri in np.where(negative)[0]:
                    net=z[ri,:,14].sum();generation=z[ri,:,0].sum()
                    country.append(dict(sample_id=int(sample.sample_id),country_tag=regions[ri],net_gt=net,generation_twh=generation,net_g_co2e_kwh=net/generation*1e6))
        print('Paired figure draws',min(first+128,len(p)),'/',len(p),'seconds',round(time.time()-begin,1),flush=True)
    matched=pd.DataFrame(rows)
    np.testing.assert_allclose(matched.delivered_twh,matched.target_twh,rtol=1e-10)
    matched.to_csv(D/'matched_scenarios.csv',index=False);pd.DataFrame(ranks).to_csv(D/'ranking_scenarios.csv',index=False)
    pd.DataFrame(rankbase).to_csv(D/'ranking_comparisons.csv',index=False);pd.DataFrame(country).to_csv(D/'country_sensitivity_intensity.csv',index=False)
    check={'baseline_global_net_gt':float(ref[:,:,14].sum()),'negative_countries':tags.tolist(),'negative_total_mt':base_negative*1000,'retained_regions':k,'draws':2048,'maximum_relative_delivery_error':maxerr,'fast_adapter_verified_against_independent_vintage_interface':True,'grid_sum_matches_country':True,'baseline_matches_native_scenario_report':True,'scenario_mapping':{'Low':'EIA low zero-carbon technology cost regional electricity pathway','Reference':'EIA reference regional electricity pathway','High':'EIA high zero-carbon technology cost regional electricity pathway'},'procurement':'Additional wind fraction ramps from 0 to 50% by 2050','inactive_inherited_parameters':['pv_lca_g_per_kwh','pv_lca_2050_multiplier','battery_lca_2050_multiplier','manufacturing_path_exponent'],'battery_uncertainty':'Initial factor draws divided by 80 scale the new pack factor; no extra terminal decline; housing factors fixed','manufacturing_paths':'Common GREET factors per scenario; not coupled to sampled use-region grid paths','elapsed_seconds':time.time()-begin}
    (PREVIEW/'checks/data_validation.json').write_text(json.dumps(check,indent=2),encoding='utf-8')
    print(json.dumps(check,indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--physical-only',action='store_true');parser.add_argument('--baseline-only',action='store_true');parser.add_argument('--procurement-only',action='store_true');parser.add_argument('--tradeoffs-only',action='store_true');args=parser.parse_args()
    if args.tradeoffs_only:strategy_tradeoffs()
    elif args.procurement_only:procurement_contrasts()
    elif args.physical_only:physical_cache()
    else:
        main(args.baseline_only)
        if not args.baseline_only:
            procurement_contrasts()
            strategy_tradeoffs()
