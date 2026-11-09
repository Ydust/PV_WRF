"""Restore all device-technology contrasts using explicit price conditions.

The 10% M30 hardware price condition is an author stress-test middle case,
not a product quote, nor a consequence of the 30% carbon target.
"""
from pathlib import Path
import os,sys,json,gzip,hashlib,math,shutil
import numpy as np
import pandas as pd

JOB=Path(__file__).resolve().parents[1];R=JOB.parents[1]
OLD=R/'outputs/economic_native_aligned_20261030/code/calculate.py'
source=OLD.read_text(encoding='utf-8-sig');prefix=source.split("BGS=['CP'")[0]
exec(compile(prefix,str(OLD),'exec'),globals())
body="    e={k:None if v is None"+source.split("    e={k:None if v is None",1)[1].split("    finance_by[sid]=values",1)[0]
exec(compile("def value_account(a,q,sid):\n    p=a['parameters']\n    maxgen=maxenergy=0.\n"+body+"    return values,dict(new=first*dfc,replacement=(replacement+service)*dfc,retirement=retirement*dfc,OM=om*dfo,bill=variable_bill*dfo),generror,err\n",str(OLD)+'#existing_valuation','exec'),globals())
J=JOB;D=J/'source_data';Q=J/'qa';OUT=J/'outputs'
B=R/'outputs/figure6_joint_baseline_maps_costs_20261031';P6=R/'outputs/figure6_component_process_repricing_20261031';M6=R/'outputs/figure6_M30_redraw_20261102'
BG=['CP','NDC','B2C','NZ2050','LD'];TECH=['FIG4_M_BEST','FIG4_L_BEST','FIG4_E_BEST','FIG4_COMBINED'];PP=.1
save=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
for name in ['CURRENT_FIGURE6_MAIN.json','CURRENT_FIGURE6_MAPS_COSTS.json','CURRENT_M30_FIGURE4_FIGURE6_ALIGNMENT.json']:
 shutil.copyfile(R/name,Q/('before_'+name));protect(R/name)
oldprotected={str(f):sha(f) for root in [M6,R/'outputs/figure4_maps_style_matched_20261031'] for f in (root/'outputs').glob('*') if f.is_file()}
save(Q/'protected_legacy_figures.json',oldprotected)
fm=read(protect(R/'outputs/figure4_maps_style_matched_20261031/source_data/account_manifest.json'))
cm=read(protect(D/'combined_account_manifest.json'))
acc={}
for x in fm:
 p=protect(x['account']);assert sha(p)==x['sha256'];acc[x['scenario_id'],x['background']]=unzip(p)
for x in cm:
 p=protect(x['path']);assert sha(p)==x['sha256'];acc[x['configuration'],x['background']]=unzip(p)
refmoney=pd.read_csv(protect(B/'source_data/all_231_country_financial_ledgers.csv')).set_index(['configuration','export','country']).sort_index()
den=refmoney.loc[('REF','UNLIMITED')].loc[codes].denominator_MWh.to_numpy()
refval=refmoney.loc[('REF','UNLIMITED')].loc[codes]
COHORT=read(protect(B/'source_data/pooled_fixed_cohorts.json'));roles={c:k for k,cs in COHORT.items() for c in cs};save(D/'pooled_fixed_cohorts.json',COHORT)
priorA=pd.read_csv(protect(P6/'source_data/all_country_background_candidates.csv'),low_memory=False)
existingL=priorA[priorA.configuration.isin(['FIG4_L_BEST','FIG4_E_BEST'])].set_index(['configuration','background','country'])
P_INV_L=.28/.22-1;P_INV_E=.25/.22-1
jointINV=max(P_INV_L,P_INV_E)
money={};extra={};raw=[];allrows=[];maxge=maxee=0.;pairerr=0.
def ev(C):
 neg=np.flatnonzero(C<0);first=int(neg[0]) if len(neg) else 1000
 losses=np.flatnonzero((np.arange(76)>first)&(C>0))
 return dict(C2100=float(C[-1]),first_negative_year=None if first==1000 else int(2025+first),loss_year=None if not len(losses) else int(2025+losses[0]))
