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
def reverse(on, decks=None):          # music decks only (reversed drums lose the groove); default all three songs, the moves row passes one
    for deck in (decks or (S.A, S.B, S.D, *S.SONG_DECKS)): S.call('vcvrack_set_params', {'moduleId': deck, 'params': [{'id': 36 + k, 'value': 1.0 if on else 0.0} for k in range(4)]})
def strip(k, on):                      # Mixer strip k (2 = deck A music, 3 = deck B music, 4 = deck C drums, 7 = deck D music): unity or silent
    set_strip_map({k: S.U if on else 0.0})
def clean(song=None):                  # song: the song playing (pads.py PLAY). A strip that rests at 0 (deck D) opens if its song plays, else
    set_filters(BASE); set_deck_filters(S.D, BASEF[S.D]); reverse(False); strip(2, True); strip(3, True); strip(4, True)   # back to rest: a transition
    if song is not None:                                            # cut off mid-fade leaves no strip part-open. None: deck D's strip left as is
        set_strip_map({STRIP[d]: S.U if own_deck(song) == d else r for d, r in REST.items()})
    err = None                                                      # no Recycler STUT left held (a break & drop cut off), each deck on its own
    for d in (S.A, S.B, S.D, C, *S.SONG_DECKS):
        try: S.call('vcvrack_set_params', {'moduleId': d, 'params': [{'id': STUT + k, 'value': 0.0} for k in range(4)]})
        except Exception as e: err = err or e
    if song is not None:                                            # and the arp on the playing song's keys (one read; a write only if off)
        import synths
        try: synths.follow(lambda: song)
        except Exception as e: err = err or e
    if err: raise err

# Per song (2026-11-06, Ari: "sweep is only for samples ... a sweep up and down for each [song]" + "a transition from one song
# to another"). A song = its own deck (page 1 Lowdown = A, page 2 Time Out Of Mind = B, page 3 Disco Ulysses = D, sections.PAGES
# 'deck') + deck C while its drums row plays.
STRIP = {S.A: 2, S.B: 3, C: 4, S.D: 7, **{x['deck']: x['strip'] for x in S.SONGS['songs']}}   # Mixer strip per deck (8+ = Mixer 2, songs 4+)
BASEF = {S.A: BASE[0:4], C: BASE[4:5], S.B: BASE[5:9], S.D: [0.0] * 4, **{d: [0.0] * 4 for d in S.SONG_DECKS}}   # resting filters per deck (deck C: its drums slot only)
REST = {S.D: 0.0, **{d: 0.0 for d in S.SONG_DECKS}}                                                  # strip level a deck rests at after a transition out (else unity)
FIRST = (71, 41, 21)                                               # silent song on show: break & drop brings in pad 1 of these rows
def heard(mix, paths):                                             # song page -> its strip level, for the songs you hear: strip open and a
    out = {}                                                       # row on its own deck playing (paths: pads.py state['path'], per page row -> sample)
    for k, p in enumerate(S.PAGES):
        if not p['rows']: continue
        lv = mix[STRIP[own_deck(k)]]
        if lv > 0.001 and any(paths[k].get(b) for b, r in p['rows'].items() if r.get('deck', S.A) == own_deck(k)): out[k] = lv
    return out
def playing(mix, paths, page):                                     # startup: the song heard loudest; a tie -> the page on show if tied, else the
    h = heard(mix, paths); top = [k for k, v in h.items() if v == max(h.values())] if h else []   # first; none -> the page on show if a song, else 0
    return (page if page in top else top[0]) if top else page if S.PAGES[page]['rows'] else 0
def song_decks(page, on):
    return [own_deck(page)] + ([C] if on[page].get(21) is not None else [])
