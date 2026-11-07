# 4-bar A/B halves of every pad sample on the Launchpad song pages (sections.PAGES: every row's samples and samples2).
# A = loop bars 1-4, B = bars 5-8, on the loop's own grid (frames / 8 per bar, as vocal_cuts.py / chop.py): A = y[0:n//2],
# B = y[n//2:2*(n//2)], 5 ms edge fades, written in the source's format to crates\chops\<source crate folder>\<name>-chop4a/b.wav
# (outside the deck crates). A loop whose frames are not 8 bars at its pinned tempo still gets the frames/2 split; it is reported.
# Skipped: sources that are already 4-bar files (name has 'chop' or library bars 4), and halves below -55 dBFS RMS (the Recycler
# normalises renders, so a silent half would play as hiss). A half peaking above -1 dBFS is scaled to -1 dBFS (as vocal_cuts.py).
# Pinned in the Recycler cache like vocal_cuts.py: bars 4, tempo 960 / chop seconds, keyConf 1, bestOnset 0; key, minor and role
# copied from the source loop's own library entry. chops.json (next to this file) = {source path: [chop A or null, chop B or null]}.
# Re-runnable: overwrites its own outputs, replaces its own cache entries, backs up library.json first. Never touches crate files.
# usage: py -3.11 row_chops.py [--check]   (--check = verify the existing outputs, the index and the cache pins only)
import os, sys, json, time, shutil, numpy as np, soundfile as sf
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sections                                                # import only: defines the rows, no rig calls at import time
CR = r'C:\Users\Arikl\Desktop\uvr-loops\crates'; OUT = os.path.join(CR, 'chops')
LIB = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\MyLilRecycler\library.json'); INDEX = os.path.join(HERE, 'chops.json')
FADE, CEIL, SILENT, GRID_TOL = 0.005, 10 ** (-1 / 20), -55.0, 1e-4   # GRID_TOL: relative frame mismatch vs 8 bars at the pinned tempo
db = lambda x: float(20 * np.log10(x + 1e-12))
fwd = lambda p: p.replace('\\', '/')

def sources():                                                 # every row sample path on every song page, first-seen order
    out = []
    for pg in sections.PAGES:
        for r in pg['rows'].values():
            for p in r.get('samples', []) + r.get('samples2', []):
                if p not in out: out.append(p)
    return out

def is_four_bar(p, lib): return 'chop' in os.path.basename(p) or lib.get(p, {}).get('bars') == 4

def dests(src):
    d = os.path.join(OUT, os.path.basename(os.path.dirname(src))); b = os.path.basename(src)
    return [os.path.join(d, b.replace('.wav', f'-chop4{h}.wav')) for h in 'ab']

