# Section 1 rig: dj-set.vcv = MCP, Mixer, Audio 1 (Yamaha), My lil Drums, Clkd 120, Acid Bass, Recycler A (Lowdown, no drum stem).
# Built offline from live-lowdown-x-toom.vcv (which stays as it is).
import json, os, re, shutil, subprocess, time
here = os.path.dirname(os.path.abspath(__file__))
P = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\patches'); SRC = os.path.join(P, 'live-lowdown-x-toom.vcv'); DST = os.path.join(P, 'dj-set.vcv')
TAR = r'C:\Windows\System32\tar.exe'
KEEP = {6572547854515149: 'Mcp', 5823943341787308: 'Audio1', 2874844741614313: 'Mixer', 7189220493962056: 'Drums', 7081946395008297: 'Clkd', 8333663024495709: 'Acid', 5192219511640844: 'DeckA'}
CR = r'C:\Users\Arikl\Desktop\uvr-loops\crates\lowdown2-crate'
w = os.path.join(here, 'minimal_' + time.strftime('%Y%m%d-%H%M%S')); os.makedirs(w); subprocess.run([TAR, '-xf', SRC, '-C', w], check=True)
p = json.load(open(os.path.join(w, 'patch.json'), encoding='utf-8'))
p['modules'] = [m for m in p['modules'] if m['id'] in KEEP]
p['cables'] = [c for c in p['cables'] if c['outputModuleId'] in KEEP and c['inputModuleId'] in KEEP]
M = {m['id']: m for m in p['modules']}
for m in p['modules']:
    for k in ('leftModuleId', 'rightModuleId'):
        if m.get(k) not in KEEP: m.pop(k, None)
def P_(m, i, v):
    for q in m['params']:
        if q['id'] == i: q['value'] = float(v); return
    m['params'].append({'id': i, 'value': float(v)})
P_(M[7081946395008297], 3, 120)                                   # clock 120
mx = M[2874844741614313]
for i in range(8): P_(mx, i, 0.707 if i < 3 else 0.0)            # strips 1-3 at 0 dB, rest down
for i in range(16, 56): P_(mx, i, 0.0)                            # sends, duck, mutes, solos off
P_(mx, 56, 0.707)
a = M[8333663024495709]
for i, v in ((0, 0), (22, 0), (24, 10), (6, 0.6), (27, 32)): P_(a, i, v)   # tune 0, swing 0, I-B3, volume, 32 steps
d = M[5192219511640844]; files = sorted(f for f in os.listdir(CR) if f.endswith('.wav'))
slots = []
for stem in ('bass', 'piano', 'guitar', 'vocals'):
    c = [f for f in files if re.match(rf'\d-{stem}-\d\d', f)]
    slots.append(CR.replace('\\', '/') + '/' + min(c, key=lambda f: abs(int(re.search(r'-(\d\d)-', f).group(1)) - 3)))
d['data'].update(folder=CR, title='Boz Down', bars=8, chaos=0.0, deck=True, run=True, root=9, minor=False,
                 slots=[{'path': s, 'locked': False, 'level': 0.8, 'k': 0, 's': 0} for s in slots])
for i, v in ((1, 120), (2, 9), (3, 0), (4, 3), (19, 0), (14, 0.8), (15, 0.8), (16, 0.8), (17, 0.8)): P_(d, i, v)
for i in range(20, 40): P_(d, i, 0.0 if i not in (28, 29, 30, 31) else 0.0)   # per-slot shaping neutral (pan/filter/start/rev/pitch)
json.dump(p, open(os.path.join(w, 'patch.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
subprocess.run([TAR, '--zstd', '-cf', DST, '-C', w, 'patch.json', 'modules'], check=True)
chk = os.path.join(w, 'chk'); os.makedirs(chk); subprocess.run([TAR, '-xf', DST, '-C', chk, 'patch.json'], check=True)
q = json.load(open(os.path.join(chk, 'patch.json'), encoding='utf-8'))
print('dj-set.vcv:', [m['model'] for m in q['modules']], '| cables', len(q['cables']))
print('cables:', [(KEEP[c['outputModuleId']], c['outputId'], KEEP[c['inputModuleId']], c['inputId']) for c in q['cables']])
print('deck A slots:', [os.path.basename(s) for s in slots])
