"""Separate production-cohort footprints from deployment-year avoided emissions.

Positive net values denote avoided emissions. Production-route footprints include
upstream life cycles: they are not a territorial inventory for the producer country.
"""
from pathlib import Path
from dataclasses import dataclass
import json
import numpy as np
import pandas as pd
import model as m

ROOT=Path(__file__).resolve().parents[1]
BOS=json.loads((ROOT/'input/parameters/balance_of_system.json').read_text())
FACTORS=pd.read_csv(ROOT/'input/parameters/manufacturing_literature_factors.csv')
BOS2024=json.loads((ROOT/'input/parameters/balance_of_system_2024.json').read_text())
RESPONSE=pd.read_csv(ROOT/'input/parameters/manufacturing_response.csv')
SUBGRIDS=pd.read_csv(ROOT/'input/parameters/manufacturing_subgrid_scenarios.csv').set_index('route')
YEARS=np.arange(2025,2051)

@dataclass(frozen=True)
class ManufacturingCase:
    name:str='china_dynamic_hold2034'
    region:str='china'
    grid_case:str='future_grid'
    freeze_2025:bool=False
    bos_multiplier:float=1.
    freight_multiplier:float=1.
    # An explicitly assumed post-2034 continuation, never a published forecast.
    post2034_2050_multiplier:float=1.
    module_life:int=28
    inverter_life:int=15
    grid_extension:str=''
    electricity_share_2034:float=0.
    response_model:str='bounds'
    bos_inventory:str='legacy2015'
    hold_technology_2025:bool=False
    hold_manufacturing_grid_2025:bool=False
    bos_rounding_offset_g_kwh:float=0.
    manufacturing_grid_multiplier:float=1.

def manufacturing_path(case,production_grid_ratio=None):
    f=FACTORS.query('manufacturing_region == @case.region and grid_case == @case.grid_case').sort_values('year')
    if case.region=='china':
        unit=f.module_excluding_reference_freight_kg_co2e_m2.to_numpy(float)
        freight=np.full(26,BOS['freight_kg_co2e_m2']*case.freight_multiplier)
    else:
        # Non-China routes remain module+freight bundles: no invented subtraction.
        unit=f.module_and_reference_freight_kg_co2e_m2.to_numpy(float)
        freight=np.zeros(26)
        if case.freight_multiplier!=1:raise ValueError('Foreign source route freight is not separately identified')
    module=np.interp(YEARS,f.year,unit)
    if case.response_model=='calibrated_full':
        if case.region!='china' or case.freeze_2025 or case.post2034_2050_multiplier!=1:
            raise ValueError('Calibrated response requires a dynamic China module trajectory')
        if not case.grid_extension:raise ValueError('Calibrated response requires an electricity path')
        table=pd.read_csv(ROOT/'input/parameters/manufacturing_grid_continuations.csv')
        ratio=table.query('path == @case.grid_extension').set_index('year').loc[YEARS,'ratio_to_2034'].to_numpy()
        if production_grid_ratio is not None:
            if case.grid_extension!='inherited_china_grid':raise ValueError('Sample coupling requires the inherited China grid')
            ratio=np.asarray(production_grid_ratio,dtype=float)
        if ratio.shape!=(26,) or np.any(ratio<0) or not np.isfinite(ratio).all() or ratio[0]<=0:
            raise ValueError('Invalid manufacturing-grid trajectory')
        ratio=ratio/ratio[0]
        if case.hold_manufacturing_grid_2025:ratio=np.ones(26)
        E=np.interp(YEARS,RESPONSE.year,RESPONSE.effective_electricity_response_kwh_m2)
        source_grid=np.interp(YEARS,RESPONSE.year,RESPONSE.source_china_grid_kg_co2e_kwh)
        residual=module-E*source_grid
        if case.hold_technology_2025:E[:]=E[0];residual[:]=residual[0]
        if case.manufacturing_grid_multiplier<0:raise ValueError('Negative manufacturing grid multiplier')
        module=residual+E*source_grid[0]*ratio*case.manufacturing_grid_multiplier
        if np.any(module<0) or np.any(residual<0):raise ValueError('Invalid calibrated manufacturing response')
        return module,freight
    if case.response_model!='bounds':raise ValueError('Unknown manufacturing response model')
    if case.freeze_2025:module[:]=module[0]
    else:
        progress=np.clip((YEARS-2034)/16,0,1)
        module=module*(1+progress*(case.post2034_2050_multiplier-1))
    if np.any(module<0):raise ValueError('Negative manufacturing factor')
    if case.grid_extension:
        if case.region!='china' or case.freeze_2025 or case.post2034_2050_multiplier!=1:
            raise ValueError('Grid continuation requires the dynamic China reference without a second continuation')
        if not 0<=case.electricity_share_2034<=1:raise ValueError('Electricity share must lie between zero and one')
        table=pd.read_csv(ROOT/'input/parameters/manufacturing_grid_continuations.csv')
        ratios=table.query('path == @case.grid_extension').set_index('year').loc[YEARS,'ratio_to_2034'].to_numpy()
        if production_grid_ratio is not None:
            if case.grid_extension!='inherited_china_grid':
                raise ValueError('Sample-specific grid ratios only apply to the inherited China path')
            ratios=np.asarray(production_grid_ratio,dtype=float)
            if ratios.shape!=(26,) or not np.all(np.isfinite(ratios)) or np.any(ratios<0):
                raise ValueError('Production-grid ratios must be 26 finite nonnegative values')
            if not np.isclose(ratios[9],1.,rtol=1e-12,atol=1e-12):
                raise ValueError('Production-grid ratio must be anchored to 2034')
        after=YEARS>2034
        # Only the electricity-sensitive share responds. The remainder is held.
        # Shares 0 and 1 are mathematical bounds, not measured inventory fractions.
        module[after]*=(1-case.electricity_share_2034)+case.electricity_share_2034*ratios[after]
    return module,freight

