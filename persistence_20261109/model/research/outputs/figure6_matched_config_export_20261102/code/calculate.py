"""Value exactly the Figure4/5 physical accounts; preserve registered price conditions."""
from pathlib import Path
import os,json,gzip,hashlib,shutil,itertools
import numpy as np
import pandas as pd

J=Path(__file__).resolve().parents[1];R=J.parents[1];D=J/'source_data';Q=J/'qa';O=J/'outputs'
SRC=R/'outputs/figures3_5_unified_time_metric_20261102';OLD=R/'outputs/figure6_device_technology_restored_20261102'
E=R/'outputs/economic_matched_billing_20261030';P=R/'outputs/opening_balance_reference_cohorts_20261102'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
unzip=lambda p:json.loads(gzip.decompress(Path(p).read_bytes()))
save=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
sources={}
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def protect(p):
 p=Path(p);sources[str(p)]=sha(p);return p
for k in ['CURRENT_FIGURE6_MAIN.json','CURRENT_FIGURE6_MAPS_COSTS.json']:
 if (R/k).exists():shutil.copyfile(R/k,Q/('before_'+k))
registry=read(protect(SRC/'source_data/configuration_registry.json'));manifest=read(protect(SRC/'source_data/account_manifest.json'))
lookup={(x['background'],x['configuration_id']):x for x in manifest}
frozen=read(protect(P/'source_data/frozen_inputs.json'));cohorts=read(protect(P/'source_data/fixed_reference_cohorts.json'))
base=read(protect(E/'source_data/base.json'));prices_raw=read(protect(E/'source_data/prices.json'));codes=base['codes'];n=231;T=76;years=np.arange(2025,2101)
prices={k:np.array([r[k] for r in prices_raw],float).reshape(n,T) for k in prices_raw[0] if isinstance(prices_raw[0][k],(float,int))}
buy,sell,dfc,dfo=[prices[k] for k in ['buy_price_usd_kwh','sell_price_usd_kwh','capital_discount_factor','operating_discount_factor']]
ILR=base['cost_normalisation']['PV_source_ILR'];sourceHours=base['cost_normalisation']['battery_source_duration_h']
oldfin=pd.read_csv(protect(R/'outputs/figure6_joint_baseline_maps_costs_20261031/source_data/all_231_country_financial_ledgers.csv'))
den=oldfin[(oldfin.configuration=='REF')&(oldfin['export']=='UNLIMITED')].set_index('country').loc[codes].denominator_MWh.to_numpy()
assert np.all(den>0)
TECH=['FIG4_M_BEST','FIG4_L_BEST','FIG4_E_BEST','FIG4_COMBINED']
STOR=['STORAGE_FC0','STORAGE_FC50','STORAGE_FC100','STORAGE_CAP_HALF','STORAGE_CAP_DOUBLE','STORAGE_K05','STORAGE_K1','STORAGE_K2','STORAGE_UTIL50','STORAGE_UTIL0']
EX=['UNLIMITED','CAP50','CAP0'];BG=['CP','NDC','B2C','NZ2050','LD']
labels=dict(zip(TECH+STOR,['制造改善M30†','寿命改善','运行改善','综合改善†','新增不配储','新增50%配储','新增100%配储','可用容量减半','可用容量加倍','每千瓦配0.5度','每千瓦配1度','每千瓦配2度','半数天运行','不充放电']))
roles={c:r for r,cs in cohorts['unions'].items() for c in cs}
assert not(set(cohorts['unions']['formed_then_lost'])&set(cohorts['unions']['opening_benefit_then_lost']))
sd={x['id']:x for x in registry};history={x['code']:x for x in frozen['history'] if x['case']=='CENTRAL'}
components=frozen['components'];index={c:i for i,c in enumerate(codes)}
jobcache={}
def pvjobs(p):
 key=p['module_years'],p['inverter_years']
 if key in jobcache:return jobcache[key]
 roof=np.zeros((n,T));electric=roof.copy();site=roof.copy()
 invs={x['cohort_id'].replace(':INVERTER:',':PV_MODULE_AND_LINKED_BOS:'):x for x in components if x['device']=='INVERTER'}
 for x in components:
  if x['device']!='PV_MODULE_AND_LINKED_BOS':continue
  inv=invs[x['cohort_id']];c=index[x['code']];m=np.zeros(T);v=np.zeros(T)
  for item,arr,life in [(x,m,p['module_years']),(inv,v,p['inverter_years'])]:
   first=int(np.floor(item['next_due_time']+1e-9))-2025
   if first<T:arr[max(0,first)::life]+=item['quantity']
  roof[c]+=m;electric[c]+=np.maximum(m,v);site[c]+=np.maximum(m,v)
 jobcache[key]=(roof,electric,site);return roof,electric,site
