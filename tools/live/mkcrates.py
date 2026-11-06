# Cut 8-bar crates on each song's tracked beats (as wafb_crate.py): bar phase from snare backbeat + bass changes, every cut
# snapped to the nearest drum onset (30 ms). Writes crates\<slug>-crate\<i>-<stem>-NN-<bpm>bpm.wav and crates_meta.json.
import os, sys, glob, json, numpy as np, librosa, soundfile as sf
sys.path.insert(0, r"C:\Users\Arikl\dev\mcp-servers\my-lil-uvr-mcp")
from uvrcore import analysis
here = os.path.dirname(os.path.abspath(__file__))
S = r"C:\Users\Arikl\Music\Library\Stems-Loops"; A8 = S + r"\thumb-D-LangModels\_Archive-2026-08-16"; U5 = A8 + r"\UVR5-UI-outputs"
CR = r"C:\Users\Arikl\Desktop\uvr-loops\crates"
PEG = S + r"\GoogleDrive\Archive\_Music\stems\Steely Dan - Peg (Groovefunkel Remix)"
MW = A8 + r"\uvr-loops\stems\michael-winning\Michael Winning_(%s)_htdemucs_6s.wav"
WEG = U5 + r"\Pet Shop Boys - West End Girls Official Video HD REMASTERED_(%s)_htdemucs_ft.wav"
ATM = A8 + r"\uvr-loops\Arrow Through Me - Scary Pockets\Arrow Through Me - Scary Pockets_(%s)_htdemucs_ft.wav"
TAYB = r"C:\Users\Arikl\Documents\Image-Line\FL Studio\Projects\Project_4\Audio\Bobby McFerrin - Thinking About Your Body (1986) [XD78BWkhn2E]_9_%s.wav"
SONGS = {   # slug: (key 0-11, minor, [(stem, path)])
    'peg': (7, False, [('drums', PEG + r'\01-drums.wav'), ('bass', PEG + r'\02-bass.wav'), ('guitar', PEG + r'\04-guitar.wav'), ('piano', PEG + r'\05-piano.wav'),
                       ('other', PEG + r'\03-other.wav'), ('vocals', PEG + r'\vocals-lead.wav'), ('backing', PEG + r'\vocals-backing.wav')]),
    'winning': (10, False, [(s.lower(), MW % s) for s in ('Drums', 'Bass', 'Guitar', 'Piano', 'Other', 'Vocals')]),
    'westend': (7, False, [(s.lower(), WEG % s) for s in ('Drums', 'Bass', 'Other', 'Vocals')]),
    'arrow': (4, False, [(s.lower(), ATM % s) for s in ('Drums', 'Bass', 'Other', 'Vocals')]),
    'mcferrin': (2, True, [('drums', TAYB % 'drums'), ('bass', TAYB % 'bass'), ('other', TAYB % 'instruments'), ('vocals', TAYB % 'vocals')]),
}
LOW = r"C:\Users\Arikl\Music\Library\Stems-Loops\laptop\Desktop\Converted for ep133\stemmed and split\Lowdown (2023 Remaster)\_full stems\Lowdown (2023 Remaster)_(%s)_%s.wav"
SONGS['lowdown2'] = (9, False, [(s.lower(), LOW % (s, 'mel_band_roformer' if s == 'Vocals' else 'BS-Roformer-SW')) for s in ('Drums', 'Bass', 'Guitar', 'Piano', 'Other', 'Vocals')])
only = sys.argv[1:] or list(SONGS)
meta = json.load(open(os.path.join(here, 'crates_meta.json'))) if os.path.exists(os.path.join(here, 'crates_meta.json')) else {}
sr = 22050
for slug in only:
    key, minor, stems = SONGS[slug]
    for _, p in stems: assert os.path.exists(p), p
    drums = stems[0][1]; bass = [p for s, p in stems if s == 'bass'][0]
    bt = np.array(analysis.analyze(drums)['beats'])
    med = float(np.median(np.diff(bt))); fixed = [bt[0]]
    for b in bt[1:]:                                       # repair the beat list: fill gaps (drumless parts), drop doubles
        gap = b - fixed[-1]; n = int(round(gap / med))
        if n < 1: continue
        fixed += [fixed[-1] + gap * j / n for j in range(1, n + 1)]
    bt = np.array(fixed)
    yd, _ = librosa.load(drums, sr=sr, mono=True)
    oe = librosa.onset.onset_strength(y=librosa.effects.preemphasis(yd, coef=0.95), sr=sr, hop_length=128)
    t = librosa.frames_to_time(np.arange(len(oe)), sr=sr, hop_length=128)
    snare = np.zeros(4)
    for i, b in enumerate(bt): j = np.searchsorted(t, b); snare[i % 4] += oe[max(0, j - 4):j + 5].max()
    yb, _ = librosa.load(bass, sr=sr, mono=True)
    f0, v, _ = librosa.pyin(yb, fmin=40, fmax=330, sr=sr, hop_length=256, frame_length=4096)
    tb = librosa.frames_to_time(np.arange(len(f0)), sr=sr, hop_length=256)
    m = np.where(v, np.round(librosa.hz_to_midi(np.nan_to_num(f0, nan=1))), -1).astype(int)
    per = [np.bincount(m[np.searchsorted(tb, bt[i]):np.searchsorted(tb, bt[i + 1])] + 1, minlength=1).argmax() - 1 for i in range(len(bt) - 1)]
    ch = np.zeros(4)
    for i in range(1, len(per)):
        if per[i] >= 0 and per[i - 1] >= 0 and per[i] % 12 != per[i - 1] % 12: ch[i % 4] += 1
    score = [ch[p] / max(ch.sum(), 1) + (snare[(p + 1) % 4] + snare[(p + 3) % 4] - snare[p] - snare[(p + 2) % 4]) / snare.sum() for p in range(4)]
    P = int(np.argmax(score))
    oe2 = librosa.onset.onset_strength(y=yd, sr=sr, hop_length=64); t2 = librosa.frames_to_time(np.arange(len(oe2)), sr=sr, hop_length=64)
    def snap(x):
        lo, hi = np.searchsorted(t2, x - 0.03), np.searchsorted(t2, x + 0.03)
        return float(t2[lo + int(np.argmax(oe2[lo:hi]))]) if hi > lo else float(x)
    starts = [snap(bt[i]) for i in range(P, len(bt), 32)]
    bpm = int(round(60 / np.median(np.diff(bt))))
    dst = os.path.join(CR, f'{slug}-crate'); assert not os.path.exists(dst) or not os.listdir(dst), dst + ' not empty'
    os.makedirs(dst, exist_ok=True)
    made, skipped, lens = 0, 0, []
    for si, (stem, path) in enumerate(stems, 1):
        y, fs = sf.read(path, always_2d=True); fade = int(0.003 * fs); ramp = np.linspace(0, 1, fade)[:, None]
        for k in range(len(starts) - 1):
            a, b = int(round(starts[k] * fs)), int(round(starts[k + 1] * fs))
            if b > len(y): break
            seg = y[a:b].copy()
            if si == 1: lens.append((b - a) / fs)
            if 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12) < -45: skipped += 1; continue
            seg[:fade] *= ramp; seg[-fade:] *= ramp[::-1]       # ponytail: 3 ms edge fades against loop clicks
            sf.write(os.path.join(dst, f'{si}-{stem}-{k + 1:02d}-{bpm}bpm.wav'), seg, fs, subtype='PCM_16'); made += 1
    L = np.array(lens)
    meta[slug] = dict(crate=dst, key=key, minor=minor, stems=[s for s, _ in stems], bpm=bpm, phase=P, phase_scores=[round(x, 3) for x in score],
                      loops=len(lens), files=made, tempo_range=[round(1920 / L.max(), 2), round(1920 / L.min(), 2)])
    print(slug, meta[slug], 'skipped', skipped, flush=True)
    json.dump(meta, open(os.path.join(here, 'crates_meta.json'), 'w'), indent=1)