def deck_filters(d): return [p['value'] for p in json.loads(S.call('vcvrack_get_params', {'moduleId': d})) if 24 <= p['id'] < 24 + len(BASEF[d])]
def set_deck_filters(d, v): S.call('vcvrack_set_params', {'moduleId': d, 'params': [{'id': 24 + k, 'value': x} for k, x in enumerate(v)]})
# Song-to-song moves (2026-11-06, Ari: "each pair its own"; docs/superpowers/specs/2026-11-06-song-transitions-design.md). The 'transition'
# pad runs the move for (song playing -> song on show). The table is data: retune a pair here. Unlisted pairs: same key = blend, else break & drop.
MOVES = {(0, 1): ('blend', 16), (1, 0): ('blend', 16),                                   # Lowdown <-> TOOM, both D major
         (0, 2): ('break_drop', 4), (2, 0): ('break_drop', 4), (1, 2): ('break_drop', 4), (2, 1): ('break_drop', 4)}   # in / out of Disco (its own move, kept after Disco went to D)
BLEND_ROWS = ((41, 21), (71, 81))      # blend, silent song on show: first half its bass + drums rows come up (pad 1), second half keys + vocals
BREAK_STUT = (0, 0, 1, 2)              # break: STUT LEN per quarter of the break = 1/4, 1/4, 1/8, 1/16 bar (4 bars: one per bar)
CLOSE = LP                             # break: the outgoing filters close. The rig has no echo (2026-11-06: no delay module, Mixer sends 1-2
                                       # and returns unpatched), so a low-pass close stands in for the echo tail
POLL = 0.005                           # clock edge poll (each MCP read takes ~16 ms on its own)
LEVEL_STEP = 0.05                      # blend: Recycler slot LEVEL is unsmoothed, so its ramps write at 20 Hz (Mixer strips slew 5 ms: STEP is fine)
SWAP_GAP = 0.15                        # load_now: the Recycler's worker drops the emptied slot before the new path is written
def quick(n, a):                       # an MCP read that gives up after 1 s (the clock poll must not hang a move); board_check stubs it
    return S.rpc('tools/call', {'name': n, 'arguments': a}, timeout=1.0)['result']['content'][0]['text']
def move_for(frm, to):
    if (frm, to) in MOVES: return MOVES[(frm, to)]
    return ('blend', 16) if S.SCALES.get(frm) == S.SCALES.get(to) else ('break_drop', 4)
def smooth(x): x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)
def mixw(m):                           # strip map {k: v} -> {module: {param: v}}: strips 0-7 = the Mixer, 8-15 = Mixer 2 (songs 4+)
    w = {}
    for k, v in m.items(): w.setdefault(S.MIX if k < 8 else S.MIX2, {})[k % 8] = v
    return w
def put(w):                            # {module: {param: value}}: one set_params per module; S.MIX entries are strip maps (routed by mixw)
    w = dict(w); mx = w.pop(S.MIX, None) or {}
    for m, ps in mixw(mx).items(): w[m] = {**w.get(m, {}), **ps}
    for m, ps in w.items():
        if ps: S.call('vcvrack_set_params', {'moduleId': m, 'params': [{'id': k, 'value': v} for k, v in ps.items()]})
def clock_gate():                      # Clocked master clock out (one pulse a beat: every deck and My lil Drums run on it), volts
    o = json.loads(quick('vcvrack_get_voltages', {'moduleId': CLOCK}))[0]['outputs']
    return next(x['voltages'][0] for x in o if x['id'] == 0)
def next_beat(alive, beat):            # the set clock's next rising edge; None = cut off while waiting; a stopped or unreadable clock = now
    t_end, low = time.time() + 1.5 * beat, None
    while time.time() < t_end:
        if not alive(): return None
        t = time.time()
        try: v = clock_gate()
        except Exception: break
        if v < 5.0: low = t
        elif low is not None: return (low + time.time()) / 2   # between the last low read and this high one
        time.sleep(POLL)
    return time.time()