def eligible(re,ce):
 tol=128*np.finfo(float).eps*max(1,abs(re['C2100']),abs(ce['C2100']))
 ok=True if re['first_negative_year'] is None else (ce['first_negative_year'] is not None and (ce['loss_year'] is None if re['loss_year'] is None else ce['loss_year'] is None or ce['loss_year']>=re['loss_year']))
 gain=re['C2100']-ce['C2100'];return gain,bool(gain>tol and ok),bool(ok)
for sid in TECH:
 a=acc[sid,'CP'];obj=unzip(protect((J if sid=='FIG4_COMBINED' else B)/f'quantities/{sid}.json.gz'))
 assert obj['parameters']==a['parameters'];q={k:np.asarray(v,float).reshape(n,T) for k,v in obj['quantity'].items()}
 val,an,ge,ee=value_account(a,q,sid);maxge=max(maxge,ge);maxee=max(maxee,ee)
 pp=a['parameters'];PKEYS=['pv_module_hw_usd_kwp','pv_sbos_hw_usd_kwp','pv_ebos_hw_usd_kwp','inv_hw_usd_kwac','battery_module_hw_usd_kwh_nom','bms_hw_usd_kw','case_hw_usd_kwh_nom_supported']
 qn=[q['newPV']]*3+[q['newPV']/ILR,q['newBat_nominal'],q['newBat_nominal']*pp['effective_DoD']/pp['hours'],q['newHouse']/pp['effective_DoD']]
 qr=[q['modRepl']]*3+[q['invRepl']/ILR,q['batRepl_nominal'],q['batRepl_nominal']*pp['effective_DoD']/pp['hours'],q['houseRepl']/pp['effective_DoD']]
 hwn=sum(v*prices[k] for v,k in zip(qn,PKEYS));hwr=sum(v*prices[k] for v,k in zip(qr,PKEYS));invn=qn[3]*prices[PKEYS[3]];invr=qr[3]*prices[PKEYS[3]]
 np.testing.assert_allclose(((hwn+hwr)*dfc).sum(axis=1),val['affected'],rtol=1e-12,atol=.01)
 rI=P_INV_L if sid=='FIG4_L_BEST' else P_INV_E if sid=='FIG4_E_BEST' else jointINV if sid=='FIG4_COMBINED' else 0.
 rM=PP if sid in ['FIG4_M_BEST','FIG4_COMBINED'] else 0.
 dn=(hwn*rM+invn*rI*(1+rM))*dfc;dr=(hwr*rM+invr*rI*(1+rM))*dfc
 priced={k:v.copy() for k,v in val.items()};priced['new']+=dn.sum(axis=1);priced['replacement']+=dr.sum(axis=1);priced['NPC']+=dn.sum(axis=1)+dr.sum(axis=1)
 dc=(priced['NPC']-refval.NPC.to_numpy())/den
 invE=((invn+invr)*dfc).sum(axis=1)/den;hwE=val['affected']/den
 # A base cost without the unknown M30 manufacturing premium. L/E already
 # include their part-specific JRC engineering proxy; combined uses one
 # inverter premium, max(L,E), with a sum(L,E) sensitivity below.
 basecost=(val['NPC']-refval.NPC.to_numpy())/den+rI*invE
 slope=hwE+rI*invE
 money[sid]=dc;extra[sid]=dict(base=basecost,hw=hwE,inv=invE,rI=rI,slope=slope)
 np.testing.assert_allclose(dc,basecost+rM*slope,rtol=1e-11,atol=1e-9)
 np.savez_compressed(J/'annual'/f'{sid}__priced.npz',new=an['new']+dn,replacement=an['replacement']+dr,retirement=an['retirement'],OM=an['OM'],bill=an['bill'],codes=np.asarray(codes),years=years)
 for i,c in enumerate(codes):
  raw.append(dict(configuration=sid,country=c,denominator_MWh=den[i],base_delta_cost_USD_MWh=basecost[i],main_delta_cost_USD_MWh=dc[i],hardware_exposure_USD_MWh=hwE[i],inverter_exposure_USD_MWh=invE[i],M30_premium_slope_USD_MWh=slope[i],inverter_engineering_proxy=rI,M30_main_price_condition=rM,M30_actual_implementation_quote=np.nan,**{k:float(priced[k][i]) for k in ['NPC','new','replacement','retirement','OM','bill']}))
 for bg in BG:
  ca,ra=acc[sid,bg],acc['REF',bg]
  for k in ['generation','useful','gridAux','discharge','curtailment']:np.testing.assert_allclose(ca['energyCountry'][k],a['energyCountry'][k],rtol=1e-12,atol=1e-3)
  for i,c in enumerate(codes):
   re,ce=ev(np.asarray(ra['countries']['C'][i])),ev(np.asarray(ca['countries']['C'][i]));gain,ok,timeok=eligible(re,ce)
   comp={k+'_delta_USD_MWh':(priced[k][i]-refval.loc[c,k])/den[i] for k in ['new','replacement','retirement','OM','bill']}
   assert abs(sum(comp.values())-dc[i])<1e-8
   row=dict(country=c,background=bg,family='technology',configuration=sid,export='UNLIMITED',REF_state=roles.get(c,'other'),reference_C2100_Gt=re['C2100'],case_C2100_Gt=ce['C2100'],carbon_gain_Gt=gain,reference_loss_year=re['loss_year'],case_loss_year=ce['loss_year'],eligible=ok,loss_not_earlier=timeok,cost_reference_anchor_USD_MWh=dc[i],price_status='CONDITIONAL_ENGINEERING_PRICE_NOT_MARKET_QUOTE',M30_price_condition=rM,M30_actual_quote=np.nan,**comp)
   if sid in ['FIG4_L_BEST','FIG4_E_BEST']:
    old=existingL.loc[(sid,bg,c)];pairerr=max(pairerr,abs(old.cost_reference_anchor_USD_MWh-dc[i]));assert bool(old.eligible)==ok;assert abs(old.case_C2100_Gt-ce['C2100'])<1e-11
   allrows.append(row)
 print(json.dumps(dict(stage='four-technology-pricing',configuration=sid,median=float(np.median(dc)),min=float(dc.min()),max=float(dc.max()))),flush=True)
