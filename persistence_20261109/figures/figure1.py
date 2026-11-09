from pathlib import Path
import json
import os
import sys

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, Rectangle

ROOT = Path(__file__).resolve().parents[1]
from release_paths import require_matplotlib_panel_alignment

WIDTH_MM = 162
TOP_MM = 153.3
BOTTOM_MM = 9.8
HEIGHT_MM = TOP_MM - BOTTOM_MM
LAYOUT_WIDTH = 180
INK, MUTED, RULE = '#152831', '#435762', '#80929B'
EDGE = '#C9D5D9'
SCENARIO_PALE, SCENARIO_EDGE = '#F1EEF6', '#CCC3D8'
GTL, IBL = '#24628B', '#AC501D'
AVOID, AVOID_PALE = '#286A61', '#EDF5F1'
SYSTEM, SYSTEM_PALE = '#654F3D', '#F6F1EB'
mpl.rcParams.update({'font.family': 'sans-serif', 'font.size': 7, 'pdf.fonttype': 42,
                     'svg.fonttype': 'none', 'figure.facecolor': 'white', 'savefig.facecolor': 'white'})
OUT, QA = ROOT / 'build/figures', ROOT / 'build/qa'
for directory in (OUT, QA):
    directory.mkdir(parents=True, exist_ok=True)

INPUTS = (
    (('Rooftop resources', '屋顶资源'), ('GRA2020 · SSP', 'GRA2020 · SSP')),
    (('Historical capacity', '历史装机'), ('IEA PVPS · national records', 'IEA PVPS · 国别统计')),
    (('Climate', '气候驱动'), ('CMIP6 · SSP', 'CMIP6 · SSP')),
    (('Power transitions', '电网转型'), ('NGFS · REMIND–MAgPIE', 'NGFS · REMIND–MAgPIE')),
)
REFERENCE_SETTINGS = (
    ('SSP2 rooftops · SSP2-4.5 climate', 'SSP2屋顶 · SSP2-4.5气候'),
    ('Five NGFS power transition pathways', '五条NGFS电网转型路径'),
    ('Baseline component and storage settings · unrestricted export', '基准器件与储能配置 · 外送不限'),
)
INTERVENTIONS = (
    (('Technology', '器件技术'), ('Manufacturing · lifetime · operation · disposal', '制造 · 寿命 · 运行 · 退役处置')),
    (('Storage', '储能配置'), ('Battery adoption · chemistry · sizing · use', '配储比例 · 电池类型 · 容量与功率 · 使用')),
    (('Export', '余电外送'), ('Power cap for surplus PV sent to the grid', '光伏余电送入电网的功率上限')),
)
EMISSIONS = (
    ('−', ('Avoided emissions', '避免排放'), AVOID, AVOID_PALE),
    ('+', ('Grid auxiliary emissions', '电网辅助用电排放'), SYSTEM, SYSTEM_PALE),
    ('+', ('Manufacturing emissions', '制造排放'), SYSTEM, SYSTEM_PALE),
    ('+', ('End-of-life emissions', '处置排放'), SYSTEM, SYSTEM_PALE),
)


