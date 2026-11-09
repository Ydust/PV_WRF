"""Figure 2 from the registered national events and global trajectories."""
from hashlib import file_digest
from pathlib import Path
import json
import os
import sys

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.colors import LinearSegmentedColormap, to_hex, to_rgb
from matplotlib.font_manager import FontProperties
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Wedge
import numpy as np
import pandas as pd
from scipy.ndimage import distance_transform_edt
import cartopy.crs as ccrs
from cartopy.io.shapereader import Reader

ROOT = Path(__file__).resolve().parents[1]
from release_paths import MAP, require_matplotlib_panel_alignment

WIDTH_MM = 180
LABEL_PT = 5.8
QA, OUT = ROOT / 'build/qa', ROOT / 'build/figures'
for folder in (QA, OUT):
    folder.mkdir(parents=True, exist_ok=True)
GEO = MAP
PROJ, PC = ccrs.Robinson(), ccrs.PlateCarree()
SOUTH_LIMIT = -72
VIEW_Y = PROJ.transform_point(0, SOUTH_LIMIT, PC)[1], PROJ.y_limits[1]
ASPECT = (VIEW_Y[1] - VIEW_Y[0]) / (PROJ.x_limits[1] - PROJ.x_limits[0])
BGS = ('CP', 'NDC', 'B2C', 'NZ2050', 'LD')
NAMES = ('Current Policies', 'NDCs', 'Below 2°C', 'Net Zero 2050', 'Low Demand')
ROLES = ('formed_then_lost', 'opening_benefit_then_lost')
STATE_COLORS = ('#153AB8', '#A3263D')
INK, MUTED, RULE = '#152831', '#425762', '#81929B'
OCEAN = '#F4F7F8'
SOURCES = ROOT / 'data/figure2'
YEAR_TICKS = (2025, 2050, 2075, 2100)
YEAR_EDGES = (*YEAR_TICKS[:-1], YEAR_TICKS[-1]+1)
YEAR_KEY_WIDTH_MM, YEAR_KEY_HEIGHT_MM = 34, 1.85
RING_DIVIDER_DEG = -90
RING_INNER_RATIO = .54
RING_DIAMETER_TO_MAP_WIDTH = 6.7 / 51
HASHES = {}
GEOMETRIES = None


def source(path):
    with path.open('rb') as stream:
        HASHES[path.as_posix()] = file_digest(stream, 'sha256').hexdigest()
    return path


def csv(name):
    return pd.read_csv(source(SOURCES / name))


def read_json(name):
    return json.loads(source(SOURCES / name).read_text(encoding='utf-8-sig'))


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


class Layout:
    def __init__(self, number, height, language):
        self.number, self.height, self.language = number, height, language
        self.stem = f'Figure{number}_{language}'
        family = ['Arial', 'DejaVu Sans'] if language == 'en' else ['Microsoft YaHei', 'DejaVu Sans', 'Arial']
        mpl.rcParams.update({'font.family': family,
            'font.size': LABEL_PT, 'text.color': INK, 'axes.labelcolor': INK,
            'axes.labelsize': LABEL_PT, 'xtick.labelsize': LABEL_PT, 'ytick.labelsize': LABEL_PT,
            'legend.fontsize': LABEL_PT,
            'axes.linewidth': .55, 'svg.fonttype': 'none', 'pdf.fonttype': 42,
            'legend.frameon': False, 'axes.unicode_minus': True, 'hatch.linewidth': .19})
        self.fig = plt.figure(figsize=(WIDTH_MM / 25.4, height / 25.4), facecolor='white')

    def label(self, en, zh):
        return en if self.language == 'en' else zh

    def text(self, x, y, text, *, align='center', color=INK, weight='normal', angle=0):
        return self.fig.text(x / WIDTH_MM, y / self.height, text, ha=align, va='center',
                             color=color, weight=weight, rotation=angle, rotation_mode='anchor')

    def axes(self, x, y, width, height, **kwargs):
        return self.fig.add_axes((x / WIDTH_MM, y / self.height, width / WIDTH_MM, height / self.height), **kwargs)

    def letter(self, x, y, char):
        self.text(x, y, char, align='left', weight='bold')

    def legend(self, x, y, handles, labels, cols, **kwargs):
        loc = kwargs.pop('loc', 'center')
        return self.fig.legend(handles, labels, bbox_to_anchor=(x / WIDTH_MM, y / self.height),
            loc=loc, ncol=cols, handlelength=1.45,
            columnspacing=.85, handletextpad=.45, borderaxespad=0, **kwargs)

    def alignment(self, axes, ids, rows=None, cols=None, name='panels', *, exemptions=()):
        require_matplotlib_panel_alignment(self.fig, axes=axes, panel_ids=list(ids),
            row_groups=rows, column_groups=cols, json_out=QA / f'{self.stem}.{name}.alignment.json',
            tolerance_pt=1.5, gutter_tolerance_pt=1.5, strict=True, exemptions=exemptions)

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