active_valuation=None
def parent_generation(a):
 return np.array(a['energyCountry']['generation']),*[np.asarray(active_valuation[k],float).reshape(n,T) for k in ['direct','night','stock']]
src=(R/'outputs/economic_native_aligned_20261030/code/calculate.py').read_text(encoding='utf-8-sig')
body='    e={k:None if v is None'+src.split('    e={k:None if v is None',1)[1].split('    finance_by[sid]=values',1)[0]
assert "q['legacyFirst']/.9" in body
body=body.replace("q['legacyFirst']/.9","q['legacyFirst']")
body=body.replace("    # Component quantities", "    np.testing.assert_allclose(roof,q['modRepl'],rtol=1e-10,atol=1e-5)\n    # Component quantities")
exec(compile('def value_account(a,q,sid):\n    p=a["parameters"];maxgen=maxenergy=0.\n'+body+'    return values,dict(new=first*dfc,replacement=(replacement+service)*dfc,retirement=retirement*dfc,OM=om*dfo,bill=variable_bill*dfo),dict(selfuse=selfuse,export=export),generror,err\n',str(J/'code/calculate.py')+'#registered_valuation','exec'),globals())
quant={};money={};raw=[];annuals={};extras={};max_energy=0.;max_closure=0.;max_carbon=0.
P_INV_L=.28/.22-1;P_INV_E=.25/.22-1
cases=['REF__UNLIMITED']+[s+'__UNLIMITED' for s in TECH]+[s+'__'+e for s in STOR for e in EX]
alignment=[]
for no,cid in enumerate(cases):
 cfg=sd[cid];sid=cid.split('__')[0];exp=cfg['selection']['exportConstraint'];fam='technology' if sid in TECH else 'storage_export' if sid in STOR else 'reference'
 p=cfg['parameters'];qp=J/'quantities'/(sid+'__UNLIMITED.json.gz')
 obj=quant.setdefault(sid,unzip(protect(qp)));assert obj['parameters']==p
 q={k:np.asarray(v,float).reshape(n,T) for k,v in obj['quantity'].items()};active_valuation=obj['valuation']
 rr=lookup['CP',cid];a=unzip(protect(rr['path']));assert sha(rr['path'])==rr['sha256'];assert a['parameters']==p and a['_codes']==codes
 v,an,flows,ge,ee=value_account(a,q,sid);max_energy=max(max_energy,ge,ee)
 # Preserve the existing independent engineering cost conditions.
 qn=[q['newPV']]*3+[q['newPV']/ILR,q['newBat_nominal'],q['newBat_nominal']*p['effective_DoD']/p['hours'],q['newHouse']/p['effective_DoD']]
 qr=[q['modRepl']]*3+[q['invRepl']/ILR,q['batRepl_nominal'],q['batRepl_nominal']*p['effective_DoD']/p['hours'],q['houseRepl']/p['effective_DoD']]
 keys=['pv_module_hw_usd_kwp','pv_sbos_hw_usd_kwp','pv_ebos_hw_usd_kwp','inv_hw_usd_kwac','battery_module_hw_usd_kwh_nom','bms_hw_usd_kw','case_hw_usd_kwh_nom_supported']
 hwn=sum(x*prices[k] for x,k in zip(qn,keys));hwr=sum(x*prices[k] for x,k in zip(qr,keys));ivn=qn[3]*prices[keys[3]];ivr=qr[3]*prices[keys[3]]
 hw=((hwn+hwr)*dfc).sum(axis=1)/den;inv=((ivn+ivr)*dfc).sum(axis=1)/den
 rM=.1 if sid in ['FIG4_M_BEST','FIG4_COMBINED'] else 0.
 rI=P_INV_L if sid in ['FIG4_L_BEST','FIG4_COMBINED'] else P_INV_E if sid=='FIG4_E_BEST' else 0.
 dn=(hwn*rM+ivn*rI*(1+rM))*dfc;dr=(hwr*rM+ivr*rI*(1+rM))*dfc
 v['new']+=dn.sum(axis=1);v['replacement']+=dr.sum(axis=1);v['NPC']+=dn.sum(axis=1)+dr.sum(axis=1)
 for key in ['NPC0','NPC1','NPC_combined_service','NPC0_combined_service','NPC1_combined_service']:v[key]+=dn.sum(axis=1)+dr.sum(axis=1)
 an['new']+=dn;an['replacement']+=dr
 np.testing.assert_allclose(v['NPC'],sum(v[k] for k in an),rtol=1e-12,atol=.01)
 if sid=='REF':ref=v
 dc=(v['NPC']-ref['NPC'])/den
 if sid in TECH:extras[sid]=dict(hw=hw,inv=inv,base=dc-rM*(hw+rI*inv),slope=hw+rI*inv)
 money[cid]=dict(delta=dc,values=v)
 variants=[(v[k]-ref[k])/den for k in ['NPC','NPC0','NPC1','NPC_combined_service','NPC0_combined_service','NPC1_combined_service']]
 envelope_low=np.minimum.reduce(variants);envelope_high=np.maximum.reduce(variants)
 np.savez_compressed(J/'annual'/(cid+'.npz'),**an,codes=np.asarray(codes),years=years,source_selfuse_kWh=flows['selfuse'],source_export_kWh=flows['export'],denominator_MWh=den)
 for i,c in enumerate(codes):
  comps={k+'_delta_USD_MWh':(v[k][i]-ref[k][i])/den[i] for k in an};max_closure=max(max_closure,abs(sum(comps.values())-dc[i]))
  raw.append(dict(configuration_id=cid,country=c,configuration=sid,export=exp,family=fam,delta_cost_USD_MWh=dc[i],denominator_MWh=den[i],**comps,**{k+'_USD2025':v[k][i] for k in ['NPC',*an]},hardware_exposure_USD_MWh=hw[i],inverter_exposure_USD_MWh=inv[i],M30_price_condition=rM,inverter_engineering_proxy=rI,allocation_service_condition_low_USD_MWh=envelope_low[i],allocation_service_condition_high_USD_MWh=envelope_high[i]))
 alignment.append(dict(configuration_id=cid,figure='4 + Extended Data' if sid in TECH else '5' if sid in STOR else 'REF',configuration=sid,export=exp,label=labels.get(sid,'参考持续配置'),parameters=p,source=rr['path'],source_sha256=rr['sha256'],quantity_source=str(qp),quantity_sha256=sha(qp),source_of_export='ANNUAL_ALLOCATION_PROXY' if exp=='UNLIMITED' else 'RECORDED_BOUNDED_EXPORT',legacy_first_unit='nominal kWh; no second DoD conversion'))
 print(json.dumps(dict(stage='priced',done=no+1,total=len(cases),configuration=cid,median=float(np.median(dc)))),flush=True)
