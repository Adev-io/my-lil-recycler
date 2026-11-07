# Presses every button on the virtual console (http://127.0.0.1:2700) through the page server, as a click would: both arrows,
# every sample pad on every page, the bank button, every move in every bank, the drum machine button, both MiniLab mode
# buttons, every labelled MiniLab knob / fader in both modes and every MiniLab pad. One PASS / FAIL line per button.
# Saves the rig first (decks A/B/C, Arp, Acid, Mixer, Drums, tempo, page, bank, MiniLab mode) and puts it back at the end.
# Audible while it runs (several minutes). Run with Rack + pads.py up, no move held: py -3.11 board_sweep.py
import json, os, sys, time, urllib.request
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import sections as S, fx, maps, synths
C, U, URL = fx.C, S.U, 'http://127.0.0.1:2700'
LOGF, LEVELF = os.path.join(here, 'pads.log'), maps.LEVELF
NAMES = {S.A: 'A', S.B: 'B', C: 'C', S.MIX: 'MIX', S.DRUMS: 'DRUMS', S.ACID: 'ACID', fx.CLOCK: 'CLOCK'}
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
def mark(): return len(open(LOGF, encoding='utf-8', errors='replace').readlines())
def logged(n, text): return any(text in l for l in open(LOGF, encoding='utf-8', errors='replace').readlines()[n:])
def snap(): return {m: prms(m) for m in NAMES}                                   # every param of the modules the console moves
def put(sn):
    for m, p in sn.items(): S.call('vcvrack_set_params', {'moduleId': m, 'params': [{'id': k, 'value': v} for k, v in p.items()]})
def diff(a, b, skip=()):                                                         # params that differ, as 'MIX[4] 0.707->0.0'
    return [f'{NAMES[m]}[{k}] {round(a[m][k], 3)}->{round(b[m][k], 3)}' for m in a for k in a[m]
            if (m, k) not in skip and abs(a[m][k] - b[m][k]) > 0.002]
near = lambda a, b, tol=0.002: abs(a - b) <= tol