def draw(language, lang):
    fonts = ['Arial', 'DejaVu Sans'] if language == 'en' else ['Microsoft YaHei', 'Arial', 'DejaVu Sans']
    mpl.rcParams['font.sans-serif'] = fonts
    fig = plt.figure(figsize=(WIDTH_MM / 25.4, HEIGHT_MM / 25.4))
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set(xlim=(0, LAYOUT_WIDTH), ylim=(BOTTOM_MM, TOP_MM))
    ax.set_axis_off()
    boxes = []

    def label(x, y, pair, size=7, color=INK, align='center', bold=False, angle=0):
        value = pair[lang] if isinstance(pair, tuple) else pair
        return ax.text(x, y, value, fontsize=size, color=color, ha=align, va='center',
                       weight='bold' if bold else 'normal', rotation=angle,
                       rotation_mode='anchor', linespacing=1.12)

    def panel(letter, y, title):
        label(9, y, letter, 8.2, align='left', bold=True)
        label(15, y, title, 7.5, align='left', bold=True)

    def box(x, y, width, height, fill='white', edge=EDGE):
        patch = Rectangle((x, y), width, height, facecolor=fill, edgecolor=edge, lw=.55)
        ax.add_patch(patch)
        boxes.append(patch)

    def line(x1, y1, x2, y2, color=RULE, width=.68):
        ax.plot((x1, x2), (y1, y2), color=color, lw=width, solid_capstyle='round')

    def arrow(x1, y1, x2, y2, color=RULE):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle='-|>', mutation_scale=6,
                                     color=color, lw=.72, shrinkA=0, shrinkB=0, zorder=4))

    panel('a', 148, ('Inputs and scenario design', '模型输入与情景设计'))
    columns = (9, 50.5, 92, 133.5)
    centers = tuple(x + 18.75 for x in columns)
    for x, xc, (title, source) in zip(columns, centers, INPUTS, strict=True):
        box(x, 131.8, 37.5, 11.7)
        label(xc, 139.8, title, 7, bold=True)
        label(xc, 135.7, source, 6, MUTED)
    left, right = (centers[0] + centers[1]) / 2, (centers[2] + centers[3]) / 2
    for x, xc, title in ((9, left, ('Reference scenarios', '参考情景')),
                         (92, right, ('Intervention scenarios', '干预情景'))):
        box(x, 113.1, 79, 15.5, SCENARIO_PALE, SCENARIO_EDGE)
        label(x+4, 125.1, title, 7, align='left', bold=True)
        line(xc, 113.1, xc, 111.3)
    scenario_rows = (121.55, 118.65, 115.75)
    for y, item in zip(scenario_rows, REFERENCE_SETTINGS, strict=True):
        label(13, y, item, 6.15, MUTED, align='left')
    intervention_rows = [
        (label(96, y, term, 6.15, align='left', bold=True),
         label(113, y, definition, 6.15, MUTED, align='left'))
        for y, (term, definition) in zip(scenario_rows, INTERVENTIONS, strict=True)
    ]
    line(left, 111.3, right, 111.3)
    arrow(90, 111.3, 90, 106.9)

    panel('b', 107.5, ('Annual carbon accounting', '年度碳收支核算'))
    box(9, 94, 79, 11)
    box(92, 94, 79, 11)
    label(left, 101.35, ('Generation and operation', '发电与运行'), 7, bold=True)
    label(left, 97.3, ('Self-use · storage · export · curtailment', '自用 · 储能 · 外送 · 弃光'), 6.15, MUTED)
    label(right, 101.35, ('Component life cycle', '部件生命周期'), 7, bold=True)
    label(right, 97.3, ('Emissions by installation cohort', '按安装批次核算排放'), 6.15, MUTED)
    for middle, ends in ((left, centers[:2]), (right, centers[2:])):
        line(middle, 94, middle, 92.8)
        line(ends[0], 92.8, ends[1], 92.8)
        for xc in ends:
            arrow(xc, 92.8, xc, 90.4)
    for x, xc, (sign, title, color, fill) in zip(columns, centers, EMISSIONS):
        box(x, 82.1, 37.5, 8.1, fill)
        label(xc, 86.15, f'{sign}  {title[lang]}', 6.7, color, bold=True)
    line(centers[0], 82.1, centers[0], 79.65, AVOID)
    line(centers[0], 79.65, 52, 79.65, AVOID)
    arrow(52, 79.65, 52, 77.7, AVOID)
    for xc in centers[1:]:
        line(xc, 82.1, xc, 79.65, SYSTEM)
    line(centers[1], 79.65, centers[3], 79.65, SYSTEM)
    arrow(centers[2], 79.65, centers[2], 77.7, SYSTEM)
    box(41, 70.7, 98, 6.8)
    label(90, 74.1, ('Annual net emissions', '年度净排放'), 7, bold=True)
    line(90, 70.7, 90, 68)
    line(90, 68, 120.3, 68)
    arrow(120.3, 68, 120.3, 64.9)
    box(9, 57.4, 55, 7.3, 'white')
    label(36.5, 61.05, ('Opening carbon balance', '期初历史碳余额'), 6.7, bold=True)
    arrow(64, 61.05, 69.4, 61.05)
    box(69.6, 57.4, 101.4, 7.3, edge='#9EB4BE')
    label(120.3, 61.05, ('Cumulative net emissions', '累计净排放'), 7, bold=True)
    line(120.3, 57.4, 120.3, 53.7)
    line(120.3, 53.7, 94, 53.7)
    arrow(94, 53.7, 94, 51.7)

    panel('c', 49.9, ('Identifying the first loss of cumulative benefits', '识别累计减排效益首次消失'))
    plot_lefts, plot_width = (17, 101), 70
    label(7.5, 29.6, ('Cumulative net emissions', '累计净排放'), 6.4, angle=90)
    label(plot_lefts[0]+plot_width/2, 43.7, ('Benefit gained then lost (GTL)', '期内形成效益后消失（GTL）'), 7, GTL, bold=True)
    label(plot_lefts[1]+plot_width/2, 43.7, ('Initial benefit lost (IBL)', '期初已有效益后消失（IBL）'), 7, IBL, bold=True)

    year_ends = np.linspace(0, 1, 77)
    # Each schematic is a single quadratic arc in normalized time.
    trajectories = (
        (4.5, -4.5 * (.17 + .68), 4.5 * .17 * .68),
        (1.15, .25, -.80),
    )
    plot_axes = []
    event_checks = {}
    for x, color, state, coefficients in zip(plot_lefts, (GTL, IBL), ('GTL', 'IBL'), trajectories):
        plot = fig.add_axes((x / LAYOUT_WIDTH, (16.2 - BOTTOM_MM) / HEIGHT_MM,
                             plot_width / LAYOUT_WIDTH, 24 / HEIGHT_MM))
        plot_axes.append(plot)
        plot.set(xlim=(0, 1), ylim=(-.96, 1.38), xticks=[], yticks=[])
        for name in ('right', 'top'):
            plot.spines[name].set_visible(False)
        for name in ('left', 'bottom'):
            plot.spines[name].set(color=RULE, linewidth=.65)
        plot.axhline(0, color=RULE, lw=.7, zorder=1)
        roots = np.roots(coefficients)
        roots = roots[(roots > 0) & (roots < 1)]
        crossing_time = float(max(roots))
        assert np.polyval(np.polyder(coefficients), crossing_time) > 0
        curve_time = np.unique(np.r_[np.linspace(0, 1, 501), roots])
        curve_values = np.polyval(coefficients, curve_time)
        curve_values[np.isin(curve_time, roots)] = 0
        plot.fill_between(curve_time, curve_values, 0, where=curve_values < 0, interpolate=True,
                          color=color, alpha=.10, lw=0, zorder=0)
        curve, = plot.plot(curve_time, curve_values, color=color, lw=1.28, solid_capstyle='round', zorder=2)
        curve.get_path().should_simplify = False
        values = np.polyval(coefficients, year_ends)
        loss = next(j for j, val in enumerate(values) if val > 0 and min(values[:j], default=0) < 0)
        assert loss > 0 and values[loss - 1] < 0 < values[loss]
        assert (values[0] < 0) == (state == 'IBL')
        assert year_ends[loss - 1] < crossing_time < year_ends[loss]
        sample_points = [j for j in (0, 10, 20, 30, 40, 50, 60, 70, 76) if abs(j - loss) > 2]
        plot.plot(year_ends[sample_points], values[sample_points], linestyle='none', marker='o', markersize=2.05,
                  markeredgewidth=.5, markerfacecolor='white', markeredgecolor=color, zorder=3, clip_on=False)
        event_checks[state] = {
            'opening_negative': bool(values[0] < 0),
            'previous_year_end_value': float(values[loss - 1]),
            'first_positive_year_end_value': float(values[loss]),
            'event_year_end_index': loss,
            'schematic_marker': [crossing_time, 0],
            'quadratic_coefficients': coefficients,
            'data_kind': 'schematic',
        }
        plot.plot(crossing_time, 0, marker='o', markersize=4.1, color=color,
                  markeredgecolor='white', markeredgewidth=.65, zorder=5)
        plot.annotate(('First loss', '首次消失')[lang],
                      xy=(crossing_time, 0), xytext=(crossing_time, .68),
                      ha='center', va='bottom', fontsize=6.5, color=color,
                      arrowprops={'arrowstyle': '-', 'lw': .65, 'color': color, 'shrinkA': 2, 'shrinkB': 2.5})
        label(x - 1.2, 16.2 + 24 * .96 / 2.34, '0', 6, MUTED, align='right')
        label(x, 13.35, '2025', 6, MUTED, align='left')
        label(x + plot_width, 13.35, '2100', 6, MUTED, align='right')

    stem = f'Figure1_{language}'
    fig.canvas.draw()
    mm_per_px = 25.4 / fig.dpi
    renderer = fig.canvas.get_renderer()
    intervention_box = boxes[5].get_window_extent(renderer)
    for term, definition in intervention_rows:
        term_bounds = term.get_window_extent(renderer)
        text_bounds = definition.get_window_extent(renderer)
        assert (text_bounds.x0-term_bounds.x1)*mm_per_px > 1, term.get_text()
        assert (intervention_box.x1-text_bounds.x1)*mm_per_px > 1, definition.get_text()
        assert intervention_box.contains(*text_bounds.p0) and intervention_box.contains(*text_bounds.p1)
    bounds = np.array([p.get_window_extent().extents for p in boxes])*mm_per_px
    for row in (bounds[:4], bounds[4:6], bounds[6:8], bounds[8:12]):
        assert np.max(np.ptp(row[:, [1, 3]], axis=0)) < .01
        assert np.ptp(row[:,2]-row[:,0]) < .01
        assert np.ptp(row[1:,0]-row[:-1,2]) < .01
    assert np.allclose(bounds[:4, [0,2]], bounds[8:12, [0,2]])
    assert np.allclose(bounds[4:6, [0,2]], bounds[6:8, [0,2]])
    expected_fills = (
        ['white']*4 + [SCENARIO_PALE]*2 + ['white']*2
        + [AVOID_PALE] + [SYSTEM_PALE]*3 + ['white']*3
    )
    assert [patch.get_facecolor() for patch in boxes] == [mpl.colors.to_rgba(fill) for fill in expected_fills]
    (QA / 'Figure1_framework_alignment.json').write_text(
        json.dumps({'status':'PASS','box_bounds_mm':bounds.tolist()},indent=2)+'\n',encoding='utf-8')
    require_matplotlib_panel_alignment(
        fig, axes=plot_axes, exclude_axes=[ax], panel_ids=['GTL', 'IBL'], row_groups=[['GTL', 'IBL']],
        json_out=QA / f'{stem}.alignment.json', strict=True, tolerance_pt=1.5, gutter_tolerance_pt=1.5,
    )
    fig.savefig(OUT / f'{stem}.pdf')
    fig.savefig(OUT / f'{stem}.svg')
    fig.savefig(OUT / f'{stem}.png', dpi=300)
    fig.savefig(OUT / f'{stem}.tiff', dpi=600, pil_kwargs={'compression': 'tiff_lzw'})
    plt.close(fig)
    return event_checks


if __name__ == '__main__':
    evidence = {'en': draw('en', 0)}
    (QA / 'schematic_events.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
