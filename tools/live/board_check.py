# Self-check for the virtual controller helpers in maps.py (no Rack needed): py -3.11 board_check.py
import maps, sections as S
for pg in S.PAGES:
    for b, r in sorted(pg['rows'].items(), reverse=True):
        l = maps.pad_labels(r['samples']); assert len(l) == len(r['samples']) and all(l), (r['name'], l); print(f'{pg["name"][:7]} {r["name"]:12s}', l)
        assert all(b + i <= b + 7 for i in range(len(l))), (r['name'], 'more than 8 pads')
assert S.PAGES[2]['synth'] and not S.PAGES[2]['rows'] and S.PAGES[2]['name'] == 'Synths', S.PAGES[2]   # page 3: Synths, no sample rows
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
assert set(S.SCALES) == {0, 1} and all(len(set(p)) == 7 and all(0 <= c < 12 for c in p) for p in S.SCALES.values()), S.SCALES
assert synths.mask_of((1, 2, 4, 6, 7, 9, 11)) == 2774
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
finally: synths.S.call = real_call
assert maps.ACID[77][:2] == (synths.ARP, 19) and maps.ACID[18][:2] == (synths.TRI, 28) and maps.ACID[16][:2] == (S.ACID, 28), 'Synths map'
assert maps.ACID[16][2](0) == -12.0 and maps.ACID[16][2](127) == 12.0 and maps.MODES['acid']['title'] == 'Synths'
for song in (0, 1):                                                          # Synths page pads (phase 3)
    P = synths.pads(song)
    assert all(n // 10 * 10 + 1 in synths.ROWS and 1 <= n % 10 <= 8 for n in P), sorted(P)
    assert all(l.isascii() and len(l) <= 12 for l, *_ in P.values()), [l for l, *_ in P.values()]
    assert all(0 <= v <= 31 for v in S.ACID_SONG[song]) and S.ACID_SONG[song][0] == (10, 14)[song]
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
P = dict(state={'busy': True, 'vox': {}, 'down': set(), 'held': set()}, fx=fx, MOVES=lambda: bank_[0], SYN=lambda: False, SP=lambda: 0, pad=lambda n: None,
         led=lambda *a, **k: None, paint=lambda: None, LOG=types.SimpleNamespace(write=lambda s: None), HOLDL=threading.RLock(), CLEANL=threading.Lock(),
         threading=types.SimpleNamespace(Thread=SyncThread), traceback=__import__('traceback'), time=__import__('time'),
         fx_act=lambda name: done.append(('fx_act', name)), act=lambda note, hw=False: done.append(('act', note)), let_go=lambda n: None)
exec(compile(ast.Module(body=fns, type_ignores=[]), 'pads.py', 'exec'), P)
msg = lambda t, n, v=100: types.SimpleNamespace(type=t, note=n, velocity=v)
try:
    vs = []; fx.vox_stut = lambda d, div: vs.append((d, div)); A = fx.own_deck(0)
    P['on_msg'](msg('note_on', 12)); P['on_msg'](msg('note_on', 13))             # busy the whole time (another press in flight)
    assert vs == [(A, 0), (A, 1)] and set(P['state']['vox']) == {12, 13}, vs        # second vox press while busy: NOT dropped
    P['on_msg'](msg('note_off', 12)); P['on_msg'](msg('note_on', 13, 0))            # (a note_on at velocity 0 = note off)
    assert vs == [(A, 0), (A, 1), (A, None)] and P['state']['vox'] == {} and not P['state']['down'], vs
    assert P['press'](12) is True and P['press'](12) is True and vs[-2:] == [(A, 0), (A, None)], vs   # page clicks toggle past busy too
    assert P['press'](11) is False and not done, done                             # other moves still wait on busy (drums in/out dropped)
    bank_[0] = fx.FX; assert P['press'](18) is True and done == [('fx_act', 'clean')], done   # clean (bank 1 pad 18) never dropped by busy
    assert P['state']['busy'] is True                                             # and leaves busy to the press that set it
finally: fx.vox_stut = real_vox['vox_stut']
print('Vox fixes offline: record before write (failed hold stays held + lit, its note off lets go), quick-stab let go retried once, clean per deck + first error raised,'
      ' no_stut drops 40-44, sections.play state has no params, pads.press/on_msg: second vox press while busy not dropped, clean past busy, other moves still wait')
print('Vox offline: FX3 12-15, one set_params call per hold / let go, slide = length only, first up keeps the second, latest up = back to the first length,'
      ' page turn releases the deck it started on, page 2 = deck B, quick stab, page click toggles, clean lets both decks go, failed off stays held')
print('DnB offline: snapshot records the set tempo, release + clean return to it (128), a snapshot without bpm falls back to 120')
print('Synths offline: auto_step mutate/next/undo + first-of-song + acid error keeps arp, hold-button release, octjump at 4, ramp cut-off, cancelled acid_out writes nothing after, acid_in floor 0.5, exception restores open, arp_in roll + ROLLS put back,'
      ' finished out after a newer press writes nothing, arp_in cut off in its roll writes no gate, held arp roll left alone')
print('ok')
