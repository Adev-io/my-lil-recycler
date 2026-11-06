# usage: swing_set.py <clk1 swing raw>   -> master swing 0, CLK1 swing as given, RESET, print displays + ranges
import json, os, sys, time
here = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(here, 'rack.py')).read().split('if sys.argv[1]')[0])
call = lambda n, a: rpc('tools/call', {'name': n, 'arguments': a}, timeout=30)['result']['content'][0]['text']
C = json.load(open(os.path.join(here, 'clock.json')))['CLOCK']
v = float(sys.argv[1])
call('vcvrack_set_params', {'moduleId': C, 'params': [{'id': 4, 'value': 0.0}, {'id': 5, 'value': v}]})
call('vcvrack_set_params', {'moduleId': C, 'params': [{'id': 12, 'value': 1}]}); time.sleep(0.2); call('vcvrack_set_params', {'moduleId': C, 'params': [{'id': 12, 'value': 0}]})
ps = {p['id']: p for p in json.loads(call('vcvrack_get_params', {'moduleId': C}))}
for i in (4, 5, 9, 15): print(f"{ps[i]['name']}: {ps[i]['displayValue']} (raw {ps[i]['value']:.3f}, range {ps[i]['min']}..{ps[i]['max']})")
