# Self-check for the virtual controller helpers in maps.py (no Rack needed): py -3.11 board_check.py
import maps, sections as S
for pg in S.PAGES:
    for b, r in sorted(pg['rows'].items(), reverse=True):
        l = maps.pad_labels(r['samples']); assert len(l) == len(r['samples']) and all(l), (r['name'], l); print(f'{pg["name"][:7]} {r["name"]:12s}', l)
        assert all(b + i <= b + 7 for i in range(len(l))), (r['name'], 'more than 8 pads')
assert maps.pad_labels(S.ROWS_TOOM[71]['samples'])[:2] == ['05 verse', '02 verse']
assert maps.pad_labels(S.ROWS[81]['samples']) == ['14 chop', '14'], maps.pad_labels(S.ROWS[81]['samples'])
assert maps.pad_labels(S.ROWS[31]['samples'])[:3] == ['strings 08', 'strings 13', 'full 08']
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
print('ok')
