"""Recompute supplementary analyses with the resolved production inventory."""
from prepare_main_figure_data import *
import hashlib
SD=ROOT/'output/Supplementary_Data'
SD.mkdir(parents=True,exist_ok=True)
F=matrices(factor_table())

def account(raw,label='Reference',scale=1.,event=False):
    if not event:return service_account(raw,F[label],scale)
    f=F[label]
    factors=ProductionFactors({'module':f[:,0],'mounting':np.zeros(26),'electrical':f[:,1],'inverter':f[:,2]},f[:,3]*scale,storage_auxiliary=f[:,4])
    return allocate(raw,factors)['event']

def adjusted(x,label):
    z={**x,'cell':x['cell'].copy(),'intensive':x['intensive'].copy()};ctl=m.Controls();patch={};factor='Reference'
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
    if label=='Low manufacturing':factor='Low'
    if label=='High manufacturing':factor='High'
    return z,ctl,pd.DataFrame([{**m.BASE,**patch}]),factor,label=='Production-event PV accounting'

def wq(v,w,q=.5):
    ix=np.argsort(v);v=np.asarray(v)[ix];w=np.asarray(w)[ix]
    return v[np.searchsorted(np.cumsum(w),q*w.sum(),side='left')]

def main():
    x=m.prepare_inputs();regions=x['regions'];p=pd.read_csv(OLD/'input/parameters/scenario_parameters.csv').sort_values('sample_id')
    raw=np.load(OLD/'output/reference_75.npy');ref=account(raw);negative=ref[:,:,14].sum(1)<0
    labels=['Baseline','Production-event PV accounting','Linear thermal exposure','Lossless storage','Zero thermal response','No storage','Fixed battery life','Constant sizing 0.003','No roof credit','Reduced PV-grid']
    tests=[f'Displaced EF {v}' for v in [.5,.75,1,1.25,1.5]]+['Earlier storage','Later storage','Higher direct use']
    rows=[]
    for label in labels+tests:
        z,ctl,pp,f,event=adjusted(x,label);a=account(m.evaluate(z,pp,75,ctl)[0][0],f,event=event);v=a[:,:,14].sum(1)
        rows.append(dict(case=label,net_gt=v.sum(),negative_regions=int((v<0).sum()),shortfall_gt=-np.minimum(v,0).sum(),delivered_twh=a[:,:,1].sum(),pv_burden_gt=a[:,:,9].sum()))
        if label=='Reduced PV-grid':m.annual_frame(x,a,75).to_csv(SD/'reduced_annual.csv',index=False)
        print('Structural:',label,flush=True)
    df=pd.DataFrame(rows);df[df.case.isin(labels)].to_csv(SD/'structural.csv',index=False);df[df.case.isin(tests)].rename(columns={'case':'test'}).to_csv(SD/'grid_storage.csv',index=False)
    sel=x['region_idx']==regions.index('france');fx={**x,'cell':x['cell'][sel].copy(),'group':x['group'][sel].copy(),'region_idx':np.zeros(sel.sum(),dtype=x['region_idx'].dtype),'regions':['france']}
    scans=[];times=[]
    for label in ['Baseline','Low manufacturing','High manufacturing','Earlier storage','Later storage','No storage','Zero thermal response','Fixed battery life','Production-event PV accounting']:
        z,ctl,pp,f,event=adjusted(fx,label)
        for cov in np.arange(0,75.01,.5):
            a=account(m.evaluate(z,pp,cov,ctl)[0][0],f,event=event)
            scans.append(dict(case=label,coverage_pct=cov,net_2050_gt=a[:,:,14].sum()))
            if cov==75:times.extend(dict(case=label,year=int(y),cumulative_net_gt=v) for y,v in zip(m.YEARS,a[0,:,14].cumsum()))
        print('Coverage scan:',label,flush=True)
    pd.DataFrame(scans).to_csv(SD/'france_boundary_coverage.csv',index=False);pd.DataFrame(times).to_csv(SD/'france_boundary_time.csv',index=False)
    # Procurement and reference use exactly the same physical service ledger.
    ann={k:m.annual_frame(x,account(raw,k),75).set_index(['country_tag','year']) for k in ['Reference','Frozen','Procurement']}
    b=ann['Reference'].reset_index();b=b[b.country_tag.isin(['sweden','paraguay','switzerland','france','germany'])&b.year.isin([2030,2050])].copy()
    b['deployment_ef_g_kwh']=b.annual_displaced_grid_gt/b.annual_delivered_twh*1e6
    for k in ['Frozen','Procurement']:
        b[k.lower()+'_cumulative_net_gt']=[ann[k].loc[(r.country_tag,r.year),'cumulative_net_gt'] for r in b.itertuples()]
    b['manufacturing_gain_gt']=b.cumulative_net_gt-b.frozen_cumulative_net_gt
    b['procurement_gain_gt']=b.procurement_cumulative_net_gt-b.cumulative_net_gt
    b.to_csv(SD/'country_milestones.csv',index=False)
    base=-np.minimum(ref[:,:,14].sum(1),0).sum();rows=[]
    specs=[('Coverage 75 to 25%',{},25,'Reference',1),('Low-emission manufacturing',{},75,'Low',1),('Battery footprint halved',{},75,'Reference',.5),('Direct use +20 pp',{'direct_use_lift':.2},75,'Reference',1),('Roof credit doubled',{'roof_credit_multiplier':2},75,'Reference',1),('Battery life +50%',{'battery_life_multiplier':1.5},75,'Reference',1),('Cooling demand halved',{'cooling_demand_multiplier':.5},75,'Reference',1),('Manufacturing renewable procurement',{},75,'Procurement',1)]
    for label,patch,cov,f,scale in specs:
        a=account(m.evaluate(x,pd.DataFrame([{**m.BASE,**patch}]),cov)[0][0],f,scale);v=a[:,:,14].sum(1)
        rows.append(dict(intervention=label,reduction_pct=100*(1+np.minimum(v[negative],0).sum()/base),recovered=int((v[negative]>=0).sum()),net_gt=v.sum(),delivered_twh=a[:,:,1].sum()))
    pd.DataFrame(rows).to_csv(SD/'interventions.csv',index=False)
    # Fixed 2050 deployment-factor diagnostic; replace both PV and storage burdens.
    cells=pd.read_csv(OLD/'input/parameters/figure2_diagnostic_cells.csv');grid=pd.read_csv(D/'grid_reference.csv').set_index('Id').loc[cells.Id]
    np.testing.assert_allclose(cells.cumulative_generation_twh,grid.generation_twh,rtol=1e-12)
    ef=cells.grid_ef_2050_g_per_kwh
    net=cells.cumulative_delivered_twh*ef/1e6-grid.pv_embodied_gt.to_numpy()-cells.cooling_kwh*ef/1e15-cells.cumulative_ac_gt+cells.cumulative_roof_credit_gt-grid.battery_gt.to_numpy()
    cells['diagnostic_g_kwh']=net/cells.cumulative_generation_twh*1e6;cells['cumulative_pv_embodied_gt']=grid.pv_embodied_gt.to_numpy();cells['cumulative_battery_gt']=grid.battery_gt.to_numpy()
    cells.to_csv(SD/'diagnostic_cells.csv',index=False)
    bins=pd.read_csv(OLD/'input/parameters/figure2_diagnostic_trend.csv');trend=[]
    for r in bins.itertuples():
        z=cells[cells.main_displayed&(ef>=r.bin_lower)&(ef<r.bin_upper)];assert len(z)==r.cells
        trend.append(dict(ef_g_kwh=wq(z.grid_ef_2050_g_per_kwh,z.cumulative_generation_twh),median=wq(z.diagnostic_g_kwh,z.cumulative_generation_twh)))
    pd.DataFrame(trend).to_csv(SD/'diagnostic_trend.csv',index=False)
    red,ctl,_,_,_=adjusted(x,'Reduced PV-grid');members=pd.read_csv(D/'ranking_membership.csv').Full.to_numpy(bool);key=f'{int.from_bytes(hashlib.sha256(members.tobytes()).digest()[:6],"big"):012x}'
    fullrows=[];redrows=[];matched=[]
    for first in range(0,len(p),128):
        batch=p.iloc[first:first+128]
        with np.load(CACHE/f'physical_{first:04d}.npz') as q:u=q['uniform50'];a75=q['uniform75']
        with np.load(CACHE/f'matched_{first:04d}_{key}.npz') as q:s=q['annual'];covers=q['covers']
        rc=SD/f'reduced_physical_{first:04d}.npy'
        if rc.exists():rr=np.load(rc)
        else:rr=m.evaluate(red,batch,75,ctl)[0];np.save(rc,rr)
        for j,r in enumerate(batch.itertuples()):
            for arr,dest in [(a75[j],fullrows),(rr[j],redrows)]:
                a=account(arr,scale=r.battery_lca_kg_per_kwh_capacity/80.)
                dest.extend(dict(sample_id=r.sample_id,country_tag=tag,net_gt=v) for tag,v in zip(regions,a[:,:,14].sum(1)))
            for f in ['Low','Reference','High']:
                for strategy,arr in [('Uniform',u[j]),('Screened',s[j])]:
                    v=account(arr,f,r.battery_lca_kg_per_kwh_capacity/80.)[:,:,14].sum(1)
                    matched.extend(dict(sample_id=r.sample_id,country_tag=tag,scenario=f,strategy=strategy,net_gt=v[i],coverage_pct=50 if strategy=='Uniform' else covers[j] if members[i] else 0) for i,tag in enumerate(regions))
        print('Supplementary ensemble:',min(first+128,len(p)),'/',len(p),flush=True)
    full=pd.DataFrame(fullrows);red=pd.DataFrame(redrows);co=pd.DataFrame(matched)
    full.to_csv(SD/'full_scenarios.csv',index=False);red.to_csv(SD/'reduced_scenarios.csv',index=False);co.to_csv(SD/'matched_countries.csv',index=False)
    a=full.query('sample_id>0').pivot(index='sample_id',columns='country_tag',values='net_gt');b=red.query('sample_id>0').pivot(index='sample_id',columns='country_tag',values='net_gt');dis=(a<0)!=(b<0)
    stats=dict(pairs=int(dis.to_numpy().sum()),total_pairs=int(dis.size),pair_percent=float(dis.to_numpy().mean()*100),affected_scenarios=int(dis.any(axis=1).sum()),scenarios=2048,full_negative_only=int(((a<0)&(b>=0)).to_numpy().sum()),reduced_negative_only=int(((a>=0)&(b<0)).to_numpy().sum()))
    (SD/'sign_disagreement.json').write_text(json.dumps(stats,indent=2))
    expected=pd.read_csv(D/'matched_scenarios.csv').set_index(['sample_id','scenario','strategy']).net_gt
    got=co.groupby(['sample_id','scenario','strategy']).net_gt.sum();np.testing.assert_allclose(got,expected.loc[got.index],atol=1e-9,rtol=0)
    target=-a.clip(upper=0).sum(1);params=p.query('sample_id>0').set_index('sample_id')
    inactive=['pv_lca_g_per_kwh','pv_lca_2050_multiplier','battery_lca_2050_multiplier','manufacturing_path_exponent']
    rho=[dict(parameter=k,spearman_rho=params[k].rank().corr(target.loc[params.index].rank())) for k in m.PNAMES if k not in inactive]
    assert len(rho)==14;pd.DataFrame(rho).to_csv(SD/'conditional_spearman.csv',index=False)
    (SD/'validation.json').write_text(json.dumps({'matched_country_totals_verified':True,'baseline_net_gt':float(ref[:,:,14].sum()),'sign_comparison':stats},indent=2))
    print('COMPLETE',stats,flush=True)

if __name__=='__main__':main()
