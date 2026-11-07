# My lil Arpeggio + My lil Acid Bass helpers for the live set (rig ids in sections.py, voice.json, triple.json).
# Phase 1: the arp's keys follow the song page (sections.SCALES), held by the Arpeggio's scale lock so a stray click cannot move them.
import json, os, threading
import sections as S
ARP = json.load(open(os.path.join(S.here, 'voice.json')))['ARP']
TRI = json.load(open(os.path.join(S.here, 'triple.json')))['TRIPLE']
ARP_LOCK = threading.RLock()                 # every Arpeggio module-state write goes through here (pads.py threads share it)
def mask_of(pcs): return sum(1 << p for p in set(pcs))
def getp(mid): return {x['id']: x['value'] for x in json.loads(S.call('vcvrack_get_params', {'moduleId': mid}))}
def setp(mid, vals): S.call('vcvrack_set_params', {'moduleId': mid, 'params': [{'id': k, 'value': v} for k, v in vals.items()]})
def arp_data(**kv):                          # read-modify-write of the arp's module data only (dir, gateOuts, locked, lockedMask ...)
    with ARP_LOCK:
        st = json.loads(S.call('vcvrack_get_module_state', {'id': ARP})); st['data'].update(kv)
        st.pop('params', None)               # params stay as Rack has them now (checked live 2026-11-06: a state without 'params' leaves OCT and the keys alone)
        S.call('vcvrack_set_module_state', {'id': ARP, 'state': st}); return st['data']
def set_scale(page):                         # page 0 Lowdown, 1 Time Out Of Mind; any other page keeps the scale playing
    if page not in S.SCALES: return None
    m = mask_of(S.SCALES[page])
    with ARP_LOCK:
        d = json.loads(S.call('vcvrack_get_module_state', {'id': ARP}))['data']
        if d.get('locked') and d.get('lockedMask') == m: return m
        arp_data(locked=True, lockedMask=m)  # the module forces the 12 key latches itself while locked
    return m
def follow(get_page):                        # the page is read inside the lock, so the last page turn wins
    with ARP_LOCK: return set_scale(get_page())
def scale_now():
    d = json.loads(S.call('vcvrack_get_module_state', {'id': ARP}))['data']
    return d.get('lockedMask') if d.get('locked') else None

# ---- phase 3: the Synths page (Launchpad page 3), phrase auto-change, melodic entries
import random, time
import fx                                    # fx imports sections only, so no cycle
A_TRANSPOSE, A_MUTATE, A_AMOUNT, A_UNDO, A_KEEP, A_FILL, A_FILLBTN = range(28, 35)   # Acid Bass 2.3.0 params (appended)
R_OCT, R_INT, R_GATE, R_ROLLN, R_ROLLBTN = 16, 18, 19, 20, 21                        # Arpeggio params (GATE.. = 2.3.0)
def tap(mid, pid):                                                   # a panel button press: the module sees the edge
    setp(mid, {pid: 1.0})
    try: time.sleep(0.1)
    finally: setp(mid, {pid: 0.0})
def mutate(n): setp(S.ACID, {A_AMOUNT: float(n)}); tap(S.ACID, A_MUTATE)
def arp_dir(): return json.loads(S.call('vcvrack_get_module_state', {'id': ARP}))['data'].get('dir', 0)
def direction(d): arp_data(dir=d)                                    # DIR has no param: it is module data (data-only write, ARP_LOCK)
def pattern(v): setp(S.ACID, {24: float(v)})                          # lands at the end of the pattern playing
def fill(mode):                                                      # 0 roll, 1 octave, 2 accent; None = let go (FILL mode stays as set)
    setp(S.ACID, {A_FILLBTN: 0.0} if mode is None else {A_FILL: float(mode), A_FILLBTN: 1.0})
def roll(n):                                                         # None = let go (the ROLLS knob stays as set)
    setp(ARP, {R_ROLLN: float(n), R_ROLLBTN: 1.0} if n else {R_ROLLBTN: 0.0})
