"""Independent account audit, documented boundary decision and frozen country lists."""
import os,json,gzip,hashlib,math,csv
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[4]
J=Path(__file__).resolve().parents[1];D=J/'source_data';O=J/'outputs';QA=J/'qa'
U=ROOT/'research';P=U/'outputs/baseline_replacement_package_20261031'
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
f=load(D/'frozen_inputs.json');reg=load(D/'fixed_reference_cohorts.json');old=load(D/'old_reference_cohorts_SNAPSHOT_NOT_ACTIVE.json')
allrows=load(D/'country_reference_classifications.json');hist=pd.DataFrame(f['history']);central=hist[hist['case']=='CENTRAL'].set_index('code');names={r['code']:r['country'] for r in f['opening']}
labels={'formed_then_lost':'期内形成收益后丧失','opening_benefit_then_lost':'期初已有收益后丧失','benefit_without_observed_loss':'有收益但观察期内未丧失','no_observed_benefit':'观察期内未出现收益'}
bgnames={'CP':'Current Policies','NDC':'NDCs','B2C':'Below 2°C','NZ2050':'Net Zero 2050','LD':'Low Demand'}
codes=list(names);years=list(range(2025,2101))

# Independent state oracle: enumerate strictly negative and later strictly positive years,
# rather than the JS streaming classifier. The2024 boundary can itself supply the negative state.
def oracle(B,C):
    v=[B]+list(C);positive=[i for i,x in enumerate(v) if x>0];negative=[i for i,x in enumerate(v) if x<0]
    losses=[i for i in positive if any(n<i for n in negative) and v[max(j for j in range(i) if v[j]!=0)]<0]
    loss=years[losses[0]-1] if losses else None
    if loss is not None:state='opening_benefit_then_lost' if B<0 else 'formed_then_lost'
    else:state='benefit_without_observed_loss' if negative else 'no_observed_benefit'
    return state,loss

