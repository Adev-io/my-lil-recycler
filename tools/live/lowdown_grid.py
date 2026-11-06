# Is Lowdown steady? Fit the drum stem's beats to a straight line; compare each lowdown2 loop's length with 8 bars on that line.
import os, re, sys, glob, numpy as np, soundfile as sf
sys.path.insert(0, r"C:\Users\Arikl\dev\mcp-servers\my-lil-uvr-mcp")
from uvrcore import analysis
DR = r"C:\Users\Arikl\Music\Library\Stems-Loops\laptop\Desktop\Converted for ep133\stemmed and split\Lowdown (2023 Remaster)\_full stems\Lowdown (2023 Remaster)_(Drums)_BS-Roformer-SW.wav"
CR = r'C:\Users\Arikl\Desktop\uvr-loops\crates\lowdown2-crate'
bt = np.array(analysis.analyze(DR)['beats'])
med = np.median(np.diff(bt)); idx = np.concatenate([[0], np.cumsum(np.round(np.diff(bt) / med))]).astype(int)
T, b0 = np.polyfit(idx, bt, 1); res = bt - (b0 + T * idx); h = len(bt) // 2
halves = [60 / np.polyfit(idx[s], bt[s], 1)[0] for s in (slice(0, h), slice(h, None))]
print(f'drum stem: {60 / T:.3f} BPM (halves {halves[0]:.2f} / {halves[1]:.2f}), beat residual median {np.median(abs(res)) * 1000:.0f} ms, max {abs(res).max() * 1000:.0f} ms, {len(bt)} beats')
print(f'8 bars on the line = {32 * T:.3f} s')
for f in sorted(glob.glob(os.path.join(CR, '4-piano-*-115bpm.wav'))):
    nn = re.search(r'-(\d\d)-', f).group(1); d = sf.info(f).duration
    print(f'  loop {nn}: {d:6.3f} s = {d / (4 * T):5.2f} bars  ({1920 / d:6.2f} BPM)  off by {(d - 32 * T) / T:+5.2f} beats')
