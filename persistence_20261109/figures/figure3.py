"""Render Figure 3 from the registered parameter-level paired medians."""
from decimal import Decimal, ROUND_HALF_UP
from hashlib import file_digest
import json
import os
from pathlib import Path
import sys

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnnotationBbox, DrawingArea
from matplotlib.patches import Wedge
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
from release_paths import require_matplotlib_panel_alignment

SOURCE = ROOT / 'data/figure3/parameter_time_and_state_response.csv'
CONTINENT_SOURCE = ROOT / 'data/figure3/scenario_dominant_continent.csv'
FIG, QA = ROOT / 'build/figures', ROOT / 'build/qa'
WIDTH = 180
HEIGHT = 146
LABEL_PT = 5.8
POINT_AREA = 2.85
INK, MUTED, RULE = '#152831', '#425762', '#81929B'
BACKGROUNDS = (
    ('CP', 'Current Policies'), ('NDC', 'NDCs'), ('B2C', 'Below 2°C'),
    ('NZ2050', 'Net Zero 2050'), ('LD', 'Low Demand'),
)
GROUPS = (
    ('formed_then_lost', 'GTL'),
    ('opening_benefit_then_lost', 'IBL'),
)
FAMILIES = (('technology', 'Technology', 32), ('storage', 'Storage', 19), ('export', 'Export', 3))
TICKS = [-50, -10, -1, 0, 1, 10, 50]
CONTINENT_COLORS = {'AF':'#B56906','AO':'#087E6E','EU':'#285D9E','NA':'#C43257'}
CONTINENT_LABELS = ('Africa','Asia & Oceania','Europe','North America')
BENCHMARK_YEAR = 2050
BENCHMARK_DASH = (0,(3,2))


def separate_circles(ax, values, areas, row):
    """Retain exact x positions and resolve collisions in display points."""
    pt_per_px = 72/ax.figure.dpi
    x_points = ax.get_xaxis_transform().transform(np.column_stack((values, np.zeros(len(values)))))[:,0]*pt_per_px
    row_height = ax.bbox.height*pt_per_px/3
    radii = np.sqrt(areas)/2
    offsets = np.r_[0., (np.arange(1, int(row_height/.24)+1)[:, None]*[.12,-.12]).ravel()]
    chosen = np.zeros(len(values))
    placed = []
    stacks = [np.flatnonzero(values==value) for value in np.unique(values)]
    stacks.sort(key=lambda indices:-radii[indices].sum())
    gap = .35
    for indices in stacks:
        diameters = 2*radii[indices]
        height = diameters.sum()+gap*(len(indices)-1)
        centers = np.r_[0,np.cumsum(diameters[:-1]+gap)]+radii[indices]-height/2
        for offset in offsets:
            positions = centers+offset
            if np.any(abs(positions)+radii[indices] > .47*row_height):
                continue
            distance = np.hypot(x_points[indices,None]-x_points[placed],
                                positions[:,None]-chosen[placed])
            if np.all(distance >= radii[indices,None]+radii[placed]+gap):
                chosen[indices] = positions
                placed.extend(indices)
                break
        else:
            raise ValueError(f'Circles at {values[indices[0]]} years cannot fit in row {row}.')
    return row+chosen/row_height


