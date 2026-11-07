# Live end-to-end test of the set controls, driven through the page server (the same path as a click or a Launchpad press).
# Saves the rig first (decks A/B/C/D, Arp, Acid, Mixer, Drums, Triple, tempo, page, bank, MiniLab mode) and puts it back at the end.
# Audible while it runs (~6 min). Run with Rack + pads.py up: py -3.11 test_live.py
import json, os, sys, time, urllib.request, urllib.error
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import sections as S, fx, maps, synths
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
def row(name): return next(r for r in get()['launchpad']['rows'] if r['name'] == name)   # Synths page rows: 'lit' = pad indexes lit
def rp_to(name, k):                                               # press a row's end button until its row page k is on show
    for _ in range(row(name)['rpages'] + 1):
        if row(name)['rpage'] == k: return
        idle(); post('/rowpage', {'base': row(name)['base']})
near = lambda a, b, tol=0.002: abs(a - b) <= tol
ENTRY_KNOB = {'acid in/out': fx.acid_cutoff, 'arp in/out': synths.arp_gate}               # what each 2-bar entry ramps, then puts back

# ---- save the rig
saved = {d: json.loads(S.call('vcvrack_get_module_state', {'id': d})) for d in (S.A, S.B, C, S.D)}
saved_vs = {m: json.loads(S.call('vcvrack_get_module_state', {'id': m})) for m in (synths.ARP, S.ACID)}   # arp dir + Acid patterns (keep writes one)
saved_p = {m: {x['id']: x['value'] for x in json.loads(S.call('vcvrack_get_params', {'moduleId': m}))} for m in (S.MIX, S.DRUMS, S.ACID, synths.TRI)}
g0 = get(); saved_page, saved_bank, saved_mode, saved_bpm = g0['launchpad']['page'], g0['launchpad']['bank'], g0['minilab']['mode'], fx.bpm()
saved_rp = None                                                  # Lowdown vocals / keys row pages as found, put back at the end
print('saved rig: page', saved_page + 1, 'bank', saved_bank + 1, 'mode', saved_mode, 'bpm', saved_bpm, 'strips', st())
try:
    # ---- baseline: every sample part muted, strips open, drum machine on, bank 1
    for d in (S.A, S.B, C, S.D): S.call('vcvrack_set_params', {'moduleId': d, 'params': [{'id': 14 + k, 'value': 0.0} for k in range(4)]})
    fx.set_strip_map({2: U, 3: U, 4: U, 7: 0.0}); maps.drum_machine(True); bank(0); page(0); time.sleep(6)   # Disco's strip rests at 0

    check('page server answers, Rack up', g0['rack'])
    idle(); post('/page', {'dir': -1}); check('no page left of page 1', get()['launchpad']['page'] == 0)
    page(1); check('right arrow -> page 2 Time Out Of Mind', get()['launchpad']['page'] == 1)
    page(2); check('right arrow -> page 3 Disco Ulysses', get()['launchpad']['page'] == 2 and get()['launchpad']['pages'][2:] == ['Disco Ulysses', 'Synths'])
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
    page(2); press(71); a = (path(S.D, 1), lv(S.D)[1], lit('piano')); press(71)                 # Disco: deck D, strip 8 resting at 0 (cue)
    check('Disco piano pad 1 plays 15 chorus on deck D, again mutes', a[0].startswith('4-piano-15') and a[1] == 1.0 and a[2] == 0 and lv(S.D)[1] == 0.0 and lit('piano') is None, f'{a}')
    page(0)

    # ---- page follows the rig
    press(41); S.call('vcvrack_set_params', {'moduleId': S.A, 'params': [{'id': 14, 'value': 0.0}]}); time.sleep(6.5)
    check('page follows a change made in Rack', lit('bass') is None)

    # ---- row pages: the round button at a row's end (CC base + 8) cycles main -> samples2 -> chop halves -> main
    v = row('vocals')
    if 'rpages' not in v: print('SKIP  row pages  pads.py from before the row page cycle: restart it', flush=True)
    else:
        saved_rp = {nm: row(nm)['rpage'] for nm in ('vocals', 'keys')}; s2 = S.ROWS[81]['samples2']
        rp_to('vocals', 0)
        a0 = (path(S.A, 3), lv(S.A)[3]); idle(); r = post('/rowpage', {'base': 81}); g = row('vocals')
        check('vocals round button -> page 2, sound untouched', r['ok'] and g['rpage'] == 1 and g['rkind'] == 'extra' and g['labels'] == maps.pad_labels(s2) and (path(S.A, 3), lv(S.A)[3]) == a0, f"{g['labels']}")
        press(85); time.sleep(6)                                      # the 5 s refresh reads the rig by row page: still lit
        check('vocals page 2 pad 5 plays 04 choir, lit after the refresh', path(S.A, 3) == os.path.basename(s2[4]) and lv(S.A)[3] == 1.0 and lit('vocals') == 4, f'{path(S.A, 3)} lit {lit("vocals")}')
        rp_to('vocals', 0); a = lit('vocals'); rp_to('vocals', 1); b = lit('vocals')
        check('page 1 shown: no pad lit; page 2 again: pad 5 lit', a is None and b == 4 and path(S.A, 3) == os.path.basename(s2[4]), f'{a} {b}')
        press(85); check('page 2 lit pad again mutes', lv(S.A)[3] == 0.0 and lit('vocals') is None)
        rp_to('vocals', 0)
        try: post('/rowpage', {'base': 81}, origin='http://evil.example'); check('foreign site refused (row page)', False)
        except urllib.error.HTTPError as e: check('foreign site refused (row page)', e.code == 403 and row('vocals')['rpage'] == 0, f'HTTP {e.code}')
        k = row('keys')                                               # keys row: once round to its first chop page, the 'a' pad plays the 4-bar half A
        if not os.path.exists(S.CHOPS) or k['rpages'] < 2: print('SKIP  keys chop page  no chops.json (or no keys halves in it)', flush=True)
        else:
            idle(); r = post('/rowpage', {'base': 71}); g = row('keys')
            check('keys round button -> chop page', r['ok'] and g['rpage'] == 1 and g['rkind'] == 'chop' and g['labels'][0].endswith(' a'), f"{g['labels']}")
            press(71); p1 = path(S.A, 1)
            check("keys chop page 'a' pad plays its -chop4a half", p1.endswith('-chop4a.wav') and p1 == os.path.basename(S.cur(S.ROWS[71], 1)[0]) and lv(S.A)[1] == 1.2 and lit('keys') == 0, f'{p1} lit {lit("keys")}')
            press(71); check('keys chop pad again mutes', lv(S.A)[1] == 0.0 and lit('keys') is None)
            n = row('keys')['rpages']
            for _ in range(n - 1): idle(); post('/rowpage', {'base': 71})
            check('keys round button cycles back to page 1', row('keys')['rpage'] == 0 and row('keys')['labels'] == maps.pad_labels(S.ROWS[71]['samples']), f"{n} pages")

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
    p0, b0 = S.current_drum_pattern(), fx.bpm(); press(16); time.sleep(9); b1, p1 = fx.bpm(), S.current_drum_pattern()
    press(16); time.sleep(9.5)
    check('dnb: 140 BPM + break', b1 == 140.0 and p1 == fx.BREAK, f'{b1} BPM pattern {p1}')
    check('dnb release: tempo from before, beat + strips back', fx.bpm() == b0 and S.current_drum_pattern() == p0 and st() == s0, f'{b0} -> {fx.bpm()} BPM pattern {S.current_drum_pattern()}')
    press(71); page(1); press(17); time.sleep(18)
    check('transition to TOOM: Lowdown out, TOOM pad 1 rows in', lv(S.A) == [0.0] * 4 and lv(S.B)[1] == 1.0 and lv(S.B)[0] == 1.0 and path(C, 0).startswith('1-drums-05') and st()[2] == U, f'A {lv(S.A)} B {lv(S.B)}')
    page(0); press(17); time.sleep(18)
    check('transition back: TOOM out, Lowdown pad 1 rows in', lv(S.B) == [0.0] * 4 and lv(S.A)[1] == 1.2 and lv(S.A)[0] == 1.0 and path(C, 0).startswith('1-drums-15'), f'A {lv(S.A)} B {lv(S.B)}')
    page(2); press(17); time.sleep(18)
    check('transition to Disco: Lowdown out, Disco pad 1 rows in, strip 8 up', lv(S.A) == [0.0] * 4 and lv(S.D)[1] == 1.0 and lv(S.D)[0] == 1.0 and path(C, 0).startswith('1-drums-08_chorus')
          and st()[7] == U and st()[2] == U, f'A {lv(S.A)} D {lv(S.D)} strips {st()}')
    page(0); press(17); time.sleep(18)
    check('transition Disco -> Lowdown: Disco out, strip 8 back to 0', lv(S.D) == [0.0] * 4 and st()[7] == 0.0 and lv(S.A)[1] == 1.2 and path(C, 0).startswith('1-drums-15'), f'A {lv(S.A)} D {lv(S.D)} strips {st()}')
    press(11); time.sleep(2); press(18)
    check('clean: filters at rest, strips open', [round(x, 2) for x in fx.deck_filters(S.A)] == fx.BASEF[S.A] and st()[2:5] == [U, U, U] and not fxon('sweep up'))

    # ---- bank 2
    bank(1); press(81)
    for note, name in ((11, 'acid in/out'), (12, 'arp in/out')):      # 2-bar entries: strip + cutoff / gate ramp, the knob put back
        (k, dflt), knob, w = fx.STRIP_TOGGLE[name], ENTRY_KNOB[name], fx.bars_secs(2) + 1.5
        a, c0 = st()[k], knob(); want = a if a > 0.001 else dflt         # in: the level it had (out remembers it) or the default
        press(note); m = st()[k]; time.sleep(w); b, c1 = st()[k], knob()
        press(note); time.sleep(w); s2, c2 = st()[k], knob()
        first = (b == 0 and m > 0.001) if a > 0.001 else near(b, dflt)   # an out keeps the strip up while the ramp runs
        check(f'{name} ramps strip {k + 1} over 2 bars, {ENTRY_KNOB[name].__name__} put back', first and abs(c1 - c0) <= 0.02 and near(s2, a) and abs(c2 - c0) <= 0.02,
              f'strip {a} -> {m} (1 s) -> {b} -> {s2}, knob {round(c0, 3)} -> {round(c1, 3)} -> {round(c2, 3)}')
        if a > 0.001: press(note); time.sleep(w)                          # reversal starts from out
        c0 = knob(); press(note); time.sleep(0.2); press(note); time.sleep(w); s3, c3 = st()[k], knob()
        check(f'{name} in, then out after ~1 s: reverses to out', s3 == 0 and abs(c3 - c0) <= 0.02, f'strip {s3}, knob {round(c0, 3)} -> {round(c3, 3)}')
        if a > 0.001: press(note); time.sleep(w); check(f'{name} back in at its level', near(st()[k], a), f'{st()[k]} (was {a})')
    k = fx.STRIP_TOGGLE['voice in/out'][0]; a = st()[k]; press(13); b = st()[k]; press(13)
    check(f'voice in/out toggles strip {k + 1} at once', (a == 0) != (b == 0) and st()[k] == a, f'{a} -> {b} -> {st()[k]}')
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
    VS = fx.STUT + fx.VOX_SLOT                                         # vox stutter (Recycler 2.4.0): a page click holds, again lets go
    for pg, d, o in ((0, S.A, S.B), (1, S.B, S.A), (2, S.D, S.A)):          # Disco: slot 3 = horns/synth (no vocals)
        n = len(json.loads(S.call('vcvrack_get_params', {'moduleId': d})))
        if n <= fx.STUTLEN: print(f'SKIP  vox 1/8 on page {pg + 1}  deck has {n} params (Recycler before 2.4.0)', flush=True); continue
        page(pg); press(13); a = (prm(d, VS), prm(d, fx.STUTLEN), prm(o, VS), fxon('vox 1/8')); press(13); b = (prm(d, VS), fxon('vox 1/8'))
        check(f'vox 1/8 on page {pg + 1} holds its vocals stutter at 1/8, click again lets go', a == (1.0, 1.0, 0.0, True) and b == (0.0, False), f'held {a} let go {b}')
    page(0); bank(0)

    # ---- Synths page (page 4): it acts on the song last shown, here Disco (page 4 is reached through page 3)
    page(1); page(3); names = [r['name'] for r in get()['launchpad']['rows']]; time.sleep(1)
    check('Synths page rows', get()['launchpad']['page'] == 3 and names == ['acid patterns', 'acid moves', 'fills (hold)', 'arp dir / oct', 'arp interval', 'auto change'], f'{names}')
    check('arp scale follows Disco: B major (mask 3418)', synths.scale_now() == 3418, f'{synths.scale_now()}')
    AC, AR = (lambda i: prm(S.ACID, i)), (lambda i: prm(synths.ARP, i))
    press(76); a = AC(28); press(75); b = AC(28)
    check('tr +5 then tr 0 transpose the Acid', a == 5 and b == 0, f'{a} {b}')
    pats = lambda: json.loads(S.call('vcvrack_get_module_state', {'id': S.ACID}))['data']['patterns']
    slot = round(AC(24)); p0 = pats()[slot]; press(72); press(74); t0 = time.time()
    while pats()[slot] == p0 and time.time() - t0 < 3: time.sleep(0.25)
    check('mut x3 then keep stores the mutated pattern in the playing slot', pats()[slot] != p0, f'slot {slot} after {round(time.time() - t0, 1)} s')
    press(52); d = synths.arp_dir(); press(51)
    check('down / up set the arp direction', d == 1 and synths.arp_dir() == 0, f'{d} {synths.arp_dir()}')
    press(56); check('oct 2 = Arp OCT 2', AR(16) == 2, f'{AR(16)}')
    press(43); check('5th = Arp INT 4', AR(18) == 4, f'{AR(18)}')
    press(61); a = (AC(34), AC(33), 0 in row('fills (hold)')['lit']); press(61); b = (AC(34), 0 in row('fills (hold)')['lit'])
    check('acid roll: click holds the roll fill, click again lets go', a == (1.0, 0.0, True) and b == (0.0, False), f'{a} {b}')
    press(64); a = (AR(21), AR(20)); press(64); b = AR(21)
    check('arp x2: click holds roll 2, click again lets go', a == (1.0, 2.0) and b == 0.0, f'{a} {b}')
    press(31); a = 0 in row('auto change')['lit']; press(31); b = 0 in row('auto change')['lit']
    check('auto acid on (lit) / off', a and not b, f'{a} {b}')
    press(82); check('acid patterns pad 2 = Disco pattern 2', AC(24) == S.ACID_SONG[2][1] and 1 in row('acid patterns')['lit'], f'{AC(24)} want {S.ACID_SONG[2][1]}')
    press(11); time.sleep(4); fa, fd = fx.deck_filters(S.A), fx.deck_filters(S.D); press(11)
    check('sweep up on the Synths page moves Disco (deck D) only', fd[0] > 0.2 and [round(x, 2) for x in fa] == fx.BASEF[S.A] and [round(x, 2) for x in fx.deck_filters(S.D)] == fx.BASEF[S.D],
          f'A {[round(x, 2) for x in fa]} D {[round(x, 2) for x in fd]}')
    page(0); time.sleep(1); check('arp scale back to D major on Lowdown (mask 2774)', synths.scale_now() == 2774, f'{synths.scale_now()}')

    # ---- drums
    l0 = prm(S.DRUMS, 5); r1 = post('/machine'); r2 = post('/machine')
    check('drum machine button (top-row Session) off / on', r1['on'] is False and r2['on'] is True and abs(prm(S.DRUMS, 5) - l0) < 0.002)
    post('/mode', {'mode': 'mix'}); time.sleep(3); p0 = S.current_drum_pattern() - 1
    tp = 1 if p0 != 1 else 2                                   # a beat that is not the one playing
    post('/set', {'pad': tp}); a = (S.current_drum_pattern(), prm(S.DRUMS, 5) > 0)
    post('/set', {'pad': tp}); b = prm(S.DRUMS, 5) > 0
    post('/set', {'pad': p0}); c = (S.current_drum_pattern() - 1, prm(S.DRUMS, 5) > 0)
    check('beat pads: pick, same again = off, any = on', a == (tp + 1, True) and b is False and c == (p0, True), f'{a} {b} {c}')

    # ---- MiniLab follows the song on show
    for pg, d, nm in ((0, S.A, 'keys vol'), (1, S.B, 'piano vol'), (2, S.D, 'piano vol')):
        page(pg); time.sleep(0.5); v0 = prm(d, 15); lab = get()['minilab']['faders'][1]['label']
        post('/set', {'cc': 83, 'value': 64}); v1 = prm(d, 15); post('/set', {'cc': 83, 'value': maps.to_cc(maps.fader, v0)})
        check(f'MiniLab fader 2 on page {pg + 1} = {nm}', lab == nm and abs(v1 - maps.fader(64)) < 0.01, f'{round(v0, 2)} -> {round(v1, 2)}')
    page(0)
    post('/mode', {'mode': 'acid'}); time.sleep(3); a = get()['minilab']['faders'][0]['label']
    post('/mode', {'mode': 'mix'}); time.sleep(3); b = get()['minilab']['faders'][0]['label']
    check('MiniLab mode switch relabels', a == 'cutoff' and b == 'vocals vol', f'{a} / {b}')
    post('/mode', {'mode': 'env'}); time.sleep(3); g = get()['minilab']; f = [x['label'] for x in g['faders']]
    check('MiniLab Acid Env mode', g['mode'] == 'env' and g['title'] == 'Acid Env' and f == ['filter attack', 'filter decay', 'filter sustain', 'filter release'], f'{g["mode"]} {g["title"]} {f}')
    post('/mode', {'mode': 'mix'}); time.sleep(3)
