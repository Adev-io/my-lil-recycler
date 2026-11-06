import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(here, 'rack.py')).read().split('if sys.argv[1]')[0])
call = lambda n, a: rpc('tools/call', {'name': n, 'arguments': a}, timeout=30)['result']['content'][0]['text']
D = 7189220493962056
d = json.loads(call('vcvrack_get_module_state', {'id': D}))['data']
hits = lambda row: sum(1 for i in range(0, len(row), 2) if row[i:i + 2] != '00')
for i, p in enumerate(d['patterns']):
    per = [hits(r) for r in p['rows']]
    print(f'pattern {i + 1:2d} len {p["length"]:2d} total hits {sum(per):3d} | rows with hits', [(r, n) for r, n in enumerate(per) if n])
print('kick row of pattern 1 (first 16 steps):', [d['patterns'][0]['rows'][0][i:i + 2] for i in range(0, 32, 2)])
pads = d.get('pads'); print('pads type', type(pads).__name__, 'first:', json.dumps(pads[0] if isinstance(pads, list) else pads)[:200])
