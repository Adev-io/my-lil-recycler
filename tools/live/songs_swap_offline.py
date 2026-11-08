# Swap a song deck's crate offline, in dj-set.vcv itself (Rack closed; no audio device or MCP needed). For each songs.json entry
# whose name is not in songs_add.WANT, the next WANT song not yet in songs.json takes its deck: folder, title, root, slots (levels 0),
# ROOT param, slot levels and STUT holds 0. Same module, strip and cables. Patch backup first; repacked with tar.exe (zstd);
# read back after. usage: py -3.11 songs_swap_offline.py [--dry]
import json, os, re, sys, time, shutil, subprocess, tempfile
here = os.path.dirname(os.path.abspath(__file__))
PATCH = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\patches\dj-set.vcv'); TAR = r'C:\Windows\System32\tar.exe'; SONGF = os.path.join(here, 'songs.json')
src = open(os.path.join(here, 'songs_add.py'), encoding='utf-8').read()
CR = r'C:\Users\Arikl\Desktop\uvr-loops\crates'
WANT = eval(src[src.index('WANT = [') + 7:src.index('MX2 = ')].strip(), {'CR': CR})
def slot_loops(crate):                                         # same pick as songs_add.py: bass, piano (else other), other (else guitar), vocals
    fs = sorted(f for f in os.listdir(crate) if f.endswith('.wav'))
    def first(*stems):
        for st in stems:
            c = [f for f in fs if re.match(rf'\d-{st}-\d\d_', f)]; c = [f for f in c if not re.search(r'_(intro|outro)-', f)] or c
            if c: return crate.replace('\\', '/') + '/' + c[0]
        return ''
    return [first('bass'), first('piano', 'other'), first('other', 'guitar'), first('vocals')]
assert not subprocess.run(['powershell', '-NoProfile', '-Command', '(Get-Process Rack -ErrorAction SilentlyContinue).Id'], capture_output=True, text=True).stdout.strip(), 'close Rack first'
cfg = json.load(open(SONGF)); names = {w['name'] for w in WANT}
spare = [s for s in cfg['songs'] if s['name'] not in names]; todo = [w for w in WANT if w['name'] not in {s['name'] for s in cfg['songs']}]
assert spare and len(todo) <= len(spare) and all(os.path.isdir(w['crate']) for w in todo), (spare, todo)
w_dir = tempfile.mkdtemp(); subprocess.run([TAR, '-xf', PATCH, '-C', w_dir], check=True)
pj = os.path.join(w_dir, 'patch.json'); p = json.load(open(pj, encoding='utf-8')); M = {m['id']: m for m in p['modules']}
for old, w in zip(spare, todo):
    m = M[old['deck']]; assert m['plugin'] == 'MyLilRecycler' and m['model'] == 'Recycler', m['model']
    m['data'].update(folder=w['crate'], title=w['name'], root=w['root'], minor=False, bars=8, chaos=0.0, deck=True, run=True,
                     slots=[{'path': x, 'locked': False, 'level': 0.0, 'k': 0, 's': 0} for x in slot_loops(w['crate'])])
    for q in m['params']:
        if q['id'] == 2: q['value'] = float(w['root'])
        if q['id'] == 3: q['value'] = 0.0
        if q['id'] in (14, 15, 16, 17) or 40 <= q['id'] < 44: q['value'] = 0.0
    i = cfg['songs'].index(old); cfg['songs'][i] = dict(name=w['name'], crate=w['crate'], deck=old['deck'], strip=old['strip'], root=w['root'])
    print(old['name'], '->', w['name'], 'deck', old['deck'], 'strip', old['strip'], [os.path.basename(s['path']) for s in m['data']['slots']])
if '--dry' in sys.argv: sys.exit(0)
bk = PATCH.replace('.vcv', time.strftime('.bak-pre-songswap-%Y%m%d-%H%M%S.vcv')); shutil.copy2(PATCH, bk); print('backup', bk)
json.dump(p, open(pj, 'w', encoding='utf-8'), ensure_ascii=False)
names_in = [n for n in os.listdir(w_dir)]
subprocess.run([TAR, '--zstd', '-cf', PATCH, '-C', w_dir] + names_in, check=True)
json.dump(cfg, open(SONGF, 'w'), indent=1)
chk = tempfile.mkdtemp(); subprocess.run([TAR, '-xf', PATCH, '-C', chk], check=True)               # read back
q = {m['id']: m for m in json.load(open(os.path.join(chk, 'patch.json'), encoding='utf-8'))['modules']}
for s in cfg['songs']:
    d = q[s['deck']]; print('read back', s['name'], '| title', d['data'].get('title'), '| root', [x['value'] for x in d['params'] if x['id'] == 2], '| slots', [os.path.basename(x['path']) for x in d['data']['slots']])
print('modules', len(q), '| songs.json', [s['name'] for s in cfg['songs']])
