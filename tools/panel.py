#!/usr/bin/env python3
"""panel.py: writes res/Recycler.svg and src/layout.hpp from one layout table.

Labels become paths (DejaVu Sans from the Rack install, or the font named by RACK_FONT), so the SVG has no <text>,
as the VCV panel guide asks. The widgets read the same table through layout.hpp, so art and components cannot drift.
House style as in My lil Looper / Acid Bass / Toolbox. Run from anywhere: py -3.11 tools/panel.py   (needs fontTools).
Author: Ari Klopfer / A_Development. MIT
"""
import math
import os
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

H = 128.5
W = 5.08 * 36
BAND = 8.6
INK, INK2 = '#16161a', '#202027'
LIME, MAGENTA, BLUE, WHITE, DIM = '#c8ff3a', '#ff3d9a', '#5ac8e6', '#f2f2f4', '#8d8d96'
WELL = '#0f0f12'              # backing of the regions the module draws text into (as in My lil Drums)
FONT = os.environ.get('RACK_FONT', r'C:\Program Files\VCV\Rack2Free\res\fonts\DejaVuSans.ttf')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Round parts: radius in mm, from the Rack component SVGs: knob Rogan1PS, small = small knob (LEVEL), button VCVButton
# (the MODE / BARS switches take a button-size spot), out = output jack, light = an LED the module draws (kept clear,
# no art, no label). Input jacks by role, ring coloured as in My lil Acid Bass: seq = clock / reset / run / triggers
# (blue), cv = modulation (magenta).
RADIUS = {'knob': 6.7, 'small': 4.0, 'button': 3.1, 'seq': 4.0, 'cv': 4.0, 'out': 4.0, 'light': 1.5}
LABEL_SIZE = {'knob': 2.6, 'small': 2.0, 'button': 2.0, 'seq': 2.4, 'cv': 2.4, 'out': 2.6}
RING_COLOR = {'seq': BLUE, 'cv': MAGENTA}
PAD_R = 4.8                   # dark plate behind an output jack
RING_R = RADIUS['cv'] + 0.7   # ring around an input jack

font = TTFont(FONT)
glyphs, cmap, upm = font.getGlyphSet(), font.getBestCmap(), font['head'].unitsPerEm


def width(s, size):
    """Advance width of the string in mm at this em size."""
    return sum(glyphs[cmap[ord(c)]].width for c in s) * size / upm


def text(s, x, y, size, fill, anchor='middle', stroke=0.0):
    """One <path> for the string: baseline at y, em size in mm, optional stroke for a bolder face."""
    k = size / upm
    w = width(s, size)
    pen_x = x - w / 2 if anchor == 'middle' else x - w if anchor == 'end' else x
    d = []
    for c in s:
        g = glyphs[cmap[ord(c)]]
        pen = SVGPathPen(glyphs)
        g.draw(TransformPen(pen, (k, 0, 0, -k, pen_x, y)))
        d.append(pen.getCommands())
        pen_x += g.width * k
    bold = ' stroke="%s" stroke-width="%g" stroke-linejoin="round"' % (fill, stroke) if stroke else ''
    return '<path fill="%s"%s d="%s"/>' % (fill, bold, ' '.join(d))


# ---- the title band, as in My lil Toolbox: Rack's screws sit in its corners (5.08 mm squares at x 5.08 and
# W - 10.16), so the title starts right of the left one and the face sits left of the right one
TITLE, TITLE_X, TITLE_Y, TITLE_SIZE = 'MY LIL RECYCLER', 11.2, 6.3, 4.3
MASCOT_X = W - 14.46
MASCOT_R = BAND * 0.36


def mascot(cx, cy, r):
    """The My lil face: magenta disc, dot eyes, a flat mouth (src/TalkingFace.hpp paints the live mouth over it)."""
    e = r * 0.37
    return ''.join([
        '<circle cx="%g" cy="%g" r="%g" fill="%s"/>' % (cx, cy, r, MAGENTA),
        '<circle cx="%g" cy="%g" r="%g" fill="%s"/>' % (cx - e, cy - r * 0.32, r * 0.145, INK),
        '<circle cx="%g" cy="%g" r="%g" fill="%s"/>' % (cx + e, cy - r * 0.32, r * 0.145, INK),
        '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-width="%g" stroke-linecap="round"/>'
        % (cx - r * 0.58, cy + r * 0.45, cx + r * 0.58, cy + r * 0.45, INK, r * 0.16),
    ])


