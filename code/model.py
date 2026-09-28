"""Annual energy and carbon accounting for rooftop PV and storage."""
from pathlib import Path
from dataclasses import dataclass, asdict, replace
import sys, json, hashlib, math
import numpy as np
import pandas as pd
from numba import njit, prange

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from paths import DATA_ROOT,RESULTS
ROOT = DATA_ROOT / 'grids'
DATA = RESULTS / 'model_generated'
DATA.mkdir(parents=True,exist_ok=True)
sys.path.insert(0, str(ROOT))
from model_support import country_ac_units_per_person
from model_support import PARAMETERS, latin_hypercube, baseline_sample

YEARS = np.arange(2025, 2051)
FIELDS = ['generation_twh', 'delivered_twh', 'direct_twh', 'battery_charge_twh',
          'battery_discharge_twh', 'export_twh', 'storage_loss_twh', 'curtailed_twh',
          'displaced_grid_gt', 'pv_embodied_gt', 'cooling_gt', 'ac_gt',
          'roof_credit_gt', 'battery_gt', 'net_gt', 'battery_stock_gwh',
          'battery_additions_gwh', 'battery_retired_gwh', 'pv_area_km2',
          'pv_additions_km2']
IDX = {x: i for i, x in enumerate(FIELDS)}
PNAMES = list(PARAMETERS)
# Eighteen model parameters; additional settings are defined by Controls.
BASE = {k: float(baseline_sample().iloc[0][k]) for k in PNAMES}

@dataclass(frozen=True)
class Controls:
    pv_life: float = 28.0
    battery_rte: float = .85
    battery_duration_h: float = 2.5
    pv_event_accounting: bool = False
    cooling_linear_coverage: bool = False
    initial_roof_life: float = 20.0
    roof_extension: float = 1.30
    roof_kg_m2: float = 30.0
    ac_life: float = 15.0
    ac_kg_unit: float = 250.0

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for part in iter(lambda: stream.read(1048576), b''): h.update(part)
    return h.hexdigest()

def prepare_inputs():
    source = []
    frames = []
    for year in [2021, 2030, 2040, 2050]:
        path = ROOT / f'global_grid_feedback_{year}_high.csv'
        f = pd.read_csv(path).query('farea > 0').sort_values('Id').reset_index(drop=True)
        if frames: np.testing.assert_array_equal(f.Id, frames[0].Id)
        frames.append(f)
        source.append({'file': path.name, 'sha256': sha(path), 'year': year})
    b = frames[0]
    regions = sorted(b.country_tag.unique())
    zone_names = sorted(b.climate_zone.unique())
    pairs = sorted(set(zip(b.country_tag, b.climate_zone)))
    pair_index = {key: i for i, key in enumerate(pairs)}
    group = np.array([pair_index[x] for x in zip(b.country_tag, b.climate_zone)], dtype=np.int64)
    region_idx = np.array([regions.index(x) for x in b.country_tag], dtype=np.int64)
    # G = coefficient * area-fraction * installation efficiency * SSRD trend.
    # This generation coefficient does not include temperature derating.
    eta21 = .20 * (1 + .0035)
    coefficient = b.annual_gen_kwh_realised.to_numpy() / (.75 * eta21 * b.ssrd_factor.to_numpy() * (1 - b.grid_curtailment.to_numpy()))
    rho = np.clip(5.221e-7 * np.abs(b.lat_center.to_numpy())**2 + 3.233e-6 * np.abs(b.lat_center.to_numpy()) + .00162, .0015, .004)
    # A population term is reconstructed independently of area calibration.
    pop = b.people.to_numpy()
    # Per country x zone annual intensive fields: EF, direct use, SSRD, heat,
    # latent multiplier, AC ownership. These are uniform within each group.
    intensive = np.zeros((len(pairs), 26, 6))
    for gi, (country, zone) in enumerate(pairs):
        mask = group == gi
        j = np.flatnonzero(mask)[0]
        for fi in frames:
            for name in ['country_co2', 'direct_use_eff', 'ssrd_factor', 'heatwave_dt_c', 'pgw_factor', 'latent_mult']:
                assert np.ptp(fi.loc[mask, name].to_numpy()) < 1e-9, (country, zone, name)
        for ti, year in enumerate(YEARS):
            for ki, name in enumerate(['country_co2', 'direct_use_eff', 'ssrd_factor']):
                intensive[gi, ti, ki] = np.interp(year, [2021,2030,2040,2050], [f.loc[j, name] for f in frames])
            # heatwave_dt_c already includes the PGW factor in the source.
            intensive[gi, ti, 3] = np.interp(year, [2021,2030,2040,2050], [f.loc[j,'heatwave_dt_c'] for f in frames])
            intensive[gi, ti, 4] = b.loc[j, 'latent_mult']
            intensive[gi, ti, 5] = country_ac_units_per_person(country, int(year), zone)
    # Battery life is fixed across input years within each cell.
    for f in frames[1:]: np.testing.assert_allclose(f.battery_life, b.battery_life, rtol=1e-10)
    physical_scale=np.minimum(1.,1.239e10*np.cos(np.radians(b.lat_center.to_numpy()))/np.maximum(b.aarea.to_numpy(),1.))
    roof_area=b.farea.to_numpy()*physical_scale
    inferred_area=b.roof_credit_t.to_numpy()*1000./(.75*28./20.*(1-1/1.3)*30.)
    np.testing.assert_allclose(roof_area,inferred_area,rtol=1e-8,atol=1e-5)
    cell = np.column_stack([coefficient, roof_area, pop, rho, b.battery_life]).astype(float)
    inputs_export=b[['Id','lat_center','lon_center','country_tag','climate_zone','farea','people','battery_life']].copy()
    inputs_export['roof_reference_m2_after_cap']=roof_area
    inputs_export['physical_area_scale']=physical_scale
    inputs_export['resource_coefficient_q']=coefficient
    inputs_export['battery_rho_kwh_per_annual_kwh']=rho
    inputs_export.to_csv(DATA/'input_cells.csv',index=False)
    rows=[]
    for gi,(country,zone) in enumerate(pairs):
        for ti,year in enumerate(YEARS):
            rows.append(dict(country_tag=country,climate_zone=zone,year=int(year),**dict(zip(['grid_ef_kg_kwh','direct_use_fraction','ssrd_factor','heatwave_increment_c','latent_multiplier','ac_units_per_person'],intensive[gi,ti]))))
    pd.DataFrame(rows).to_csv(DATA/'input_annual_intensities.csv',index=False)
    return dict(meta=b, regions=regions,pairs=pairs,group=group,region_idx=region_idx,cell=cell,intensive=intensive,sources=source)

