"""Command-line interface for calculation and plotting."""
from pathlib import Path
import argparse, os, shutil, subprocess, sys, json
R=Path(__file__).resolve().parent
from paths import DATA_ROOT,WORK,RESULTS,OUTPUT_ROOT
def call(script,*args):
    subprocess.run([sys.executable,str(R/script),*args],cwd=R,check=True)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('mode',choices=['baseline','figures','full','rules','supplementary','verify'])
    args=ap.parse_args()
    os.environ.setdefault('NUMBA_NUM_THREADS','8')
    for d in [WORK/'Source_Data',RESULTS/'checks',RESULTS/'figures',RESULTS/'checks/figures']:d.mkdir(parents=True,exist_ok=True)
    # Copy reference inputs to a separate working directory.
    if not (DATA_ROOT/'grids').is_dir():
        raise SystemExit('Missing grid inputs. Set PV_WRF_DATA_ROOT or populate the input directory.')
    if not (WORK/'Source_Data/scenario_parameters.csv').exists():
        shutil.copytree(DATA_ROOT/'parameters',WORK/'Source_Data',dirs_exist_ok=True)
        shutil.copy2(DATA_ROOT/'parameters/scenario_parameters_41.csv',WORK/'Source_Data/scenario_parameters.csv')
    if args.mode in ['baseline','full']:
        call('recalculate.py',*(['--ensemble'] if args.mode=='full' else []))
    if args.mode in ['rules','full']:call('solve_rules.py')
    if args.mode=='full':
        call('prepare_lmh.py')
        call('supplementary.py')
    if args.mode=='supplementary':call('supplementary.py')
    if args.mode in ['figures','full']:
        notebook = json.loads((R / 'main_figures.ipynb').read_text(encoding='utf-8'))
        namespace = {'__name__': '__main__', '__file__': str(R / 'main_figures.ipynb')}
        for index, cell in enumerate(notebook['cells']):
            if cell['cell_type'] == 'code':
                text = ''.join(cell['source'])
                exec(compile(text, f'main_figures.ipynb:cell_{index}', 'exec'), namespace)
    if args.mode in ['full','verify']:call('verify_results.py')
if __name__=='__main__':main()