def cohort_generation(annual,exponent=1.,life=28):
    """Allocate inherited PV output to installation cohorts exactly.

    The original model has no degradation/retirement before 2050. Allocation after
    2050 holds the last modelled per-cohort output constant, solely to define the
    service denominator. No post-2050 avoided emissions enter reported balances.
    Returns generation[deployment region, cohort, operating year 2025..2077].
    """
    n=len(annual);horizon=26+life-1
    eta=.20*(1+.0035*(YEARS-2020))
    weights=annual[:,:,19]*eta[None,:]
    g=np.zeros((n,26,horizon))
    for t in range(26):
        total=weights[:,:t+1].sum(1)
        if np.any((annual[:,t,0]>0)&(total<=0)):raise ValueError('Generation without installed PV area')
        share=np.divide(weights[:,:t+1],total[:,None],out=np.zeros_like(weights[:,:t+1]),where=total[:,None]>0)
        g[:,:t+1,t]=annual[:,t,0,None]*share
    for v in range(26):
        g[:,v,26:v+life]=g[:,v,25,None]
    np.testing.assert_allclose(g[:,:,:26].sum(1),annual[:,:,0],rtol=1e-12,atol=1e-8)
    return g

def distribute_event(event, generation, start, duration, out):
    """Allocate a fixed production-event burden once over that device's service."""
    stop=min(start+duration,generation.shape[-1])
    denom=generation[:,start:stop].sum(1)
    shares=np.divide(generation[:,start:stop],denom[:,None],out=np.zeros_like(generation[:,start:stop]),where=denom[:,None]>0)
    if np.any((event>0)&(denom<=0)):raise ValueError('Installed device has no service denominator')
    out[:,start:stop]+=event[:,None]*shares

def account(annual,case=ManufacturingCase(),exponent=1.,return_cohorts=False,production_grid_ratio=None):
    if case.module_life<=26:raise ValueError('Energy model needs explicit PV retirement for lifetimes <=26 years')
    g=cohort_generation(annual,exponent,case.module_life)
    n,h=annual.shape[0],g.shape[-1]
    module,freight=manufacturing_path(case,production_grid_ratio)
    area=annual[:,:,19]*1e6 # km2 -> m2 of model-covered PV area
    eta=.20*(1+.0035*(YEARS-2020))
    kwp=area*eta[None,:] # 1 kW/m2 standard-test irradiance
    initial={
        'module':area*module[None,:]/1e12,
        'freight':area*freight[None,:]/1e12,
        'mounting':area*BOS['mounting_kg_co2e_m2']*case.bos_multiplier/1e12,
        'electrical':kwp*BOS['electrical_kg_co2e_kwp']*case.bos_multiplier/1e12,
        'inverter':kwp*BOS['inverter_kg_co2e_kwp_per_installation']*case.bos_multiplier/1e12,
    }
    if case.bos_inventory=='iea2024':
        offset=case.bos_rounding_offset_g_kwh/1000*BOS2024['reference_lifetime_yield_kwh_kwp']
        if abs(case.bos_rounding_offset_g_kwh)>.05:raise ValueError('Rounding offset exceeds half the published precision')
        del initial['mounting'],initial['electrical']
        initial['combined_bos']=kwp*(BOS2024['combined_bos_kg_co2e_kwp']+offset)*case.bos_multiplier/1e12
        initial['inverter']=kwp*(BOS2024['inverter_kg_co2e_kwp_per_installation']+offset/2)*case.bos_multiplier/1e12
    elif case.bos_inventory!='legacy2015':raise ValueError('Unknown BOS inventory')
    events={k:np.zeros((n,h)) for k in initial}
    service={k:np.zeros((n,h)) for k in initial}
    records=[]
    for v in range(26):
        for component,burden in initial.items():
            ev=burden[:,v]
            events[component][:,v]+=ev
            duration=case.inverter_life if component=='inverter' else case.module_life
            distribute_event(ev,g[:,v],v,min(duration,case.module_life),service[component])
            if component=='inverter':
                for age in range(case.inverter_life,case.module_life,case.inverter_life):
                    when=v+age
                    events[component][:,when]+=ev
                    distribute_event(ev,g[:,v],when,min(case.inverter_life,case.module_life-age),service[component])
            if return_cohorts:
                for r in range(n):
                    records.append(dict(region_index=r,installation_year=int(YEARS[v]),component=component,
                        initial_footprint_gt=float(ev[r]),module_area_m2=float(area[r,v]),
                        stc_capacity_kwp=float(kwp[r,v]),lifetime_generation_twh=float(g[r,v].sum())))
    # Lifetime conservation and no addition of the old aggregate PV factor.
    for k in events:np.testing.assert_allclose(events[k].sum(1),service[k].sum(1),rtol=2e-12,atol=1e-12)
    pv_event=sum(events.values())[:,:26]
    pv_service=sum(service.values())[:,:26]
    nonpv=annual[:,:,14]+annual[:,:,9]
    a_event=annual.copy();a_service=annual.copy()
    a_event[:,:,9]=pv_event;a_service[:,:,9]=pv_service
    a_event[:,:,14]=nonpv-pv_event;a_service[:,:,14]=nonpv-pv_service
    return dict(event=a_event,service=a_service,component_events=events,component_service=service,
        cohort_records=records,module_factors=module,freight_factors=freight,
        post2050_service_of_pre2051_events_gt=(pv_event-pv_service).sum(1))