def band_boxes():
    return [('title', (TITLE_X, TITLE_Y - 0.73 * TITLE_SIZE, TITLE_X + width(TITLE, TITLE_SIZE), TITLE_Y)),
            ('mascot', (MASCOT_X - MASCOT_R, BAND / 2 - MASCOT_R, MASCOT_X + MASCOT_R, BAND / 2 + MASCOT_R))]


# ---- layout: library row, lock row (knobs over jacks), four stem rows, combo row
ROW_LIB, ROW_LOCK, ROW_JACK = 18.0, 34.0, 49.0   # jacks 1 mm up from 50: their labels end above the zone
STEM_Y = [63.6 + 13.0 * i for i in range(4)]   # from 64: row 3's L / R labels keep the same 0.6 mm to the MIX plates as every row
ROW_COMBO = 115.6   # up from 118: MIX R's label clears the bottom-right screw, MIX pads clear the row-3 labels
ROLES = ('DRUMS', 'BASS', 'MELODY', 'TEXTURE')
OUT_LX, OUT_RX = 165.8, 175.5   # 10 HP right of 2.1's 115.0 / 124.7: the R plate keeps the 2.5 mm zone margin
ZONE_X, ZONE_Y, ZONE_B = 2.5, 57.0, 126.0
SEP_Y = 57.0
CAPTION_X, CAPTION_SIZE = 5.0, 2.2
FOOTER = ('A_DEVELOPMENT', W - 11.2, 127.9, 2.2)   # left of the bottom-right screw, below the zone   # text, right edge x, baseline, size

# Regions the module draws into: x, y, w, h in mm
REGIONS = {'PATH_BOX': (16.0, ROW_LIB - 3.5, 100.0, 7.0)}
NAME_BOX = [(4.0, y - 3.0, 54.0, 6.0) for y in STEM_Y]

# (name, kind, x, y, label). A name ending in '+i' is stem i of a per-stem array.
RECYCLER = [
    ('FOLDER_PARAM', 'button', 10.0, ROW_LIB, 'FOLDER'),
    ('LIB_LIGHT', 'light', 122.0, ROW_LIB, ''),
    ('BPM_PARAM', 'knob', 14.0, ROW_LOCK, 'BPM'), ('ROOT_PARAM', 'knob', 34.0, ROW_LOCK, 'ROOT'),
    ('MODE_PARAM', 'button', 52.0, ROW_LOCK, 'MODE'), ('BARS_PARAM', 'button', 66.0, ROW_LOCK, 'BARS'),
    ('RUN_PARAM', 'button', 82.0, ROW_LOCK, 'RUN'), ('RUN_LIGHT', 'light', 88.0, 29.0, ''),
    ('CLOCK_INPUT', 'seq', 14.0, ROW_JACK, 'CLOCK'), ('VOCT_INPUT', 'cv', 34.0, ROW_JACK, 'V/OCT'),
    ('RESET_INPUT', 'seq', 52.0, ROW_JACK, 'RESET'), ('RUN_INPUT', 'seq', 66.0, ROW_JACK, 'RUN'),
] + [part for i, y in enumerate(STEM_Y) for part in (
    ('ROLL_PARAM+%d' % i, 'button', 66.0, y, 'ROLL'),
    ('LOCK_PARAM+%d' % i, 'button', 76.0, y, 'LOCK'),
    ('LOCK_LIGHT+%d' % i, 'light', 80.5, y - 4.0, ''),
    ('LEVEL_PARAM+%d' % i, 'small', 90.0, y, 'LEVEL'),
    ('PITCH_PARAM+%d' % i, 'small', 101.0, y, 'PITCH'),
    ('FILTER_PARAM+%d' % i, 'small', 111.0, y, 'FILT'),
    ('PAN_PARAM+%d' % i, 'small', 121.0, y, 'PAN'),
    ('START_PARAM+%d' % i, 'small', 131.0, y, 'START'),
    ('REV_PARAM+%d' % i, 'button', 141.0, y, 'REV'),
    ('REV_LIGHT+%d' % i, 'light', 145.5, y - 4.0, ''),
    ('ROLL_INPUT+%d' % i, 'seq', 154.8, y, 'ROLL'),
    ('OUT_L_OUTPUT+%d' % i, 'out', OUT_LX, y, 'L'),
    ('OUT_R_OUTPUT+%d' % i, 'out', OUT_RX, y, 'R'),
)] + [
    ('BATCH_PARAM', 'button', 14.0, ROW_COMBO, 'BATCH'), ('BATCH_INPUT', 'seq', 26.0, ROW_COMBO, 'BATCH'),   # +4 mm: label clears the screw
    ('CHAOS_PARAM', 'knob', 40.0, ROW_COMBO, 'CHAOS'), ('CHAOS_INPUT', 'cv', 56.0, ROW_COMBO, 'CV'),
    ('RENDER_LIGHT', 'light', 68.0, ROW_COMBO, ''),
    ('MIX_L_OUTPUT', 'out', OUT_LX, ROW_COMBO, 'MIX L'), ('MIX_R_OUTPUT', 'out', OUT_RX, ROW_COMBO, 'MIX R'),
]


