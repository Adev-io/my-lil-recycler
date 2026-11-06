# Bass pitch classes per lowdown2 loop -> which loops are the E/A vamp (verse) and which carry F#/B (the real chorus).
import os, re, glob, json, numpy as np, librosa
CR = r'C:\Users\Arikl\Desktop\uvr-loops\crates\lowdown2-crate'; N = 'C C# D D# E F F# G G# A A# B'.split()
out = {}
for f in sorted(glob.glob(os.path.join(CR, '2-bass-??-115bpm.wav'))):
    nn = re.search(r'-(\d\d)-', f).group(1); y, sr = librosa.load(f, sr=22050, mono=True)
    f0, v, _ = librosa.pyin(y, fmin=40, fmax=330, sr=sr, hop_length=512, frame_length=4096)
    if v.sum() < 20: out[nn] = ('quiet', []); continue
    pc = np.bincount(np.round(librosa.hz_to_midi(f0[v])).astype(int) % 12, minlength=12); pc = pc / pc.sum()
    top = [(N[i], round(pc[i] * 100)) for i in np.argsort(pc)[::-1][:3]]
    lab = 'chorus' if pc[6] + pc[11] > 0.45 else ('verse' if pc[4] + pc[9] > 0.45 else 'other')
    out[nn] = (lab, top); print(f'loop {nn}: {lab:6s} {top}')
cj = json.load(open(os.path.join(CR, 'crate.json'))); secs = cj.get('sections', {})
for nn, (lab, _) in out.items():
    if lab in ('chorus', 'verse'): secs[nn] = lab
cj['sections'] = secs; json.dump(cj, open(os.path.join(CR, 'crate.json'), 'w'), indent=1)
print('sections now:', ' '.join(f'{k}={v}' for k, v in sorted(secs.items())))
