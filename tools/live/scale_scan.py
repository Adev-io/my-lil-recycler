# Read only: bass pitch classes per song crate -> the arp keys for each Launchpad page. py -3.11 scale_scan.py
# Lowdown's bass plays E/A (verse) and F#/B (chorus); TOOM's walk-down is A G F# E D: both read as D major (D E F# G A B C#).
import os, glob, numpy as np, librosa
N = 'C C# D D# E F F# G G# A A# B'.split()
CRATES = {'Lowdown': r'C:\Users\Arikl\Desktop\uvr-loops\crates\lowdown2-crate',
          'Time Out Of Mind': r'C:\Users\Arikl\Desktop\uvr-loops\crates\toom-crate'}
D_MAJOR = (1, 2, 4, 6, 7, 9, 11)
for song, cr in CRATES.items():
    h = np.zeros(12)
    for f in sorted(glob.glob(os.path.join(cr, '*-bass-*.wav'))):
        if 'chop' in f: continue
        y, sr = librosa.load(f, sr=22050, mono=True)
        f0, v, _ = librosa.pyin(y, fmin=40, fmax=330, sr=sr, hop_length=512, frame_length=4096)
        if v.sum() >= 20: h += np.bincount(np.round(librosa.hz_to_midi(f0[v])).astype(int) % 12, minlength=12)
    h = h / h.sum(); top7 = sorted(int(i) for i in np.argsort(h)[::-1][:7])
    print(f"{song}: top 7 {top7} = {[N[i] for i in top7]} | share inside D major {sum(h[i] for i in D_MAJOR):.0%}")