assert pairerr<1e-7
pd.DataFrame(raw).to_csv(D/'technology_price_decomposition_231.csv',index=False,encoding='utf-8-sig')
A=pd.DataFrame(allrows);storage=priorA[(priorA.family=='storage_export')&(priorA['export']=='UNLIMITED')].copy();storage['REF_state']=storage.country.map(roles).fillna('other')
A=pd.concat([A,storage],ignore_index=True);A.to_csv(D/'all_country_background_candidates.csv',index=False,encoding='utf-8-sig')
selected=[]
for (country,bg,family),g in A.groupby(['country','background','family']):
 valid=g[g.eligible].copy();eligibleN=len(valid)
 refC=float(g.reference_C2100_Gt.iloc[0]);ref=dict(country=country,background=bg,family=family,configuration='REF',cost_reference_anchor_USD_MWh=0.,case_C2100_Gt=refC,REF_state=roles.get(country,'other'))
 options=valid.to_dict('records')+[ref]
 z=min(options,key=lambda x:(x['cost_reference_anchor_USD_MWh'],x['case_C2100_Gt'],x['configuration']));z.update(eligible_candidates=eligibleN,selection_status='LEAST_CONDITIONAL_COST_WITH_CARBON_AND_NO_EARLIER_LOSS_GATE');selected.append(z)
