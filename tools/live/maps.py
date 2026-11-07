# MiniLab 3 maps for acid.py, minilab.py and the virtual controller page (board.py). One source, so the page labels what the
# hardware does. cc -> (module, param, scale 0-127 -> Rack value, label). Plus helpers the page uses: to_cc, pad_labels.
import json, os, re
import sections as S
C = json.load(open(os.path.join(S.here, 'deckc.json')))['C']
KNOBS, FADERS = (74, 71, 76, 77, 93, 18, 16, 19), (82, 83, 85, 17)        # hardware order: knob 1-8, fader 1-4 (factory map)

lin = lambda v: round(v / 127, 3)
from synths import ARP, TRI
ACID = {   # MiniLab "Synths" (Keys button): Acid Bass, plus the arp's gate (knob 4) and Triple's cutoff (knob 6)
    82: (S.ACID, 1, lin, 'cutoff'), 83: (S.ACID, 2, lin, 'resonance'), 85: (S.ACID, 3, lin, 'env mod'), 17: (S.ACID, 4, lin, 'decay'),
    74: (S.ACID, 5, lin, 'accent'), 71: (S.ACID, 6, lin, 'volume'), 76: (S.ACID, 23, lin, 'gate length'),
    77: (ARP, 19, lambda v: round(0.05 + v / 127 * 0.9, 3), 'arp gate'),            # swing stays 0: Clocked already swings
    93: (S.ACID, 15, lin, 'high-pass'), 18: (TRI, 28, lambda v: round(7.0 + v / 127 * 6.3, 3), 'arp bright'),   # 128 Hz .. 10 kHz (log2)
    16: (S.ACID, 28, lambda v: float(round((v - 64) / 64 * 12)), 'transpose'),     # Acid TRANSPOSE: the arp follows it
    19: (S.ACID, 27, lambda v: 1.0 + round(v / 127 * 31), 'pattern length'),
}
ENV = {    # MiniLab "Acid Env" (User button): Acid Bass filter envelope on the faders, amp envelope on knobs 1-4, tone on knobs 5-8
    82: (S.ACID, 8, lin, 'filter attack'), 83: (S.ACID, 4, lin, 'filter decay'), 85: (S.ACID, 9, lin, 'filter sustain'), 17: (S.ACID, 10, lin, 'filter release'),
    74: (S.ACID, 11, lin, 'amp attack'), 71: (S.ACID, 12, lin, 'amp decay'), 76: (S.ACID, 13, lin, 'amp sustain'), 77: (S.ACID, 14, lin, 'amp release'),
    93: (S.ACID, 3, lin, 'env mod'), 18: (S.ACID, 5, lin, 'accent'), 16: (S.ACID, 1, lin, 'cutoff'), 19: (S.ACID, 2, lin, 'resonance'),
}
ACID_TOLS = {(S.ACID, 28): 1.0, (S.ACID, 27): 1.0, (TRI, 28): 0.15}                       # pickup widths: stepped params within one step count as caught; Triple cutoff (log2 Hz) within 0.15
TOP = 1.5                                                               # fader at the top = Recycler level 1.5 (max 2.0)
fader = lambda v: round(v / 127 * TOP, 3)
knob = lambda v: round(max(-1.0, min(1.0, (v - 64) / 63)), 3)           # filter: centre off, left low-pass, right high-pass
PAGEF = os.path.join(S.here, 'page.txt')                               # the Launchpad page on show (pads.py writes it): 0 Lowdown, 1 TOOM
def page_now():
    try: return int(open(PAGEF).read().strip())
    except (OSError, ValueError): return 0
SONG_PARTS = [('vocals', 'keys', 'horns', 'bass'), ('vocals', 'piano', 'guitar/horns', 'bass')]   # slots 3, 1, 2, 0 per page
def mix_map(page=None):   # drums + mix: faders / knobs 1-4 = the sample tracks of the song on show; drums the same on both songs
    page = page_now() if page is None else page
    d, m = (S.A if page == 0 else S.B), {}
    for (fcc, kcc), k, part in zip(((82, 74), (83, 71), (85, 76), (17, 77)), (3, 1, 2, 0), SONG_PARTS[page]):
        m[fcc] = (d, 14 + k, fader, f'{part} vol'); m[kcc] = (d, 24 + k, knob, f'{part} filter')
    m.update({93: (C, 24, knob, 'sample drums filter'), 18: (C, 14, fader, 'sample drums vol'),   # the record's drum stem (deck C)
              16: (S.DRUMS, 5, fader, 'drum machine vol')})                                    # My lil Drums' own level: 0 = off
    return m
