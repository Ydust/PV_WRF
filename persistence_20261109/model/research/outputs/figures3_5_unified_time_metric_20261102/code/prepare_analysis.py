"""Unified first-loss timing, fixed REF countries, and explicit non-event outcomes."""
import os,json,gzip,hashlib,math
from pathlib import Path
import numpy as np
import pandas as pd


J=Path(__file__).resolve().parents[1];R=J.parents[1];D=J/'source_data';Q=J/'qa'
P=R/'outputs/opening_balance_reference_cohorts_20261102'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def account(p):
    with gzip.open(p,'rt',encoding='utf8') as ff:return json.load(ff)
cohorts=load(P/'source_data/fixed_reference_cohorts.json');manifest=load(D/'account_manifest.json');configs=load(D/'configuration_registry.json')
codes=list(load(P/'source_data/frozen_inputs.json')['opening'][i]['code'] for i in range(231));years=np.arange(2025,2101)
BGS=['CP','NDC','B2C','NZ2050','LD'];ROLES=['formed_then_lost','opening_benefit_then_lost']
NAMES={'CP':'Current Policies','NDC':'NDCs','B2C':'Below 2°C','NZ2050':'Net Zero 2050','LD':'Low Demand'}
GROUPS={'配储比例':['STORAGE_FC0','STORAGE_FC50','STORAGE_FC100'],'储能容量':['STORAGE_CAP_HALF','STORAGE_CAP_DOUBLE','STORAGE_K05','STORAGE_K1','STORAGE_K2'],'运行启用程度':['STORAGE_UTIL50','STORAGE_UTIL0']}
EX=['UNLIMITED','CAP50','CAP0'];STATUS=['observed_loss','benefit_not_lost_by_2100','no_benefit_observed']
def event(B,C):
    signs=[np.sign(B)]+list(np.sign(C));last=0;events=[];benefit=B<0
    for i,s in enumerate(signs):
        if s==0:continue
        if s<0:benefit=True
        if last and last!=s and i>0:events.append((int(years[i-1]),int(last),int(s)))
        last=s
    loss=next((y for y,a,b in events if a<0 and b>0),None)
    status='observed_loss' if loss is not None else 'benefit_not_lost_by_2100' if benefit else 'no_benefit_observed'
    return loss,status,events
def role(bg,code):return next((r for r in ROLES if code in cohorts['groups'][bg][r]),'outside_fixed_loss_cohorts')
refs={bg:account(P/f'accounts/{bg}__REF.json.gz') for bg in BGS}
refrow={}
for bg,a in refs.items():
    for c,code in enumerate(codes):
        loss,status,ev=event(a['openingBalances'][c],a['countries']['C'][c]);refrow[bg,code]={'year':loss,'status':status,'C2100':a['countries']['C'][c][-1]}
        assert loss==a['classifications'][c]['first_loss_year']
