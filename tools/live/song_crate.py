# Cut any BS-Roformer-SW 6-stem song into 8-bar loops on its kick (generalised from disco_crate.py). Nothing hand-set.
# Method:
#  1. Native tempo: librosa beat_track on the drums stem (raw; octave ambiguity printed).
#  2. Beat grid: kick PLL as disco_crate.py: low-band (30-120 Hz) onset envelope of drums, seeded at its strongest peak in
#     the first 20 s, tracked forward and back; each beat = envelope peak within +-12 % of a period around the prediction,
#     period = median of the last 8 intervals (follows live-band drift). Native T = 60 / median grid interval.
#  3. Multiplier: loops are 32 beats at the playback tempo T*mult. mult auto = {0.5, 1, 2} whichever puts T*mult closest
#     to TARGET (128) on a log scale; --mult overrides. Native beats per loop N = 32/mult (64, 32 or 16), i.e. 16, 8 or 4
#     native bars. Pinned tempo = 1920/len = T*mult; file names carry it; stretch to TARGET printed.
#  4. Bar phase (0-3): mean kick (30-120 Hz), snare (1-5 kHz) and bass-onset peak per grid residue mod 4. Score: kick on
#     beat 1 vs 3, snare on 2 and 4 vs 1 and 3, bass change on 1 vs 3. Snare cannot tell 1 from 3, so kick/bass decide
#     that; a small margin is printed as a warning. --d0 overrides (nearest grid beat).
#  5. Loop phase (0..Bn-1 bars, Bn = 8/mult): per-bar dB RMS of every stem; novelty = summed |change| across stems at each
#     bar line; loop phase = residue with the highest mean novelty (section changes should land on loop lines).
#  6. Loop edges moved onto the kick by each loop's circular-mean kick offset (as disco_crate.py).
#  7. Key: Krumhansl-Schmuckler on the mean chroma of bass+guitar+piano+other (each stem normalised, RMS-weighted).
#     Top 3 printed; shift to D major (or B minor if minor) printed as the nearest semitone move.
#  8. Labels per loop from drums and vocals RMS (see label()); honest heuristic, check the table.
# usage: py -3.11 song_crate.py <stems_dir> <crate_name> "<Title>" "<Artist>" [--dry] [--d0 S] [--mult 0.5|1|2]
#                              [--key K --minor 0|1]          py -3.11 song_crate.py --selftest
import os, re, sys, json, shutil, time, argparse, numpy as np, librosa, soundfile as sf
BASE = r'C:\Users\Arikl\Desktop\uvr-loops'
LIB = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\MyLilRecycler\library.json')
STEMS = ['drums', 'bass', 'guitar', 'piano', 'other', 'vocals']
KEY_STEMS = ['bass', 'guitar', 'piano', 'other']
ROLE = {'drums': [1, 0, 0, 0], 'bass': [0, 1, 0, 0], 'other': [0, 0, .5, .5]}
NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
FLATS = {'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#'}
MAJ = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]   # Krumhansl-Kessler profiles
MIN = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
TARGET = 128.0                            # set clock; Recycler stretches every loop to it
ROOT_MAJ, ROOT_MIN = 2, 11                # every deck root is D major / B minor
SR = 22050; HOP = 64

def estimate_key(c):
    """Krumhansl-Schmuckler: correlate 12-bin chroma with each rotated profile. Best first: [(r, pitch_class, minor)]."""
    out = [(float(np.corrcoef(c, np.roll(P, t))[0, 1]), t, m) for m, P in ((0, MAJ), (1, MIN)) for t in range(12)]
    return sorted(out, reverse=True)

def key_chroma(ys):
    """Chroma per stem (RMS-weighted mean, normalised), averaged over stems."""
    acc = np.zeros(12)
    for y in ys:
        C = librosa.feature.chroma_cqt(y=y, sr=SR, tuning=0)
        w = librosa.feature.rms(y=y)[0]; n = min(C.shape[1], len(w)); C, w = C[:, :n], w[:n]
        m = C @ w / (w.sum() + 1e-9); acc += m / (m.sum() + 1e-9)
    return acc / len(ys)