def faded(seg, sr):
    seg = seg.copy(); n = min(int(FADE * sr), len(seg) // 2); r = np.linspace(0, 1, n)[:, None]
    seg[:n] *= r; seg[-n:] *= r[::-1]; return seg

def halves(y, sr):                                             # [(faded half, gain to apply)] for A and B
    h = len(y) // 2; out = []
    for seg in (y[:h], y[h:2 * h]):
        seg = faded(seg, sr); pk = np.abs(seg).max(); out.append((seg, CEIL / pk if pk > CEIL else 1.0))
    return out

def make():
    lib = {e['path']: e for e in json.load(open(LIB, encoding='utf-8'))}
    index, written, skip4, silent, offgrid = {}, [], [], [], []
    for src in sources():
        if is_four_bar(src, lib): skip4.append(src); continue
        e = lib[src]; info = sf.info(src); y, sr = sf.read(src, always_2d=True)
        want = e['bars'] * 240.0 / e['tempo'] * sr
        if e['bars'] != 8 or abs(len(y) - want) > GRID_TOL * len(y):
            offgrid.append(src); print(f'OFF-GRID {os.path.basename(src)}: {len(y)} frames vs {want:.1f} for {e["bars"]} bars at {e["tempo"]} -> frames/2 split')
        pair = []
        for (seg, g), dst in zip(halves(y, sr), dests(src)):
            rms = db(np.sqrt(np.mean(seg ** 2)))
            if rms < SILENT: silent.append(fwd(dst)); pair.append(None); print(f'SILENT   {os.path.basename(dst)} rms {rms:.1f} dBFS, skipped'); continue
            os.makedirs(os.path.dirname(dst), exist_ok=True); tmp = dst + '.tmp'
            sf.write(tmp, seg * g, sr, format=info.format, subtype=info.subtype); os.replace(tmp, dst)
            written.append((dst, src)); pair.append(fwd(dst))
            print(f'wrote {os.path.relpath(dst, OUT)}: {len(seg)} frames, gain {db(g):+.2f} dB, rms {rms:.1f} dBFS')
        index[fwd(src)] = pair
    bak = LIB + time.strftime('.bak-pre-rowchops-%Y%m%d-%H%M%S'); shutil.copy2(LIB, bak); print('backup', bak)
    new = {fwd(d) for d, _ in written}
    entries = [x for x in json.load(open(LIB, encoding='utf-8')) if x['path'] not in new]
    for dst, src in written:                                   # pin what is on disk (16-bit, after gain)
        seg, sr = sf.read(dst, always_2d=True); st = os.stat(dst); secs = len(seg) / sr; s = lib[src]
        entries.append(dict(path=fwd(dst), size=st.st_size, mtime=int(st.st_mtime), sampleRate=sr, frames=len(seg), seconds=secs,
                            tempo=round(960.0 / secs, 3), tempoConf=1.0, bars=4, key=s['key'], minor=s['minor'], keyConf=1.0, onsets=[],
                            bestOnset=0.0, role=s['role'], rms=db(np.sqrt(np.mean(seg ** 2))), peak=db(np.abs(seg).max())))
    with open(LIB + '.rc.tmp', 'w', encoding='utf-8') as f: json.dump(entries, f, ensure_ascii=False)
    os.replace(LIB + '.rc.tmp', LIB)
    with open(INDEX + '.tmp', 'w', encoding='utf-8') as f: json.dump(index, f, ensure_ascii=False, indent=1)
    os.replace(INDEX + '.tmp', INDEX)
    print(f'{len(written)} chops written from {len(index)} sources; skipped {len(skip4)} already-4-bar sources, {len(silent)} near-silent halves; '
          f'{len(offgrid)} off-grid sources'); print('index', INDEX)

def check():
    lib = {e['path']: e for e in json.load(open(LIB, encoding='utf-8'))}; index = json.load(open(INDEX, encoding='utf-8'))
    ok, n, per = True, 0, {}
    for src in sources():
        if is_four_bar(src, lib): continue
        if src not in index: print('BAD not in chops.json:', src); ok = False; continue
        info = sf.info(src); y, sr = sf.read(src, always_2d=True); h = len(y) // 2; s = lib[src]
        for k, ((seg, g), dst, got) in enumerate(zip(halves(y, sr), dests(src), index[src])):
            if got is None:                                    # null only when that half really is near silent
                good = db(np.sqrt(np.mean(seg ** 2))) < SILENT; ok &= good
                print(f'{"OK " if good else "BAD"} null {os.path.basename(dst)} (near-silent half)'); continue
            c, csr = sf.read(got, always_2d=True); ci = sf.info(got); st = os.stat(got); e = lib.get(got)
            pk, dc, f = db(np.abs(c).max()), float(np.abs(c.mean(0)).max()), int(FADE * sr)
            diff = float(np.abs(c[f:-f] - (y[k * h:(k + 1) * h] * g)[f:-f]).max())   # source samples inside the fades
            pinned = bool(e) and e['size'] == st.st_size and e['mtime'] == int(st.st_mtime) and e['bars'] == 4 \
                and abs(e['tempo'] - round(960.0 / (len(c) / csr), 3)) < 1e-6 and (e['key'], e['minor'], e['role']) == (s['key'], s['minor'], s['role'])
            good = (got == fwd(dst) and abs(len(c) - len(y) / 2) <= 1 and (csr, ci.subtype, ci.format, ci.channels) == (sr, info.subtype, info.format, info.channels)
                    and pk < -0.3 and dc < 1e-3 and diff <= (0 if g == 1.0 else 1.5 / 32768) and pinned)
            ok &= good; n += 1; crate = os.path.basename(os.path.dirname(got)); per[crate] = per.get(crate, 0) + 1
            print(f'{"OK " if good else "BAD"} {os.path.relpath(got, OUT)}: {len(c)} frames (src {len(y)}/2), {csr} Hz {ci.subtype}, '
                  f'peak {pk:.2f} dBFS, dc {dc:.1e}, gain {db(g):+.2f} dB, max diff vs source[{"0:half" if k == 0 else "half:"}] {diff:.1e}, pinned {pinned}')
    print(f'checked {n} chops: {per}'); print('ALL OK' if ok else 'FAILURES'); return ok

if __name__ == '__main__':
    if '--check' not in sys.argv: make()
    sys.exit(0 if check() else 1)
