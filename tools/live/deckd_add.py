# Deck D "Disco Ulysses": a fourth Recycler (row 4, after deck C) on disco-crate, silent until used. Clock/reset from Clocked
# (out 0 / out 4, as decks A-C), MIX L/R -> Mixer strip 8 (index 7 = inputs 7 / 15; level stays 0). DECK mode, BARS 8, root B
# major (the crate's pin), all 4 slot levels 0. Slots = bass, piano, guitar, other (horns/synth) of the full-band chorus 08
# (other only exists in 11/12). Touches no other module: checks strip 7 is free first, then diffs every other module's params
# and the cable list before/after. Patch backup first; id saved to deckd.json. usage: py -3.11 deckd_add.py
import json, os, sys, time, shutil
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import sections as S
call = S.call
CLOCK = json.load(open(os.path.join(here, 'clock.json')))['CLOCK']
CR = r'C:\Users\Arikl\Desktop\uvr-loops\crates\disco-crate'; X, Y = 30990, 39140; STRIP = 7
PATCH = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\patches\dj-set.vcv')
SLOTS = ['2-bass-08_chorus-134bpm.wav', '4-piano-08_chorus-134bpm.wav', '3-guitar-08_chorus-134bpm.wav', '5-other-12_bridge-134bpm.wav']
for f in SLOTS: assert os.path.exists(os.path.join(CR, f)), f
def snap():
    mods = json.loads(call('vcvrack_list_modules', {}))
    ps = {m['id']: {p['id']: p['value'] for p in json.loads(call('vcvrack_get_params', {'moduleId': m['id']}))} for m in mods if m['params']}
    cab = {(c['outputModuleId'], c['outputId'], c['inputModuleId'], c['inputId']) for c in json.loads(call('vcvrack_list_cables', {}))}
    return mods, ps, cab
mods0, ps0, cab0 = snap()
assert not [c for c in cab0 if c[2] == S.MIX and c[3] in (STRIP, STRIP + 8)], 'mixer strip 8 inputs are taken'
assert ps0[S.MIX][STRIP] == 0.0, f'strip {STRIP} level is {ps0[S.MIX][STRIP]}'
row = sorted((m['x'], m['x'] + m['width']) for m in mods0 if m['y'] == Y)
assert all(b <= X or a >= X + 540 for a, b in row) and X + 540 <= 29910 + 1800, f'no room at x {X}: {row}'
bk = os.path.join(os.path.dirname(PATCH), '_archive-20261103', time.strftime('dj-set-%Y%m%d-%H%M%S-before-deckd.vcv'))
shutil.copy2(PATCH, bk); print('patch backup', bk)
print(call('vcvrack_add_module', {'plugin_slug': 'MyLilRecycler', 'module_slug': 'Recycler', 'x': X, 'y': Y})[:120]); time.sleep(1.0)
new = [m for m in json.loads(call('vcvrack_list_modules', {})) if m['id'] not in ps0 and m['id'] not in {x['id'] for x in mods0}]
assert len(new) == 1, new
D = new[0]['id']; print('deck D', D, 'at', new[0]['x'], new[0]['y'], 'width', new[0]['width'])
json.dump({'D': D}, open(os.path.join(here, 'deckd.json'), 'w'))
call('vcvrack_set_params', {'moduleId': D, 'params': [{'id': i, 'value': 0.0} for i in (14, 15, 16, 17)]})   # silent first
st = json.loads(call('vcvrack_get_module_state', {'id': D}))
st['data'].update(folder=CR, deck=True, run=True, root=11, minor=False, bars=8, chaos=0.0, title='Disco Ulysses',
                  slots=[{'path': CR.replace('\\', '/') + '/' + f, 'locked': False, 'level': 0.0, 'k': 0, 's': 0} for f in SLOTS])
for q in st['params']:
    if q['id'] in (2, 3, 4, 19): q['value'] = {2: 11.0, 3: 0.0, 4: 3.0, 19: 0.0}[q['id']]
    if q['id'] in (14, 15, 16, 17): q['value'] = 0.0
call('vcvrack_set_module_state', {'id': D, 'state': st})          # a brand-new module: no live STUT hold to clobber
for o, oi, i, ii in ((CLOCK, 0, D, 0), (CLOCK, 4, D, 2), (D, 8, S.MIX, STRIP), (D, 9, S.MIX, STRIP + 8)):
    print(' cable', call('vcvrack_add_cable', {'outputModuleId': o, 'outputId': oi, 'inputModuleId': i, 'inputId': ii})[:80])
time.sleep(25)
d = json.loads(call('vcvrack_get_module_state', {'id': D}))['data']; ps = {p['id']: p for p in json.loads(call('vcvrack_get_params', {'moduleId': D}))}
print('deck D', d.get('title'), 'deck', d.get('deck'), 'folder', d.get('folder'), '| root', ps[2]['displayValue'], ps[3]['displayValue'], 'bars', ps[4]['displayValue'])
print('  levels', [ps[i]['displayValue'] for i in (14, 15, 16, 17)], '| slots', [(os.path.basename(s['path']), s.get('level')) for s in d['slots']])
print('  slot peaks (dB)', [json.loads(call('vcvrack_measure', {'moduleId': D, 'outputId': o, 'seconds': 1.5}))['left']['peakDb'] for o in range(4)],
      '| MIX L', json.loads(call('vcvrack_measure', {'moduleId': D, 'outputId': 8, 'seconds': 1.5}))['left']['peakDb'])
mods1, ps1, cab1 = snap()
print('cables added', sorted(cab1 - cab0), '| removed', sorted(cab0 - cab1))
diff = {m: {k: (ps0[m][k], v) for k, v in ps1[m].items() if abs(v - ps0[m].get(k, v)) > 1e-6} for m in ps1 if m in ps0}
print('other modules param changes during the add:', {m: v for m, v in diff.items() if v} or 'none')
print(S.save()[:120])
