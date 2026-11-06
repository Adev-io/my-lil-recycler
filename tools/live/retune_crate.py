# Retune a crate to A440: median tuning offset of its piano loops (librosa.estimate_tuning), then resample every WAV by the
# inverse ratio (pitch and length change together, clean), re-pin the cache (tempo from the new length). usage: retune_crate.py <crate>
import os, re, sys, glob, json, numpy as np, soundfile as sf, librosa
CR = sys.argv[1]; LIB = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\MyLilRecycler\library.json')
ROLE = {'drums': [1, 0, 0, 0], 'bass': [0, 1, 0, 0], 'other': [0, 0, .5, .5]}
offs = []
for f in sorted(glob.glob(os.path.join(CR, '*-piano-*.wav'))):
    if 'chop' in f: continue
    y, sr = librosa.load(f, sr=22050, mono=True)
    if np.sqrt(np.mean(y ** 2)) < 1e-3: continue
    offs.append(librosa.estimate_tuning(y=y, sr=sr, bins_per_octave=120) * 100)
cents = float(np.median(offs))
if len(sys.argv) > 2: cents = -float(sys.argv[2]); print('override: shifting by', sys.argv[2], 'cents')   # explicit shift wins
ratio = 2 ** (-cents / 1200)      # multiply pitch by ratio -> back to 440
print(f'{os.path.basename(CR)}: piano loops read {np.round(offs).astype(int).tolist()} -> median {cents:+.0f} cents; shifting by {-cents:+.0f}')
lib = [e for e in json.load(open(LIB, encoding='utf-8')) if '/' + os.path.basename(CR) + '/' not in e['path']]
n = 0
for f in sorted(glob.glob(os.path.join(CR, '*.wav'))):
    y, fs = sf.read(f, always_2d=True)
    out = np.stack([librosa.resample(y[:, c].astype(np.float32), orig_sr=fs, target_sr=fs / ratio, res_type='soxr_hq') for c in range(y.shape[1])], axis=1)
    sf.write(f, out, fs, subtype='PCM_16'); n += 1
    st = os.stat(f); secs = len(out) / fs; bars = 4 if 'chop4' in f else 8
    stem = re.match(r'\d-(\w+?)-', os.path.basename(f)).group(1)
    lib.append(dict(path=f.replace('\\', '/'), size=st.st_size, mtime=int(st.st_mtime), sampleRate=fs, frames=len(out), seconds=secs, tempo=round(240.0 * bars / secs, 3),
                    tempoConf=1.0, bars=bars, key=9, minor=False, keyConf=1.0, onsets=[], bestOnset=0.0, role=[float(x) for x in ROLE.get(stem, [0, 0, 1, 0])],
                    rms=float(20 * np.log10(np.sqrt(np.mean(out ** 2)) + 1e-12)), peak=float(20 * np.log10(np.abs(out).max() + 1e-12))))
json.dump(lib, open(LIB, 'w', encoding='utf-8'), ensure_ascii=False)
chk = []
for f in sorted(glob.glob(os.path.join(CR, '*-piano-*.wav')))[:3]:
    y, sr = librosa.load(f, sr=22050, mono=True); chk.append(round(librosa.estimate_tuning(y=y, sr=sr, bins_per_octave=120) * 100))
print(f'  {n} files resampled; piano loops now read {chk} cents; cache re-pinned (8-bar tempo now ~{240 * 8 / secs:.1f})')