def region_boxes():
    """(name, (x0, y0, x1, y1)) for every module-drawn region."""
    out = [(n, (x, y, x + w, y + h)) for n, (x, y, w, h) in REGIONS.items()]
    return out + [('NAME_BOX %d' % i, (x, y, x + w, y + h)) for i, (x, y, w, h) in enumerate(NAME_BOX)]


def caption_base(y):
    """Baseline of a stem's role caption, centred on the row (cap height 0.73 em)."""
    return y + 0.73 * CAPTION_SIZE / 2


def extras():
    out = ['<rect x="%g" y="%g" width="%g" height="%g" rx="2" fill="%s"/>' % (ZONE_X, ZONE_Y, W - 2 * ZONE_X, ZONE_B - ZONE_Y, INK2),
           '<rect x="%g" y="%g" width="%g" height="0.3" fill="%s"/>' % (ZONE_X + 2, SEP_Y, W - 2 * ZONE_X - 4, DIM)]
    out += ['<rect x="%g" y="%g" width="%g" height="%g" rx="1" fill="%s"/>' % (b[0], b[1], b[2] - b[0], b[3] - b[1], WELL)
            for _, b in region_boxes()]
    out += [text(r, CAPTION_X, caption_base(y), CAPTION_SIZE, DIM, 'start') for r, y in zip(ROLES, STEM_Y)]
    return out


def reach(kind):
    return RING_R if kind in RING_COLOR else PAD_R if kind == 'out' else RADIUS[kind]


def label_at(kind, y, row_bottom):
    """Baseline, size, colour and stroke of the label under a part. Labels in a row share the row's lowest part."""
    colour, stroke = (LIME, 0.25) if kind == 'out' else (WHITE, 0.18)
    low = y + PAD_R if kind == 'out' else row_bottom[y]
    return low + 2.8, LABEL_SIZE[kind], colour, stroke


def row_bottoms(layout):
    rb = {}
    for _, kind, _, y, label in layout:
        if kind != 'out' and label:
            rb[y] = max(rb.get(y, 0), y + reach(kind))
    return rb


def label_box(x, base, size, label, anchor='middle'):
    w = width(label, size)
    x0 = x - w / 2 if anchor == 'middle' else x - w if anchor == 'end' else x
    return x0, base - 0.73 * size, x0 + w, base


SCREW = 5.08


def screws():
    return [(x, y, x + SCREW, y + SCREW) for x in (SCREW, W - 2 * SCREW) for y in (0, H - SCREW)]


def box_hits_circle(b, cx, cy, r):
    nx, ny = min(max(cx, b[0]), b[2]), min(max(cy, b[1]), b[3])
    return math.hypot(cx - nx, cy - ny) < r


def boxes_hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def all_labels(layout):
    """(name, box) for every part label, the role captions and the footer."""
    rb = row_bottoms(layout)
    labels = []
    for n, k, x, y, label in layout:
        if label:
            base, size, _, _ = label_at(k, y, rb)
            labels.append((n + ' label', label_box(x, base, size, label)))
    labels += [(r + ' caption', label_box(CAPTION_X, caption_base(y), CAPTION_SIZE, r, 'start')) for r, y in zip(ROLES, STEM_Y)]
    s, x, base, size = FOOTER
    labels.append(('footer', label_box(x, base, size, s, 'end')))
    return labels


