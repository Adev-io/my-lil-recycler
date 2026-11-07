# Presses every button on the virtual console (http://127.0.0.1:2700) through the page server, as a click would: both arrows,
# every sample pad on every page (every row page too: samples2 and the chop halves, through its row-end round button), the bank button, every move in every bank, the drum machine button, every Synths page pad,
# the three MiniLab mode buttons, every labelled MiniLab knob / fader in every mode and every MiniLab pad. One PASS / FAIL line per button.
# Saves the rig first (decks A/B/C/D, Arp, Acid, Mixer, Drums, tempo, page, bank, MiniLab mode) and puts it back at the end.
# Audible while it runs (several minutes). Run with Rack + pads.py up, no move held: py -3.11 board_sweep.py
import json, os, sys, time, urllib.request
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import sections as S, fx, maps, synths
C, U, URL = fx.C, S.U, 'http://127.0.0.1:2700'
LOGF, LEVELF = os.path.join(here, 'pads.log'), maps.LEVELF
NAMES = {S.A: 'A', S.B: 'B', C: 'C', S.D: 'D', S.MIX: 'MIX', S.DRUMS: 'DRUMS', S.ACID: 'ACID', fx.CLOCK: 'CLOCK'}
res = []
def check(name, ok, info=''):
    res.append((name, bool(ok))); print(f"{'PASS' if ok else 'FAIL'}  {name}  {info}", flush=True)
def get(): return json.loads(urllib.request.urlopen(URL + '/state', timeout=20).read())
def post(path, d=None):
    h = {'Content-Type': 'application/json', 'Origin': URL}                      # the page's own origin, as a click sends
    return json.loads(urllib.request.urlopen(urllib.request.Request(URL + path, data=json.dumps(d or {}).encode(), headers=h), timeout=20).read())
def idle():
    for _ in range(120):
        if not get()['launchpad']['busy']: return
        time.sleep(0.1)
def press(note): idle(); r = post('/press', {'note': note}); time.sleep(0.1); idle(); return r['ok']
def page(p):
    while get()['launchpad']['page'] != p: idle(); post('/page', {'dir': 1 if p > get()['launchpad']['page'] else -1}); time.sleep(0.3)
def bank(b):
    while get()['launchpad']['bank'] != b: post('/bank'); time.sleep(0.3)
def prms(m): return {x['id']: x['value'] for x in json.loads(S.call('vcvrack_get_params', {'moduleId': m}))}
def prm(m, i): return prms(m)[i]
def path(d, k): return os.path.basename(json.loads(S.call('vcvrack_get_module_state', {'id': d}))['data']['slots'][k]['path'])
def lit(base): return next(r['on'] for r in get()['launchpad']['rows'] if r['base'] == base)
def fxon(name): return next(f['on'] for f in get()['launchpad']['fx'] if f['name'] == name)
def rlit(base): return next(r['lit'] for r in get()['launchpad']['rows'] if r['base'] == base)   # Synths page: pad indexes lit
def mark(): return len(open(LOGF, encoding='utf-8', errors='replace').readlines())
def logged(n, text): return any(text in l for l in open(LOGF, encoding='utf-8', errors='replace').readlines()[n:])
def snap(): return {m: prms(m) for m in NAMES}                                   # every param of the modules the console moves
def put(sn):
    for m, p in sn.items():
        ps = [{'id': k, 'value': v} for k, v in p.items()]
        S.call('vcvrack_set_params', {'moduleId': m, 'params': fx.no_stut(ps) if m in (S.A, S.B, C, S.D) else ps})   # Recycler STUT 40-44 left alone
def diff(a, b, skip=()):                                                         # params that differ, as 'MIX[4] 0.707->0.0'
    return [f'{NAMES[m]}[{k}] {round(a[m][k], 3)}->{round(b[m][k], 3)}' for m in a for k in a[m]
            if (m, k) not in skip and abs(a[m][k] - b[m][k]) > 0.002]
near = lambda a, b, tol=0.002: abs(a - b) <= tol

