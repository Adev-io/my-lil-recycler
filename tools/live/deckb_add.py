# Deck B "Steely Mind": second Recycler (row 3) on toom-crate, clock + reset from Clocked, MIX -> mixer strip 4 (fader 0).
# Slots: bass stem (level 0: Acid is the bass), piano, guitar, vocals of loop NN. usage: deckb_add.py [NN]
import json, os, re, sys, time
here = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(here, 'rack.py')).read().split('if sys.argv[1]')[0])
def call(n, a, t=60):
    r = rpc('tools/call', {'name': n, 'arguments': a}, timeout=t)
    if 'error' in r or r['result'].get('isError'): raise RuntimeError(str(r)[:300])
    return r['result']['content'][0]['text']
MIX = 2874844741614313; CLOCK = json.load(open(os.path.join(here, 'clock.json')))['CLOCK']
CR = r'C:\Users\Arikl\Desktop\uvr-loops\crates\toom-crate'; NN = sys.argv[1] if len(sys.argv) > 1 else '05'
mods = json.loads(call('vcvrack_list_modules', {}))
recs = [m for m in mods if m['slug'] == 'Recycler']
if len(recs) < 2:
    call('vcvrack_add_module', {'plugin_slug': 'MyLilRecycler', 'module_slug': 'Recycler', 'x': 29910, 'y': 39140}); time.sleep(1)
    recs = [m for m in json.loads(call('vcvrack_list_modules', {})) if m['slug'] == 'Recycler']
B = next(m['id'] for m in recs if m['id'] != 5192219511640844)
have = {(c['inputModuleId'], c['inputId']) for c in json.loads(call('vcvrack_list_cables', {}))}
for o, oi, i, ii in ((CLOCK, 0, B, 0), (CLOCK, 4, B, 2), (B, 8, MIX, 3), (B, 9, MIX, 11)):
    if (i, ii) not in have: call('vcvrack_add_cable', {'outputModuleId': o, 'outputId': oi, 'inputModuleId': i, 'inputId': ii})
call('vcvrack_set_params', {'moduleId': MIX, 'params': [{'id': 3, 'value': 0.0}, {'id': 43, 'value': 0}]})
files = sorted(f for f in os.listdir(CR) if f.endswith('.wav'))
paths = []
for stem in ('bass', 'piano', 'guitar', 'vocals'):
    c = [f for f in files if re.match(rf'\d-{stem}-(\d\d)_', f)]
    paths.append(CR.replace('\\', '/') + '/' + min(c, key=lambda f: abs(int(re.search(r'-(\d\d)_', f).group(1)) - int(NN))))
st = json.loads(call('vcvrack_get_module_state', {'id': B}))
st['data'].update(folder=CR, deck=True, run=True, root=9, minor=False, bars=8, chaos=0.0, title='Steely Mind',
                  slots=[{'path': p, 'locked': False, 'level': 0.0 if k == 0 else 1.0, 'k': 0, 's': 0} for k, p in enumerate(paths)])
for q in st['params']:
    if q['id'] in (2, 3, 4, 19): q['value'] = {2: 9.0, 3: 0.0, 4: 3.0, 19: 0.0}[q['id']]
    if q['id'] in (14, 15, 16, 17): q['value'] = 0.0 if q['id'] == 14 else 1.0
call('vcvrack_set_module_state', {'id': B, 'state': st})
time.sleep(25)
d = json.loads(call('vcvrack_get_module_state', {'id': B}))['data']; ps = {p['id']: p for p in json.loads(call('vcvrack_get_params', {'moduleId': B}))}
print('deck B', B, d.get('title'), 'root', ps[2]['displayValue'], ps[3]['displayValue'], 'bars', ps[4]['displayValue'])
print('  slots', [(os.path.basename(s['path'])[:26], s.get('s')) for s in d['slots']])
print('  peaks', [round(json.loads(call('vcvrack_measure', {'moduleId': B, 'outputId': o, 'seconds': 2}))['left']['peakDb']) for o in range(4)], '| strip 4', [p['displayValue'] for p in json.loads(call('vcvrack_get_params', {'moduleId': MIX})) if p['id'] == 3][0])
json.dump({'B': B}, open(os.path.join(here, 'deckb.json'), 'w'))
print(call('vcvrack_save_patch', {'path': os.path.expandvars(r'%LOCALAPPDATA%\Rack2\patches\dj-set.vcv')}))
