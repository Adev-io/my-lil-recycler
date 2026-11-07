# Launchpad Mini MK3 (Programmer mode) -> the set by rows. Each row in sections.ROWS = one slot (row 1 vocals, row 2 keys ...):
# a pad picks that row's sample (blinking blue = playing), the lit pad again mutes the row. Pressed pad flashes white.
# Row 8 (fx.FX) = transition moves; a toggled move blinks blue, pressing it again releases it. The moves row is on every page.
# Top-row Drums / Keys / User buttons (CC 96/97/98) = MiniLab program: drums + mix map (minilab.py) / Synths (acid.py) /
# Acid Env (acid.py env: filter + amp ADSR).
# Top-row arrows left/right (CC 93/94) = previous/next page (sections.PAGES: 1 Lowdown, 2 Time Out Of Mind, 3 Synths). A page turn changes
# only the pads, never the sound; each page remembers what its rows play. Lit arrow = there is a page that way.
# Page 3 Synths (synths.py): acid patterns / moves, held fills, arp dir / oct / interval, auto change; the moves row acts on the song last shown.
# MIDI only plus one MCP batch per press; sections.py and fx.py are reloaded per press. Stops when pads.stop exists. Log: pads.log.
import os, sys, time, threading, traceback, importlib, subprocess, mido
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
LOG = open(os.path.join(here, 'pads.log'), 'a', buffering=1); sys.stderr = LOG
import sections, fx, synths
STOP = os.path.join(here, 'pads.stop')
state = {'on': [{} for _ in sections.PAGES], 'page': 0, 'busy': False, 'fx': set(), 'gen': 0, 'dgen': 0, 'snap': None, 'hw': False, 'swept': [], 'tgen': 0, 'hush': {}, 'bank': 0, 'saved': {}, 'agen': 0, 'machine': True, 'fgen': 0, 'fading': False, 'acts': 0,
         'song': 0, 'held': set(), 'auto': set(), 'phrase': 8, 'egen': {}, 'edir': {}, 'slit': set(), 'down': set()}   # egen / edir: per entry move (acid, arp)
HUSH = {'drums only': (1, 2, 3, 5, 6), 'no drums': (0, 4)}       # Mixer strips each move silences: drums only = Acid, decks A/B,
                                                                 # Acid Voice, Triple; no drums = My lil Drums + the drum stem
lp = lambda names, pre: next((x for x in names if x.startswith(pre)), None)        # Launchpad unplugged -> page only
lock = threading.Lock()                                          # Launchpad sends AND closes happen under it: send on a closed rtmidi port = segfault
PROG = mido.Message('sysex', data=[0x00, 0x20, 0x29, 0x02, 0x0D, 0x0E, 0x01])   # Launchpad Mini MK3 -> Programmer mode (a power-cycled one boots in Live mode)
try: out = lp(mido.get_output_names(), 'MIDIOUT2 (LPMiniMK3'); out = out and mido.open_output(out)
except Exception as e: out = None; LOG.write(time.ctime() + f' launchpad output open failed: {e}; the 5 s refresh retries\n')
state['hw'] = bool(out)
def lp_send(msg):                                               # every Launchpad send goes through here: a lost port (Windows re-enumerates
    global out                                                  # MIDI when another device is replugged) must not kill pads.py; the 5 s refresh reopens it
    with lock:
        o = out
        if not o: return
        try: o.send(msg); return
        except Exception as e:
            out = None; state['hw'] = False                     # out goes None BEFORE the close, inside the lock: nobody can send on a closed port
            LOG.write(time.ctime() + f' launchpad output lost: {e}; retrying\n')
            try: o.close()
            except Exception: pass
