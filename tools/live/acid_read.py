import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(here, 'rack.py')).read().split('if sys.argv[1]')[0])
call = lambda n, a: rpc('tools/call', {'name': n, 'arguments': a}, timeout=30)['result']['content'][0]['text']
ps = {p['id']: p for p in json.loads(call('vcvrack_get_params', {'moduleId': 8333663024495709}))}
print('ACID now:', ' | '.join(f"{ps[i]['name'][:12]}={ps[i]['displayValue']}" for i in (0, 1, 2, 3, 4, 5, 6, 7, 15, 22, 24)))
