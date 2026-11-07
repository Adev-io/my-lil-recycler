# Row 8 (notes 11-18) = transition moves made from the Recycler's own controls (filter, reverse) and the Mixer strips.
# Stateless: pads.py keeps the toggles and runs the sweeps. Filter -1..1 per slot: left low-pass, right high-pass, 0 off.
import json, os
import sections as S
C = json.load(open(os.path.join(S.here, 'deckc.json')))['C']
FX = {11: 'sweep up', 12: 'sweep down', 13: 'reverse', 14: 'drums only', 15: 'no drums', 16: 'dnb', 17: 'transition', 18: 'clean'}
COLOR = 49
BASE = [0.0, 0.3, 0.3, 0.0, 0.0,      # resting filters: deck A bass, keys, horns, vocals (keys + horns HP'd in the balance pass), deck C drums,
        0.0, 0.0, 0.0, 0.0]            # deck B (page 2, Time Out Of Mind) bass, piano, guitar, vocals: moves work on every page
SWEEP_SECS = 8.0                       # 4 bars at 120 BPM
HP, LP = 0.85, -0.85
STEP = 0.25                            # ponytail: 4 MCP calls/s; the Recycler smooths the filter between steps
def set_filters(v):                    # v = 9 values in BASE order
    S.call('vcvrack_set_params', {'moduleId': S.A, 'params': [{'id': 24 + k, 'value': v[k]} for k in range(4)]})
    S.call('vcvrack_set_params', {'moduleId': C, 'params': [{'id': 24, 'value': v[4]}]})
    S.call('vcvrack_set_params', {'moduleId': S.B, 'params': [{'id': 24 + k, 'value': v[5 + k]} for k in range(4)]})
def reverse(on, decks=None):          # music decks only (reversed drums lose the groove); default both, the moves row passes one
    for deck in (decks or (S.A, S.B)): S.call('vcvrack_set_params', {'moduleId': deck, 'params': [{'id': 36 + k, 'value': 1.0 if on else 0.0} for k in range(4)]})
def strip(k, on):                      # Mixer strip k (2 = deck A music, 3 = deck B music, 4 = deck C drums): unity or silent
    S.call('vcvrack_set_params', {'moduleId': S.MIX, 'params': [{'id': k, 'value': S.U if on else 0.0}]})
def clean():
    set_filters(BASE); reverse(False); strip(2, True); strip(3, True); strip(4, True)

# Per song (2026-11-06, Ari: "sweep is only for samples ... a sweep up and down for each [song]" + "a transition from one song
# to another"). A song = its own deck (page 1 Lowdown = A, page 2 Time Out Of Mind = B) + deck C while its drums row plays.
STRIP = {S.A: 2, S.B: 3, C: 4}                                     # Mixer strip per deck
BASEF = {S.A: BASE[0:4], C: BASE[4:5], S.B: BASE[5:9]}             # resting filters per deck (deck C: its drums slot only)
TRANS_SECS = 16.0                                                  # 8 bars at 120: the loops a transition brings in land inside it
FIRST = (71, 41, 21)                                               # silent song on show: a transition brings in pad 1 of these rows
def song_decks(page, on):
    return [S.A if page == 0 else S.B] + ([C] if on[page].get(21) is not None else [])
def deck_filters(d): return [p['value'] for p in json.loads(S.call('vcvrack_get_params', {'moduleId': d})) if 24 <= p['id'] < 24 + len(BASEF[d])]
def set_deck_filters(d, v): S.call('vcvrack_set_params', {'moduleId': d, 'params': [{'id': 24 + k, 'value': x} for k, x in enumerate(v)]})
def transition(page, on, alive):   # the song not on show sweeps up + fades out; the song on show fades in. Returns False if cut off.
    rows, other = S.PAGES[page]['rows'], 1 - page
    own = S.A if page == 0 else S.B; mix = strips()
    if not any(v is not None for v in S.now(rows).values()):       # nothing of it playing (asked of the rig): bring in its verse pads
        for b in FIRST:
            r = rows[b]; S.play(r['slot'], r['samples'][0], r['level'], r.get('deck')); on[page][b] = 0
        S.call('vcvrack_set_params', {'moduleId': S.MIX, 'params': [{'id': STRIP[own], 'value': 0.0}]}); mix[STRIP[own]] = 0.0
    inn = song_decks(page, on); out = [d for d in song_decks(other, on) if d not in inn]
    f0 = {d: deck_filters(d) for d in inn + out}; t0 = time.time()
    while True:
        if not alive(): return False
        x = min(1.0, (time.time() - t0) / TRANS_SECS); e = x * x * (3 - 2 * x)
        for d in out: set_deck_filters(d, [a + (HP - a) * e for a in f0[d]])
        for d in inn: set_deck_filters(d, [a + (b - a) * e for a, b in zip(f0[d], BASEF[d])])
        S.call('vcvrack_set_params', {'moduleId': S.MIX, 'params': [{'id': STRIP[d], 'value': mix[STRIP[d]] * (1 - e)} for d in out]
                                      + [{'id': STRIP[d], 'value': mix[STRIP[d]] + (S.U - mix[STRIP[d]]) * e} for d in inn]})
        if x >= 1.0: break
        time.sleep(STEP)
    for b, r in S.PAGES[other]['rows'].items():                   # the old song's pads go dark with it
        if r.get('deck', S.A) in out: on[other][b] = None
    for d in out:                                                  # the old song's rows stop; its deck is ready for next time
        S.call('vcvrack_set_params', {'moduleId': d, 'params': [{'id': 14 + k, 'value': 0.0} for k in range(len(BASEF[d]))]})
        set_deck_filters(d, BASEF[d]); S.call('vcvrack_set_params', {'moduleId': S.MIX, 'params': [{'id': STRIP[d], 'value': S.U}]})
    return True