def next_bar(alive, beat, tp):         # bar 1 of a move = the bar line after the press: the clock beat nearest the press + 4 beats (Rack shows
    e = next_beat(alive, beat)         # no bar counter, so the press marks the downbeat: press on the 1). Waits for it; None = cut off
    if e is None: return None
    t0 = e - beat * round((e - tp) / beat) + 4 * beat
    while t0 < time.time() + 0.05: t0 += 4 * beat                  # setup ran long: the next bar line after that
    while time.time() < t0:
        if not alive(): return None
        time.sleep(min(STEP, t0 - time.time()))
    return t0
def run(t0, total, events, frame, alive, step=STEP):   # events [(secs, fn)] fire once on time, frame(secs) writes the ramps every step; False = cut off
    ev = sorted(events, key=lambda e: e[0])
    while True:
        if not alive(): return False
        t = time.time() - t0
        while ev and ev[0][0] <= t:
            ev.pop(0)[1]()
            if not alive(): return False
        if t >= total: return True
        frame(t)
        time.sleep(max(0.0, min(step, t0 + min(ev[0][0] if ev else total, total) - time.time())))
def setup(page, on, want):             # reads only: what comes in, what goes out, where every deck is now
    rows, own, mix = S.PAGES[page]['rows'], own_deck(page), strips()
    ps = {}; S.now(rows, None, ps)                                 # nothing of it playing on any row page (asked of the rig): bring in pad 1 rows
    bring = [b for b in want if b in rows] if not any(ps.values()) else []
    inn = list(dict.fromkeys([own] + [rows[b].get('deck', S.A) for b in bring] + song_decks(page, on)))
    others = [k for k, p in enumerate(S.PAGES) if p['rows'] and k != page]   # out: decks heard now; one at strip 0 (a Disco cue) keeps its slots + lit pads
    out = list(dict.fromkeys(d for k in others for d in song_decks(k, on) if d not in inn and mix[STRIP[d]] > 0.001))
    P = {d: {p['id']: p['value'] for p in json.loads(S.call('vcvrack_get_params', {'moduleId': d}))} for d in inn + out}
    sounding = lambda b: mix[STRIP[deck_of(rows[b])]] > 0.001 and P[deck_of(rows[b])][14 + rows[b]['slot']] > 0.01   # its slot heard now
    return dict(page=page, rows=rows, own=own, mix=mix, bring=bring, inn=inn, out=out, others=others, P=P, beat=60.0 / bpm(),
                hot=[b for b in bring if sounding(b)], f0={d: [P[d][24 + k] for k in range(len(BASEF[d]))] for d in inn + out})
deck_of = lambda r: r.get('deck', S.A)
def get_state(d):                      # a deck's module state for load_now, data only (read ahead of a tight moment: the air)
    st = json.loads(S.call('vcvrack_get_module_state', {'id': d})); st.pop('params', None); return st
def load_now(d, paths, st=None):       # {slot: path} playing from now: the Recycler lands a new path at its 8-bar loop wrap, or at once in an
    st = st or get_state(d)                                        # empty slot (Recycler.cpp process: pending lands when wrapped ||
    sl = st['data']['slots']                                       # !running || !cur), so empty the slots first, then load. A slot that
    paths = {k: p for k, p in paths.items() if sl[k]['path'] != p}   # has the path already plays it now: left alone (every write re-renders)
    if not paths: return True
    if all(k in paths or not x['path'] for k, x in enumerate(sl)):   # never all four empty at once (the scan would deal the deck a new combo):
        for k, p in paths.items(): sl[k]['path'] = p               # then they wait for the wrap
        S.call('vcvrack_set_module_state', {'id': d, 'state': st}); return False
    for k in paths: sl[k]['path'] = ''
    S.call('vcvrack_set_module_state', {'id': d, 'state': st}); time.sleep(SWAP_GAP)
    for k, p in paths.items(): sl[k]['path'] = p
    S.call('vcvrack_set_module_state', {'id': d, 'state': st}); return True
