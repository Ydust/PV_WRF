"""Price each physical rooftop-climate pairing with the registered bill model."""
import itertools
import os
import shutil

from prepare import *

ECON = R / 'outputs/figure6_matched_config_export_20261102'
PREVIOUS = R / 'outputs/figure6_legend_tight_labels_20261104'
GROUPS = ['technology', 'storage_export']
MAP_BG = 'NZ2050'


def price():
    template = (ECON / 'code/calculate.py').read_text(encoding='utf-8-sig')
    anchor = template.index('quant={};money={}')
    prefix = template[:anchor]
    prefix = prefix[:prefix.index("for k in ['CURRENT_FIGURE6_MAIN.json'")] + prefix[prefix.index('registry=read(protect('):]
    prefix = prefix.replace("SRC/'source_data/configuration_registry.json'", "D/'configuration_registry.json'")
    prefix = prefix.replace("SRC/'source_data/account_manifest.json'", "D/'complete_account_manifest.json'")
    prefix = prefix.replace("P/'source_data/fixed_reference_cohorts.json'", "D/'fixed_reference_cohorts.json'")
    scope = {'__file__': __file__}
    exec(compile(prefix, str(ECON / 'code/calculate.py'), 'exec'), scope)
    raw_code = template[anchor:template.index('F=pd.DataFrame(raw);')]
    raw_code = raw_code.replace("J/'quantities'/(sid+'__UNLIMITED.json.gz')", "J/'quantities'/(roof+'__'+sid+'__UNLIMITED.json.gz')")
    raw_code = raw_code.replace("rr=lookup['CP',cid]", "rr=lookup[priced_bg,cid]")
    raw_code = raw_code.replace("q={k:np.asarray(v,float).reshape(n,T) for k,v in obj['quantity'].items()};active_valuation=obj['valuation']",
        "q={k:np.asarray(v,float).reshape(n,T) for k,v in obj['quantity'].items()};active_valuation=obj['valuation'];assert obj['selection']['roof']==roof")
    raw_code = raw_code.replace(" if sid=='REF':ref=v", """ if sid=='REF':
  ref=v
  np.savez_compressed(J/'annual'/(roof+'__reference_service.npz'),country=codes,denominator_MWh=den)
  case_demand=np.array(base['national']['cap'])*np.array(a['energyCountry']['generation'])[:,0]/(np.array(base['national']['p0'])+q['newPV'][:,0])
  case_den=(case_demand[:,None]*dfo).sum(axis=1)/1000
  assert np.all(np.isfinite(case_den)&(case_den>0))""")
    raw_code = raw_code.replace("(cid+'.npz')", "(roof+'__'+cid+'.npz')")
    raw_code = raw_code.replace("dict(configuration_id=cid,country=c,", "dict(roof=roof,configuration_id=cid,country=c,")
    raw_code = raw_code.replace("denominator_MWh=den[i],**comps", "denominator_MWh=den[i],matched_first_year_service_MWh=case_den[i],delta_cost_matched_service_USD_MWh=dc[i]*den[i]/case_den[i],**comps")
    raw_code = raw_code.replace("dict(configuration_id=cid,figure=", "dict(roof=roof,configuration_id=cid,figure=")
    raw_code = raw_code.replace("done=no+1,total=len(cases),configuration=cid", "done=no+1,total=len(cases),roof=roof,configuration=cid")
    ranking = read(D / 'ranking.json')['selected']
    groups = {roof: next(bg for bg in BGS if ranking[bg]['roof'] == roof)
              for roof in sorted({p['roof'] for p in ranking.values()})}
    (J / 'annual').mkdir(exist_ok=True)
    financial = []
    alignment = []
    extra = {}
    checks = {}
    for roof, bg in groups.items():
        scope.update(roof=roof, priced_bg=bg)
        exec(compile(raw_code, str(ECON / 'code/calculate.py'), 'exec'), scope)
        financial.extend(scope['raw'])
        alignment.extend(scope['alignment'])
        extra[roof] = scope['extras']
        same_physical = 0
        for cid in scope['cases']:
            priced_account = account(scope['lookup'][bg, cid]['path'])
            for another in BGS:
                if another != bg and ranking[another]['roof'] == roof:
                    compared = account(scope['lookup'][another, cid]['path'])
                    assert compared['energyCountry'] == priced_account['energyCountry']
                    assert compared['parameters'] == priced_account['parameters']
                    same_physical += 1
        checks[roof] = dict(max_energy=scope['max_energy'], max_closure=scope['max_closure'],
                            exact_equal_energy_accounts=same_physical)
        assert scope['max_energy'] < 1e-10 and scope['max_closure'] < 1e-8
    valuation = pd.DataFrame(financial)
    assert len(valuation) == len(groups)*35*231
    valuation.to_csv(D / 'financial_231_exact_configurations.csv', index=False, encoding='utf-8-sig')
    save(D / 'economic_scenario_crosswalk.json', alignment)
    save(Q / 'economic_source_hashes.json', scope['sources'])
    return valuation, extra, scope, checks