# Pad 16 'dnb' = drum + bass section: My lil Drums + Acid Bass only, tempo on an ADSR. Press: attack from the set's tempo -> peak, decay -> sustain,
# held there. Press again: release back to the tempo from before and every strip back where it was. Peak above sustain = overshoot then settle.
import time
CLOCK = json.load(open(os.path.join(S.here, 'clock.json')))['CLOCK']
BPM = 120.0
DNB = dict(attack=8.0, decay=0.0, peak=140.0, sustain=140.0, release=8.0)   # seconds / BPM
DNB_KEEP = (0, 1)                      # Mixer strips kept: 0 My lil Drums, 1 Acid Bass. Deck A, B, C and Acid Voice fade out.
def bpm(v=None):
    if v is None: return next(p['value'] for p in json.loads(S.call('vcvrack_get_params', {'moduleId': CLOCK})) if p['id'] == 0)
    S.call('vcvrack_set_params', {'moduleId': CLOCK, 'params': [{'id': 0, 'value': round(v, 2)}]})
def strips(): return [p['value'] for p in json.loads(S.call('vcvrack_get_params', {'moduleId': S.MIX})) if p['id'] < 8]   # 8 strip levels
def set_strip_map(m): S.call('vcvrack_set_params', {'moduleId': S.MIX, 'params': [{'id': k, 'value': v} for k, v in m.items()]})
def set_strips(v): S.call('vcvrack_set_params', {'moduleId': S.MIX, 'params': [{'id': k, 'value': x} for k, x in enumerate(v)]})
def ramp(to_bpm, to_strips, secs, alive):          # eased move from where the rig is now; False if another press took over
    b0, s0, t0 = bpm(), strips(), time.time()
    while True:
        if not alive(): return False
        x = min(1.0, (time.time() - t0) / secs) if secs > 0 else 1.0; e = x * x * (3 - 2 * x)
        bpm(b0 + (to_bpm - b0) * e); set_strips([a + (b - a) * e for a, b in zip(s0, to_strips)])
        if x >= 1.0: return True
        time.sleep(STEP)
BREAK = 9                              # My lil Drums pattern 9 = Amen-style 2-bar break (written 2026-11-05; old one in drums_pattern9.bak.json)
def snapshot(): return dict(strips=strips(), drums=S.current_drum_pattern(), bpm=bpm())   # the set's tempo, not a fixed 120
def restore(snap): bpm(snap.get('bpm', BPM)); set_strips(snap['strips']); S.drum_pattern(snap['drums'])
def dnb_on(snap, alive):               # the break kicks in on the press
    S.drum_pattern(BREAK)
    keep = [v if k in DNB_KEEP else 0.0 for k, v in enumerate(snap['strips'])]
    if ramp(DNB['peak'], keep, DNB['attack'], alive) and DNB['decay'] > 0: ramp(DNB['sustain'], keep, DNB['decay'], alive)
def dnb_off(snap, alive):              # the break rides the release down, then the old pattern returns. True = it finished
    if ramp(snap.get('bpm', BPM), snap['strips'], DNB['release'], alive): S.drum_pattern(snap['drums']); return True
    return False
def dnb_arm(state):                    # state['snap'] = the rig before the first dnb press; a release cut off mid-ramp keeps it, so the next press doesn't snapshot the half-way rig
    if state['snap'] is None: state['snap'] = snapshot()
    return state['snap']
def dnb_release(state, alive):         # snapshot dropped once the release has finished (and is still the latest press)
    if dnb_off(state['snap'], alive) and alive(): state['snap'] = None

