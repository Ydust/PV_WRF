"""Fast production-vintage accounting for paired main-figure calculations."""
import numpy as np
from numba import njit

@njit(cache=True)
def service_account(raw, factors, battery_scale=1.0):
    # Columns: module+mounting+freight / m2, electrical / kWp,
    # inverter / kWp / event, battery / kWh, housing / kWh.
    out=raw.copy()
    for r in range(raw.shape[0]):
        area=raw[r,:,19]*1e6
        kwp=np.empty(26);q=np.empty(26)
        total=0.
        for t in range(26):
            kwp[t]=area[t]*.20*(1+.0035*(2025+t-2020))
            total+=kwp[t]
            q[t]=raw[r,t,0]/total if total>0 else 0.
        pv=np.zeros(26)
        for vintage in range(26):
            for component in range(3):
                life=15 if component==2 else 28
                amount=area[vintage] if component==0 else kwp[vintage]
                for age in range(0,28,life):
                    production=vintage+age
                    if production>=26:continue
                    stop=min(production+life,vintage+28)
                    denom=0.
                    for y in range(production,stop):denom+=q[min(y,25)]
                    burden=amount*factors[production,component]/1e12
                    if denom>0:
                        for y in range(production,min(stop,26)):
                            pv[y]+=burden*q[y]/denom
        peak=0.
        for t in range(26):
            expansion=max(0.,raw[r,t,15]-peak)
            peak=max(peak,raw[r,t,15])
            battery=(raw[r,t,16]*factors[t,3]*battery_scale+expansion*factors[t,4])/1e6
            out[r,t,9]=pv[t];out[r,t,13]=battery
            out[r,t,14]=raw[r,t,14]+raw[r,t,9]+raw[r,t,13]-pv[t]-battery
    return out
