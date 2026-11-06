# usage: audio_swap.py laptop | restore   (Rack must be closed)
# laptop: Audio 1 -> WASAPI "Speakers (Realtek(R) Audio)" 48 kHz, saving the original audio blocks to audio_orig.json first.
# restore: put the saved Yamaha / PreSonus blocks back.
import json, os, sys, shutil, subprocess, time
here = os.path.dirname(os.path.abspath(__file__))
PATCH = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\patches\live-lowdown-x-toom.vcv'); TAR = r'C:\Windows\System32\tar.exe'
A1, A2 = 5823943341787308, 8104319004150697
ts = time.strftime('%Y%m%d-%H%M%S'); shutil.copy2(PATCH, PATCH.replace('.vcv', f'.bak-pre-audio{sys.argv[1]}-{ts}.vcv'))
w = os.path.join(here, f'audio_{sys.argv[1]}_{ts}'); os.makedirs(w); subprocess.run([TAR, '-xf', PATCH, '-C', w], check=True)
p = json.load(open(os.path.join(w, 'patch.json'), encoding='utf-8')); M = {m['id']: m for m in p['modules']}
orig = os.path.join(here, 'audio_orig.json')
if sys.argv[1] == 'laptop':
    if not os.path.exists(orig): json.dump({str(k): M[k]['data']['audio'] for k in (A1, A2)}, open(orig, 'w'), indent=1)
    M[A1]['data']['audio'].update(driver=6, deviceName='Speakers (Realtek(R) Audio)', sampleRate=48000.0, blockSize=512)
else:
    o = json.load(open(orig))
    for k in (A1, A2): M[k]['data']['audio'] = o[str(k)]
json.dump(p, open(os.path.join(w, 'patch.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
new = PATCH + '.new'; subprocess.run([TAR, '--zstd', '-cf', new, '-C', w, 'patch.json', 'modules'], check=True)
c = os.path.join(w, 'chk'); os.makedirs(c); subprocess.run([TAR, '-xf', new, '-C', c, 'patch.json'], check=True)
q = {m['id']: m for m in json.load(open(os.path.join(c, 'patch.json'), encoding='utf-8'))['modules']}
os.replace(new, PATCH)
print('audio now:', [(q[k]['data']['audio']['driver'], q[k]['data']['audio']['deviceName']) for k in (A1, A2)], '| modules', len(q))