@njit(cache=True)
def curve_interpolate(values, year_float):
    t = min(max(year_float-2025.,0.),25.)
    j = min(int(t),24)
    w = t-j
    return values[j]*(1-w) + values[j+1]*w

@njit(cache=True)
def group_paths(params, final_cover, intensive, settings):
    """Replacement kernels shared by cells with identical intensive paths."""
    # columns: cover, installed eta-area, new eta-area, EF, DU, SSRD,
    # heat dose, cooling kg/person, AC kg/person, roof kg/m2, curtailment.
    ng = intensive.shape[0]
    path = np.zeros((ng, 26, 11))
    roof_event = np.zeros(26)
    cover = np.zeros(26)
    pv_eff = np.zeros(26)
    pv_add_eff = np.zeros(26)
    roof_life, roof_ext, roofkg = settings[5],settings[6],settings[7]
    aclife, ackg = settings[8], settings[9]
    for t in range(26):
        cover[t] = final_cover/100.*((t+1)/26.)**params[17]
        new_area = cover[t] - (cover[t-1] if t else 0.)
        eta = .20*(1+.0035*(2025+t-2020))
        pv_add_eff[t] = new_area*eta
        pv_eff[t] = pv_add_eff[t]+(pv_eff[t-1] if t else 0.)
        # Uniform phase in the pre-existing 20-year roof stock. Paired renewal
        # ages advance at 1 versus 1/extension, and reset only at replacement.
        for v in range(t+1):
            a = t-v
            added = cover[v] - (cover[v-1] if v else 0.)
            increment = 0.
            for phase in range(int(roof_life)):
                age0=(phase+.5)
                nr0=math.floor((age0+a+1)/roof_life)-math.floor((age0+a)/roof_life)
                nr1=math.floor((age0+(a+1)/roof_ext)/roof_life)-math.floor((age0+a/roof_ext)/roof_life)
                increment += nr0-nr1
            roof_event[t] += added*increment/roof_life*roofkg*params[10]
    for g in range(ng):
        # Paired initial AC ages plus subsequent ownership additions.
        ages0=np.zeros(42); ages1=np.zeros(42); units=np.zeros(42)
        for k in range(int(aclife)):
            ages0[k]=k+.5; ages1[k]=k+.5
            units[k]=intensive[g,0,5]/aclife
        for t in range(26):
            if t:
                units[int(aclife)+t-1]=max(0.,intensive[g,t,5]-intensive[g,t-1,5])
            progress=t/25.
            grid_y=2025.+25.*progress**params[7]
            ef=curve_interpolate(intensive[g,:,0],grid_y)
            ef += intensive[g,25,0]*(params[6]-1)*progress**params[7]
            ef=max(ef,0.)
            du=min(.85,intensive[g,t,1]+params[14])
            exposure=cover[t] if settings[4] else min(cover[t]/.25,1.)
            dt=intensive[g,t,3]*exposure
            shortlife=aclife*(1-min(.30,max(0.,.10*dt)))
            extra=0.
            for k in range(42):
                n0=math.floor((ages0[k]+1)/aclife)
                n1=math.floor((ages1[k]+aclife/shortlife)/aclife)
                ages0[k]=(ages0[k]+1)-n0*aclife
                ages1[k]=(ages1[k]+aclife/shortlife)-n1*aclife
                extra += units[k]*(n1-n0)
            cooling=dt*120.*intensive[g,t,4]*(intensive[g,t,5]/.90)*ef*params[9]
            ramp=max(0.,min(1.,(cover[t]*100-params[15])/(90.-params[15])))
            curtail=params[16]*ramp*max(1-du,.15)
            path[g,t,0]=cover[t]
            path[g,t,1]=pv_eff[t]
            path[g,t,2]=pv_add_eff[t]
            path[g,t,3]=ef
            path[g,t,4]=du
            path[g,t,5]=intensive[g,t,2]
            path[g,t,6]=dt
            path[g,t,7]=cooling
            path[g,t,8]=extra*ackg
            path[g,t,9]=roof_event[t]
            path[g,t,10]=curtail
    return path

