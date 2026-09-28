"""Apply independently resolved production factors to the existing energy ledger.

Factors are kg CO2e per m2 of module area, kWp of inverter/electrical
capacity, or kWh of nameplate storage. Production after 2050 is excluded;
the remaining service of production through 2050 is retained for reconciliation.
"""
from dataclasses import dataclass
import numpy as np

YEARS = np.arange(2025, 2051)
PV_UNITS = {'module': 'm2', 'freight': 'm2', 'mounting': 'm2',
            'electrical': 'kwp', 'combined_bos': 'kwp', 'inverter': 'kwp'}

@dataclass(frozen=True)
class ProductionFactors:
    pv: dict
    battery: np.ndarray
    storage_capacity_basis: str = 'nameplate_kwh'
    storage_auxiliary: np.ndarray | None = None

    def validate(self):
        if self.storage_capacity_basis != 'nameplate_kwh':
            raise ValueError('Storage factors must be converted to nameplate capacity first')
        if 'combined_bos' in self.pv and ({'mounting', 'electrical'} & self.pv.keys()):
            raise ValueError('Combined and separate BOS would double count production')
        if not {'module', 'inverter'}.issubset(self.pv):
            raise ValueError('Module and inverter factors are required')
        if not ('combined_bos' in self.pv or {'mounting','electrical'}.issubset(self.pv)):
            raise ValueError('Complete BOS factors are required')
        if not self.pv.keys() <= PV_UNITS.keys():
            raise ValueError('Unknown component or functional unit')
        all_factors={**self.pv, 'battery': self.battery}
        if self.storage_auxiliary is not None:all_factors['storage_auxiliary']=self.storage_auxiliary
        for name, a in all_factors.items():
            a = np.asarray(a, dtype=float)
            if a.shape != (26,) or not np.isfinite(a).all() or (a < 0).any():
                raise ValueError(f'{name}: 26 finite nonnegative annual factors required')

def allocate(annual, factors, module_life=28, inverter_life=15):
    factors.validate()
    annual = np.asarray(annual, dtype=float)
    if annual.ndim != 3 or annual.shape[1:] != (26,20) or not np.isfinite(annual).all():
        raise ValueError('Expected a finite region x 26 years x 20 fields ledger')
    if module_life <= 26 or not 0 < inverter_life < module_life:
        raise ValueError('This energy ledger has no module retirement before 2050')
    n = len(annual); horizon = 26 + module_life - 1
    area = annual[:,:,19] * 1e6
    kwp = area * (.20 * (1 + .0035 * (YEARS - 2020)))[None,:]
    generation = np.zeros((n,26,horizon))
    for t in range(26):
        denominator = kwp[:,:t+1].sum(1)
        if np.any((annual[:,t,0] > 0) & (denominator <= 0)):
            raise ValueError('Generation without producing cohorts')
        fractions = np.divide(kwp[:,:t+1], denominator[:,None],
                              out=np.zeros_like(kwp[:,:t+1]), where=denominator[:,None]>0)
        generation[:,:t+1,t] = annual[:,t,0,None] * fractions
    for vintage in range(26):
        generation[:,vintage,26:vintage+module_life] = generation[:,vintage,25,None]
    np.testing.assert_allclose(generation[:,:,:26].sum(1),annual[:,:,0],rtol=1e-12,atol=1e-8)
    events = {k: np.zeros((n,horizon)) for k in factors.pv}
    services = {k: np.zeros((n,horizon)) for k in factors.pv}
    for component, values in factors.pv.items():
        physical = area if PV_UNITS[component] == 'm2' else kwp
        lifetime = inverter_life if component == 'inverter' else module_life
        for vintage in range(26):
            for age in range(0,module_life,lifetime):
                production = vintage + age
                if production >= 26:
                    continue
                # Replacement uses its actual production-year factor.
                burden = physical[:,vintage] * values[production] / 1e12
                events[component][:,production] += burden
                stop = min(production+lifetime,vintage+module_life)
                g = generation[:,vintage,production:stop]
                total = g.sum(1)
                if np.any((burden>0) & (total<=0)):
                    raise ValueError('Positive production burden without service')
                shares = np.divide(g,total[:,None],out=np.zeros_like(g),where=total[:,None]>0)
                services[component][:,production:stop] += burden[:,None]*shares
        np.testing.assert_allclose(events[component].sum(1),services[component].sum(1),rtol=2e-12,atol=1e-12)
    battery = annual[:,:,16] * 1e6 * np.asarray(factors.battery)[None,:] / 1e12
    auxiliary=np.zeros_like(battery)
    if factors.storage_auxiliary is not None:
        # Enclosures/racks persist for 30 years in the GREET reference system,
        # beyond this 26-year window. Retain/reuse installed enclosure capacity
        # when only the battery module is replaced or storage demand falls.
        peak=np.maximum.accumulate(annual[:,:,15],axis=1)
        expansion=np.diff(peak,axis=1,prepend=np.zeros((n,1)))
        auxiliary=expansion*1e6*np.asarray(factors.storage_auxiliary)[None,:]/1e12
        battery=battery+auxiliary
    pv_event = sum(events.values())[:,:26]
    pv_service = sum(services.values())[:,:26]
    result = {}
    for name, pv in [('event',pv_event),('service',pv_service)]:
        out = annual.copy()
        out[:,:,9] = pv
        out[:,:,13] = battery
        # Replace both old footprints exactly once.
        out[:,:,14] = annual[:,:,14] + annual[:,:,9] + annual[:,:,13] - pv - battery
        result[name] = out
    return {**result,'component_events':events,'component_service':services,'storage_auxiliary_gt':auxiliary,
            'post2050_service_gt':{k:v[:,26:].sum(1) for k,v in services.items()}}