F=pd.DataFrame(raw);F.to_csv(D/'financial_231_exact_configurations.csv',index=False,encoding='utf-8-sig');save(D/'scenario_crosswalk.json',alignment)
flat=[]
def eligible(re,ce,refC,caseC):
 tol=128*np.finfo(float).eps*max(1,abs(refC),abs(caseC));gain=refC-caseC
 rb=re['state']!='no_observed_benefit';cb=ce['state']!='no_observed_benefit';rl=re['first_loss_year'];cl=ce['first_loss_year']
 timeok=(not rb) or (cb and (cl is None if rl is None else cl is None or cl>=rl))
 return bool(gain>tol and timeok),bool(timeok),gain
for bg in BG:
 rr=lookup[bg,'REF__UNLIMITED'];refa=unzip(protect(rr['path']));assert sha(rr['path'])==rr['sha256']
 for cid in cases[1:]:
  row=lookup[bg,cid];a=unzip(protect(row['path']));assert sha(row['path'])==row['sha256']
  cp=unzip(lookup['CP',cid]['path']);assert a['parameters']==cp['parameters']
  for k in a['energyCountry']:
   if a['energyCountry'][k] is not None:np.testing.assert_allclose(a['energyCountry'][k],cp['energyCountry'][k],rtol=1e-12,atol=1e-3)
  sid=cid.split('__')[0];ex=cid.split('__')[1];v=money[cid]['values'];dc=money[cid]['delta']
  for i,c in enumerate(codes):
   re=refa['classifications'][i];ce=a['classifications'][i];assert re['code']==ce['code']==c
   refC=refa['countries']['C'][i][-1];caseC=a['countries']['C'][i][-1];ok,timeok,gain=eligible(re,ce,refC,caseC)
   max_carbon=max(max_carbon,max(abs(x-h+av) for x,h,av in zip(a['countries']['C'][i],a['countries']['H'][i],a['countries']['A'][i])))
   flat.append(dict(country=c,background=bg,configuration_id=cid,configuration=sid,export=ex,family='technology' if sid in TECH else 'storage_export',REF_union_state=roles.get(c,'other'),REF_state=re['state'],case_state=ce['state'],reference_loss_year=re['first_loss_year'],case_loss_year=ce['first_loss_year'],reference_C2100_Gt=refC,case_C2100_Gt=caseC,carbon_gain_Gt=gain,eligible=ok,loss_not_earlier=timeok,cost_reference_anchor_USD_MWh=dc[i],**{k+'_delta_USD_MWh':(v[k][i]-ref[k][i])/den[i] for k in ['new','replacement','retirement','OM','bill']},account_sha256=row['sha256']))
 print('Matched carbon and money '+bg,flush=True)
