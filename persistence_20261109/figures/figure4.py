"""Draw the registered country-paired technology effects in Figure 4."""
from hashlib import file_digest
import json
import os
from pathlib import Path
import sys

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.hatch as hatch
from matplotlib import pyplot as plt
from matplotlib.patches import Patch, Rectangle
from matplotlib.path import Path as MplPath
from matplotlib.transforms import Bbox
import numpy as np
import pandas as pd
import cartopy.crs as ccrs
from cartopy.io.shapereader import Reader

ROOT = Path(__file__).resolve().parents[1]
from release_paths import MAP, require_matplotlib_panel_alignment

SOURCE = ROOT / 'data/figure4/paired_national_effects.csv'
BOUNDARIES = MAP
OUT, QA = ROOT / 'build/figures', ROOT / 'build/qa'
WIDTH = 180
HEIGHT = 152
FONT_PT = 5.8
INK, OCEAN, OUTSIDE = '#152831', '#F4F7F8', '#DFE5E9'
BORDER, RETAINED, TEXTURE = '#92A0AA', '#E5F1EA', '#597D68'
DELAY_BINS = (1,5,10,20,30,36)
DELAY_LABELS = ('1–4','5–9','10–19','20–29','30+')
DELAY_COLORS = ('#BDD9ED','#91BEDB','#6299C3','#386F9D','#174768')
BACKGROUNDS = (('CP','Current\nPolicies'),('NDC','NDCs'),('B2C','Below 2°C'),
               ('NZ2050','Net Zero\n2050'),('LD','Low Demand'))
CASES = (('FIG4_M_BEST','Lower manufacturing emissions'),
         ('FIG4_L_BEST','Longer service life'),('FIG4_E_BEST','Improved operation'))
SOUTH_LIMIT = -72


class Snowflakes(hatch.HatchPatternBase):
    """Repeat the six-arm texture of the registered map design."""
    def __init__(self, pattern, density):
        points = []
        n = 6*density*pattern.count('*')
        for iy in range(n):
            for ix in range(n):
                center = np.array([((ix+.5+.5*(iy%2))%n)/n,(iy+.5)/n])
                for angle in np.arange(6)*np.pi/3:
                    unit = np.array([np.cos(angle),np.sin(angle)])
                    points.extend([center,center+.0093*unit])
                    for turn in (-np.pi/4,np.pi/4):
                        branch = center+.0052*unit
                        twig = np.array([np.cos(angle+turn),np.sin(angle+turn)])
                        points.extend([branch,branch+.0038*twig])
        self.vertices = np.asarray(points)
        self.num_vertices = len(points)

    def set_vertices_and_codes(self, vertices, codes):
        vertices[:] = self.vertices
        codes[::2],codes[1::2] = MplPath.MOVETO,MplPath.LINETO


