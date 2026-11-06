# Deck C = a Recycler for the record's drum stem (deck A's 4 slots are full). Clock/reset like deck A, MIX -> Mixer strip 5.
import json, os, sys, time
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import sections as S
call = S.call
C = json.load(open(os.path.join(here, 'clock.json')))['CLOCK']
before = {m['id'] for m in json.loads(call('vcvrack_list_modules', {}))}
print(call('vcvrack_add_module', {'plugin_slug': 'MyLilRecycler', 'module_slug': 'Recycler', 'x': 30450, 'y': 39140})[:120])
time.sleep(1.0)
new = [m for m in json.loads(call('vcvrack_list_modules', {})) if m['id'] not in before]
assert len(new) == 1, new
D = new[0]['id']; print('deck C id', D)
st = json.loads(call('vcvrack_get_module_state', {'id': S.A}))
st = {k: v for k, v in st.items() if k not in ('pos', 'leftModuleId', 'rightModuleId')}; st['id'] = D
drums = S.P('1-drums-14-115bpm.wav')
st['data']['title'] = 'Boz Down drums'
for k, s in enumerate(st['data']['slots']):
    s['path'] = drums; s['level'] = 1.0 if k == 0 else 0.0; s['locked'] = False
st['params'] = [dict(p, value=(1.0 if p['id'] == 14 else 0.0)) if p['id'] in (14, 15, 16, 17) else p for p in st['params']]
call('vcvrack_set_module_state', {'id': D, 'state': st})
for o, oi, i, ii in ((C, 0, D, 0), (C, 4, D, 2), (D, 8, S.MIX, 4), (D, 9, S.MIX, 12)):
    print(' cable', call('vcvrack_add_cable', {'outputModuleId': o, 'outputId': oi, 'inputModuleId': i, 'inputId': ii})[:80])
call('vcvrack_set_params', {'moduleId': S.MIX, 'params': [{'id': 4, 'value': 0.707}, {'id': 44, 'value': 0}]})
json.dump({'C': D}, open(os.path.join(here, 'deckc.json'), 'w'))
p = {x['id']: x for x in json.loads(call('vcvrack_get_params', {'moduleId': D}))}
print('deck C levels', [p[i]['displayValue'] for i in (14, 15, 16, 17)], '| slot0', os.path.basename(json.loads(call('vcvrack_get_module_state', {'id': D}))['data']['slots'][0]['path']))
