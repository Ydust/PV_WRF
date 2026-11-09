"""Rebuild figure sources from the selected historical accounts."""
import gzip
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

J = Path(__file__).resolve().parents[1]
R = J.parents[1]
D = J / 'source_data'
Q = J / 'qa'
OLD = R / 'outputs/figures3_5_unified_time_metric_20261102'
PRIOR_FIG2 = R / 'outputs/figure2_compact_rings_20261104/source_data'
HIST = R / 'outputs/opening_balance_reference_cohorts_20261102'
BGS = ['CP', 'NDC', 'B2C', 'NZ2050', 'LD']
ROLES = ['formed_then_lost', 'opening_benefit_then_lost']
STATES = ROLES + ['benefit_without_observed_loss', 'no_observed_benefit']
EX = ['UNLIMITED', 'CAP50', 'CAP0']
BRANCH = 'PATHWAY_OPTIMAL_MATCHED_SSP_HISTORICAL_20261105'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def account(path):
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        return json.load(handle)


def determine_state(balance, trajectory):
    last_sign = np.sign(balance)
    benefit = balance < 0
    first_loss = None
    for year, value in enumerate(trajectory, 2025):
        sign = np.sign(value)
        if sign == 0:
            continue
        benefit |= sign < 0
        if last_sign < 0 and sign > 0 and first_loss is None:
            first_loss = year
        last_sign = sign
    if first_loss is not None:
        return (ROLES[1] if balance < 0 else ROLES[0]), first_loss
    return (STATES[2] if benefit else STATES[3]), None