def default_cases():
    return [ManufacturingCase(name='china_frozen2025',freeze_2025=True),ManufacturingCase(),
        ManufacturingCase(name='china_dynamic_bos_half',bos_multiplier=.5),
        ManufacturingCase(name='china_dynamic_bos_double',bos_multiplier=2.),
        ManufacturingCase(name='china_dynamic_no_freight',freight_multiplier=0.),
        ManufacturingCase(name='china_dynamic_double_freight',freight_multiplier=2.),
        ManufacturingCase(name='china_dynamic_post2034_half',post2034_2050_multiplier=.5),
        ManufacturingCase(name='china_dynamic_life35',module_life=35),
        ManufacturingCase(name='china_staticgrid_technology',grid_case='static_grid'),
        ManufacturingCase(name='india_dynamic_hold2034',region='india'),
        ManufacturingCase(name='usa_dynamic_hold2034',region='usa'),
        ManufacturingCase(name='europe_dynamic_hold2034',region='europe')]+[
        ManufacturingCase(name=f'china_{path}_share{int(share*100)}',grid_extension=path,electricity_share_2034=share)
        for path in ['inherited_china_grid','ssp2_no_climate_target','ssp2_2c','ssp2_1p5c'] for share in [.5,1.]]+updated_cases()

def updated_cases():
    common=dict(response_model='calibrated_full',grid_extension='inherited_china_grid',bos_inventory='iea2024')
    return [
        ManufacturingCase(name='china_frozen2025_iea2024',freeze_2025=True,bos_inventory='iea2024'),
        ManufacturingCase(name='china_source_hold_iea2024',bos_inventory='iea2024'),
        ManufacturingCase(name='china_coupled_legacybos',response_model='calibrated_full',grid_extension='inherited_china_grid'),
        ManufacturingCase(name='china_coupled_iea2024',**common),
        ManufacturingCase(name='china_coupled_iea2024_static_technology',hold_technology_2025=True,**common),
        ManufacturingCase(name='china_coupled_iea2024_static_grid',hold_manufacturing_grid_2025=True,**common),
        ManufacturingCase(name='china_coupled_iea2024_bos_half',bos_multiplier=.5,**common),
        ManufacturingCase(name='china_coupled_iea2024_bos_double',bos_multiplier=2.,**common),
        ManufacturingCase(name='china_coupled_iea2024_rounding_low',bos_rounding_offset_g_kwh=-.05,**common),
        ManufacturingCase(name='china_coupled_iea2024_rounding_high',bos_rounding_offset_g_kwh=.05,**common),
    ]+[
        ManufacturingCase(name=f'china_calibrated_{p}_iea2024',response_model='calibrated_full',grid_extension=p,bos_inventory='iea2024')
        for p in ['ssp2_no_climate_target','ssp2_2c','ssp2_1p5c']]+[
        ManufacturingCase(name=f'china_coupled_iea2024_{label}_manufacturing',manufacturing_grid_multiplier=float(SUBGRIDS.loc[route,'relative_grid_multiplier']),**common)
        for label,route in [('low','china_southwest'),('high','china_northeast')]]