def selftest():
    t = np.arange(int(2 * SR)) / SR
    prog = [(146.83, 185.00, 220.00), (196.00, 246.94, 293.66), (220.00, 277.18, 329.63), (146.83, 185.00, 220.00)]  # D G A D triads
    y = np.concatenate([sum(0.2 * np.sin(2 * np.pi * f * t) for f in ch) for ch in prog]).astype(np.float32)
    best = estimate_key(key_chroma([y]))[0]
    print(f'selftest: best {NOTES[best[1]]} {"minor" if best[2] else "major"} r={best[0]:+.3f}')
    assert best[1] == 2 and best[2] == 0, 'selftest FAILED: expected D major'
    print('selftest OK: D major wins')

def find_stems(d):
    found = {}
    for f in sorted(os.listdir(d)):
        m = re.search(r'_\((\w+)\)_', f)
        if m and m.group(1) in STEMS and f.lower().endswith('.wav'): found[m.group(1)] = os.path.join(d, f)
    missing = [s for s in STEMS if s not in found]
    assert not missing, f'missing stems {missing} in {d}'
    return found

def pll(lo, tt, seed, d, tend, p0):
    beats, per = [seed], [p0] * 8
    while True:
        p = float(np.median(per[-8:])); x = beats[-1] + d * p
        if (d > 0 and x > tend) or (d < 0 and x < tend): return beats
        a, b = np.searchsorted(tt, x - 0.12 * p), np.searchsorted(tt, x + 0.12 * p)
        j = a + int(np.argmax(lo[a:b])) if b > a else -1
        nx = float(tt[j]) if j >= 0 and lo[j] > 0.12 else x
        per.append(abs(nx - beats[-1])); beats.append(nx)

def label(rows):
    dr = np.array([r[3]['drums'] for r in rows]); vx = np.array([r[3]['vocals'] for r in rows])
    dmed, vmed, n = np.median(dr), np.median(vx), len(rows)
    out = []
    for k in range(n):
        if k == n - 1 and n > 2: out.append('outro')
        elif k == 0 and (dr[k] < -36 or dr[k] < dmed - 6): out.append('intro')
        elif dr[k] < -36 or dr[k] < dmed - 10: out.append('break')
        elif vx[k] > -40 and vx[k] >= vmed: out.append('vox')
        else: out.append('inst')
    return out

def parse_key(s):
    s = s.strip()
    if s.isdigit(): return int(s) % 12
    s = FLATS.get(s[0].upper() + s[1:], s[0].upper() + s[1:])
    if s not in NOTES: raise SystemExit(f'unknown key {s!r}')
    return NOTES.index(s)