SEL=pd.DataFrame(selected);SEL.to_csv(D/'countrywise_selected_all_backgrounds.csv',index=False,encoding='utf-8-sig')
counts=SEL.groupby(['background','family','configuration']).size().reset_index(name='countries');counts.to_csv(D/'choice_counts.csv',index=False,encoding='utf-8-sig')
same=all(g.configuration.nunique()==1 and g.cost_reference_anchor_USD_MWh.max()-g.cost_reference_anchor_USD_MWh.min()<1e-9 for _,g in SEL.groupby(['country','family']))
mapbg='CP' if same else 'NZ2050';MAP=SEL[SEL.background==mapbg].copy();MAP['map_value_USD_MWh']=MAP.cost_reference_anchor_USD_MWh;MAP['metric']='conditional_incremental_cost';assert len(MAP)==462
assert MAP.map_value_USD_MWh.max()<1e-8
MAP.to_csv(D/'map_values.csv',index=False,encoding='utf-8-sig')
stats=[];details=[]
specs=[('c','FIG4_M_BEST','制造改善M30†'),('c','FIG4_L_BEST','寿命改善'),('c','FIG4_E_BEST','运行改善'),('c','FIG4_COMBINED','综合改善†'),('d','STORAGE_FC0','新增不配储'),('d','STORAGE_CAP_HALF','可用容量减半'),('d','STORAGE_K05','每千瓦配0.5度')]
for panel,sid,label in specs:
 g=A[(A.background==mapbg)&(A.configuration==sid)]
 for role in ['strict','initial']:
  gg=g[g.REF_state==role];assert len(gg)==len(COHORT[role]);vals=gg.cost_reference_anchor_USD_MWh.to_numpy();qt=np.quantile(vals,[.25,.5,.75])
  stats.append(dict(panel=panel,configuration=sid,label=label,role=role,n=len(vals),q25=qt[0],median=qt[1],q75=qt[2]))
  for z in gg.to_dict('records'):details.append(dict(**z,displayed_panel=panel,displayed_row=sid,value_USD_MWh=z['cost_reference_anchor_USD_MWh']))
pd.DataFrame(stats).to_csv(D/'plotted_bar_values.csv',index=False,encoding='utf-8-sig');pd.DataFrame(details).to_csv(D/'plotted_country_values.csv',index=False,encoding='utf-8-sig')
sens=[];senscounts=[]
AI=A[A.family=='technology'].set_index(['country','background','configuration'])
# Existing 0/10/20% unpriced-hardware stress-test grid. These are author
# price conditions, not source quotes. The combined inverter may require
# max(L,E) or sum(L,E); both are inspected without double-counting equipment.
for pm in [0.,.1,.2]:
 for pl in [0.,.1,.2]:
  for pe in [0.,.1,.2]:
   for jointmode in ['max','sum']:
    for bg in BG:
     tally={}
     for i,c in enumerate(codes):
      opts=[('REF',0.,float(AI.loc[(c,bg,'FIG4_M_BEST'),'reference_C2100_Gt']))]
      for sid in TECH:
       z=AI.loc[(c,bg,sid)];x=extra[sid];basev=x['base'][i]
       if sid=='FIG4_M_BEST':u=basev+pm*x['slope'][i]
       elif sid=='FIG4_L_BEST':u=basev+pl*x['hw'][i]
       elif sid=='FIG4_E_BEST':u=basev+pe*x['hw'][i]
       else:
        di=(P_INV_L+P_INV_E-jointINV)*x['inv'][i] if jointmode=='sum' else 0.
        u=basev+di+pm*(x['slope'][i]+di)+max(pl,pe)*x['hw'][i]
       if z.eligible:opts.append((sid,u,z.case_C2100_Gt))
      w=min(opts,key=lambda x:(x[1],x[2],x[0]));tally[w[0]]=tally.get(w[0],0)+1
      sens.append(dict(country=c,background=bg,M30_hardware_price_condition=pm,unpriced_life_premium=pl,unpriced_operation_premium=pe,joint_inverter_proxy=jointmode,selected_configuration=w[0],selected_cost_USD_MWh=w[1]))
     for sid,nn in tally.items():senscounts.append(dict(background=bg,M30_hardware_price_condition=pm,unpriced_life_premium=pl,unpriced_operation_premium=pe,joint_inverter_proxy=jointmode,configuration=sid,countries=nn))