summary=[];sens=[];unstable=[];year_sensitive=[];oldnew=[];status_checks=0;closure=0.;globalerr=0.;nearzero=[]
revaluation_cases=[c for c in hist['case'].unique() if c not in ['MEAN_AGE_ONLY','EARLIEST_BUCKET_10Y_OLDER']]
for record in reg['reference_accounts']:
    bg=record['background']
    with gzip.open(record['path'],'rt',encoding='utf-8') as ff:a=json.load(ff)
    assert a['_codes']==codes and a['selection']['roof']=='SSP2' and a['selection']['climateCoupling']=='PV_TW'
    assert a['selection']['storage']=='REF' and a['selection']['exportConstraint']=='UNLIMITED'
    assert sha(Path(record['path']))==record['sha256']
    for i,code in enumerate(codes):
        H=np.array(a['countries']['H'][i]);A=np.array(a['countries']['A'][i]);C=np.array(a['countries']['C'][i]);B=float(central.loc[code].opening_balance_Gt)
        assert np.all(np.isfinite(C))
        closure=max(closure,float(np.max(np.abs(C-(H-A)))))
        for t in range(76):
            expected=math.fsum([B]+a['annualCountry']['net'][i][:t+1]);assert math.isclose(C[t],expected,rel_tol=1e-11,abs_tol=2e-13)
        state,loss=oracle(B,C);cl=a['classifications'][i];assert state==cl['state'] and loss==cl['first_loss_year'];status_checks+=1
        assert code in reg['groups'][bg][state]
        ambiguous=np.where((np.abs(C)>0)&(np.abs(C)<=1e-12*np.maximum(np.maximum(np.abs(H),np.abs(A)),1e-30)))[0]
        nearzero.extend({'background':bg,'code':code,'year':years[t],'C':C[t]} for t in ambiguous)
    for k in ['H','A','C']:
        for t in range(76):globalerr=max(globalerr,abs(math.fsum(row[t] for row in a['countries'][k])-a['global'][k][t]))
        assert math.isclose(math.fsum(row[k][-1] for row in a['regions']),a['global'][k][-1],abs_tol=1e-11)
        assert math.isclose(math.fsum(row[k] for row in a['bubble']['regions']),a['global'][k][-1],abs_tol=1e-11)
    counts=a['trajectorySummary']['stateCounts'];rr={'background':bg,'background_name':bgnames[bg],**counts,'C2100_Gt':a['global']['C'][-1],'global_first_loss':a['events']['global']['first_loss_year']}
    for st in ['formed_then_lost','opening_benefit_then_lost']:
        rows=[cl for cl in a['classifications'] if cl['state']==st]
        rr[st+'_positive_2100']=sum(cl['positive_at_2100'] for cl in rows)
        rr[st+'_recovery_after_loss']=sum(cl['recovery_after_loss'] for cl in rows)
        rr[st+'_negative_2100']=sum(cl['recovered_at_2100'] for cl in rows)
        rr[st+'_zero_2100']=sum(cl['terminal_zero'] for cl in rows)
    summary.append(rr)
    # Historical valuation sensitivities share unchanged current vintages and future quantities.
    # Age-distribution alternatives MUST NOT be treated as opening-offset sensitivities.
    for case in revaluation_cases+['PERIOD_ONLY_DIAGNOSTIC','MANUFACTURE_ONLY_DEBT_STRESS']:
        lookup=hist[hist['case']==case].set_index('code') if case in revaluation_cases else central
        changes=[];cc={k:0 for k in labels};year_changes=[]
        for i,code in enumerate(codes):
            B=0. if case=='PERIOD_ONLY_DIAGNOSTIC' else float(lookup.loc[code].history_H_Gt) if case=='MANUFACTURE_ONLY_DEBT_STRESS' else float(lookup.loc[code].opening_balance_Gt)
            st,loss=oracle(B,np.array(a['periodCountries']['C'][i])+B);cc[st]+=1
            ref=a['classifications'][i]
            if st!=ref['state']:changes.append(code);unstable.append({'case':case,'background':bg,'code':code,'reference_state':ref['state'],'alternative_state':st,'alternative_first_loss_year':loss})
            if loss is not None and ref['first_loss_year'] is not None:
                delta=loss-ref['first_loss_year'];year_changes.append(delta)
                if abs(delta)>=5:year_sensitive.append({'case':case,'background':bg,'code':code,'reference_opening_balance_Gt':a['openingBalances'][i],'alternative_opening_balance_Gt':B,'reference_state':ref['state'],'alternative_state':st,'reference_first_loss_year':ref['first_loss_year'],'alternative_first_loss_year':loss,'year_change':delta})
        sens.append({'case':case,'background':bg,**cc,'changed_state_count':len(changes),'minimum_matched_year_change':min(year_changes) if year_changes else None,'maximum_matched_year_change':max(year_changes) if year_changes else None,'interpretation':'historical valuation only; unchanged future physical cohorts' if case in revaluation_cases else 'boundary stress diagnostic; not formal reference'})

