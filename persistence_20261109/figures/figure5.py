"""Render the registered English Figure 5 with a shared cross for the export conditions."""
from hashlib import file_digest
from pathlib import Path
import json
import os
import sys

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import NullLocator
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
from release_paths import require_matplotlib_panel_alignment

WIDTH_MM = 156
QA, OUT = ROOT / 'build/qa', ROOT / 'build/figures'
for folder in (QA, OUT):
    folder.mkdir(parents=True, exist_ok=True)
ROLES = ('formed_then_lost', 'opening_benefit_then_lost')
EX = ('UNLIMITED', 'CAP50', 'CAP0')
EX_COLOR = ('#20282E', '#007F63', '#783DB2')
STATE_COLORS = ('#24628B', '#AC501D')
INK, MUTED, RULE = '#152831', '#425762', '#81929B'
GRID = '#E7EDF0'
SOURCE = ROOT / 'data/figure5'
HASHES = {}


def source(path):
    with path.open('rb') as stream:
        HASHES[path.as_posix()] = file_digest(stream, 'sha256').hexdigest()
    return path


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


class Layout:
    def __init__(self, number, height, language):
        self.number, self.height, self.language = number, height, language
        self.stem = f'Figure{number}_{language}'
        family = ['Arial', 'DejaVu Sans'] if language == 'en' else ['Microsoft YaHei', 'DejaVu Sans', 'Arial']
        mpl.rcParams.update({'font.family': family,
            'font.size': 6.3, 'text.color': INK, 'axes.labelcolor': INK,
            'axes.labelsize': 6.5, 'xtick.labelsize': 5.8, 'ytick.labelsize': 5.8,
            'axes.linewidth': .55, 'svg.fonttype': 'none', 'pdf.fonttype': 42,
            'legend.frameon': False, 'axes.unicode_minus': True, 'hatch.linewidth': .19})
        self.fig = plt.figure(figsize=(WIDTH_MM / 25.4, height / 25.4), facecolor='white')

    def label(self, en, zh):
        return en if self.language == 'en' else zh

    def text(self, x, y, text, size=6.5, *, align='center', color=INK, weight='normal', angle=0):
        return self.fig.text(x / WIDTH_MM, y / self.height, text, ha=align, va='center',
                             fontsize=size, color=color, weight=weight, rotation=angle, rotation_mode='anchor')

    def axes(self, x, y, width, height, **kwargs):
        return self.fig.add_axes((x / WIDTH_MM, y / self.height, width / WIDTH_MM, height / self.height), **kwargs)

    def letter(self, x, y, char):
        self.text(x, y, char, 8, align='left', weight='bold')

    def legend(self, x, y, handles, labels, cols, *, size=6, **kwargs):
        loc = kwargs.pop('loc', 'center')
        return self.fig.legend(handles, labels, bbox_to_anchor=(x / WIDTH_MM, y / self.height),
            loc=loc, ncol=cols, fontsize=size, handlelength=1.45,
            columnspacing=1.2, handletextpad=.45, borderaxespad=0, **kwargs)

    def alignment(self, axes, ids, rows, cols, *, exemptions=()):
        require_matplotlib_panel_alignment(self.fig, axes=axes, panel_ids=list(ids),
            row_groups=rows, column_groups=cols, json_out=QA / f'{self.stem}.panels.alignment.json',
            exemptions=exemptions, tolerance_pt=1.5, gutter_tolerance_pt=1.5, strict=True)

    def finish(self, facts):
        self.fig.savefig(OUT / f'{self.stem}.pdf', dpi=600)
        self.fig.savefig(OUT / f'{self.stem}.svg', dpi=600)
        self.fig.savefig(OUT / f'{self.stem}.tiff', dpi=600, pil_kwargs={'compression': 'tiff_lzw'})
        self.fig.savefig(OUT / f'{self.stem}.png', dpi=300)
        plt.close(self.fig)
        save_json(QA / f'{self.stem}.data.json', facts)