def year_key(layout, right, top, ramps):
    width, height = YEAR_KEY_WIDTH_MM, YEAR_KEY_HEIGHT_MM
    left, bottom = right-width, top-height
    swatches = layout.axes(left,bottom,width,height)
    first, last = YEAR_TICKS[0],YEAR_TICKS[-1]
    swatches.set(xlim=(first,last),ylim=(0,1))
    swatches.set_axis_off()
    tick_y = bottom-2.05
    for start, stop, ramp in zip(YEAR_TICKS[:-1], YEAR_TICKS[1:], ramps, strict=True):
        edges = np.linspace(start, stop, 101)
        # Overlap neighbouring strips to suppress hairline seams in vector viewers.
        right = np.minimum(edges[1:]+.25, stop)
        strips = [[(left,0),(end,0),(end,1),(left,1)]
                  for left,end in zip(edges[:-1],right,strict=True)]
        swatches.add_collection(PolyCollection(strips, facecolors=ramp(np.linspace(0,1,100)),
                                              edgecolors='none', antialiased=False))
    swatches.vlines(YEAR_TICKS[1:-1], 0, 1, color='white', lw=.45)
    tick_labels = []
    for year in YEAR_TICKS:
        swatches.plot([year,year],[0,-.19],color=INK,lw=.4,clip_on=False)
        x = left+(year-first)*width/(last-first)
        tick_labels.append(layout.text(x,tick_y,str(year)))
    title = layout.text(left+width/2,top+2.15,
                        layout.label('First-loss year','效益首次消失年份'))
    return swatches, title, tick_labels, (bottom+height/2, tick_y)


def shared_ocean(layout, positions, width, height, step):
    """Keep only pixels that lie over open ocean in every map."""
    layout.fig.canvas.draw()
    rgb = np.asarray(layout.fig.canvas.buffer_rgba())[:, :, :3].astype(np.int16)
    ocean_rgb = np.rint(np.asarray(mpl.colors.to_rgb(OCEAN)) * 255)
    sea = np.max(abs(rgb-ocean_rgb), axis=2) <= 2
    scale = layout.fig.dpi / 25.4
    x = np.arange(0, width, step)
    y = np.arange(0, height, step)
    common = np.ones((len(y), len(x)), dtype=bool)
    for left, bottom in positions:
        cols = np.rint((left+x)*scale).astype(int)
        rows = sea.shape[0]-1-np.rint((bottom+y)*scale).astype(int)
        common &= sea[np.ix_(rows, cols)]
    return common


def ring_callouts(center, radius, counts, font_widths, label_drop, label_gap):
    """Place labels under the two wedges that meet on the vertical centreline."""
    arc = np.array(counts[:2])*360/sum(counts)
    sides = np.array([-1, 1])
    angles = np.deg2rad(RING_DIVIDER_DEG+sides*np.minimum(arc/2, 39))
    labels = []
    for n, theta, side in zip(counts[:2], angles, sides):
        text = f'{100*n/sum(counts):.1f}%'
        width = font_widths[text]
        anchor = center+[side*(label_gap+width/2), -radius-label_drop]
        lower = anchor - [width/2,.98]
        upper = anchor + [width/2,.98]
        start = center + (radius+.02)*np.array([np.cos(theta),np.sin(theta)])
        end = np.array([np.clip(start[0], lower[0]+.18, upper[0]-.18), upper[1]+.22])
        labels.append((text, anchor, lower, upper, np.linspace(start,end,18)))
    return labels