def eligibility(ref_c, case_c, ref_benefit, case_benefit, ref_loss, case_loss):
    tol = 128 * np.finfo(float).eps * np.maximum(1., np.maximum(abs(ref_c), abs(case_c)))
    no_earlier = ~ref_benefit | (case_benefit & (case_loss.isna() | (ref_loss.notna() & (case_loss >= ref_loss))))
    return (ref_c - case_c > tol) & no_earlier, no_earlier


def prepare_cost_figure(financial, extras, scope, checks):
    tech, storage = scope['TECH'], scope['STOR']
    codes = scope['codes']
    rank = read(D / 'ranking.json')['selected']
    carbon = pd.read_parquet(D / 'all_country_scenario_timing.parquet')
    carbon = carbon[carbon.configuration_id.isin(financial.configuration_id)].copy()
    carbon['roof'] = carbon.background.map({bg: p['roof'] for bg, p in rank.items()})
    prices = carbon.merge(financial.drop(columns='export'), on=['roof', 'configuration_id', 'country'], validate='many_to_one')
    prices['eligible'], prices['loss_not_earlier'] = eligibility(
        prices.REF_C2100_Gt, prices.case_C2100_Gt,
        prices.REF_outcome_status.ne('no_benefit_observed'), prices.outcome_status.ne('no_benefit_observed'),
        prices.REF_loss_year.astype(float), prices.case_loss_year.astype(float))
    prices.to_csv(D / 'all_country_background_candidates.csv', index=False, encoding='utf-8-sig')
    selected = prices[prices['export'].eq('UNLIMITED') & prices.family.isin(GROUPS) & prices.eligible &
                      prices.delta_cost_USD_MWh.le(0)].sort_values(
        ['delta_cost_USD_MWh', 'case_C2100_Gt', 'configuration_id'])
    ids = ['country', 'background', 'family']
    selected = selected.drop_duplicates(ids)
    index = pd.MultiIndex.from_product([codes, BGS, GROUPS], names=ids)
    selected = selected.set_index(ids).reindex(index).reset_index()
    selected['configuration'] = selected.configuration.fillna('REF')
    selected['configuration_id'] = selected.configuration_id.fillna('REF__UNLIMITED')
    selected['delta_cost_USD_MWh'] = selected.delta_cost_USD_MWh.fillna(0.)
    selected[['country', 'background', 'family', 'configuration_id', 'configuration', 'delta_cost_USD_MWh']].to_csv(
        D / 'countrywise_selected_unlimited.csv', index=False, encoding='utf-8-sig')

    m = selected[selected.background.eq(MAP_BG)].copy()
    manifest = {(r['background'], r['configuration_id']): r for r in read(D / 'complete_account_manifest.json')}
    a_ref = account(manifest[MAP_BG, 'REF__UNLIMITED']['path'])
    ix = {c: i for i, c in enumerate(codes)}
    assert a_ref['_codes'] == codes
    acc = {}
    tests = []
    for row in m.itertuples(index=False):
        if row.configuration == 'REF':
            continue
        i = ix[row.country]
        ref_class = a_ref['classifications'][i]
        ref_c = a_ref['countries']['C'][i][-1]
        for export in EX:
            key = row.configuration + '__' + export
            if key not in acc:
                acc[key] = account(manifest[MAP_BG, key]['path'])
            a = acc[key]
            cl = a['classifications'][i]
            case_c = a['countries']['C'][i][-1]
            assert a['_codes'][i] == row.country and a['parameters'] == acc[row.configuration + '__UNLIMITED']['parameters']
            time_ok = ref_class['state'] == STATES[3] or (cl['state'] != STATES[3] and (
                cl['first_loss_year'] is None or (ref_class['first_loss_year'] is not None and cl['first_loss_year'] >= ref_class['first_loss_year'])))
            qualifies = ref_c - case_c > 128*np.finfo(float).eps*max(1, abs(ref_c), abs(case_c)) and time_ok
            tests.append(dict(country=row.country, family=row.family, configuration=row.configuration, export=export,
                qualified=qualifies, time_ok=time_ok, reference_C2100_Gt=ref_c, case_C2100_Gt=case_c,
                reference_loss_year=ref_class['first_loss_year'], case_loss_year=cl['first_loss_year'],
                reference_state=ref_class['state'], case_state=cl['state'], source_sha256=manifest[MAP_BG, key]['sha256']))
    table = pd.DataFrame(tests)
    table.to_csv(D / 'same_plan_export_qualification.csv', index=False, encoding='utf-8-sig')
    flags = table.pivot(index=['country', 'family'], columns='export', values='qualified')
    assert flags['UNLIMITED'].all()
    flags['applicability'] = np.select(
        [flags.CAP0 & flags.CAP50, flags.CAP0, flags.CAP50],
        ['CAP0_still_qualified', 'CAP0_only_not_CAP50', 'CAP50_still_qualified'], default='UNLIMITED_only')
    m = m.merge(flags.reset_index(), on=['country', 'family'], how='left', validate='one_to_one')
    m['applicability'] = m.applicability.fillna('reference_fallback')
    m['map_value_USD_MWh'] = m.delta_cost_USD_MWh
    palette = read(PREVIOUS / 'source_data/bivariate_palette.json')
    bounds = palette['cost_boundaries']
    bounds[0] = min(bounds[0], int(5*np.floor(m.map_value_USD_MWh.min()/5)))
    assert np.all(m.map_value_USD_MWh.between(bounds[0], 0))
    m['cost_bin'] = np.maximum(0, np.searchsorted(bounds, m.map_value_USD_MWh, side='left')-1)
    m[['country', 'family', 'configuration_id', 'configuration', 'map_value_USD_MWh', 'applicability',
       'cost_bin', 'UNLIMITED', 'CAP50', 'CAP0']].to_csv(D / 'map_values.csv', index=False, encoding='utf-8-sig')
    save(D / 'bivariate_palette.json', palette)

    # Preserve country weighting despite differences in country cash flows between paired SSPs.
    p = prices[prices.role.isin(ROLES) & prices.family.isin(GROUPS)].copy()
    country = p.groupby(['configuration_id', 'configuration', 'export', 'role', 'country'], as_index=False).agg(
        delta_cost_USD_MWh=('delta_cost_USD_MWh', 'median'),
        delta_cost_matched_service_USD_MWh=('delta_cost_matched_service_USD_MWh', 'median'),
        background_count=('background', 'nunique'))
    country.to_csv(D / 'country_pooled_bar_values.csv', index=False, encoding='utf-8-sig')
    statistics = []
    for bg, group in [('pooled', country), *p.groupby('background')]:
        for (cid, config, export, role), g in group.groupby(['configuration_id', 'configuration', 'export', 'role']):
            q25, med, q75 = g.delta_cost_USD_MWh.quantile([.25, .5, .75])
            statistics.append(dict(background=bg, configuration_id=cid, configuration=config, export=export,
                                   role=role, n=g.country.nunique(), q25=q25, median=med, q75=q75))
    bars = pd.DataFrame(statistics)
    bars.to_csv(D / 'bar_values_all_backgrounds.csv', index=False, encoding='utf-8-sig')
    bars[bars.background.eq('pooled')].to_csv(D / 'plotted_bar_values.csv', index=False, encoding='utf-8-sig')

    # Three explicit M30 test levels. Break-even values remain conditional on the registered price model.
    out = []
    threshold = []
    for bg in BGS:
        roof = rank[bg]['roof']
        fin = financial[financial.roof.eq(roof)].set_index(['configuration_id', 'country'])
        available = prices[prices.background.eq(bg) & prices.family.eq('technology')].set_index(['configuration', 'country'])
        targets = {'REF': np.zeros(len(codes))}
        for cid in tech[1:3]:
            targets[cid] = fin.loc[cid + '__UNLIMITED'].loc[codes].delta_cost_USD_MWh.to_numpy()
        for cid in [tech[0], tech[-1]]:
            d = extras[roof][cid]
            eligible = available.loc[cid].loc[codes].eligible.to_numpy()
            for rate in [0., .1, .2]:
                for c, cost, ok in zip(codes, d['base'] + rate*d['slope'], eligible):
                    out.append(dict(background=bg, roof=roof, country=c, configuration=cid,
                                    M30_test_premium=rate, delta_cost_USD_MWh=cost, carbon_eligible=ok))
            if cid == tech[0]:
                for name, target in targets.items():
                    for c, val, ok in zip(codes, (target-d['base'])/d['slope'], eligible):
                        threshold.append(dict(background=bg, roof=roof, country=c, comparator=name,
                                              M30_price_premium_at_cost_equality=val, carbon_eligible=ok))
    pd.DataFrame(out).to_csv(D / 'M30_price_sensitivity.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(threshold).to_csv(D / 'M30_cost_equality_thresholds.csv', index=False, encoding='utf-8-sig')
    assert len(m) == 462 and len(bars[bars.background.eq('pooled')]) == 68
    save(Q / 'economic_checks.json', dict(status='PASS', valuation=checks, maps=len(m),
        map_support=m.groupby(['family', 'applicability']).size().rename('n').reset_index().to_dict('records'),
        selected_no_intervention=int(m.configuration.eq('REF').sum()), two_physical_cost_runs=True,
        common_service_denominator_frozen_for_comparability=True, all_price_inputs_previously_registered=True))


if __name__ == '__main__':
    
    prepare_cost_figure(*price())
