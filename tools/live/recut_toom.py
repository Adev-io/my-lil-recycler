# Re-cut toom-crate (Time Out Of Mind) with every loop start on the record's kick: fixed grid (124.425 BPM, first downbeat
# 1.1549 s) + per-loop circular-mean kick offset, as recut_lowdown.py. Same file names; cache re-pinned (key A, 8 bars).
import os, re, glob, json, numpy as np, librosa, soundfile as sf
SRC = r"C:\Users\Arikl\Music\Library\Stems-Loops\thumb-D-LangModels\_Archive-2026-08-16\uvr-loops\Time Out Of Mind\_full stems\source_(%s)_%s.wav"
CR = r'C:\Users\Arikl\Desktop\uvr-loops\crates\toom-crate'; LIB = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\MyLilRecycler\library.json')
T = 0.48222; D0 = 0.1905 + 2 * T; LOOP = 32 * T
STEMS = [('drums', 'Drums'), ('bass', 'Bass'), ('guitar', 'Guitar'), ('piano', 'Piano'), ('other', 'Other'), ('vocals', 'Vocals')]
ROLE = {'drums': [1, 0, 0, 0], 'bass': [0, 1, 0, 0], 'other': [0, 0, .5, .5]}
old = {int(re.search(r'-(\d\d)_', f).group(1)): re.search(r'_(\w+)-124', f).group(1) for f in glob.glob(os.path.join(CR, '1-drums-*.wav'))}   # keep section names
sr = 22050; y, _ = librosa.load(SRC % ('Drums', 'BS-Roformer-SW'), sr=sr, mono=True)
kick = librosa.onset.onset_detect(y=librosa.effects.preemphasis(y, coef=-0.97), sr=sr, units='time', hop_length=64, delta=0.2, backtrack=False)
starts = [D0 + k * LOOP for k in range(17)]
def off(a, b):
    beat = (b - a) / 32; ks = kick[(kick >= a - beat / 2) & (kick < b - beat / 2)]
    if len(ks) < 8: return 0.0
    pos = (ks - a) / beat; return float(np.angle(np.mean(np.exp(2j * np.pi * (pos % 1)))) / (2 * np.pi) * beat)
new = [starts[k] + (off(starts[k], starts[k + 1]) if k + 1 < len(starts) else off(starts[k - 1], starts[k])) for k in range(len(starts))]
print('boundary moves (ms):', [round((n - s) * 1000) for n, s in zip(new, starts)])
for f in glob.glob(os.path.join(CR, '*.wav')): os.remove(f)
lib = [e for e in json.load(open(LIB, encoding='utf-8')) if '/toom-crate/' not in e['path']]
made = skipped = 0
for si, (stem, tag) in enumerate(STEMS, 1):
    ys, fs = sf.read(SRC % (tag, 'mel_band_roformer' if tag == 'Vocals' else 'BS-Roformer-SW'), always_2d=True)
    fade = int(0.003 * fs); ramp = np.linspace(0, 1, fade)[:, None]
    for k in range(len(new) - 1):
        a, b = int(round(new[k] * fs)), int(round(new[k + 1] * fs))
        if b > len(ys): break
        seg = ys[a:b].copy()
        if 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12) < -45: skipped += 1; continue
        seg[:fade] *= ramp; seg[-fade:] *= ramp[::-1]
        p = os.path.join(CR, f'{si}-{stem}-{k + 1:02d}_{old.get(k + 1, "x")}-124bpm.wav'); sf.write(p, seg, fs, subtype='PCM_16'); made += 1
        st = os.stat(p); secs = len(seg) / fs
        lib.append(dict(path=p.replace('\\', '/'), size=st.st_size, mtime=int(st.st_mtime), sampleRate=fs, frames=len(seg), seconds=secs, tempo=round(1920.0 / secs, 3),
                        tempoConf=1.0, bars=8, key=9, minor=False, keyConf=1.0, onsets=[], bestOnset=0.0, role=[float(x) for x in ROLE.get(stem, [0, 0, 1, 0])],
                        rms=float(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12)), peak=float(20 * np.log10(np.abs(seg).max() + 1e-12))))
json.dump(lib, open(LIB, 'w', encoding='utf-8'), ensure_ascii=False)
print('files', made, 'skipped (silent)', skipped, '| cache entries', sum('/toom-crate/' in e['path'] for e in lib))
