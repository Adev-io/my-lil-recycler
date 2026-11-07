# Self-check for the virtual controller helpers in maps.py (no Rack needed): py -3.11 board_check.py
import os; os.environ['LIVE_SONGS'] = ''                                    # the core set (3 songs); songs 4+ = songs_check.py
import maps, sections as S
for pg in S.PAGES:
    for b, r in sorted(pg['rows'].items(), reverse=True):
        l = maps.pad_labels(r['samples']); assert len(l) == len(r['samples']) and all(l), (r['name'], l); print(f'{pg["name"][:7]} {r["name"]:12s}', l)
        assert all(b + i <= b + 7 for i in range(len(l))), (r['name'], 'more than 8 pads')
SY = len(S.PAGES) - 1                                                            # the Synths page: last (page 4 + one per song 4+)
assert [p['name'] for p in S.PAGES] == ['Lowdown', 'Time Out Of Mind', 'Disco Ulysses', *(x['name'] for x in S.SONGS['songs'] if os.path.isdir(x['crate'])), 'Synths'], [p['name'] for p in S.PAGES]   # Disco = page 3
assert S.PAGES[SY]['synth'] and not S.PAGES[SY]['rows'] and [k for k, p in enumerate(S.PAGES) if p.get('synth')] == [SY], S.PAGES[SY]   # Synths last, no sample rows
assert [p['deck'] for p in S.PAGES[3:SY]] == S.SONG_DECKS and all(S.ACID_SONG[k] == S.ACID_SONG[1] for k in range(3, SY))   # songs 4+: TOOM acid set (scales: songs_check)
assert [p.get('deck') for p in S.PAGES[:3]] == [S.A, S.B, S.D] and S.D not in (S.A, S.B, S.ACID, S.MIX, S.DRUMS), S.D   # each song page names its own deck
assert maps.pad_labels(S.ROWS_TOOM[71]['samples'])[:2] == ['05 verse', '02 verse']
assert maps.pad_labels(S.ROWS[81]['samples'])[:2] == ['14 chop', '14'], maps.pad_labels(S.ROWS[81]['samples'])   # Ari's two pads stay first
import os
assert all(os.path.exists(p) for pg in S.PAGES for r in pg['rows'].values() for p in r['samples']), 'a pad points at a missing file'
assert maps.pad_labels(S.ROWS[31]['samples'])[:3] == ['strings 08', 'strings 13', 'full 08']
E = maps.MODES['env']                                                       # Acid Env (Launchpad User button): filter + amp ADSR
assert set(E['cc']) == set(maps.KNOBS + maps.FADERS) and E['title'] == 'Acid Env', sorted(E['cc'])
assert all(mod == S.ACID and pid in {1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13, 14} for mod, pid, *_ in E['cc'].values()), E['cc']
assert [E['cc'][c][1] for c in maps.FADERS] == [8, 4, 9, 10] and [E['cc'][c][1] for c in maps.KNOBS] == [11, 12, 13, 14, 3, 5, 1, 2]
assert E['pads'] == maps.MODES['acid']['pads'] and E['keys'] == maps.MODES['acid']['keys'] and E['pad_label'] is maps.acid_name
for mode, M in maps.MODES.items():
    assert set(M['cc']) <= set(maps.KNOBS + maps.FADERS), mode
    for cc, (mod, pid, f, label) in M['cc'].items():
        for v in range(128): assert f(maps.to_cc(f, f(v))) == f(v), (mode, label, v)
assert maps.to_cc(maps.lin, 0.5) in (63, 64) and maps.to_cc(maps.fader, 2.0) == 127 and maps.to_cc(maps.knob, 0.0) == 64
assert [maps.acid_name(v) for v in (8, 10, 11, 16, 23)] == ['I-B1', 'Lowdown vamp', 'I-B4', 'walk-down', 'I-C8']
m0, m1 = maps.mix_map(0), maps.mix_map(1)                                   # drums + mix follows the song on show
assert m0[83][:2] == (S.A, 15) and m0[83][3] == 'keys vol' and m1[83][:2] == (S.B, 15) and m1[83][3] == 'piano vol', (m0[83], m1[83])
assert m0[16] == m1[16] and m0[18] == m1[18] and m0[16][0] == S.DRUMS                     # drums the same on both songs
import synths                                                               # arp scale per song page (2026-11-06 arp + acid)
assert set(S.SCALES) == {0, 1, 2} and all(len(set(p)) == 7 and all(0 <= c < 12 for c in p) for p in S.SCALES.values()), S.SCALES
DISCO_MASK = synths.mask_of(S.SCALES[2])
assert synths.mask_of((1, 2, 4, 6, 7, 9, 11)) == 2774 and synths.mask_of(S.SCALES[2]) == 2774, synths.mask_of(S.SCALES[2])   # Disco: D major (deck D ROOT = D)
import json
calls, real_call = [], synths.S.call                                        # set_scale writes the arp's module data only, never params, and only when needed
def fake_arp(locked, mask):
    st = {'id': 1, 'params': [{'id': i, 'value': 0.0} for i in range(19)], 'data': {'dir': 2, 'gateOuts': True, 'passThrough': False, 'type': 3, 'locked': locked, 'lockedMask': mask}}
    return lambda name, args=None: (calls.append((name, args)), json.dumps(st))[1]
try:
    synths.S.call = fake_arp(False, 0); assert synths.set_scale(0) == 2774
    sets = [a for n, a in calls if n == 'vcvrack_set_module_state']; assert len(sets) == 1, calls
    s = sets[0]['state']; assert 'params' not in s and sets[0]['id'] == synths.ARP, s
    assert s['data'] == {'dir': 2, 'gateOuts': True, 'passThrough': False, 'type': 3, 'locked': True, 'lockedMask': 2774}, s['data']
    calls.clear(); synths.S.call = fake_arp(True, 2774); assert synths.set_scale(0) == 2774 and synths.follow(lambda: 1) == 2774
    assert not [1 for n, a in calls if n == 'vcvrack_set_module_state'], calls
    calls.clear(); assert synths.follow(lambda: 2) == DISCO_MASK and synths.set_scale(3) is None   # Disco page: its scale written; Synths page 4: nothing
    sets = [a for n, a in calls if n == 'vcvrack_set_module_state']; assert [x['state']['data']['lockedMask'] for x in sets] == ([DISCO_MASK] if DISCO_MASK != 2774 else []), calls   # same key: no write
