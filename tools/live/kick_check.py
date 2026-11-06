# Where does the record's kick fall inside each lowdown2 loop? Rebuild the loop starts the way mkcrates.py did, then measure
# the kick onsets (drum stem, low band) against each loop's own 32-beat grid: mean offset in ms and which beat the kick lands on.
import os, sys, json, numpy as np, librosa, soundfile as sf
sys.path.insert(0, r"C:\Users\Arikl\dev\mcp-servers\my-lil-uvr-mcp")
from uvrcore import analysis
here = os.path.dirname(os.path.abspath(__file__))
DR = r"C:\Users\Arikl\Music\Library\Stems-Loops\laptop\Desktop\Converted for ep133\stemmed and split\Lowdown (2023 Remaster)\_full stems\Lowdown (2023 Remaster)_(Drums)_BS-Roformer-SW.wav"
P = json.load(open(os.path.join(here, 'crates_meta.json')))['lowdown2']['phase']
bt = np.array(analysis.analyze(DR)['beats']); med = float(np.median(np.diff(bt))); fx = [bt[0]]
for b in bt[1:]:
    g = b - fx[-1]; n = int(round(g / med))
    if n >= 1: fx += [fx[-1] + g * j / n for j in range(1, n + 1)]
bt = np.array(fx)
sr = 22050; y, _ = librosa.load(DR, sr=sr, mono=True)
oe = librosa.onset.onset_strength(y=y, sr=sr, hop_length=64); t = librosa.frames_to_time(np.arange(len(oe)), sr=sr, hop_length=64)
def snap(x):
    lo, hi = np.searchsorted(t, x - 0.03), np.searchsorted(t, x + 0.03)
    return float(t[lo + int(np.argmax(oe[lo:hi]))]) if hi > lo else float(x)
starts = [snap(bt[i]) for i in range(P, len(bt), 32)]
# kick onsets: low band
yk = librosa.effects.preemphasis(y, coef=-0.97)        # tilt toward lows
kick = librosa.onset.onset_detect(y=yk, sr=sr, units='time', hop_length=64, delta=0.2, backtrack=False)
json.dump({'starts': starts}, open(os.path.join(here, 'lowdown2_starts.json'), 'w'))
print(f'{len(starts) - 1} loops; kick onsets {len(kick)}')
for k in range(len(starts) - 1):
    a, b = starts[k], starts[k + 1]; beat = (b - a) / 32
    ks = kick[(kick >= a - beat / 2) & (kick < b - beat / 2)]
    if len(ks) < 8: print(f'  loop {k + 1:02d}: few kicks ({len(ks)})'); continue
    pos = (ks - a) / beat; frac = pos - np.round(pos)            # offset from the nearest beat, in beats
    ang = np.angle(np.mean(np.exp(2j * np.pi * (pos % 1)))) / (2 * np.pi)   # circular mean of the sub-beat phase
    which = np.bincount((np.round(pos).astype(int) % 4), minlength=4)
    print(f'  loop {k + 1:02d}: start {a:7.3f} s, kick off-beat {ang * beat * 1000:+5.0f} ms, |spread| {np.median(abs(frac)) * beat * 1000:3.0f} ms, kicks per beat-slot {which.tolist()}')
