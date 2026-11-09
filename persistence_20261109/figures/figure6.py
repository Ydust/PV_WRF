"""Render the English Figure 6 with its centered map key shifted northwest."""
from hashlib import file_digest
from pathlib import Path
import json
import os
import sys

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle
import numpy as np
import pandas as pd
from scipy.ndimage import distance_transform_edt, label as connected_components
import cartopy.crs as ccrs
from cartopy.io.shapereader import Reader

ROOT = Path(__file__).resolve().parents[1]
from release_paths import MAP, require_matplotlib_panel_alignment

WIDTH_MM = 170
QA, OUT = ROOT / 'build/qa', ROOT / 'build/figures'
for folder in (QA, OUT):
    folder.mkdir(parents=True, exist_ok=True)
GEO = MAP
PROJ, PC = ccrs.Robinson(), ccrs.PlateCarree()
VIEW_Y = PROJ.transform_point(0, -60, PC)[1], PROJ.y_limits[1]
ROLES = ('formed_then_lost', 'opening_benefit_then_lost')
EX = ('UNLIMITED', 'CAP50', 'CAP0')
EX_COLOR = ('#20282E', '#007F63', '#783DB2')
STATE_COLORS = ('#24628B', '#AC501D')
INK, MUTED, RULE = '#152831', '#425762', '#81929B'
OCEAN, LAND, GRID = '#F4F7F8', '#DFE5E9', '#E7EDF0'
SOURCE = ROOT / 'data/figure6'
HASHES = {}
GEOMETRIES = None


def source(path):
    with path.open('rb') as stream:
        HASHES[path.as_posix()] = file_digest(stream, 'sha256').hexdigest()
    return path


def csv(name):
    return pd.read_csv(source(SOURCE / name))


def read_json(name):
    return json.loads(source(SOURCE / name).read_text(encoding='utf-8-sig'))


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

    def alignment(self, axes, ids, rows=None, cols=None, name='panels'):
        require_matplotlib_panel_alignment(self.fig, axes=axes, panel_ids=list(ids),
            row_groups=rows, column_groups=cols, json_out=QA / f'{self.stem}.{name}.alignment.json',
            tolerance_pt=1.5, gutter_tolerance_pt=1.5, strict=True)

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


def map_axes(layout, x, y, width, limits=VIEW_Y):
    global GEOMETRIES
    if GEOMETRIES is None:
        for extension in ('.shp', '.shx', '.dbf', '.prj'):
            source(GEO.with_suffix(extension))
        GEOMETRIES = {r.attributes['ADM0_A3']: r.geometry for r in Reader(str(GEO)).records()}
    ratio = (limits[1]-limits[0])/(PROJ.x_limits[1]-PROJ.x_limits[0])
    ax = layout.axes(x, y, width, width*ratio, projection=PROJ)
    ax.set_xlim(PROJ.x_limits)
    ax.set_ylim(limits)
    ax.set_facecolor(OCEAN)
    ax.spines['geo'].set_visible(False)
    return ax


def map_fill(ax, country_codes, color, **kwargs):
    shapes = [GEOMETRIES[code] for code in country_codes]
    if shapes:
        ax.add_geometries(shapes, crs=PC, facecolor=color, **kwargs)


def ocean_clearance(layout, small_island_mm2):
    layout.fig.canvas.draw()
    rgb = np.asarray(layout.fig.canvas.buffer_rgba())[:, :, :3].astype(int)
    ocean_rgb = np.rint(np.asarray(mpl.colors.to_rgb(OCEAN)) * 255)
    ocean = np.all(rgb >= ocean_rgb-2,axis=2)
    outside = np.min(rgb,axis=2) >= 251
    px_per_mm = layout.fig.dpi/25.4
    land = ~(ocean | outside)
    components,_ = connected_components(land,structure=np.ones((3,3)))
    component_sizes = np.bincount(components.ravel())
    main_land = land & (component_sizes[components] >= small_island_mm2*px_per_mm**2)
    return (distance_transform_edt(~main_land)/px_per_mm,
            distance_transform_edt(~outside)/px_per_mm, land)


