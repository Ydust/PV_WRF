"""Recalculate supplementary results and dated country examples."""
from prepare_main_figures import *
from prepare_template_data import weighted_quantile
SD=O/'Supplementary_Data';SD.mkdir(exist_ok=True)

def adjusted(x,label):
    z={**x,'cell':x['cell'].copy(),'intensive':x['intensive'].copy()};ctl=m.Controls();patch={};case=REF;acct='service'
    if label=='Production-event PV accounting':acct='event'
    if label=='Linear thermal exposure':ctl=replace(ctl,cooling_linear_coverage=True)
    if label=='Lossless storage':ctl=replace(ctl,battery_rte=1)
    if label in ['Zero thermal response','Reduced PV-grid']:z['intensive'][:,:,3]=0
    if label in ['No storage','Reduced PV-grid']:z['cell'][:,3]=0
    if label=='Fixed battery life':z['cell'][:,4]=10
    if label=='Constant sizing 0.003':z['cell'][:,3]=.003
    if label in ['No roof credit','Reduced PV-grid']:ctl=replace(ctl,roof_kg_m2=0)
    if label=='Earlier storage':patch=dict(storage_onset_pct=15,storage_full_need_pct=60,storage_sizing_multiplier=1.4)
    if label=='Later storage':patch=dict(storage_onset_pct=50,storage_full_need_pct=90,storage_sizing_multiplier=.45)
    if label=='Higher direct use':patch=dict(direct_use_lift=.2)
    if label.startswith('Displaced EF '):patch={'displaced_ef_multiplier':float(label.split()[-1])}
    if label=='Low manufacturing':case=CASES['Low']
    if label=='High manufacturing':case=CASES['High']
    return z,ctl,pd.DataFrame([{**m.BASE,**patch}]),case,acct