def led(note, vel, ch=0): lp_send(mido.Message('note_on', channel=ch, note=note, velocity=vel))
lp_send(PROG)
R = lambda: sections.PAGES[state['page']]['rows']                # rows of the page on show
ON = lambda: state['on'][state['page']]                          # row -> playing index, for that page
SYN = lambda: bool(sections.PAGES[state['page']].get('synth'))    # the Synths page on show
SP = lambda: state['song']                                        # the song the moves act on: the song page last shown
HOLD = ('fill', 'roll', 'octjump')                                # Synths pads that act while held (a page click toggles)
HOLDL = threading.RLock()                                        # hold on / let go one at a time (RLock: synth_act calls let_go)
ELOCK = threading.Lock()                                         # acid / arp entry: generation bump + direction, and a run's end check
ARROWS = {93: -1, 94: 1}                                         # top row: left / right arrow (programmer mode CC)
MACHINE_CC = 29                                                  # right column, round button at the end of the drums row
def machine():                                                  # My lil Drums on / off, apart from the tracked drums (stem row)
    import maps; state['machine'] = maps.drum_machine(); LOG.write(time.ctime() + f" drum machine {'on' if state['machine'] else 'off'}\n"); paint(); return state['machine']
MOVES = lambda: fx.BANKS[state['bank']]                           # moves row: bank 1 (fx.FX) or bank 2 (fx.FX2), flipped by fx.BANK_CC
def flip():                                                     # the round button at the end of the moves row: next bank of moves
    state['bank'] = (state['bank'] + 1) % len(fx.BANKS); LOG.write(time.ctime() + f" moves bank {state['bank'] + 1}\n"); paint(); return True
MODE_CC = {96: 'mix', 97: 'acid', 98: 'env'}                     # top row Drums / Keys / User buttons: MiniLab = drums + mix map / Synths / Acid Env
MODEF = os.path.join(here, 'minilab.mode')
MODE_LOCK = threading.Lock()                                     # one MiniLab swap at a time: never two acid.py
state.update(mreq=0, mrun=None)                                  # mreq = latest mode press; mrun = program go() last launched (None = unknown)
def mode_now():
    try: return open(MODEF).read().strip()
    except OSError: return ''
def minilab(m):                                                 # swap (or restart, e.g. after plugging it in) the MiniLab program
    if m not in MODE_CC.values(): return False                   # Windows lets one program hold the MiniLab
    open(MODEF, 'w').write(m)                                    # the page relabels at once, plugged in or not
    state['mreq'] += 1; n = state['mreq']
    def go():
        with MODE_LOCK:
            if state['mreq'] != n: return                        # a newer press is waiting: it does the swap (the last press wins)
            f = lambda x: os.path.join(here, x)
            if state['mrun'] != 'mix':                           # an acid.py may run: it lets go (note-offs, sequencer back on), removes acid.stop
                open(f('acid.stop'), 'w').close()                # (from mix there is none; acid.py itself stops minilab.py via minilab.stop)
                for _ in range(8):
                    if not os.path.exists(f('acid.stop')): break
                    time.sleep(0.25)
            for x in ('acid.stop', 'minilab.stop'):              # stale stop files would end the new program at once
                if os.path.exists(f(x)): os.remove(f(x))
            logf = f('minilab.log' if m == 'mix' else 'acid.log'); n0 = os.path.getsize(logf) if os.path.exists(logf) else 0
            p = subprocess.Popen([sys.executable, 'minilab.py'] if m == 'mix' else [sys.executable, 'acid.py', m], cwd=here)
            state['mrun'] = m; LOG.write(time.ctime() + f' minilab -> {m}\n')
            for _ in range(16):                                  # LED once the new program is up (first log line) or has given up
                if p.poll() is not None or (os.path.exists(logf) and os.path.getsize(logf) > n0): break
                time.sleep(0.25)
            paint()
    threading.Thread(target=go, daemon=True).start(); return True
def pad(note):                                                  # note -> (row base, sample index) or None
    if SYN(): return None
    for b, r in R().items():
        if b <= note < b + len(r['samples']): return b, note - b
