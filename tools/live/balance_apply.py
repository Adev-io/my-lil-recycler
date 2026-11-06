# Balance pass 1: drums lead by ~2 dB; the record's bass stem becomes mid texture (lower + high-passed); Acid high-passed at
# 35 Hz so only the kick owns the sub; piano/guitar trimmed, vocals at 0 dB. Then save.
import json, os, sys, time
here = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(here, 'rack.py')).read().split('if sys.argv[1]')[0])
call = lambda n, a: rpc('tools/call', {'name': n, 'arguments': a}, timeout=40)['result']['content'][0]['text']
A, ACID, MIX, DRUMS = 5192219511640844, 8333663024495709, 2874844741614313, 7189220493962056
call('vcvrack_set_params', {'moduleId': MIX, 'params': [{'id': 0, 'value': 0.80}]})                                    # drums strip ~ +2 dB
call('vcvrack_set_params', {'moduleId': A, 'params': [{'id': 14, 'value': 0.5}, {'id': 15, 'value': 1.2}, {'id': 16, 'value': 1.0}, {'id': 17, 'value': 1.0},
                                                      {'id': 25, 'value': 0.45}, {'id': 26, 'value': 0.2}]})           # bass stem HP, piano slight HP
# Acid high-pass: find the raw value that reads ~35 Hz
ps = {p['id']: p for p in json.loads(call('vcvrack_get_params', {'moduleId': ACID}))}; lo, hi = ps[15]['min'], ps[15]['max']
import re
def hz(v):
    call('vcvrack_set_params', {'moduleId': ACID, 'params': [{'id': 15, 'value': v}]})
    return float(re.findall(r'\d+\.?\d*', next(p['displayValue'] for p in json.loads(call('vcvrack_get_params', {'moduleId': ACID})) if p['id'] == 15))[0])
for _ in range(14):
    mid = (lo + hi) / 2
    if hz(mid) < 35: lo = mid
    else: hi = mid
print('acid HP now', hz((lo + hi) / 2), 'Hz')
time.sleep(2)
mx = {p['id']: p for p in json.loads(call('vcvrack_get_params', {'moduleId': MIX}))}; da = {p['id']: p for p in json.loads(call('vcvrack_get_params', {'moduleId': A}))}
print('strips', [mx[i]['displayValue'][:6] for i in range(3)], '| deck A levels', [da[i]['displayValue'][:6] for i in (14, 15, 16, 17)], '| bass filt', da[25]['displayValue'], 'piano filt', da[26]['displayValue'])
print(call('vcvrack_save_patch', {'path': os.path.expandvars(r'%LOCALAPPDATA%\Rack2\patches\dj-set.vcv')}))
