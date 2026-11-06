# 4-bar chop of the chorus vocal (first half of 6-vocals-14) -> lowdown2-crate\6-vocals-14-115bpm-chop4.wav, cache entry bars=4.
import os, json, numpy as np, soundfile as sf, librosa
CR = r'C:\Users\Arikl\Desktop\uvr-loops\crates\lowdown2-crate'; LIB = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\MyLilRecycler\library.json')
src = os.path.join(CR, '6-vocals-14-115bpm.wav'); dst = os.path.join(CR, '6-vocals-14-115bpm-chop4.wav')
y, sr = sf.read(src, always_2d=True); half = len(y) // 2
# which half is choppier: vocal onsets per bar
m = y.mean(1); on = librosa.onset.onset_detect(y=m.astype(np.float32), sr=sr, units='samples', hop_length=256)
bar = len(y) / 8; per_bar = [int(((on >= k * bar) & (on < (k + 1) * bar)).sum()) for k in range(8)]
print('vocal onsets per bar (loop 14):', per_bar, '| first half', sum(per_bar[:4]), 'second half', sum(per_bar[4:]))
seg = y[:half].copy(); fade = int(0.003 * sr); ramp = np.linspace(0, 1, fade)[:, None]; seg[:fade] *= ramp; seg[-fade:] *= ramp[::-1]
sf.write(dst, seg, sr, subtype='PCM_16')
lib = json.load(open(LIB, encoding='utf-8')); lib = [e for e in lib if e['path'] != dst.replace('\\', '/')]
st = os.stat(dst); secs = len(seg) / sr
lib.append(dict(path=dst.replace('\\', '/'), size=st.st_size, mtime=int(st.st_mtime), sampleRate=sr, frames=len(seg), seconds=secs, tempo=round(960.0 / secs, 3),
                tempoConf=1.0, bars=4, key=9, minor=False, keyConf=1.0, onsets=[], bestOnset=0.0, role=[0.0, 0.0, 1.0, 0.0],
                rms=float(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12)), peak=float(20 * np.log10(np.abs(seg).max() + 1e-12))))
json.dump(lib, open(LIB, 'w', encoding='utf-8'), ensure_ascii=False)
print('wrote', os.path.basename(dst), f'{secs:.2f} s = 4 bars at {960 / secs:.1f} BPM; cache entry added')