# Bank 2 (2026-11-06, Ari: the round button at the right end of the moves row flips to 8 more moves). pads.py keeps the toggles.
FX2 = {11: 'acid in/out', 12: 'arp in/out', 13: 'voice in/out', 14: 'acid sweep', 15: 'break fill', 16: 'no bass', 17: 'no vocals', 18: 'breakdown'}
FX3 = {11: 'drums in/out', 12: 'vox 1/4', 13: 'vox 1/8', 14: 'vox 1/16', 15: 'vox 1/32'}   # bank 3: tracked drums fade, vox stutter holds; 16-18 free
BANKS = [FX, FX2, FX3]
FADE_BARS = 4                                                      # drums in/out: the record's drum stem (deck C strip) fades over 4 bars
BANK_CC = 19                                                       # right column, bottom round button (end of the moves row)
STRIP_TOGGLE = {'acid in/out': (1, S.U), 'arp in/out': (6, 0.5), 'voice in/out': (5, 0.3)}   # Mixer strip, level if none was saved
SLOT_TOGGLE = {'no bass': 0, 'no vocals': 3}                       # deck slot of the song on show (both decks: 0 bass, 3 vocals)
BREAKDOWN_LP = -0.6                                                # breakdown: the song on show low-passed, drums out
own_deck = lambda page: S.A if page == 0 else S.B
def slot_level(d, k, v=None):
    if v is None: return next(p['value'] for p in json.loads(S.call('vcvrack_get_params', {'moduleId': d})) if p['id'] == 14 + k)
    S.call('vcvrack_set_params', {'moduleId': d, 'params': [{'id': 14 + k, 'value': v}]})
def acid_cutoff(v=None):                                           # My lil Acid Bass param 1, 0..1
    if v is None: return next(p['value'] for p in json.loads(S.call('vcvrack_get_params', {'moduleId': S.ACID})) if p['id'] == 1)
    S.call('vcvrack_set_params', {'moduleId': S.ACID, 'params': [{'id': 1, 'value': round(v, 3)}]})
def bars_secs(n): return n * 4 * 60.0 / bpm()

# Bank 3 vox stutter (2026-11-06, Recycler 2.4.0 STUT, docs/superpowers/specs/2026-11-06-recycler-stutter-design.md): hold pads on the
# vocals slot of the song on show. state['vox'] = {note: (deck, name, hw)} in press order; pads.py calls these under HOLDL.
STUT, STUTLEN, VOX_SLOT = 40, 44, 3                                # STUT_PARAM 40-43 (hold per slot), STUTLEN_PARAM 44 (0 = 1/4 bar .. 3 = 1/32)
VOX_STUT = {'vox 1/4': 0, 'vox 1/8': 1, 'vox 1/16': 2, 'vox 1/32': 3}
def vox_stut(deck, div):                                           # div None = let go; else length + hold in one call
    S.call('vcvrack_set_params', {'moduleId': deck, 'params': [{'id': STUT + VOX_SLOT, 'value': 0.0}] if div is None else
                                  [{'id': STUTLEN, 'value': float(div)}, {'id': STUT + VOX_SLOT, 'value': 1.0}]})
def vox_on(state, note, name, deck, hw):                           # a press: hold (another vox pad held on that deck = slide, no let go)
    if note in state['vox']: return vox_off(state, note)           # a held pad again (a page click) = let go
    vox_stut(deck, VOX_STUT[name]); state['vox'][note] = (deck, name, hw)   # held only once the rig took it
    if hw and note not in state['down']: vox_off(state, note)     # quick stab: the pad came up before the hold landed
    return True
def vox_off(state, note):                                          # let go; the deck it started on, whatever page is on show now
    v = state['vox'].get(note)
    if v is None: return False                                     # already let go (clean, a page click, the other release path)
    same = [n for n, x in state['vox'].items() if x[0] == v[0]]   # vox pads held on that deck, press order
    if len(same) == 1: vox_stut(v[0], None)                        # the last one off lets go
    elif same[-1] == note: vox_stut(v[0], VOX_STUT[state['vox'][same[-2]][1]])   # the latest off: back to the length of the one still held
    del state['vox'][note]; return True                            # (a failed write above leaves it held: the next press / clean tries again)
def vox_clean(state):                                              # clean: every held vox stutter let go
    for d in {x[0] for x in state['vox'].values()}:
        vox_stut(d, None)                                          # a failed write keeps that deck's pads held
        for n in [n for n, x in state['vox'].items() if x[0] == d]: del state['vox'][n]
def vox_lit(state): return {x[1] for x in list(state['vox'].values())}   # lit from the holds, not state['fx']: the 5 s refresh never touches them