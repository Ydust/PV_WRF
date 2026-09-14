from pathlib import Path
import sys,os
R=Path(__file__).resolve().parent;BASE=R
sys.path.insert(0,str(BASE))
from paths import DATA_ROOT,WORK,RESULTS,OUTPUT_ROOT
INPUT=DATA_ROOT/'grids'
S=BASE;D=WORK/'Source_Data';Q=RESULTS/'checks';O=D
for p in [D,Q,D/'input_snapshot']:p.mkdir(parents=True,exist_ok=True)
os.environ.setdefault('NUMBA_NUM_THREADS','8')
os.environ.setdefault('NUMBA_CACHE_DIR',str(WORK/'numba'))
sys.path.insert(0,str(S))