A=pd.DataFrame(flat);assert len(A)==34*5*231;A.to_csv(D/'all_country_background_candidates.csv',index=False,encoding='utf-8-sig')
selected=[]
for (c,bg,family),g in A.groupby(['country','background','family']):
 opts=g[g.eligible].to_dict('records')+[dict(country=c,background=bg,family=family,configuration_id='REF__UNLIMITED',configuration='REF',export='UNLIMITED',cost_reference_anchor_USD_MWh=0.,case_C2100_Gt=float(g.reference_C2100_Gt.iloc[0]))]
 w=min(opts,key=lambda x:(x['cost_reference_anchor_USD_MWh'],x['case_C2100_Gt'],x['configuration_id']));w['eligible_candidates']=int(g.eligible.sum());selected.append(w)
SEL=pd.DataFrame(selected);SEL.to_csv(D/'countrywise_selected_all_backgrounds.csv',index=False,encoding='utf-8-sig')
SEL.groupby(['background','family','configuration_id']).size().reset_index(name='countries').to_csv(D/'choice_counts.csv',index=False,encoding='utf-8-sig')
M=SEL[SEL.background=='NZ2050'].copy();M['map_value_USD_MWh']=M.cost_reference_anchor_USD_MWh;M.to_csv(D/'map_values.csv',index=False,encoding='utf-8-sig')
stats=[]
for bg in ['pooled',*BG]:
 for cid in cases[1:]:
  sid,ex=cid.split('__');g=F[F.configuration_id==cid].set_index('country')
  for role in ['formed_then_lost','opening_benefit_then_lost']:
   members=cohorts['unions'][role] if bg=='pooled' else cohorts['groups'][bg][role]
   vals=g.loc[members].delta_cost_USD_MWh.to_numpy();qt=np.quantile(vals,[.25,.5,.75])
   stats.append(dict(panel='c' if sid in TECH else 'd',background=bg,configuration_id=cid,configuration=sid,export=ex,label=labels[sid],role=role,n=len(vals),q25=qt[0],median=qt[1],q75=qt[2]))
S=pd.DataFrame(stats);S.to_csv(D/'bar_values_all_backgrounds.csv',index=False,encoding='utf-8-sig');S[S.background=='pooled'].to_csv(D/'plotted_bar_values.csv',index=False,encoding='utf-8-sig')
thresholds=[]
for i,c in enumerate(codes):
 m=extras['FIG4_M_BEST'];comparators={'REF':0.,'FIG4_L_BEST':money['FIG4_L_BEST__UNLIMITED']['delta'][i],'FIG4_E_BEST':money['FIG4_E_BEST__UNLIMITED']['delta'][i]}
 for target,cost in comparators.items():thresholds.append(dict(country=c,competitor=target,M30_extra_hardware_price_ceiling=(cost-m['base'][i])/m['slope'][i],scope='Conditional cost equality only; not a product quote or a guarantee of carbon eligibility'))
