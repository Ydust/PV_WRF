"""Calculate physical ledgers and the reference manufacturing account."""
from pathlib import Path
import numpy as np
import model as m
from cohort_accounting import account, updated_cases

ROOT=Path(__file__).resolve().parents[1]

def main():
    x=m.prepare_inputs()
    for cover in [50,75]:
        raw=m.evaluate(x,final_coverage=cover)[0][0]
        np.save(ROOT/f'output/reference_{cover}.npy',raw)
        result=account(raw,updated_cases()[3])['service']
        total=result[:,:,14].sum()
        print(f'{cover}% coverage: {total:.12f} Gt CO2e net mitigation',flush=True)
        if cover==75:np.testing.assert_allclose(total,117.61190473366243,rtol=0,atol=1e-9)

if __name__=='__main__':main()