# ---- save the rig
saved = {d: json.loads(S.call('vcvrack_get_module_state', {'id': d})) for d in (S.A, S.B, C, S.D, synths.ARP, S.ACID)}
saved_p = {m: prms(m) for m in (S.MIX, S.DRUMS, S.ACID, synths.TRI)}
saved_strips, saved_bpm = fx.strips(), fx.bpm()
saved_level = open(LEVELF).read() if os.path.exists(LEVELF) else None
g0 = get(); L0 = g0['launchpad']; saved_page, saved_bank, saved_mode = L0['page'], L0['bank'], g0['minilab']['mode']
print('saved rig: page', saved_page + 1, 'bank', saved_bank + 1, 'mode', saved_mode, 'bpm', saved_bpm, 'strips', [round(x, 3) for x in saved_strips])
held = [f['name'] for f in L0['fx'] if f['on'] and not f['name'].endswith('in/out')]
if held: sys.exit(f'a move is held ({held}): release it first')
try:
    # ---- arrows
    page(0); idle(); r = post('/page', {'dir': -1}); check('left arrow on page 1 refused', r['ok'] is False and get()['launchpad']['page'] == 0)
    last = len(L0['pages']) - 1; page(last); idle(); r = post('/page', {'dir': 1})
    check(f'right arrow on page {last + 1} refused', r['ok'] is False and get()['launchpad']['page'] == last)
    idle(); r1 = post('/page', {'dir': -1}); p1 = get()['launchpad']['page']; idle(); r2 = post('/page', {'dir': 1}); p2 = get()['launchpad']['page']
    check('left / right arrow turn the page', r1['ok'] and r2['ok'] and p1 == last - 1 and p2 == last, f'{p1 + 1} {p2 + 1}')

    # ---- a) every sample pad on every page: plays its sample in its deck slot, lit; again = muted
    for d in (S.A, S.B, C, S.D): S.call('vcvrack_set_params', {'moduleId': d, 'params': [{'id': 14 + k, 'value': 0.0} for k in range(4)]})
    time.sleep(6)                                                                # pads.py re-reads the rig: every row dark
    def row_pads(P, pg, row):                                                    # every pad of a row as shown (its row page)
        r = S.PAGES[pg]['rows'][row['base']]; deck, slot = r.get('deck', S.A), r['slot']; L = S.cur(r, row.get('rpage', 0))
        tag = f' page {row["rpage"] + 1}/{row["rpages"]}' if row.get('rpages', 1) > 1 else ''
        for i, label in enumerate(row['labels']):
            if not label: continue
            note, want = row['base'] + i, os.path.basename(L[i])
            if lit(row['base']) == i: press(note)                            # already lit: a press would mute, so mute first
            ok1 = press(note); on1, p1, l1 = lit(row['base']), path(deck, slot), prm(deck, 14 + slot)
            ok2 = press(note); on2, l2 = lit(row['base']), prm(deck, 14 + slot)
            check(f'{P} {row["name"]}{tag} pad {i + 1} ({label})', ok1 and ok2 and on1 == i and p1 == want and near(l1, r['level']) and on2 is None and l2 == 0.0,
                  '' if on1 == i and p1 == want else f'lit {on1} {p1} level {round(l1, 2)} -> lit {on2} level {l2}')
    rowd = lambda b: next(x for x in get()['launchpad']['rows'] if x['base'] == b)
    for pg, P in enumerate(get()['launchpad']['pages']):
        if S.PAGES[pg].get('synth'): continue                                    # Synths page: action pads, no samples
        page(pg)
        rows_ = get()['launchpad']['rows']
        if pg == 0 and not any('rpages' in x for x in rows_): print('SKIP  row page buttons  pads.py from before the row page cycle: restart it', flush=True)
        for row in rows_:
            row_pads(P, pg, row)
            n = row.get('rpages', 1)                                             # a row with more pages: its round button through every page
            if n < 2: continue                                                   # (samples2, chop halves), every pad there, round to where it was
            b = row['base']; r = S.PAGES[pg]['rows'][b]; deck, slot = r.get('deck', S.A), r['slot']; s0 = (path(deck, slot), prm(deck, 14 + slot))
            for step in range(1, n + 1):
                want = (row['rpage'] + step) % n
                idle(); r1 = post('/rowpage', {'base': b}); g = rowd(b)
                check(f'{P} {row["name"]} row page button -> page {want + 1}/{n} ({g.get("rkind")})', r1['ok'] and g['rpage'] == want and g['labels'] == maps.pad_labels(S.cur(r, want))
                      and (path(deck, slot), prm(deck, 14 + slot)) == s0, f'{g["labels"]}')   # pads only: the sound is untouched
                if want != row['rpage']: row_pads(P, pg, g); s0 = (path(deck, slot), prm(deck, 14 + slot))

    # ---- b) bank button and every move in every bank, on page 1 (Lowdown) with vocals, keys, bass and drums rows playing
    page(0); bank(0)
    seen = [get()['launchpad']['bank']]
    for _ in range(L0['banks']): post('/bank'); time.sleep(0.2); seen.append(get()['launchpad']['bank'])
    check('bank button cycles the moves', seen == [0, 1, 2, 0], f'{seen}')
    for note in (81, 71, 41, 21): press(note)
    fx.set_filters(fx.BASE); fx.reverse(False); maps.drum_machine(True); S.drum_pattern(3); time.sleep(6)
    M = snap()                                                                   # every move starts from this mix
    def settle(): put(M); time.sleep(6)                                          # pads.py re-reads strips: in/out moves lit as the rig is
    TOG = {   # toggle move -> (seconds to let it work, the effect it must have while on: (before, during) -> bool)
        'sweep up':     (2.5, lambda b, d: d[S.A][24] > b[S.A][24] + 0.05),
        'sweep down':   (2.5, lambda b, d: d[S.A][24] < b[S.A][24] - 0.05),
        'reverse':      (0, lambda b, d: all(d[S.A][36 + k] == 1.0 for k in range(4)) and all(d[S.B][36 + k] == 0.0 and d[S.D][36 + k] == 0.0 for k in range(4))),
        'drums only':   (0, lambda b, d: all(d[S.MIX][k] == 0.0 for k in (1, 2, 3, 5, 6, 7)) and d[S.MIX][0] == b[S.MIX][0] and d[S.MIX][4] == b[S.MIX][4]),
        'no drums':     (0, lambda b, d: d[S.MIX][0] == 0.0 and d[S.MIX][4] == 0.0 and d[S.MIX][2] == b[S.MIX][2]),
        'acid in/out':  (fx.bars_secs(2) + 1.5, lambda b, d: (b[S.MIX][1] > 0.001) != (d[S.MIX][1] > 0.001)),   # 2-bar entries
        'arp in/out':   (fx.bars_secs(2) + 1.5, lambda b, d: (b[S.MIX][6] > 0.001) != (d[S.MIX][6] > 0.001)),
        'voice in/out': (0, lambda b, d: (b[S.MIX][5] > 0.001) != (d[S.MIX][5] > 0.001)),
        'acid sweep':   (2.5, lambda b, d: d[S.ACID][1] > b[S.ACID][1] + 0.05),
        'no bass':      (0, lambda b, d: b[S.A][14] > 0 and d[S.A][14] == 0.0),
        'no vocals':    (0, lambda b, d: b[S.A][17] > 0 and d[S.A][17] == 0.0),
        'breakdown':    (0, lambda b, d: d[S.MIX][0] == 0.0 and d[S.MIX][4] == 0.0 and all(near(d[S.A][24 + k], fx.BREAKDOWN_LP) for k in range(4))),
        'drums in/out': (fx.bars_secs(fx.FADE_BARS) + 1, lambda b, d: (b[S.MIX][4] > 0.001) != (d[S.MIX][4] > 0.001)),
    }
    for bk in range(L0['banks']):
        bank(bk)
        for f in get()['launchpad']['fx']:
            name, note = f['name'], f['note']; settle(); b, on0, n0 = snap(), fxon(name), mark()
            if name in TOG:
                wait, effect = TOG[name]
                ok1 = press(note); time.sleep(wait); d, on1 = snap(), fxon(name)
                ok2 = press(note); time.sleep(wait); a, on2 = snap(), fxon(name)
                back = diff(b, a)
                check(f'bank {bk + 1} {name}', ok1 and ok2 and on1 != on0 and effect(b, d) and on2 == on0 and not back,
                      f'lit {on0}->{on1}->{on2}' + (f' not back: {back}' if back else '') + ('' if effect(b, d) else ' no effect'))
            elif name == 'dnb':                                                  # tempo up to the peak; again = release back to the tempo before
                ok1 = press(note); time.sleep(4); t1, on1 = fx.bpm(), fxon(name)
                ok2 = press(note); time.sleep(fx.DNB['release'] + 1.5); a, on2 = snap(), fxon(name)
                back = diff(b, a, skip={(fx.CLOCK, 0)})
                check(f'bank {bk + 1} dnb', ok1 and ok2 and on1 and t1 > b[fx.CLOCK][0] and not on2 and a[fx.CLOCK][0] == b[fx.CLOCK][0] and not back,
                      f'{b[fx.CLOCK][0]} -> {t1} -> {a[fx.CLOCK][0]} BPM' + (f' not back: {back}' if back else ''))
            elif name == 'transition':                                           # Lowdown on show: TOOM (deck B) sweeps out, Lowdown in
                ok1 = press(note); on1 = fxon(name); time.sleep(fx.TRANS_SECS + 2.5); a, on2 = snap(), fxon(name)
                check(f'bank {bk + 1} transition', ok1 and on1 and not on2 and logged(n0, 'transition to Lowdown done') and a[S.MIX][2] == U and a[S.MIX][3] == U
                      and a[S.MIX][7] == 0.0 and all(a[S.B][14 + k] == 0.0 and a[S.D][14 + k] == 0.0 for k in range(4))   # Disco (deck D) out too, strip 8 at rest 0
                      and [round(a[S.A][24 + k], 2) for k in range(4)] == fx.BASEF[S.A], f'lit {on1}->{on2}')
            elif name == 'clean':                                                # a sweep up held, then clean: filters at rest, strips 3-5 open
                press(11 if 11 in [x['note'] for x in get()['launchpad']['fx']] else note); time.sleep(2); d = snap()
                ok = press(note); a = snap(); lit_any = [x['name'] for x in get()['launchpad']['fx'] if x['on'] and not x['name'].endswith('in/out')]
                filt = [round(a[S.A][24 + k], 2) for k in range(4)] + [round(a[C][24], 2)] + [round(a[S.B][24 + k], 2) for k in range(4)]
                check(f'bank {bk + 1} clean', ok and d[S.A][24] > b[S.A][24] + 0.05 and filt == fx.BASE and [round(a[S.D][24 + k], 2) for k in range(4)] == fx.BASEF[S.D]
                      and [a[S.MIX][k] for k in (2, 3, 4)] == [U, U, U] and not lit_any,
                      f'filters {filt} strips {[round(a[S.MIX][k], 3) for k in (2, 3, 4)]} lit {lit_any}')
            elif name == 'break fill':                                           # the break for 2 bars, then the beat before
                ok1 = press(note); p1, on1 = round(prm(S.DRUMS, 3)) + 1, fxon(name); time.sleep(fx.bars_secs(2) + 1.5)
                p2, on2 = round(prm(S.DRUMS, 3)) + 1, fxon(name)
                check(f'bank {bk + 1} break fill', ok1 and p1 == fx.BREAK and on1 and p2 == round(b[S.DRUMS][3]) + 1 and not on2 and logged(n0, 'fx break fill'),
                      f'pattern {round(b[S.DRUMS][3]) + 1} -> {p1} -> {p2}')
            elif name in fx.VOX_STUT:                                            # vox stutter (Recycler 2.4.0): a click holds the song playing's
                VS = fx.STUT + fx.VOX_SLOT                                       # vocals at its length, a second click lets go; from every page
                song = get()['launchpad']['song']; d = fx.own_deck(song); o = S.B if d != S.B else S.A
                for pg in range(len(L0['pages'])):
                    if len(b[d]) <= fx.STUTLEN: print(f'SKIP  bank {bk + 1} {name} page {pg + 1}  deck has {len(b[d])} params (Recycler before 2.4.0)', flush=True); continue
                    page(pg); ok1 = press(note); h = (prm(d, VS), prm(d, fx.STUTLEN), prm(o, VS), fxon(name))
                    ok2 = press(note); a = (prm(d, VS), fxon(name))
                    check(f'bank {bk + 1} {name} page {pg + 1}', ok1 and ok2 and h == (1.0, float(fx.VOX_STUT[name]), 0.0, True) and a == (0.0, False), f'held {h} let go {a}')
                page(0)
            else: check(f'bank {bk + 1} {name}', False, 'no check written for this move')
    settle(); bank(0)

    # ---- c) drum machine button: off, then on
    maps.drum_machine(True); time.sleep(0.3); l0 = prm(S.DRUMS, 5)
    r1 = post('/machine'); a = (prm(S.DRUMS, 5), get()['launchpad']['machine'])
    r2 = post('/machine'); b = (prm(S.DRUMS, 5), get()['launchpad']['machine'])
    check('drum machine button (top-row Session) off / on', r1['on'] is False and a == (0.0, False) and r2['on'] is True and near(b[0], l0) and b[1] is True, f'{round(l0, 3)} -> {a} -> {b}')

    # ---- c2) every Synths pad (page 4). It acts on the song playing (the transition above: Lowdown), not on Disco's page 3 passed on the way.
    # Hold pads: a click holds, a second click lets go. Others: one click, its param checked. Auto / phrase: put back after.
    page(1); page(len(L0['pages']) - 1); P = synths.pads(get()['launchpad']['song'])
    rows3 = {r['base']: r for r in get()['launchpad']['rows']}
    AC, AR = (lambda i: prm(S.ACID, i)), (lambda i: prm(synths.ARP, i))
    phrase0 = next((31 + i for i in rlit(31) if i in (2, 3)), None)
    for note in sorted(P, key=lambda n: (-(n // 10), n)):
        label, kind, arg = P[note]; base = note // 10 * 10 + 1; i = note - base; n0 = mark()
        tag = f'Synths {rows3[base]["name"]} pad {i + 1} ({label})'; named = rows3[base]['labels'][i] == label
        if kind in ('fill', 'roll', 'octjump'):
            o0 = AR(16)
            ok1 = press(note); on = i in rlit(base)
            d = (AC(34), AC(33)) if kind == 'fill' else (AR(21), AR(20)) if kind == 'roll' else AR(16)
            ok2 = press(note); off = i not in rlit(base)
            a = AC(34) if kind == 'fill' else AR(21) if kind == 'roll' else AR(16)
            want = (min(4.0, o0 + 1), o0) if kind == 'octjump' else ((1.0, float(arg)), 0.0)   # octjump has no arg
            check(tag, named and ok1 and ok2 and on and off and d == want[0] and a == want[1] and logged(n0, f'synths {label} let go'), f'held {d} let go {a} (want {want}) lit {on} -> {not off}')
        elif kind in ('auto', 'phrase'):
            was = i in rlit(base); ok1 = press(note); on = i in rlit(base)
            if kind == 'auto': press(note)
            else: phrase0 and press(phrase0)
            back = (i in rlit(base)) == was
            check(tag, named and ok1 and on and back and logged(n0, f'synths {label} held'), f'lit {was} -> {on}, back {back}')
        else:
            ok = press(note); lt = i in rlit(base)
            got = {'pattern': lambda: AC(24), 'mutate': lambda: AC(synths.A_AMOUNT), 'undo': lambda: AC(synths.A_UNDO), 'keep': lambda: AC(synths.A_KEEP),
                   'transpose': lambda: AC(synths.A_TRANSPOSE), 'dir': synths.arp_dir, 'oct': lambda: AR(synths.R_OCT), 'int': lambda: AR(synths.R_INT)}[kind]()
            want = 0.0 if kind in ('undo', 'keep') else arg                     # a tap: the button is let go again
            lit_ok = lt if kind not in ('mutate', 'undo', 'keep') else True       # moves are actions, not states: never lit
            check(tag, named and ok and got == want and lit_ok and logged(n0, f'synths {label} held'), f'{got} (want {want}) lit {lt}')
    for m in (synths.ARP, S.ACID): S.call('vcvrack_set_module_state', {'id': m, 'state': saved[m]})   # the Synths pads changed patterns, transpose, arp
    page(0)

    # ---- d) MiniLab mode buttons (each launches acid.py / minilab.py; with no MiniLab plugged in they exit, the page relabels anyway)
    for m, f0 in (('acid', 'cutoff'), ('env', 'filter attack'), ('mix', 'vocals vol')):
        r = post('/mode', {'mode': m}); time.sleep(3); g = get()['minilab']; fm = open(os.path.join(here, 'minilab.mode')).read().strip()
        check(f'mode button {m}', r['ok'] and fm == m and g['mode'] == m and g['title'] == maps.MODES[m]['title'] and g['faders'][0]['label'] == f0, f'file {fm} page {g["mode"]} fader 1 {g["faders"][0]["label"]}')

    # ---- e) every MiniLab knob / fader with a label, both modes (mix on both song pages): 0, 127, back to the saved value
    def sweep_ccs(tag, cmap):
        g = get()['minilab']
        for ctl in g['knobs'] + g['faders']:
            if not ctl['label']: continue
            cc = ctl['cc']; mod, pid, f, label = cmap[cc]; v0 = prm(mod, pid); tol = maps.ACID_TOLS.get((mod, pid), 0.002) / 2 if mod == S.ACID else 0.002
            post('/set', {'cc': cc, 'value': 0, 'log': False}); a = prm(mod, pid)
            post('/set', {'cc': cc, 'value': 127, 'log': False}); b = prm(mod, pid)
            back = maps.to_cc(f, v0); post('/set', {'cc': cc, 'value': back}); c = prm(mod, pid)
            check(f'MiniLab {tag} cc {cc} {label}', label == ctl['label'] and near(a, f(0), tol) and near(b, f(127), tol) and near(c, f(back), tol),
                  f'{round(v0, 3)}: 0 -> {round(a, 3)} (want {f(0)}), 127 -> {round(b, 3)} (want {f(127)}), back {round(c, 3)}')
    song = get()['launchpad']['song']; want = [maps.mix_map(song)[c][3] for c in maps.FADERS]
    for pg in range(len(L0['pages'])):                                           # the mix map follows the song playing, whatever page is on show
        page(pg); time.sleep(0.5); labs = [c['label'] for c in get()['minilab']['faders']]
        check(f'MiniLab mix labels on page {pg + 1} = {S.PAGES[song]["name"]} (playing)', labs == want, f'{labs}')
    sweep_ccs(f'mix {S.PAGES[song]["name"]}', maps.mix_map(song)); page(0)

    # ---- e) MiniLab pads, mix mode: pick beat i (on), same pad again = off
    maps.drum_machine(False)
    for i, pd in enumerate(get()['minilab']['pads']):
        post('/set', {'pad': i}); a = (round(prm(S.DRUMS, 3)), prm(S.DRUMS, 5) > 0.001, get()['minilab']['pads'][i]['on'])
        post('/set', {'pad': i}); b = (prm(S.DRUMS, 5) > 0.001, get()['minilab']['pads'][i]['on'])
        check(f'MiniLab mix pad {i + 1} ({pd["label"]})', a == (i, True, True) and b == (False, False), f'{a} {b}')

    # ---- e) acid mode: knobs / faders, then pads = Acid pattern 8 + i
    post('/mode', {'mode': 'acid'}); time.sleep(3); sweep_ccs('acid', maps.ACID)
    p0 = prm(S.ACID, 24)
    for i, pd in enumerate(get()['minilab']['pads']):
        post('/set', {'pad': i}); a = (round(prm(S.ACID, 24)), get()['minilab']['pads'][i]['on'])
        check(f'MiniLab acid pad {i + 1} ({pd["label"]})', a == (8 + i, True), f'{a}')
    S.call('vcvrack_set_params', {'moduleId': S.ACID, 'params': [{'id': 24, 'value': p0}]})

    # ---- e) Acid Env mode: filter / amp ADSR knobs and faders (pads + keys are the acid mode's)
    post('/mode', {'mode': 'env'}); time.sleep(3); sweep_ccs('env', maps.ENV)
    post('/mode', {'mode': 'mix'}); time.sleep(3)
except Exception:
    import traceback; traceback.print_exc(); check('sweep ran to the end', False)
finally:
    # ---- put the rig back
    try:
        bank(0)
        if any(f['on'] for f in get()['launchpad']['fx'] if not f['name'].endswith('in/out')): press(18)   # clean lets go of a held move
    except Exception as e: print('clean failed', e)
    try:                                                                         # Synths page: let go of a held fill, auto change off
        page(len(L0['pages']) - 1)
        for b3 in (61, 31):
            for i in rlit(b3):
                if b3 == 61 or i in (0, 1): press(b3 + i)                        # auto change pads 3-4 = phrase length, lit by design
    except Exception as e: print('Synths let go failed', e)
    post('/mode', {'mode': saved_mode}); bank(saved_bank); page(saved_page); time.sleep(2)   # page turn first: the arp scale write settles
    for d, s in saved.items():
        if d in (S.A, S.B, C, S.D): s = dict(s, params=fx.no_stut(s['params']))   # Recycler decks: STUT 40-44 never restored (no hold left on)
        S.call('vcvrack_set_module_state', {'id': d, 'state': s})
    for m, p in saved_p.items(): S.call('vcvrack_set_params', {'moduleId': m, 'params': [{'id': k, 'value': v} for k, v in p.items()]})
    fx.set_strips(saved_strips); fx.bpm(saved_bpm)
    if saved_level is not None: open(LEVELF, 'w').write(saved_level)
    time.sleep(6)
    g = get(); print('restored: page', g['launchpad']['page'] + 1, 'bank', g['launchpad']['bank'] + 1, 'mode', g['minilab']['mode'], 'bpm', fx.bpm(),
                     'strips', [round(x, 3) for x in fx.strips()], 'machine', g['launchpad']['machine'])
    print(f"\n{sum(ok for _, ok in res)}/{len(res)} passed" + ''.join(f'\n  FAILED: {n}' for n, ok in res if not ok))
    sys.exit(0 if res and all(ok for _, ok in res) else 1)