assert closure<1e-10 and globalerr<1e-10 and len(nearzero)==0
df=pd.DataFrame(allrows);df['state_label']=df['state'].map(labels);df['events']=df['events'].map(lambda x:json.dumps(x,ensure_ascii=False));df.to_csv(D/'country_reference_classifications_231x5.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(summary).to_csv(D/'reference_group_counts.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(sens).to_csv(D/'historical_balance_sensitivity_counts.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(unstable).to_csv(D/'historical_balance_sensitive_membership.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(year_sensitive).to_csv(D/'historical_balance_sensitive_loss_years.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(f['opening']).to_csv(D/'opening_inventory_scope_snapshot.csv',index=False,encoding='utf-8-sig')
quality=[];history_subset={}
for bg in bgnames:
    history_subset[bg]={}
    for st in labels:
        rows=[r for r in allrows if r['background']==bg and r['state']==st]
        reconstructed=[r['code'] for r in rows if r['history_status']=='CONDITIONAL_CONTINUING_SITE_HISTORY']
        history_subset[bg][st]=reconstructed
        quality.append({'background':bg,'state':st,'full_model_group_n':len(rows),'reconstructed_history_n':len(reconstructed),'scenario_zero_history_n':sum(r['history_status']=='MODEL_ZERO_NOT_EMPIRICAL_HISTORY' for r in rows),'known_installed_but_zero_n':sum(r['known_zero_conflict'] is True for r in rows),'interpretation':'model-defined group; scenario zero does not demonstrate historical absence of PV or benefits'})
pd.DataFrame(quality).to_csv(D/'reference_cohort_history_quality.csv',index=False,encoding='utf-8-sig')
save(D/'history_reconstructed_33_subset_groups.json',{'purpose':'quality-stratified robustness only; not a replacement silently dropping198 countries','groups':history_subset})
countrylist=[]
for bg,groups in reg['groups'].items():
    for st,members in groups.items():
        for code in members:countrylist.append({'background':bg,'reference_group':st,'reference_group_zh':labels[st],'code':code,'country':names[code]})
pd.DataFrame(countrylist).to_csv(D/'fixed_country_lists.csv',index=False,encoding='utf-8-sig')

oldgroups=old.get('backgrounds',old.get('groups',old))
for bg in bgnames:
    prev=oldgroups[bg]
    for oldid,newid in [('strict','formed_then_lost'),('initial','opening_benefit_then_lost')]:
        value=prev[oldid];prevset=set(value if isinstance(value,list) else value.get('codes',value.get('members',[])));newset=set(reg['groups'][bg][newid])
        for code in sorted(prevset|newset):oldnew.append({'background':bg,'old_label':oldid,'new_label':newid,'code':code,'was_old_member':code in prevset,'is_new_member':code in newset,'warning':'boundary, initial chronology and terminal filter all differ; not a pure historical-offset effect'})
pd.DataFrame(oldnew).to_csv(D/'old_new_membership_reconciliation.csv',index=False,encoding='utf-8-sig')

freeze={
 'decision_id':reg['id'],'status':'FIVE_REF_RECOMPUTED_AND_COUNTRY_GROUPS_FROZEN_CONDITIONAL_HISTORY',
 'opening_boundary':{'date':'2024-12-31','primary':'matching historical burden minus matching historical avoided emissions of continuing installation sites represented by adopted2025 opening stock','not_claimed':'full history of all national rooftop PV installations','future_cumulative':'C_t=B_2024+sum_{2025..t}(H_y-A_y)','historical_emissions_booking':'occurred year; balance transfer only at2025; no repeat manufacture or lifetime amortisation','common_past':'identical historical inputs for all future backgrounds and interventions','alternative_accounts':['2025-onward period-only diagnostic','manufacture-only opening debt conservative stress test']},
 'reference_conditions':{'resolution':'native1km','IAM':'REMIND-MAgPIE3.3-4.8,NGFS PhaseV','roof':'SSP2','climate':'MPI-ESM1-2-LR SSP2-4.5 radiation+temperature+wind; PV_TW','storage':'unified LFP REF; national share; replacement continues','export':'complete absorption UNLIMITED reference; conditional rather than empirical grid acceptance','life':'module30,inverter15,cabinet20; LFP16.5calendar/6250cycle, reference annual interval17','opening_inventory':'adopted33 positive stocks and198 scenario-zero stocks;6 known installed/zero conflicts flagged; not observed zero'},
 'states':{'formed_then_lost':{'label':labels['formed_then_lost'],'rule':'B_2024>=0; at least one future C<0 followed by first future C>0'},'opening_benefit_then_lost':{'label':labels['opening_benefit_then_lost'],'rule':'B_2024<0; first future C>0; may occur in2025'},'mutually_exclusive':True,'exhaustive_of_observed_loss_events':True,'not_exhaustive_of_all_countries':True,'other_states':{k:labels[k] for k in ['benefit_without_observed_loss','no_observed_benefit']},'terminal_sign_separate':True,'zero_handling':'exact zeros carry no sign; bridge last nonzero; event in first subsequent strictly signed year','time_rule':'annual integer year of event; no interpolation or fake missing-event year'},
 'cohort_freeze':{'file':str(D/'fixed_reference_cohorts.json'),'sha256':sha(D/'fixed_reference_cohorts.json'),'membership':'background-specific REF, immutable across interventions, roof/climate sensitivities and resolution checks','all_country_overview':'all231 unchanged; missing historical observations stay quality flags','cross_model_robustness':'use REMIND frozen countries for controlled matched-country test; separately labelled model-own REF classification may be added but not mixed','economic_pooled_figures':'deduplicated union of background-specific REF members; one country one vote; cost availability explicitly audited without refilling missing prices','pooled_union_counts':{k:len(v) for k,v in reg['unions'].items()},'future_versions':'input/boundary changes require a versioned full REF rerun; never silently overwrite member lists'},
 'historical_interpretation_guard':{'warning':'The two groups are model-defined within the adopted opening inventory. Model-zero history does not establish absence of historic generation or benefits. Do not infer an empirical causal distinction between the two groups from these counts.','history_quality_file':str(D/'reference_cohort_history_quality.csv'),'quality_stratified_robustness':str(D/'history_reconstructed_33_subset_groups.json')},
 'figure_application':{'Fig2':'all231; continuous balance and opening-aware event classification','Fig3':'within-background fixed two REF cohorts; parameters cannot reselect event-only countries','Fig4':'same two REF cohorts; same countries for all technology comparisons','Fig5':'same two REF cohorts; same countries for all storage/export comparisons','Fig6':'same fixed groups or expressly declared deduplicated unions; future cashflow re-estimated from new quantities; historical burden is not2025 expenditure','statistics':'retain missing-event states and denominators; year medians only conditional on observed events, with event count; compare event-state changes before matched year shifts'},
 'execution_scope':{'REF_backgrounds_recomputed':5,'all_interventions_recomputed':False,'old_figures_overwritten':False,'main_figure_pointers_switched':False,'next_required':'fractional old/new technology operation and future scenario replay before updating figures and economics'},
 'sources':f['references'],'input_hashes':f['source_hashes']}
save(J/'BASELINE_BOUNDARY_AND_COHORT_POLICY.json',freeze)
save(QA/'independent_audit.json',{'status':'PASS','state_oracle_comparisons':status_checks,'maximum_H_A_identity_error_Gt':closure,'maximum_global_sum_error_Gt':globalerr,'relative_roundoff_near_zero_records':len(nearzero),'history_revaluation_cases_with_unchanged_future':revaluation_cases,'age_change_cases_excluded_from_offset_audit':['MEAN_AGE_ONLY','EARLIEST_BUCKET_10Y_OLDER'],'frozen_source_hashes_verified':all(sha(Path(p))==h for p,h in f['source_hashes'].items()),'reference_account_hashes_verified':True})

lines=['# 期初历史余额、两类收益丧失轨迹与固定参考国家组','',
'本次已确定核算口径，并实际重算五个联合背景的1 km参考配置。以下名单基于同口径历史—未来账户，不是把历史余额直接叠加到旧情景曲线上得到的名单。原图及其入口未改动，干预情景与经济核算尚需按新账户重算。','',
'**期初余额。** 截至2024年末，将同一组安装场所及部件的历史制造、更换、所选处置和运行负担，与其历史发电避免排放匹配，净余额结转至2025年。历史制造按发生年入账，2025年不再重复计入，也不按剩余寿命均摊。2025—2100的逐年增量另保留，供识别历史起点的作用。','',
'当前数据支持的是“2025期初存量所代表的持续安装场所的条件历史”，不是全部国家屋顶光伏产业的完整历史。主方案保持33国正库存、198国模型零以隔离本次口径调整；已有安装但输入仍为零的6国继续单列，不把模型零称为实际无装机。任何库存扩展须另立版本并重新生成名单。','',
'**解释边界：这套名单是模型参考组，不是已经核实的国家实际历史类型。** 尤其“期内形成收益后丧失”组多数来自期初库存模型零；不能把两组经济或碳结果差异直接归因于真实的历史收益形成机制。已另存33国历史可重建子集用于分层核查，不静默删除其余198国。','',
'**两类轨迹。**','',
'|名称|确定标准|','|---|---|',
'|期内形成收益后丧失|2024年末余额≥0；2025年后先出现累计净排放<0，随后出现累计净排放>0|',
'|期初已有收益后丧失|2024年末余额<0；2025—2100首次出现累计净排放>0，可发生于2025年|','',
'两类互斥，涵盖观察期内发生收益丧失的国家；其余国家归为“有收益但观察期内未丧失”或“观察期内未出现收益”。不再以2025首个年末为期初判断依据，避免把2025年内刚形成的收益误称为历史已有收益。旧称“收益仅丧失”建议停用。','',
'首次负→正是收益丧失事件；此后是否再次转负、2100年的符号分别登记。不能把“曾经丧失”直接写成永久失效。零值年不强行赋予正负号；年份按首次满足相应严格符号的年末记录，不以2100或2101补缺失年份。','',
'**固定参考条件。** 1 km、REMIND–MAgPIE3.3–4.8、SSP2屋顶、MPI-ESM1-2-LR SSP2-4.5辐射＋气温＋风速、统一LFP参考、国别配储比例、参考寿命、持续续换、完全消纳。五条NGFS路径分别匹配使用端电网和制造供应地供电，过去的历史余额共同不变。','',
'|联合背景|期内形成收益后丧失|期初已有收益后丧失|其中2100仍为正：前类／后类|全球首次收益丧失年|','|---|---:|---:|---:|---:|']
for r in summary:
    yr=r['global_first_loss'] or '未发生'
    lines.append(f"|{r['background_name']}|{r['formed_then_lost']}|{r['opening_benefit_then_lost']}|{r['formed_then_lost_positive_2100']}／{r['opening_benefit_then_lost_positive_2100']}|{yr}|")
lines+=['', '**成员固定规则。** 每条背景只用REF确定成员。图3—图5中同一背景的技术、储能、外送、屋顶和气候对照全部使用同一名单；发生新事件或被干预阻止事件，只改变结果列，不改变分母。图2全球、区域与国家概览保留全部231国。图6若跨背景合并，采用明确登记的去重并集，按国家一票；不得重复计入同一国家。跨模型或分辨率稳健性比较沿用这些参考名单。','',
f"五背景去重并集：期内形成收益后丧失 {len(reg['unions']['formed_then_lost'])} 国，期初已有收益后丧失 {len(reg['unions']['opening_benefit_then_lost'])} 国，两组无重叠。不同背景各自的名单可以不同；若要把背景差异解释为同一批国家的政策效应，须使用明确的共同组，不能直接比较成员不同的组中位数。",'',
'**数字的依据与限制。** 主历史余额合计约−0.870 Gt CO₂e，23国为负、10国为正、198国为模型零。这是历史余额符号数，不等于未来收益丧失国家数。历史年度部署有直接序列及总PV路径补估两类，制造供应地和历史非电过程存在已登记转用假设，历史天气未被伪称为未来SSP天气。', '',
'**敏感性与质量核对。** 独立逐部件续换链核对实际未来制造/处置量；独立Python事件枚举与JS流式判定核对1155条国家—背景记录；检查累计闭合、全球和区域汇总、电量守恒和相对舍入误差附近的跨零记录。历史强度/发电估值敏感性只改变历史估值，固定同一未来队列；均龄和早期批次调整会改变未来事件，未将它们伪装成余额平移检验。具体成员变化见源表。', '',
'**与旧版的差异。** 本次同时修正历史起点、部件年龄续换、期初电池名义/可用容量和首次处置量，并将“2100仍为正”从事件分类条件中拆出。新旧名单变化不能全归因于历史余额一项。旧名单仅作快照保留。','',
'**方法依据。** IEA-PVPS生命周期指南要求明确研究目标和匹配的边界，没有规定任意模拟期初只能迁入制造碳债；Louwen等（2016）提供历史历年投入与发电避免排放匹配累计的全球光伏先例。本研究“持续安装场所”的数据边界及代表来源回溯属于明示建模选择，不能冒称文献要求或完整历史实测。','',
'- IEA-PVPS (2020), Methodology Guidelines on Life Cycle Assessment of Photovoltaic Electricity, 4th ed., §§3.2.1,3.5.3: https://iea-pvps.org/wp-content/uploads/2020/07/IEA_Task12_LCA_Guidelines.pdf',
'- Louwen et al. (2016), Nature Communications 7:13728: https://www.nature.com/articles/ncomms13728','',
'**主要文件。** `BASELINE_BOUNDARY_AND_COHORT_POLICY.json`为规则；`source_data/fixed_reference_cohorts.json`为冻结名单及账户哈希；`fixed_country_lists.csv`可直接查国家；`country_reference_classifications_231x5.csv`包含全部国家状态、历史质量和事件；`reference_group_counts.csv`为数量；`historical_balance_sensitive_membership.csv`为历史估值敏感成员；`qa/`为运行与独立审核。','',
'## 五背景的完整两类参考国家名单','']
for bg in bgnames:
    lines.append('**'+bgnames[bg]+'**');lines.append('')
    for st in ['formed_then_lost','opening_benefit_then_lost']:
        members=reg['groups'][bg][st];lines.append(f"{labels[st]}（{len(members)}国）："+'、'.join(f'{c} {names[c]}' for c in members)+'。');lines.append('')
(O/'期初历史余额与参考国家组_定稿口径.md').write_text('\n'.join(lines),encoding='utf-8')
register={'status':freeze['status'],'decision_id':reg['id'],'date':'2026-11-02','policy':str(J/'BASELINE_BOUNDARY_AND_COHORT_POLICY.json'),'reference_cohorts':str(D/'fixed_reference_cohorts.json'),'cohort_sha256':sha(D/'fixed_reference_cohorts.json'),'country_lists_csv':str(D/'fixed_country_lists.csv'),'report':str(O/'期初历史余额与参考国家组_定稿口径.md'),'REF_accounts':str(D/'account_manifest.json'),'all_intervention_scenarios_recomputed':False,'current_main_figures_not_yet_migrated':True}
save(U/'CURRENT_OPENING_BALANCE_POLICY.json',register);save(U/'CURRENT_REFERENCE_COUNTRY_COHORTS.json',register)
save(QA/'freeze_manifest.json',{'decision_id':reg['id'],'files':{str(p):sha(p) for p in [J/'BASELINE_BOUNDARY_AND_COHORT_POLICY.json',D/'fixed_reference_cohorts.json',D/'fixed_country_lists.csv',D/'country_reference_classifications_231x5.csv']}})
print(json.dumps({'status':'PASS','reference_counts':summary,'union_counts':freeze['cohort_freeze']['pooled_union_counts'],'reference_classifications':status_checks,'sources_verified':True,'opening_scope':{'negative':int((central.opening_balance_Gt<0).sum()),'positive':int((central.opening_balance_Gt>0).sum()),'model_zero':int((central.opening_balance_Gt==0).sum())}},ensure_ascii=False))
