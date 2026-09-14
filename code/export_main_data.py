"""Export only the values represented in the main figure panels."""
from pathlib import Path
import numpy as np
import pandas as pd
from paths import DATA_ROOT, WORK, RESULTS


def read(name):
    for path in [WORK / 'Source_Data' / name, DATA_ROOT / 'parameters' / name]:
        if path.is_file():
            return pd.read_csv(path)
    raise FileNotFoundError(name)


def main():
    tables = {}
    def save(name, frame):
        if frame.empty or frame.columns.duplicated().any():
            raise ValueError(name)
        tables[name] = frame.reset_index(drop=True)

    endpoints = read('country_endpoints.csv')
    high = endpoints.query('final_coverage_pct == 75').set_index('country_tag')
    negative = high.query('cumulative_net_gt < 0').sort_values('cumulative_net_gt')
    tags = negative.index.tolist()
    assert len(tags) == 7
    grid = read('figure1_cells.csv')
    visible = (np.floor(grid.lat_center) >= -55) & (np.floor(grid.lat_center) < 75)
    visible &= (np.floor(grid.lon_center) >= -180) & (np.floor(grid.lon_center) < 180)
    coords = ['Id', 'lon_center', 'lat_center']
    map_a = grid.loc[visible, coords].copy()
    map_a['net_balance_mt_co2e'] = grid.loc[visible, 'cumulative_net_gt'] * 1000
    save('figure1a_map.csv', map_a)
    save('figure1b_bars.csv', pd.DataFrame({'country': tags, 'shortfall_mt_co2e': -negative.cumulative_net_gt.to_numpy() * 1000}))
    eligible = (grid.cumulative_net_gt >= 0) & (grid.gross_gt > 0)
    net_emitting = grid.cumulative_net_gt < 0
    map_c = grid.loc[visible & (eligible | net_emitting), coords].copy()
    map_c['series'] = np.where(net_emitting.loc[map_c.index], 'Net-emitting cell', 'Gross saving offset')
    map_c['color_value_pct'] = np.where(net_emitting.loc[map_c.index], np.nan, np.clip(grid.loc[map_c.index, 'offset_pct'], 0, 100))
    save('figure1c_map.csv', map_c)
    zones = read('figure1_zone_summary.csv').sort_values('temperature_c')
    save('figure1d_bars.csv', zones[['climate_zone', 'offset_pct', 'temperature_c']].rename(columns={'offset_pct':'median_gross_saving_offset_pct'}))

    countries = ['brazil','france','ethiopia','costa_rica','kenya','germany']
    budget = high.loc[countries]
    den = budget.cumulative_generation_twh * 1e-6
    components = pd.DataFrame({'country': countries})
    for field,sign in [('displaced_grid',1),('pv_embodied',-1),('battery',-1),('cooling',-1),('ac',-1),('roof_credit',1)]:
        components[field + '_g_co2e_per_kwh'] = (sign * budget['cumulative_' + field + '_gt'] / den).to_numpy()
    components['net_g_co2e_per_kwh'] = (budget.cumulative_net_gt / den).to_numpy()
    save('figure2a_bars.csv', components)
    cells = read('figure2_diagnostic_cells.csv')
    points = cells.loc[cells.main_displayed.astype(bool), ['Id','grid_ef_2050_g_per_kwh','diagnostic_g_kwh','battery_life']]
    save('figure2b_points.csv', points.rename(columns={'grid_ef_2050_g_per_kwh':'grid_ef_g_co2e_per_kwh','diagnostic_g_kwh':'diagnostic_balance_g_co2e_per_kwh','battery_life':'battery_life_years'}))
    save('figure2b_line.csv', read('figure2_diagnostic_trend.csv')[['ef_g_kwh','median']].rename(columns={'ef_g_kwh':'grid_ef_g_co2e_per_kwh','median':'median_balance_g_co2e_per_kwh'}))
    save('figure2b_markers.csv', read('figure2_country_anchors.csv')[['country_tag','ef_g_kwh','net_g_kwh']].rename(columns={'country_tag':'country','ef_g_kwh':'grid_ef_g_co2e_per_kwh','net_g_kwh':'diagnostic_balance_g_co2e_per_kwh'}))

    bars = endpoints[endpoints.country_tag.isin(tags) & endpoints.final_coverage_pct.isin([25,50,75])][['country_tag','final_coverage_pct','cumulative_net_gt']].copy()
    bars['cumulative_net_gt'] *= 1000
    bars = bars.rename(columns={'country_tag':'country','final_coverage_pct':'coverage_pct','cumulative_net_gt':'net_mitigation_mt_co2e'})
    bars['country'] = pd.Categorical(bars.country, categories=tags, ordered=True)
    save('figure3a_points.csv', bars.sort_values(['coverage_pct','country']))
    paths = read('figure3_time_paths.csv')
    paths = paths[paths.country_tag.isin(['sweden','switzerland','france'])][['country_tag','model','year','net_gt']].copy()
    paths['net_gt'] *= 1000
    save('figure3b_lines.csv', paths.rename(columns={'country_tag':'country','net_gt':'net_mitigation_mt_co2e'}))
    assert len(bars) == 21 and len(paths) == 156

    levers = read('figure4_interventions.csv')
    levers = pd.concat([levers.iloc[:1], levers.iloc[1:].sort_values('removed_pct', ascending=False)])
    save('figure4a_bars.csv', levers[['lever','removed_pct']].rename(columns={'removed_pct':'shortfall_removed_pct'}))
    joint = read('figure4_country_scenarios.csv')
    joint = joint[(joint.sample_id > 0) & joint.country_tag.isin(tags)]
    save('figure4b_distribution.csv', joint[['country_tag','sample_id','net_g_kwh']].rename(columns={'country_tag':'country','net_g_kwh':'net_balance_g_co2e_per_kwh'}))
    summary = read('figure4_quantiles.csv').sort_values(['negative_share','median'], ascending=[False,True])
    summary = summary[summary.country_tag.isin(tags)][['country_tag','p25','median','p75','negative_share']].copy()
    summary['baseline'] = [high.loc[t,'cumulative_net_gt'] / high.loc[t,'cumulative_generation_twh'] * 1e6 for t in summary.country_tag]
    summary['negative_share'] *= 100
    save('figure4b_markers.csv', summary.rename(columns={'country_tag':'country','p25':'p25_g_co2e_per_kwh','median':'median_g_co2e_per_kwh','p75':'p75_g_co2e_per_kwh','baseline':'baseline_g_co2e_per_kwh','negative_share':'negative_scenarios_pct'}))
    assert len(joint) == 7 * 2048

    totals = read('figure5_lmh_totals.csv').query('sample_id > 0')
    params = read('scenario_parameters_41.csv').query('sample_id > 0').set_index('sample_id')
    rules = read('figure5_rule_results.csv').query('sample_id > 0')
    categories = [('Screened','Screened',41),('PV 26','Uniform',26),('PV 41','Uniform',41),('PV 60','Uniform',60),('Combined','Screened',26)]
    paired = pd.DataFrame({label:totals.query('strategy == @strategy and pv_factor == @factor').set_index('sample_id').gain_gt for label,strategy,factor in categories}).sort_index()
    assert paired.shape == (2048,5) and paired.notna().all().all()
    save('figure5a_lines_gt_co2e.csv', paired.rename_axis('sample_id').reset_index())
    rows = []
    for label,_,_ in categories:
        q = np.quantile(paired[label], [.05,.5,.95])
        rows.append(dict(category=label,p05_gt_co2e=q[0],median_gt_co2e=q[1],p95_gt_co2e=q[2]))
    save('figure5a_intervals.csv', pd.DataFrame(rows))

    full = rules.query('rule == "FullSign"').set_index('sample_id').sort_index()
    alternatives = ['ReducedSign','ReducedTopK','GridDynamicTopK','Grid2025TopK','YieldTopK','TotalPVTopK']
    labels = ['Reduced sign (38)','Reduced rank (37)','Dynamic grid (37)','2025 grid (37)','Yield per roof (37)','Total generation (37)']
    dots=[]; intervals=[]
    for j,(rule,label) in enumerate(zip(alternatives,labels)):
        alternative = rules.query('rule == @rule').set_index('sample_id').loc[full.index]
        vals = full.net_gt.to_numpy() - alternative.net_gt.to_numpy()
        jitter = ((full.index.to_numpy() * 37) % 101 / 100 - .5) * .27
        dots.extend(dict(sample_id=int(sid),alternative=label,gain_gt_co2e=float(v),plot_y=float(j+dy)) for sid,v,dy in zip(full.index,vals,jitter))
        q=np.quantile(vals,[.05,.5,.95]);intervals.append(dict(alternative=label,plot_y=j,p05_gt_co2e=q[0],median_gt_co2e=q[1],p95_gt_co2e=q[2]))
    save('figure5b_points.csv',pd.DataFrame(dots))
    save('figure5b_intervals.csv',pd.DataFrame(intervals))

    dots=[];intervals=[];cdf=[]
    bins=np.linspace(.5,1.5,9)
    maximum=int(totals.negative_regions.max())
    for fi,factor in enumerate([26,41,60]):
        pair=totals.query('pv_factor == @factor').pivot(index='sample_id',columns='strategy',values='net_gt').sort_index()
        gain=pair.Screened-pair.Uniform;x=params.loc[pair.index,'displaced_ef_multiplier']
        dots.extend(dict(sample_id=int(sid),pv_factor_g_co2e_per_kwh=factor,displaced_ef_multiplier=float(xx),gain_gt_co2e=float(yy)) for sid,xx,yy in zip(pair.index,x,gain))
        for k,(lo,hi) in enumerate(zip(bins[:-1],bins[1:])):
            mask=(x>=lo)&(x<hi if k<7 else x<=hi)
            q=np.quantile(gain[mask],[.05,.5,.95]);center=(lo+hi)/2
            intervals.append(dict(pv_factor_g_co2e_per_kwh=factor,bin_center=center,plot_x=center+(fi-1)*.016,p05_gt_co2e=q[0],median_gt_co2e=q[1],p95_gt_co2e=q[2]))
        for strategy in ['Uniform','Screened']:
            counts=totals.query('pv_factor == @factor and strategy == @strategy').negative_regions.to_numpy(int)
            cdf.extend(dict(pv_factor_g_co2e_per_kwh=factor,strategy=strategy,net_emitting_regions=int(n),cumulative_scenarios_pct=float((counts<=n).mean()*100)) for n in range(maximum+1))
    save('figure5c_points.csv',pd.DataFrame(dots))
    save('figure5c_intervals.csv',pd.DataFrame(intervals))
    save('figure5d_lines.csv',pd.DataFrame(cdf))

    RESULTS.mkdir(parents=True,exist_ok=True)
    for name,frame in tables.items():
        frame.to_csv(RESULTS/name,index=False)
    print(f'Exported {len(tables)} plotting-data tables.')

if __name__ == '__main__':
    main()