def paint():
    for n in range(11, 90): led(n, 0)
    if SYN():                                                    # Synths page: what is live now (or held) blinks, like the sample rows
        lit = state['slit'] | state['held']
        for n in synths.pads(SP()):
            if n in lit: led(n, 0); led(n, 45, ch=1)
            else: led(n, synths.ROWS[n // 10 * 10 + 1][1])
    for b, r in R().items():
        for i in range(len(r['samples'])):
            if ON().get(b) == i: led(b + i, 0); led(b + i, 45, ch=1)    # engaged: blinks blue (ch 1 alternates with the ch 0 colour, off)
            else: led(b + i, r['color'])
    for n, name in MOVES().items():
        if name in state['fx']: led(n, 0); led(n, 45, ch=1)
        else: led(n, fx.COLOR)
    cc_ = lambda c, v: lp_send(mido.Message('control_change', control=c, value=v))
    cc_(fx.BANK_CC, fx.COLOR if state['bank'] else 1)           # lit = bank 2
    cc_(MACHINE_CC, 13 if state['machine'] else 1)              # yellow = machine on
    for cc, d in ARROWS.items(): cc_(cc, 3 if 0 <= state['page'] + d < len(sections.PAGES) else 0)
    for cc, m in MODE_CC.items(): cc_(cc, 37 if mode_now() == m else 1)   # the MiniLab mode on show: lit cyan, the others dim
def turn(d):                                                    # arrow: next / previous page (pads only)
    p = state['page'] + d
    if not 0 <= p < len(sections.PAGES) or state['busy']: return False
    state['page'] = p
    if SYN():                                                    # what is live on the Synths page: read in a thread (3 Rack reads), then lit
        def look():
            try: state['slit'] = synths.lit(state)
            except Exception: LOG.write(traceback.format_exc())  # keeps the old slit
            paint()
        threading.Thread(target=look, daemon=True).start()
    else:
        state['song'] = p
        threading.Thread(target=lambda: synths.follow(SP), daemon=True).start()     # the arp's keys follow the song (last song shown wins)
    open(os.path.join(here, 'page.txt'), 'w').write(str(SP()))   # the MiniLab (minilab.py, page) follows the song, not the Synths page
    LOG.write(time.ctime() + f" page {p + 1} {sections.PAGES[p]['name']}\n"); paint(); return True
def sweep(to, gen, decks):                                      # the song's decks: base -> target over SWEEP_SECS, stops if another move takes over
    n = int(fx.SWEEP_SECS / fx.STEP)
    for k in range(1, n + 1):
        if state['gen'] != gen: return
        for d in decks: fx.set_deck_filters(d, [b + (to - b) * k / n for b in fx.BASEF[d]])
        time.sleep(fx.STEP)
def fx_act(name):
    if name in ('sweep up', 'sweep down'):
        state['gen'] += 1
        if name in state['fx']:                                   # release = snap back (the drop)
            state['fx'].discard(name)
            for d in state['swept']: fx.set_deck_filters(d, fx.BASEF[d])
        else:                                                     # only the song on show (page 1 Lowdown, page 2 TOOM)
            decks = fx.song_decks(SP(), state['on'])
            for d in set(state['swept']) - set(decks): fx.set_deck_filters(d, fx.BASEF[d])
            state['fx'] -= {'sweep up', 'sweep down'}; state['fx'].add(name); state['swept'] = decks
            threading.Thread(target=sweep, args=(fx.HP if name == 'sweep up' else fx.LP, state['gen'], decks), daemon=True).start()
    elif name == 'reverse':                                       # the song on show; release un-reverses the same song after a page turn
        if name in state['fx']: fx.reverse(False, [state['saved'].pop(name, fx.own_deck(SP()))]); state['fx'].discard(name)
        else: d = state['saved'][name] = fx.own_deck(SP()); fx.reverse(True, [d]); state['fx'].add(name)
    elif name in HUSH:                                            # release puts each strip back where it was
        if name in state['fx']: state['fx'].discard(name); fx.set_strip_map(state['hush'].pop(name, {}))
        else:
            cur = fx.strips(); state['hush'][name] = {k: cur[k] for k in HUSH[name]}; state['fx'].add(name)
            fx.set_strip_map({k: 0.0 for k in HUSH[name]})
    elif name == 'dnb':
        state['dgen'] += 1; g = state['dgen']; alive = lambda: state['dgen'] == g
        if name in state['fx']: state['fx'].discard(name); threading.Thread(target=fx.dnb_off, args=(state['snap'], alive), daemon=True).start()
        else:
            state['snap'] = fx.snapshot(); state['fx'].add(name)
            threading.Thread(target=fx.dnb_on, args=(state['snap'], alive), daemon=True).start()
    elif name == 'transition':                                    # hand over to the song on show over 8 bars; runs once, blinks while it runs
        if name in state['fx']: return
        state['tgen'] += 1; g = state['tgen']; state['fx'].add(name)
        def run():
            try: done = fx.transition(SP(), state['on'], lambda: state['tgen'] == g)
            except Exception: LOG.write(traceback.format_exc()); done = False
            state['fx'].discard(name); LOG.write(time.ctime() + f" transition to {sections.PAGES[SP()]['name']} {'done' if done else 'cut off'}\n"); paint()
        threading.Thread(target=run, daemon=True).start()
    elif name in fx.STRIP_TOGGLE:                                  # in / out; lit = in. Out remembers the level, in puts it back
        k, dflt = fx.STRIP_TOGGLE[name]; cur = fx.strips()[k]
        if name in synths.ENTRY:                                   # acid / arp come in and go out melodically over 2 bars (synths.ENTRY)
            with ELOCK:
                g = state['egen'][name] = state['egen'].get(name, 0) + 1; alive = lambda: state['egen'][name] == g   # per voice: only a newer
                go_in, go_out = synths.ENTRY[name]                 # press of this move cancels it; the cancelled run hands the knob over
                was = state['edir'].get(name)                      # a run still in flight: this press reverses it (during an out ramp
                out_ = was == 'in' if was else cur > 0.001         # the strip is still up, so the strip alone would say "out" again)
                state['edir'][name] = 'out' if out_ else 'in'
            def run(fn, *a):
                try: fn(*a)
                except Exception: LOG.write(traceback.format_exc())
                finally:
                    with ELOCK:
                        if state['egen'][name] == g: state['edir'].pop(name, None)   # a cancelled run leaves the newer run's direction alone
            if name == 'acid in/out' and 'acid sweep' in state['fx']: release('acid sweep')   # one owner of the cutoff: the sweep snaps back first
            if out_:
                if cur > 0.001: state['saved'][name] = cur
                state['fx'].discard(name); threading.Thread(target=run, args=(go_out, alive), daemon=True).start()
            else: state['fx'].add(name); threading.Thread(target=run, args=(go_in, state['saved'].get(name, dflt), alive), daemon=True).start()
        elif cur > 0.001: state['saved'][name] = cur; fx.set_strip_map({k: 0.0}); state['fx'].discard(name)
        else: fx.set_strip_map({k: state['saved'].get(name, dflt)}); state['fx'].add(name)
    elif name == 'acid sweep' and 'acid in/out' in state['edir']:   # an acid entry owns the cutoff while it ramps
        LOG.write(time.ctime() + ' acid sweep ignored: acid in/out still ramping\n')
    elif name == 'acid sweep':                                    # Acid cutoff up over SWEEP_SECS; press again = snap back
        state['agen'] += 1; g = state['agen']
        if name in state['fx']: release(name)
        else:
            c0 = state['saved'][name] = fx.acid_cutoff(); state['fx'].add(name)
            def up():
                n = int(fx.SWEEP_SECS / fx.STEP)
                for i in range(1, n + 1):
                    if state['agen'] != g: return
                    fx.acid_cutoff(c0 + (1.0 - c0) * i / n); time.sleep(fx.STEP)
            threading.Thread(target=up, daemon=True).start()
    elif name == 'break fill':                                    # 2 bars of the break (My lil Drums pattern fx.BREAK), then the beat before
        if name in state['fx']: return
        state['fx'].add(name); p0 = sections.current_drum_pattern(); sections.drum_pattern(fx.BREAK)
        def back():
            time.sleep(fx.bars_secs(2)); sections.drum_pattern(p0); state['fx'].discard(name); paint()
        threading.Thread(target=back, daemon=True).start()
    elif name in fx.SLOT_TOGGLE:                                  # mute that part of the song on show; lit = muted
        if name in state['fx']: release(name)
        else:
            d, k = fx.own_deck(SP()), fx.SLOT_TOGGLE[name]
            state['saved'][name] = (d, k, fx.slot_level(d, k)); fx.slot_level(d, k, 0.0); state['fx'].add(name)
    elif name == 'breakdown':                                     # drums out + the song on show low-passed; press again = as before
        if name in state['fx']: release(name)
        else:
            d = fx.own_deck(SP()); cur = fx.strips()
            state['saved'][name] = (d, fx.deck_filters(d), {k: cur[k] for k in (0, 4)})
            fx.set_strip_map({0: 0.0, 4: 0.0}); fx.set_deck_filters(d, [fx.BREAKDOWN_LP] * 4); state['fx'].add(name)
    elif name == 'drums in/out':                                  # tracked drums (deck C strip) fade out / in over FADE_BARS; lit = in
        state['fgen'] += 1; g = state['fgen']; cur = fx.strips()[4]
        if name in state['fx']:                                   # out: remember the level unless a fade was already moving it
            if not state['fading']: state['saved'][name] = cur
            to = 0.0; state['fx'].discard(name)
        else: to = state['saved'].get(name) or sections.U; state['fx'].add(name)
        def fade():
            state['fading'] = True; secs = fx.bars_secs(fx.FADE_BARS); t0 = time.time()
            while state['fgen'] == g:
                x = min(1.0, (time.time() - t0) / secs); e = x * x * (3 - 2 * x)
                fx.set_strip_map({4: cur + (to - cur) * e})
                if x >= 1.0: state['fading'] = False; break
                time.sleep(fx.STEP)
        threading.Thread(target=fade, daemon=True).start()
    elif name == 'clean':
        state['fgen'] += 1; state['fading'] = False
        for n in ('acid sweep', 'no bass', 'no vocals', 'breakdown'):
            if n in state['fx']: release(n)
        state['gen'] += 1; state['tgen'] += 1
        if 'dnb' in state['fx']: state['dgen'] += 1; fx.restore(state['snap'])   # snap back to the tempo from before, strips + drum pattern as before
        for n in list(state['hush']): fx.set_strip_map(state['hush'].pop(n))
        fx.clean(); state['fx'] = set()
    LOG.write(time.ctime() + f" fx {name} -> {sorted(state['fx'])}\n")
def release(name):                                              # put a bank-2 move back the way it found things
    s = state['saved'].pop(name, None); state['fx'].discard(name)
    if s is None: return
    if name == 'acid sweep': state['agen'] += 1; fx.acid_cutoff(s)
    elif name in fx.SLOT_TOGGLE: fx.slot_level(s[0], s[1], s[2])
    elif name == 'breakdown': fx.set_deck_filters(s[0], s[1]); fx.set_strip_map(s[2])
def synth_act(note, hw=False):                                  # a Synths pad: one action, a held fill, or an auto setting
    label, kind, arg = synths.pads(SP())[note]
    if kind in HOLD:
        with HOLDL:                                              # a legato slide's let_go waits until this pad is in held
            if note in state['held']: return let_go(note)        # second click on the page = let go
            s = synths.hold(kind, arg, True); state['saved'][note] = s
            state['held'].add(note)                              # after the on: a release before this line finds nothing held ...
            if hw and note not in state['down']: return let_go(note)   # ... and is caught here (quick stab: the pad is already up)
    elif kind == 'auto': state['auto'] ^= {arg}
    elif kind == 'phrase': state['phrase'] = arg
    else: synths.do(kind, arg)
    try: state['slit'] = synths.lit(state)
    except Exception: LOG.write(traceback.format_exc())
    LOG.write(time.ctime() + f" synths {label} held {sorted(state['held'])} auto {sorted(state['auto'])} phrase {state['phrase']}\n")
def let_go(note):                                               # Launchpad note off on a held pad, or its second click
    with HOLDL:                                                  # one hold change at a time: a slide's off never lands after the next pad's on
        try: state['held'].remove(note)                          # atomic claim: two let_go calls for one hold, only one acts
        except KeyError: return
        s = state['saved'].pop(note, None)
        try:
            P = synths.pads(SP()); label, kind, arg = P[note]
            same = [n for n in sorted(state['held']) if P[n][1] == kind]   # another held pad on the same hold button (slide between fills)
            if not same: synths.hold(kind, arg, False, s)        # the last one off lets go (octjump: puts the octave back)
            elif kind != 'octjump': synths.hold(kind, P[same[-1]][2], True)   # the one still held keeps going
        except Exception:                                        # off failed: still held, the next press or release tries again
            LOG.write(traceback.format_exc()); state['saved'][note] = s; state['held'].add(note); paint(); return
    try: state['slit'] = synths.lit(state)                       # octjump puts the octave back: its oct pad lights again
    except Exception: LOG.write(traceback.format_exc())
    LOG.write(time.ctime() + f" synths {label} let go" + (f", {P[same[-1]][0]} still held" if same else '') + '\n'); paint()
def act(note, hw=False):
    try:
        importlib.reload(sections); importlib.reload(fx)            # not synths: a reload would swap ARP_LOCK and drop _open under running threads
        if note in MOVES(): fx_act(MOVES()[note])
        elif SYN(): synth_act(note, hw)
        else:
            rows, on = R(), ON(); b, i = pad(note); r = rows[b]
            i = None if on.get(b) == i else i                          # lit pad again = mute the row
            sections.play(r['slot'], r['samples'][i] if i is not None else None, r['level'], r.get('deck')); on[b] = i
            for pg, pon in zip(sections.PAGES, state['on']):             # rows sharing this deck slot, on any page, are no longer playing
                for o, ro in pg['rows'].items():
                    if ro is not r and ro['slot'] == r['slot'] and ro.get('deck') == r.get('deck') and i is not None: pon[o] = None
            LOG.write(time.ctime() + f" {r['name']} " + (os.path.basename(r['samples'][i]) if i is not None else 'muted') + '\n')
    except Exception: LOG.write(traceback.format_exc())
    state['acts'] += 1; state['busy'] = False; paint()
def press(note, hw=False):                                      # hardware pad (hw) or a click on the page (board.py): same path
    if not (pad(note) or note in MOVES() or (SYN() and note in synths.pads(SP()))): return False
    led(note, 3); led(note, 3, ch=1)
    if state['busy']: return False
    state['busy'] = True; threading.Thread(target=act, args=(note, hw), daemon=True).start(); return True
def on_msg(msg):
    if msg.type == 'note_on' and msg.velocity:
        if SYN(): state['down'].add(msg.note)                    # Synths pads physically down (a song-page pad is not tracked)
        press(msg.note, True)
    elif msg.type in ('note_on', 'note_off'):                    # release: lets go of a held pad pressed on the Synths page
        was = msg.note in state['down']; state['down'].discard(msg.note)   # (a song-page pad 61 never lets go of a page-held fill)
        if msg.note in state['held'] and (SYN() or was): threading.Thread(target=let_go, args=(msg.note,), daemon=True).start()
    elif msg.type == 'control_change' and msg.value and msg.control in ARROWS: turn(ARROWS[msg.control])
    elif msg.type == 'control_change' and msg.value and msg.control in MODE_CC: minilab(MODE_CC[msg.control])
    elif msg.type == 'control_change' and msg.value and msg.control == fx.BANK_CC: flip()
    elif msg.type == 'control_change' and msg.value and msg.control == MACHINE_CC: threading.Thread(target=machine, daemon=True).start()
open(os.path.join(here, 'page.txt'), 'w').write('0')
try: sections.base(); state['on'] = [sections.now(p['rows']) if p['rows'] else {} for p in sections.PAGES]
except Exception: LOG.write(traceback.format_exc())
def _scale():
    try: synths.follow(SP)
    except Exception: LOG.write(traceback.format_exc())
threading.Thread(target=_scale, daemon=True).start()           # the arp's keys follow the page on show (own thread: a slow arp must not hold startup)
try: inp = lp(mido.get_input_names(), 'LPMiniMK3 MIDI'); inp = inp and mido.open_input(inp, callback=on_msg)
except Exception as e: inp = None; LOG.write(time.ctime() + f' launchpad input open failed: {e}; the 5 s refresh retries\n')
def auto_loop():                                                # phrase auto-change: one small move per phrase per enabled voice
    t0 = time.time()                                            # (roughly bar-aligned: the Acid takes a pattern at its pattern end,
    while not os.path.exists(STOP):                             # the arp a change on its next step)
        try: secs = fx.bars_secs(state['phrase'])               # absolute grid: a slow step does not push the next phrase later
        except Exception: secs = 16.0
        t0 += secs
        if t0 < time.time(): t0 = time.time()                    # missed a whole phrase (Rack stalled): fire now, grid from here
        while time.time() < t0 and not os.path.exists(STOP): time.sleep(0.25)
        if state['auto'] and not state['held'] and not state['busy'] and 'dnb' not in state['fx']:
            try:
                did = synths.auto_step(SP(), set(state['auto']))
                LOG.write(time.ctime() + ' auto ' + ', '.join(did) + '\n')
                if SYN(): state['slit'] = synths.lit(state); paint()
            except Exception: LOG.write(traceback.format_exc())
threading.Thread(target=auto_loop, daemon=True).start()
import board; board.start(press, state, turn, minilab, flip, machine)
LOG.write(time.ctime() + f" start rows {state['on']} fx row {list(fx.FX.values())} launchpad {'on' if out else 'missing: page only'}"
          f" page http://127.0.0.1:{board.PORT}\n")
try: paint()
except Exception: LOG.write(traceback.format_exc())
t = time.time()
while not os.path.exists(STOP):
    time.sleep(0.25)
    if time.time() - t > 5:                                      # re-read the rig: rows brought in or out elsewhere (MiniLab, page
        stale = not out                                          # output lost = the USB / MIDI stack changed: the input is suspect too
        if stale:                                                # reopen the output when it is back (failure = wait for the next refresh)
            try:
                nm = lp(mido.get_output_names(), 'MIDIOUT2 (LPMiniMK3')
                if nm:
                    new = mido.open_output(nm)                   # outside the lock; only the swap is inside
                    with lock: out = new; state['hw'] = True
                    LOG.write(time.ctime() + ' launchpad output back\n'); lp_send(PROG)
                    try: paint()
                    except Exception: LOG.write(traceback.format_exc())
            except Exception: pass
        try:                                                     # input: reopen when missing, when the output was lost, or when its name left the port list
            names = mido.get_input_names()
            if inp is None or stale or getattr(inp, 'name', None) not in names:
                if inp is not None:
                    try: inp.close()
                    except Exception: pass
                    inp = None; LOG.write(time.ctime() + ' launchpad input lost; retrying\n')
                nm = lp(names, 'LPMiniMK3 MIDI')
                if nm: inp = mido.open_input(nm, callback=on_msg); state['inp_err'] = None; LOG.write(time.ctime() + ' launchpad input back\n')
        except Exception as e:
            if state.get('inp_err') != str(e): state['inp_err'] = str(e); LOG.write(time.ctime() + f' launchpad input reopen failed: {e}\n')
        try:                                                    # faders, Rack itself) light up or go dark on both pages too
            n0 = state['acts']; fresh = [sections.now(p['rows']) if p['rows'] else {} for p in sections.PAGES]
            if not state['busy'] and state['acts'] == n0: state['on'] = fresh   # a press during the read wins: that snapshot is stale
            state['machine'] = next(x['value'] for x in sections.json.loads(sections.call('vcvrack_get_params', {'moduleId': sections.DRUMS})) if x['id'] == 5) > 0.001
            cur = fx.strips()                                    # in/out moves lit by what the strips really are
            for name, (k, _) in list(fx.STRIP_TOGGLE.items()) + ([('drums in/out', (4, 0))] if not state['fading'] else []):
                if name in state['edir']: continue               # an entry still ramping: its press set the light (an out keeps the strip up)
                state['fx'] = (state['fx'] | {name}) if cur[k] > 0.001 else (state['fx'] - {name})
            if SYN(): state['slit'] = synths.lit(state)              # Synths page: lit by what the arp + acid really are (MiniLab, Rack)
        except Exception: LOG.write(traceback.format_exc())
        try: paint()
        except Exception: LOG.write(traceback.format_exc())
        t = time.time()
try: inp and inp.close()
except Exception: pass
for n in range(11, 90): led(n, 0)
with lock: o, out = out, None
try: o and o.close()
except Exception: pass