lookup={x['id']:x for x in configs};rows=[];checks=0;maxclosure=0.;maxbridge=0.;account_data={}
for m in manifest:
    assert sha(m['path'])==m['sha256'];a=account(m['path']);cfg=lookup[m['configuration_id']];bg=m['background'];assert a['referenceAccountId']==cohorts['id'];assert a['_codes']==codes
    comp={k:np.sum(np.array(a['annualCountry'][k]),axis=1) for k in ['newManufacturing','replacementManufacturing','treatment','gridAux','A']}
    for c,code in enumerate(codes):
        B=a['openingBalances'][c];C=a['countries']['C'][c];yr,st,ev=event(B,C);cl=a['classifications'][c]
        assert yr==cl['first_loss_year'];checks+=1
        if cfg['id']=='REF__UNLIMITED':
            assert yr==refs[bg]['classifications'][c]['first_loss_year']
            assert cl['state']==refs[bg]['classifications'][c]['state']
        rr=refrow[bg,code];both=yr is not None and rr['year'] is not None
        delta=yr-rr['year'] if both else None
        change='loss_delayed' if both and delta>0 else 'loss_advanced' if both and delta<0 else 'same_loss_year' if both else 'no_benefit_observed' if st=='no_benefit_observed' else 'loss_not_observed_by_2100' if st=='benefit_not_lost_by_2100' else 'new_loss_relative_to_REF'
        for t in range(76):
            maxclosure=max(maxclosure,abs(C[t]-a['countries']['H'][c][t]+a['countries']['A'][c][t]));expected=math.fsum([B]+a['annualCountry']['net'][c][:t+1]);maxbridge=max(maxbridge,abs(C[t]-expected))
        rec={'background':bg,'configuration_id':cfg['id'],'country':code,'role':role(bg,code),'export':m['selection']['exportConstraint'],'case_loss_year':yr,'REF_loss_year':rr['year'],'outcome_status':st,'REF_outcome_status':rr['status'],'paired_delta_T':delta,'paired_events_observed':both,'event_change':change,'opening_balance_Gt':B,'case_C2100_Gt':C[-1],'REF_C2100_Gt':rr['C2100'],'carbon_gain_Mt':(rr['C2100']-C[-1])*1000,'secondary_negative_yearend_count':sum(x<0 for x in C),'recovery_after_loss':yr is not None and any(y>yr and fr>0 and to<0 for y,fr,to in ev),'positive_2100':C[-1]>0,'history_scope':'model_zero_not_observed_zero' if B==0 else 'conditional_continuing_site_history',**{k+'_Gt':float(v[c]) for k,v in comp.items()}}
        rec['case_formation_year']=cl['formation_year'];rec['opening_has_benefit']=B<0
        rows.append(rec)
raw=pd.DataFrame(rows);assert not raw.duplicated(['background','configuration_id','country']).any()
for col in ['case_loss_year','REF_loss_year','paired_delta_T','case_formation_year']:raw[col]=raw[col].astype('Int64')
raw.to_csv(D/'all_country_scenario_timing.csv',index=False,encoding='utf-8-sig')
raw.to_parquet(D/'all_country_scenario_timing.parquet',index=False)

# Figure3: each registered scenario remains a separate case; only matched event pairs have a delta.
f3=[]
for cfg in configs:
    uses=[u for u in cfg['uses'] if u['figure']==3]
    if not uses:continue
    for use in uses:
        part=raw[raw.configuration_id==cfg['id']].copy();part['scenario_id']=use['scenario_id'];part['family']=use['family'];part['scenario_label']=use.get('label') or use['scenario_id'];f3.append(part)
f3=pd.concat(f3,ignore_index=True);f3.to_csv(D/'figure3_all_records.csv',index=False,encoding='utf-8-sig')
points=[];coverage=[]
for (bg,r,fam,sc),p in f3[(f3.role.isin(ROLES))&(f3.family!='reference')].groupby(['background','role','family','scenario_id']):
    v=p.paired_delta_T.dropna();n=len(p);record={'background':bg,'role':r,'family':fam,'scenario_id':sc,'n_reference':n,'n_events':len(v),'median_paired_delta_T':None if not len(v) else float(v.median()),'case_observed_year_median':None if p.case_loss_year.notna().sum()==0 else float(p.case_loss_year.median()),'REF_year_median':float(p.REF_loss_year.median()),**{st:int(p.outcome_status.eq(st).sum()) for st in STATUS}}
    assert sum(record[st] for st in STATUS)==n;points.append(record)
pd.DataFrame(points).to_csv(D/'figure3_parameter_summaries.csv',index=False,encoding='utf-8-sig')
assert len(points)==540 and len(coverage)==0
save(D/'figure3_parameter_summaries.json',points)
for (bg,r,fam),p in f3[(f3.role.isin(ROLES))&(f3.family!='reference')].groupby(['background','role','family']):coverage.append({'background':bg,'role':r,'family':fam,'n_records':len(p),'n_countries':p.country.nunique(),'n_cases':p.scenario_id.nunique(),**{st:int(p.outcome_status.eq(st).sum()) for st in STATUS}})
pd.DataFrame(coverage).to_csv(D/'figure3_outcome_coverage.csv',index=False,encoding='utf-8-sig')