def problems(layout):
    """Everything on the panel that touches something else or leaves the panel: parts (rings, plates, lights), their
    labels, the role captions and footer, the module-drawn regions, the band's title and face, Rack's four screws, the
    separator. Parts below the jack zone's top stay inside its side margin; no label straddles the zone's top edge.
    Must be empty."""
    bad = []
    parts = [(n, (x, y, reach(k))) for n, k, x, y, _ in layout]
    labels = all_labels(layout)
    regions = region_boxes()
    sep = (ZONE_X + 2, SEP_Y, W - ZONE_X - 2, SEP_Y + 0.3)
    for j, (a, (x, y, r)) in enumerate(parts):
        e = (x - r, y - r, x + r, y + r)
        for b, (bx, by, br) in parts[j + 1:]:
            if math.hypot(x - bx, y - by) < r + br:
                bad.append('%s touches %s' % (a, b))
        if e[0] < 0 or e[2] > W or e[1] < BAND or e[3] > H:
            bad.append('%s leaves the panel or enters the band' % a)
        if e[3] > ZONE_Y and e[1] < ZONE_B and (e[0] < ZONE_X or e[2] > W - ZONE_X):
            bad.append('%s leaves the jack zone' % a)
        for name, box in labels + regions:
            if name != a + ' label' and box_hits_circle(box, x, y, r):
                bad.append('%s covers %s' % (a, name))
        for s in screws() + [sep]:
            if box_hits_circle(s, x, y, r):
                bad.append('%s under a screw or on the separator' % a)
    boxes = labels + band_boxes()
    for j, (a, box) in enumerate(boxes):
        if box[0] < 0 or box[2] > W or box[3] > H:
            bad.append('%s leaves the panel' % a)
        if box[1] < ZONE_Y < box[3] or box[1] < ZONE_B < box[3]:
            bad.append('%s straddles the jack zone edge' % a)
        for b, other in boxes[j + 1:]:
            if boxes_hit(box, other):
                bad.append('%s overlaps %s' % (a, b))
        for s in screws() + [sep]:
            if boxes_hit(box, s):
                bad.append('%s under a screw or on the separator' % a)
        for name, region in regions:
            inside = a.endswith(' caption') and name.startswith('NAME_BOX')
            if boxes_hit(box, region) and not inside:
                bad.append('%s overlaps %s' % (a, name))
    return bad


def panel(layout):
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" viewBox="0 0 %g %g">' % (W, H, W, H),
        '<rect width="%g" height="%g" fill="%s"/>' % (W, H, INK),
        '<rect width="%g" height="%g" fill="%s"/>' % (W, BAND, LIME),
        text(TITLE, TITLE_X, TITLE_Y, TITLE_SIZE, INK, 'start', 0.39), mascot(MASCOT_X, BAND / 2, MASCOT_R),
    ] + extras()
    rb = row_bottoms(layout)
    for _, kind, x, y, label in layout:
        if kind in RING_COLOR:
            out.append('<circle cx="%g" cy="%g" r="%g" fill="none" stroke="%s" stroke-width="0.5"/>' % (x, y, RING_R, RING_COLOR[kind]))
        elif kind == 'out':
            out.append('<circle cx="%g" cy="%g" r="%g" fill="%s" stroke="%s" stroke-width="0.5"/>' % (x, y, PAD_R, INK, LIME))
        if label:
            base, size, colour, stroke = label_at(kind, y, rb)
            out.append(text(label, x, base, size, colour, stroke=stroke))
    s, x, base, size = FOOTER
    out.append(text(s, x, base, size, DIM, 'end'))
    out.append('</svg>')
    return '\n'.join(out) + '\n'


def header(layout):
    lines = ['// layout.hpp: generated by tools/panel.py, do not edit. Component centres and widget regions in mm.', '#pragma once',
             'namespace layout {', 'namespace recycler {']
    lines += ['constexpr float %s[2] = {%.2ff, %.2ff};' % (n, x, y) for n, _, x, y, _ in layout if '+' not in n]
    stems = {}
    for n, _, x, y, _ in layout:
        if '+' in n:
            stems.setdefault(n.split('+')[0], []).append((x, y))
    lines += ['constexpr float %s[%d][2] = {%s};' % (n, len(p), ', '.join('{%.2ff, %.2ff}' % q for q in p)) for n, p in stems.items()]
    lines += ['constexpr float %s[4] = {%.2ff, %.2ff, %.2ff, %.2ff};   // x, y, w, h' % ((n,) + r) for n, r in REGIONS.items()]
    lines += ['constexpr float NAME_BOX[%d][4] = {%s};   // x, y, w, h' % (len(NAME_BOX), ', '.join('{%.2ff, %.2ff, %.2ff, %.2ff}' % r for r in NAME_BOX))]
    lines += ['constexpr float FACE[3] = {%.2ff, %.2ff, %.3ff};   // mascot centre x, y, radius (TalkingFace)' % (MASCOT_X, BAND / 2, MASCOT_R)]
    lines += ['}', '}', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    for n, k, x, y, label in RECYCLER:
        print('%-16s %-6s %7.2f %7.2f  %s' % (n, k, x, y, label))
    bad = problems(RECYCLER)
    assert not bad, '\n'.join(bad)
    files = {os.path.join('res', 'Recycler.svg'): panel(RECYCLER), os.path.join('src', 'layout.hpp'): header(RECYCLER)}
    for rel, body in files.items():
        with open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as f:
            f.write(body)
    print('wrote', ', '.join(files), '(%d components), no problems' % len(RECYCLER))
