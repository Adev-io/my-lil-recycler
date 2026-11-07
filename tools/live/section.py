# usage: py -3 section.py <name>   -> moves the dj-set rig to that section (deck A loops + Acid pattern). One move, then save.
import json, os, re, sys, time
here = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(here, 'rack.py')).read().split('if sys.argv[1]')[0])
call = lambda n, a: rpc('tools/call', {'name': n, 'arguments': a}, timeout=60)['result']['content'][0]['text']
A, ACID = 5192219511640844, 8333663024495709
CR = r'C:\Users\Arikl\Desktop\uvr-loops\crates\lowdown2-crate'
SECTIONS = {          # name: (deck A loop number, Acid pattern index, Acid pattern name, slot-1 song-bass level)
    '1-intro': (3, 10, 'I-B3', 0.0), '2-chorus': (14, 12, 'I-B5', 0.0), '3-chorus-bass': (14, 12, 'I-B5', 0.8),
    'verse': (9, 11, 'I-B4', 0.0), 'turn': (17, 13, 'I-B6', 0.0),
}
name = sys.argv[1]; loop, pat, patname, bass = SECTIONS[name]
files = sorted(f for f in os.listdir(CR) if f.endswith('.wav'))
st = json.loads(call('vcvrack_get_module_state', {'id': A}))
for s in st['data']['slots']:
    stem = re.match(r'\d-(\w+)-', os.path.basename(s['path'])).group(1)
    c = [f for f in files if re.match(rf'\d-{stem}-\d\d', f)]
    s['path'] = CR.replace('\\', '/') + '/' + min(c, key=lambda f: abs(int(re.search(r'-(\d\d)-', f).group(1)) - loop))
st.pop('params', None)                                  # data only: params stay as Rack has them (a STUT hold is not overwritten)
call('vcvrack_set_module_state', {'id': A, 'state': st})
call('vcvrack_set_params', {'moduleId': ACID, 'params': [{'id': 24, 'value': pat}]})
call('vcvrack_set_params', {'moduleId': A, 'params': [{'id': 14, 'value': bass}]})
time.sleep(1)
d = json.loads(call('vcvrack_get_module_state', {'id': A}))['data']
print(name, '->', [os.path.basename(s['path']) for s in d['slots']], '| slot-1 bass level', [p['displayValue'] for p in json.loads(call('vcvrack_get_params', {'moduleId': A})) if p['id'] == 14][0], 'dB | Acid', [p['displayValue'] for p in json.loads(call('vcvrack_get_params', {'moduleId': ACID})) if p['id'] == 24][0])
print(call('vcvrack_save_patch', {'path': os.path.expandvars(r'%LOCALAPPDATA%\Rack2\patches\dj-set.vcv')}))
