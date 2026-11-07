# Vocal pads for the live set: 4-bar cuts and roll builds from the TOOM (toom-crate, 124 BPM) and Lowdown (lowdown2-crate,
# 115 BPM) vocal stems, written to crates\vocal-cuts (NOT a deck folder: the decks scan only their own crate folders) and
# pinned in the Recycler cache like chop.py (bars 4, tempo 960/seconds, key A major, keyConf 1, bestOnset 0, role melody).
#
# Grid: every cut uses the SOURCE LOOP's own grid (loop frames / 8 per bar), not the nominal BPM. The crate loops are cut
# kick-to-kick and pinned at 1920 / their length, so their real grid drifts from 124 / 115 (TOOM 02 = 123.53, Lowdown 02 =
# 114.04); a 4-bar cut must be exactly half its loop (as chop.py) or the Recycler stretches it to a different tempo.
#   half cut  = loop bars 1-4 or 5-8, phrase in place, 5 ms edge fades.
#   roll      = a word repeated on the grid, one hit count per bar: its VOWEL onset (< 1.5 kHz rise) sits on the grid line, its
#               consonant (the 140 ms "S" of "Son", the "T" of "Time") as pre-roll before it, at most a quarter of the grid unit
#               (min 5 ms), so denser bars keep less consonant. Each hit ends at the next hit's pre-roll or the word end; 5 ms
#               fades. A pad lands at the next loop start, so build then line = a 4-bar run-up.
# Any output peaking above -1 dBFS is scaled to -1 dBFS (the Recycler normalises loops anyway; this only stops clipping).
# Re-runnable: overwrites its own outputs, replaces its own cache entries, backs up library.json first. Never touches crate files.
# usage: py -3.11 vocal_cuts.py [--check] [--png DIR]   (--check = verify the existing outputs only; --png = waveform plots)
import os, re, sys, json, time, shutil, numpy as np, soundfile as sf, librosa
from scipy.signal import butter, sosfilt
CR = r'C:\Users\Arikl\Desktop\uvr-loops\crates'; OUT = os.path.join(CR, 'vocal-cuts')
TOOM = lambda n: os.path.join(CR, 'toom-crate', f'6-vocals-{n}-124bpm.wav')
LOW = lambda n: os.path.join(CR, 'lowdown2-crate', f'6-vocals-{n}-115bpm.wav')
LIB = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\MyLilRecycler\library.json')
FADE, PRE, CEIL = 0.005, 0.005, 10 ** (-1 / 20)
# word = (onset hint s, word end s) inside the source loop; the hint snaps to the nearest backtracked onset within 60 ms
# (word_at). Ends read off the 20 ms envelope (the dip before the next word).
SON, TIME, BABYS, HEY, HEYBOY = (2.27, 2.70), (10.13, 10.68), (8.63, 8.895), (8.25, 8.775), (8.25, 9.19)
CUTS = [   # (output name, source, kind, spec); roll spec = [(hits in the bar, word)] for bars 1-4
    ('6-vocals-02_first-124bpm-chop4.wav',  TOOM('02_verse'),  'half', 0),    # "Son, you better be ready for love"
    ('6-vocals-02_build-124bpm-chop4.wav',  TOOM('02_verse'),  'roll', [(4, SON), (8, SON), (16, SON), (32, SON)]),
    ('6-vocals-04_time-124bpm-chop4.wav',   TOOM('04_chorus'), 'roll', [(4, TIME), (4, TIME), (8, TIME), (16, TIME)]),
    ('6-vocals-02_verse-115bpm-chop4.wav',  LOW('02'),         'half', 1),    # "Baby's into running around ... talking out loud"
    ('6-vocals-02_build-115bpm-chop4.wav',  LOW('02'),         'roll', [(4, BABYS), (8, BABYS), (16, BABYS), (32, BABYS)]),
    ('6-vocals-03_heyboy-115bpm-chop4.wav', LOW('03'),         'roll', [(2, HEYBOY), (2, HEYBOY), (8, HEY), (16, HEY)]),
]

def rise(x, sr, a, b, db):       # first sample in x[a:b] whose 1 ms RMS gets within db of that span's maximum
    h = max(1, int(0.001 * sr)); env = np.sqrt(np.convolve(x[a:b] ** 2, np.ones(h) / h, 'same'))
    return a + int(np.argmax(env > env.max() * 10 ** (-db / 20)))

def lowband(m, sr): return sosfilt(butter(4, 1500, 'low', fs=sr, output='sos'), m)

