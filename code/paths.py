from pathlib import Path
import os
ROOT=Path(__file__).resolve().parent.parent
DATA_ROOT=Path(os.environ.get('PV_WRF_DATA_ROOT',str(ROOT/'input'))).expanduser().resolve()
OUTPUT_ROOT=Path(os.environ.get('PV_WRF_OUTPUT_ROOT',str(ROOT/'output'))).expanduser().resolve()
WORK=OUTPUT_ROOT/'work'
RESULTS=OUTPUT_ROOT