# ---- save the rig
saved = {d: json.loads(S.call('vcvrack_get_module_state', {'id': d})) for d in (S.A, S.B, C, synths.ARP, S.ACID)}
saved_p = {m: prms(m) for m in (S.MIX, S.DRUMS, S.ACID)}
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
    for d in (S.A, S.B, C): S.call('vcvrack_set_params', {'moduleId': d, 'params': [{'id': 14 + k, 'value': 0.0} for k in range(4)]})
    time.sleep(6)                                                                # pads.py re-reads the rig: every row dark
    for pg, P in enumerate(get()['launchpad']['pages']):
        page(pg)
        for row in get()['launchpad']['rows']:
            r = S.PAGES[pg]['rows'][row['base']]; deck, slot = r.get('deck', S.A), r['slot']
            for i, label in enumerate(row['labels']):
                if not label: continue
                note, want = row['base'] + i, os.path.basename(r['samples'][i])
                if lit(row['base']) == i: press(note)                            # already lit: a press would mute, so mute first
                ok1 = press(note); on1, p1, l1 = lit(row['base']), path(deck, slot), prm(deck, 14 + slot)
                ok2 = press(note); on2, l2 = lit(row['base']), prm(deck, 14 + slot)
                check(f'{P} {row["name"]} pad {i + 1} ({label})', ok1 and ok2 and on1 == i and p1 == want and near(l1, r['level']) and on2 is None and l2 == 0.0,
                      '' if on1 == i and p1 == want else f'lit {on1} {p1} level {round(l1, 2)} -> lit {on2} level {l2}')

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
        'reverse':      (0, lambda b, d: all(d[S.A][36 + k] == 1.0 for k in range(4)) and all(d[S.B][36 + k] == 0.0 for k in range(4))),
        'drums only':   (0, lambda b, d: all(d[S.MIX][k] == 0.0 for k in (1, 2, 3, 5, 6)) and d[S.MIX][0] == b[S.MIX][0] and d[S.MIX][4] == b[S.MIX][4]),
        'no drums':     (0, lambda b, d: d[S.MIX][0] == 0.0 and d[S.MIX][4] == 0.0 and d[S.MIX][2] == b[S.MIX][2]),
        'acid in/out':  (0, lambda b, d: (b[S.MIX][1] > 0.001) != (d[S.MIX][1] > 0.001)),
        'arp in/out':   (0, lambda b, d: (b[S.MIX][6] > 0.001) != (d[S.MIX][6] > 0.001)),
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
            elif name == 'dnb':                                                  # tempo up to the peak; again = release back to fx.BPM
                ok1 = press(note); time.sleep(4); t1, on1 = fx.bpm(), fxon(name)
                ok2 = press(note); time.sleep(fx.DNB['release'] + 1.5); a, on2 = snap(), fxon(name)
                back = diff(b, a, skip={(fx.CLOCK, 0)})
                check(f'bank {bk + 1} dnb', ok1 and ok2 and on1 and t1 > b[fx.CLOCK][0] and not on2 and a[fx.CLOCK][0] == fx.BPM and not back,
                      f'{b[fx.CLOCK][0]} -> {t1} -> {a[fx.CLOCK][0]} BPM' + (f' not back: {back}' if back else ''))
            elif name == 'transition':                                           # Lowdown on show: TOOM (deck B) sweeps out, Lowdown in
                ok1 = press(note); on1 = fxon(name); time.sleep(fx.TRANS_SECS + 2.5); a, on2 = snap(), fxon(name)
                check(f'bank {bk + 1} transition', ok1 and on1 and not on2 and logged(n0, 'transition to Lowdown done') and a[S.MIX][2] == U and a[S.MIX][3] == U
                      and all(a[S.B][14 + k] == 0.0 for k in range(4)) and [round(a[S.A][24 + k], 2) for k in range(4)] == fx.BASEF[S.A], f'lit {on1}->{on2}')
            elif name == 'clean':                                                # a sweep up held, then clean: filters at rest, strips 3-5 open
                press(11 if 11 in [x['note'] for x in get()['launchpad']['fx']] else note); time.sleep(2); d = snap()
                ok = press(note); a = snap(); lit_any = [x['name'] for x in get()['launchpad']['fx'] if x['on'] and not x['name'].endswith('in/out')]
                filt = [round(a[S.A][24 + k], 2) for k in range(4)] + [round(a[C][24], 2)] + [round(a[S.B][24 + k], 2) for k in range(4)]
                check(f'bank {bk + 1} clean', ok and d[S.A][24] > b[S.A][24] + 0.05 and filt == fx.BASE and [a[S.MIX][k] for k in (2, 3, 4)] == [U, U, U] and not lit_any,
                      f'filters {filt} strips {[round(a[S.MIX][k], 3) for k in (2, 3, 4)]} lit {lit_any}')
            elif name == 'break fill':                                           # the break for 2 bars, then the beat before
                ok1 = press(note); p1, on1 = round(prm(S.DRUMS, 3)) + 1, fxon(name); time.sleep(fx.bars_secs(2) + 1.5)
                p2, on2 = round(prm(S.DRUMS, 3)) + 1, fxon(name)
                check(f'bank {bk + 1} break fill', ok1 and p1 == fx.BREAK and on1 and p2 == round(b[S.DRUMS][3]) + 1 and not on2 and logged(n0, 'fx break fill'),
                      f'pattern {round(b[S.DRUMS][3]) + 1} -> {p1} -> {p2}')
            else: check(f'bank {bk + 1} {name}', False, 'no check written for this move')
    settle(); bank(0)

    # ---- c) drum machine button: off, then on
    maps.drum_machine(True); time.sleep(0.3); l0 = prm(S.DRUMS, 5)
    r1 = post('/machine'); a = (prm(S.DRUMS, 5), get()['launchpad']['machine'])
    r2 = post('/machine'); b = (prm(S.DRUMS, 5), get()['launchpad']['machine'])
    check('drum machine button off / on', r1['on'] is False and a == (0.0, False) and r2['on'] is True and near(b[0], l0) and b[1] is True, f'{round(l0, 3)} -> {a} -> {b}')

    # ---- d) MiniLab mode buttons (each launches acid.py / minilab.py; with no MiniLab plugged in they exit, the page relabels anyway)
    for m, f0 in (('acid', 'cutoff'), ('mix', 'vocals vol')):
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
    for pg in range(len(L0['pages'])):
        page(pg); time.sleep(0.5); sweep_ccs(f'mix page {pg + 1}', maps.mix_map(pg))
    page(0)

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
    post('/mode', {'mode': 'mix'}); time.sleep(3)
except Exception:
    import traceback; traceback.print_exc(); check('sweep ran to the end', False)
finally:
    # ---- put the rig back
    try:
        bank(0)
        if any(f['on'] for f in get()['launchpad']['fx'] if not f['name'].endswith('in/out')): press(18)   # clean lets go of a held move
    except Exception as e: print('clean failed', e)
    post('/mode', {'mode': saved_mode}); bank(saved_bank); page(saved_page); time.sleep(2)   # page turn first: the arp scale write settles
    for d, s in saved.items(): S.call('vcvrack_set_module_state', {'id': d, 'state': s})
    for m, p in saved_p.items(): S.call('vcvrack_set_params', {'moduleId': m, 'params': [{'id': k, 'value': v} for k, v in p.items()]})
    fx.set_strips(saved_strips); fx.bpm(saved_bpm)
    if saved_level is not None: open(LEVELF, 'w').write(saved_level)
    time.sleep(6)
    g = get(); print('restored: page', g['launchpad']['page'] + 1, 'bank', g['launchpad']['bank'] + 1, 'mode', g['minilab']['mode'], 'bpm', fx.bpm(),
                     'strips', [round(x, 3) for x in fx.strips()], 'machine', g['launchpad']['machine'])
    print(f"\n{sum(ok for _, ok in res)}/{len(res)} passed" + ''.join(f'\n  FAILED: {n}' for n, ok in res if not ok))
    sys.exit(0 if res and all(ok for _, ok in res) else 1)