def main():
    mpl.rcParams.update({'font.family':['Arial','DejaVu Sans'],'font.size':FONT_PT,'text.color':INK,
                         'svg.fonttype':'none','pdf.fonttype':42,'hatch.linewidth':.19})
    hatch._hatch_types = [kind for kind in hatch._hatch_types if kind!=hatch.Stars]+[Snowflakes]
    data = pd.read_csv(SOURCE)
    paired = data[data.paired_events_observed]
    assert len(data)==1671 and len(paired)==1332
    assert (paired.paired_delta_T==paired.case_loss_year-paired.REF_loss_year).all()
    assert paired.paired_delta_T.between(0,DELAY_BINS[-1]-1).all()
    assert set(data.loc[~data.paired_events_observed,'outcome_status'])=={'benefit_not_lost_by_2100'}
    geometries = {rec.attributes['ADM0_A3']:rec.geometry for rec in Reader(str(BOUNDARIES)).records()
                  if rec.attributes['ADM0_A3']!='ATA'}
    assert set(data.country)<=geometries.keys()
    map_crs, lon_lat = ccrs.Robinson(),ccrs.PlateCarree()
    map_ylim = (map_crs.transform_point(0,SOUTH_LIMIT,lon_lat)[1],map_crs.y_limits[1])
    ratio = (map_ylim[1]-map_ylim[0])/(map_crs.x_limits[1]-map_crs.x_limits[0])
    fig = plt.figure(figsize=(WIDTH/25.4,HEIGHT/25.4),facecolor='white')

    def label(x,y,text,**kwargs):
        ha = kwargs.pop('ha','center')
        return fig.text(x/WIDTH,y/HEIGHT,text,va='center',ha=ha,**kwargs)

    def fill(ax,countries,color,**kwargs):
        shapes = [geometries[code] for code in countries]
        if shapes:
            ax.add_geometries(shapes,crs=lon_lat,facecolor=color,**kwargs)

    xs,ys,width = (25,76,127),(104,79,54,29,4),47
    height = width*ratio
    axes,panels = [],[]
    for x,(_,title) in zip(xs,CASES,strict=True):
        label(x+width/2,130.6,title,weight='bold')
    for row,((background,pathway),y) in enumerate(zip(BACKGROUNDS,ys,strict=True)):
        label(22,y+height/2,pathway,ha='right',weight='bold')
        for col,((case,_),x) in enumerate(zip(CASES,xs,strict=True)):
            ax = fig.add_axes((x/WIDTH,y/HEIGHT,width/WIDTH,height/HEIGHT),projection=map_crs)
            ax.set_xlim(map_crs.x_limits)
            ax.set_ylim(map_ylim)
            ax.set_facecolor(OCEAN)
            ax.spines['geo'].set_visible(False)
            axes.append(ax)
            sub = data[data.background.eq(background)&data.case.eq(case)]
            events = sub[sub.paired_events_observed]
            retained = sub[~sub.paired_events_observed]
            fill(ax,geometries,OUTSIDE,edgecolor='none',zorder=0)
            fill(ax,events.loc[events.paired_delta_T.eq(0),'country'],'white',edgecolor='none',zorder=1)
            for lo,hi,color in zip(DELAY_BINS[:-1],DELAY_BINS[1:],DELAY_COLORS,strict=True):
                fill(ax,events.loc[events.paired_delta_T.ge(lo)&events.paired_delta_T.lt(hi),'country'],
                     color,edgecolor='none',zorder=1)
            fill(ax,retained.country,RETAINED,edgecolor=TEXTURE,hatch='*',linewidth=0,zorder=2)
            fill(ax,geometries,'none',edgecolor=BORDER,linewidth=.12,zorder=3)
            label(x-.45,y+height+.82,chr(97+3*row+col),ha='left',weight='bold')
            panels.append({'background':background,'case':case,'fixed':len(sub),
                           'paired':len(events),'retained':len(retained)})

    handles = [Patch(facecolor='white',edgecolor=BORDER,lw=.45),
               Patch(facecolor=RETAINED,edgecolor=TEXTURE,hatch='*',lw=.45),Patch(facecolor=OUTSIDE)]
    key_y, key_width, key_height = 144.3, 37, 2.35
    key_bottom = key_y-key_height/2
    key_top = key_bottom+key_height
    title_y = key_top+2.15
    ticks_y = key_bottom-2.15
    legend_rows = (
        fig.legend(handles[:2],['Same loss year (0)','Benefit retained to 2100'],
                   loc='upper left',ncols=2,frameon=False,borderaxespad=0,borderpad=0,
                   handlelength=1.55,handleheight=1,handletextpad=.5,columnspacing=1.25),
        fig.legend(handles[2:],['Outside reference group'],
                   loc='lower left',frameon=False,borderaxespad=0,borderpad=0,
                   handlelength=1.55,handleheight=1,handletextpad=.5),
    )
    renderer = fig.canvas.get_renderer()
    mm_per_px = 25.4/fig.dpi
    legend_width = max(legend.get_window_extent(renderer).width for legend in legend_rows)*mm_per_px
    legend_gap = 8
    block_left = (WIDTH-legend_width-legend_gap-key_width)/2
    key_left = block_left+legend_width+legend_gap
    key_title = label(key_left+key_width/2,title_y,'Delay in first loss, ΔT (years)')
    key = fig.add_axes((key_left/WIDTH,key_bottom/HEIGHT,key_width/WIDTH,key_height/HEIGHT))
    key.set(xlim=(0,len(DELAY_COLORS)),ylim=(0,1))
    key.set_axis_off()
    tick_labels = []
    for i,(color,text) in enumerate(zip(DELAY_COLORS,DELAY_LABELS,strict=True)):
        key.add_patch(Rectangle((i,0),1,1,facecolor=color,edgecolor='white',linewidth=.42))
        tick_labels.append(label(key_left+(i+.5)*key_width/len(DELAY_COLORS),ticks_y,text))
    key_bounds = Bbox.union([artist.get_window_extent(renderer) for artist in (key_title,key,*tick_labels)])
    outside_raise_mm = 1.3
    row_edges = (key_bounds.y1,key_bounds.y0+outside_raise_mm/mm_per_px)
    for legend,edge in zip(legend_rows,row_edges,strict=True):
        legend.set_bbox_to_anchor((block_left/WIDTH,edge/fig.bbox.height),transform=fig.transFigure)
    ids = list('abcdefghijklmno')
    require_matplotlib_panel_alignment(
        fig,axes=axes,panel_ids=ids,row_groups=[ids[i:i+3] for i in range(0,15,3)],
        column_groups=[ids[k::3] for k in range(3)],tolerance_pt=1.5,gutter_tolerance_pt=1.5,strict=True,
        json_out=QA/'Figure4_en.panels.alignment.json',
    )
    fig.savefig(OUT/'Figure4_en.pdf')
    fig.savefig(OUT/'Figure4_en.svg')
    fig.savefig(OUT/'Figure4_en.png',dpi=300)
    fig.savefig(OUT/'Figure4_en.tiff',dpi=600,pil_kwargs={'compression':'tiff_lzw'})
    plt.close(fig)
    paths = [SOURCE,*(BOUNDARIES.with_suffix(ext) for ext in ('.shp','.shx','.dbf','.prj'))]
    sources = {}
    for path in paths:
        with path.open('rb') as stream:
            sources[path.as_posix()] = file_digest(stream,'sha256').hexdigest()
    facts = {'fixed_country_path_configurations':len(data),'common_events':len(paired),
             'retained':int((~data.paired_events_observed).sum()),'panels':panels,
             'delay_bins':DELAY_BINS,'delay_labels':DELAY_LABELS,'delay_colors':DELAY_COLORS,
             'delay_counts':np.histogram(paired.paired_delta_T,bins=DELAY_BINS)[0].tolist(),
             'same_loss_year':int(paired.paired_delta_T.eq(0).sum()),'map_south_limit':SOUTH_LIMIT,
             'key_box_mm':[key_left,key_bottom,key_width,key_height],'sources_sha256':sources}
    (QA/'Figure4_en.data.json').write_text(json.dumps(facts,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