pd.DataFrame(sens).to_csv(D/'price_condition_sensitivity_country_choices.csv',index=False,encoding='utf-8-sig');pd.DataFrame(senscounts).to_csv(D/'price_condition_sensitivity_choice_counts.csv',index=False,encoding='utf-8-sig')
sensdf=pd.DataFrame(sens);maincond=sensdf[(sensdf.M30_hardware_price_condition==PP)&(sensdf.unpriced_life_premium==0)&(sensdf.unpriced_operation_premium==0)&(sensdf.joint_inverter_proxy=='max')]
join=SEL[SEL.family=='technology'].merge(maincond,on=['country','background'],validate='one_to_one');assert (join.configuration==join.selected_configuration).all();np.testing.assert_allclose(join.cost_reference_anchor_USD_MWh,join.selected_cost_USD_MWh,atol=1e-8)
for src in ['source_register.json','combined_value_register.json','部件工艺计价_逐值溯源表.csv']:
 shutil.copyfile(P6/'source_data'/src,D/src)
save(D/'price_condition_assumptions.json',[
 {'id':'P_M30','value':.1,'range':[0,.1,.2],'scope':'新增/更换受M30影响的七类制造硬件采购价差','status':'AUTHOR_PRICE_CONDITION_NOT_QUOTE','reason':'沿用已登记0/10/20%技术溢价压力测试网格，取中间档作明确条件展示，真实M30报价仍未知；非由30%减碳率推出10%成本。','method_sources':['10.1002/pip.3305','10.1039/D3SE00828B'],'source_of_numeric_grid':'既有price_sensitivity_choice_counts.csv/competitor_price_condition_sensitivity.csv的作者敏感性网格，不是上述论文的M30实测值'},
 {'id':'P_LE','scope':'L/E逆变器新增与更换','values':{'durability_relative':P_INV_L,'efficiency_relative':P_INV_E},'source':'JRC Task6 Table6, 0.22/0.28/0.25 EUR/VA','status':'PARTIAL_ENGINEERING_TRANSFER','limit':'历史设计比价；不是现有确定寿命或99%目标的完全匹配报价；其余额外硬件0/10/20%条件另检验'},
 {'id':'P_COMB','value':jointINV,'sensitivity_upper':P_INV_L+P_INV_E,'scope':'同一台逆变器同时改善耐久与效率','status':'AUTHOR_JOINT_COST_PROXY','reason':'主条件采用较高单项比价，避免把同一硬件当成两台重复收费；上限采用两项增量之和另检验。M30价差与该改造价差按同件硬件复合；物理事件联合重算。'},
 {'id':'SAMPLES','strict':113,'initial':66,'status':'FIXED_REF_COHORT_UNIONS','uncertainty':'国别中位数及Q25-Q75；价格条件不混入误差线'},
 {'id':'NO_QUOTE','status':'M30实际报价保持空；不宣称市场全局最优；所有主图成本均为条件工程估算'}])
save(D/'source_hashes.json',sources)
check=dict(status='PASS',countries=231,technology_country_background_rows=4620,combined_joint_accounts=5,source_country_counts={k:len(v) for k,v in COHORT.items()},main_M30_hardware_price_condition=PP,all_five_choices_identical=same,map_background=mapbg,maximum_generation_replay_relative_error=maxge,maximum_energy_closure_relative_error=maxee,maximum_L_E_cost_replay_error_USD_MWh=pairerr,map_value_range=[float(MAP.map_value_USD_MWh.min()),float(MAP.map_value_USD_MWh.max())],technology_choices=counts[counts.family=='technology'].to_dict('records'),M30_actual_quotes_unknown=True,main_figure_contains_no_price_thresholds=True,old_sources_unchanged=True)
for p,h in sources.items():assert sha(p)==h,p
save(Q/'data_checks.json',check);print(json.dumps(check,ensure_ascii=False),flush=True)
