# Put the running rig back to the saved dj-set.vcv programming (Mixer, Drums, Clocked, Acid, decks A and B), restart on bar 1,
# and report what had drifted. Usage: py -3 reset.py
import json, os, sys, subprocess, tempfile, time
here = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(here, 'rack.py')).read().split('if sys.argv[1]')[0])
call = lambda n, a: rpc('tools/call', {'name': n, 'arguments': a}, timeout=60)['result']['content'][0]['text']
PATCH = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\patches\dj-set.vcv')
C = json.load(open(os.path.join(here, 'clock.json')))                      # Impromptu Clocked replaced Clkd on 2026-11-03
NAMES = {2874844741614313: 'Mixer', 7189220493962056: 'Drums', C['CLOCK']: 'Clocked', 8333663024495709: 'Acid', 5192219511640844: 'DeckA',
         json.load(open(os.path.join(here, 'deckb.json')))['B']: 'DeckB'}
d = tempfile.mkdtemp(); subprocess.run([r'C:\Windows\System32\tar.exe', '-xf', PATCH, '-C', d, 'patch.json'], check=True)
saved = {m['id']: m for m in json.load(open(os.path.join(d, 'patch.json'), encoding='utf-8'))['modules']}
drift = []
for mid, nm in NAMES.items():
    live = json.loads(call('vcvrack_get_module_state', {'id': mid}))
    lp = {p['id']: p['value'] for p in live['params']}; sp = {p['id']: p['value'] for p in saved[mid]['params']}
    for k in sp:
        if abs(lp.get(k, 0) - sp[k]) > 1e-3: drift.append(f'{nm} param {k}: {lp.get(k):.3g} -> {sp[k]:.3g}')
    if nm == 'DeckA':
        ls = [os.path.basename(s['path']) for s in live['data']['slots']]; ss = [os.path.basename(s['path']) for s in saved[mid]['data']['slots']]
        if ls != ss: drift.append(f'DeckA slots {ls} -> {ss}')
    if nm == 'Drums' and live['data'].get('patterns') != saved[mid]['data'].get('patterns'): drift.append('Drums patterns edited (restored from the save)')
    st = {k: v for k, v in saved[mid].items() if k not in ('pos', 'leftModuleId', 'rightModuleId')}
    if nm.startswith('Deck'): st['params'] = [p for p in st['params'] if not 40 <= p['id'] <= 44]   # Recycler STUT 40-44 (fx.STUT_IDS): never restored held
    r = call('vcvrack_set_module_state', {'id': mid, 'state': st})
    if 'error' in r.lower() or 'fail' in r.lower(): print(nm, 'restore reply:', r[:200])
time.sleep(1.5)
call('vcvrack_set_params', {'moduleId': C['CLOCK'], 'params': [{'id': C['P_RESET'], 'value': 1}]}); time.sleep(0.2)
call('vcvrack_set_params', {'moduleId': C['CLOCK'], 'params': [{'id': C['P_RESET'], 'value': 0}]})
print('drift fixed:' if drift else 'nothing had drifted'); [print('  ', x) for x in drift]
ps = {p['id']: p for p in json.loads(call('vcvrack_get_params', {'moduleId': 2874844741614313}))}
dr = {p['id']: p for p in json.loads(call('vcvrack_get_params', {'moduleId': 7189220493962056}))}
ac = {p['id']: p for p in json.loads(call('vcvrack_get_params', {'moduleId': 8333663024495709}))}
print('now: strips', [ps[i]['displayValue'][:5] for i in range(3)], '| drums pattern', dr[3]['displayValue'], '| acid', ac[24]['displayValue'], 'tune', ac[0]['displayValue'],
      '| clock', [p['displayValue'] for p in json.loads(call('vcvrack_get_params', {'moduleId': C['CLOCK']})) if p['id'] == C['P_BPM']][0])