def word_at(m, sr, hint):        # (consonant start, vowel onset) in samples. The vowel (< 1.5 kHz rise) is the beat the ear hears;
    on = librosa.onset.onset_detect(y=m.astype(np.float32), sr=sr, units='samples', hop_length=128, backtrack=True)   # "Son" has
    near = on[np.abs(on - hint * sr) < 0.06 * sr]                                                              # a 140 ms "S"
    t = int(near[np.argmin(np.abs(near - hint * sr))]) if len(near) else int(hint * sr)
    c = rise(m, sr, max(0, t - int(0.02 * sr)), t + int(0.08 * sr), 20)
    return c, rise(lowband(m, sr), sr, c, c + int(0.25 * sr), 12)

def faded(seg, sr):
    seg = seg.copy(); n = min(int(FADE * sr), len(seg) // 2); r = np.linspace(0, 1, n)[:, None]
    seg[:n] *= r; seg[-n:] *= r[::-1]; return seg

def cut(src, kind, spec):
    y, sr = sf.read(src, always_2d=True); n4 = len(y) // 2; hits = []
    if kind == 'half':
        return faded(y[spec * n4:(spec + 1) * n4], sr), sr, hits
    out = np.zeros((n4, y.shape[1])); bar = n4 / 4; m = y.mean(1); plan = []
    for b, (k, (hint, end)) in enumerate(spec):   # one hit per grid line: (grid sample, consonant pre-roll, vowel, word end)
        c, v = word_at(m, sr, hint); unit = bar / k
        for i in range(k):
            g = int(round(b * bar + i * unit))
            plan.append((g, 0 if g == 0 else max(int(PRE * sr), min(v - c, int(unit / 4))), v, int(round(end * sr))))
    plan.append((n4, 0, 0, 0))
    for (g, pre, v, e), (g2, pre2, _, _) in zip(plan, plan[1:]):
        L = min(g2 - pre2, g + e - v) - (g - pre)   # vowel on the grid line, consonant (<= a quarter unit) before it; ends at
        out[g - pre:g - pre + L] = faded(y[v - pre:v - pre + L], sr); hits.append((g, pre))   # the next hit's pre-roll or word end
    return out, sr, hits

def pin(lib, path, seg, sr):
    st = os.stat(path); secs = len(seg) / sr
    lib.append(dict(path=path.replace('\\', '/'), size=st.st_size, mtime=int(st.st_mtime), sampleRate=sr, frames=len(seg), seconds=secs,
                    tempo=round(960.0 / secs, 3), tempoConf=1.0, bars=4, key=9, minor=False, keyConf=1.0, onsets=[], bestOnset=0.0,
                    role=[0.0, 0.0, 1.0, 0.0], rms=float(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12)),
                    peak=float(20 * np.log10(np.abs(seg).max() + 1e-12))))

def make():
    os.makedirs(OUT, exist_ok=True); made = []
    for name, src, kind, spec in CUTS:
        seg, sr, hits = cut(src, kind, spec); pk = np.abs(seg).max(); g = CEIL / pk if pk > CEIL else 1.0
        dst = os.path.join(OUT, name); sf.write(dst, seg * g, sr, subtype=sf.info(src).subtype); made.append((dst, sr))
        print(f'wrote {name}: {len(seg)} frames, gain {20 * np.log10(g):+.2f} dB')
    bak = LIB + time.strftime('.bak-pre-vocalcuts-%Y%m%d-%H%M%S'); shutil.copy2(LIB, bak); print('backup', bak)
    new = {d.replace('\\', '/') for d, _ in made}
    lib = [e for e in json.load(open(LIB, encoding='utf-8')) if e['path'] not in new]
    for dst, sr in made: pin(lib, dst, sf.read(dst, always_2d=True)[0], sr)   # pin what is on disk (16-bit, after gain)
    with open(LIB + '.vc.tmp', 'w', encoding='utf-8') as f: json.dump(lib, f, ensure_ascii=False)
    os.replace(LIB + '.vc.tmp', LIB)