def main():
    ap = argparse.ArgumentParser(description='Cut a BS-Roformer-SW 6-stem song into 8-bar kick-locked crate loops.')
    ap.add_argument('stems_dir', nargs='?'); ap.add_argument('crate_name', nargs='?')
    ap.add_argument('title', nargs='?'); ap.add_argument('artist', nargs='?')
    ap.add_argument('--dry', action='store_true', help='print analysis table, write nothing')
    ap.add_argument('--bpm', type=float, help='seed the kick PLL at this native tempo (beat_track picked a wrong period)')
    ap.add_argument('--d0', type=float, help='override first downbeat (seconds)')
    ap.add_argument('--mult', type=float, choices=[0.5, 1.0, 2.0], help='tempo multiplier (default: auto, closest to 128)')
    ap.add_argument('--key', help='tonic override, e.g. D, Eb or 2'); ap.add_argument('--minor', type=int, choices=[0, 1])
    ap.add_argument('--selftest', action='store_true')
    A = ap.parse_args()
    if A.selftest: return selftest()
    if not all([A.stems_dir, A.crate_name, A.title, A.artist]): ap.error('need stems_dir crate_name "Title" "Artist"')

    paths = find_stems(A.stems_dir)
    song = os.path.basename(paths['drums']).split('_(')[0]
    print('stems', len(paths), '| song', song)
    M = {s: librosa.load(paths[s], sr=SR, mono=True)[0] for s in STEMS}
    reads = {s: sf.read(paths[s], dtype='float32', always_2d=True) for s in STEMS}
    Y = {s: reads[s][0] for s in STEMS}; fs = reads['drums'][1]
    assert all(reads[s][1] == fs for s in STEMS), 'stems differ in sample rate'
    yd = M['drums']

    # ---- kick PLL grid (native beats)
    S = np.abs(librosa.stft(yd, n_fft=1024, hop_length=HOP)); fr = librosa.fft_frequencies(sr=SR, n_fft=1024)
    tt = librosa.frames_to_time(np.arange(S.shape[1]), sr=SR, hop_length=HOP)
    def band_onset(band):
        e = np.maximum(0, np.diff(S[band].sum(0), prepend=0)); return e / (e.max() + 1e-12)
    lo = band_onset((fr >= 30) & (fr < 120)); sn = band_onset((fr >= 1000) & (fr < 5000))
    rb = librosa.feature.rms(y=M['bass'], frame_length=1024, hop_length=HOP)[0]
    rb = np.pad(rb, (0, max(0, len(tt) - len(rb))))[:len(tt)]
    bs = np.maximum(0, np.diff(rb, prepend=0)); bs /= bs.max() + 1e-12
    raw = A.bpm or float(np.atleast_1d(librosa.beat.beat_track(y=yd, sr=SR)[0])[0])
    seed = float(tt[int(np.argmax(lo[:np.searchsorted(tt, 20)]))])
    grid = np.array(sorted(set(pll(lo, tt, seed, -1, 0.0, 60 / raw)[1:] + pll(lo, tt, seed, 1, tt[-1] - 0.3, 60 / raw))))
    per = float(np.median(np.diff(grid))); T = 60 / per
    ib = 60 / np.diff(grid); p5, pmed, p95 = np.percentile(ib, [5, 50, 95])
    print(f'native tempo: beat_track raw {raw:.1f} | PLL grid {T:.2f} (interval p5-p95 {p5:.1f}-{p95:.1f}, drift {100 * (p95 - p5) / pmed:.1f}%)')
    octv = [f'{x:.0f}' for x in (raw / 2, raw * 2) if 90 <= x <= 140]
    if octv or not (90 <= raw <= 140): print(f'  OCTAVE RISK: raw {raw:.1f}, half/double {octv or "-"} inside 90-140; check by ear')

    # ---- multiplier: playback tempo T*mult closest to TARGET (log scale)
    mult = A.mult if A.mult is not None else min([0.5, 1.0, 2.0], key=lambda m: abs(np.log(T * m / TARGET)))
    pinned = T * mult; N = int(round(32 / mult)); assert N % 4 == 0, 'mult must give whole bars'
    Bn = N // 4                                       # native bars per loop (16 / 8 / 4)
    stretch = (TARGET / pinned - 1) * 100
    print(f'mult {mult} ({"auto" if A.mult is None else "forced"}): pinned tempo {pinned:.2f}, loop = {N} native beats = {Bn} native bars '
          f'= 8 bars at {pinned:.1f} | stretch to {TARGET:.0f}: {stretch:+.1f}%')

    # ---- bar phase
    def beat_peak(env, t):
        a, b = np.searchsorted(tt, t - .12 * per), np.searchsorted(tt, t + .12 * per)
        return float(env[a:b].max()) if b > a else 0.0
    pos = np.arange(len(grid)) % 4
    def pos_mean(env):
        v = np.array([beat_peak(env, t) for t in grid]); m = np.array([v[pos == j].mean() for j in range(4)]); return m / (m.max() + 1e-12)
    K, Sn, B = pos_mean(lo), pos_mean(sn), pos_mean(bs)
    score = [float((K[p] - K[(p + 2) % 4]) + .5 * (Sn[(p + 1) % 4] + Sn[(p + 3) % 4] - Sn[p] - Sn[(p + 2) % 4]) + .5 * (B[p] - B[(p + 2) % 4])) for p in range(4)]
    print('bar phase per grid residue 0-3: kick', np.round(K, 2), 'snare', np.round(Sn, 2), 'bass', np.round(B, 2))
    srt = sorted(score, reverse=True)
    if A.d0 is not None:
        i_d = int(np.argmin(np.abs(grid - A.d0))); p = i_d % 4; D0 = float(grid[i_d])
        why = f'--d0 {A.d0} -> grid beat {D0:.3f}s'
    else:
        p = int(np.argmax(score)); D0 = float(grid[p])
        why = f'max score {srt[0]:.2f}, next {srt[1]:.2f}'
        if srt[0] - srt[1] < 0.2: why += '  WARNING: ambiguous 1 vs 3, check with --d0'
    print('bar scores', [round(x, 2) for x in score], '| bar phase', p, '|', why, f'| D0 {D0:.3f}s')

    # ---- loop phase (bar lines with the biggest summed stem change)
    nb = (len(grid) - 1 - p) // 4
    def db(x): return float(20 * np.log10(np.sqrt(np.mean(x.astype(np.float64) ** 2)) + 1e-12))
    def seg(s, t0, t1): return Y[s][int(round(t0 * fs)):int(round(t1 * fs))]
    F = np.array([[max(db(seg(s, grid[p + 4 * b], grid[p + 4 * b + 4])), -70) for s in STEMS] for b in range(nb)])
    nov = np.zeros(nb); nov[1:] = np.minimum(np.abs(np.diff(F, axis=0)), 30).sum(1)
    lsc = [float(np.mean([nov[b] for b in range(1, nb) if b % Bn == L] or [0])) for L in range(Bn)]
    L8 = int(np.argmax(lsc)); srl = sorted(lsc, reverse=True)
    print(f'loop phase: bar {L8} of {Bn} (novelty {lsc[L8]:.2f}, next {srl[1]:.2f}); scores {[round(x, 2) for x in lsc]}')

    # ---- loop boundaries + kick offset per loop
    bidx = list(range(L8, nb, Bn)); assert len(bidx) >= 2, 'song too short for loops'
    starts = [float(grid[p + 4 * b]) for b in bidx]
    kick = librosa.onset.onset_detect(y=librosa.effects.preemphasis(yd, coef=-0.97), sr=SR, units='time', hop_length=HOP, delta=0.2, backtrack=False)
    def off(a, b):
        beat = (b - a) / N; ks = kick[(kick >= a - beat / 2) & (kick < b - beat / 2)]
        if len(ks) < 8: return 0.0
        q = (ks - a) / beat; return float(np.angle(np.mean(np.exp(2j * np.pi * (q % 1)))) / (2 * np.pi) * beat)
    new = [s + (off(s, starts[k + 1]) if k + 1 < len(starts) else off(starts[k - 1], s)) for k, s in enumerate(starts)]
    print(f'lead-in before loop 1 (unused): {starts[0] - grid[0]:.2f}s | boundary moves (ms):', [round((n - s) * 1000) for n, s in zip(new, starts)])
    rows = []
    for k in range(len(new) - 1):
        a0, b0 = int(round(new[k] * fs)), int(round(new[k + 1] * fs))
        rows.append((k + 1, new[k], (b0 - a0) / fs, {s: db(Y[s][a0:b0]) for s in STEMS}))
    labs = label(rows)

    # ---- key
    cands = estimate_key(key_chroma([M[s] for s in KEY_STEMS]))
    kpc, kmin = cands[0][1], cands[0][2]
    overridden = A.key is not None or A.minor is not None
    if A.key is not None: kpc = parse_key(A.key); kmin = 0 if A.minor is None else A.minor
    elif A.minor is not None: kmin = A.minor
    tgt, tpc = ('B minor', ROOT_MIN) if kmin else ('D major', ROOT_MAJ)
    shift = ((tpc - kpc + 6) % 12) - 6                 # nearest semitone move, -6..+5
    print('key candidates (Krumhansl-Schmuckler):', ' | '.join(f'{NOTES[pc]} {"minor" if mn else "major"} r={r:+.3f}' for r, pc, mn in cands[:3]))
    print(f'key used: {NOTES[kpc]} {"minor" if kmin else "major"}{" (override)" if overridden else ""} -> shift to {tgt}: {shift:+d} semitones'
          + ('  (tie at 6: either way)' if abs(shift) == 6 else ''))

    # ---- table
    print(' NN   start    len    bpm ' + ' '.join(f'{s[:7]:>7s}' for s in STEMS) + '  label')
    for (n, t, Ln, r), lab in zip(rows, labs):
        print(f' {n:02d} {t:7.2f} {Ln:6.2f} {1920 / Ln:6.1f} ' + ' '.join(f'{r[s]:7.1f}' for s in STEMS) + f'  {lab}')
    if A.dry: return

    # ---- write
    crate = os.path.join(BASE, 'crates', f'{A.crate_name}-crate'); quiet = os.path.join(BASE, 'crates', '_quiet', A.crate_name)
    assert not os.path.exists(crate) or not os.listdir(crate), crate + ' not empty'
    os.makedirs(crate, exist_ok=True); os.makedirs(quiet, exist_ok=True)
    bk = LIB + time.strftime('.bak-%Y%m%d-%H%M%S'); shutil.copy2(LIB, bk); print('library backup', bk)
    lib = [e for e in json.load(open(LIB, encoding='utf-8')) if f'/{A.crate_name}-crate/' not in e['path']]
    bpm = int(round(pinned))
    made, quiet_l, silent = [], [], []
    fade = int(0.003 * fs); ramp = np.linspace(0, 1, fade)[:, None]
    for si, stem in enumerate(STEMS, 1):
        for (n, t, Ln, r), lab in zip(rows, labs):
            a0 = int(round(new[n - 1] * fs)); b0 = int(round(new[n] * fs)); sg = Y[stem][a0:b0].copy(); v = r[stem]
            if v < -60: silent.append(f'{si}-{stem}-{n:02d}'); continue
            sg[:fade] *= ramp; sg[-fade:] *= ramp[::-1]
            name = f'{si}-{stem}-{n:02d}_{lab}-{bpm}bpm.wav'
            if v < -42: sf.write(os.path.join(quiet, name), sg, fs, subtype='PCM_16'); quiet_l.append((name, round(v, 1))); continue
            pth = os.path.join(crate, name); sf.write(pth, sg, fs, subtype='PCM_16'); made.append(name)
            st = os.stat(pth); secs = len(sg) / fs
            lib.append(dict(path=pth.replace('\\', '/'), size=st.st_size, mtime=int(st.st_mtime), sampleRate=fs, frames=len(sg), seconds=secs,
                            tempo=round(1920.0 / secs, 3), tempoConf=1.0, bars=8, key=kpc, minor=bool(kmin), keyConf=1.0, onsets=[], bestOnset=0.0,
                            role=[float(x) for x in ROLE.get(stem, [0, 0, 1, 0])], rms=v, peak=float(20 * np.log10(np.abs(sg).max() + 1e-12))))
    with open(LIB, 'w', encoding='utf-8') as f: json.dump(lib, f, ensure_ascii=False)
    with open(os.path.join(crate, 'crate.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(title=A.title, artist=A.artist, song=song, sections={f'{n:02d}': lab for (n, _, _, _), lab in zip(rows, labs)}),
                  f, indent=1, ensure_ascii=False)
    print('crate files', len(made), '| quiet', len(quiet_l), quiet_l, '| not written (< -60 dB)', len(silent))
    print(f'cache entries for {A.crate_name}-crate:', sum(f'/{A.crate_name}-crate/' in e['path'] for e in json.load(open(LIB, encoding='utf-8'))))
    for f in sorted(x for x in made if x.startswith('1-drums')):     # verify: kick offset inside each drum loop vs its own 32-beat grid
        yy, _ = librosa.load(os.path.join(crate, f), sr=SR, mono=True); d = len(yy) / SR; beat = d / 32
        ks = librosa.onset.onset_detect(y=librosa.effects.preemphasis(yy, coef=-0.97), sr=SR, units='time', hop_length=HOP, delta=0.2, backtrack=False)
        ph = np.exp(2j * np.pi * ((ks / beat) % 1)); bars_ = [np.angle(np.mean(ph[(ks >= q * 4 * beat) & (ks < (q + 1) * 4 * beat)])) / (2 * np.pi) * beat * 1000 for q in range(8)]
        print(f'  {f}: kick off-beat {np.angle(np.mean(ph)) / (2 * np.pi) * beat * 1000:+4.0f} ms, per bar {[round(x) for x in bars_]}')

if __name__ == '__main__':
    main()
