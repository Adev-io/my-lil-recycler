# Replace Clkd with Impromptu Clocked (same cables), BPM 120, CLK1 x4 with swing so Drums + Acid 16ths match the record.
# usage: py -3 clock_swap.py <swing percent>
import json, os, re, sys, time
here = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(here, 'rack.py')).read().split('if sys.argv[1]')[0])
def call(n, a, t=60):
    r = rpc('tools/call', {'name': n, 'arguments': a}, timeout=t)
    if 'error' in r or r['result'].get('isError'): raise RuntimeError(str(r)[:300])
    return r['result']['content'][0]['text']
SWING = float(sys.argv[1]); OLD = 7081946395008297
mods = json.loads(call('vcvrack_list_modules', {}))
if not any(m['slug'] == 'Clocked' for m in mods):
    old = next(m for m in mods if m['id'] == OLD)
    call('vcvrack_add_module', {'plugin_slug': 'ImpromptuModular', 'module_slug': 'Clocked', 'x': old['x'] + old['width'], 'y': old['y']}); time.sleep(1)
    mods = json.loads(call('vcvrack_list_modules', {}))
NEW = next(m['id'] for m in mods if m['slug'] == 'Clocked')
info = json.loads(call('vcvrack_get_module', {'module_id': NEW}))
outs = {o['name'].lower(): o['id'] for o in info['outputs']}; prm = {p['name'].lower(): p for p in info['params']}
print('Clocked outputs', outs); print('Clocked params', {k: v['id'] for k, v in prm.items()})
pick = lambda d, *keys: next(v for k, v in d.items() if all(x in k for x in keys))
O_MASTER, O_CLK1, O_RESET = pick(outs, 'master'), pick(outs, 'clk 1') if any('clk 1' in k for k in outs) else pick(outs, 'clock 1'), pick(outs, 'reset')
P_BPM, P_RATIO1, P_SWING1, P_RESET = pick(prm, 'master')['id'], pick(prm, 'ratio')['id'] if any('ratio' in k and '1' in k for k in prm) else pick(prm, 'clk 1')['id'], pick(prm, 'swing')['id'], pick(prm, 'reset')['id']
# old cables -> new module (same destinations)
MAP = {0: O_MASTER, 1: O_CLK1, 4: O_RESET}
for c in json.loads(call('vcvrack_list_cables', {})):
    if c['outputModuleId'] == OLD:
        call('vcvrack_delete_cable', {'id': c['id']})
        call('vcvrack_add_cable', {'outputModuleId': NEW, 'outputId': MAP[c['outputId']], 'inputModuleId': c['inputModuleId'], 'inputId': c['inputId']})
def seek(pid, target):                       # bisection on the displayed number
    p = next(q for q in json.loads(call('vcvrack_get_params', {'moduleId': NEW})) if q['id'] == pid); lo, hi = p['min'], p['max']
    def num(v):
        call('vcvrack_set_params', {'moduleId': NEW, 'params': [{'id': pid, 'value': v}]})
        d = next(q['displayValue'] for q in json.loads(call('vcvrack_get_params', {'moduleId': NEW})) if q['id'] == pid)
        return float(re.findall(r'-?\d+\.?\d*', d)[0])
    for _ in range(16):
        mid = (lo + hi) / 2
        if num(mid) < target: lo = mid
        else: hi = mid
    num((lo + hi) / 2)
call('vcvrack_set_params', {'moduleId': NEW, 'params': [{'id': P_BPM, 'value': 120}, {'id': P_RATIO1, 'value': 5}]})
seek(P_SWING1, SWING)
st = json.loads(call('vcvrack_get_module_state', {'id': NEW}))
if not st['data'].get('running', True):
    run = pick(prm, 'run')['id']; call('vcvrack_set_params', {'moduleId': NEW, 'params': [{'id': run, 'value': 1}]}); time.sleep(0.2); call('vcvrack_set_params', {'moduleId': NEW, 'params': [{'id': run, 'value': 0}]})
call('vcvrack_set_params', {'moduleId': NEW, 'params': [{'id': P_RESET, 'value': 1}]}); time.sleep(0.2); call('vcvrack_set_params', {'moduleId': NEW, 'params': [{'id': P_RESET, 'value': 0}]})
call('vcvrack_delete_module', {'id': OLD})
time.sleep(2)
ps = {p['id']: p['displayValue'] for p in json.loads(call('vcvrack_get_params', {'moduleId': NEW}))}
print('Clocked', NEW, '| BPM', ps[P_BPM], '| CLK1 ratio', ps[P_RATIO1], '| swing 1', ps[P_SWING1], '| running', json.loads(call('vcvrack_get_module_state', {'id': NEW}))['data'].get('running'))
for mid, nm, o in ((7189220493962056, 'drums', 0), (8333663024495709, 'acid', 3), (5192219511640844, 'deck A', 8)):
    print(f'  {nm} peak', round(json.loads(call('vcvrack_measure', {'moduleId': mid, 'outputId': o, 'seconds': 2}))['left']['peakDb']), 'dB')
json.dump({'CLOCK': NEW, 'P_BPM': P_BPM, 'P_RATIO1': P_RATIO1, 'P_SWING1': P_SWING1, 'P_RESET': P_RESET}, open(os.path.join(here, 'clock.json'), 'w'))
print(call('vcvrack_save_patch', {'path': os.path.expandvars(r'%LOCALAPPDATA%\Rack2\patches\dj-set.vcv')}))