finally:
    # ---- put the rig back
    try: bank(0); press(18)                                    # clean: pads.py lets go of any move the test left held
    except Exception as e: print('clean failed', e)
    try:                                                       # Synths page: let go of a held fill, auto change off
        page(3)
        for name, keep in (('fills (hold)', ()), ('auto change', (2, 3))):   # auto change pads 3-4 = phrase length, lit by design
            for i in row(name)['lit']:
                if i not in keep: press(row(name)['base'] + i)
    except Exception as e: print('Synths let go failed', e)
    for d, s in list(saved.items()) + list(saved_vs.items()):
        if d in saved: s = dict(s, params=fx.no_stut(s['params']))       # Recycler decks: STUT 40-44 never restored (no hold left on)
        S.call('vcvrack_set_module_state', {'id': d, 'state': s})
    for m, p in saved_p.items(): S.call('vcvrack_set_params', {'moduleId': m, 'params': [{'id': k, 'value': v} for k, v in p.items()]})
    fx.bpm(saved_bpm); time.sleep(1)
    try:                                                       # vocals / keys row pages as found
        page(0)
        for nm, k in (saved_rp or {}).items(): rp_to(nm, k)
    except Exception as e: print('row page put back failed', e)
    post('/mode', {'mode': saved_mode}); bank(saved_bank); page(saved_page); time.sleep(6)
    print('restored: page', get()['launchpad']['page'] + 1, 'bank', get()['launchpad']['bank'] + 1, 'mode', get()['minilab']['mode'], 'bpm', fx.bpm(), 'strips', st())
    print(f"\n{sum(ok for _, ok in res)} / {len(res)} passed" + ''.join(f'\n  FAILED: {n}' for n, ok in res if not ok))
