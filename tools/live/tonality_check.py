import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(here, 'rack.py')).read().split('if sys.argv[1]')[0])
call = lambda n, a: rpc('tools/call', {'name': n, 'arguments': a}, timeout=30)['result']['content'][0]['text']
A, ACID = 5192219511640844, 8333663024495709
LIB = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\MyLilRecycler\library.json')
lib = {e['path']: e for e in json.load(open(LIB, encoding='utf-8'))}
d = json.loads(call('vcvrack_get_module_state', {'id': A}))['data']
ps = {p['id']: p for p in json.loads(call('vcvrack_get_params', {'moduleId': A}))}
print('deck A root', ps[2]['displayValue'], ps[3]['displayValue'], '| data root', d['root'], 'minor', d['minor'])
for s in d['slots']:
    e = lib.get(s['path']); st = os.stat(s['path'])
    match = e and e['size'] == st.st_size and e['mtime'] == int(st.st_mtime)
    print(f"  {os.path.basename(s['path']):30s} shift s={s.get('s')} k={s.get('k')} | cache key {e['key'] if e else '?'} minor {e['minor'] if e else '?'} tempo {round(e['tempo'], 1) if e else '?'} conf {e['keyConf'] if e else '?'} | entry matches file: {bool(match)}")
n = [e for p, e in lib.items() if '/lowdown2-crate/' in p]
print('lowdown2 cache entries', len(n), 'keys', sorted({(e['key'], e['minor']) for e in n}), 'keyConf', sorted({round(e['keyConf'], 2) for e in n}))
a = {p['id']: p for p in json.loads(call('vcvrack_get_params', {'moduleId': ACID}))}
print('acid pattern', a[24]['displayValue'], 'tune', a[0]['displayValue'], 'cents')
