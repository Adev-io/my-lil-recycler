# Re-cut lowdown2-crate with every loop start moved onto the record's kick (circular-mean kick offset per loop, measured by
# kick_check.py), re-pin the cache, re-make the two 4-bar chops, and verify the new files against their own kick.
import os, re, sys, json, glob, numpy as np, librosa, soundfile as sf
here = os.path.dirname(os.path.abspath(__file__))
SRC = r"C:\Users\Arikl\Music\Library\Stems-Loops\laptop\Desktop\Converted for ep133\stemmed and split\Lowdown (2023 Remaster)\_full stems\Lowdown (2023 Remaster)_(%s)_%s.wav"
CR = r'C:\Users\Arikl\Desktop\uvr-loops\crates\lowdown2-crate'; LIB = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\MyLilRecycler\library.json')
STEMS = [('drums', 'Drums'), ('bass', 'Bass'), ('guitar', 'Guitar'), ('piano', 'Piano'), ('other', 'Other'), ('vocals', 'Vocals')]
ROLE = {'drums': [1, 0, 0, 0], 'bass': [0, 1, 0, 0], 'other': [0, 0, .5, .5]}
starts = json.load(open(os.path.join(here, 'lowdown2_starts.json')))['starts']
sr = 22050; y, _ = librosa.load(SRC % ('Drums', 'BS-Roformer-SW'), sr=sr, mono=True)
kick = librosa.onset.onset_detect(y=librosa.effects.preemphasis(y, coef=-0.97), sr=sr, units='time', hop_length=64, delta=0.2, backtrack=False)
def kick_offset(a, b):
    beat = (b - a) / 32; ks = kick[(kick >= a - beat / 2) & (kick < b - beat / 2)]
    if len(ks) < 8: return 0.0
    pos = (ks - a) / beat; return float(np.angle(np.mean(np.exp(2j * np.pi * (pos % 1)))) / (2 * np.pi) * beat)
# move each boundary by the offset measured on the loop that starts there (the last boundary: by the loop that ends there)
new = []
for k in range(len(starts)):
    a = starts[k]; b = starts[k + 1] if k + 1 < len(starts) else None
    off = kick_offset(a, b) if b else kick_offset(starts[k - 1], a)
    new.append(a + off)
print('boundary moves (ms):', [round((n - s) * 1000) for n, s in zip(new, starts)])
for f in glob.glob(os.path.join(CR, '*.wav')): os.remove(f)
lib = [e for e in json.load(open(LIB, encoding='utf-8')) if '/lowdown2-crate/' not in e['path']]
def pin(path, seg, fs, stem, bars):
    st = os.stat(path); secs = len(seg) / fs
    lib.append(dict(path=path.replace('\\', '/'), size=st.st_size, mtime=int(st.st_mtime), sampleRate=fs, frames=len(seg), seconds=secs,
                    tempo=round(240.0 * bars / secs, 3), tempoConf=1.0, bars=bars, key=9, minor=False, keyConf=1.0, onsets=[], bestOnset=0.0,
                    role=[float(x) for x in ROLE.get(stem, [0, 0, 1, 0])], rms=float(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12)),
                    peak=float(20 * np.log10(np.abs(seg).max() + 1e-12))))
made = skipped = 0
for si, (stem, tag) in enumerate(STEMS, 1):
    ys, fs = sf.read(SRC % (tag, 'mel_band_roformer' if tag == 'Vocals' else 'BS-Roformer-SW'), always_2d=True)
    fade = int(0.003 * fs); ramp = np.linspace(0, 1, fade)[:, None]
    for k in range(len(new) - 1):
        a, b = int(round(new[k] * fs)), int(round(new[k + 1] * fs)); seg = ys[a:b].copy()
        if 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12) < -45: skipped += 1; continue
        seg[:fade] *= ramp; seg[-fade:] *= ramp[::-1]
        p = os.path.join(CR, f'{si}-{stem}-{k + 1:02d}-115bpm.wav'); sf.write(p, seg, fs, subtype='PCM_16'); pin(p, seg, fs, stem, 8); made += 1
        if k + 1 == 14 and stem in ('guitar', 'vocals'):                       # the section-4 chops: first half of loop 14
            h = len(seg) // 2; c = ys[a:a + h].copy(); c[:fade] *= ramp; c[-fade:] *= ramp[::-1]
            pc = p.replace('.wav', '-chop4.wav'); sf.write(pc, c, fs, subtype='PCM_16'); pin(pc, c, fs, stem, 4)
json.dump(lib, open(LIB, 'w', encoding='utf-8'), ensure_ascii=False)
print('files', made, 'skipped (silent)', skipped, '| cache entries for lowdown2:', sum('/lowdown2-crate/' in e['path'] for e in lib))
# verify: kick offset inside each new drum file against its own 32-beat grid
for f in sorted(glob.glob(os.path.join(CR, '1-drums-*-115bpm.wav'))):
    yy, _ = librosa.load(f, sr=sr, mono=True); d = len(yy) / sr; beat = d / 32
    ks = librosa.onset.onset_detect(y=librosa.effects.preemphasis(yy, coef=-0.97), sr=sr, units='time', hop_length=64, delta=0.2, backtrack=False)
    pos = ks / beat; off = np.angle(np.mean(np.exp(2j * np.pi * (pos % 1)))) / (2 * np.pi) * beat * 1000
    print(f'  {os.path.basename(f)}: kick off-beat {off:+4.0f} ms, {d / (4 * beat):.2f} bars')
