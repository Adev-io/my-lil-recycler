# Recycler normalises every render to -18 dBFS RMS, so a near-silent loop plays as boosted hiss. Find loops under -42 dBFS RMS
# in the set's crates, move playing slots off them (nearest loud loop, same stem), then move those files to crates\_quiet\<crate>.
import json, os, re, sys, shutil, glob, time, numpy as np, soundfile as sf
here = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(here, 'rack.py')).read().split('if sys.argv[1]')[0])
call = lambda n, a, t=60: rpc('tools/call', {'name': n, 'arguments': a}, timeout=t)['result']['content'][0]['text']
CR = r'C:\Users\Arikl\Desktop\uvr-loops\crates'; Q = os.path.join(CR, '_quiet'); TH = -42.0
mods = json.loads(call('vcvrack_list_modules', {})); decks = [m for m in mods if m['slug'] == 'Recycler']
quiet = {}
for m in decks:
    folder = json.loads(call('vcvrack_get_module_state', {'id': m['id']}))['data']['folder']
    for f in glob.glob(os.path.join(folder, '*.wav')):
        y, _ = sf.read(f, always_2d=True)
        r = 20 * np.log10(np.sqrt(np.mean(y ** 2)) + 1e-12)
        if r < TH: quiet[f.replace('\\', '/')] = round(r, 1)
print('near-silent loops:', len(quiet))
for k, v in sorted(quiet.items()): print('  ', v, 'dB', k.split('/crates/')[1])
for m in decks:
    st = json.loads(call('vcvrack_get_module_state', {'id': m['id']})); d = st['data']; changed = False
    files = sorted(f for f in os.listdir(d['folder']) if f.endswith('.wav') and os.path.join(d['folder'], f).replace('\\', '/') not in quiet)
    for s in d['slots']:
        if s['path'] in quiet:
            stem = re.match(r'\d-(\w+?)-\d\d', os.path.basename(s['path'])).group(1); n = int(re.search(r'-(\d\d)', os.path.basename(s['path'])).group(1))
            cand = [f for f in files if re.match(rf'\d-{stem}-\d\d', f)]
            new = min(cand, key=lambda f: abs(int(re.search(r'-(\d\d)', f).group(1)) - n)) if cand else None
            print(f"{d.get('title')}: slot {os.path.basename(s['path'])} -> {new}")
            if new: s['path'] = d['folder'].replace('\\', '/') + '/' + new; changed = True
    st.pop('params', None)                                  # data only: params stay as Rack has them (a STUT hold is not overwritten)
    if changed: call('vcvrack_set_module_state', {'id': m['id'], 'state': st})
for f in quiet:
    rel = f.split('/crates/')[1]; dst = os.path.join(Q, rel.replace('/', os.sep)); os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(f.replace('/', os.sep), dst)
print('moved', len(quiet), 'files to', Q)
time.sleep(8)
A = 5192219511640844
print('deck A slots now:', [os.path.basename(s['path']) for s in json.loads(call('vcvrack_get_module_state', {'id': A}))['data']['slots']],
      '| slot 3 out', json.loads(call('vcvrack_measure', {'moduleId': A, 'outputId': 2, 'seconds': 2}))['left']['peakDb'])