pd.DataFrame(thresholds).to_csv(D/'M30_current_cost_condition_thresholds.csv',index=False,encoding='utf-8-sig')
# Preserve all 54 registered price conditions, without mixing them into country IQR.
sens=[];counts=[]
for pm,pl,pe,mode in itertools.product([0.,.1,.2],[0.,.1,.2],[0.,.1,.2],['max','sum']):
 for bg in BG:
  costs=[np.zeros(n)];ids=['REF__UNLIMITED'];refcs=A[A.background==bg].groupby('country').reference_C2100_Gt.first().reindex(codes).to_numpy();cs=[refcs]
  for sid in TECH:
   z=A[(A.background==bg)&(A.configuration==sid)].set_index('country').loc[codes];x=extras[sid]
   if sid=='FIG4_M_BEST':u=x['base']+pm*x['slope']
   elif sid=='FIG4_L_BEST':u=x['base']+pl*x['hw']
   elif sid=='FIG4_E_BEST':u=x['base']+pe*x['hw']
   else:
    di=(P_INV_L+P_INV_E-max(P_INV_L,P_INV_E))*x['inv'] if mode=='sum' else np.zeros(n)
    u=x['base']+di+pm*(x['slope']+di)+max(pl,pe)*x['hw']
   costs.append(np.where(z.eligible.to_numpy(),u,np.inf));cs.append(z.case_C2100_Gt.to_numpy());ids.append(sid+'__UNLIMITED')
  costs=np.asarray(costs);cs=np.asarray(cs);best=np.array([min(range(5),key=lambda k:(costs[k,i],cs[k,i],ids[k])) for i in range(n)])
  for i,c in enumerate(codes):sens.append(dict(country=c,background=bg,M30_hardware_price_condition=pm,unpriced_life_premium=pl,unpriced_operation_premium=pe,joint_inverter_proxy=mode,selected_configuration_id=ids[best[i]],selected_cost_USD_MWh=costs[best[i],i]))
  for k in range(5):counts.append(dict(background=bg,M30_hardware_price_condition=pm,unpriced_life_premium=pl,unpriced_operation_premium=pe,joint_inverter_proxy=mode,configuration_id=ids[k],countries=int((best==k).sum())))
pd.DataFrame(sens).to_csv(D/'price_condition_sensitivity_country_choices.csv',index=False,encoding='utf-8-sig');pd.DataFrame(counts).to_csv(D/'price_condition_sensitivity_choice_counts.csv',index=False,encoding='utf-8-sig')
for name in ['price_condition_assumptions.json','source_register.json','部件工艺计价_逐值溯源表.csv','cost_method_source_register.json','cost_method_numeric_evidence.csv','本次价格条件_逐值登记.csv']:
 if (OLD/'source_data'/name).exists():shutil.copyfile(protect(OLD/'source_data'/name),D/name)
# The copied pricing assumptions are a source snapshot: their old sample size is superseded explicitly.
save(D/'current_sample_and_cost_boundary.json',dict(cohort_id=cohorts['id'],groups={k:len(cohorts['unions'][k]) for k in ['formed_then_lost','opening_benefit_then_lost']},monetary_years=[2025,2100],currency='2025 real USD',denominator='Unchanged fixed discounted common-service MWh by country',old_historical_capital='sunk, excluded; no manufacture-carbon-to-dollar conversion',price_paths='Existing country price and discount paths unchanged across NGFS',map_background='NZ2050',candidate_count=dict(technology=4,storage_export=30),source_snapshot_sample_counts_superseded=True))
save(D/'source_hashes.json',sources)
for p,h in sources.items():assert sha(p)==h,p
check=dict(status='PASS',countries=n,configurations_including_REF=len(cases),technical_cases=4,storage_configurations=10,export_conditions=EX,storage_export_combinations=30,country_financial_rows=len(F),country_background_candidates=len(A),price_sensitivity_rows=len(sens),source_country_counts={k:len(cohorts['unions'][k]) for k in ['formed_then_lost','opening_benefit_then_lost']},maximum_energy_error=max_energy,maximum_cash_closure_USD_MWh=max_closure,maximum_carbon_H_minus_A_error_Gt=max_carbon,map_background='NZ2050',map_range=[float(M.map_value_USD_MWh.min()),float(M.map_value_USD_MWh.max())],original_prices_and_accounts_unchanged=True)
assert max_energy<1e-10 and max_closure<1e-8 and max_carbon<1e-10
save(Q/'data_checks.json',check);print(json.dumps(check,ensure_ascii=False),flush=True)
