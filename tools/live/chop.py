# usage: chop.py <stem> <NN> [first|second]  -> lowdown2-crate\<n>-<stem>-NN-115bpm-chop4.wav (4 bars = half the 8-bar loop) + cache entry bars=4
import os, sys, glob, json, numpy as np, soundfile as sf, librosa
CR = r'C:\Users\Arikl\Desktop\uvr-loops\crates\lowdown2-crate'; LIB = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\MyLilRecycler\library.json')
stem, nn = sys.argv[1], sys.argv[2]; half_name = sys.argv[3] if len(sys.argv) > 3 else 'first'
src = glob.glob(os.path.join(CR, f'*-{stem}-{nn}-115bpm.wav'))[0]; dst = src.replace('.wav', '-chop4.wav')
y, sr = sf.read(src, always_2d=True); half = len(y) // 2
on = librosa.onset.onset_detect(y=y.mean(1).astype(np.float32), sr=sr, units='samples', hop_length=256)
bar = len(y) / 8; per_bar = [int(((on >= k * bar) & (on < (k + 1) * bar)).sum()) for k in range(8)]
print(f'{stem} loop {nn} onsets per bar:', per_bar, '| first half', sum(per_bar[:4]), 'second half', sum(per_bar[4:]))
seg = (y[:half] if half_name == 'first' else y[half:2 * half]).copy()
fade = int(0.003 * sr); ramp = np.linspace(0, 1, fade)[:, None]; seg[:fade] *= ramp; seg[-fade:] *= ramp[::-1]
sf.write(dst, seg, sr, subtype='PCM_16')
lib = [e for e in json.load(open(LIB, encoding='utf-8')) if e['path'] != dst.replace('\\', '/')]
st = os.stat(dst); secs = len(seg) / sr
role = {'drums': [1, 0, 0, 0], 'bass': [0, 1, 0, 0]}.get(stem, [0, 0, 1, 0])
lib.append(dict(path=dst.replace('\\', '/'), size=st.st_size, mtime=int(st.st_mtime), sampleRate=sr, frames=len(seg), seconds=secs, tempo=round(960.0 / secs, 3),
                tempoConf=1.0, bars=4, key=9, minor=False, keyConf=1.0, onsets=[], bestOnset=0.0, role=[float(x) for x in role],
                rms=float(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12)), peak=float(20 * np.log10(np.abs(seg).max() + 1e-12))))
json.dump(lib, open(LIB, 'w', encoding='utf-8'), ensure_ascii=False)
print('wrote', os.path.basename(dst), f'({half_name} half, {secs:.2f} s); cache entry added')