def clean(ax):
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(length=2, width=.55, pad=1.8)
    ax.minorticks_off()
    ax.set_axisbelow(True)


def export_labels(layout):
    return (layout.label('Unrestricted export','外送不限'),
            layout.label('50% export capacity','外送能力50%'),layout.label('No export','禁止外送'))


def figure5(language):
    l = Layout(5, 152, language)
    raw = pd.read_parquet(source(SOURCE / 'figure5_all_fixed_country_records.parquet'))
    timing, process = pd.read_csv(source(SOURCE / 'figure5_timing_coverage.csv')), pd.read_csv(source(SOURCE / 'figure5_full_group_process.csv'))
    groups = ('配储比例','储能容量','运行启用程度')
    group_titles = ('Storage adoption','Storage capacity','Storage use') if language=='en' else groups
    columns = ('contribution_A','contribution_newManufacturing','contribution_replacementManufacturing','contribution_treatment','contribution_gridAux')
    colors = ('#276F9C','#D8A52C','#BA3D4B','#559044','#5A646D')
    component_labels = ('Avoided emissions','New manufacturing','Replacement','End of life','Grid auxiliary') if language=='en' else ('避免排放','新增制造','更换制造','退役处置','电网辅助用电')
    assert len(raw)==16710 and raw.paired_events_observed.sum()==12572
    assert raw.loc[raw['export'].eq('UNLIMITED'),'common_event_all_three'].sum()==2103
    xs, ys, side = (22,67,112),(104.2,59.7,7.3),38
    plot_center = (xs[0]+xs[-1]+side)/2
    axes, lower, counts = [],[],[]
    crosses = [Line2D([],[],color=c,marker='+',linestyle='none',markersize=6.2,
                      markeredgewidth=1.05) for c in EX_COLOR]
    l.legend(WIDTH_MM/2,148.85,crosses,export_labels(l),3,borderpad=0)
    for row,(role,y) in enumerate(zip(ROLES,ys[:2],strict=True)):
        l.text(6.1,y+side/2,l.label('Reduction in cumulative\nnet emissions (Mt CO₂e)',
                                  '累计净排放减少量\n（Mt CO₂e）'),6.4,angle=90)
        l.text(11,y+side+2.65,('GTL','IBL')[row],6.4,align='left',weight='bold',color=STATE_COLORS[row])
        for col,(group,x) in enumerate(zip(groups,xs)):
            a = l.axes(x,y,side,side)
            axes.append(a)
            clean(a)
            a.set(xlim=(-80,80),ylim=(-10000,10000),yscale='symlog')
            a.set_yscale('symlog',linthresh=.01)
            a.set_xticks([-80,-40,0,40,80]);a.set_yticks([-1000,-10,-.1,0,.1,10,1000],['−1000','−10','−0.1','0','0.1','10','1000'])
            a.xaxis.set_minor_locator(NullLocator());a.yaxis.set_minor_locator(NullLocator())
            a.tick_params(labelleft=col==0,labelbottom=row==1)
            a.grid(axis='y',c=GRID,lw=.45)
            a.axhline(0,c=RULE,lw=.55,zorder=0);a.axvline(0,c=RULE,lw=.55,zorder=0)
            sel = raw[raw.role.eq(role)&raw.subgroup.eq(group)]
            points = sel[sel.paired_events_observed]
            assert points.paired_delta_T.abs().max()<=80 and points.carbon_gain_Mt.abs().max()<=10000
            a.scatter(points.paired_delta_T,points.carbon_gain_Mt,s=4,facecolors='none',edgecolors='#83919A',linewidths=.24,alpha=.29,zorder=2)
            for ex,c in zip(EX,EX_COLOR,strict=True):
                record = timing[timing.role.eq(role)&timing.subgroup.eq(group)&timing['export'].eq(ex)].iloc[0]
                x_med,y_med = record.x_median,record.y_median
                a.errorbar(x_med,y_med,xerr=[[x_med-record.x_q25],[record.x_q75-x_med]],
                           yerr=[[y_med-record.y_q25],[record.y_q75-y_med]],fmt='none',
                           color=c,elinewidth=1.05,capsize=1.8,capthick=.65,zorder=5)
            if row==0:
                l.text(x+side/2,y+side+2.65,group_titles[col],7,weight='bold')
            l.letter(x-3.3,y+side+2.65,chr(97+row*3+col))
            counts.append({'group':group,'role':role,'points':len(points),'full':len(sel)})
    l.text(plot_center,55.05,l.label('Paired change in first-loss year, ΔT (years)','首次消失的配对年份差 ΔT（年）'),6.4)
    handles = [Patch(fc=c) for c in colors]+[Line2D([],[],marker='o',ls='none',ms=3.5,c=INK)]
    l.legend(WIDTH_MM/2,51.15,handles,[*component_labels,l.label('Net mean','净效应均值')],6,size=5.7,borderpad=0)
    low = process[list(columns)].clip(upper=0).sum(axis=1).min()
    high = process[list(columns)].clip(lower=0).sum(axis=1).max()
    xmin,xmax = min(-225,5*np.floor(low/5)-3),max(22,5*np.ceil(high/5)+3)
    focus = ('Manufacturing and replacement','Avoidance and manufacturing','Avoided emissions') if language=='en' else ('制造与更换','避免排放与制造','避免排放主导')
    conditions = ('Open','50%','None') if language=='en' else ('不限','50%','禁送')
    for col,(group,x) in enumerate(zip(groups,xs)):
        y=ys[2]
        a = l.axes(x,y,side,side)
        lower.append(a)
        clean(a)
        a.set(xlim=(xmin,xmax),ylim=(-.65,5.65),xticks=[-200,-150,-100,-50,0]);a.grid(axis='x',c=GRID,lw=.45)
        a.axvline(0,c=RULE,lw=.55,zorder=0)
        selected = process[process.subgroup.eq(group)].set_index(['role','export']).loc[[(r,e) for r in ROLES for e in EX]]
        order=np.arange(6)[::-1]
        pos,neg=np.zeros(6),np.zeros(6)
        for key,c in zip(columns,colors):
            vals=selected[key].to_numpy()
            a.barh(order,vals,left=np.where(vals>=0,pos,neg),height=.50,color=c,edgecolor='white',linewidth=.28,zorder=3)
            pos+=np.maximum(vals,0);neg+=np.minimum(vals,0)
        net=selected.carbon_gain_mean_Mt.to_numpy()
        assert np.allclose(net,pos+neg,atol=1e-8)
        a.scatter(net,order,s=13,c=INK,edgecolor='white',linewidths=.35,zorder=5)
        a.set_yticks(order,[f'{state} · {e}' for state in ('GTL','IBL') for e in conditions])
        a.tick_params(axis='y',labelleft=col==0,length=0,labelsize=5.75)
        l.letter(x-3.3,y+side+2.2,chr(103+col))
        l.text(x+side/2,y+side+2.2,focus[col],6.3,weight='bold')
    l.text(plot_center,2.5,l.label('Mean contribution across the full reference groups (Mt CO₂e)','完整参考组平均碳量贡献（Mt CO₂e）'),6.3)
    l.alignment(axes+lower,'abcdefghi',[list(row) for row in ('abc','def','ghi')],
                [list(col) for col in ('adg','beh','cfi')],
                exemptions=[{'panels':list('ghi'),'checks':['vertical-gutter'],
                             'reason':'The shared timing axis title and contribution legend sit between these rows.'}])
    l.finish({'full_records':16710,'paired_records':12572,'common_units':2103,'panels':counts,'process_axes_shared':True})



if __name__=='__main__':
    figure5('en')
    save_json(QA / 'sources_sha256.json', HASHES)