@njit(cache=True)
def storage_day(annual_generation, du, capacity, rte, duration):
    """Cyclic repeated-day AC-side storage screen with an external sink.

    Twelve daylight bins use a normalised sine. Direct demand absorbs du in
    every bin; charging is energy/power/SOC constrained. Discharge to the
    retained sink occurs during the twelve night hours. SOC starts/ends zero.
    No national load feasibility is asserted by this boundary.
    """
    eta=math.sqrt(rte)
    soc=0.; charged=0.; direct=0.; exported=0.
    power=capacity/duration
    total_sin=0.
    for h in range(12):total_sin += math.sin(math.pi*(h+.5)/12.)
    for h in range(12):
        pv=annual_generation/365.*math.sin(math.pi*(h+.5)/12.)/total_sin
        d=pv*du
        ch=min(pv-d,power,max(0.,(capacity-soc)/eta))
        soc += ch*eta
        charged += ch; direct += d; exported += pv-d-ch
    discharged=0.
    for h in range(12):
        dis=min(power,soc*eta)
        soc-=dis/eta; discharged+=dis
    loss=charged-discharged
    return direct*365.,charged*365.,discharged*365.,exported*365.,loss*365.,soc

@njit(cache=True, parallel=True)
def _evaluate(samples, final_cover, cell, groups, ridx, intensive, nregion, settings, collect_cells):
    ns=samples.shape[0]
    annual=np.zeros((ns,nregion,26,20))
    cell_end=np.zeros((cell.shape[0] if collect_cells else 0,20))
    for s in prange(ns):
        p=samples[s]
        paths=group_paths(p,final_cover,intensive,settings)
        for i in range(cell.shape[0]):
            g=groups[i]; r=ridx[i]
            gen_coef,area,pop,rho,life=cell[i]
            tau=max(1,int(math.ceil(life*p[5]-1e-10)))
            retires=np.zeros(80)
            stock=0.
            for t in range(26):
                a=paths[g,t]
                raw=gen_coef*a[1]*a[5]
                curtailed=raw*a[10]
                gen=raw-curtailed
                storage_ramp=max(0.,min(1.,(a[0]*100-p[11])/(p[12]-p[11])))
                target=gen*rho*storage_ramp*(1-a[4])*p[13]
                retired=retires[t]
                stock=max(0.,stock-retired)
                added=max(0.,target-stock)
                stock+=added
                if t+tau<80:retires[t+tau]+=added
                direct,charge,discharge,export,loss,soc=storage_day(gen,a[4],stock,settings[1],settings[2])
                delivered=direct+discharge+export
                manufprogress=(t/25.)**p[4]
                pv_factor=p[0]/1000.*(1+(p[1]-1)*manufprogress)
                bat_factor=p[2]*(1+(p[3]-1)*manufprogress)
                # Use commissioning-year uncurtailed yield without global scaling.
                # Remaining service receives no terminal credit.
                pv=gen_coef*a[2]*a[5]*settings[0]*pv_factor if settings[3] else gen*pv_factor
                displaced=delivered*a[3]*p[8]
                cool=pop*a[7]
                ac=pop*a[8]
                roof=area*a[9]
                bat=added*bat_factor
                net=displaced-pv-cool-ac+roof-bat
                vals=np.array([gen/1e9,delivered/1e9,direct/1e9,charge/1e9,
                    discharge/1e9,export/1e9,loss/1e9,curtailed/1e9,
                    displaced/1e12,pv/1e12,cool/1e12,ac/1e12,roof/1e12,bat/1e12,net/1e12,
                    stock/1e6,added/1e6,retired/1e6,area*a[0]/1e6,
                    area*(a[0]-(paths[g,t-1,0] if t else 0.))/1e6])
                for k in range(20):
                    annual[s,r,t,k]+=vals[k]
                    if collect_cells:
                        if k in (15,18):cell_end[i,k]=vals[k]
                        else:cell_end[i,k]+=vals[k]
    return annual,cell_end

