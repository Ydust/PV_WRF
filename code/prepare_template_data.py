"""Recalculate diagnostic and selection-rule panels in the established template."""
from prepare_main_figures import *

def weighted_quantile(v, w, q):
    order=np.argsort(v);v=np.asarray(v)[order];w=np.asarray(w)[order]
    return v[np.searchsorted(np.cumsum(w),q*w.sum(),side='left')]

def diagnostics():
    source=R/'input/parameters'
    cells=pd.read_csv(source/'diagnostic_cells.csv')
    grid=pd.read_csv(D/'grid_reference.csv').set_index('Id').loc[cells.Id]
    np.testing.assert_allclose(cells.cumulative_generation_twh,grid.generation_twh,rtol=1e-12)
    ef=cells.grid_ef_2050_g_per_kwh
    net=cells.cumulative_delivered_twh*ef/1e6-grid.pv_embodied_gt.to_numpy()-cells.cooling_kwh*ef/1e15-cells.cumulative_ac_gt+cells.cumulative_roof_credit_gt-cells.cumulative_battery_gt
    cells['diagnostic_g_kwh']=net/cells.cumulative_generation_twh*1e6
    cells['cumulative_pv_embodied_gt']=grid.pv_embodied_gt.to_numpy()
    cells.to_csv(D/'diagnostic_cells.csv',index=False)
    old=pd.read_csv(source/'diagnostic_bins.csv');rows=[]
    for row in old.itertuples():
        z=cells[cells.main_displayed&(ef>=row.bin_lower)&(ef<row.bin_upper)]
        w=z.cumulative_generation_twh
        assert len(z)==row.cells
        np.testing.assert_allclose(weighted_quantile(z.grid_ef_2050_g_per_kwh,w,.5),row.ef_g_kwh,atol=1e-10)
        rows.append(dict(ef_g_kwh=weighted_quantile(z.grid_ef_2050_g_per_kwh,w,.5),median=weighted_quantile(z.diagnostic_g_kwh,w,.5)))
    pd.DataFrame(rows).to_csv(D/'diagnostic_trend.csv',index=False)

def main():
    diagnostics();start=time.time();x=m.prepare_inputs();regions=np.array(x['regions']);ci=x['regions'].index('china')
    p=pd.read_csv(R/'input/parameters/scenario_parameters.csv').sort_values('sample_id').reset_index(drop=True)
    reduced={**x,'cell':x['cell'].copy(),'intensive':x['intensive'].copy()};reduced['cell'][:,3]=0;reduced['intensive'][:,:,3]=0
    reduced75=account(m.evaluate(reduced,final_coverage=75,controls=replace(m.Controls(),roof_kg_m2=0))[0][0],REF)['service']
    rf=m.annual_frame(x,reduced75,75).set_index(['country_tag','year'])
    paths=pd.read_csv(D/'time_paths.csv');paths['cumulative_reduced_net_gt']=[rf.loc[(r.country_tag,r.year),'cumulative_net_gt'] for r in paths.itertuples()]
    paths.to_csv(D/'time_paths.csv',index=False)
    a50=np.load(O/'reference_50.npy');full=account(a50,REF)['service'];mask=full[:,:,14].sum(1)>=0;k=int(mask.sum())
    red=account(m.evaluate(reduced,final_coverage=50,controls=replace(m.Controls(),roof_kg_m2=0))[0][0],REF)['service']
    scores={'Reduced sign':red[:,:,14].sum(1),'Reduced rank':red[:,:,14].sum(1)/red[:,:,1].sum(1),'Dynamic grid':red[:,:,8].sum(1)/red[:,:,1].sum(1),'2025 grid':red[:,0,8]/red[:,0,1],'Yield per roof':a50[:,:,0].sum(1)/a50[:,-1,18],'Total generation':a50[:,:,0].sum(1)}
    masks={label:(s>=0 if label=='Reduced sign' else np.isin(np.arange(len(regions)),np.argsort(-s,kind='stable')[:k])) for label,s in scores.items()}
    matched=pd.read_csv(D/'matched_scenarios.csv').query('scenario=="Reference" and strategy=="Screened"').set_index('sample_id')
    records=[];maxerror=0
    for start_i in range(0,len(p),128):
        batch=p.iloc[start_i:start_i+128];n=len(batch);raw=m.evaluate(x,batch,50)[0];upper=m.evaluate(x,batch,75)[0];target=raw[:,:,:,1].sum((1,2))
        ratios=raw[:,ci,:,8]/raw[:,ci,:,1];ratios=ratios/ratios[:,9,None]
        for label,selected in masks.items():
            ref=matched.loc[batch.sample_id]
            if np.array_equal(selected,mask):
                covers=ref.coverage_pct.to_numpy();net=ref.net_gt.to_numpy();served=ref.delivered_twh.to_numpy()
            else:
                lo=np.full(n,50.);hi=np.full(n,75.);flo=raw[:,:,:,1][:,selected,:].sum((1,2))-target;fhi=upper[:,:,:,1][:,selected,:].sum((1,2))-target
                assert (fhi>=0).all() and (flo<=0).all()
                pending=np.arange(n);covers=np.full(n,np.nan)
                for it in range(60):
                    if not len(pending):break
                    c=lo[pending]-flo[pending]*(hi[pending]-lo[pending])/(fhi[pending]-flo[pending])
                    if it>8 and it%4==0:c=(lo[pending]+hi[pending])/2
                    a=evaluate_coverages(x,batch.iloc[pending],c);f=a[:,:,:,1][:,selected,:].sum((1,2))-target[pending]
                    done=abs(f)/target[pending]<1e-10;covers[pending[done]]=c[done]
                    lower=f<0;lo[pending[lower]]=c[lower];flo[pending[lower]]=f[lower];hi[pending[~lower]]=c[~lower];fhi[pending[~lower]]=f[~lower]
                    pending=pending[~done]
                assert not len(pending)
                a=evaluate_coverages(x,batch,covers);a[:,~selected]=0;served=a[:,:,:,1].sum((1,2))
                net=np.array([account(a[j],REF,exponent=sample.deployment_path_exponent,production_grid_ratio=ratios[j])['service'][:,:,14].sum() for j,sample in enumerate(batch.itertuples())])
            error=abs(served/target-1);assert error.max()<1e-10;maxerror=max(maxerror,float(error.max()))
            for j,sample in enumerate(batch.itertuples()):records.append(dict(sample_id=sample.sample_id,rule=label,retained_regions=int(selected.sum()),coverage_pct=covers[j],net_gt=net[j],full_minus_alternative_gt=ref.net_gt.iloc[j]-net[j],delivered_twh=served[j],target_twh=target[j]))
        print('Template selection draws',start_i+n,'/',len(p),'seconds',round(time.time()-start,1),flush=True)
    result=pd.DataFrame(records);result.to_csv(D/'ranking_scenarios.csv',index=False)
    baseline=pd.read_csv(D/'ranking_comparisons.csv').set_index('rule');new=result.query('sample_id==0').set_index('rule').loc[baseline.index]
    np.testing.assert_allclose(new.net_gt,baseline.net_gt,rtol=0,atol=1e-7)
    (R/'output/checks/template_data.json').write_text(json.dumps(dict(draws=2048,rules=6,maximum_relative_delivery_error=maxerror,baseline_verified=True),indent=2))

if __name__=='__main__':main()
