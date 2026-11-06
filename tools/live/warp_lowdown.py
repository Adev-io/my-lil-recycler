# Beat-warp lowdown2-crate: every loop = 32 beat segments, each taken between the record's own kick onsets and resampled to
# exactly 1/32 of the loop, so the loop is locked to a fixed grid like a drum machine. Re-pins the cache, re-makes the chops,
# prints the kick offset per bar for loops 03 and 14 before and after.
import os, sys, json, glob, numpy as np, librosa, soundfile as sf
sys.path.insert(0, r"C:\Users\Arikl\dev\mcp-servers\my-lil-uvr-mcp")
from uvrcore import analysis
here = os.path.dirname(os.path.abspath(__file__))
SRC = r"C:\Users\Arikl\Music\Library\Stems-Loops\laptop\Desktop\Converted for ep133\stemmed and split\Lowdown (2023 Remaster)\_full stems\Lowdown (2023 Remaster)_(%s)_%s.wav"
CR = r'C:\Users\Arikl\Desktop\uvr-loops\crates\lowdown2-crate'; LIB = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\MyLilRecycler\library.json')
STEMS = [('drums', 'Drums'), ('bass', 'Bass'), ('guitar', 'Guitar'), ('piano', 'Piano'), ('other', 'Other'), ('vocals', 'Vocals')]
ROLE = {'drums': [1, 0, 0, 0], 'bass': [0, 1, 0, 0], 'other': [0, 0, .5, .5]}
P = json.load(open(os.path.join(here, 'crates_meta.json')))['lowdown2']['phase']
DRUM = SRC % ('Drums', 'BS-Roformer-SW')
bt = np.array(analysis.analyze(DRUM)['beats']); med = float(np.median(np.diff(bt))); fx = [bt[0]]
for b in bt[1:]:
    g = b - fx[-1]; n = int(round(g / med))
    if n >= 1: fx += [fx[-1] + g * j / n for j in range(1, n + 1)]
bt = np.array(fx)
sr = 22050; y, _ = librosa.load(DRUM, sr=sr, mono=True); yk = librosa.effects.preemphasis(y, coef=-0.97)
kick = librosa.onset.onset_detect(y=yk, sr=sr, units='time', hop_length=64, delta=0.2, backtrack=True)    # onset starts, not peaks
def snapk(x, win=0.07):
    i = np.searchsorted(kick, x); c = [kick[j] for j in (i - 1, i) if 0 <= j < len(kick)]
    return min(c, key=lambda k: abs(k - x)) if c and abs(min(c, key=lambda k: abs(k - x)) - x) <= win else x
beats = np.array([snapk(b) for b in bt]); snapped = int(np.sum(np.abs(beats - bt) > 1e-6))
loops = [beats[P + 32 * k: P + 32 * k + 33] for k in range((len(beats) - P - 1) // 32)]
print(f'{len(loops)} loops; {snapped}/{len(bt)} beats snapped to a kick onset')
def bar_offsets(path):            # kick offset per bar inside a file, against its own fixed grid
    yy, _ = librosa.load(path, sr=sr, mono=True); beat = len(yy) / sr / 32
    ks = librosa.onset.onset_detect(y=librosa.effects.preemphasis(yy, coef=-0.97), sr=sr, units='time', hop_length=64, delta=0.2, backtrack=True)
    out = []
    for bar in range(8):
        k = ks[(ks >= bar * 4 * beat - beat / 2) & (ks < (bar + 1) * 4 * beat - beat / 2)]
        d = (k / beat) - np.round(k / beat); out.append(int(round(np.median(d) * beat * 1000))) if len(k) else out.append(None)
    return out
for nn in ('03', '14'): print(f'before, loop {nn} kick offset per bar (ms):', bar_offsets(os.path.join(CR, f'1-drums-{nn}-115bpm.wav')))
for f in glob.glob(os.path.join(CR, '*.wav')): os.remove(f)
lib = [e for e in json.load(open(LIB, encoding='utf-8')) if '/lowdown2-crate/' not in e['path']]
def pin(path, seg, fs, stem, bars):
    st = os.stat(path); secs = len(seg) / fs
    lib.append(dict(path=path.replace('\\', '/'), size=st.st_size, mtime=int(st.st_mtime), sampleRate=fs, frames=len(seg), seconds=secs,
                    tempo=round(240.0 * bars / secs, 3), tempoConf=1.0, bars=bars, key=9, minor=False, keyConf=1.0, onsets=[], bestOnset=0.0,
                    role=[float(x) for x in ROLE.get(stem, [0, 0, 1, 0])], rms=float(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12)),
                    peak=float(20 * np.log10(np.abs(seg).max() + 1e-12))))
def warp(ys, fs, lb):             # lb = 33 beat times; each beat segment -> exactly n samples
    n = int(round((lb[-1] - lb[0]) * fs / 32)); out = np.zeros((32 * n, ys.shape[1]), dtype=ys.dtype)
    for i in range(32):
        a, b = int(round(lb[i] * fs)), int(round(lb[i + 1] * fs)); seg = ys[a:b]
        xs = np.linspace(0, len(seg) - 1, n)
        for ch in range(ys.shape[1]): out[i * n:(i + 1) * n, ch] = np.interp(xs, np.arange(len(seg)), seg[:, ch])
    return out
made = skipped = 0
for si, (stem, tag) in enumerate(STEMS, 1):
    ys, fs = sf.read(SRC % (tag, 'mel_band_roformer' if tag == 'Vocals' else 'BS-Roformer-SW'), always_2d=True)
    fade = int(0.003 * fs); ramp = np.linspace(0, 1, fade)[:, None]
    for k, lb in enumerate(loops):
        seg = warp(ys, fs, lb)
        if 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12) < -45: skipped += 1; continue
        seg[:fade] *= ramp; seg[-fade:] *= ramp[::-1]
        p = os.path.join(CR, f'{si}-{stem}-{k + 1:02d}-115bpm.wav'); sf.write(p, seg, fs, subtype='PCM_16'); pin(p, seg, fs, stem, 8); made += 1
        if k + 1 == 14 and stem in ('guitar', 'vocals'):
            c = seg[:len(seg) // 2].copy(); c[-fade:] *= ramp[::-1]
            pc = p.replace('.wav', '-chop4.wav'); sf.write(pc, c, fs, subtype='PCM_16'); pin(pc, c, fs, stem, 4)
json.dump(lib, open(LIB, 'w', encoding='utf-8'), ensure_ascii=False)
print('files', made, 'skipped (silent)', skipped)
for nn in ('03', '14'): print(f'after,  loop {nn} kick offset per bar (ms):', bar_offsets(os.path.join(CR, f'1-drums-{nn}-115bpm.wav')))