MIX = mix_map(0)

ACID_NAMES = {10: 'Lowdown vamp', 14: 'TOOM vamp', 16: 'walk-down'}
acid_name = lambda v: ACID_NAMES.get(v, f'I-{"ABCD"[v // 8]}{v % 8 + 1}')   # Acid Bass pattern index -> its bank name
MODES = {                                                               # pads = (module, param, first value, pad count)
    'acid': dict(title='Synths', cc=ACID, pads=(S.ACID, 24, 8, 16), pad_label=acid_name,
                 keys='play the bass, 1 octave down · hold into the next key = slide · hit hard = accent (the arp follows)'),
    'mix': dict(title='Drums + mix', cc=MIX, pads=(S.DRUMS, 3, 0, 8), pad_label=lambda v: f'beat {v + 1}',
                keys='My lil Drums volume · far left silent → far right full'),
}
MODES['env'] = dict(title='Acid Env', cc=ENV, pads=MODES['acid']['pads'], pad_label=acid_name, keys=MODES['acid']['keys'])   # pads + keys as Synths

def to_cc(f, value):                                                    # Rack value -> the 0-127 position whose scale lands closest
    return min(range(128), key=lambda v: abs(f(v) - value))

def pad_labels(samples):                                                # Launchpad pad text from the row's sample files
    half = lambda f: (re.search(r'-chop4([ab])\.wav$', f) or [None, None])[1]                  # chop4a / chop4b = 4-bar half A / B -> 'a' / 'b'
    parts = [re.match(r'\d-([a-z]+)-(\d\d)(?:_([a-z]+))?', f).groups() + ('chop' in f and not half(f), half(f)) for f in map(os.path.basename, samples)]
    mixed_stem, mixed_chop = len({s for s, *_ in parts}) > 1, len({c for *_, c, _ in parts}) > 1
    return [(({'other': 'strings', 'mix': 'full'}.get(s, s) + ' ') if mixed_stem else '') + n + (f' {w}' if w else '')
            + (' chop' if c and mixed_chop else '') + (f' {h}' if h else '') for s, n, w, c, h in parts]   # w = section word in the file name (toom: 05_verse)

LEVELF = os.path.join(S.here, 'drums_level.json')                       # the drum machine's level from before a pad turned it off
def drum_pad(i):   # drums + mix pad i: pick beat i + 1; the playing beat again = drum beat off; any pad while off = on, that beat
    p = {x['id']: x['value'] for x in json.loads(S.call('vcvrack_get_params', {'moduleId': S.DRUMS}))}
    off = p[5] > 0.001 and round(p[3]) == i                             # param 5 = My lil Drums mix level (keys keep the Mixer strip)
    if off: json.dump({'level': p[5]}, open(LEVELF, 'w')); v = [{'id': 5, 'value': 0.0}]
    else:
        v = [{'id': 3, 'value': i}]
        if p[5] <= 0.001: v.append({'id': 5, 'value': json.load(open(LEVELF))['level'] if os.path.exists(LEVELF) else 0.8})
    S.call('vcvrack_set_params', {'moduleId': S.DRUMS, 'params': v})
    return off

def drum_machine(on=None):   # My lil Drums alone (not the record's drum stem): None = flip. Same level switch as the beat pads.
    lv = next(x['value'] for x in json.loads(S.call('vcvrack_get_params', {'moduleId': S.DRUMS})) if x['id'] == 5)
    now = lv > 0.001
    if on is None: on = not now
    if on and not now: S.call('vcvrack_set_params', {'moduleId': S.DRUMS, 'params': [{'id': 5, 'value': json.load(open(LEVELF))['level'] if os.path.exists(LEVELF) else 0.8}]})
    if now and not on: json.dump({'level': lv}, open(LEVELF, 'w')); S.call('vcvrack_set_params', {'moduleId': S.DRUMS, 'params': [{'id': 5, 'value': 0.0}]})
    return on