def callout_fits(label, sea, step, blocked):
    _, _, lower, upper, path = label
    ix0, iy0 = np.floor((lower-.18)/step).astype(int)
    ix1, iy1 = np.ceil((upper+.18)/step).astype(int)+1
    if ix0 < 0 or iy0 < 0 or ix1 > sea.shape[1] or iy1 > sea.shape[0]:
        return False
    occupied = blocked[iy1,ix1]-blocked[iy0,ix1]-blocked[iy1,ix0]+blocked[iy0,ix0]
    gx, gy = np.rint(path/step).astype(int).T
    return occupied == 0 and sea[gy,gx].all()


def ring_layout(layout, ring_data, width):
    step = .10
    old_dpi = layout.fig.dpi
    layout.fig.set_dpi(300)
    sea = shared_ocean(layout, [(x,y) for x,y,_ in ring_data], width, width*ASPECT, step)
    distance = distance_transform_edt(sea)*step
    blocked = np.pad((~sea).astype(np.int32).cumsum(0).cumsum(1), ((1,0),(1,0)))
    renderer = layout.fig.canvas.get_renderer()
    font = FontProperties(family=mpl.rcParams['font.family'], weight='bold', size=LABEL_PT)
    widths = {}
    for _,_,counts in ring_data:
        for n in counts[:2]:
            text = f'{100*n/sum(counts):.1f}%'
            w, _, _ = renderer.get_text_width_height_descent(text, font, False)
            widths[text] = w*25.4/layout.fig.dpi
    grid = [(x,y) for x in np.arange(3.6,width-3.6,.18) for y in np.arange(4.65,width*ASPECT-2.3,.18)]
    grid.sort(key=lambda xy: (xy[0]-.72*width)**2+(xy[1]-.255*width*ASPECT)**2)
    target_radius = width*RING_DIAMETER_TO_MAP_WIDTH/2
    for radius in target_radius-np.arange(0,1.2,.15):
        for x,y in grid:
            margin = distance[round(y/step),round(x/step)]-radius
            if margin < .35:
                continue
            center = np.array([x,y])
            for label_drop in (1.43,1.64,1.85):
                placements = [ring_callouts(center,radius,counts,widths,label_drop,.34)
                              for _,_,counts in ring_data]
                if all(callout_fits(label,sea,step,blocked) for labels in placements for label in labels):
                    layout.fig.set_dpi(old_dpi)
                    return center, radius, margin, placements
    raise RuntimeError('No shared map location fits the rings and both percentage labels.')


def draw_rings(layout, ring_data, width, colors):
    center, radius, margin, placements = ring_layout(layout, ring_data, width)
    overlay = layout.axes(0, 0, WIDTH_MM, layout.height, frameon=False, zorder=7)
    overlay.set(xlim=(0, WIDTH_MM), ylim=(0, layout.height))
    overlay.set_axis_off()
    texts = []
    for (x,y,counts), labels in zip(ring_data,placements):
        origin = np.array([x,y])
        arc = np.asarray(counts)*360/sum(counts)
        edge = RING_DIVIDER_DEG-arc[0]+np.r_[0,np.cumsum(arc)]
        assert np.isclose(edge[1],RING_DIVIDER_DEG)
        for low,high,color in zip(edge,edge[1:],colors):
            overlay.add_patch(Wedge(origin+center,radius,low,high,width=radius*(1-RING_INNER_RATIO),
                                    facecolor=color,edgecolor='none'))
        xc, yc = origin+center
        overlay.plot([xc,xc],[yc-radius,yc-radius*RING_INNER_RATIO],color=OCEAN,lw=.42,solid_capstyle='butt')
        for (text, point, lower, upper, path), color in zip(labels, colors[:2]):
            overlay.plot(*(origin+path[[0,-1]]).T,color=color,lw=.48,solid_capstyle='round')
            artist = overlay.text(*(origin+point),text,color=color,
                                  weight='bold',ha='center',va='center')
            texts.append((artist, origin+lower, origin+upper))
    old_dpi = layout.fig.dpi
    layout.fig.set_dpi(300)
    layout.fig.canvas.draw()
    renderer = layout.fig.canvas.get_renderer()
    for artist,lower,upper in texts:
        bounds = artist.get_window_extent(renderer).extents*25.4/layout.fig.dpi
        assert np.all(bounds[:2]>=lower-.12) and np.all(bounds[2:]<=upper+.12), artist.get_text()
    layout.fig.set_dpi(old_dpi)
    return {'center_from_panel_origin_mm':center.tolist(), 'diameter_mm':2*radius,
            'target_diameter_mm':width*RING_DIAMETER_TO_MAP_WIDTH,
            'inner_diameter_mm':round(2*radius*RING_INNER_RATIO,3),
            'state_divider_degrees':RING_DIVIDER_DEG, 'label_font_pt':LABEL_PT,
            'label_position':'below ring, GTL left and IBL right',
            'minimum_ring_clearance_mm':round(margin,3), 'all_labels_inside_open_ocean':True}