def reference_sources(ranking):
    prior_refs = read(PRIOR_FIG2 / 'reference_curves.json')
    prior_national = pd.read_csv(PRIOR_FIG2 / 'national_reference_events.csv')
    countries = prior_national.drop_duplicates('country').set_index('country').name.to_dict()
    refs = {}
    national = []
    rings = []
    comparisons = []
    candidates = []
    groups = {}
    for bg in BGS:
        winner = ranking['selected'][bg]
        current = J / 'accounts' / f'{bg}__REF__UNLIMITED.json.gz'
        prior_output = R / 'outputs/supplementary_complete_figures_20261104/accounts'
        for i, candidate in enumerate(ranking['candidates'][bg], 1):
            src = prior_output / f"{bg}__ROOF_{candidate['roof']}__CLIMATE_{candidate['climate']}.json.gz"
            a = account(src)
            assert abs(a['global']['C'][-1] - candidate['C2100_Gt']) < 1e-10
            counts = pd.Series([c['state'] for c in a['classifications']]).value_counts()
            candidates.append(dict(background=bg, rank=i, **candidate,
                first_loss_year=a['events']['global']['first_loss_year'],
                GTL=int(counts.get(ROLES[0], 0)), IBL=int(counts.get(ROLES[1], 0)),
                gap_from_best_Gt=candidate['C2100_Gt'] - winner['C2100_Gt'],
                source=str(src), source_sha256=sha(src)))
            if i != 1:
                continue
            source = current if current.exists() else src
            if source == current:
                replay = account(source)
                assert replay['countries'] == a['countries']
                assert replay['referenceAccountId'] == BRANCH
            global_year = a['events']['global']['first_loss_year']
            opening = sum(a['openingBalances'])
            assert determine_state(opening, a['global']['C'])[1] == global_year
            refs[bg] = dict(C=a['global']['C'], opening_Gt=opening, first_loss_year=global_year,
                            source_account=str(source), source_sha256=sha(source))
            members = {state: [] for state in STATES}
            for c, cl, balance, curve in zip(a['_codes'], a['classifications'], a['openingBalances'], a['countries']['C']):
                state, loss = determine_state(balance, curve)
                assert (state, loss) == (cl['state'], cl['first_loss_year'])
                national.append(dict(background=bg, country=c, name=countries[c], opening_balance_Gt=balance,
                    first_loss_year=loss, state=state, C2025_Gt=curve[0], C2100_Gt=curve[-1],
                    recovery_after_loss=cl['recovery_after_loss'], recovered_at_2100=cl['recovered_at_2100'],
                    positive_at_2100=cl['positive_at_2100']))
                members[state].append(c)
            n = len(a['_codes'])
            event = sorted(members[ROLES[0]] + members[ROLES[1]])
            rings.append(dict(background=bg, denominator=n, counts={k: len(v) for k, v in members.items()},
                first_loss_country_ids=event, slice_country_ids=members, loss_numerator=len(event), loss_percent=100*len(event)/n,
                global_first_loss_year=global_year, global_C2100_Gt=a['global']['C'][-1]))
            groups[bg] = {state: sorted(members[state]) for state in ROLES}
            old = prior_national[prior_national.background == bg].set_index('country').loc[a['_codes']]
            diff_state = old.state.to_numpy() != np.array([c['state'] for c in a['classifications']])
            new_years = pd.Series([c['first_loss_year'] for c in a['classifications']], dtype='Float64').to_numpy(na_value=np.nan)
            paired = np.isfinite(new_years) & old.first_loss_year.notna().to_numpy()
            comparisons.append(dict(background=bg, **candidate, global_loss_year=global_year,
                SSP2_C2100_Gt=prior_refs[bg]['C'][-1], SSP2_loss_year=prior_refs[bg]['first_loss_year'],
                delta_C2100_vs_SSP2_Gt=a['global']['C'][-1] - prior_refs[bg]['C'][-1],
                GTL=len(members[ROLES[0]]), IBL=len(members[ROLES[1]]), changed_country_state=int(diff_state.sum()),
                common_event_country_count=int(paired.sum()),
                changed_year_in_common_event_countries=int(np.count_nonzero(new_years[paired] != old.first_loss_year.to_numpy()[paired]))))
    unions = {state: sorted({c for bg in BGS for c in groups[bg][state]}) for state in ROLES}
    assert not set(unions[ROLES[0]]).intersection(unions[ROLES[1]])
    save(D / 'fixed_reference_cohorts.json', dict(id=BRANCH, groups=groups, unions=unions))
    save(D / 'reference_curves.json', refs)
    save(D / 'ring_statistics.json', rings)
    pd.DataFrame(national).to_csv(D / 'national_reference_events.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(comparisons).to_csv(D / 'reference_comparison.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(candidates).to_csv(D / 'matched_ssp_ranking.csv', index=False, encoding='utf-8-sig')
    return refs


def consolidate():
    cfgs = read(OLD / 'source_data/configuration_registry.json')
    keys = {(bg, x['id']) for x in cfgs for bg in BGS}
    rows = [r for manifest in sorted(D.glob('worker_*_manifest.json')) for r in read(manifest)]
    all_rows = {(r['background'], r['configuration_id']): r for r in rows}
    assert len(all_rows) == len(rows) == len(keys) + 8
    assert keys <= set(all_rows)
    analysis = [all_rows[key] for key in sorted(keys)]
    ranking = read(D / 'ranking.json')
    for r in all_rows.values():
        s = r['selection']
        pair = ranking['selected'][r['background']]
        assert (s['roof'], s['climate']) == (pair['roof'], pair['climate'])
        assert sha(r['path']) == r['sha256']
    save(D / 'configuration_registry.json', cfgs)
    save(D / 'account_manifest.json', analysis)
    save(D / 'complete_account_manifest.json', rows)
    return cfgs, analysis


def envelope(configs, rows):
    ids = {'REF__UNLIMITED'} | {c['id'] for c in configs if any(u['figure'] == 3 for u in c['uses'])}
    curves = [account(r['path'])['global']['C'] for r in rows if r['configuration_id'] in ids]
    assert len(ids) == 55 and len(curves) == 275
    save(D / 'all_configuration_envelope.json', dict(low=np.min(curves, axis=0).tolist(),
        high=np.max(curves, axis=0).tolist(), backgrounds=BGS, configurations_per_background=len(ids),
        total_trajectories=len(curves), selection_by_loss_state=False))


def figures_3_to_5():
    # Reuse the published state-pairing and carbon-component workflow.
    text = (OLD / 'code/prepare_analysis.py').read_text(encoding='utf-8-sig')
    text = text.replace("load(P/'source_data/fixed_reference_cohorts.json')", "load(D/'fixed_reference_cohorts.json')")
    text = text.replace("account(P/f'accounts/{bg}__REF.json.gz')", "account(J/f'accounts/{bg}__REF__UNLIMITED.json.gz')")
    text = text.replace("sha(P/'source_data/fixed_reference_cohorts.json')", "sha(D/'fixed_reference_cohorts.json')")
    text = text.replace("for t in range(76):\n            maxclosure=max(maxclosure,abs(C[t]-a['countries']['H'][c][t]+a['countries']['A'][c][t]));expected=math.fsum([B]+a['annualCountry']['net'][c][:t+1]);maxbridge=max(maxbridge,abs(C[t]-expected))",
        "maxclosure=max(maxclosure,float(np.max(np.abs(np.array(C)-a['countries']['H'][c]+np.array(a['countries']['A'][c])))));maxbridge=max(maxbridge,float(np.max(np.abs(np.array(C)-B-np.cumsum(a['annualCountry']['net'][c])))))")
    scope = {'__file__': str(J / 'code/prepare.py'), '__name__': '__main__'}
    exec(compile(text, str(OLD / 'code/prepare_analysis.py'), 'exec'), scope)
    assert scope['maxclosure'] < 1e-10 and scope['maxbridge'] < 1e-10
    f4 = pd.read_csv(D / 'figure4_national_outcomes.csv')
    f4[f4.role.isin(ROLES)].to_csv(D / 'figure4_paired_fixed_cohorts.csv', index=False, encoding='utf-8-sig')
    cols = ['background', 'role', 'family', 'scenario_id']
    f3 = scope['f3']
    grouped = f3[f3.role.isin(ROLES) & f3.family.ne('reference')].groupby(cols)
    f3 = grouped.apply(lambda p: pd.Series(dict(
        n_REF=len(p), n_observed_loss=int(p.paired_events_observed.sum()),
        median_paired_delta_T=p.paired_delta_T.median(), REF_year_median=float(p.REF_loss_year.median()),
        n_advanced=int(p.paired_delta_T.lt(0).sum()), n_unchanged=int(p.paired_delta_T.eq(0).sum()),
        n_delayed=int(p.paired_delta_T.gt(0).sum()), n_not_lost=int(p.outcome_status.eq('benefit_not_lost_by_2100').sum()),
        n_not_formed=int(p.outcome_status.eq('no_benefit_observed').sum()))), include_groups=False).reset_index()
    f3['pct_changed_year'] = 100 * (f3.n_advanced + f3.n_delayed) / f3.n_REF
    assert len(f3) == 540
    f3.to_csv(D / 'parameter_time_and_state_response.csv', index=False, encoding='utf-8-sig')
    f5 = scope['f5']
    keys = ['background', 'role', 'country', 'configuration']
    f5['common_event_all_three'] = f5.groupby(keys).paired_events_observed.transform('all')
    f5.to_parquet(D / 'figure5_all_fixed_country_records.parquet', index=False)
    f5.to_csv(D / 'figure5_all_fixed_country_records.csv', index=False, encoding='utf-8-sig')
    coverage = []
    for (role, group, export), p in f5.groupby(['role', 'subgroup', 'export']):
        q = p[p.common_event_all_three]
        rec = dict(role=role, subgroup=group, export=export, n_full=len(p),
                   n_matched_loss_events=len(q), n_conditional_event_pairs=int(p.paired_events_observed.sum()),
                   common_event_percent=100*len(q)/len(p))
        for axis, col in [('x', 'paired_delta_T'), ('y', 'carbon_gain_Mt')]:
            quant = q[col].quantile([.25, .5, .75])
            rec.update({f'{axis}_{key}': value for key, value in zip(['q25', 'median', 'q75'], quant)})
        coverage.append(rec)
    pd.DataFrame(coverage).to_csv(D / 'figure5_timing_coverage.csv', index=False, encoding='utf-8-sig')


if __name__ == '__main__':
    import sys
    
    reference_sources(read(D / 'ranking.json'))
    if '--references-only' not in sys.argv:
        cfgs, manifest = consolidate()
        envelope(cfgs, manifest)
        figures_3_to_5()
        save(Q / 'data_checks.json', dict(status='PASS', model_accounts=len(manifest), added_restricted_technology_accounts=8))