def export_labels(layout):
    return (layout.label('Unrestricted export','外送不限'),
            layout.label('50% export capacity','外送能力50%'),layout.label('No export','禁止外送'))


def validate_legend_land(layout, ax, map_rect):
    """Place the full legend in the lower-left ocean of panel a."""
    fig = layout.fig
    original_dpi = fig.dpi
    fig.set_dpi(240)
    ax.set_visible(False)
    px_per_mm = fig.dpi / 25.4
    small_island_mm2 = .35
    coast_gap,outline_gap,all_land = ocean_clearance(layout,small_island_mm2)
    ax.set_visible(True)
    map_x,map_y,map_width,map_height = map_rect
    previous = SOURCE / 'legend_anchor.json'
    old_x, old_y, key_width, key_height = json.loads(previous.read_text(encoding='utf-8'))['legend']['rect_mm']
    preferred_x, preferred_y = old_x - 4, old_y + 5
    candidates = [(x,y) for y in np.arange(old_y+2, old_y+9, .2)
                  for x in np.arange(old_x-8, old_x-1.9, .2)]
    acceptable = []
    for lw,lh in [(key_width, key_height)]:
        anchor_x,anchor_y = preferred_x,preferred_y
        ax.set_position((anchor_x/WIDTH_MM,anchor_y/layout.height,lw/WIDTH_MM,lh/layout.height))
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        labels = [*ax.get_xticklabels(),*ax.get_yticklabels(),ax.xaxis.label,ax.yaxis.label]
        extents = [ax.get_window_extent(renderer),*[label.get_window_extent(renderer) for label in labels]]
        left, bottom, right, top = np.array([box.extents for box in extents]).T
        for lx,ly in candidates:
            dx,dy = (lx-anchor_x)*px_per_mm,(ly-anchor_y)*px_per_mm
            content = np.array([min(left+dx),min(bottom+dy),max(right+dx),max(top+dy)])/px_per_mm
            if not (map_x<content[0]<content[2]<map_x+map_width/2
                    and map_y<content[1]<content[3]<map_y+map_height/2):
                continue
            x0,x1 = np.floor(left+dx).astype(int),np.ceil(right+dx).astype(int)
            y0,y1 = np.floor(coast_gap.shape[0]-top-dy).astype(int),np.ceil(coast_gap.shape[0]-bottom-dy).astype(int)
            regions = [np.s_[a:b,c:d] for a,b,c,d in zip(y0,y1,x0,x1)]
            coast_by_region = [coast_gap[region].min() for region in regions]
            coast = min(coast_by_region)
            outline = min(outline_gap[region].min() for region in regions)
            if coast >= .30 and outline >= .40:
                # Keep clear of the main landmasses and prefer clear water behind text.
                islands_behind_text = sum(all_land[region].sum() for region in regions[1:])
                score = (-.25*np.hypot(lx-preferred_x,ly-preferred_y)
                         +.05*min(coast,outline,1.2)-.003*islands_behind_text)
                island_overlap = bool(islands_behind_text or all_land[regions[0]].any())
                acceptable.append((score,lx,ly,lw,lh,coast,outline,content.tolist(),island_overlap))
    if not acceptable:
        raise ValueError('No legend position clears the rendered map boundary and country outlines.')
    _,lx,ly,lw,lh,coast,outline,content,island_overlap = max(acceptable,key=lambda record: record[0])
    ax.set_position((lx/WIDTH_MM,ly/layout.height,lw/WIDTH_MM,lh/layout.height))
    fig.set_dpi(original_dpi)
    return {'panel':'a','rect_mm':[lx,ly,lw,lh],'content_bounds_mm':content,
            'whole_legend_within_map':True,'main_land_overlap':False,
            'ignored_island_threshold_mm2':small_island_mm2,'small_island_overlap':island_overlap,
            'boundary_clearance_mm':round(outline,3),'land_clearance_mm':round(coast,3),'qa_dpi':240}


