# Balance pass 2: Acid -2.5 dB, hat pad up, piano HP a touch more. Then save.
import json, os, sys, time
here = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(here, 'rack.py')).read().split('if sys.argv[1]')[0])
call = lambda n, a: rpc('tools/call', {'name': n, 'arguments': a}, timeout=40)['result']['content'][0]['text']
A, ACID, MIX, DRUMS = 5192219511640844, 8333663024495709, 2874844741614313, 7189220493962056
st = json.loads(call('vcvrack_get_module_state', {'id': DRUMS}))
pads = st['data']['pads']; names = [os.path.basename(str(s)) for s in st['data'].get('samples', [])]
print('pads 0-5 vol', [round(p['vol'], 2) for p in pads[:6]], '| samples', names[:6])
hits = lambda row: sum(1 for i in range(0, len(row), 2) if row[i:i + 2] != '00')
print('pattern 2 rows with hits', [(r, hits(x)) for r, x in enumerate(st['data']['patterns'][1]['rows']) if hits(x)])
pads[3]['vol'] = min(1.0, pads[3]['vol'] + 0.2)
call('vcvrack_set_module_state', {'id': DRUMS, 'state': st})
call('vcvrack_set_params', {'moduleId': ACID, 'params': [{'id': 6, 'value': 0.31}]})
call('vcvrack_set_params', {'moduleId': A, 'params': [{'id': 26, 'value': 0.3}]})
time.sleep(1)
print('hat pad vol now', round(json.loads(call('vcvrack_get_module_state', {'id': DRUMS}))['data']['pads'][3]['vol'], 2), '| acid volume', [p['displayValue'] for p in json.loads(call('vcvrack_get_params', {'moduleId': ACID})) if p['id'] == 6][0])
print(call('vcvrack_save_patch', {'path': os.path.expandvars(r'%LOCALAPPDATA%\Rack2\patches\dj-set.vcv')}))
