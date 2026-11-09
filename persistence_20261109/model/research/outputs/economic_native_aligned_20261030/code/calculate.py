"""Price the unchanged native carbon-model quantities and operating flows.

No re-dispatch, no renewal-clock recalculation and no carbon replacement.
Unmetered unlimited-export electricity is explicitly allocated for valuation;
the allocation envelope is not a statistical confidence interval.
"""
import os,json,gzip,hashlib
from pathlib import Path
import numpy as np
import pandas as pd


ROOT=Path(__file__).resolve().parents[1]
E=Path(__file__).resolve().parents[3] / 'outputs/economic_matched_billing_20261030'
C=Path(__file__).resolve().parents[3] / 'outputs/country_manufacturing_recalculation_20261028'
V=Path(__file__).resolve().parents[4] / 'native'
F3=Path(__file__).resolve().parents[3] / 'outputs/figure3_scenario_families_country_only_20261029'
F4=Path(__file__).resolve().parents[3] / 'outputs/figure4_warm_apricot_20261029'
OLD6=Path(__file__).resolve().parents[3] / 'outputs/figure6_maps_five_country_costs_20261030'
D,O,Q=[ROOT/x for x in ['source_data','outputs','qa']]
for p in [D,O,Q]:p.mkdir(parents=True,exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
unzip=lambda p:json.loads(gzip.decompress(Path(p).read_bytes()))
save=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
sources={}
def protect(p):
    p=Path(p);sources[str(p)]=sha(p);return p

manifest=read(protect(C/'source_data/recalculated_account_manifest.json'))
lookup={(r['scenario_id'],r['background']):r for r in manifest}
configs=read(protect(E/'source_data/configurations.json'))
reg=read(protect(OLD6/'source_data/display_scenarios.json'))
bindings=read(protect(E/'source_data/provenance/country_bindings.json'))
base=read(protect(E/'source_data/base.json'))
prices_raw=read(protect(E/'source_data/prices.json'))
cat=read(protect(V/'multiscale_full_resolution_20261024/source_data/full_catalog.json'))
pn=np.load(protect(V/'multiscale_full_resolution_20261024/source_data/parent_inputs.npz'))
codes=base['codes'];n=231;T=76;years=np.arange(2025,2101)
assert len(codes)==n and pn['years'].tolist()==years.tolist()
P=base['parent'];N=len(P);pc=pn['countryIndex'].astype(int)
assert N==14209 and pc.tolist()==[p['country'] for p in P]
du=pn['du'];progress=pn['progress'];Y=np.array([p['Y'] for p in P])
p0=np.array([p['p0'] for p in P]);cap=np.array([p['cap'] for p in P]);fc=pn['fc']
modDue=pn['modDue'].astype(int);invFirst=np.array([p['invFirst'] for p in P])
with np.load(protect(V/'multiscale_full_resolution_20261024/source_data/native_opening.npz')) as opening_archive:
    # NPZ members are lazily decompressed; cache the four required vectors once.
    opening={k:opening_archive[k] for k in ['parentOffsets','offsets','prefixAY','due']}
# Weighted clean-Y mass of opening battery cohorts, before their original due.
beforeY=np.zeros((N,T));totalY=np.zeros(N)
for i in range(N):
    g0,g1=opening['parentOffsets'][i:i+2].astype(int)
    for g in range(g0,g1):
        lo,hi=opening['offsets'][g:g+2].astype(int)
        mass=float(opening['prefixAY'][hi-1]) if hi>lo else 0.
        totalY[i]+=mass
        beforeY[i,:min(T,int(opening['due'][g]))]+=mass
scale_area=pn['allocatedArea']/pn['area']
p0_per_area=pn['p0']/pn['area']
prices={k:np.array([r[k] for r in prices_raw],dtype=float).reshape(n,T) for k in prices_raw[0] if isinstance(prices_raw[0][k],(float,int))}
buy,sell,dfc,dfo=[prices[k] for k in ['buy_price_usd_kwh','sell_price_usd_kwh','capital_discount_factor','operating_discount_factor']]
assert np.all(buy>=sell) and np.all(sell>=0)
ILR=base['cost_normalisation']['PV_source_ILR'];sourceHours=base['cost_normalisation']['battery_source_duration_h']
ref_native=unzip(protect(Path(lookup['REF','CP']['source_account'])))
refq=unzip(protect(C/f"quantity_cache/{lookup['REF','CP']['physical_id']}.json.gz"))['quantity']
denom_demand=np.array(base['national']['cap'])*np.array(ref_native['energyCountry']['generation'])[:,0]/(np.array(base['national']['p0'])+np.array(refq['newPV']).reshape(n,T)[:,0])
denominator=(denom_demand[:,None]*dfo).sum(axis=1)/1000
assert np.all(denominator>0)

def aggregate(x):
    out=np.zeros((n,T));np.add.at(out,pc,x);return out

weather_cache={}
def parent_generation(a):
    s,p=a['selection'],a['parameters']
    roof=np.array(cat['roofRatios'][s['roof']],float)
    new=np.maximum(0,(cap[:,None]*roof[None,:]-p0[:,None])*progress[None,:])
    if s['climate']=='CLEAN_CONTROL':ratio=np.ones((N,T))
    elif s['climate']=='HOLD':ratio=np.broadcast_to(pn['Fold'][:,None],(N,T))
    else:
        key=f"{s['model']}_{s['climate']}"
        if key not in weather_cache:
            f=protect(V/f'ssp_physical_extensions_20261027/source_data/{key}.npz')
            w=np.load(f);weather_cache[key]=w['radiationRatio' if s['climateCoupling']=='RADIATION_ONLY' else 'pvRatio']
        ratio=weather_cache[key]
    phase=np.minimum(1,np.divide(np.cumsum(invFirst,axis=1),p0[:,None],out=np.ones((N,T)),where=p0[:,None]>0))
    pg=p.get('pv_system_gain',1);ig=p.get('inverter_gain',1)
    ratioOld=ratio*np.where(np.arange(T)[None,:]>=modDue[:,None],pg,1)*(1+(ig-1)*phase)
    generation=(p0[:,None]*ratioOld+new*ratio*pg*ig)*Y[:,None]
    direct=aggregate(generation*du[:,None])
    fn=fc if p['share'] is None else np.full(N,p['share'])
    # Existing bounded-model nightAlpha=1, used only as an annual monetary
    # allocation proxy. No country-specific measured night load is asserted.
    night_new=new*Y[:,None]*du[:,None]*fn[:,None]*p['duty']
    night_old=p0_per_area[:,None]*du[:,None]*fc[:,None]*(beforeY+(totalY[:,None]-beforeY)*p['duty'])
    return aggregate(generation),direct,aggregate(night_new+night_old),aggregate(new+p0[:,None])

pvjob_cache={}
def pvjobs(p):
    key=p['module_years'],p['inverter_years']
    if key in pvjob_cache:return pvjob_cache[key]
    roof=np.zeros((n,T));electric=np.zeros((n,T));site=np.zeros((n,T))
    for i,x in enumerate(P):
        c=x['country'];inv=np.zeros(T)
        for first in range(T):inv[first::p['inverter_years']]+=invFirst[i,first]
        mod=np.zeros(T)
        if x['p0']>0 and x['modDue']<T:mod[x['modDue']::p['module_years']]=x['p0']
        roof[c]+=mod;electric[c]+=np.maximum(mod,inv);site[c]+=np.maximum(mod,inv)
    pvjob_cache[key]=(roof,electric,site);return roof,electric,site

def events(v):
    nz=np.flatnonzero(v!=0);neg=np.flatnonzero(v<0);first=int(neg[0]) if len(neg) else None
    losses=np.flatnonzero((np.arange(T)>(first if first is not None else T))&(v>0))
    loss=int(losses[0]) if len(losses) else None
    initial=bool(len(nz) and v[nz[0]]<0);cross=int(np.sum(np.diff(np.sign(v[nz]))!=0))
    status='NEVER_NEGATIVE' if first is None else 'NEGATIVE_NO_LOSS_OBSERVED' if loss is None else 'LOSS_THEN_RECOVERED' if v[-1]<0 else 'LOSS_OBSERVED'
    return dict(first_negative_year=None if first is None else int(years[first]),loss_year=None if loss is None else int(years[loss]),K=int((v<0).sum()),initially_negative=initial,crossings=cross,status=status)

BGS=['CP','NDC','B2C','NZ2050','LD'];allfinance=[];finance_by={};maxgen=0.;maxenergy=0.;closure=0.
case_ids=[c['id'] for c in configs]
for no,conf in enumerate(configs):
    sid=conf['id'];r=lookup[sid,'CP'];a=unzip(protect(Path(r['source_account'])))
    assert a['_codes']==codes and a['years']==years.tolist()
    p=a['parameters'];assert p==conf['parameters']
    qobj=unzip(protect(C/f"quantity_cache/{r['physical_id']}.json.gz"))
    q={k:np.array(v,float).reshape(n,T) for k,v in qobj['quantity'].items()}
    e={k:None if v is None else np.array(v,float) for k,v in a['energyCountry'].items()}
    g,direct,night,stock=parent_generation(a)
    generror=float(np.max(np.abs(g-e['generation'])/np.maximum(1,e['generation'])))
    maxgen=max(maxgen,generror);assert generror<1e-10,(sid,generror)
    balance=e['generation']-e['useful']-e['loss']-e['pvAux']-e['curtailment']
    err=float(np.max(np.abs(balance)/np.maximum(1,e['generation'])));maxenergy=max(maxenergy,err);assert err<1e-10
    delivered=np.maximum(0,e['discharge']-e['pvAux'])
    if e['export'] is None:
        direct=np.minimum(direct,e['useful'])
        selfuse=np.minimum(e['useful'],direct+np.minimum(delivered,night))
        lowself=direct;highself=np.minimum(e['useful'],direct+delivered)
        split='NATIVE_DIRECT_PLUS_ANNUAL_POOLED_NIGHT_PROXY'
    else:
        selfuse=e['useful']-e['export'];lowself=selfuse.copy();highself=selfuse.copy()
        assert float(np.min(selfuse))>=-1e-4
        selfuse=np.maximum(0,selfuse);split='NATIVE_RECORDED_EXPORT'
    export=e['useful']-selfuse
    assert float(np.min(export))>=-1e-4
    np.testing.assert_allclose(selfuse+export,e['useful'],rtol=1e-14,atol=1e-4)
    roof,elec,site=[v.copy() for v in pvjobs(p)]
    for t in range(T):
        for o in range(t):
            mr=q['newPV'][:,o] if (t-o)%p['module_years']==0 else np.zeros(n)
            ir=q['newPV'][:,o] if (t-o)%p['inverter_years']==0 else np.zeros(n)
            # Different installation origins must never be deduplicated into
            # one national work order, even when their due years coincide.
            roof[:,t]+=mr;elec[:,t]+=np.maximum(mr,ir);site[:,t]+=np.maximum(mr,ir)
    # Component quantities are copied verbatim; no new age/cycle calculation.
    bmsnew=q['newBat_nominal']*p['effective_DoD']/p['hours']
    bmsrenew=q['batRepl_nominal']*p['effective_DoD']/p['hours']
    caserenew=q['houseRepl']/p['effective_DoD']
    retired=q['legacyFirst']/.9+q['adoptedRetired_nominal']
    first=q['newPV']*prices['pv_new_usd_kwp']+q['newBat_nominal']*prices['battery_module_hw_usd_kwh_nom']+bmsnew*prices['bms_hw_usd_kw']+q['newHouse']/p['effective_DoD']*prices['case_hw_usd_kwh_nom_supported']+q['newBat_nominal']*prices['battery_first_bos_usd_kwh_nom']
    pvHW=q['modRepl']*(prices['pv_module_hw_usd_kwp']+prices['pv_sbos_hw_usd_kwp']+prices['pv_ebos_hw_usd_kwp'])
    invHW=q['invRepl']/ILR*prices['inv_hw_usd_kwac']
    replacement=pvHW+invHW+q['batRepl_nominal']*prices['battery_module_hw_usd_kwh_nom']+bmsrenew*prices['bms_hw_usd_kw']+caserenew*prices['case_hw_usd_kwh_nom_supported']
    batteryjobs=np.maximum(q['batRepl_nominal'],sourceHours*bmsrenew)
    # Module and its BMS always share their original replacement event.
    # Housing has a separate source clock. Add its work as the central priced
    # scope; all-combined versus separate service is retained as a sensitivity,
    # rather than silently merging national events from unrelated installations.
    essjobs=batteryjobs+caserenew
    essjobs_combined=np.maximum(batteryjobs,caserenew)
    service=roof*prices['pv_roof_service_usd_kwp']+elec*prices['pv_electric_service_usd_kwp']+site*prices['pv_site_service_usd_kwp']+essjobs*prices['battery_service_usd_kwh_nom']
    retirement=q['modRepl']*prices['eol_pv_usd_kwp']+q['invRepl']*prices['eol_inv_usd_kwp_dc']+retired*prices['eol_battery_usd_kwh_nom']+q['houseRepl']*prices['eol_case_usd_kwh_usable']
    om=stock*prices['om_pv_usd_kwp_year']
    # Common load-only expenditure cancels in paired differences. This is an
    # economic valuation, not a fabricated set of measured national invoices.
    variable_bill=e['gridAux']*buy-selfuse*buy-export*sell
    bill0=e['gridAux']*buy-lowself*buy-(e['useful']-lowself)*sell
    bill1=e['gridAux']*buy-highself*buy-(e['useful']-highself)*sell
    capital=(first+replacement+service+retirement)*dfc
    cash=capital+(om+variable_bill)*dfo
    cash0=capital+(om+bill0)*dfo;cash1=capital+(om+bill1)*dfo
    service_room=(essjobs-essjobs_combined)*prices['battery_service_usd_kwh_nom']*dfc
    allpv=(q['newPV']+q['modRepl'])*(prices['pv_module_hw_usd_kwp']+prices['pv_sbos_hw_usd_kwp']+prices['pv_ebos_hw_usd_kwp'])+(q['newPV']+q['invRepl'])/ILR*prices['inv_hw_usd_kwac']
    bat=(q['newBat_nominal']+q['batRepl_nominal'])*prices['battery_module_hw_usd_kwh_nom']
    bmshw=(bmsnew+bmsrenew)*prices['bms_hw_usd_kw'];hhw=(q['newHouse']/p['effective_DoD']+caserenew)*prices['case_hw_usd_kwh_nom_supported']
    if sid.startswith('FIG4_') or sid.startswith('LIFE_ALL'):affected=allpv+bat+bmshw+hhw
    elif sid.startswith('LIFE_PV'):affected=(q['newPV']+q['modRepl'])*(prices['pv_module_hw_usd_kwp']+prices['pv_sbos_hw_usd_kwp']+prices['pv_ebos_hw_usd_kwp'])
    elif sid.startswith('LIFE_INV'):affected=(q['newPV']+q['invRepl'])/ILR*prices['inv_hw_usd_kwac']
    elif sid.startswith('LIFE_HOUSE'):affected=hhw
    else:affected=bat
    values=dict(NPC=cash.sum(axis=1),NPC0=cash0.sum(axis=1),NPC1=cash1.sum(axis=1),
        NPC_combined_service=(cash-service_room).sum(axis=1),NPC0_combined_service=(cash0-service_room).sum(axis=1),NPC1_combined_service=(cash1-service_room).sum(axis=1),affected=(affected*dfc).sum(axis=1),
        new=(first*dfc).sum(axis=1),replacement=((replacement+service)*dfc).sum(axis=1),retirement=(retirement*dfc).sum(axis=1),OM=(om*dfo).sum(axis=1),bill=(variable_bill*dfo).sum(axis=1))
    np.testing.assert_allclose(values['NPC'],sum(values[k] for k in ['new','replacement','retirement','OM','bill']),rtol=2e-12,atol=.01)
    finance_by[sid]=values
    np.savez_compressed(O/f'annual_{sid}.npz',cashflow_USD2025=cash,combined_service_discounted_savings_USD2025=service_room,source_selfuse_kWh=selfuse,source_export_kWh=export,source_gridAux_kWh=e['gridAux'],source_generation_kWh=e['generation'],source_useful_kWh=e['useful'],source_new_battery_nominal=q['newBat_nominal'],source_replacement_battery_nominal=q['batRepl_nominal'],source_retired_battery_nominal=retired)
    for i,code in enumerate(codes):
        allfinance.append(dict(scenario_id=sid,code=code,country=bindings[i]['country'],cost_status=conf['cost_status'],
            valuation_NPC_USD2025=float(values['NPC'][i]),discounted_common_service_MWh=float(denominator[i]),
            new_USD2025=float(values['new'][i]),replacement_USD2025=float(values['replacement'][i]),retirement_USD2025=float(values['retirement'][i]),OM_USD2025=float(values['OM'][i]),electricity_value_USD2025=float(values['bill'][i]),
            electricity_split=split,source_account_sha256=sources[str(Path(r['source_account']))],quantity_sha256=sources[str(C/f"quantity_cache/{r['physical_id']}.json.gz")]))
    if (no+1)%5==0:print(json.dumps(dict(stage='native-events-priced',done=no+1,total=len(configs))),flush=True)

fin=pd.DataFrame(allfinance)
ref=finance_by['REF']
for sid,v in finance_by.items():
    ix=fin.scenario_id==sid
    dc=(v['NPC']-ref['NPC'])/denominator
    variants=[(v[k]-ref[k])/denominator for k in ['NPC','NPC0','NPC1','NPC_combined_service','NPC0_combined_service','NPC1_combined_service']]
    lo=np.minimum.reduce(variants);hi=np.maximum.reduce(variants)
    fin.loc[ix,'delta_cost_USD2025_per_MWh']=dc
    fin.loc[ix,'allocation_envelope_low_USD2025_per_MWh']=lo
    fin.loc[ix,'allocation_envelope_high_USD2025_per_MWh']=hi
    fin.loc[ix,'allowable_affected_hardware_premium_fraction']=np.divide(-(v['NPC']-ref['NPC']),v['affected'],out=np.full(n,np.nan),where=v['affected']>0)
fin.to_csv(O/'231国_75配置_原生碳账本同口径单位成本.csv',index=False,encoding='utf-8-sig')
fidx=fin.set_index(['scenario_id','code']);refs={};rows=[];original_comparisons=[]
for bg in BGS:
    a=unzip(protect(Path(lookup['REF',bg]['source_account'])));refs[bg]=a
for conf in configs:
    sid=conf['id']
    for bg in BGS:
        r=lookup[sid,bg];a=unzip(protect(Path(r['source_account'])));refa=refs[bg]
        assert a['_codes']==codes and a['years']==years.tolist()
        for i,code in enumerate(codes):
            v=np.asarray(a['countries']['C'][i]);rv=np.asarray(refa['countries']['C'][i]);se=events(v);re=events(rv)
            delay=se['loss_year']-re['loss_year'] if se['loss_year'] is not None and re['loss_year'] is not None else None
            state=('initial' if re['initially_negative'] else 'strict') if re['loss_year'] is not None and rv[-1]>0 else 'other'
            if se['first_negative_year'] is None:outcome='未形成收益'
            elif re['first_negative_year'] is None:outcome='新形成收益'
            elif delay is not None:outcome='丧失推迟' if delay>0 else '丧失提前' if delay<0 else '丧失年相同'
            elif re['loss_year'] is not None:outcome='截至2100未丧失'
            elif se['loss_year'] is not None:outcome='新增丧失事件'
            else:outcome='双方均未丧失'
            h=np.asarray(a['countries']['H'][i]);aa=np.asarray(a['countries']['A'][i]);closure=max(closure,float(np.max(np.abs(v-h+aa))))
            f=fidx.loc[sid,code]
            rows.append(dict(scenario_id=sid,code=code,country=f.country,background=bg,REF_state=state,reference_loss_year=re['loss_year'],scenario_loss_year=se['loss_year'],loss_delay_years=delay,loss_outcome=outcome,
                REF_K=re['K'],scenario_K=se['K'],delta_K=se['K']-re['K'],REF_C2100_Mt=rv[-1]*1000,C2100_Mt=v[-1]*1000,delta_C2100_Mt=(v[-1]-rv[-1])*1000,
                reference_crossings=re['crossings'],scenario_crossings=se['crossings'],reference_status=re['status'],scenario_status=se['status'],
                delta_cost_USD2025_per_MWh=f.delta_cost_USD2025_per_MWh,allocation_envelope_low_USD2025_per_MWh=f.allocation_envelope_low_USD2025_per_MWh,allocation_envelope_high_USD2025_per_MWh=f.allocation_envelope_high_USD2025_per_MWh,
                allowable_affected_hardware_premium_fraction=f.allowable_affected_hardware_premium_fraction,cost_status=f.cost_status,source_account_sha256=sources[str(Path(r['source_account']))]))
        original_comparisons.append(dict(background=bg,scenario_id=sid,source_account=str(r['source_account']),source_sha256=sources[str(Path(r['source_account']))],carbon_arrays_used='countries.C/H/A and annualCountry unchanged',physical_events='quantity_cache unchanged'))
pair=pd.DataFrame(rows);assert len(pair)==75*231*5
pair.to_csv(O/'231国_75配置_五背景_统一成本转折与累计排放.csv',index=False,encoding='utf-8-sig')
main=pair[pair.scenario_id.isin([r['scenario_id'] for r in reg])].copy()
main.to_csv(O/'图6_26干预_全部国家配对.csv',index=False,encoding='utf-8-sig')
main[main.code.isin(['CHN','USA','BRA','CHL','COL'])].to_csv(O/'图6_五国配对.csv',index=False,encoding='utf-8-sig')
# Cross-check against the actual Figure4 source table, not a similarly named
# conditional economic account. K, first-loss and C must all replay.
f4=pd.read_csv(protect(F4/'source_data/selected_country_matched_outcomes.csv'))
f4errors=[]
for _,r in f4.iterrows():
    d=pair[(pair.background==r.background)&(pair.scenario_id==r['case'])&(pair.code==r.country)].iloc[0]
    assert int(d.scenario_K)==int(r.K)
    assert (pd.isna(d.scenario_loss_year) and pd.isna(r.first_loss)) or d.scenario_loss_year==r.first_loss
    f4errors.append(abs(d.C2100_Mt/1000-r.C2100_Gt))
    assert f4errors[-1]<1e-10
f3cohort=read(protect(F3/'source_data/reference_cohorts.json'))
save(D/'figure3_reference_cohorts_snapshot.json',f3cohort)
f4hashes=read(protect(F4/'source_data/account_sha256.json'))
for p,h in f4hashes.items():assert sha(p)==h
for p,h in list(sources.items()):assert sha(p)==h,(p,'changed during pricing')
save(D/'source_manifest.json',dict(files=[dict(path=p,sha256=h) for p,h in sources.items()],original_accounts_unchanged=True))
save(D/'display_scenarios.json',reg)
save(D/'native_account_bindings.json',original_comparisons)
contract=dict(question='哪些干预以怎样的单位成本改变了哪些国家的收益丧失年份和累计净排放？',
    physical_authority='图3和图4现行国家制造来源修正后的原生1km账户；REMIND；SSP2-4.5辐射+气温+风速为中心；具体源选择逐账户保存',
    physical_locked=['generation','charge','discharge','loss','pvAux','gridAux','curtailment','newPV','modRepl','invRepl','newBat_nominal','batRepl_nominal','adoptedRetired_nominal','legacyFirst','newHouse','houseRepl'],
    economic_method='逐年按原新增/更换/退役事件与原电量计价；无重新调度、无寿命重算；现金流折现，碳不折现',
    unit='2025实值USD/MWh；同国REF增量净支出现值/固定全期共同服务需求折现MWh，非发电LCOE',
    unlimited_metering_gap='原完全消纳账户未记录自用/售电拆分，不能伪称已取得逐国实际账单',
    allocation_assumption='直接用电按原网格du加总；电池净放电按既有nightAlpha=1清洁设计夜间接纳量在国家年度池中分配自用，其余售电；只影响货币估值，不改碳或原电量',
    allocation_limits='国家年度池可能高于逐网格夜间限制的自用和；作者账单分配代理，不称原生逐户小时调度',
    service_assumption='按原事件计价；电池与BMS同一事件，壳体检修分别计入；合并至同年最大工作量为检修合并敏感性，不将其当实测工单',
    sensitivity='电池净放电全部售电／全部自用及参考分配，分别配对分开／合并检修，共六规则包络；受限外送用原export记录，不改变原弃光；非置信区间',
    price_sources='复用逐值溯源的原prices与provenance目录；ATB中等年度路径不改；未套用制造碳下降比例作采购折扣',
    unknowns='额外技术溢价、化学体系价差和匹配处理价仍未知；改善柱是参考价截距；新国别规模校准未接入',
    inference='经济估值与碳干预配对，不称成本内生驱动投资；无实际价格假设时可给允许溢价阈值',
    model_rerun=False,economic_cashflow_recalculated=True,original_figures_changed=False)
save(D/'alignment_contract.json',contract)
checks=dict(status='PASS',configurations=75,financial_cases=len(fin),background_carbon_pairs=len(pair),figure6_pairs=len(main),figure6_country_pairs=int(main.code.isin(['CHN','USA','BRA','CHL','COL']).sum()),
    max_generation_replay_relative_error=maxgen,max_energy_closure_relative_error=maxenergy,max_carbon_closure_error_Gt=closure,
    figure4_source_rows_reproduced=len(f4),max_figure4_C2100_replay_error_Gt=max(f4errors),all_source_hashes_unchanged=True,
    no_dispatch_or_replacement_recalculation=True,price_inputs_unchanged=True)
save(Q/'alignment_checks.json',checks)
old=pd.read_csv(E/'outputs/75配置_231国条件净支出与允许溢价.csv')
cmp=fin.merge(old[['scenario_id','code','delta_cost_USD2025_per_MWh']],on=['scenario_id','code'],suffixes=('_aligned','_old'),validate='1:1')
cmp['aligned_minus_old_USD_per_MWh']=cmp.delta_cost_USD2025_per_MWh_aligned-cmp.delta_cost_USD2025_per_MWh_old
cmp.to_csv(O/'经济成本_统一前后逐国对照.csv',index=False,encoding='utf-8-sig')
save(O/'summary.json',checks)
print(json.dumps(checks,ensure_ascii=False))