def bring_in(s, on, rows, level=None, sts={}):   # pad 1 of these brought rows, per deck (level None = as its slot plays now; sts: states read ahead)
    by = {}
    for b in rows: by.setdefault(deck_of(s['rows'][b]), []).append(b)
    for d, bs in by.items():
        load_now(d, {s['rows'][b]['slot']: s['rows'][b]['samples'][0] for b in bs}, sts.get(d))
        if level is not None: put({d: {14 + s['rows'][b]['slot']: level(b) for b in bs}})
        for b in bs: on[s['page']][b] = 0
def lvl(s, b, e, w, a=None):           # a brought-in row from a (default: where it was) to its row level
    r = s['rows'][b]; d = deck_of(r); a = s['P'][d][14 + r['slot']] if a is None else a
    w.setdefault(d, {})[14 + r['slot']] = a + (r['level'] - a) * e
def finish(s, on):                     # the end of every move: the incoming song up first, the old songs' decks silent + reset, THEN their
    for k in s['others']:              # strips back to rest (a strip reopened before its slots are zeroed = a blip of the old song)
        for b, r in S.PAGES[k]['rows'].items():
            if deck_of(r) in s['out']: on[k][b] = None
    w = {}
    for d in s['inn']: w.setdefault(d, {}).update({24 + k: x for k, x in enumerate(BASEF[d])})
    for b in s['bring']: lvl(s, b, 1.0, w)
    for d in s['out']: w.setdefault(d, {}).update({14 + k: 0.0 for k in range(len(BASEF[d]))}); w[d].update({24 + k: x for k, x in enumerate(BASEF[d])})
    put(w)
    put({S.MIX: {**{STRIP[d]: S.U for d in s['inn']}, **{STRIP[d]: REST.get(d, S.U) for d in s['out']}}})   # one Mixer write, after the decks
def transition(page, on, alive, song=None, tp=None):   # song: the song playing (pads.py PLAY, a value or a callable); None = as if the song
    tp = time.time() if tp is None else tp             # on show. tp: the press (bar 1 = the bar line after it)
    frm = song() if callable(song) else song
    name, bars = move_for(page if frm is None else frm, page)
    return (blend if name == 'blend' else break_drop)(page, on, alive, bars, frm, tp)
def blend(page, on, alive, bars, frm=None, tp=None):   # first half: the incoming bass + drums come up under the outgoing song; second half:
    tp = time.time() if tp is None else tp             # the outgoing song high-passes away and fades while the incoming keys + vocals come in
    s = setup(page, on, sum(BLEND_ROWS, ()))
    t0 = next_bar(alive, s['beat'], tp)
    if t0 is None: return False
    H, inn, out, f0, mix, rows = bars / 2 * 4 * s['beat'], s['inn'], s['out'], s['f0'], s['mix'], s['rows']
    cold = [b for b in s['bring'] if b not in s['hot']]            # brought rows on silent slots: loaded at once (they play from bar 1)
    lo, hi = [b for b in BLEND_ROWS[0] if b in cold], [b for b in BLEND_ROWS[1] if b in cold]
    rise = [d for d in inn if any(deck_of(rows[b]) == d for b in lo) and not any(deck_of(rows[b]) == d for b in s['hot'])]
    lo_lv = [b for b in lo if deck_of(rows[b]) not in rise]        # first-half rows on a deck that keeps its strip: slot ramp, every LEVEL_STEP
    def bar1():                        # first half rises on the decks' STRIPS (Mixer slews them: no zipper), its slots at row level
        if rise: put({S.MIX: {STRIP[d]: 0.0 for d in rise}})
        try: bring_in(s, on, cold, lambda b: rows[b]['level'] if b in lo and b not in lo_lv else 0.0)
        except Exception:                                          # the strips never stay down on a failed load: back open, then the error
            if rise: put({S.MIX: {STRIP[d]: S.U for d in rise}})
            raise
        for d in rise: mix[STRIP[d]] = 0.0
        for b in s['hot']:                                         # the shared drums slot sounding (the outgoing drums): the new path
            r = rows[b]; S.play(r['slot'], r['samples'][0], s['P'][deck_of(r)][14 + r['slot']], deck_of(r)); on[page][b] = 0   # lands at the wrap
    last = [-1.0]
    def frame(t):
        w, e1, e2 = {S.MIX: {}}, smooth(t / H), smooth((t - H) / H)
        if t <= H + LEVEL_STEP:                                    # first half, a deck that keeps its strip: slot levels, every LEVEL_STEP
            for b in lo_lv: lvl(s, b, e1, w, 0.0)
        if t >= H:                                                 # second half: keys + vocals slot levels, every LEVEL_STEP
            for b in hi: lvl(s, b, e2, w, 0.0)
        if t - last[0] >= STEP - 1e-9:                             # filters + strips every STEP
            last[0] = t
            if t <= H + STEP:
                for d in inn:
                    w.setdefault(d, {}).update({24 + k: a + (z - a) * e1 for k, (a, z) in enumerate(zip(f0[d], BASEF[d]))})
                    w[S.MIX][STRIP[d]] = mix[STRIP[d]] + (S.U - mix[STRIP[d]]) * e1
            if t >= H:
                for d in out:
                    w.setdefault(d, {}).update({24 + k: a + (HP - a) * e2 for k, a in enumerate(f0[d])}); w[S.MIX][STRIP[d]] = mix[STRIP[d]] * (1 - e2)
        put(w)
    if not run(t0, 2 * H, [(0.0, bar1)], frame, alive, LEVEL_STEP) or not alive(): return False
    finish(s, on); return True
