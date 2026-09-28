"""Create explicit electricity-supply scenarios for GREET reference inventories.

Regional projections change each source reference mix by the relative change in
regional fuel shares since 2025. The result is an anchored scenario, not observed
country electricity or a procurement record. No material supply location moves.
"""
from pathlib import Path
import json
import numpy as np
from openpyxl.utils import get_column_letter
import argparse

parser=argparse.ArgumentParser()
parser.add_argument('--projection',choices=['reference','low_cost','high_cost'],default='reference')
args=parser.parse_args()

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'input/inventory'
g1=json.loads((OUT/'greet1_cells.json').read_text(encoding='utf-8'))
g2=json.loads((OUT/'greet2_cells.json').read_text(encoding='utf-8'))
def lookup(data,sheet):return {f'{c}{r["r"]}':v for r in data[sheet] for c,v in r['cells'].items()}
electric=lookup(g1,'Electric');mat=lookup(g2,'Mat_Inputs')
eia=json.loads((OUT/'eia_generation_mix.json').read_text())
fuels=['Liquid fuels','Natural gas','Coal','Other','Nuclear','Hydro','Geothermal','Wind','Solar']
regions={
 'Chile':'Other Americas','South Africa for PGM Production':'Africa','Australia':'Australia and New Zealand',
 'Brazil':'Brazil','Canada':'Canada','China':'China','Finland':'Western Europe','Japan':'Japan',
 'New Caledonia':'Other Asia Pacific','Norway':'Western Europe','Russia':'Russia','Alberta':'Canada',
 'Congo for Cobalt Production':'Africa','Korea':'South Korea','Europe':'Western Europe',
 'EU AL':'Western Europe','China AL':'China','Japan AL':'Japan','Korea AL':'South Korea',
 'Chile Grid for Lithium':'Other Americas','Singapore':'Other Asia Pacific','Indonesia':'Other Asia Pacific',
 'Papua New Guinea for Nickel Production':'Other Asia Pacific','Argentina':'Other Americas','Bahrain':'Middle East',
 'UAE':'Middle East','Venezuela':'Other Americas','World':'World','France':'Western Europe',
 'Germany':'Western Europe','India':'India','Jamaica':'Other Americas','Kazakhstan':'Eastern Europe and Eurasia',
 'Poland':'Western Europe','Ukraine':'Eastern Europe and Eurasia','Philippines':'Other Asia Pacific',
 'Mexico':'Mexico','U.S.: WECC':'United States','U.S.: SERC':'United States','South Africa':'Africa',
 'Uzbekistan':'Eastern Europe and Eurasia','Netherlands':'Western Europe','United Kingdom':'Western Europe',
 'APAC region for solar PV cell production':'Other Asia Pacific',
 'APAC region for solar PV panel production':'Other Asia Pacific','Spain':'Western Europe'}

def trajectory(region,year):
    records=sorted([r for r in eia if r['case']==args.projection and r['region']==region],key=lambda x:x['year'])
    assert records,region
    values=[]
    for f in fuels:
        values.append(np.interp(year,[r['year'] for r in records],
                      [r['generation_billion_kWh'][f]/r['generation_billion_kWh']['Net generation to grid'] for r in records]))
    a=np.asarray(values);assert abs(a.sum()-1)<1e-9
    return a

def change(base,region,year,procurement):
    future=trajectory(region,year);start=trajectory(region,2025)
    # A proportional anchored scenario cannot introduce a source absent from its
    # reference mix. Zero-reference regional technologies retain their native
    # contribution; additional wind procurement is represented separately.
    a=base*np.divide(future,start,out=np.ones(9),where=start>0)
    a=a/a.sum();a*=1-procurement;a[7]+=procurement
    assert abs(a.sum()-1)<1e-10 and (a>=0).all()
    return a