def main():
    mpl.rcParams.update({
        'font.family':['Arial','DejaVu Sans'], 'font.size':LABEL_PT, 'text.color':INK,
        'xtick.labelsize':LABEL_PT, 'ytick.labelsize':LABEL_PT, 'legend.fontsize':LABEL_PT,
        'axes.linewidth':.55, 'pdf.fonttype':42, 'svg.fonttype':'none',
    })
    data = pd.read_csv(SOURCE)
    assert len(data) == 540 and data.median_paired_delta_T.notna().sum() == 539
    continent = pd.read_csv(CONTINENT_SOURCE,keep_default_na=False)
    data = data.merge(continent[['background','role','family','scenario_id','dominant_continent']],
                      on=['background','role','family','scenario_id'],validate='one_to_one')
    assert len(data)==540 and data.loc[data.median_paired_delta_T.notna(),'dominant_continent'].ne('').all()
    assert {code for group in data.dominant_continent if group for code in group.split('+')}==set(CONTINENT_COLORS)
    fig = plt.figure(figsize=(WIDTH/25.4,HEIGHT/25.4), facecolor='white')

    def label(x, y, value, **kwargs):
        ha = kwargs.pop('ha','center')
        return fig.text(x/WIDTH,y/HEIGHT,value,va='center',ha=ha,**kwargs)

    xs, panel_width = (30,103), 65
    axes, panel_counts, frequencies, reference_groups = [], [], [], []
    sizes = (1, 5, 15, 25)
    handles = [Line2D([],[],linestyle='none')] + [
        Line2D([],[],marker='o',ls='none',c=MUTED,mew=0,ms=np.sqrt(POINT_AREA*n)) for n in sizes
    ]
    handles.append(Line2D([],[],color='black',ls=BENCHMARK_DASH,lw=.7))
    legend_y = (1-4/HEIGHT,1-11.1/HEIGHT)
    frequency_legend = fig.legend(
        handles,['Scenarios per circle',*map(str,sizes),'2050 relative to REF'],loc='center',
        bbox_to_anchor=(.5,legend_y[0]),frameon=False,ncols=6,
        handlelength=2.15,handletextpad=.42,columnspacing=1.18,borderpad=0,
    )
    continent_handles = [Line2D([],[],linestyle='none')] + [
        Line2D([],[],marker='o',ls='none',c=color,mew=0,ms=5.7) for color in CONTINENT_COLORS.values()
    ]
    continent_legend = fig.legend(
        continent_handles,['Most represented continent',*CONTINENT_LABELS],loc='center',
        bbox_to_anchor=(.5,legend_y[1]),frameon=False,ncols=5,
        handlelength=1.25,handletextpad=.55,columnspacing=1.25,borderpad=0,
    )
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for legend,y in zip((frequency_legend,continent_legend),legend_y,strict=True):
        texts = legend.get_texts()
        left = texts[0].get_window_extent(renderer).x0
        right = texts[-1].get_window_extent(renderer).x1
        center = (left+right)/(2*fig.bbox.width)
        legend.set_bbox_to_anchor((1-center,y),transform=fig.transFigure)
    for x, (_, heading) in zip(xs,GROUPS,strict=True):
        label(x+panel_width/2,126.1,heading,weight='bold')
    for row,(background, pathway) in enumerate(BACKGROUNDS):
        y = 102-22*row
        for col,(x, (role, _)) in enumerate(zip(xs,GROUPS,strict=True)):
            sub = data[data.background.eq(background)&data.role.eq(role)]
            n, = sub.n_REF.unique()
            ref, = sub.REF_year_median.unique()
            year = int(Decimal(str(ref)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            panel = chr(97+2*row+col)
            ax = fig.add_axes((x/WIDTH,y/HEIGHT,panel_width/WIDTH,15.6/HEIGHT))
            axes.append(ax)
            ax.spines[['top','right','bottom','left']].set_visible(True)
            ax.set_xscale('symlog',linthresh=1,linscale=.8)
            ax.set(xlim=(-80,80),ylim=(2.5,-.5))
            tick_labels = ['0' if t==0 else f'{t:+g}'.replace('-','−') for t in TICKS]
            ax.set_xticks(TICKS,tick_labels)
            ax.minorticks_off()
            ax.tick_params(axis='x',length=2,width=.55,pad=1.8,labelbottom=row==4)
            ax.axvline(0,c=RULE,ls=(0,(2.5,2.5)),lw=.65,zorder=1)
            benchmark = BENCHMARK_YEAR-ref
            ax.axvline(benchmark,c='black',ls=BENCHMARK_DASH,lw=.7,zorder=2)
            x_pt = ax.get_xaxis_transform().transform((benchmark,0))[0]*72/fig.dpi
            reference_groups.append({'panel':panel,'background':background,'role':role,
                                     'countries':int(n),'REF_year_median':float(ref),'REF_year_label':year,
                                     'benchmark_delta_years':float(benchmark),'benchmark_x_pt':float(x_pt)})
            labels = []
            for i,(family,family_label,total) in enumerate(FAMILIES):
                records = sub.loc[sub.family.eq(family),['median_paired_delta_T','dominant_continent']]
                paired = records.dropna(subset='median_paired_delta_T').copy()
                assert len(records)==total and paired.median_paired_delta_T.abs().lt(80).all()
                counts = paired.groupby(['median_paired_delta_T','dominant_continent']).size()
                values = counts.index.get_level_values('median_paired_delta_T').to_numpy()
                labels.append(family_label)
                areas = counts.to_numpy()*POINT_AREA
                positions = separate_circles(ax,values,areas,i)
                dominant = counts.index.get_level_values('dominant_continent').to_numpy()
                for code,color in CONTINENT_COLORS.items():
                    solid = dominant==code
                    ax.scatter(values[solid],positions[solid],s=areas[solid],c=color,linewidths=0,zorder=3)
                for x_pos,y_pos,area,codes in zip(values,positions,areas,dominant,strict=True):
                    if '+' in codes:
                        radius = np.sqrt(area)/2
                        circle = DrawingArea(2*radius,2*radius)
                        groups_at_maximum = codes.split('+')
                        edges = np.linspace(90,450,len(groups_at_maximum)+1)
                        for code,start,stop in zip(groups_at_maximum,edges[:-1],edges[1:],strict=True):
                            circle.add_artist(Wedge((radius,radius),radius,start,stop,
                                                    facecolor=CONTINENT_COLORS[code],edgecolor='none'))
                        ax.add_artist(AnnotationBbox(circle,(x_pos,y_pos),frameon=False,pad=0,zorder=3))
                group = {'background':background,'role':role,'family':family}
                panel_counts.append({**group,'plotted':len(paired),'source_parameters':total})
                frequencies.extend({**group,'median_years':float(value),'dominant_continent':codes,
                                    'scenarios':int(count)} for (value,codes),count in counts.items())
            ax.set_yticks(range(3),labels if col==0 else ['']*3)
            ax.tick_params(axis='y',length=0,pad=3)
            label(x-3.5,y+18.6,panel,weight='bold',ha='left')
            if col==0:
                label(x+1,y+18.6,pathway,weight='bold',ha='left')
    label(xs[0],4.8,'← Earlier loss',ha='left',color=MUTED)
    label(99,4.8,'Paired change in first-loss year, ΔT (years)')
    label(xs[-1]+panel_width,4.8,'Later loss →',ha='right',color=MUTED)
    ids = list('abcdefghij')
    require_matplotlib_panel_alignment(
        fig,axes=axes,panel_ids=ids,row_groups=[ids[i:i+2] for i in range(0,10,2)],
        column_groups=[ids[::2],ids[1::2]],tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True,
        json_out=QA/'Figure3_en.panels.alignment.json',
    )
    fig.savefig(FIG/'Figure3_en.pdf')
    fig.savefig(FIG/'Figure3_en.svg')
    fig.savefig(FIG/'Figure3_en.tiff',dpi=600,pil_kwargs={'compression':'tiff_lzw'})
    fig.savefig(FIG/'Figure3_en.png',dpi=300)
    plt.close(fig)
    with SOURCE.open('rb') as stream:
        digest = file_digest(stream,'sha256').hexdigest()
    facts = {
        'parameters_total':len(data), 'parameters_plotted':sum(p['plotted'] for p in panel_counts),
        'panels':panel_counts, 'frequencies':frequencies, 'reference_groups':reference_groups,
        'colors':CONTINENT_COLORS, 'source_sha256':digest,
        'benchmark_year':BENCHMARK_YEAR,
    }
    (QA/'Figure3_en.data.json').write_text(json.dumps(facts,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
