# Live end-to-end test of the set controls, driven through the page server (the same path as a click or a Launchpad press).
# Saves the rig first (decks A/B/C, Mixer, Drums, Acid, tempo, page, bank, MiniLab mode) and puts it back at the end.
# Audible while it runs (~4 min). Run with Rack + pads.py up: py -3.11 test_live.py
import json, os, sys, time, urllib.request, urllib.error
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import sections as S, fx, maps
C, U, URL = fx.C, S.U, 'http://127.0.0.1:2700'
res = []
def check(name, ok, info=''):
    res.append((name, bool(ok))); print(f"{'PASS' if ok else 'FAIL'}  {name}  {info}", flush=True)
def get(): return json.loads(urllib.request.urlopen(URL + '/state', timeout=20).read())
def post(path, d=None, origin=None):
    h = {'Content-Type': 'application/json'}
    if origin: h['Origin'] = origin
    return json.loads(urllib.request.urlopen(urllib.request.Request(URL + path, data=json.dumps(d or {}).encode(), headers=h), timeout=20).read())
def idle():
    for _ in range(80):
        if not get()['launchpad']['busy']: return
        time.sleep(0.25)
def press(note): idle(); r = post('/press', {'note': note}); time.sleep(0.8); idle(); return r['ok']
def page(p):
    while get()['launchpad']['page'] != p: idle(); post('/page', {'dir': 1 if p > get()['launchpad']['page'] else -1}); time.sleep(0.3)
def bank(b):
    while get()['launchpad']['bank'] != b: post('/bank'); time.sleep(0.3)
def prm(m, i): return next(x['value'] for x in json.loads(S.call('vcvrack_get_params', {'moduleId': m})) if x['id'] == i)
def lv(d): return [round(prm(d, 14 + k), 2) for k in range(4)]
def st(): return [round(x, 3) for x in fx.strips()]
def path(d, k): return os.path.basename(json.loads(S.call('vcvrack_get_module_state', {'id': d}))['data']['slots'][k]['path'])
def loud(d): return json.loads(S.call('vcvrack_measure', {'moduleId': d, 'outputId': 8, 'seconds': 0.5}))['lufs']
def lit(name): return next(r['on'] for r in get()['launchpad']['rows'] if r['name'] == name)
def fxon(name): return next(f['on'] for f in get()['launchpad']['fx'] if f['name'] == name)

