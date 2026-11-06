# Tuning offset from monophonic bass (pYIN): deviation of every voiced frame from the nearest equal-tempered note, as a
# circular histogram over -50..+50 cents; the peak is the offset. Run on the original stems and on the current crate bass loops.
import os, glob, sys, numpy as np, librosa
def offset(path, dur=None):
    y, sr = librosa.load(path, sr=22050, mono=True, duration=dur)
    f0, v, _ = librosa.pyin(y, fmin=35, fmax=400, sr=sr, hop_length=256, frame_length=2048)
    m = librosa.hz_to_midi(f0[v]); dev = ((m - np.round(m)) * 100)
    ang = np.angle(np.mean(np.exp(1j * 2 * np.pi * dev / 100))) / (2 * np.pi) * 100     # circular mean, cents
    spread = float(np.median(np.abs(((dev - ang + 50) % 100) - 50)))
    return ang, spread, int(v.sum())
S = r"C:\Users\Arikl\Music\Library\Stems-Loops"
items = [('Lowdown 2023 bass stem', S + r"\laptop\Desktop\Converted for ep133\stemmed and split\Lowdown (2023 Remaster)\_full stems\Lowdown (2023 Remaster)_(Bass)_BS-Roformer-SW.wav"),
         ('TOOM bass stem', S + r"\thumb-D-LangModels\_Archive-2026-08-16\uvr-loops\Time Out Of Mind\_full stems\source_(Bass)_BS-Roformer-SW.wav"),
         ('lowdown2 crate bass 14 (now)', r"C:\Users\Arikl\Desktop\uvr-loops\crates\lowdown2-crate\2-bass-14-115bpm.wav"),
         ('lowdown2 crate bass 05 (now)', r"C:\Users\Arikl\Desktop\uvr-loops\crates\lowdown2-crate\2-bass-05-115bpm.wav"),
         ('toom crate bass 05 (now)', glob.glob(r"C:\Users\Arikl\Desktop\uvr-loops\crates\toom-crate\2-bass-05_*.wav")[0]),
         ('toom crate bass 04 (now)', glob.glob(r"C:\Users\Arikl\Desktop\uvr-loops\crates\toom-crate\2-bass-04_*.wav")[0])]
for name, p in items:
    a, s, n = offset(p, 150 if 'stem' in name else None); print(f'{name:30s} {a:+5.0f} cents  (spread {s:4.0f}, {n} frames)')