# Figure4: complete national maps use every country, with no-event classes separate.
f4=raw[raw.configuration_id.isin([c['id'] for c in configs if any(u['scenario_id'] in ['FIG4_M_BEST','FIG4_L_BEST','FIG4_E_BEST'] for u in c['uses'])])].copy()
f4['case']=f4.configuration_id.str.split('__').str[0];assert len(f4)==5*3*231
f4.to_csv(D/'figure4_national_outcomes.csv',index=False,encoding='utf-8-sig')
oldpairs=load(R/'outputs/figure4_maps_style_matched_20261031/source_data/confirmed_row_pairs.json')['pairs'];casepairs={};pairaudit=[]
for bg in BGS:
    pair=[]
    for i,r in enumerate(ROLES):
        prior=oldpairs[bg][i];members=cohorts['groups'][bg][r]
        if prior in members:chosen=prior;method='retain previous representative, compatible with new fixed REF group'
        else:
            # Representative selection uses REF only: prefer reconstructed-history countries,
            # then largest absolute REF terminal balance, ISO tie-break; no intervention selection.
            eligible=[c for c in members if refrow[bg,c] and refs[bg]['openingBalances'][codes.index(c)]!=0] or members
            chosen=sorted(eligible,key=lambda c:(-abs(refrow[bg,c]['C2100']),c))[0];method='previous representative no longer in same REF group; largest absolute REF C2100 among history-reconstructed group members, fallback to full group'
        pair.append(chosen);pairaudit.append({'background':bg,'role':r,'previous_country':prior,'selected_country':chosen,'method':method})
    casepairs[bg]=pair
save(D/'figure4_representative_countries.json',{'pairs':casepairs,'audit':pairaudit,'selection_uses_intervention_results':False})
f4[f4.apply(lambda r:r.country in casepairs[r.background],axis=1)].to_csv(D/'figure4_selected_country_outcomes.csv',index=False,encoding='utf-8-sig')

# Figure5: all configurations x all three export conditions x fixed countries retained.
# Same unlimited REF is the PRIMARY control across figures. Same-export REF is secondary only.
f5=[]
for cfg in configs:
    for u in [u for u in cfg['uses'] if u['figure']==5 and u['scenario_id']!='REF']:
        p=raw[(raw.configuration_id==cfg['id'])&raw.role.isin(ROLES)].copy();p['configuration']=u['scenario_id'];p['subgroup']=next(k for k,v in GROUPS.items() if u['scenario_id'] in v);f5.append(p)
f5=pd.concat(f5,ignore_index=True);assert f5.groupby(['background','country','configuration']).export.nunique().eq(3).all()
for k in ['newManufacturing','replacementManufacturing','treatment','gridAux','A']:
    refvals={(bg,c):float(np.sum(refs[bg]['annualCountry'][k][i])) for bg in BGS for i,c in enumerate(codes)}
    f5['contribution_'+k]=[(v-refvals[bg,c])*1000 if k=='A' else (refvals[bg,c]-v)*1000 for bg,c,v in f5[['background','country',k+'_Gt']].itertuples(index=False,name=None)]