finally: synths.S.call = real_call
assert maps.ACID[77][:2] == (synths.ARP, 19) and maps.ACID[18][:2] == (synths.TRI, 28) and maps.ACID[16][:2] == (S.ACID, 28), 'Synths map'
assert maps.ACID[16][2](0) == -12.0 and maps.ACID[16][2](127) == 12.0 and maps.MODES['acid']['title'] == 'Synths'
assert S.ACID_SONG[2] == S.ACID_SONG[1], S.ACID_SONG[2]                     # Disco in D: TOOM's acid set
for song in (0, 1, 2):                                                       # Synths page pads (phase 3)
    P = synths.pads(song)
    assert all(n // 10 * 10 + 1 in synths.ROWS and 1 <= n % 10 <= 8 for n in P), sorted(P)
    assert all(l.isascii() and len(l) <= 12 for l, *_ in P.values()), [l for l, *_ in P.values()]
    assert all(0 <= v <= 31 for v in S.ACID_SONG[song]) and S.ACID_SONG[song][0] == (10, 14, 14)[song]
    assert {k for _, k, _ in P.values()} == {'pattern', 'mutate', 'undo', 'keep', 'transpose', 'fill', 'roll', 'octjump', 'dir', 'oct', 'int', 'auto', 'phrase'}
assert [k for _, k in synths.ACID_RULE] == ['mutate', 'next', 'undo'] and synths.ACID_RULE[-1][0] == 1.0
assert set(synths.ENTRY) == {'acid in/out', 'arp in/out'}
import fx                                                                   # Synths actions offline: stub the rig, put it back after
real = dict(setp=synths.setp, getp=synths.getp, arp_dir=synths.arp_dir, arp_data=synths.arp_data)
real_fx = dict(acid_cutoff=fx.acid_cutoff, set_strip_map=fx.set_strip_map, bars_secs=fx.bars_secs, STEP=fx.STEP)
sent, rig = [], {S.ACID: {24: 10.0}, synths.ARP: {16: 1.0, 18: 2.0, 19: 0.6, 20: 2.0}}
class Rng:
    def __init__(s, *v): s.v = list(v)
    def random(s): return s.v.pop(0)
def cutoff(v=None):
    if v is None: return rig['cut']
    rig['cut'] = v; sent.append(('cut', v))
def fails(): raise RuntimeError('no rig')
try:
    def put(mid, vals): rig[mid].update(vals); sent.append((mid, dict(vals)))                               # the stub writes the rig, so a read after a write sees it
    synths.setp = put
    synths.getp = lambda mid: rig[mid]
    synths.arp_dir = lambda: 0; synths.arp_data = lambda **kv: sent.append(('data', kv))
    fx.acid_cutoff, fx.set_strip_map = cutoff, lambda m: sent.append(('strip', dict(m)))
    fx.bars_secs, fx.STEP = (lambda n: n * 0.02), 0.002
    A = S.ACID
    for r, did, want in ((0.69, 'acid mutate', [(A, {30: 1.0}), (A, {29: 1.0}), (A, {29: 0.0})]),
                         (0.89, 'acid next', [(A, {24: 8.0})]), (0.95, 'acid undo', [(A, {31: 1.0}), (A, {31: 0.0})])):
        sent.clear(); assert synths.auto_step(0, {'acid'}, Rng(r)) == [did] and sent == want, (r, sent)
    rig[A][24] = 3.0; sent.clear(); synths.auto_step(0, {'acid'}, Rng(0.89)); assert sent == [(A, {24: 10.0})], sent   # not in the song: its first
    synths.getp = lambda mid: fails() if mid == A else rig[mid]; sent.clear()                                         # acid fails, arp still moves
    did = synths.auto_step(0, {'acid', 'arp'}, Rng(0.89, 0.3)); assert did == ['acid error: no rig', 'arp direction'] and sent == [('data', {'dir': 1})], (did, sent)
    synths.getp = lambda mid: rig[mid]
    sent.clear(); synths.fill(None); synths.roll(None); assert sent == [(A, {34: 0.0}), (synths.ARP, {21: 0.0})], sent   # release = hold buttons only
    rig[synths.ARP][16] = 4.0; sent.clear(); assert synths.hold('octjump', None, True) == 4.0 and sent == [], sent
    n = [0]; alive2 = lambda: (n.__setitem__(0, n[0] + 1), n[0] <= 2)[1]                                            # alive for 2 steps
    steps = []; assert synths.ramp(steps.append, 0.0, 1.0, 10.0, alive2) is False and len(steps) == 2, steps
    rig['cut'] = 0.4; n[0] = 0; sent.clear(); synths.acid_out(alive2)                                               # cancelled out: its 2 ramp steps, then
    assert len(sent) == 2 and all(k == 'cut' for k, _ in sent) and synths._open == {'cut': 0.4}, sent              # no strip, no cutoff write; _open kept
    synths._open.clear(); rig['cut'] = 0.05; sent.clear(); synths.acid_in(0.7, lambda: True)                       # cold start: open to the floor
    cuts = [v for k, v in sent if k == 'cut']; assert ('strip', {1: 0.7}) in sent and cuts[0] == 0.05 and cuts[-1] == 0.5 and cuts == sorted(cuts), sent
    assert synths._open == {}, synths._open
    w = [0]                                                                 # exception mid-ramp (step 2 write fails): cutoff still back open
    def flaky(v=None):
        if v is not None:
            w[0] += 1
            if w[0] == 3: raise RuntimeError('step 2')                       # writes: 1 = CLOSED, 2 = ramp step 1, 3 = ramp step 2
        return cutoff(v)
    rig['cut'] = 0.4; sent.clear(); fx.acid_cutoff = flaky
    try: synths.acid_in(0.7, lambda: True); raise AssertionError('acid_in swallowed the error')
    except RuntimeError: pass
    fx.acid_cutoff = cutoff; assert sent[-1] == ('cut', 0.4) and synths._open == {}, sent
    sent.clear(); synths.arp_in(0.5, lambda: True); g = [v[19] for k, v in sent if k == synths.ARP and 19 in v]        # arp in: short -> 0.6, roll x4 released
    assert g[0] == 0.05 and g[-1] == 0.6 and (synths.ARP, {20: 4.0, 21: 1.0}) in sent and (synths.ARP, {21: 0.0}) in sent and synths._open == {}, sent
    assert sent.index((synths.ARP, {20: 2.0})) > sent.index((synths.ARP, {20: 4.0, 21: 1.0})), sent        # ROLLS (param 20) put back at 2 after the x4
    rig['cut'] = 0.4; synths._open.clear(); sent.clear()                     # out reaches its end, but a newer press came in on the last step:
    synths.acid_out(lambda: rig['cut'] > 0.05 + 1e-9)                          # no strip down, no cutoff restore, _open kept for the newer one
    assert not any(k == 'strip' for k, _ in sent) and sent[-1][0] == 'cut' and abs(sent[-1][1] - 0.05) < 1e-9 and synths._open == {'cut': 0.4}, sent
    live = [True]                                                            # arp_in cut off during its roll: lets go of its own roll x4,
    synths.setp = lambda mid, vals: (put(mid, vals), vals.get(21) == 1.0 and live.__setitem__(0, False))   # then no gate write
    synths._open.clear(); sent.clear(); synths.arp_in(0.5, lambda: live[0]); i = sent.index((synths.ARP, {20: 4.0, 21: 1.0}))
    assert sent[i + 1:] == [(synths.ARP, {21: 0.0}), (synths.ARP, {20: 2.0})] and synths._open == {'gate': 0.6}, sent
    synths.setp = put
    rig[synths.ARP][21] = 1.0; synths._open.clear(); sent.clear(); synths.arp_in(0.5, lambda: True)   # arp roll fill held: no x4, no release
    assert not any(k == synths.ARP and 21 in v for k, v in sent) and synths._open == {}, sent
    del rig[synths.ARP][21]
finally:
    for k, v in real.items(): setattr(synths, k, v)
    for k, v in real_fx.items(): setattr(fx, k, v)
    synths._open.clear()
real_dnb = dict(bpm=fx.bpm, strips=fx.strips, set_strips=fx.set_strips, STEP=fx.STEP, cdp=S.current_drum_pattern, dp=S.drum_pattern)
try:                                                                            # dnb release + clean return to the tempo the set was at (not 120)
    now = {'bpm': 128.0, 'strips': [0.5] * 8, 'pat': 3}
    fx.bpm = lambda v=None: now['bpm'] if v is None else now.__setitem__('bpm', v)
    fx.strips = lambda: list(now['strips']); fx.set_strips = lambda v: now.__setitem__('strips', list(v))
    S.current_drum_pattern = lambda: now['pat']; S.drum_pattern = lambda p: now.__setitem__('pat', p); fx.STEP = 0.002
    snap = fx.snapshot(); assert snap['bpm'] == 128.0, snap
    now['bpm'], now['pat'] = 140.0, fx.BREAK; saved = dict(fx.DNB); fx.DNB['release'] = 0.02
    try: assert fx.dnb_off(snap, lambda: True) is True
    finally: fx.DNB.update(saved)
    assert now['bpm'] == 128.0 and now['pat'] == 3, now                         # release ends at 128
    now['bpm'], now['pat'] = 140.0, fx.BREAK; fx.restore(snap); assert now['bpm'] == 128.0 and now['pat'] == 3, now   # clean while dnb is on
    old = {k: v for k, v in snap.items() if k != 'bpm'}; now['bpm'] = 140.0; fx.restore(old); assert now['bpm'] == 120.0, now     # old snapshot: 120
    now['bpm'] = 140.0; fx.DNB['release'] = 0.02
    try: fx.dnb_off(old, lambda: True)
    finally: fx.DNB.update(saved)
    assert now['bpm'] == 120.0, now
    state = {'snap': snap}; now['bpm'], now['pat'] = 140.0, fx.BREAK; n = [0]; cut = lambda: (n.__setitem__(0, n[0] + 1), n[0] <= 4)[1]   # release cut off mid-ramp,
    fx.DNB['release'] = 0.05
    try: fx.dnb_release(state, cut); assert 128.0 < now['bpm'] < 140.0 and now['pat'] == fx.BREAK and state['snap'] is snap, (now, state)
    finally: fx.DNB.update(saved)
    assert fx.dnb_arm(state) is snap and snap['bpm'] == 128.0 and snap['drums'] == 3, (snap, state)                    # dnb again: still the first snapshot, not the half-way rig
    fx.DNB['release'] = 0.02
    try: fx.dnb_release(state, lambda: True)                                                                          # a finished release drops it
    finally: fx.DNB.update(saved)
    assert state['snap'] is None and now['bpm'] == 128.0 and now['pat'] == 3, (now, state)
    now['strips'] = [0.1] * 8; now['bpm'] = 131.0; assert fx.dnb_arm(state)['bpm'] == 131.0 and state['snap']['strips'] == [0.1] * 8   # next press snapshots fresh
finally:
    fx.bpm, fx.strips, fx.set_strips, fx.STEP = (real_dnb[k] for k in ('bpm', 'strips', 'set_strips', 'STEP'))
    S.current_drum_pattern, S.drum_pattern = real_dnb['cdp'], real_dnb['dp']
assert {n: fx.FX3[n] for n in (12, 13, 14, 15)} == {12: 'vox 1/4', 13: 'vox 1/8', 14: 'vox 1/16', 15: 'vox 1/32'} and fx.FX3[11] == 'drums in/out'
assert (fx.STUT, fx.STUTLEN, fx.VOX_SLOT) == (40, 44, 3) and fx.VOX_STUT == {'vox 1/4': 0, 'vox 1/8': 1, 'vox 1/16': 2, 'vox 1/32': 3}
real_vox = dict(call=S.call, vox_stut=fx.vox_stut)
vrow = lambda k: next(b for b, r in S.PAGES[k]['rows'].items() if r['slot'] == fx.VOX_SLOT and r.get('deck', S.A) == fx.own_deck(k))   # vox_deck: the vocals you hear
vmix = [0.0] * 8; vmix[2] = vmix[7] = S.U; vp = [{vrow(0): 'x'}, {}, {}, {}]
assert fx.vox_deck(vmix, vp, 0, 2) == S.A and fx.vox_deck(vmix, vp, 2, 2) == S.A        # Disco playing, horns muted, Lowdown vocals up: Lowdown
vp[2] = {vrow(2): 'y'}; assert fx.vox_deck(vmix, vp, 2, 0) == S.D and fx.vox_deck(vmix, vp, 0, 2) == S.A   # both up: page on show wins
assert fx.vox_deck(vmix, vp, 3, 2) == S.D and fx.vox_deck(vmix, [{}, {}, {}, {}], 3, 1) == S.B           # Synths page: song playing; none heard: song playing
vmix[2] = 0.0; assert fx.vox_deck(vmix, vp, 0, 0) == S.D                                 # Lowdown strip shut: not heard
try:                                                                            # bank 3 vox stutter holds (pads.py: vox / vox_up / clean -> fx.vox_*)
    got = []; S.call = lambda name, args=None: got.append((name, args)) or '[]'
    fx.vox_stut(S.A, 2); fx.vox_stut(S.B, None)                                  # one set_params call each: length + hold, or the hold let go
    assert got == [('vcvrack_set_params', {'moduleId': S.A, 'params': [{'id': 44, 'value': 2.0}, {'id': 43, 'value': 1.0}]}),
                   ('vcvrack_set_params', {'moduleId': S.B, 'params': [{'id': 43, 'value': 0.0}]})], got
    S.call = real_vox['call']
    vs = []; fx.vox_stut = lambda d, div: vs.append((d, div))
    st = {'vox': {}, 'down': set()}; A, B = fx.own_deck(0), fx.own_deck(1)
    def hw_on(note, page): st['down'].add(note); return fx.vox_on(st, note, fx.FX3[note], fx.own_deck(page), True)   # pads.on_msg + act
    def hw_off(note): st['down'].discard(note); v = st['vox'].get(note); return v and v[2] and fx.vox_off(st, note)
    hw_on(12, 0); assert vs == [(A, 0)] and fx.vox_lit(st) == {'vox 1/4'}, vs                       # hold 1/4 on Lowdown vocals
    vs.clear(); hw_on(13, 0); assert vs == [(A, 1)] and fx.vox_lit(st) == {'vox 1/4', 'vox 1/8'}, vs   # slide: length only, no let go
    vs.clear(); hw_off(12); assert vs == [] and fx.vox_lit(st) == {'vox 1/8'}, vs                    # 13 still down: keeps going at 1/8
    vs.clear(); hw_off(13); assert vs == [(A, None)] and st['vox'] == {} and not fx.vox_lit(st), vs  # last one up: let go
    vs.clear(); hw_on(12, 0); hw_on(14, 0); hw_off(14); assert vs == [(A, 0), (A, 2), (A, 0)] and list(st['vox']) == [12], vs   # latest up: back to 1/4
    hw_off(12); vs.clear()
    hw_on(12, 0); vs.clear(); page_now = 1                                          # page turn to TOOM mid-hold (vox_off takes no page:
    assert hw_off(12) and vs == [(A, None)], vs                                     # the release goes to the deck the hold started on)
    vs.clear(); hw_on(12, page_now); assert vs == [(B, 0)] and st['vox'][12][0] == B, vs   # page 2 on show: TOOM vocals (deck B)
    hw_off(12); assert vs == [(B, 0), (B, None)], vs
    vs.clear(); st['down'].discard(15); fx.vox_on(st, 15, 'vox 1/32', A, True); assert vs == [(A, 3), (A, None)] and st['vox'] == {}, vs   # quick stab: up before the hold landed
    vs.clear(); fx.vox_on(st, 13, 'vox 1/8', A, False); assert vs == [(A, 1)] and st['vox'][13][2] is False   # page click: on, no note off to come
    assert not hw_off(13) and vs == [(A, 1)], vs                                    # a note off on a page-held pad lets nothing go
    fx.vox_on(st, 13, 'vox 1/8', A, False); assert vs == [(A, 1), (A, None)] and st['vox'] == {}, vs   # click again: off
    vs.clear(); hw_on(12, 0); hw_on(14, 1); fx.vox_clean(st); assert vs[2:] and sorted(vs[2:], key=str) == sorted([(A, None), (B, None)], key=str) and st['vox'] == {}, vs   # clean: both decks
    assert not hw_off(12) and not hw_off(14) and len(vs) == 4, vs                   # pads come up after clean: nothing more sent
    vs.clear(); hw_on(12, 0); hw_on(13, 0); hw_on(12, 0)                          # Launchpad re-press of a held pad (missed note off): never off,
    assert vs == [(A, 0), (A, 1), (A, 1)] and list(st['vox']) == [12, 13], vs      # the hold re-asserted at the length playing (1/8)
    fx.vox_on(st, 13, 'vox 1/8', A, False); assert vs[-1] == (A, 0) and list(st['vox']) == [12], vs   # a page click still toggles (back to 1/4)
    hw_off(12); assert vs[-1] == (A, None) and st['vox'] == {}, vs
    vs.clear(); fx.vox_on(st, 14, 'vox 1/16', A, False); hw_on(14, 0)              # page-held pad pressed on the Launchpad: re-asserted, not off
    assert vs == [(A, 2), (A, 2)] and st['vox'] == {14: (A, 'vox 1/16', False)}, vs
    fx.vox_on(st, 14, 'vox 1/16', A, False); st['down'].discard(14); assert vs[-1] == (A, None) and st['vox'] == {}, vs
    def boom(d, div):
        if div is None: raise RuntimeError('no rig')
        vs.append((d, div))
    vs.clear(); fx.vox_stut = boom; hw_on(12, 0)
    try: hw_off(12); raise AssertionError('vox_off swallowed the error')
    except RuntimeError: pass
    assert 12 in st['vox'] and fx.vox_lit(st) == {'vox 1/4'}, st                     # off failed: still held + lit, the next press / clean retries
    fx.vox_stut = lambda d, div: vs.append((d, div)); fx.vox_clean(st); assert st['vox'] == {} and vs[-1] == (A, None), vs
    def fail_on(d, div):                                                         # record before write: the hold write fails ->
        if div is not None: raise RuntimeError('no rig')
        vs.append((d, div))
    vs.clear(); fx.vox_stut = fail_on; st['down'].add(13)
    try: fx.vox_on(st, 13, 'vox 1/8', A, True); raise AssertionError('vox_on swallowed the error')
    except RuntimeError: pass
    assert st['vox'] == {13: (A, 'vox 1/8', True)} and fx.vox_lit(st) == {'vox 1/8'}, st   # still recorded held + lit (safe to let go)
    assert hw_off(13) and vs == [(A, None)] and st['vox'] == {}, vs                  # and its note off lets go
    n_off = [0]
    def flaky_off(d, div):
        if div is None:
            n_off[0] += 1
            if n_off[0] == 1: raise RuntimeError('blip')
        vs.append((d, div))
    vs.clear(); fx.vox_stut = flaky_off; st['down'].discard(14); fx.vox_on(st, 14, 'vox 1/16', A, True)   # quick stab, first let go fails:
    assert vs == [(A, 2), (A, None)] and st['vox'] == {} and n_off[0] == 2, vs      # one retry lets go
    fx.vox_stut = lambda d, div: vs.append((d, div)) if d != B else (_ for _ in ()).throw(RuntimeError('deck B'))
    vs.clear(); st['vox'].update({12: (A, 'vox 1/4', True), 14: (B, 'vox 1/16', True)})   # clean: deck B write fails, deck A still goes,
    try: fx.vox_clean(st); raise AssertionError('vox_clean swallowed the error')       # the first error raised at the end
    except RuntimeError: pass
    assert vs == [(A, None)] and st['vox'] == {14: (B, 'vox 1/16', True)}, (vs, st)
    st['vox'].clear()
    assert fx.no_stut([{'id': i, 'value': 1.0} for i in (14, 39, 40, 43, 44, 45)]) == [{'id': 14, 'value': 1.0}, {'id': 39, 'value': 1.0}, {'id': 45, 'value': 1.0}]
finally: S.call, fx.vox_stut = real_vox['call'], real_vox['vox_stut']
try:                                                                             # sections.play writes slot paths as data only: no 'params'
    got = []; rig_st = {'id': S.A, 'params': [{'id': 43, 'value': 0.0}], 'data': {'slots': [{'path': 'x'}] * 4}}
    S.call = lambda name, args=None: (got.append((name, args)), json.dumps(rig_st))[1]
    S.play(3, 'new.wav', 1.0, S.A); sets = [a for n, a in got if n == 'vcvrack_set_module_state']
    assert len(sets) == 1 and 'params' not in sets[0]['state'] and sets[0]['state']['data']['slots'][3]['path'] == 'new.wav', sets
finally: S.call = real_vox['call']
import ast, types, threading                                                     # pads.py press / on_msg as written (pads.py itself opens the
src = open(os.path.join(S.here, 'pads.py'), encoding='utf-8').read()             # Launchpad on import): those functions alone, rig + threads stubbed
fns = [n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name in ('press', 'side', 'vox', 'vox_up', 'on_msg')]
assert len(fns) == 5, [n.name for n in fns]
class SyncThread:                                                                # a thread that runs on start(): the order is the test's
    def __init__(s, target, args=(), daemon=None): s.t, s.a = target, args
    def start(s): s.t(*s.a)
done = []; bank_ = [fx.FX3]
P = dict(state={'busy': True, 'vox': {}, 'down': set(), 'held': set(), 'page': 0, 'path': [{} for _ in S.PAGES]}, fx=fx, MOVES=lambda: bank_[0], SYN=lambda: False, SP=lambda: 0, PLAY=lambda: 0, pad=lambda n: None,
         led=lambda *a, **k: None, paint=lambda: None, LOG=types.SimpleNamespace(write=lambda s: None), HOLDL=threading.RLock(), CLEANL=threading.Lock(),
         threading=types.SimpleNamespace(Thread=SyncThread), traceback=__import__('traceback'), time=__import__('time'),
         fx_act=lambda name: done.append(('fx_act', name)), act=lambda note, hw=False: done.append(('act', note)), let_go=lambda n: None)
exec(compile(ast.Module(body=fns, type_ignores=[]), 'pads.py', 'exec'), P)
msg = lambda t, n, v=100: types.SimpleNamespace(type=t, note=n, velocity=v)
try:
    vs = []; fx.vox_stut = lambda d, div: vs.append((d, div)); A = fx.own_deck(0); real_strips_v = fx.strips; fx.strips = lambda: [0.0] * 8
    P['on_msg'](msg('note_on', 12)); P['on_msg'](msg('note_on', 13))             # busy the whole time (another press in flight)
    assert vs == [(A, 0), (A, 1)] and set(P['state']['vox']) == {12, 13}, vs        # second vox press while busy: NOT dropped
    P['on_msg'](msg('note_off', 12)); P['on_msg'](msg('note_on', 13, 0))            # (a note_on at velocity 0 = note off)
    assert vs == [(A, 0), (A, 1), (A, None)] and P['state']['vox'] == {} and not P['state']['down'], vs
    assert P['press'](12) is True and P['press'](12) is True and vs[-2:] == [(A, 0), (A, None)], vs   # page clicks toggle past busy too
    assert P['press'](11) is False and not done, done                             # other moves still wait on busy (drums in/out dropped)
    bank_[0] = fx.FX; assert P['press'](18) is True and done == [('fx_act', 'clean')], done   # clean (bank 1 pad 18) never dropped by busy
    assert P['state']['busy'] is True                                             # and leaves busy to the press that set it
finally: fx.vox_stut, fx.strips = real_vox['vox_stut'], real_strips_v
R81 = S.ROWS[81]                                                                 # row page 2 (row-end round button, CC base + 8)
assert maps.pad_labels(R81['samples2']) == ['15', '16', '12', '04', '04 choir', '14 choir', '15 choir'], maps.pad_labels(R81['samples2'])
for pg in S.PAGES:
    for b, r in pg['rows'].items():
        if 'samples2' not in r: continue
        l2 = maps.pad_labels(r['samples2']); assert 0 < len(l2) <= 8 and all(l2) and len(set(l2)) == len(l2), (r['name'], l2)
        assert all(os.path.exists(p) for p in r['samples2']), (r['name'], 'a page 2 pad points at a missing file')
        assert not set(r['samples2']) & set(r['samples']), (r['name'], 'a sample on both row pages')
        assert b != 11, (r['name'], 'row-end CC 19 = moves bank')
src_p = open(os.path.join(S.here, 'pads.py'), encoding='utf-8').read()
keep = [n for n in ast.parse(src_p).body if (isinstance(n, ast.FunctionDef) and n.name in ('rowflip', 'pad', 'act'))
        or (isinstance(n, ast.Assign) and any(getattr(t, 'id', None) in ('ROW_CC', 'L', 'RP') for t in n.targets))]
assert len(keep) == 6, [getattr(n, 'name', None) for n in keep]
played, logs, real_play = [], [], S.play
st2 = {'page': 0, 'song': 0, 'busy': False, 'acts': 0, 'rowpage': {},'on': [{} for _ in S.PAGES], 'path': [{} for _ in S.PAGES]}
Q2 = dict(state=st2, sections=S, fx=fx, os=os, time=__import__('time'), traceback=__import__('traceback'), importlib=types.SimpleNamespace(reload=lambda m: m),
          MOVES=lambda: {}, SYN=lambda: bool(S.PAGES[st2['page']].get('synth')), R=lambda: S.PAGES[st2['page']]['rows'], ON=lambda: st2['on'][st2['page']],
          paint=lambda: None, LOG=types.SimpleNamespace(write=logs.append))
exec(compile(ast.Module(body=keep, type_ignores=[]), 'pads.py', 'exec'), Q2)
real_chops = S.CHOPS; S.CHOPS = os.path.join(S.here, 'no-such-chops.json')   # main + samples2 only here; the chop pages are checked below on a fake chops.json
try:
    S.play = lambda slot, path, level, deck=None: played.append((slot, path, level, deck))
    rf, pad, act, on = Q2['rowflip'], Q2['pad'], Q2['act'], st2['on'][0]
    s1, s2 = R81['samples'], R81['samples2']
    assert Q2['ROW_CC'] == {29: 21, 39: 31, 49: 41, 59: 51, 69: 61, 79: 71, 89: 81}, Q2['ROW_CC']       # 19 (moves bank) left alone; 29 = drums row pages
    assert pad(88) == (81, 7) and rf(81) and st2['rowpage'] == {(0, 81): 1} and pad(88) is None and pad(87) == (81, 6)   # page 2: 7 pads
    act(85); assert played[-1] == (3, s2[4], R81['level'], None) and on[81] == 4 and st2['path'][0][81] == s2[4], (played, on)   # page 2 pad 5 plays samples2[4]
    rf(81); assert on[81] is None and st2['path'][0][81] == s2[4]          # page 1 on show: the playing page-2 sample lights nothing
    rf(81); assert on[81] == 4                                             # back on page 2: lit again
    act(85); assert played[-1][1] is None and on[81] is None and st2['path'][0][81] is None   # lit pad again = muted
    rf(81); assert on[81] is None; rf(81); assert on[81] is None
    rf(81); act(81); assert played[-1][1] == s1[0] and on[81] == 0            # page 1 pad 1, then page 2 shows nothing lit, page 1 lit again
    rf(81); assert on[81] is None and st2['rowpage'][(0, 81)] == 1; rf(81); assert on[81] == 0
    n = len(played); assert not rf(71) and not rf(21) and len(played) == n   # rows without a page 2: nothing, never a sound
    st2['busy'] = True; assert not rf(81); st2['busy'] = False
    st2['page'] = 1; assert not rf(81); st2['page'] = 2; assert not rf(81); st2['page'] = 3; assert not rf(81); st2['page'] = 0   # TOOM vocals, Disco horns: no page 2; Synths page: no rows
    assert not [l for l in logs if 'Traceback' in l], logs
    vst = {'params': [{'id': 14 + k, 'value': 1.0 if k == 3 else 0.0} for k in range(4)], 'data': {'slots': [{'path': ''}] * 3 + [{'path': s2[2]}]}}
    S.call = lambda name, args=None: json.dumps(vst); ps = {}                 # sections.now with row pages: index in the list on show
    assert S.now({81: R81}, {81: 1}, ps) == {81: 2} and ps == {81: s2[2]} and S.now({81: R81}) == {81: None}, ps
    vst['params'][3]['value'] = 0.0; assert S.now({81: R81}, {81: 1}, ps) == {81: None} and ps == {81: None}
    import board; board.ST = dict(st2, bank=0, machine=True, fx=set(), vox={}, hw=False)   # the console: labels of the row page on show
    rows = {r['base']: r for r in board.launchpad()['rows']}
    assert rows[81]['labels'] == maps.pad_labels(s1) and (rows[81]['rpage'], rows[81]['rpages']) == (0, 2) and rows[71]['rpages'] == 1, rows[81]
    rf(81); board.ST['rowpage'] = st2['rowpage']; rows = {r['base']: r for r in board.launchpad()['rows']}
    assert rows[81]['labels'][:7] == maps.pad_labels(s2) and (rows[81]['rpage'], rows[81]['rkind']) == (1, 'extra') and rows[81]['on'] is None, rows[81]
finally: S.play, S.call = real_play, real_vox['call']
# ---- chop pages (every row's end button: main -> samples2 -> chop halves -> main) on a fake chops.json
import tempfile, shutil
assert maps.pad_labels(['x/4-piano-14-115bpm-chop4a.wav', 'x/4-piano-14-115bpm-chop4b.wav']) == ['14 a', '14 b']
assert maps.pad_labels(['x/6-vocals-05_verse-124bpm-chop4b.wav', 'x/6-vocals-04_choir-115bpm-chop4a.wav', 'x/6-vocals-14-115bpm-chop4a.wav']) == ['05 verse b', '04 choir a', '14 a']
assert maps.pad_labels(['x/5-other-15-115bpm-chop4a.wav', 'x/7-mix-08-115bpm-chop4b.wav']) == ['strings 15 a', 'full 08 b']   # stem prefix kept
half = lambda p, h: p[:-4] + f'-chop4{h}.wav'
K, V2, DR = S.ROWS[71]['samples'], R81['samples2'], S.ROWS[21]['samples']
fake = {p: [half(p, 'a'), half(p, 'b')] for p in K + V2[:3] + DR[:3]}
fake[K[2]] = [half(K[2], 'a'), None]                                             # a null half is skipped
tmpd = tempfile.mkdtemp(); S.CHOPS = os.path.join(tmpd, 'chops.json'); json.dump(fake, open(S.CHOPS, 'w'))
try:
    S.play = lambda slot, path, level, deck=None: played.append((slot, path, level, deck))
    st2.update(page=0, busy=False, rowpage={}, on=[{} for _ in S.PAGES], path=[{} for _ in S.PAGES]); on = st2['on'][0]
    kh = [h for p in K for h in fake[p] if h]                                     # keys: 15 halves -> chop pages of 8 + 7
    PK = S.pages(S.ROWS[71]); assert PK == [K, kh[:8], kh[8:]] and [S.kind(S.ROWS[71], k) for k in range(3)] == ['main', 'chop', 'chop'], PK
    assert maps.pad_labels(PK[1]) == ['14 a', '14 b', '15 a', '15 b', '16 a', '13 a', '13 b', '03 a'], maps.pad_labels(PK[1])
    PV = S.pages(R81); assert PV == [s1, V2, [h for p in V2[:3] for h in fake[p]]] and S.kind(R81, 1) == 'extra' and S.kind(R81, 2) == 'chop', PV
    assert maps.pad_labels(PV[2]) == ['15 a', '15 b', '16 a', '16 b', '12 a', '12 b'], maps.pad_labels(PV[2])
    order = []
    for _ in range(4): rf(81); order.append(st2['rowpage'][(0, 81)])
    assert order == [1, 2, 0, 1], order                                            # main -> samples2 -> chops -> main -> samples2
    rf(81); rf(81); assert st2['rowpage'][(0, 81)] == 0
    rf(71); assert pad(71) == (71, 0) and pad(78) == (71, 7)                      # keys chop page 1: 8 pads
    on[61] = 2; act(71); R71 = S.ROWS[71]                                         # 'a' plays its half; bridge keys (same slot) cleared
    assert played[-1] == (R71['slot'], kh[0], R71['level'], None) and kh[0].endswith('-chop4a.wav') and on[71] == 0 and on[61] is None, (played[-1], on)
    act(72); assert played[-1][1] == kh[1] and kh[1].endswith('-chop4b.wav') and on[71] == 1 and st2['path'][0][71] == kh[1]
    rf(71); assert on[71] is None and pad(78) is None and pad(77) == (71, 6)       # chop page 2: 7 pads, the playing half lit nowhere
    rf(71); assert on[71] is None and st2['rowpage'][(0, 71)] == 0                 # wraps to main: the half is not on main
    rf(71); assert on[71] == 1; act(72); assert played[-1][1] is None and on[71] is None   # back on its page: lit; again = muted
    rf(71); rf(71)
    assert rf(21) and S.kind(S.ROWS[21], st2['rowpage'][(0, 21)]) == 'chop' and rf(21) and st2['rowpage'][(0, 21)] == 0   # CC 29: drums row cycles too
    assert not rf(61)                                                            # bridge keys: sources already 4-bar chops, one page
    vst = {'params': [{'id': 14 + k, 'value': 1.0 if k == 1 else 0.0} for k in range(4)], 'data': {'slots': [{'path': ''}, {'path': kh[9]}, {'path': ''}, {'path': ''}]}}
    S.call = lambda name, args=None: json.dumps(vst); ps = {}                    # sections.now on a chop page: index there, path on any page
    assert S.now({71: R71}, {71: 2}, ps) == {71: 1} and ps == {71: kh[9]} and S.now({71: R71}, {71: 1}, ps) == {71: None} and ps == {71: kh[9]}
    board.ST = dict(st2, bank=0, machine=True, fx=set(), vox={}, hw=False); st2['rowpage'][(0, 71)] = 1
    rows = {r['base']: r for r in board.launchpad()['rows']}
    assert (rows[71]['rpage'], rows[71]['rpages'], rows[71]['rkind']) == (1, 3, 'chop') and rows[71]['labels'][0] == '14 a' and rows[21]['rpages'] == 2, rows[71]
    st2['rowpage'][(0, 71)] = 7; assert board.launchpad()['rows'][1]['rpage'] == 0 and Q2['L'](0, 71) == K   # stale index (fewer pages now) = page 1
    rf(71); assert st2['rowpage'][(0, 71)] == 0
    os.remove(S.CHOPS); assert S.pages(R71) == [K] and not rf(71)               # chops.json gone: no chop pages
    open(S.CHOPS, 'w').write('{"half written'); assert S.pages(R71) == [K]      # half-written: none either, no error
    assert not [l for l in logs if 'Traceback' in l], logs
finally: S.play, S.call, S.CHOPS = real_play, real_vox['call'], real_chops; shutil.rmtree(tmpd, ignore_errors=True)
PM = {'state': {'machine': True}, 'ARROWS': {93: -1, 94: 1}, 'MODE_CC': {96: 'mix', 97: 'acid', 98: 'env'}, 'fx': fx, 'SYN': lambda: False, 'MOVES': lambda: {}}
hits = []; PM.update(threading=types.SimpleNamespace(Thread=SyncThread), machine=lambda: hits.append('machine'), rowflip=lambda b: hits.append(('row', b)),
                     turn=lambda d: hits.append(('turn', d)), minilab=lambda m: hits.append(('mode', m)), flip=lambda: hits.append('bank'), press=lambda *a: None)
exec(compile(ast.Module(body=[n for n in ast.parse(src_p).body if (isinstance(n, ast.FunctionDef) and n.name == 'on_msg')
                              or (isinstance(n, ast.Assign) and any(getattr(t, 'id', None) in ('MACHINE_CC', 'ROW_CC') for t in n.targets))], type_ignores=[]), 'pads.py', 'exec'), PM)
for c in (95, 29, fx.BANK_CC, 89, 96): PM['on_msg'](types.SimpleNamespace(type='control_change', control=c, value=127))
assert PM['MACHINE_CC'] == 95 and hits == ['machine', ('row', 21), 'bank', ('row', 81), ('mode', 'mix')], hits   # Session = drum machine, CC 29 = drums row pages
html = open(os.path.join(S.here, 'board.html'), encoding='utf-8').read()
assert 'c === 4' in html and 'round machine' in html and 'r.base === 21' not in html, 'console: the drum machine button sits on the top row (Session)'
if os.path.exists(real_chops):                                                   # the real chops.json (once cut): every page labelled, chop files there
    for pg in S.PAGES:
        for b, r in pg['rows'].items():
            for k, Lk in enumerate(S.pages(r)):
                lk = maps.pad_labels(Lk); assert 0 < len(lk) <= 8 and all(lk) and len(set(lk)) == len(lk), (pg['name'], r['name'], k, lk)
                if S.kind(r, k) == 'chop': assert all(os.path.exists(p) and p.endswith(('-chop4a.wav', '-chop4b.wav')) for p in Lk), (r['name'], k, 'a chop pad points at a missing file')
    print('Real chops.json: row pages', {f"{pg['name'][:7]} {r['name']}": len(S.pages(r)) for pg in S.PAGES for r in pg['rows'].values()})
else: print('Real chops.json absent: no chop pages yet (rows show main / samples2 only)')
print('Chop pages offline: pages = main, samples2, chop halves (nulls skipped, 8 a page); end button cycles main -> samples2 -> chops -> main, a/b labels,'
      ' chop pad plays its -chop4a/b file, lit follows across pages, bridge keys cleared, CC 29 cycles drums, Session CC 95 = drum machine, chops.json missing / half-written = none')
print('Row page 2 offline: Lowdown vocals page 2 =', maps.pad_labels(R81['samples2']), '| CC 89 flips (29..89, not 19), page 2 pad plays samples2[i], lit follows the sample'
      ' playing across flips, mute, busy / no page 2 / TOOM / Synths refused, sections.now by row page, console labels + page2')
print('Vox fixes offline: record before write (failed hold stays held + lit, its note off lets go), quick-stab let go retried once, clean per deck + first error raised,'
      ' no_stut drops 40-44, sections.play state has no params, pads.press/on_msg: second vox press while busy not dropped, clean past busy, other moves still wait')
print('Vox offline: FX3 12-15, one set_params call per hold / let go, slide = length only, first up keeps the second, latest up = back to the first length,'
      ' page turn releases the deck it started on, page 2 = deck B, quick stab, page click toggles, clean lets both decks go, failed off stays held')
print('DnB offline: snapshot records the set tempo, release + clean return to it (128), a snapshot without bpm falls back to 120')
print('Synths offline: auto_step mutate/next/undo + first-of-song + acid error keeps arp, hold-button release, octjump at 4, ramp cut-off, cancelled acid_out writes nothing after, acid_in floor 0.5, exception restores open, arp_in roll + ROLLS put back,'
      ' finished out after a newer press writes nothing, arp_in cut off in its roll writes no gate, held arp roll left alone')
PD = {'_dead': [], 'mido': types.SimpleNamespace(get_input_names=lambda: ['gone-not-listed-here'], get_output_names=lambda: [])}   # pads.py park_or_close as written
exec(compile(ast.Module(body=[n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == 'park_or_close'], type_ignores=[]), 'pads.py', 'exec'), PD)
class FakePort:
    def __init__(s, name, boom=False): s.name, s.boom, s.closes, s.callback, s.is_input = name, boom, 0, 'cb', True
    def close(s):
        s.closes += 1
        if s.boom: raise RuntimeError('midiInUnprepareHeader failed')
bad, vanished, fine = FakePort('Launchpad', boom=True), FakePort('LPMiniMK3 MIDI'), FakePort('ok-port')
PD['park_or_close'](bad, False); PD['park_or_close'](vanished, True); PD['park_or_close'](fine, False); PD['park_or_close'](None)
assert bad.closes == 1 and PD['_dead'] == [bad, vanished], PD['_dead']           # a close that raises = parked (closed once, never again); a vanished port is never closed
assert vanished.closes == 0 and fine.closes == 1 and fine not in PD['_dead'] and bad.callback is None and vanished.callback is None
lookup = FakePort('Launchpad lookup', boom=True); PD['park_or_close'](lookup); assert lookup.closes == 0 and lookup in PD['_dead']   # gone=None: looked up, name not listed -> parked untried
PD['mido'].get_input_names = lambda: ['listed']; listed = FakePort('listed', boom=True); PD['park_or_close'](listed); assert listed.closes == 1 and listed in PD['_dead']
PD['mido'].get_input_names = lambda: 1 / 0; blind = FakePort('listed'); PD['park_or_close'](blind)   # the lookup itself fails: parked, never closed on a guess
assert blind.closes == 0 and blind in PD['_dead'] and blind.callback is None
print('Dead port offline: a vanished port or a close that raises is parked in _dead, never closed again; a healthy port closes once')
# ---- page 3 Disco Ulysses (deck D, disco-crate): rows, pins, labels, mix map, moves, base, transition in and out (rig stubbed)
RD, U = S.ROWS_DISCO, S.U; LIBF = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\MyLilRecycler\library.json')
lib = {e['path']: e for e in json.load(open(LIBF, encoding='utf-8'))}
assert {b: (r['name'], r['slot']) for b, r in RD.items()} == {81: ('horns/synth', 3), 71: ('piano', 1), 51: ('guitar', 2), 41: ('bass', 0), 21: ('drums', 0)}, RD
assert all(r['deck'] == S.D for b, r in RD.items() if b != 21) and RD[21]['deck'] == S.ROWS[21]['deck'] == S.ROWS_TOOM[21]['deck'], 'Disco drums share deck C slot 0'
assert [r['color'] for b, r in sorted(RD.items())] == [13, 37, 21, 45, 9] and all(b in RD for b in fx.FIRST), 'colours as pages 1-2; transition rows there'
for b, r in sorted(RD.items(), reverse=True):
    l = maps.pad_labels(r['samples']); assert 0 < len(r['samples']) <= 8 and len(set(l)) == len(l) and len(set(r['samples'])) == len(r['samples']), (r['name'], l)
    for p in r['samples']:
        e = lib.get(p); assert os.path.exists(p) and '/disco-crate/' in p and '_quiet' not in p, p
        assert e and e['bars'] == 8 and e['key'] == 11 and not e['minor'] and e['size'] == os.path.getsize(p), (p, e and {k: e[k] for k in ('bars', 'key', 'minor')})
    print(f'Disco   {r["name"]:12s}', l)
assert maps.pad_labels(RD[71]['samples'])[:4] == ['15 chorus', '13 chorus', '14 chorus', '08 chorus'] and maps.pad_labels(RD[81]['samples']) == ['11 bridge', '12 bridge']
m2 = maps.mix_map(2)                                                          # MiniLab drums + mix on the Disco page: deck D slots 3, 1, 2, 0
assert [m2[c][:2] + (m2[c][3],) for c in maps.FADERS] == [(S.D, 17, 'horns/synth vol'), (S.D, 15, 'piano vol'), (S.D, 16, 'guitar vol'), (S.D, 14, 'bass vol')], m2
assert m2[16] == m0[16] and m2[18] == m0[18] and [m2[c][1] for c in maps.KNOBS[:4]] == [27, 25, 26, 24]
assert fx.own_deck(2) == S.D and fx.STRIP[S.D] == 7 and fx.BASEF[S.D] == [0.0] * 4 and fx.REST == {S.D: 0.0} and fx.own_deck(0) == S.A and fx.own_deck(1) == S.B
assert fx.song_decks(2, [{}, {}, {21: 0}, {}]) == [S.D, fx.C] and fx.song_decks(2, [{}, {}, {}, {}]) == [S.D]
HU = next(n for n in ast.parse(src_p).body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', None) == 'HUSH')
HUV = eval(compile(ast.Expression(HU.value), 'pads.py', 'eval'), {'fx': fx, 'sections': S})
assert HUV == {'drums only': (1, 2, 3, 5, 6, 7, *(fx.STRIP[d] for d in S.SONG_DECKS)), 'no drums': (0, 4)}, HUV   # drums only silences deck D + songs 4+ too
sP = synths.pads(2); assert [sP[81 + i][2] for i in range(4)] == [14, 15, 16, 19] and 85 not in sP   # Synths acid row on Disco
class Clock:                                                                  # fake time for fx (sleeps advance it); the set clock beats on it
    def __init__(s, t=1000.0, bpm=128.0): s.t, s.beat = t, 60.0 / bpm
    def time(s): return s.t
    def sleep(s, d): s.t += max(d, 1e-6)
    def gate(s): return 10.0 if s.t % s.beat < s.beat / 2 else 0.0               # Clocked master out: high for the first half of each beat
class Rig:                                                                    # decks / Mixer as params + slot paths, the clock, the arp's data; S.call answers from it
    def __init__(s):
        s.p = {m: {i: 0.0 for i in range(48)} for m in (S.A, S.B, fx.C, S.D, S.MIX)}; s.path = {m: [''] * 4 for m in s.p}; s.sets = []
        s.clk, s.arp, s.log, s.fail, s.reads = Clock(), {'locked': True, 'lockedMask': 2774}, [], None, []; s.p[fx.CLOCK] = {0: 128.0}   # log: (time, module, writes)
    def __call__(s, name, a=None):
        if name == 'vcvrack_get_voltages': return json.dumps([{'id': fx.CLOCK, 'outputs': [{'id': 0, 'voltages': [s.clk.gate()]}]}])
        if name == 'vcvrack_get_params': return json.dumps([{'id': i, 'value': v} for i, v in s.p[a['moduleId']].items()])
        if name == 'vcvrack_set_params':
            if s.fail and s.fail(a): s.fail = None; raise RuntimeError('rig write failed')   # one-shot failure
            s.sets.append(a); s.log.append((s.clk.t, a['moduleId'], {x['id']: x['value'] for x in a['params']}))
            for x in a['params']: s.p[a['moduleId']][x['id']] = x['value']
            return '[]'
        if name == 'vcvrack_get_module_state':
            s.reads.append((s.clk.t, a['id']))
            if a['id'] == synths.ARP: return json.dumps({'id': synths.ARP, 'data': dict(s.arp)})
            return json.dumps({'params': [{'id': i, 'value': v} for i, v in s.p[a['id']].items()], 'data': {'slots': [{'path': x} for x in s.path[a['id']]]}})
        if name == 'vcvrack_set_module_state':
            if a['id'] == synths.ARP: s.arp.update(a['state']['data']); s.log.append((s.clk.t, synths.ARP, dict(a['state']['data']))); return '{}'
            s.path[a['id']] = [x['path'] for x in a['state']['data']['slots']]; s.log.append((s.clk.t, a['id'], {'paths': list(s.path[a['id']])})); return '{}'
        raise AssertionError(name)
real_t = dict(call=S.call, time=fx.time, quick=fx.quick)
try:
    rig = Rig(); S.call = rig; rig.p[S.D].update({14: 0.8, 15: 0.8}); rig.p[S.MIX].update({2: U, 3: U, 4: U, 7: 0.0})
    S.base(); assert all(rig.p[S.D][14 + k] == 0.0 for k in range(4)) and rig.p[S.MIX][7] == 0.0, rig.p[S.D]   # strip 7 closed: Disco slots silenced
    assert all(x['id'] in (0, 1, 2, 3, 40, 41, 42, 43) for a in rig.sets if a['moduleId'] == S.MIX for x in a['params']), 'base never writes strip 7'
    rig.p[S.MIX][7] = U; rig.p[S.D][15] = 1.0; S.base(); assert rig.p[S.D][15] == 1.0, 'Disco open: base leaves its rows playing'
    rig = Rig(); S.call = rig; fx.time, fx.quick = rig.clk, rig
    K = S.ROWS[71]; rig.path[S.A][1] = K['samples'][0]; rig.p[S.A][15] = K['level']; rig.p[S.MIX].update({2: U, 3: U, 4: U, 7: 0.0})   # Lowdown keys playing
    rig.p[S.A].update({24 + k: v for k, v in enumerate(fx.BASEF[S.A])}); on = [{71: 0}, {}, {}, {}]
    assert fx.transition(2, on, lambda: True, song=0) is True                 # Lowdown -> Disco (break & drop): silent, so pad 1 of piano, bass, drums comes in
    assert rig.path[S.D][1] == RD[71]['samples'][0] and rig.path[S.D][0] == RD[41]['samples'][0] and rig.path[fx.C][0] == RD[21]['samples'][0], rig.path
    assert (rig.p[S.D][15], rig.p[S.D][14], rig.p[fx.C][14]) == (1.0, 1.0, 1.0) and rig.p[S.MIX][7] == U and on[2] == {71: 0, 41: 0, 21: 0}, (rig.p[S.MIX][7], on)
    assert all(rig.p[S.A][14 + k] == 0.0 for k in range(4)) and on[0][71] is None and rig.p[S.MIX][2] == U and rig.p[S.MIX][3] == U, 'Lowdown out, its strip ready at unity'
    assert [rig.p[S.A][24 + k] for k in range(4)] == fx.BASEF[S.A] and rig.p[S.MIX][4] == U, 'filters back at rest; drums strip kept'
    assert fx.transition(0, on, lambda: True, song=2) is True                 # back to Lowdown (break & drop): Disco out, its strip rests at 0 again
    assert all(rig.p[S.D][14 + k] == 0.0 for k in range(4)) and rig.p[S.MIX][7] == 0.0 and rig.p[S.MIX][2] == U, (rig.p[S.D], rig.p[S.MIX][7])
    assert on[2][71] is None and on[2][41] is None and [on[0][b] for b in fx.FIRST] == [0, 0, 0] and rig.path[fx.C][0] == S.ROWS[21]['samples'][0], on
    rig.sets.clear(); fx.clean(); assert rig.p[S.MIX][7] == 0.0 and not any(x['id'] == 7 for a in rig.sets if a['moduleId'] == S.MIX for x in a['params'])
    assert any(a['moduleId'] == S.D and {x['id'] for x in a['params']} == {36, 37, 38, 39} for a in rig.sets), 'clean un-reverses deck D'
finally: S.call, fx.time, fx.quick = real_t['call'], real_t['time'], real_t['quick']
print('Disco offline: page 3 rows on deck D (+ shared drums slot), files in disco-crate pinned bars 8 key B major, labels unique, mix map = deck D, own deck / strip 7 /'
      ' rest 0, drums only hushes strip 7, Synths acid row = the TOOM set, scale D major, base silences Disco slots when strip 7 is closed and never opens it,'
      ' transition in (pad 1 rows, strip 7 to unity, Lowdown out) and out (strip 7 back to 0), clean leaves strip 7, un-reverses deck D')
# ---- the song playing (pads.py PLAY / playing()): the arp's keys, the acid set and the MiniLab mix map follow it, never a page turn
mx = [0.0] * 8; mx[2] = mx[3] = U; lowk = S.ROWS[71]['samples'][0]                # strips: decks A, B open, deck D (7) resting at 0
pth = lambda **kw: [kw.get('p0', {}), kw.get('p1', {}), kw.get('p2', {}), {}]
assert fx.heard(mx, pth(p0={71: lowk})) == {0: U} and fx.playing(mx, pth(p0={71: lowk}), 2) == 0   # Lowdown heard, Disco page on show: Lowdown
assert fx.heard(mx, pth(p2={71: 'x'})) == {} and fx.playing(mx, pth(p2={71: 'x'}), 2) == 2 and fx.playing(mx, pth(), 3) == 0   # Disco cued at strip 0: not
assert fx.heard(mx, pth(p0={21: 'drums'})) == {}                                  # heard; none -> the song page on show, Synths page -> 0; drums row alone: no song
m3 = list(mx); m3[3] = 0.5; assert fx.playing(m3, pth(p0={71: 'a'}, p1={71: 'b'}), 1) == 0 and fx.playing(mx, pth(p0={71: 'a'}, p1={71: 'b'}), 1) == 1   # loudest; tie -> page on show
keep3 = [n for n in ast.parse(src_p).body if (isinstance(n, ast.FunctionDef) and n.name in ('turn', 'playing', 'fx_act'))
         or (isinstance(n, ast.Assign) and any(getattr(t, 'id', None) in ('PLAY', 'SP', 'SYN', 'HUSH') for t in n.targets))]
assert len(keep3) == 7, [getattr(n, 'name', None) for n in keep3]
tmpp, arp, trans = tempfile.mkdtemp(), {'locked': True, 'lockedMask': 2774}, []
def fake_arp2(name, a=None):                                                     # the arp's module data, written back by set_module_state
    if name == 'vcvrack_set_module_state': arp.update(a['state']['data']); return '{}'
    return json.dumps({'id': synths.ARP, 'data': dict(arp)})
st3 = dict(page=0, song=0, busy=False, fx=set(), tgen=0, on=[{} for _ in S.PAGES], slit=set())
fx3 = types.SimpleNamespace(transition=lambda pg, on, alive, song=None, tp=None: trans.append(pg) or True)
Q3 = dict(state=st3, sections=S, fx=fx3, synths=types.SimpleNamespace(follow=synths.follow, lit=lambda st: set()), os=os, here=tmpp, time=__import__('time'),
          threading=types.SimpleNamespace(Thread=SyncThread), traceback=__import__('traceback'), paint=lambda: None, LOG=types.SimpleNamespace(write=lambda s: None))
exec(compile(ast.Module(body=keep3, type_ignores=[]), 'pads.py', 'exec'), Q3)
real_pagef, real_call3 = maps.PAGEF, synths.S.call; maps.PAGEF = os.path.join(tmpp, 'page.txt')
try:
    synths.S.call = fake_arp2; Q3['playing'](0)                                 # Lowdown playing
    for p in (1, 2, 3): assert Q3['turn'](1) and st3['page'] == p                # turn to TOOM, Disco, then Synths
    assert st3['song'] == 0 and arp['lockedMask'] == 2774 and Q3['SP']() == 0, (st3['song'], arp)   # scale stays D major; Synths moves act on Lowdown
    assert [synths.pads(st3['song'])[81 + i][2] for i in range(3)] == S.ACID_SONG[0] and maps.mix_map()[83][:2] == (S.A, 15), maps.mix_map()[83]   # Lowdown's acid set, MiniLab on deck A
    Q3['turn'](-1); assert Q3['SP']() == 2; Q3['fx_act']('transition')           # Disco page: transition to Disco
    assert trans == [2] and st3['song'] == 2 and arp['lockedMask'] == DISCO_MASK and maps.mix_map()[83][:2] == (S.D, 15), (trans, st3['song'], arp)
    Q3['turn'](-1); Q3['turn'](-1); assert st3['page'] == 0 and st3['song'] == 2 and arp['lockedMask'] == DISCO_MASK   # back on the Lowdown page: Disco still playing
    fx3.transition = lambda pg, on, alive, song=None, tp=None: trans.append(pg) and False; Q3['fx_act']('transition')   # cut off (clean): the song playing stays
    assert trans == [2, 0] and st3['song'] == 2 and arp['lockedMask'] == DISCO_MASK and maps.page_now() == 2
    for held in ('drums only', 'dnb'):                                          # their release restores saved strips (strip 8 too): transition ignored
        st3['fx'] = {held}; Q3['fx_act']('transition'); assert trans == [2, 0] and st3['fx'] == {held}, (held, trans, st3['fx'])
    for nm in ('drums only', 'dnb', 'breakdown'):                               # and nothing that saves strips / filters engages mid-move
        st3['fx'] = {'transition'}; Q3['fx_act'](nm); assert st3['fx'] == {'transition'}, (nm, st3['fx'])
    st3['fx'] = set()
finally: maps.PAGEF, synths.S.call = real_pagef, real_call3; shutil.rmtree(tmpp, ignore_errors=True)
Q2['playing'] = lambda p: st2.__setitem__('song', p); real_strips = fx.strips    # a song pad pressed while no other song is heard: that song plays
try:
    S.play = lambda *a, **k: None; fx.strips = lambda: list(mx); logs.clear()
    st2.update(page=1, song=0, busy=False, rowpage={}, on=[{} for _ in S.PAGES], path=[{71: lowk}, {}, {}, {}])
    Q2['act'](71); assert st2['song'] == 0 and st2['on'][1][71] == 0             # Lowdown still heard: a TOOM pad cues, Lowdown stays playing
    st2['path'][0][71] = None; Q2['act'](72); assert st2['song'] == 1             # nothing else heard: TOOM is the song playing
    st2['page'] = 2; Q2['act'](71); assert st2['song'] == 1                      # TOOM heard: a Disco cue changes nothing
    opened = []; real_strip = fx.strip; fx.strip = lambda k, on: opened.append((k, on))
    try:
        Q2['act'](72); assert opened == [], opened                               # TOOM heard: Disco strip stays shut (a cue)
        st2['path'][1] = {}; st2['fx'] = {'drums only'}; Q2['act'](73); assert opened == [], opened   # drums only held: left shut
        st2['fx'] = set(); Q2['act'](74); assert st2['song'] == 2 and opened == [(7, True)], opened   # nothing heard, strip 7 shut: Disco opens
    finally: fx.strip = real_strip
    assert not [l for l in logs if 'Traceback' in l], logs
finally: S.play, fx.strips = real_play, real_strips
try:                                                                            # transition: an out deck already at strip 0 (a Disco cue) is left alone
    rig = Rig(); S.call = rig; fx.time, fx.quick = rig.clk, rig
    rig.path[S.A][1] = K['samples'][0]; rig.p[S.A][15] = K['level']; rig.p[S.MIX].update({2: U, 3: U, 4: U, 7: 0.0})   # Lowdown keys heard
    rig.path[S.D][1] = RD[71]['samples'][0]; rig.p[S.D][15] = 1.0; on = [{71: 0}, {}, {71: 0}, {}]                  # Disco piano cued at strip 0
    rig.sets.clear(); assert fx.transition(1, on, lambda: True, song=0) is True                                            # Lowdown -> TOOM
    assert rig.p[S.D][15] == 1.0 and on[2] == {71: 0} and rig.p[S.MIX][7] == 0.0 and all(rig.p[S.A][14 + k] == 0.0 for k in range(4)), (rig.p[S.D][15], on)
    assert not any(a['moduleId'] == S.D for a in rig.sets) and not any(x['id'] == 7 for a in rig.sets if a['moduleId'] == S.MIX for x in a['params']), 'deck D untouched'
    rig.p[S.MIX][7] = 0.4; fx.clean(0); assert rig.p[S.MIX][7] == 0.0 and [rig.p[S.MIX][k] for k in (2, 3, 4)] == [U, U, U]   # clean, Lowdown playing:
    rig.p[S.MIX][7] = 0.4; fx.clean(2); assert rig.p[S.MIX][7] == U                                               # a half-faded strip 8 back to 0; Disco playing: open
    rig.p[S.MIX][7] = 0.4; fx.clean(); assert rig.p[S.MIX][7] == 0.4                                              # no song given: left as is
    rig.log.clear(); rig.arp['lockedMask'] = 2774; fx.clean(2)                                                     # clean: STUT let go on every deck, arp on the song
    assert {m for t, m, w in rig.log if set(w) == set(range(fx.STUT, fx.STUT + 4)) and set(w.values()) == {0.0}} == {S.A, S.B, S.D, fx.C} and rig.arp['lockedMask'] == DISCO_MASK
finally: S.call, fx.time, fx.quick = real_t['call'], real_t['time'], real_t['quick']
print('Reviewer fixes offline: transition ignored while drums only / dnb held; transition leaves an out deck at strip 0 (Disco cue: slots, lit pads, strip 8);'
      ' clean settles strip 8: 0 unless Disco is the song playing, then unity')
print('Song playing offline: heard / playing (loudest, tie -> page on show, cued Disco at strip 0 not heard), Lowdown playing -> pages TOOM, Disco, Synths:'
      ' scale 2774, Lowdown acid set, mix map deck A; transition to Disco -> D major, deck D, page.txt 2; page turns back keep it; cut-off transition keeps it;'
      ' first song pad with no other song heard sets it, a cue over a heard song does not')
# ---- song-to-song moves (fx.MOVES): pair -> move, bar timing on the set clock, STUT, arp scale, cut-off, end state (rig, clock + time stubbed)
pairs = {(a, b): fx.move_for(a, b) for a in range(3) for b in range(3) if a != b}
assert pairs == {(0, 1): ('blend', 16), (1, 0): ('blend', 16), (0, 2): ('break_drop', 4), (2, 0): ('break_drop', 4), (1, 2): ('break_drop', 4),
                 (2, 1): ('break_drop', 4)}, pairs
mv0, sc0 = dict(fx.MOVES), dict(S.SCALES); fx.MOVES.clear(); S.SCALES[2] = (1, 3, 4, 6, 8, 10, 11)   # unlisted pairs go by key (Disco as B major here)
try: assert fx.move_for(0, 1) == ('blend', 16) and fx.move_for(2, 1) == ('break_drop', 4) and fx.move_for(2, 2) == ('blend', 16)
finally: fx.MOVES.update(mv0); S.SCALES.update(sc0)
SHARED = synths.mask_of(set(S.SCALES[0]) & set(S.SCALES[2]))                     # shared keys (D major both since 2026-11-07)
BEAT = 60.0 / 128; BAR = 4 * BEAT; STUTS = set(range(fx.STUT, fx.STUT + 4))
assert abs(16 * BAR - 30.0) < 1e-9 and abs(4 * BAR - 7.5) < 1e-9                # at 128: blend 30 s, break 7.5 s to the drop
def song_on(rig, page, on):                                                     # a song heard: pad 1 of its FIRST rows at row level, its strip open
    for b in fx.FIRST:
        r = S.PAGES[page]['rows'][b]; d = r.get('deck', S.A); rig.path[d][r['slot']] = r['samples'][0]; rig.p[d][14 + r['slot']] = r['level']; on[page][b] = 0
    rig.p[S.MIX][fx.STRIP[fx.own_deck(page)]] = U
def bar_after(tp):                                                              # the bar line after a press: nearest beat + 4 beats
    return round(tp / BEAT) * BEAT + 4 * BEAT
def fresh(page):
    rig = Rig(); S.call = rig; fx.time, fx.quick = rig.clk, rig; rig.p[S.MIX].update({2: U, 3: U, 4: U, 7: 0.0}); on = [{}, {}, {}, {}]
    for d in (S.A, S.B, fx.C, S.D):
        rig.p[d].update({24 + k: v for k, v in enumerate(fx.BASEF[d])}); rig.path[d] = [f'old-{k}.wav' for k in range(4)]   # every slot loaded, as on the rig
    song_on(rig, page, on); rig.arp['lockedMask'] = synths.mask_of(S.SCALES[page])
    return rig, on, bar_after(rig.clk.t)
def val(rig, T, m, i, v=0.0):                                                   # what (module, param) held at time T, from the write log
    for t, mm, w in rig.log:
        if t <= T + 1e-9 and mm == m and i in w: v = w[i]
    return v
def writes(rig, m, i): return [(t, w[i]) for t, mm, w in rig.log if mm == m and i in w]
def paths(rig, d, k): return [(t, w['paths'][k]) for t, m, w in rig.log if m == d and 'paths' in w]   # slot k path per module-state write
def rows_in(rig, page):                                                         # the song's FIRST rows: pad 1 paths at row levels
    return all(rig.path[r.get('deck', S.A)][r['slot']] == r['samples'][0] and rig.p[r.get('deck', S.A)][14 + r['slot']] == r['level']
               for b, r in S.PAGES[page]['rows'].items() if b in fx.FIRST)
real_setup = fx.setup
sc1 = dict(S.SCALES); S.SCALES[2] = (1, 3, 4, 6, 8, 10, 11)                    # the key-change path, run with Disco as B major (its record key)
SHARED, DISCO_B = synths.mask_of(set(S.SCALES[0]) & set(S.SCALES[2])), synths.mask_of(S.SCALES[2]); assert (SHARED, DISCO_B) == (2130, 3418)
try:
    for (a, b), (name, bars) in sorted(pairs.items()):                         # every ordered pair: its move, the same end state
        rig, on, t0 = fresh(a); da, db = fx.own_deck(a), fx.own_deck(b)
        assert fx.transition(b, on, lambda: True, song=lambda: a) is True, (a, b)
        stl = writes(rig, da, fx.STUTLEN)
        assert bool(stl) == (name == 'break_drop') and abs(rig.log[-1][0] - (t0 + bars * BAR)) <= fx.POLL, (a, b, stl, rig.log[-1][0] - t0)
        assert all(rig.p[da][14 + k] == 0.0 and rig.p[da][24 + k] == fx.BASEF[da][k] and rig.p[da][fx.STUT + k] == 0.0 for k in range(4)), (a, b, rig.p[da])
        assert rig.p[S.MIX][fx.STRIP[da]] == fx.REST.get(da, U) and rig.p[S.MIX][fx.STRIP[db]] == U and rig.p[S.MIX][4] == U and rows_in(rig, b), (a, b)
        assert all(on[a][r] is None for r in (71, 41)) and all(on[b][r] == 0 for r in fx.FIRST), (a, b, on)
        assert rig.p[fx.C][fx.STUT] == 0.0 and (name == 'blend' or rig.arp['lockedMask'] == synths.mask_of(S.SCALES[b])), (a, b, rig.arp)
        i_mix = max(i for i, (t, m, w) in enumerate(rig.log) if m == S.MIX and fx.STRIP[da] in w)   # the old song's strip goes back to rest only
        i_zero = max(i for i, (t, m, w) in enumerate(rig.log) if m == da and 14 in w)            # after its slots are zeroed (no end blip)
        assert i_zero < i_mix and rig.log[i_mix][2][fx.STRIP[da]] == fx.REST.get(da, U), (a, b, i_zero, i_mix)
    # bar 1 = the bar line after the press, even when the setup reads run past the beat (a press on the 1, setup taking 0.3 s)
    rig, on, _ = fresh(1); rig.clk.t = 1000 * BEAT + 0.01; fx.setup = lambda *a: (rig.clk.sleep(0.3), real_setup(*a))[1]
    assert fx.transition(2, on, lambda: True, song=1) is True and abs(writes(rig, S.B, fx.STUTLEN)[0][0] - (1004 * BEAT)) <= fx.POLL, writes(rig, S.B, fx.STUTLEN)[0]
    fx.setup = real_setup
    # blend Lowdown -> TOOM: drums + bass come up under Lowdown (bars 1-8), Lowdown high-passes away while keys + vocals come in (bars 9-16)
    rig, on, t0 = fresh(0); H = 8 * BAR
    assert fx.transition(1, on, lambda: True, song=lambda: 0) is True
    assert abs(rig.log[0][0] - t0) <= fx.POLL and rig.log[0] [1:] == (S.MIX, {3: 0.0}), ('blend starts on the bar line: TOOM strip down, then its rows', rig.log[0])
    assert [p for t, p in paths(rig, S.B, 0)][:2] == ['', S.ROWS_TOOM[41]['samples'][0]], 'TOOM bass slot emptied, then loaded: it plays from bar 1, not the wrap'
    assert all(t >= t0 + H - 1e-9 for t, m, w in rig.log if m == S.A or (m == S.MIX and 2 in w)), 'Lowdown untouched in bars 1-8'
    assert val(rig, t0 + 1, S.B, 14) == 1.0 and 0.3 * U < val(rig, t0 + 4 * BAR, S.MIX, 3) < 0.7 * U and val(rig, t0 + H, S.MIX, 3) > 0.99 * U, 'TOOM rises on its strip'
    assert val(rig, t0 + H, S.B, 15) == 0.0 and val(rig, t0 + H, S.B, 17) == 0.0, 'TOOM keys + vocals wait for bar 9'
    assert 0.3 < val(rig, t0 + 12 * BAR, S.B, 15) < 0.7 and 0.3 < val(rig, t0 + 12 * BAR, S.B, 17) < 0.7, 'keys + vocals rise over bars 9-16'
    kv = writes(rig, S.B, 15); assert max(v2 - v1 for (_, v1), (_, v2) in zip(kv, kv[1:])) < 0.01, 'slot level ramps in < 1 % steps (Recycler LEVEL is unsmoothed)'
    assert 0.2 < val(rig, t0 + 12 * BAR, S.A, 24) < 0.65 and 0.2 < val(rig, t0 + 12 * BAR, S.MIX, 2, U) < 0.5, 'Lowdown high-pass sweep + fade in bars 9-16'
    assert all(v == 1.0 for t, v in writes(rig, fx.C, 14)) and '' not in [p for t, p in paths(rig, fx.C, 0)] and rig.path[fx.C][0] == S.ROWS_TOOM[21]['samples'][0], \
        'shared drums slot sounding: never emptied, TOOM drums queued for the wrap (inside bars 1-8)'
    assert not any(m == synths.ARP for t, m, w in rig.log) and not writes(rig, S.A, fx.STUTLEN), 'blend: no STUT, no scale write (same key)'
    assert [rig.p[S.B][14 + k] for k in range(4)] == [1.0, 1.0, 0.0, 1.0] and on[1] == {41: 0, 21: 0, 71: 0, 81: 0}, (rig.p[S.B], on[1])
    # break & drop TOOM -> Disco: STUT 1/4, 1/4, 1/8, 1/16 per bar as TOOM's filters close, air on beat 4 of bar 4, Disco full on at bar 5
    rig, on, t0 = fresh(1); t_air, t_drop = t0 + 3 * BAR + 3 * BEAT, t0 + 4 * BAR
    assert fx.transition(2, on, lambda: True, song=lambda: 1) is True
    fb = next(x for x in rig.log if x[1] == S.B)                                # (deck A's open strip makes it an out deck too, as before: STUT on silence)
    assert abs(rig.log[0][0] - t0) <= fx.POLL and rig.log[0][2].get(fx.STUT) == 1.0 and fb[0] == rig.log[0][0] and fb[2].get(fx.STUT) == 1.0, ('STUT first, on the bar line', fb)
    for d, n in ((S.B, 4), (fx.C, 1)):                                          # TOOM's deck + the shared drums slot it was playing
        sl = writes(rig, d, fx.STUTLEN); assert [v for t, v in sl] == [0.0, 0.0, 1.0, 2.0], (d, sl)
        assert all(abs(t - (t0 + k * BAR)) <= fx.POLL for k, (t, v) in enumerate(sl)), (d, [t - t0 for t, v in sl])
        for k in range(n):
            h = writes(rig, d, fx.STUT + k); assert [v for t, v in h] == [1.0] * 4 + [0.0] and abs(h[-1][0] - t_air) <= fx.POLL, (d, k, h)
    i_air = next(i for i, (t, m, w) in enumerate(rig.log) if m == S.MIX and w.get(3) == 0.0)
    assert i_air < next(i for i, (t, m, w) in enumerate(rig.log) if m == S.B and w.get(fx.STUT) == 0.0), 'air: strips to 0 before STUT is let go'
    assert val(rig, t_air - 1e-6, S.B, 24) < -0.8 and val(rig, t_air - 1e-6, S.MIX, 3, U) == U, 'filters closed, TOOM strip still open until the air'
    assert val(rig, t_air, S.MIX, 3) == 0.0 and val(rig, t_air, S.MIX, 7) == 0.0 and val(rig, t_air, S.MIX, 4) == 0.0, 'air: strips at 0'
    pd = paths(rig, S.D, 1); assert [p for t, p in pd][:2] == ['', RD[71]['samples'][0]] and pd[1][0] < t0 + BAR, ('Disco piano loaded at bar 1, silent', pd)
    pc = paths(rig, fx.C, 0); assert [p for t, p in pc][-2:] == ['', RD[21]['samples'][0]] and all(t >= t_air - 1e-6 for t, p in pc[-2:]), ('drums slot swapped in the air', pc)
    assert val(rig, t_drop - 1e-6, S.D, 15) == 0.0 and val(rig, t_drop, S.D, 15) == 1.0 and val(rig, t_drop, S.MIX, 7) == U, 'Disco full on at the drop'
    ar = [(t, w['lockedMask']) for t, m, w in rig.log if m == synths.ARP]
    assert [v for t, v in ar] == [SHARED, DISCO_B] and abs(ar[0][0] - t0) <= fx.POLL and abs(ar[1][0] - t_drop) <= fx.POLL, ('shared keys, then the Disco scale', ar)
    assert rig.p[S.MIX][3] == U and all(rig.p[S.B][14 + k] == 0.0 for k in range(4)) and rows_in(rig, 2) and rig.p[S.MIX][4] == U, 'end state'
    # a deck whose other slots are empty is never emptied whole (the Recycler's scan would deal it a new combo): the path waits for the wrap
    rig, on, t0 = fresh(1); rig.path[S.D] = ['', '', '', '']
    assert fx.transition(2, on, lambda: True, song=1) is True and all(any(w['paths']) for t, m, w in rig.log if m == S.D and 'paths' in w) and rows_in(rig, 2)
    # cut off mid-break (clean): only STUT let go + the playing song's keys back after it, nothing else
    rig, on, t0 = fresh(1); T = t0 + 2.5 * BAR
    assert fx.transition(2, on, lambda: rig.clk.t < T, song=lambda: 1) is False
    after = [(m, w) for t, m, w in rig.log if t >= T]
    assert after and all((m in (S.A, S.B, fx.C) and set(w) <= STUTS and set(w.values()) == {0.0}) or (m == synths.ARP and w['lockedMask'] == 2774) for m, w in after), after
    assert any(m == synths.ARP for m, w in after) and rig.arp['lockedMask'] == 2774 and all(rig.p[S.B][fx.STUT + k] == 0.0 for k in range(4)) and rig.p[fx.C][fx.STUT] == 0.0
    # cut off before bar 1: nothing written at all; cut off mid-blend: nothing after
    rig, on, t0 = fresh(1); assert fx.transition(2, on, lambda: rig.clk.t < t0 - 0.01, song=1) is False and rig.log == [], rig.log
    rig, on, t0 = fresh(0); T = t0 + 10 * BAR
    assert fx.transition(1, on, lambda: rig.clk.t < T, song=0) is False and rig.log and all(t < T for t, m, w in rig.log), 'blend cut-off writes nothing after'
    # a rig write failing mid-break (bar 3 STUT): the error goes up, STUT still let go and the keys put back
    rig, on, t0 = fresh(1); rig.fail = lambda a: a['moduleId'] == S.B and any(x['id'] == fx.STUTLEN and x['value'] == 1.0 for x in a['params'])
    try: fx.transition(2, on, lambda: True, song=1); raise AssertionError('no error')
    except RuntimeError: pass
    assert all(rig.p[S.B][fx.STUT + k] == 0.0 for k in range(4)) and rig.p[fx.C][fx.STUT] == 0.0 and rig.arp['lockedMask'] == 2774, (rig.p[S.B], rig.arp)
    # STUT release fails once on one deck: the other deck is still let go, the retry gets the first, keys back
    rig, on, t0 = fresh(1); T = t0 + 1.5 * BAR
    rig.fail = lambda a: a['moduleId'] == S.B and any(x['id'] == fx.STUT and x['value'] == 0.0 for x in a['params'])
    assert fx.transition(2, on, lambda: rig.clk.t < T, song=1) is False
    assert all(rig.p[d][fx.STUT + k] == 0.0 for d in (S.A, S.B) for k in range(4)) and rig.p[fx.C][fx.STUT] == 0.0 and rig.arp['lockedMask'] == 2774
    # the drop's scale write failing: the move still counts as done (its end state is written)
    rig, on, t0 = fresh(1); real_ss = synths.set_scale; synths.set_scale = lambda pg: (_ for _ in ()).throw(RuntimeError('arp'))
    try: assert fx.transition(2, on, lambda: True, song=1) is True and rows_in(rig, 2)
    finally: synths.set_scale = real_ss
    # follow-ups: the air only writes (deck C's state read a bar ahead), a slot already on its path is left alone, a failed load at blend
    # bar 1 reopens the strips it took down, first-half rows on a deck that keeps its strip ramp on slot level in small steps
    rig, on, t0 = fresh(1); t_air = t0 + 3 * BAR + 3 * BEAT; rig.path[S.D][1] = RD[71]['samples'][0]
    assert fx.transition(2, on, lambda: True, song=1) is True and rows_in(rig, 2)
    cr = [t for t, m in rig.reads if m == fx.C]; assert cr and not [t for t in cr if t >= t_air - 1e-9] and abs(cr[-1] - (t0 + 3 * BAR)) <= fx.POLL, ('C read a bar ahead', cr, t_air)
    assert '' not in [p for t, p in paths(rig, S.D, 1)] and '' in [p for t, p in paths(rig, S.D, 0)], 'Disco piano already on its path: not emptied; bass swapped'
    rig, on, t0 = fresh(0); rig.fail = lambda a: a['moduleId'] == S.B and 14 in [x['id'] for x in a['params']]
    try: fx.transition(1, on, lambda: True, song=0); raise AssertionError('no error')
    except RuntimeError: pass
    assert rig.p[S.MIX][3] == U and [w for t, m, w in rig.log if m == S.MIX] == [{3: 0.0}, {3: U}], [w for t, m, w in rig.log if m == S.MIX]
    br0 = fx.BLEND_ROWS; fx.BLEND_ROWS = ((41, 71), (81,))                      # TOOM piano slot sounding (hot) on deck B: bass ramps on its slot
    try:
        rig, on, t0 = fresh(0); rig.p[S.B][15] = 0.5; H = 8 * BAR
        assert fx.transition(1, on, lambda: True, song=0) is True
        bs = writes(rig, S.B, 14); assert bs[0][1] == 0.0 and 0.3 < val(rig, t0 + 4 * BAR, S.B, 14) < 0.7 and max(v2 - v1 for (_, v1), (_, v2) in zip(bs, bs[1:])) < 0.01, bs[:3]
        assert 0.0 not in [w[3] for t, m, w in rig.log if m == S.MIX and 3 in w], 'deck B keeps its strip'
    finally: fx.BLEND_ROWS = br0
finally: S.call, fx.time, fx.quick, fx.setup = real_t['call'], real_t['time'], real_t['quick'], real_setup; S.SCALES.update(sc1)
print('Song moves follow-ups offline: air only writes (C read a bar ahead), unchanged slot paths left alone, failed blend load reopens strips,'
      ' first-half rows on a kept strip ramp on slot level < 1 % steps')
print('Song moves offline: 6 ordered pairs -> blend (Lowdown/TOOM) or break & drop (any Disco pair), unlisted by key; bar 1 = the bar line after the press'
      ' (setup running past the beat too); blend 16 bars (strip rise 1-8, keys + vocals in < 1 % steps + HP sweep 9-16, fresh slots emptied then loaded,'
      ' a sounding drums slot queued), break 4 bars (STUT 1/4 1/4 1/8 1/16 per bar, air on beat 4: strips then STUT, drums slot swapped in the air,'
      ' drop at bar 5), arp shared keys then target; old strips back to rest after their slots; cut-off / errors: STUT let go per deck + retry, keys back')
print('ok')