def main():
    start=time.time();x=m.prepare_inputs();regions=x['regions'];ci=regions.index('china');p=pd.read_csv(R/'input/parameters/scenario_parameters.csv').sort_values('sample_id')
    raw75=np.load(O/'reference_75.npy');ref=account(raw75,REF)['service'];negative=ref[:,:,14].sum(1)<0
    # Manufacturing counterfactuals use the identical physical deployment ledger.
    annuals={label:m.annual_frame(x,account(raw75,case)['service'],75) for label,case in [('Baseline',REF),('Frozen manufacture',updated_cases()[0]),('Frozen manufacturing grid',updated_cases()[5])]}
    b=annuals['Baseline'];examples=b[b.country_tag.isin(['france','germany'])&b.year.isin([2030,2050])].copy()
    examples['deployment_ef_g_kwh']=examples.annual_displaced_grid_gt/examples.annual_delivered_twh*1e6
    for label,key in [('Frozen manufacture','frozen_manufacture'),('Frozen manufacturing grid','frozen_grid')]:
        f=annuals[label].set_index(['country_tag','year'])
        examples[key+'_cumulative_net_gt']=[f.loc[(r.country_tag,r.year),'cumulative_net_gt'] for r in examples.itertuples()]
        examples[key+'_difference_gt']=examples.cumulative_net_gt-examples[key+'_cumulative_net_gt']
    examples.to_csv(SD/'country_milestones.csv',index=False)
    labels=['Baseline','Production-event PV accounting','Linear thermal exposure','Lossless storage','Zero thermal response','No storage','Fixed battery life','Constant sizing 0.003','No roof credit','Reduced PV-grid']
    tests=[f'Displaced EF {v}' for v in [.5,.75,1,1.25,1.5]]+['Earlier storage','Later storage','Higher direct use']
    structural=[];grid_storage=[]
    for label in labels+tests:
        z,ctl,pp,case,acct=adjusted(x,label);raw=m.evaluate(z,pp,75,ctl)[0][0];a=account(raw,case)[acct];v=a[:,:,14].sum(1)
        row=dict(case=label,net_gt=v.sum(),negative_regions=int((v<0).sum()),shortfall_gt=-np.minimum(v,0).sum(),delivered_twh=a[:,:,1].sum(),pv_burden_gt=a[:,:,9].sum())
        (structural if label in labels else grid_storage).append(row)
        if label=='Reduced PV-grid':
            redbase=a
            m.annual_frame(x,a,75).to_csv(SD/'reduced_annual.csv',index=False)
    pd.DataFrame(structural).to_csv(SD/'structural.csv',index=False);pd.DataFrame(grid_storage).rename(columns={'case':'test'}).to_csv(SD/'grid_storage.csv',index=False)
    # France coverage and annual temporal boundaries, retaining the original nine cases.
    fi=regions.index('france');sel=x['region_idx']==fi
    fx={**x,'cell':x['cell'][sel].copy(),'group':x['group'][sel].copy(),'region_idx':np.zeros(sel.sum(),dtype=x['region_idx'].dtype),'regions':['france']}
    scans=[];times=[]
    for label in ['Baseline','Low manufacturing','High manufacturing','Earlier storage','Later storage','No storage','Zero thermal response','Fixed battery life','Production-event PV accounting']:
        z,ctl,pp,case,acct=adjusted(fx,label)
        for cover in np.arange(0,75.01,.5):
            raw=m.evaluate(z,pp,cover,ctl)[0][0];a=account(raw,case)[acct]
            scans.append(dict(case=label,coverage_pct=cover,net_2050_gt=a[:,:,14].sum()))
            if cover==75:times.extend(dict(case=label,year=int(y),cumulative_net_gt=v) for y,v in zip(m.YEARS,a[0,:,14].cumsum()))
        print('France scan',label,flush=True)
    pd.DataFrame(scans).to_csv(SD/'france_boundary_coverage.csv',index=False);pd.DataFrame(times).to_csv(SD/'france_boundary_time.csv',index=False)
    # Updated isolated interventions with national outcomes and service totals.
    rows=[];base_burden=-np.minimum(ref[:,:,14].sum(1),0).sum()
    specs=[('Coverage 75 to 25%',{},25,REF),('Low-emission manufacturing',{},75,CASES['Low']),('Battery footprint halved',{'battery_lca_kg_per_kwh_capacity':40},75,REF),('Direct use +20 pp',{'direct_use_lift':.2},75,REF),('Roof credit doubled',{'roof_credit_multiplier':2},75,REF),('Battery life +50%',{'battery_life_multiplier':1.5},75,REF),('Cooling demand halved',{'cooling_demand_multiplier':.5},75,REF)]
    for label,patch,cover,case in specs:
        raw=m.evaluate(x,pd.DataFrame([{**m.BASE,**patch}]),cover)[0][0];a=account(raw,case)['service'];v=a[:,:,14].sum(1);burden=-np.minimum(v[negative],0).sum()
        rows.append(dict(intervention=label,reduction_pct=100*(1-burden/base_burden),recovered=int((v[negative]>=0).sum()),net_gt=v.sum(),delivered_twh=a[:,:,1].sum()))
    pd.DataFrame(rows).to_csv(SD/'interventions.csv',index=False)
    # Same paired draws: reduced physical model, and country outcomes at solved delivery.
    u=pd.read_csv(O/'uncertainty_countries.csv');u=u.query('case==@REF.name and accounting=="service" and sample_id>0')
    full=u.pivot(index='sample_id',columns='country_tag',values='net_gt').loc[p.query('sample_id>0').sample_id,regions]
    matched=pd.read_csv(D/'matched_scenarios.csv');members=account(np.load(O/'reference_50.npy'),REF)['service'][:,:,14].sum(1)>=0
    z,ctl,_,_,_=adjusted(x,'Reduced PV-grid');redparts=[];countries=[]
    for start_i in range(0,len(p),128):
        batch=p.iloc[start_i:start_i+128];raw=m.evaluate(x,batch,50)[0];ratio=raw[:,ci,:,8]/raw[:,ci,:,1];ratio=ratio/ratio[:,0,None]
        covers=matched.query('scenario=="Reference" and strategy=="Screened"').set_index('sample_id').loc[batch.sample_id,'coverage_pct'].to_numpy()
        screen=evaluate_coverages(x,batch,covers);screen[:,~members]=0
        redraw=m.evaluate(z,batch,75,ctl)[0]
        for j,sample in enumerate(batch.itertuples()):
            ar=account(redraw[j],REF,exponent=sample.deployment_path_exponent,production_grid_ratio=ratio[j])['service']
            redparts.extend(dict(sample_id=sample.sample_id,country_tag=tag,net_gt=v) for tag,v in zip(regions,ar[:,:,14].sum(1)))
            for scenario,case in CASES.items():
                for strategy,a in [('Uniform',raw[j]),('Screened',screen[j])]:
                    aa=account(a,case,exponent=sample.deployment_path_exponent,production_grid_ratio=ratio[j])['service'];tot=aa.sum(1)
                    countries.extend(dict(sample_id=sample.sample_id,country_tag=tag,scenario=scenario,strategy=strategy,net_gt=tot[ri,14],coverage_pct=50 if strategy=='Uniform' else covers[j] if members[ri] else 0) for ri,tag in enumerate(regions))
        print('Supplementary draws',start_i+len(batch),'/',len(p),'seconds',round(time.time()-start,1),flush=True)
    rc=pd.DataFrame(redparts);rc.to_csv(SD/'reduced_scenarios.csv',index=False)
    red=rc.query('sample_id>0').pivot(index='sample_id',columns='country_tag',values='net_gt').loc[full.index,regions];dis=(full<0)!=(red<0)
    stats=dict(pairs=int(dis.to_numpy().sum()),total_pairs=int(dis.size),pair_percent=float(dis.to_numpy().mean()*100),affected_scenarios=int(dis.any(axis=1).sum()),scenarios=2048,full_negative_only=int(((full<0)&(red>=0)).to_numpy().sum()),reduced_negative_only=int(((full>=0)&(red<0)).to_numpy().sum()))
    (SD/'sign_disagreement.json').write_text(json.dumps(stats,indent=2))
    co=pd.DataFrame(countries);co.to_csv(SD/'matched_countries.csv',index=False)
    check=co.groupby(['sample_id','scenario','strategy']).net_gt.sum();expected=matched.set_index(['sample_id','scenario','strategy']).net_gt.loc[check.index]
    np.testing.assert_allclose(check,expected,atol=1e-9,rtol=0)
    # Descriptive rank association, with the legacy aggregate PV dimensions excluded.
    totals=-u.assign(negative=u.net_gt.clip(upper=0)).groupby('sample_id').negative.sum();params=p.query('sample_id>0').set_index('sample_id')
    rho=[]
    for key in m.PNAMES:
        if key in ['pv_lca_g_per_kwh','pv_lca_2050_multiplier']:continue
        rho.append(dict(parameter=key,spearman_rho=params[key].rank().corr(totals.loc[params.index].rank())))
    pd.DataFrame(rho).to_csv(SD/'conditional_spearman.csv',index=False)
    print('Supplementary data complete',stats,flush=True)

if __name__=='__main__':main()