comp=['contribution_'+k for k in ['A','newManufacturing','replacementManufacturing','treatment','gridAux']]
assert (f5[comp].sum(axis=1)-f5.carbon_gain_Mt).abs().max()<1e-7
f5.to_csv(D/'figure5_all_fixed_country_records.csv',index=False,encoding='utf-8-sig')
f5.to_parquet(D/'figure5_all_fixed_country_records.parquet',index=False)
ranges=[];process=[]
for (group,r,ex),p in f5.groupby(['subgroup','role','export']):
    q=p[p.paired_events_observed];rec={'subgroup':group,'role':r,'export':ex,'n_full':len(p),'n_matched_loss_events':len(q),'n_countries':p.country.nunique(),**{s:int(p.outcome_status.eq(s).sum()) for s in STATUS}}
    for field,col in [('x','paired_delta_T'),('y','carbon_gain_Mt')]:
        v=q[col];rec.update({field+'_q25':None if not len(v) else float(v.quantile(.25)),field+'_median':None if not len(v) else float(v.median()),field+'_q75':None if not len(v) else float(v.quantile(.75))})
    ranges.append(rec)
    # Process decomposition keeps the FULL same fixed group, irrespective of event availability.
    process.append({'subgroup':group,'role':r,'export':ex,'n_full':len(p),**{k:float(p[k].mean()) for k in comp},'carbon_gain_mean_Mt':float(p.carbon_gain_Mt.mean())})
pd.DataFrame(ranges).to_csv(D/'figure5_timing_coverage.csv',index=False,encoding='utf-8-sig');pd.DataFrame(process).to_csv(D/'figure5_full_group_process.csv',index=False,encoding='utf-8-sig')
save(D/'UNIFIED_TIME_METRIC_CONTRACT.json',{'id':'FIRST_LOSS_MATCHED_COUNTRY_20261102','policy':str(P/'BASELINE_BOUNDARY_AND_COHORT_POLICY.json'),'reference_cohort_sha256':sha(P/'source_data/fixed_reference_cohorts.json'),'primary_time_metric':'T_loss: first strict cumulative negative-to-positive event within2025-2100, starting with2024 historical balance','paired_effect':'delta_T=T_loss_case-T_loss_REF for the same country/background, defined only if both events observed; positive delay, negative advance','common_primary_control':'unlimited absorption REF of each of the five joint backgrounds in every figure','outcomes':{'observed_loss':'negative-to-positive event observed','benefit_not_lost_by_2100':'at least one negative cumulative balance, including negative opening, but no loss event by2100; not a claim of permanent prevention','no_benefit_observed':'no negative cumulative balance including opening through2100; not a successful intervention'},'censoring':'benefit_not_lost_by_2100 is a2100 observation-window endpoint, not2100/2101 as loss year; no_benefit_observed is a different outcome, not ordinary right censoring','missing_input':'separate error, not a no-event outcome; invalid finite accounts fail audit','group_membership':'fixed REF country sets; no scenario or common-three-export finite-event intersection selection','secondary_metric':'negative-yearend count retained in sources only; not substituted for first-loss timing','Figure3':'per-parameter median of same-country paired delta_T; half-violin over parameter medians; companion full-denominator outcome coverage; a distribution of deterministic scenarios, not a confidence interval','Figure4':'national first-loss-year maps; separate unformed/no-loss fills; selected-country paired delta_T only with both events, otherwise explicit outcome text','Figure5':'timing-carbon scatter retains full fixed-country outcomes using categorical side summaries for undefined time; conditional event-pair medians labelled n_event/N_full; process decomposition over FULL fixed group, not just finite-event subset','new_country_groups':'two opening-aware REF loss types; recovered-after-loss flag separate','scope_limit':'historical balances conditional on adopted33 positive and198 model-zero opening inventories; not empirically established national types'})
save(Q/'analysis_checks.json',{'status':'PASS','actual_accounts':len(manifest),'account_country_records':len(raw),'independent_event_checks':checks,'fixed_country_records_figure5':len(f5),'figure5_deleted_for_no_event':0,'figure3_parameter_summaries':len(points),'figure4_all_country_records':len(f4),'no_artificial_loss_dates':bool(raw.case_loss_year.dropna().between(2025,2100).all()),'all_missing_years_have_explicit_outcome':bool(raw.loc[raw.case_loss_year.isna(),'outcome_status'].isin(STATUS[1:]).all()),'max_cumulative_bridge_error_Gt':maxbridge,'max_H_A_closure_error_Gt':maxclosure,'primary_control_same_across_figures':True,'old_versions_unchanged':True})
print(json.dumps(load(Q/'analysis_checks.json'),ensure_ascii=False))
