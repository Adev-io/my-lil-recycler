# Self-check for the virtual controller helpers in maps.py (no Rack needed): py -3.11 board_check.py
import maps, sections as S
for pg in S.PAGES:
    for b, r in sorted(pg['rows'].items(), reverse=True):
        l = maps.pad_labels(r['samples']); assert len(l) == len(r['samples']) and all(l), (r['name'], l); print(f'{pg["name"][:7]} {r["name"]:12s}', l)
        assert all(b + i <= b + 7 for i in range(len(l))), (r['name'], 'more than 8 pads')
assert S.PAGES[2]['synth'] and not S.PAGES[2]['rows'] and S.PAGES[2]['name'] == 'Synths', S.PAGES[2]   # page 3: Synths, no sample rows
assert maps.pad_labels(S.ROWS_TOOM[71]['samples'])[:2] == ['05 verse', '02 verse']
assert maps.pad_labels(S.ROWS[81]['samples']) == ['14 chop', '14'], maps.pad_labels(S.ROWS[81]['samples'])
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
sent, rig = [], {S.ACID: {24: 10.0}, synths.ARP: {16: 1.0, 18: 2.0, 19: 0.6}}
class Rng:
    def __init__(s, *v): s.v = list(v)
    def random(s): return s.v.pop(0)
def cutoff(v=None):
    if v is None: return rig['cut']
    rig['cut'] = v; sent.append(('cut', v))
def fails(): raise RuntimeError('no rig')
try:
    synths.setp = lambda mid, vals: sent.append((mid, dict(vals)))
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
    rig['cut'] = 0.4; synths._open.clear(); sent.clear()                     # out reaches its end, but a newer press came in on the last step:
    synths.acid_out(lambda: rig['cut'] > 0.05 + 1e-9)                          # no strip down, no cutoff restore, _open kept for the newer one
    assert not any(k == 'strip' for k, _ in sent) and sent[-1][0] == 'cut' and abs(sent[-1][1] - 0.05) < 1e-9 and synths._open == {'cut': 0.4}, sent
    live = [True]                                                            # arp_in cut off during its roll: lets go of its own roll x4,
    synths.setp = lambda mid, vals: (sent.append((mid, dict(vals))), vals.get(21) == 1.0 and live.__setitem__(0, False))   # then no gate write
    synths._open.clear(); sent.clear(); synths.arp_in(0.5, lambda: live[0]); i = sent.index((synths.ARP, {20: 4.0, 21: 1.0}))
    assert sent[i + 1:] == [(synths.ARP, {21: 0.0})] and synths._open == {'gate': 0.6}, sent
    synths.setp = lambda mid, vals: sent.append((mid, dict(vals)))
    rig[synths.ARP][21] = 1.0; synths._open.clear(); sent.clear(); synths.arp_in(0.5, lambda: True)   # arp roll fill held: no x4, no release
    assert not any(k == synths.ARP and 21 in v for k, v in sent) and synths._open == {}, sent
    del rig[synths.ARP][21]
finally:
    for k, v in real.items(): setattr(synths, k, v)
    for k, v in real_fx.items(): setattr(fx, k, v)
    synths._open.clear()
print('Synths offline: auto_step mutate/next/undo + first-of-song + acid error keeps arp, hold-button release, octjump at 4, ramp cut-off, cancelled acid_out writes nothing after, acid_in floor 0.5, exception restores open, arp_in roll,'
      ' finished out after a newer press writes nothing, arp_in cut off in its roll writes no gate, held arp roll left alone')
print('ok')
