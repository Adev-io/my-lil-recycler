# Offline check for songs 4+ (sections.SONGS, Mixer 2 routing in fx, pads HUSH): a fake songs.json + fake crates, no Rack.
# usage: py -3.11 songs_check.py
import ast, json, os, tempfile
T = tempfile.mkdtemp()
for n in ('one', 'two'):
    os.makedirs(os.path.join(T, n))
    for st in ('1-drums', '2-bass', '3-guitar', '4-piano', '5-other', '6-vocals'):
        for k in range(1, 13): open(os.path.join(T, n, f'{st}-{k:02d}_{"intro" if k == 1 else "outro" if k == 12 else "vox"}-128bpm.wav'), 'w').close()
os.makedirs(os.path.join(T, 'empty'))
SJ = os.path.join(T, 'songs.json')
json.dump({'MIX2': 111, 'songs': [{'name': 'One', 'crate': os.path.join(T, 'one'), 'deck': 222, 'strip': 8},
                                  {'name': 'Two', 'crate': os.path.join(T, 'two'), 'deck': 333, 'strip': 9, 'root': 7},
                                  {'name': 'Not cut', 'crate': os.path.join(T, 'empty'), 'deck': 444, 'strip': 10}]}, open(SJ, 'w'))
os.environ['LIVE_SONGS'] = SJ
import sections as S, fx
names = [p['name'] for p in S.PAGES]
assert names == ['Lowdown', 'Time Out Of Mind', 'Disco Ulysses', 'One', 'Two', 'Synths'], names     # a song with no loops yet: no page
assert S.SONG_DECKS == [222, 333] and S.MIX2 == 111
R = S.PAGES[3]['rows']
assert sorted(R) == [21, 41, 51, 61, 71, 81] and R[81]['slot'] == 3 and R[71]['slot'] == 1 and R[61]['slot'] == R[51]['slot'] == 2 and R[41]['slot'] == 0
assert all(r['deck'] == 222 for b, r in R.items() if b != 21) and R[21]['deck'] == S.ROWS[21]['deck']   # drums: the shared deck C slot
v = [x.split('/')[-1] for x in R[81]['samples']]
assert len(v) == 8 and v[0] == '6-vocals-02_vox-128bpm.wav' and v[-1] == '6-vocals-11_vox-128bpm.wav' and not any(('_intro-' in x or '_outro-' in x) for x in v), v   # 10 mid loops spread to 8; intro/outro only if room
assert S.SCALES[3] == S.SCALES[1] and S.SCALES[4] == (0, 2, 4, 6, 7, 9, 11) and all(S.ACID_SONG[k] == S.ACID_SONG[1] for k in (3, 4))   # D major default, root 7 = G major; TOOM acid
assert fx.STRIP[222] == 8 and fx.STRIP[333] == 9 and fx.REST[222] == fx.REST[333] == 0.0 and fx.BASEF[333] == [0.0] * 4
assert fx.mixw({2: 0.5, 8: 0.7, 9: 0.0}) == {S.MIX: {2: 0.5}, 111: {0: 0.7, 1: 0.0}}
sent = []; real = S.call
try:
    S.call = lambda n, a=None: sent.append((n, a)) or json.dumps([{'id': i, 'value': (0.1 if a['moduleId'] == S.MIX else 0.2) * (i < 8)} for i in range(16)])
    fx.put({S.MIX: {3: 1.0, 8: 0.5}, 222: {14: 1.0}})
    ids = {a['moduleId']: [(p['id'], p['value']) for p in a['params']] for n, a in sent if n == 'vcvrack_set_params'}
    assert ids == {S.MIX: [(3, 1.0)], 111: [(0, 0.5)], 222: [(14, 1.0)]}, ids
    m = fx.strips(); assert len(m) == 16 and m[:8] == [0.1] * 8 and m[8:] == [0.2] * 8, m
    sent.clear(); fx.strip(9, True); assert [(a['moduleId'], a['params']) for n, a in sent] == [(111, [{'id': 1, 'value': S.U}])], sent
finally: S.call = real
mix = [0.0] * 16; mix[2] = S.U; mix[9] = S.U
paths = [{71: 'x'}, {}, {}, {81: 'y'}, {81: 'z'}, {}]
assert fx.heard(mix, paths) == {0: S.U, 4: S.U}                                       # One's strip (8) shut: not heard; Two's open
assert fx.move_for(0, 3) == ('blend', 16) and fx.move_for(3, 4) == ('break_drop', 4) and fx.move_for(4, 1) == ('break_drop', 4)   # D->D blend; to/from G major: break & drop
assert fx.own_deck(4) == 333 and 333 in fx.song_decks(4, [{}] * 6)
src = open(os.path.join(S.here, 'pads.py'), encoding='utf-8').read()
HU = next(n for n in ast.parse(src).body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', None) == 'HUSH')
assert eval(compile(ast.Expression(HU.value), 'pads.py', 'eval'), {'fx': fx, 'sections': S})['drums only'] == (1, 2, 3, 5, 6, 7, 8, 9)
import maps
assert len(maps.SONG_PARTS) == 5 and maps.mix_map(4)[83][:2] == (333, 15)            # MiniLab faders on song 5's deck
print('songs 4+ offline: pages from songs.json (uncut crate = no page), rows from the crate, D major + TOOM acid, Mixer 2 routing (put, strips, strip),'
      ' heard with 16 strips, blend / break by key, drums only hushes them, MiniLab map\nok')