def figure6(language):
    l = Layout(6, 179, language)
    data, bars = csv('map_values.csv'),csv('plotted_bar_values.csv')
    palette = read_json('bivariate_palette.json')
    keys, color, bounds = palette['row_order'],palette['palette'],palette['cost_boundaries']
    assert len(data)==462 and len(bars)==68 and data.background.eq('NZ2050').all()
    assert np.all(data.cost_bin==np.digitize(data.map_value_USD_MWh,bounds[1:-1]))
    maps, statistics = [], []
    width, mx = 116,30
    limits=(PROJ.transform_point(0,-71,PC)[1],PROJ.transform_point(0,85,PC)[1])
    height=width*(limits[1]-limits[0])/(PROJ.x_limits[1]-PROJ.x_limits[0])
    map_rects=[(mx,top-height,width,height) for top in (173,116)]
    for i,(family,rect,title) in enumerate(zip(('technology','storage_export'),map_rects,
            (l.label('Technology','器件技术'),l.label('Storage','储能配置')))):
        x,y,w,h=rect
        ma=map_axes(l,x,y,w,limits);maps.append(ma)
        chosen=data[data.family.eq(family)]
        assert len(chosen)==231 and chosen.country.nunique()==231
        boundary_codes = [code for code in GEOMETRIES if code!='ATA']
        map_fill(ma,boundary_codes,LAND,edgecolor='none',zorder=0)
        for (group,k),g in chosen.groupby(['applicability','cost_bin']):
            map_fill(ma,g.country,color[group][k],edgecolor='none',zorder=1)
        map_fill(ma,boundary_codes,'none',edgecolor='#9CAAB3',linewidth=.12,zorder=2)
        l.letter(10.4,y+h+2.0,chr(97+i))
        l.text(16,y+h+2.0,title,7,align='left',weight='bold')
        statistics.append({'family':family,'country_count':len(chosen),'applicability':chosen.applicability.value_counts().to_dict()})
    l.text(160,175,'Net Zero 2050',6.4,align='right',color=MUTED)
    keyax=l.axes(mx+21,map_rects[0][1]+5.5,13,11.1,zorder=5)
    for col,key in enumerate(keys):
        for row,c in enumerate(color[key]):
            keyax.add_patch(Rectangle((col,row),1,1,fc=c,ec='white',lw=.45))
    keyax.set(xlim=(0,3),ylim=(0,6))
    keyax.set_yticks(range(7),[str(v).replace('-','−') for v in bounds])
    keyax.set_xticks([.5,1.5,2.5],['Full','50%','0%'] if language=='en' else ['不限','50%','禁送'])
    keyax.tick_params(axis='x',length=0,pad=.7,labelsize=5.1)
    keyax.tick_params(axis='y',length=1.5,pad=1,labelsize=5.05)
    for label in keyax.get_yticklabels():
        label.set_fontfamily('Arial')
    keyax.set_xlabel(l.label('Export class','外送适用类别'),fontsize=5.4,labelpad=1.3)
    keyax.set_ylabel(l.label('Cost (USD/MWh)','成本（USD/MWh）'),fontsize=5.4,labelpad=1)
    keyax.yaxis.set_label_coords(-.39,.5)
    for side in keyax.spines.values():side.set_linewidth(.4)
    legend_check=validate_legend_land(l,keyax,map_rects[0])
    l.alignment(maps,'ab',cols=[list('ab')],name='maps')

    bar_rect = (16,14.4,144,40.6)
    ax = l.axes(*bar_rect)
    clean(ax)
    ax.grid(axis='y',c=GRID,lw=.45)
    ax.axhline(0,c=RULE,lw=.62,zorder=0)
    ax.axvline(4,c='#B9C8CF',ls=(0,(2,2)),lw=.55,zorder=0)
    ax.set(xlim=(-.6,14.6),ylim=(-11,39),yticks=[-10,0,10,20,30],ylabel=l.label('Incremental unit cost\n(2025 USD/MWh)','增量单位成本\n（2025 USD/MWh）'))
    assert bars.q25.min()>-11 and bars.q75.max()<39
    tech = ('FIG4_M_BEST','FIG4_L_BEST','FIG4_E_BEST','FIG4_COMBINED')
    store = ('STORAGE_FC0','STORAGE_FC50','STORAGE_FC100','STORAGE_CAP_HALF','STORAGE_CAP_DOUBLE','STORAGE_K05','STORAGE_K1','STORAGE_K2','STORAGE_UTIL50','STORAGE_UTIL0')
    label_en = ('Cleaner\nmanufacturing†','Longer\nlife','Improved\noperation','Combined†','New PV\nunpaired','50% new\nPV paired','100% new\nPV paired','Half\ncapacity','Double\ncapacity','0.5\nkWh/kWp','1\nkWh/kWp','2\nkWh/kWp','Half the\ndays','No cycling')
    label_zh = ('制造改善\nM30†','延长\n寿命','运行\n改善','综合改善†','新增\n不配储','新增\n50%配储','新增\n100%配储','容量\n减半','容量\n加倍','0.5\nkWh/kWp','1\nkWh/kWp','2\nkWh/kWp','半数天\n运行','不充放电')
    xs=np.r_[np.arange(4.),np.arange(5.,15.)]
    ax.set_xticks(xs,label_en if language=='en' else label_zh)
    ax.tick_params(axis='x',length=0,pad=2,labelsize=5.45)
    consumed=0
    for sid,x in zip(tech+store,xs):
        for j,ex in enumerate(EX[:1] if sid in tech else EX):
            c=EX_COLOR[j]
            for k,role in enumerate(ROLES):
                row=bars[bars.configuration.eq(sid)&bars['export'].eq(ex)&bars.role.eq(role)].iloc[0]
                offset=(k-.5)*.125 if sid in tech else (2*j+k-2.5)*.125
                ax.bar(x+offset,row['median'],width=.102,fc=c if k==0 else 'white',ec=c,lw=.55,zorder=3)
                ax.errorbar(x+offset,row['median'],yerr=[[row['median']-row.q25],[row.q75-row['median']]],fmt='none',ecolor=c,elinewidth=.55,capsize=1,capthick=.5,zorder=4)
                consumed+=1
    assert consumed==68
    l.letter(10.4,57.8,'c')
    l.text(16,57.8,l.label('Intervention costs','单项干预成本'),7,align='left',weight='bold')
    handles=[Patch(fc='#6B808D',ec='#6B808D',lw=.5),Patch(fc='white',ec='#6B808D',lw=.55)]+[Patch(fc=c) for c in EX_COLOR]
    l.legend(160,57.8,handles,['GTL','IBL',*export_labels(l)],5,size=5.65,loc='center right')
    for center,group in zip((1.5,9.5),(l.label('Technology','器件技术'),
                                     l.label('Storage and export','储能配置与外送')),strict=True):
        x = bar_rect[0]+(center+.6)/15.2*bar_rect[2]
        l.text(x,5.7,group,5.9,color=MUTED)
    l.text(88,2.45,l.label('† Assumed 10% hardware premium for cleaner manufacturing.','† M30硬件溢价10%为假设。'),5.65,color=MUTED)
    assert all(abs(axis.get_position().x0+axis.get_position().width/2 -
                   (ax.get_position().x0+ax.get_position().width/2))*WIDTH_MM < .01 for axis in maps)
    l.finish({'maps':statistics,'bars':68,'legend':legend_check,
              'bar_rect_mm':bar_rect,'height_mm':l.height})



if __name__=='__main__':
    figure6('en')
    save_json(QA / 'sources_sha256.json', HASHES)