# ---- save the rig
saved = {d: json.loads(S.call('vcvrack_get_module_state', {'id': d})) for d in (S.A, S.B, C)}
saved_p = {m: {x['id']: x['value'] for x in json.loads(S.call('vcvrack_get_params', {'moduleId': m}))} for m in (S.MIX, S.DRUMS, S.ACID)}
g0 = get(); saved_page, saved_bank, saved_mode, saved_bpm = g0['launchpad']['page'], g0['launchpad']['bank'], g0['minilab']['mode'], fx.bpm()
print('saved rig: page', saved_page + 1, 'bank', saved_bank + 1, 'mode', saved_mode, 'bpm', saved_bpm, 'strips', st())
try:
    # ---- baseline: every sample part muted, strips open, drum machine on, bank 1
    for d in (S.A, S.B, C): S.call('vcvrack_set_params', {'moduleId': d, 'params': [{'id': 14 + k, 'value': 0.0} for k in range(4)]})
    fx.set_strip_map({2: U, 3: U, 4: U}); maps.drum_machine(True); bank(0); page(0); time.sleep(6)

    check('page server answers, Rack up', g0['rack'])
    idle(); post('/page', {'dir': -1}); check('no page left of page 1', get()['launchpad']['page'] == 0)
    page(1); check('right arrow -> page 2 Time Out Of Mind', get()['launchpad']['page'] == 1)
    page(0)
    try: post('/press', {'note': 71}, origin='http://evil.example'); check('foreign site refused', False)
    except urllib.error.HTTPError as e: check('foreign site refused', e.code == 403, f'HTTP {e.code}')

    # ---- sample pads
    press(71); check('Lowdown keys pad 1 plays', path(S.A, 1).startswith('4-piano-14') and lv(S.A)[1] == 1.2 and lit('keys') == 0, f'{path(S.A, 1)} {lv(S.A)[1]}')
    press(71); check('lit pad again mutes', lv(S.A)[1] == 0.0 and lit('keys') is None)
    page(1); press(71); t0 = time.time(); heard = None
    while time.time() - t0 < 20:
        if loud(S.B) > -60: heard = round(time.time() - t0, 1); break
        time.sleep(0.5)
    check('TOOM piano 05 lands and sounds', heard is not None and lv(S.B)[1] == 1.0, f'heard after {heard} s (next loop start)')
    press(71)
    page(0); press(21); a = path(C, 0); page(1); press(21); b = path(C, 0); time.sleep(6)
    check('drums slot shared: TOOM drums replace Lowdown drums', a.startswith('1-drums-15') and b.startswith('1-drums-05'), f'{a} -> {b}')
    page(0); check('Lowdown drums pad goes dark after the swap', lit('drums') is None)
    page(1); press(21); page(0)

    # ---- page follows the rig
    press(41); S.call('vcvrack_set_params', {'moduleId': S.A, 'params': [{'id': 14, 'value': 0.0}]}); time.sleep(6.5)
    check('page follows a change made in Rack', lit('bass') is None)

    # ---- bank 1
    press(11); time.sleep(4); fa, fb = fx.deck_filters(S.A), fx.deck_filters(S.B)
    check('sweep up on page 1 moves only Lowdown', fa[0] > 0.2 and all(abs(x) < 0.01 for x in fb), f'A {[round(x, 2) for x in fa]} B {[round(x, 2) for x in fb]}')
    press(11); check('sweep release snaps back', [round(x, 2) for x in fx.deck_filters(S.A)] == fx.BASEF[S.A])
    page(1); press(12); time.sleep(4); fb = fx.deck_filters(S.B)
    check('sweep down on page 2 moves only TOOM', fb[0] < -0.2 and [round(x, 2) for x in fx.deck_filters(S.A)] == fx.BASEF[S.A], f'B {[round(x, 2) for x in fb]}')
    press(12); page(0)
    rv = lambda d: [int(prm(d, 36 + k)) for k in range(4)]
    press(13); check('reverse page 1 = Lowdown only', rv(S.A) == [1] * 4 and rv(S.B) == [0] * 4)
    page(1); press(13); check('reverse released from page 2', rv(S.A) == [0] * 4); page(0)
    s0 = st(); press(14); s1 = st(); press(14)
    check('drums only silences Acid, decks A/B, voices', all(s1[k] == 0 for k in (1, 2, 3, 5, 6)) and s1[0] == s0[0] and s1[4] == s0[4])
    check('drums only release restores', st() == s0)
    press(15); s1 = st(); press(15)
    check('no drums silences machine + stem only', s1[0] == 0 and s1[4] == 0 and s1[2] == s0[2])
    check('no drums release restores', st() == s0)
    p0 = S.current_drum_pattern(); press(16); time.sleep(9); b1, p1 = fx.bpm(), S.current_drum_pattern()
    press(16); time.sleep(9.5)
    check('dnb: 140 BPM + break', b1 == 140.0 and p1 == fx.BREAK, f'{b1} BPM pattern {p1}')
    check('dnb release: 120 BPM, beat + strips back', fx.bpm() == 120.0 and S.current_drum_pattern() == p0 and st() == s0, f'{fx.bpm()} pattern {S.current_drum_pattern()}')
    press(71); page(1); press(17); time.sleep(18)
    check('transition to TOOM: Lowdown out, TOOM pad 1 rows in', lv(S.A) == [0.0] * 4 and lv(S.B)[1] == 1.0 and lv(S.B)[0] == 1.0 and path(C, 0).startswith('1-drums-05') and st()[2] == U, f'A {lv(S.A)} B {lv(S.B)}')
    page(0); press(17); time.sleep(18)
    check('transition back: TOOM out, Lowdown pad 1 rows in', lv(S.B) == [0.0] * 4 and lv(S.A)[1] == 1.2 and lv(S.A)[0] == 1.0 and path(C, 0).startswith('1-drums-15'), f'A {lv(S.A)} B {lv(S.B)}')
    press(11); time.sleep(2); press(18)
    check('clean: filters at rest, strips open', [round(x, 2) for x in fx.deck_filters(S.A)] == fx.BASEF[S.A] and st()[2:5] == [U, U, U] and not fxon('sweep up'))

    # ---- bank 2
    bank(1); press(81)
    for note, (k, _), name in ((11, fx.STRIP_TOGGLE['acid in/out'], 'acid'), (12, fx.STRIP_TOGGLE['arp in/out'], 'arp'), (13, fx.STRIP_TOGGLE['voice in/out'], 'voice')):
        a = st()[k]; press(note); b = st()[k]; press(note)
        check(f'{name} in/out toggles strip {k + 1}', (a == 0) != (b == 0) and st()[k] == a, f'{a} -> {b} -> {st()[k]}')
    c0 = fx.acid_cutoff(); press(14); time.sleep(4); c1 = fx.acid_cutoff(); press(14)
    check('acid sweep opens then snaps back', c1 > c0 + 0.01 and abs(fx.acid_cutoff() - c0) < 0.002, f'{round(c0, 2)} -> {round(c1, 2)} -> {round(fx.acid_cutoff(), 2)}')
    p0 = S.current_drum_pattern(); press(15); p1 = S.current_drum_pattern(); time.sleep(fx.bars_secs(2) + 1)
    check('break fill: break for 2 bars, then the beat', p1 == fx.BREAK and S.current_drum_pattern() == p0)
    a = lv(S.A); press(16); b = lv(S.A); press(16)
    check('no bass mutes Lowdown bass, then back', a[0] > 0 and b[0] == 0 and lv(S.A)[0] == a[0])
    a = lv(S.A); press(17); b = lv(S.A); press(17)
    check('no vocals mutes Lowdown vocals, then back', a[3] > 0 and b[3] == 0 and lv(S.A)[3] == a[3])
    s0, f0 = st(), fx.deck_filters(S.A); press(18); s1, f1 = st(), fx.deck_filters(S.A); press(18)
    check('breakdown: drums out + low-pass, then back', s1[0] == 0 and s1[4] == 0 and f1[0] < -0.5 and st() == s0 and fx.deck_filters(S.A) == f0)

    # ---- bank 3
    bank(2); a = st()[4]; press(11); time.sleep(fx.bars_secs(fx.FADE_BARS) + 1); b = st()[4]; press(11); time.sleep(fx.bars_secs(fx.FADE_BARS) + 1)
    check('drums in/out fades tracked drums out and back', a > 0.5 and b == 0 and abs(st()[4] - a) < 0.01, f'{a} -> {b} -> {st()[4]}')
    bank(0)

    # ---- drums
    l0 = prm(S.DRUMS, 5); r1 = post('/machine'); r2 = post('/machine')
    check('drum machine button off / on', r1['on'] is False and r2['on'] is True and abs(prm(S.DRUMS, 5) - l0) < 0.002)
    post('/mode', {'mode': 'mix'}); time.sleep(3); p0 = S.current_drum_pattern() - 1
    tp = 1 if p0 != 1 else 2                                   # a beat that is not the one playing
    post('/set', {'pad': tp}); a = (S.current_drum_pattern(), prm(S.DRUMS, 5) > 0)
    post('/set', {'pad': tp}); b = prm(S.DRUMS, 5) > 0
    post('/set', {'pad': p0}); c = (S.current_drum_pattern() - 1, prm(S.DRUMS, 5) > 0)
    check('beat pads: pick, same again = off, any = on', a == (tp + 1, True) and b is False and c == (p0, True), f'{a} {b} {c}')

    # ---- MiniLab follows the song on show
    for pg, d, nm in ((0, S.A, 'keys vol'), (1, S.B, 'piano vol')):
        page(pg); time.sleep(0.5); v0 = prm(d, 15); lab = get()['minilab']['faders'][1]['label']
        post('/set', {'cc': 83, 'value': 64}); v1 = prm(d, 15); post('/set', {'cc': 83, 'value': maps.to_cc(maps.fader, v0)})
        check(f'MiniLab fader 2 on page {pg + 1} = {nm}', lab == nm and abs(v1 - maps.fader(64)) < 0.01, f'{round(v0, 2)} -> {round(v1, 2)}')
    page(0)
    post('/mode', {'mode': 'acid'}); time.sleep(3); a = get()['minilab']['faders'][0]['label']
    post('/mode', {'mode': 'mix'}); time.sleep(3); b = get()['minilab']['faders'][0]['label']
    check('MiniLab mode switch relabels', a == 'cutoff' and b == 'vocals vol', f'{a} / {b}')
finally:
    # ---- put the rig back
    try: bank(0); press(18)                                    # clean: pads.py lets go of any move the test left held
    except Exception as e: print('clean failed', e)
    for d, s in saved.items(): S.call('vcvrack_set_module_state', {'id': d, 'state': s})
    for m, p in saved_p.items(): S.call('vcvrack_set_params', {'moduleId': m, 'params': [{'id': k, 'value': v} for k, v in p.items()]})
    fx.bpm(saved_bpm); time.sleep(1)
    post('/mode', {'mode': saved_mode}); bank(saved_bank); page(saved_page); time.sleep(6)
    print('restored: page', get()['launchpad']['page'] + 1, 'bank', get()['launchpad']['bank'] + 1, 'mode', get()['minilab']['mode'], 'bpm', fx.bpm(), 'strips', st())
    print(f"\n{sum(ok for _, ok in res)} / {len(res)} passed" + ''.join(f'\n  FAILED: {n}' for n, ok in res if not ok))
