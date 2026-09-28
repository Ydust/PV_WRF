"""Run the calculation and notebook stages from the project root."""
from pathlib import Path
import argparse,json,os,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
STAGES={
    'baseline':'prepare_baseline.py',
    'uncertainty':'run_uncertainty.py',
    'main-data':'prepare_main_figures.py',
    'selection':'prepare_template_data.py',
    'supplementary-data':'prepare_submission_data.py',
    'figures':'main_figures.ipynb',
    'supplementary-figures':'supplementary_figures.ipynb',
    'verify':'verify.py',
}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['all',*STAGES])
    args=parser.parse_args()
    os.chdir(ROOT)
    for folder in ['output/checks','output/Main_Figure_Data','output/Supplementary_Data']:
        (ROOT/folder).mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('NUMBA_NUM_THREADS','8')
    os.environ.setdefault('MPLBACKEND','Agg')
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'output/checks/mplconfig'))
    for stage in STAGES if args.stage=='all' else [args.stage]:
        print(f'Running {stage}',flush=True)
        path=ROOT/'code'/STAGES[stage]
        if path.suffix=='.ipynb':
            scope={'__name__':'__main__'}
            for cell in json.loads(path.read_text(encoding='utf8'))['cells']:
                if cell['cell_type']=='code':exec(compile(''.join(cell['source']),str(path),'exec'),scope)
        else:subprocess.run([sys.executable,str(path)],cwd=ROOT,check=True)

if __name__=='__main__':main()
