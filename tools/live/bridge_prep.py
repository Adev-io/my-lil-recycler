# Prep for the horn bridge into Time Out Of Mind:
# 1. Lowdown 'other' stem per loop: loudness + brightness -> where the horns are.
# 2. TOOM crate per loop: bass pitch classes -> which loops are the A vamp (Acid I-B7) vs the walk-down (I-C1).
import os, re, glob, numpy as np, librosa, soundfile as sf
N = 'C C# D D# E F F# G G# A A# B'.split()
LOW = r'C:\Users\Arikl\Desktop\uvr-loops\crates\lowdown2-crate'; TOOM = r'C:\Users\Arikl\Desktop\uvr-loops\crates\toom-crate'
print('Lowdown other stem (horns/strings) per loop:')
for f in sorted(glob.glob(os.path.join(LOW, '5-other-??-115bpm.wav'))):
    y, sr = sf.read(f, always_2d=True); m = y.mean(1)
    rms = 20 * np.log10(np.sqrt(np.mean(m ** 2)) + 1e-12)
    S = np.abs(librosa.stft(m.astype(np.float32), n_fft=2048)) ** 2; fr = librosa.fft_frequencies(sr=sr, n_fft=2048)
    bright = 10 * np.log10(S[fr > 1500].sum() / (S.sum() + 1e-12) + 1e-12)
    on = len(librosa.onset.onset_detect(y=m.astype(np.float32), sr=sr, delta=0.2))
    nn = re.search(r'-(\d\d)-', f).group(1)
    print(f'  loop {nn}: rms {rms:6.1f} dB, >1.5 kHz share {bright:5.1f} dB, onsets {on:3d}')
print('TOOM bass per loop:')
for f in sorted(glob.glob(os.path.join(TOOM, '2-bass-??_*-124bpm.wav'))):
    y, sr = librosa.load(f, sr=22050, mono=True)
    f0, v, _ = librosa.pyin(y, fmin=40, fmax=330, sr=sr, hop_length=512, frame_length=4096)
    if v.sum() < 20: continue
    pc = np.bincount(np.round(librosa.hz_to_midi(f0[v])).astype(int) % 12, minlength=12); pc = pc / pc.sum()
    top = [(N[i], round(pc[i] * 100)) for i in np.argsort(pc)[::-1][:3]]
    lab = 'vamp A' if pc[9] > 0.4 else ('walk-down' if pc[9] + pc[7] + pc[6] + pc[4] + pc[2] > 0.7 else 'other')
    print(f'  {os.path.basename(f)[:28]:28s} {lab:9s} {top}')