def source_mix(col):
    primary=[float(electric.get(f'{col}{row}',0)) for row in range(228,234)]
    # GREET stores foreign geothermal/wind/solar shares as absolute shares.
    other=[float(electric.get(f'{col}{row}',0)) for row in [266,267,268]]
    a=np.array(primary+other)
    # Some native backgrounds have incomplete or inconsistent detailed renewable
    # splits. Preserve their total Other share and normalize only that subdivision.
    total=float(electric.get(f'{col}234',0))
    if sum(other)>0:a[6:]*=total/sum(other)
    elif total>1e-10:a[7]=total
    if abs(a.sum()-1)>1e-8:raise ValueError((col,a.sum()))
    return a

cases=[];registry=[]
for family in (['frozen','regional_transition','regional_transition_procurement'] if args.projection=='reference' else [args.projection]):
    for year in ([2025] if family=='frozen' else range(2025,2051)):
        p=0.5*(year-2025)/25 if family.endswith('_procurement') else 0.
        changes=[]
        for i in range(6,56):
            col=get_column_letter(i);name=str(electric.get(f'{col}225','')).strip()
            if name not in regions:continue
            baseline=source_mix(col)
            a=change(baseline,regions[name],2025 if name.endswith(' AL') else year,p)
            for row,value in zip(range(228,234),a[:6]):changes.append(['energy','Electric',f'{col}{row}',float(value)])
            changes.append(['energy','Electric',f'{col}234',float(a[6:].sum())])
            for row,value in zip([266,267,268],a[6:]):changes.append(['energy','Electric',f'{col}{row}',float(value)])
            changes.append(['energy','Electric',f'{col}269',0.])
            if family=='frozen':registry.append({'greet_region':name,'greet_column':col,'eia_projection_region':regions[name],
                'source_reference_year':electric.get(f'{col}227'),'mapping':'relative regional trend applied to native supplier mix'})
        # U.S. stationary mix: renewable shares are conditional on Others.
        b=np.array([electric[f'D{r}'] for r in [60,64,69,72,75]]+
                   [electric['D76']*electric[f'F{r}'] for r in [77,78,79,80]],dtype=float)
        b[3]+=electric['D76']*electric['F81']
        a=change(b,'United States',year,p)
        for row,value in zip([60,64,69,72,75],a[:5]):changes.append(['energy','Electric',f'D{row}',float(value)])
        total=a[5:].sum();changes.append(['energy','Electric','D76',float(total)])
        for row,value in zip([77,78,79,80],a[5:]/total):changes.append(['energy','Electric',f'F{row}',float(value)])
        changes.append(['energy','Electric','F81',0.])
        # Dedicated smelter reference mixes remain distinct from national grids.
        # Only the additional procurement case modifies them; no unsupported
        # equivalence between national transition and captive smelter power.
        for col in ['D','E','F','O','P','Q']:
            base=np.array([mat[f'{col}{row}'] for row in range(411,418)],dtype=float)
            a=base*(1-p);a[-1]+=p
            for row,value in zip(range(411,418),a):changes.append(['materials','Mat_Inputs',f'{col}{row}',float(value)])
        cases.append({'case':family,'production_year':year,'additional_wind_procurement':p,'changes':changes})
config={'status':'Manuscript supply scenarios using the GREET reference inventory',
        'electricity_infrastructure':'included using GREET A15=Yes',
        'technology':'GREET source reference inventories fixed; no extra efficiency multiplier',
        'zero_reference_sources':'Relative scaling holds the native contribution where the EIA 2025 source share is zero. Technologies absent from native mixes do not emerge in the regional-only scenario.',
        'procurement':'Explicit sensitivity ramp from zero in 2025 to 50% additional wind electricity in 2050; not a forecast or observed purchase.',
        'mapping':registry,'cases':cases}
config['eia_projection']=args.projection
filename='greet_case_inputs.json' if args.projection=='reference' else f'greet_{args.projection}_inputs.json'
(OUT/filename).write_text(json.dumps(config,indent=2),encoding='utf-8')
print(f'Prepared {len(cases)} cases and {len(registry)} supplier electricity-region mappings')
