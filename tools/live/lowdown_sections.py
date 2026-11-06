# Section names for lowdown2-crate: the old crate's sections (contiguous, named) placed onto the new 8-bar grid.
# The old crate came from a different master, so its offset is found by cross-correlating its first piano section with the new piano stem.
import os, re, sys, json, glob, numpy as np, librosa, soundfile as sf
sys.path.insert(0, r"C:\Users\Arikl\dev\mcp-servers\my-lil-uvr-mcp")
from uvrcore import analysis
here = os.path.dirname(os.path.abspath(__file__))
OLD = r'C:\Users\Arikl\Desktop\uvr-loops\crates\lowdown-crate'; NEW = r'C:\Users\Arikl\Desktop\uvr-loops\crates\lowdown2-crate'
Q = r'C:\Users\Arikl\Desktop\uvr-loops\crates\_quiet\lowdown-crate'
SRC = r"C:\Users\Arikl\Music\Library\Stems-Loops\laptop\Desktop\Converted for ep133\stemmed and split\Lowdown (2023 Remaster)\_full stems\Lowdown (2023 Remaster)_(%s)_BS-Roformer-SW.wav"
# old sections in order (files may have been moved to _quiet): name + length
old = {}
for d in (OLD, Q):
    for f in glob.glob(os.path.join(d, '1-piano-*.wav')):
        n, sec = re.search(r'-(\d\d)_(\w+)\.wav', f).groups(); old[int(n)] = (sec, sf.info(f).duration, f)
starts, t = {}, 0.0
for n in sorted(old): starts[n] = t; t += old[n][1]
# offset old -> new via the first piano section vs the new piano stem
sr = 11025
a, _ = librosa.load(old[1][2], sr=sr, mono=True); b, _ = librosa.load(SRC % 'Piano', sr=sr, mono=True, duration=60)
ea = librosa.feature.rms(y=a, hop_length=128)[0]; eb = librosa.feature.rms(y=b, hop_length=128)[0]
ea -= ea.mean(); eb -= eb.mean()
xc = np.correlate(eb, ea, mode='valid'); off = float(np.argmax(xc) * 128 / sr)
print(f'old crate starts {off:.2f} s into the new master (corr peak {xc.max() / (np.linalg.norm(ea) * np.linalg.norm(eb[np.argmax(xc):np.argmax(xc) + len(ea)]) + 1e-9):.2f})')
# new grid: repaired beats, phase from crates_meta
meta = json.load(open(os.path.join(here, 'crates_meta.json')))['lowdown2']
bt = np.array(analysis.analyze(SRC % 'Drums')['beats']); med = float(np.median(np.diff(bt))); fx = [bt[0]]
for x in bt[1:]:
    g = x - fx[-1]; k = int(round(g / med))
    if k >= 1: fx += [fx[-1] + g * j / k for j in range(1, k + 1)]
bt = np.array(fx); loops = bt[meta['phase']::32]
def label(a, b):
    ov = {}
    for n in sorted(old):
        s = starts[n] + off; e = s + old[n][1]; ov[old[n][0]] = ov.get(old[n][0], 0) + max(0.0, min(b, e) - max(a, s))
    return max(ov, key=ov.get)
secs = {f'{k + 1:02d}': label(loops[k], loops[k + 1]) for k in range(len(loops) - 1)}
cj = json.load(open(os.path.join(NEW, 'crate.json'))); cj['sections'] = secs
json.dump(cj, open(os.path.join(NEW, 'crate.json'), 'w'), indent=1)
print('loop:', ' '.join(f'{k}={v}' for k, v in secs.items()))
present = sorted({int(re.search(r'-(\d\d)-', f).group(1)) for f in os.listdir(NEW) if f.endswith('.wav')})
print('loops with files:', present)