def do(kind, arg):
    if kind == 'pattern': pattern(arg)
    elif kind == 'mutate': mutate(arg)
    elif kind == 'undo': tap(S.ACID, A_UNDO)
    elif kind == 'keep': tap(S.ACID, A_KEEP)
    elif kind == 'transpose': setp(S.ACID, {A_TRANSPOSE: float(arg)})
    elif kind == 'dir': direction(arg)
    elif kind == 'oct': setp(ARP, {R_OCT: float(arg)})
    elif kind == 'int': setp(ARP, {R_INT: float(arg)})
def hold(kind, arg, on, saved=None):                                  # held pads: on returns what off needs to put back
    if kind == 'fill': fill(arg if on else None)
    elif kind == 'roll': roll(arg if on else None)
    elif kind == 'octjump':
        if on:
            o = getp(ARP)[R_OCT]
            if o < 4.0: setp(ARP, {R_OCT: min(4.0, o + 1)})          # already at 4: nothing to jump, off puts 4 back
            return o
        setp(ARP, {R_OCT: saved if saved is not None else 1.0})

ROWS = {81: ('acid patterns', 37), 71: ('acid moves', 45), 61: ('fills (hold)', 5), 51: ('arp dir / oct', 21),
        41: ('arp interval', 53), 31: ('auto change', 13)}            # row base -> name, Launchpad colour
MOVES71 = (('mut x1', 'mutate', 1), ('mut x3', 'mutate', 3), ('undo', 'undo', None), ('keep', 'keep', None),
           ('tr 0', 'transpose', 0), ('tr +5', 'transpose', 5), ('tr +7', 'transpose', 7), ('tr -2', 'transpose', -2))
FILLS61 = (('acid roll', 'fill', 0), ('acid oct', 'fill', 1), ('acid acc', 'fill', 2),
           ('arp x2', 'roll', 2), ('arp x3', 'roll', 3), ('arp x4', 'roll', 4), ('arp oct+', 'octjump', None))
ARP51 = tuple((l, 'dir', i) for i, l in enumerate(('up', 'down', 'up-dn', 'rnd'))) + tuple((f'oct {n}', 'oct', n) for n in range(1, 5))
INT41 = (('3rd', 'int', 2), ('4th', 'int', 3), ('5th', 'int', 4), ('6th', 'int', 5), ('octave', 'int', 7))
AUTO31 = (('auto acid', 'auto', 'acid'), ('auto arp', 'auto', 'arp'), ('8 bars', 'phrase', 8), ('16 bars', 'phrase', 16))
def pads(song):                                                      # note -> (label, kind, arg); row 8 follows the song last shown
    import maps                              # here, not at the top: maps does 'from synths import ARP, TRI', so a top-level import is a cycle
    P = {81 + i: (maps.acid_name(v), 'pattern', v) for i, v in enumerate(S.ACID_SONG[song][:8])}
    for base, row in ((71, MOVES71), (61, FILLS61), (51, ARP51), (41, INT41), (31, AUTO31)):
        P.update({base + i: x for i, x in enumerate(row)})
    return P
def lit(state):                                                      # notes to light: what is live now
    a, r, d = getp(S.ACID), getp(ARP), arp_dir()
    now = {'pattern': round(a[24]), 'transpose': round(a[A_TRANSPOSE]), 'dir': d, 'oct': round(r[R_OCT]), 'int': round(r[R_INT]),
           'phrase': state['phrase']}
    return {n for n, (_, k, arg) in pads(state['song']).items() if (k in now and now[k] == arg) or (k == 'auto' and arg in state['auto'])}