def break_drop(page, on, alive, bars, frm=None, tp=None):   # the outgoing slots stutter (STUT 1/4, 1/4, 1/8, 1/16 bar) as their filters
    import synths                                  # close; beat 4 of the last bar = air; the next downbeat = the incoming song full on.
    tp = time.time() if tp is None else tp         # The arp plays the notes both keys share during the break, the new song's scale
    s = setup(page, on, FIRST)                     # on the drop. False = cut off
    inn, out, f0, beat, rows = s['inn'], s['out'], s['f0'], s['beat'], s['rows']
    brk = out + ([C] if C in inn and s['mix'][STRIP[C]] > 0.001 and s['P'][C][14] > 0.01 else [])   # the shared drums slot breaks too
    late = [b for b in s['bring'] if deck_of(rows[b]) in brk]      # brought rows on a breaking deck: loaded in the air
    a, b_ = S.SCALES.get(frm), S.SCALES.get(page)
    shared = synths.mask_of(set(a) & set(b_)) if a and b_ else None
    held, scaled, done = set(), [], False
    def stut(div):
        held.update(brk)                                           # recorded before the write: a failed write is still let go
        put({d: {STUTLEN: float(div), **{STUT + k: 1.0 for k in range(len(BASEF[d]))}} for d in brk})
    def release():                                                 # each deck on its own: one failed write never keeps another held
        err = None
        for d in list(held):
            try: put({d: {STUT + k: 0.0 for k in range(len(BASEF[d]))}}); held.discard(d)
            except Exception as e: err = err or e
        if err: raise err
    def bar1():
        stut(BREAK_STUT[0])                                        # on the bar line first, the silent setup after it
        if shared is not None: scaled.append(shared); synths.set_mask(shared)
        bring_in(s, on, [b for b in s['bring'] if b not in late], lambda b: 0.0)   # loaded now, silent: running in time by the drop
    def air():
        put({S.MIX: {STRIP[d]: 0.0 for d in brk + inn}}); release()   # strips to 0 first, then STUT let go
        bring_in(s, on, late, None, sts)                           # the drums slot swapped in the silence (state read a bar ahead): set, gap, set
    B = 4 * beat; t_air, total = (bars - 1) * B + 3 * beat, bars * B
    sts = {}
    def last_bar():                                                # the bar before the air: read the late decks' states now, so the air
        for d in {deck_of(rows[b]) for b in late}: sts[d] = get_state(d)   # only writes
    events = ([(0.0, bar1)] + [(k * B, lambda k=k: stut(BREAK_STUT[k * len(BREAK_STUT) // bars])) for k in range(1, bars)]
              + [((bars - 1) * B, last_bar), (t_air, air)])
    def frame(t):
        if t <= t_air + STEP: e = smooth(t / t_air); put({d: {24 + k: x + (CLOSE - x) * e for k, x in enumerate(f0[d])} for d in brk})
    try:
        t0 = next_bar(alive, beat, tp)
        if t0 is None or not run(t0, total, events, frame, alive) or not alive(): return False
        finish(s, on); done = True
        try: synths.set_scale(page)                                # pads' playing() follows the song too: a failed write here is not a failed move
        except Exception: pass
        return True
    finally:
        try:
            if held:                                               # STUT never left held: done, cut off or an error (one retry)
                try: release()
                except Exception: release()
        finally:
            if scaled and not done and frm is not None:            # cut off: the playing song's keys back, unless the arp moved on since
                with synths.ARP_LOCK:
                    if synths.scale_now() == scaled[0]: synths.set_scale(frm)

# Pad 16 'dnb' = drum + bass section: My lil Drums + Acid Bass only, tempo on an ADSR. Press: attack from the set's tempo -> peak, decay -> sustain,
# held there. Press again: release back to the tempo from before and every strip back where it was. Peak above sustain = overshoot then settle.
import time
CLOCK = json.load(open(os.path.join(S.here, 'clock.json')))['CLOCK']
BPM = 120.0
DNB = dict(attack=8.0, decay=0.0, peak=140.0, sustain=140.0, release=8.0)   # seconds / BPM
DNB_KEEP = (0, 1)                      # Mixer strips kept: 0 My lil Drums, 1 Acid Bass. Decks A, B, C, D, Acid Voice and Triple fade out.
def bpm(v=None):
    if v is None: return next(p['value'] for p in json.loads(S.call('vcvrack_get_params', {'moduleId': CLOCK})) if p['id'] == 0)
    S.call('vcvrack_set_params', {'moduleId': CLOCK, 'params': [{'id': 0, 'value': round(v, 2)}]})
def strips():                          # strip levels: the Mixer's 8, then Mixer 2's 8 when songs 4+ are in the rig
    return [p['value'] for m in (S.MIX, S.MIX2) if m for p in json.loads(S.call('vcvrack_get_params', {'moduleId': m})) if p['id'] < 8]
def set_strip_map(m): put({S.MIX: m})
def set_strips(v): set_strip_map(dict(enumerate(v)))
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
SLOT_TOGGLE = {'no bass': 0, 'no vocals': 3}                       # deck slot of the song on show (0 bass, 3 vocals; Disco: 3 = horns/synth)
BREAKDOWN_LP = -0.6                                                # breakdown: the song on show low-passed, drums out
own_deck = lambda page: S.PAGES[page]['deck']                     # the song page's own deck: A Lowdown, B TOOM, D Disco
def slot_level(d, k, v=None):
    if v is None: return next(p['value'] for p in json.loads(S.call('vcvrack_get_params', {'moduleId': d})) if p['id'] == 14 + k)
    S.call('vcvrack_set_params', {'moduleId': d, 'params': [{'id': 14 + k, 'value': v}]})
def acid_cutoff(v=None):                                           # My lil Acid Bass param 1, 0..1
    if v is None: return next(p['value'] for p in json.loads(S.call('vcvrack_get_params', {'moduleId': S.ACID})) if p['id'] == 1)
    S.call('vcvrack_set_params', {'moduleId': S.ACID, 'params': [{'id': 1, 'value': round(v, 3)}]})
def bars_secs(n): return n * 4 * 60.0 / bpm()

# Bank 3 vox stutter (2026-11-06, Recycler 2.4.0 STUT, docs/superpowers/specs/2026-11-06-recycler-stutter-design.md): hold pads on the
# vocals slot of the song playing (pads.py PLAY). state['vox'] = {note: (deck, name, hw)} in press order; pads.py calls these under HOLDL.
STUT, STUTLEN, VOX_SLOT = 40, 44, 3                                # STUT_PARAM 40-43 (hold per slot), STUTLEN_PARAM 44 (0 = 1/4 bar .. 3 = 1/32)
                                                                   # Disco has no vocals: slot 3 there = horns/synth, so vox pads stutter the horns
VOX_STUT = {'vox 1/4': 0, 'vox 1/8': 1, 'vox 1/16': 2, 'vox 1/32': 3}
def vox_deck(mix, paths, page, song):                             # the vocals you hear (2026-11-07: song playing = Disco while Lowdown vocals
    def on(k):                                                     # were up -> vox stuttered Disco's muted horns): the page on show, then the song
        if not S.PAGES[k]['rows']: return False                    # playing, then any song, whose strip is open and its slot 3 row playing;
        d = own_deck(k)                                            # none -> the song playing (old rule)
        return mix[STRIP[d]] > 0.001 and any(paths[k].get(b) for b, r in S.PAGES[k]['rows'].items() if r['slot'] == VOX_SLOT and r.get('deck', S.A) == d)
    return own_deck(next((k for k in [page, song] + list(range(len(S.PAGES))) if on(k)), song))
def vox_stut(deck, div):                                           # div None = let go; else length + hold in one call
    S.call('vcvrack_set_params', {'moduleId': deck, 'params': [{'id': STUT + VOX_SLOT, 'value': 0.0}] if div is None else
                                  [{'id': STUTLEN, 'value': float(div)}, {'id': STUT + VOX_SLOT, 'value': 1.0}]})
def vox_on(state, note, name, deck, hw):                           # a press: hold (another vox pad held on that deck = slide, no let go)
    if note in state['vox']:
        if not hw: return vox_off(state, note)                     # a held pad clicked again on the page = let go
        d = state['vox'][note][0]                                  # a Launchpad re-press never flips it off: the hold re-asserted at the
        same = [x[1] for x in list(state['vox'].values()) if x[0] == d]   # length playing now (the latest pad held on that deck)
        vox_stut(d, VOX_STUT[same[-1]]); return True
    state['vox'][note] = (deck, name, hw)                          # recorded before the write: a false 'held' is safe to let go, a false
    try: vox_stut(deck, VOX_STUT[name])                            # 'not held' is not (a failed write stays held + lit and raises)
    finally:
        if hw and note not in state['down']:                       # quick stab: the pad came up before the hold landed
            try: vox_off(state, note)
            except Exception: vox_off(state, note)                 # one retry; a second failure raises, the pad stays held: press / clean
    return True
def vox_off(state, note):                                          # let go; the deck it started on, whatever page is on show now
    v = state['vox'].get(note)
    if v is None: return False                                     # already let go (clean, a page click, the other release path)
    same = [n for n, x in list(state['vox'].items()) if x[0] == v[0]]   # vox pads held on that deck, press order
    if len(same) == 1: vox_stut(v[0], None)                        # the last one off lets go
    elif same[-1] == note: vox_stut(v[0], VOX_STUT[state['vox'][same[-2]][1]])   # the latest off: back to the length of the one still held
    del state['vox'][note]; return True                            # (a failed write above leaves it held: the next press / clean tries again)
def vox_clean(state):                                              # clean: every held vox stutter let go, each deck on its own
    err = None
    for d in {x[0] for x in list(state['vox'].values())}:
        try: vox_stut(d, None)
        except Exception as e: err = err or e; continue            # a failed write keeps that deck's pads held; the other deck still goes
        for n in [n for n, x in list(state['vox'].items()) if x[0] == d]: del state['vox'][n]
    if err: raise err
def vox_lit(state): return {x[1] for x in list(state['vox'].values())}   # lit from the holds, not state['fx']: the 5 s refresh never touches them
STUT_IDS = range(STUT, STUTLEN + 1)                                # a restore of a Recycler never writes these: no hold left on, none dropped
def no_stut(params): return [p for p in params if p['id'] not in STUT_IDS]