def global_legend(ax, handles, names, years, upper_envelope):
    order = (0,2,4,6,5,3,1)
    legend = ax.legend([handles[i] for i in order], [names[i] for i in order],
                       loc='upper left', ncol=2, frameon=False,
                       handlelength=1.2, handletextpad=.35, labelspacing=.04,
                       columnspacing=.64, borderaxespad=.22, borderpad=.08)
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    bounds = legend.get_window_extent(renderer)
    assert ax.get_window_extent(renderer).contains(*bounds.p0)
    assert ax.get_window_extent(renderer).contains(*bounds.p1)
    entries = [mpl.transforms.Bbox.union([text.get_window_extent(renderer),
                                         handle.get_window_extent(renderer)])
               for text, handle in zip(legend.get_texts(), legend.legend_handles, strict=True)]
    clearances = []
    for entry in entries:
        (x0,y0),(x1,_) = ax.transData.inverted().transform([entry.p0,entry.p1])
        covered = np.r_[x0, years[(years>=x0)&(years<=x1)], x1]
        clearances.append(y0-np.interp(covered, years, upper_envelope).max())
    clearance = min(clearances)
    assert clearance>=2.8, (names, clearance)
    return float(clearance)


def figure2(language):
    width, gutter, row_gutter = 82., 8., 10.3
    panel_height = width*ASPECT
    left = (WIDTH_MM-2*width-gutter)/2
    xs = left, left+width+gutter
    bottom = 5.
    ys = tuple(bottom+row*(panel_height+row_gutter) for row in (2,1,0))
    l = Layout(2, ys[0]+panel_height+17.1, language)
    data = csv('national_reference_events.csv')
    refs, band = read_json('reference_curves.json'), read_json('all_configuration_envelope.json')
    rings = {r['background']: r for r in read_json('ring_statistics.json')}
    states = (*ROLES, 'benefit_without_observed_loss', 'no_observed_benefit')
    fills = (*STATE_COLORS, '#BCC8D4', '#F0DFBE')
    years = np.arange(YEAR_EDGES[0], YEAR_EDGES[-1])
    curve = ('#222222', '#1467B3', '#00805F', '#8C3B90', '#B35300')
    positions = [(x, y) for y in ys for x in xs]
    ax = l.axes(xs[0],ys[0],width,panel_height)
    axes, stats, ring_data = [ax], [], []
    ax.fill_between(years, band['low'], band['high'], color='#E3E9EC', lw=0)
    loss_colors = {}
    for bg, color in zip(BGS, curve):
        c, t = np.asarray(refs[bg]['C']), refs[bg]['first_loss_year']
        ax.plot(years, c, color=color, ls='solid', lw=.9)
        if t is not None:
            assert c[int(t)-2025] > 0 and np.any(c[:int(t)-2025] < 0)
            ax.plot(t, c[int(t)-2025], marker='^', ls='none', ms=3.3, color=color, zorder=5)
            loss_colors[int(t)] = color
    events_by_year = sorted(loss_colors.items())
    assert all(start <= year < stop for (year, _), start, stop in
               zip(events_by_year, YEAR_EDGES[:-1], YEAR_EDGES[1:], strict=True))
    ramp_colors = [(to_hex(.5+.5*np.array(to_rgb(color))), color) for _, color in events_by_year]
    ramps = [LinearSegmentedColormap.from_list(f'years_{start}', colors)
             for start, colors in zip(YEAR_TICKS[:-1], ramp_colors, strict=True)]
    year_fills = {
        year: to_hex(ramp((year-start)/(right-start)))
        for start, stop, right, ramp in zip(YEAR_EDGES[:-1], YEAR_EDGES[1:], YEAR_TICKS[1:], ramps, strict=True)
        for year in range(start, stop)
    }
    ax.set(xlim=(2024, 2101), xticks=YEAR_TICKS, yticks=[-60,-40,-20,0,20,40],
           ylabel=l.label('Cumulative net emissions\n(Gt CO₂e)', '累计净排放\n（Gt CO₂e）'))
    ax.axhline(0,c=RULE,lw=.65,ls=(0,(3.5,2.5)),zorder=1.5)
    clean(ax)
    ax.spines['bottom'].set_color('#000000')
    ax.spines['bottom'].set_linewidth(.62)
    ax.tick_params(axis='x', colors='#000000')
    ax.yaxis.labelpad = 2
    ax.set_ylim(-65,56)
    # Align the full chart, including its axis text, with the maps below.
    target_edges = np.array([xs[0],xs[0]+width])
    for _ in range(2):
        l.fig.canvas.draw()
        bbox = ax.get_tightbbox(l.fig.canvas.get_renderer())
        left_shift, right_shift = (target_edges-np.array([bbox.x0,bbox.x1])*25.4/l.fig.dpi)/WIDTH_MM
        box = ax.get_position()
        ax.set_position((box.x0+left_shift,box.y0,box.width+right_shift-left_shift,box.height))
    tick_colors = dict.fromkeys(map(str,YEAR_TICKS),'#000000')
    handles = [Line2D([], [], c=c, ls='solid', lw=1) for c in curve]
    handles += [Patch(fc='#E3E9EC'), Line2D([], [], marker='^', markerfacecolor='none',
                markeredgecolor=INK, markeredgewidth=.65, ms=3.3, ls='none')]
    names = [*NAMES,l.label('Scenario envelope','情景范围'),l.label('First loss','首次消失')]
    legend_clearance = global_legend(ax, handles, names, years, band['high'])
    global_geometry = dict(height_mm=panel_height, y_limits=list(ax.get_ylim()),
                           zero_line='dashed', year_tick_colors=tick_colors,
                           pathway_line_colors=dict(zip(BGS,curve)),
                           bottom_spine='#000000', first_loss_legend_marker='hollow triangle',
                           legend_location='upper left inside panel a',
                           legend_above_envelope_Gt=legend_clearance)
    l.text(xs[0]+width/2, ys[0]+panel_height+3.5, l.label('Global', '全球'), weight='bold')
    for index, (bg, name) in enumerate(zip(BGS, NAMES), 1):
        x, y = positions[index]
        a = map_axes(l, x, y, width)
        axes.append(a)
        sub = data[data.background.eq(bg)]
        counts = [int(sub.state.eq(s).sum()) for s in states]
        assert counts == [rings[bg]['counts'][s] for s in states] and sum(counts) == 231
        boundary_codes = [code for code in GEOMETRIES if code!='ATA']
        map_fill(a, boundary_codes, 'white', edgecolor='none', zorder=0)
        for state, color in zip(states[2:], fills[2:]):
            map_fill(a, sub.loc[sub.state.eq(state), 'country'], color, edgecolor='none', zorder=1)
        events = sub[sub.first_loss_year.notna()]
        assert sorted(events.country) == rings[bg]['first_loss_country_ids']
        for year, countries in events.groupby('first_loss_year')['country']:
            map_fill(a, countries, year_fills[year], edgecolor='none', zorder=1)
        band_counts = np.histogram(events.first_loss_year, bins=YEAR_EDGES)[0].tolist()
        map_fill(a, boundary_codes, 'none', edgecolor='#92A0AA', linewidth=.12, zorder=2)
        l.text(x+width/2, y+panel_height+3.5, name, weight='bold')
        ring_data.append((x,y,counts))
        stats.append({'background': bg, 'ring_counts': counts, 'mapped_events': len(events),
                      'global_first_loss': refs[bg]['first_loss_year'], 'year_band_counts': band_counts})
    ring_geometry = draw_rings(l, ring_data, width, fills)
    for i,(x,y) in enumerate(positions):
        l.letter(x-.6,y+panel_height+3.5,chr(97+i))
    key_top, state_left, year_right = l.height-6., 41., 137.
    year_bar, year_title, year_labels, row_centers = year_key(l,year_right,key_top,ramps)
    state_key = l.legend(state_left, np.mean(row_centers), [*[Patch(fc=c) for c in fills], Patch(fc='white',ec='#92A0AA',lw=.5)],
        ['GTL','IBL',l.label('Benefit retained','效益维持至期末'),l.label('Benefit never formed','未形成效益'),l.label('Outside study','研究范围外')],
        3, loc='center left', borderpad=0, labelspacing=.6)
    l.alignment(axes, 'abcdef', [list('ab'),list('cd'),list('ef')], [list('ace'),list('bdf')],
        exemptions=[{'panels':['a'],'checks':['panel-width','column','horizontal-gutter'],
                     'reason':'The full chart width including labels aligns with maps c and e.'}])
    boxes = [axis.get_position() for axis in axes]
    assert np.ptp([box.height for box in boxes])*l.height<.02
    for row in (boxes[:2],boxes[2:4],boxes[4:]):
        assert np.ptp([box.y0 for box in row])*l.height<.02
        assert np.ptp([box.y1 for box in row])*l.height<.02
    renderer = l.fig.canvas.get_renderer()
    mm_per_px = 25.4/l.fig.dpi
    chart_box = ax.get_tightbbox(renderer)
    chart_edges = np.array([chart_box.x0,chart_box.x1])*mm_per_px
    assert np.allclose(chart_edges,target_edges,atol=.05), chart_edges
    global_geometry.update(visual_edges_mm=chart_edges.tolist(),axes_width_mm=boxes[0].width*WIDTH_MM)
    state_box = state_key.get_window_extent(renderer)
    year_box = year_bar.get_window_extent(renderer)
    title_box = year_title.get_window_extent(renderer)
    state_rows = [text.get_window_extent(renderer) for text in state_key.get_texts()[:2]]
    row_errors = [abs((row.y0+row.y1)/2*mm_per_px-target) for row,target in zip(state_rows,row_centers)]
    year_boxes = [year_box, title_box, *(label.get_window_extent(renderer) for label in year_labels)]
    legend_bottom = min(state_box.y0, *(box.y0 for box in year_boxes))*mm_per_px
    assert legend_bottom-(ys[0]+panel_height+3.5)>2
    year_left = min(box.x0 for box in year_boxes)
    year_end = max(box.x1 for box in year_boxes)
    gap = (year_left-state_box.x1)*mm_per_px
    group_center = (state_box.x0+year_end)/2*mm_per_px
    assert max(row_errors)<.53 and 10<=gap<=16, (row_errors,gap)
    assert abs(group_center-WIDTH_MM/2)<.53, group_center
    assert abs((title_box.x0+title_box.x1-year_box.x0-year_box.x1)/2*mm_per_px)<.02
    assert (title_box.y0-year_box.y1)*mm_per_px>.3
    l.finish({'label_font_pt':LABEL_PT,'reference_countries_per_background':231,'envelope_curves':275,
              'year_bin_edges':YEAR_EDGES,'year_gradient_endpoints':ramp_colors,
              'year_fill_colors':year_fills,'map_south_limit_deg':SOUTH_LIMIT,
              'year_ticks':YEAR_TICKS,'year_key_width_mm':YEAR_KEY_WIDTH_MM,
              'year_key_height_mm':YEAR_KEY_HEIGHT_MM,
              'layout':{'rows':3,'columns':2,'read_order':'abcdef'},
              'top_keys':{'row_centers_mm':list(row_centers),'row_alignment_errors_mm':row_errors,
                          'bar_top_mm':key_top,'bar_center_x_mm':year_right-YEAR_KEY_WIDTH_MM/2,
                          'group_center_x_mm':round(group_center,3),
                          'horizontal_clearance_mm':round(gap,3)},
              'ring_geometry':ring_geometry,'ring_colors':dict(zip(states,fills,strict=True)),
              'global_geometry':global_geometry,'panels':stats})


if __name__ == '__main__':
    figure2('en')
    save_json(QA / 'sources_sha256.json', HASHES)


