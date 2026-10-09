"""Reproduce numerical outputs or execute figure notebooks."""
from pathlib import Path
import argparse,json,os,shutil
import numpy as np
import pandas as pd
from paths import ROOT

def notebook(name):
    os.chdir(ROOT)
    scope={'__name__':'__main__'}
    for cell in json.loads((ROOT/'code'/name).read_text(encoding='utf-8'))['cells']:
        if cell['cell_type']=='code':exec(compile(''.join(cell['source']),name,'exec'),scope)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['baseline','all','figures','supplementary-figures'],default='baseline');a=ap.parse_args()
    if a.mode=='figures':notebook('main_figures.ipynb');return
    if a.mode=='supplementary-figures':notebook('supplementary_figures.ipynb');return
    import prepare_main_figure_data as f
    print("Numerical baseline/all modes retain the September model; current submission graphics use frozen October source tables.")
    x=f.m.prepare_inputs()
    for cov in [50,75]:np.save(ROOT/f'output/reference_{cov}.npy',f.m.evaluate(x,final_coverage=cov)[0][0])
    if a.mode=='all':f.physical_cache()
    f.main(baseline_only=a.mode=='baseline')
    if a.mode=='all':
        f.procurement_contrasts();f.strategy_tradeoffs()
        import prepare_final_supplement as s
        s.main()
        for n in ['diagnostic_cells','diagnostic_trend']:shutil.copy2(s.SD/(n+'.csv'),f.D/(n+'.csv'))
        full=pd.read_csv(f.D/'annual_reference.csv').query('final_coverage_pct==75')
        red=pd.read_csv(s.SD/'reduced_annual.csv')[['country_tag','year','cumulative_net_gt']].rename(columns={'cumulative_net_gt':'cumulative_reduced_net_gt'})
        full.merge(red,on=['country_tag','year'],validate='one_to_one').to_csv(f.D/'time_paths.csv',index=False)
    print('Completed',a.mode)

if __name__=='__main__':main()