def evaluate(inputs, scenarios=None, final_coverage=75., controls=Controls(), collect_cells=False):
    if scenarios is None: scenarios=pd.DataFrame([BASE])
    samples=np.asarray(scenarios[PNAMES],dtype=float)
    if collect_cells and len(samples)!=1:raise ValueError('Cell capture requires one scenario')
    if controls.pv_life<=26:raise ValueError('PV retirement beyond reporting window is required; implement PV queue extension before using shorter lives')
    if not(0<controls.battery_rte<=1 and controls.battery_duration_h>0):raise ValueError('Invalid storage control')
    if np.any(samples[:,12]<=samples[:,11]):raise ValueError('Storage full threshold must exceed onset')
    settings=np.array(list(asdict(controls).values()),dtype=float)
    return _evaluate(samples,float(final_coverage),inputs['cell'],inputs['group'],inputs['region_idx'],inputs['intensive'],len(inputs['regions']),settings,collect_cells)

def crossing_metrics(annual):
    cum=annual[:,:,:,IDX['net_gt']].cumsum(axis=2)
    shape=cum.shape[:2]
    first_down=np.full(shape,np.nan)
    first_up=np.full(shape,np.nan)
    for t in range(1,26):
        prev=cum[:,:,t-1];cur=cum[:,:,t]
        down=(prev>=0)&(cur<0)&~np.isfinite(first_down)
        up=(prev<0)&(cur>=0)&~np.isfinite(first_up)
        f=np.divide(prev,prev-cur,out=np.zeros(shape),where=(prev!=cur))
        first_down[down]=2024+t+f[down]
        first_up[up]=2024+t+f[up]
    return dict(initial_carbon_debt=cum[:,:,0]<0,ever_negative=(cum<0).any(axis=2),
        net_negative_2050=cum[:,:,-1]<0,first_downcrossing_year=first_down,
        first_payback_year=first_up,recovered_by_2050=(cum<0).any(axis=2)&(cum[:,:,-1]>=0))

def annual_frame(inputs, values, final_cover):
    rows=[]
    for r,country in enumerate(inputs['regions']):
        cum=np.zeros(20)
        for t,year in enumerate(YEARS):
            cum+=values[r,t]
            rec={'country_tag':country,'year':int(year),'final_coverage_pct':float(final_cover)}
            for k,name in enumerate(FIELDS):
                rec['annual_'+name]=values[r,t,k]
                if k not in (15,18):rec['cumulative_'+name]=cum[k]
            rec['cumulative_gross_saving_gt']=cum[8]-cum[9]
            rec['cumulative_feedback_gt']=cum[10]+cum[11]-cum[12]+cum[13]
            rows.append(rec)
    return pd.DataFrame(rows)

if __name__ == '__main__':
    raise SystemExit('Run python code/run.py baseline to apply manufacturing-cohort accounting.')