def check(png=None):
    lib = {e['path']: e for e in json.load(open(LIB, encoding='utf-8'))}
    src_ = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'maps.py'), encoding='utf-8').read()
    ns = {'os': os, 're': re}; exec(re.search(r'def pad_labels.*?(?=\n\S)', src_, re.S).group(0), ns)   # maps.pad_labels, verbatim
    ok = True
    for name, src, kind, spec in CUTS:
        dst = os.path.join(OUT, name); y, sr = sf.read(dst, always_2d=True); ys = sf.read(src, always_2d=True)[0]
        want = len(ys) / 2; bpm = 240 * 4 / (len(y) / sr); m = y.mean(1)
        pk = 20 * np.log10(np.abs(y).max()); dc = float(np.abs(y.mean(0)).max())
        on = librosa.onset.onset_detect(y=m.astype(np.float32), sr=sr, units='samples', hop_length=128, backtrack=True)
        if kind == 'roll':
            hp = cut(src, kind, spec)[2]; exp = [g for g, _ in hp]; units = []; lo = lowband(m, sr)
            for b, (k, _) in enumerate(spec): units += [len(y) / 4 / k] * k
            # (1) librosa onset_detect (backtracked) nearest each grid line, per-bar median and max: it reads the consonant
            # pre-roll and the fade dips too, so it scatters on abutting repeats; (2) the vowel (< 1.5 kHz) rise of each hit
            per, lib_max, n_found = [], 0.0, 0
            for b, (k, _) in enumerate(spec):
                i0 = sum(kk for kk, _ in spec[:b]); d = [int(min(on - e, key=abs)) for e in exp[i0:i0 + k] if len(on)]
                d = [x for x in d if abs(x) < units[i0] / 2]; n_found += len(d)
                per.append(f'{np.median(d) / sr * 1000:+.0f}' if d else 'n/a'); lib_max = max([lib_max] + [abs(x) / sr * 1000 for x in d])
            vow = [rise(lo, sr, e - p, e + int(min(u, 0.25 * sr)), 12) - e for (e, p), u in zip(hp, units)]   # from the hit's own start
            dev = [max(vow, key=abs)]
            found = (f'librosa {n_found}/{len(exp)} hits, per-bar median {"/".join(per)} ms, max {lib_max:.1f} ms; '
                     f'vowel rise vs grid {min(vow) / sr * 1000:+.1f}..{max(vow) / sr * 1000:+.1f} ms')
        else:   # the phrase stays where it was: the chop is the source half sample for sample (fades aside) at lag 0
            a = spec * (len(ys) // 2); n = int(FADE * sr); best = min(range(-2, 3), key=lambda l: np.abs(y[n + 2:-n - 2] - ys[a + n + 2 + l:a + len(y) - n - 2 + l]).max())
            dev = [best]; found = f'{len(on)} detected, lag {best} samples vs source, max diff {np.abs(y[n:-n] - ys[a + n:a + len(y) - n]).max():.1e}'
        mx = max((abs(d) for d in dev), default=0) / sr * 1000
        e = lib.get(dst.replace('\\', '/')); st = os.stat(dst)
        pinned = bool(e) and e['size'] == st.st_size and e['mtime'] == int(st.st_mtime) and e['bars'] == 4 and abs(e['tempo'] - round(bpm, 3)) < 1e-6
        good = abs(len(y) - want) <= 1 and pk < -0.5 and dc < 1e-3 and pinned; ok &= good
        print(f'{"OK " if good else "BAD"} {name}  label "{ns["pad_labels"]([dst])[0]}"  {len(y)} frames (want {want}) = {len(y) / sr:.4f} s, '
              f'4 bars at {bpm:.3f}  peak {pk:.2f} dBFS  dc {dc:.1e}  onsets {found}, max dev {mx:.1f} ms  pinned {pinned}')
        if png:   # PIL waveform (matplotlib is not installed): red = bar, orange = beat, grey = 16th, green tick = detected onset
            from PIL import Image, ImageDraw
            W, H = 1600, 260; im = Image.new('RGB', (W, H + 20), 'white'); d = ImageDraw.Draw(im); x = lambda s: int(s / len(y) * (W - 1))
            for j in range(65): d.line([(x(j * len(y) / 64), 0), (x(j * len(y) / 64), H)], fill=(220, 0, 0) if j % 16 == 0 else (230, 150, 0) if j % 4 == 0 else (225, 225, 225), width=2 if j % 16 == 0 else 1)
            for c in range(W):
                s = m[c * len(m) // W:(c + 1) * len(m) // W]; d.line([(c, H / 2 - s.max() * H / 2), (c, H / 2 - s.min() * H / 2)], fill=(40, 50, 90))
            for o in on: d.line([(x(o), H), (x(o), H + 18)], fill=(0, 150, 0), width=2)
            d.text((4, 2), name, fill=(0, 0, 0)); im.save(os.path.join(png, name.replace('.wav', '.png')))
    print('ALL OK' if ok else 'FAILURES'); return ok

if __name__ == '__main__':
    png = sys.argv[sys.argv.index('--png') + 1] if '--png' in sys.argv else None
    if '--check' not in sys.argv: make()
    sys.exit(0 if check(png) else 1)