ACID_RULE = ((0.7, 'mutate'), (0.9, 'next'), (1.0, 'undo'))          # per phrase: cumulative odds, retune by ear
ARP_DIRS, ARP_INTS = (0, 1, 2), (2, 3, 4, 5, 7)                      # no random direction; intervals inside the scale
def auto_step(song, which, rng=random):                              # each part on its own: a failed acid move still lets the arp move
    did = []
    if 'acid' in which:
        try:
            r = rng.random(); kind = next(k for p, k in ACID_RULE if r < p)
            if kind == 'mutate': mutate(1)
            elif kind == 'undo': tap(S.ACID, A_UNDO)
            else:
                pats, cur = S.ACID_SONG[song], int(round(getp(S.ACID)[24]))
                pattern(pats[(pats.index(cur) + 1) % len(pats)] if cur in pats else pats[0])
            did.append('acid ' + kind)
        except Exception as e: did.append(f'acid error: {e}')
    if 'arp' in which:
        try:
            if rng.random() < 0.5:
                d = arp_dir(); direction(ARP_DIRS[(ARP_DIRS.index(d) + 1) % len(ARP_DIRS)] if d in ARP_DIRS else 0); did.append('arp direction')
            else:
                i = int(round(getp(ARP)[R_INT])); setp(ARP, {R_INT: float(ARP_INTS[(ARP_INTS.index(i) + 1) % len(ARP_INTS)] if i in ARP_INTS else 2)})
                did.append('arp interval')
        except Exception as e: did.append(f'arp error: {e}')
    return did

CLOSED, SHORT = 0.05, 0.05                                           # Acid cutoff closed; arp gate short
def ramp(set_fn, a, b, secs, alive):                                 # a -> b over secs of wall time; False if another press took over
    t0 = time.time()
    while True:
        if not alive(): return False
        x = min(1.0, (time.time() - t0) / secs) if secs > 0 else 1.0
        set_fn(a + (b - a) * x)
        if x >= 1.0: return True
        time.sleep(fx.STEP)
def arp_gate(v=None):
    if v is None: return getp(ARP)[R_GATE]
    setp(ARP, {R_GATE: round(v, 3)})
# ENTRY moves block ~2 bars (ramp sleeps); pads.py runs them in threads (Task 19).
# _open keeps the knob's open value while a ramp owns it: an in/out cut off mid-ramp leaves it here, so the next in/out
# reopens to the true value, not the half-closed one it reads. Popped only when a move completes.
_open = {}
def _hold(key, now): return _open.setdefault(key, now if now > 0.07 else 0.5)   # cold start already at CLOSED / SHORT: open to 0.5
def acid_in(level, alive):                                           # strip up, cutoff opens from closed to where it was over 2 bars
    c, done = _hold('cut', fx.acid_cutoff()), False
    try:
        fx.acid_cutoff(CLOSED); fx.set_strip_map({1: level})
        done = ramp(fx.acid_cutoff, CLOSED, c, fx.bars_secs(2), alive)
    finally:
        fx.acid_cutoff(c)
        if done: _open.pop('cut', None)
def acid_out(alive):                                                 # cutoff closes over 2 bars, strip down, cutoff back for next time
    cur = fx.acid_cutoff(); c, done = _hold('cut', cur), False
    try: done = ramp(fx.acid_cutoff, cur, CLOSED, fx.bars_secs(2), alive)
    finally:
        if done: fx.set_strip_map({1: 0.0})                          # cut off = a newer in owns the strip: leave it up
        fx.acid_cutoff(c)
        if done: _open.pop('cut', None)
def arp_in(level, alive):                                            # strip up, notes grow from short to their length, roll x4 on the last beat
    g, done = _hold('gate', arp_gate()), False
    try:
        arp_gate(SHORT); fx.set_strip_map({6: level})
        done = ramp(arp_gate, SHORT, g, fx.bars_secs(2) - fx.bars_secs(0.25), alive)
        if done:
            roll(4)
            try: time.sleep(fx.bars_secs(0.25))
            finally: roll(None)
    finally:
        arp_gate(g)
        if done: _open.pop('gate', None)
def arp_out(alive):
    cur = arp_gate(); g, done = _hold('gate', cur), False
    try: done = ramp(arp_gate, cur, SHORT, fx.bars_secs(2), alive)
    finally:
        if done: fx.set_strip_map({6: 0.0})
        arp_gate(g)
        if done: _open.pop('gate', None)
ENTRY = {'acid in/out': (acid_in, acid_out), 'arp in/out': (arp_in, arp_out)}   # bank 2 moves: (in, out)
