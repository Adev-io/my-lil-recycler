# Launchpad Mini MK3 (Programmer mode) -> the set by rows. Each row in sections.ROWS = one slot (row 1 vocals, row 2 keys ...):
# a pad picks that row's sample (blinking blue = playing), the lit pad again mutes the row. Pressed pad flashes white.
# Row 8 (fx.FX) = transition moves; a toggled move blinks blue, pressing it again releases it. The moves row is on every page.
# Top-row Drums / Keys buttons (CC 96/97) = MiniLab program: drums + mix map (minilab.py) / Synths (acid.py).
# Top-row arrows left/right (CC 93/94) = previous/next page (sections.PAGES: 1 Lowdown, 2 Time Out Of Mind). A page turn changes
# only the pads, never the sound; each page remembers what its rows play. Lit arrow = there is a page that way.
# MIDI only plus one MCP batch per press; sections.py and fx.py are reloaded per press. Stops when pads.stop exists. Log: pads.log.
import os, sys, time, threading, traceback, importlib, subprocess, mido
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
LOG = open(os.path.join(here, 'pads.log'), 'a', buffering=1); sys.stderr = LOG
import sections, fx, synths
STOP = os.path.join(here, 'pads.stop')
state = {'on': [{} for _ in sections.PAGES], 'page': 0, 'busy': False, 'fx': set(), 'gen': 0, 'dgen': 0, 'snap': None, 'hw': False, 'swept': [], 'tgen': 0, 'hush': {}, 'bank': 0, 'saved': {}, 'agen': 0, 'machine': True, 'fgen': 0, 'fading': False, 'acts': 0}
HUSH = {'drums only': (1, 2, 3, 5, 6), 'no drums': (0, 4)}       # Mixer strips each move silences: drums only = Acid, decks A/B,
                                                                 # Acid Voice, Triple; no drums = My lil Drums + the drum stem
lp = lambda names, pre: next((x for x in names if x.startswith(pre)), None)        # Launchpad unplugged -> page only
out = lp(mido.get_output_names(), 'MIDIOUT2 (LPMiniMK3'); out = out and mido.open_output(out); state['hw'] = bool(out)
lock = threading.Lock()
def lp_send(msg):                                               # every Launchpad send goes through here: a lost port (Windows re-enumerates
    global out                                                  # MIDI when another device is replugged) must not kill pads.py; the 5 s refresh reopens it
    o = out
    if not o: return
    try:
        with lock: o.send(msg)
    except Exception as e:
        try: o.close()
        except Exception: pass
        if out is o:                                            # several threads can fail on the same port: log once
            out = None; state['hw'] = False; LOG.write(time.ctime() + f' launchpad output lost: {e}; retrying\n')
def led(note, vel, ch=0): lp_send(mido.Message('note_on', channel=ch, note=note, velocity=vel))
R = lambda: sections.PAGES[state['page']]['rows']                # rows of the page on show
ON = lambda: state['on'][state['page']]                          # row -> playing index, for that page
ARROWS = {93: -1, 94: 1}                                         # top row: left / right arrow (programmer mode CC)
MACHINE_CC = 29                                                  # right column, round button at the end of the drums row
def machine():                                                  # My lil Drums on / off, apart from the tracked drums (stem row)
    import maps; state['machine'] = maps.drum_machine(); LOG.write(time.ctime() + f" drum machine {'on' if state['machine'] else 'off'}\n"); paint(); return state['machine']
MOVES = lambda: fx.BANKS[state['bank']]                           # moves row: bank 1 (fx.FX) or bank 2 (fx.FX2), flipped by fx.BANK_CC
def flip():                                                     # the round button at the end of the moves row: next bank of moves
    state['bank'] = (state['bank'] + 1) % len(fx.BANKS); LOG.write(time.ctime() + f" moves bank {state['bank'] + 1}\n"); paint(); return True
MODE_CC = {96: 'mix', 97: 'acid'}                                # top row Drums / Keys buttons: MiniLab = drums + mix map / Synths
MODEF = os.path.join(here, 'minilab.mode')
def mode_now():
    try: return open(MODEF).read().strip()
    except OSError: return ''
def minilab(m):                                                 # swap (or restart, e.g. after plugging it in) the MiniLab program
    if m not in MODE_CC.values(): return False                   # Windows lets one program hold the MiniLab
    open(MODEF, 'w').write(m)                                    # the page relabels at once, plugged in or not
    def go():
        f = lambda n: os.path.join(here, n)
        open(f('acid.stop'), 'w').close()                        # acid.py lets go (note-offs, sequencer back on) and removes acid.stop
        for _ in range(8):
            if not os.path.exists(f('acid.stop')): break
            time.sleep(0.25)
        for n in ('acid.stop', 'minilab.stop'):                  # stale stop files would end the new program at once
            if os.path.exists(f(n)): os.remove(f(n))
        subprocess.Popen([sys.executable, 'minilab.py' if m == 'mix' else 'acid.py'], cwd=here)   # acid.py stops minilab.py itself
        LOG.write(time.ctime() + f' minilab -> {m}\n'); time.sleep(1.0); paint()
    threading.Thread(target=go, daemon=True).start(); return True
def pad(note):                                                  # note -> (row base, sample index) or None
    for b, r in R().items():
        if b <= note < b + len(r['samples']): return b, note - b
def paint():
    for n in range(11, 90): led(n, 0)
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
    for cc, m in MODE_CC.items(): cc_(cc, 37 if mode_now() == m else 1)   # the MiniLab mode on show: lit cyan, the other dim
def turn(d):                                                    # arrow: next / previous page (pads only)
    p = state['page'] + d
    if not 0 <= p < len(sections.PAGES) or state['busy']: return False
    state['page'] = p; open(os.path.join(here, 'page.txt'), 'w').write(str(p))   # the MiniLab (minilab.py, page) follows it
    threading.Thread(target=lambda: synths.follow(lambda: state['page']), daemon=True).start()     # the arp's keys follow the song
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
            decks = fx.song_decks(state['page'], state['on'])
            for d in set(state['swept']) - set(decks): fx.set_deck_filters(d, fx.BASEF[d])
            state['fx'] -= {'sweep up', 'sweep down'}; state['fx'].add(name); state['swept'] = decks
            threading.Thread(target=sweep, args=(fx.HP if name == 'sweep up' else fx.LP, state['gen'], decks), daemon=True).start()
    elif name == 'reverse':                                       # the song on show; release un-reverses the same song after a page turn
        if name in state['fx']: fx.reverse(False, [state['saved'].pop(name, fx.own_deck(state['page']))]); state['fx'].discard(name)
        else: d = state['saved'][name] = fx.own_deck(state['page']); fx.reverse(True, [d]); state['fx'].add(name)
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
            try: done = fx.transition(state['page'], state['on'], lambda: state['tgen'] == g)
            except Exception: LOG.write(traceback.format_exc()); done = False
            state['fx'].discard(name); LOG.write(time.ctime() + f" transition to {sections.PAGES[state['page']]['name']} {'done' if done else 'cut off'}\n"); paint()
        threading.Thread(target=run, daemon=True).start()
    elif name in fx.STRIP_TOGGLE:                                  # in / out; lit = in. Out remembers the level, in puts it back
        k, dflt = fx.STRIP_TOGGLE[name]; cur = fx.strips()[k]
        if cur > 0.001: state['saved'][name] = cur; fx.set_strip_map({k: 0.0}); state['fx'].discard(name)
        else: fx.set_strip_map({k: state['saved'].get(name, dflt)}); state['fx'].add(name)
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
            d, k = fx.own_deck(state['page']), fx.SLOT_TOGGLE[name]
            state['saved'][name] = (d, k, fx.slot_level(d, k)); fx.slot_level(d, k, 0.0); state['fx'].add(name)
    elif name == 'breakdown':                                     # drums out + the song on show low-passed; press again = as before
        if name in state['fx']: release(name)
        else:
            d = fx.own_deck(state['page']); cur = fx.strips()
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
        if 'dnb' in state['fx']: state['dgen'] += 1; fx.restore(state['snap'])   # snap back to 120, strips + drum pattern as before
        for n in list(state['hush']): fx.set_strip_map(state['hush'].pop(n))
        fx.clean(); state['fx'] = set()
    LOG.write(time.ctime() + f" fx {name} -> {sorted(state['fx'])}\n")
def release(name):                                              # put a bank-2 move back the way it found things
    s = state['saved'].pop(name, None); state['fx'].discard(name)
    if s is None: return
    if name == 'acid sweep': state['agen'] += 1; fx.acid_cutoff(s)
    elif name in fx.SLOT_TOGGLE: fx.slot_level(s[0], s[1], s[2])
    elif name == 'breakdown': fx.set_deck_filters(s[0], s[1]); fx.set_strip_map(s[2])
def act(note):
    try:
        importlib.reload(sections); importlib.reload(fx)
        if note in MOVES(): fx_act(MOVES()[note])
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
def press(note):                                                # hardware pad or a click on the page (board.py): same path
    if not (pad(note) or note in MOVES()): return False
    led(note, 3); led(note, 3, ch=1)
    if state['busy']: return False
    state['busy'] = True; threading.Thread(target=act, args=(note,), daemon=True).start(); return True
def on_msg(msg):
    if msg.type == 'note_on' and msg.velocity: press(msg.note)
    elif msg.type == 'control_change' and msg.value and msg.control in ARROWS: turn(ARROWS[msg.control])
    elif msg.type == 'control_change' and msg.value and msg.control in MODE_CC: minilab(MODE_CC[msg.control])
    elif msg.type == 'control_change' and msg.value and msg.control == fx.BANK_CC: flip()
    elif msg.type == 'control_change' and msg.value and msg.control == MACHINE_CC: threading.Thread(target=machine, daemon=True).start()
open(os.path.join(here, 'page.txt'), 'w').write('0')
try: sections.base(); state['on'] = [sections.now(p['rows']) for p in sections.PAGES]
except Exception: LOG.write(traceback.format_exc())
def _scale():
    try: synths.follow(lambda: state['page'])
    except Exception: LOG.write(traceback.format_exc())
threading.Thread(target=_scale, daemon=True).start()           # the arp's keys follow the page on show (own thread: a slow arp must not hold startup)
inp = lp(mido.get_input_names(), 'LPMiniMK3 MIDI'); inp = inp and mido.open_input(inp, callback=on_msg)
import board; board.start(press, state, turn, minilab, flip, machine)
LOG.write(time.ctime() + f" start rows {state['on']} fx row {list(fx.FX.values())} launchpad {'on' if out else 'missing: page only'}"
          f" page http://127.0.0.1:{board.PORT}\n"); paint(); t = time.time()
while not os.path.exists(STOP):
    time.sleep(0.25)
    if time.time() - t > 5:                                      # re-read the rig: rows brought in or out elsewhere (MiniLab, page
        if not out:                                              # Launchpad output lost: reopen when it is back (failure = wait for the next refresh)
            try:
                nm = lp(mido.get_output_names(), 'MIDIOUT2 (LPMiniMK3')
                if nm: out = mido.open_output(nm); state['hw'] = True; LOG.write(time.ctime() + ' launchpad output back\n'); paint()
            except Exception: pass
        try:                                                     # same for the input: gone from the port list = close, reopen when listed
            if inp is None or getattr(inp, 'name', None) not in mido.get_input_names():
                if inp is not None:
                    try: inp.close()
                    except Exception: pass
                    inp = None; LOG.write(time.ctime() + ' launchpad input lost; retrying\n')
                nm = lp(mido.get_input_names(), 'LPMiniMK3 MIDI')
                if nm: inp = mido.open_input(nm, callback=on_msg); LOG.write(time.ctime() + ' launchpad input back\n')
        except Exception: pass
        try:                                                    # faders, Rack itself) light up or go dark on both pages too
            n0 = state['acts']; fresh = [sections.now(p['rows']) for p in sections.PAGES]
            if not state['busy'] and state['acts'] == n0: state['on'] = fresh   # a press during the read wins: that snapshot is stale
            state['machine'] = next(x['value'] for x in sections.json.loads(sections.call('vcvrack_get_params', {'moduleId': sections.DRUMS})) if x['id'] == 5) > 0.001
            cur = fx.strips()                                    # in/out moves lit by what the strips really are
            for name, (k, _) in list(fx.STRIP_TOGGLE.items()) + ([('drums in/out', (4, 0))] if not state['fading'] else []):
                state['fx'] = (state['fx'] | {name}) if cur[k] > 0.001 else (state['fx'] - {name})
        except Exception: LOG.write(traceback.format_exc())
        paint(); t = time.time()
try: inp and inp.close()
except Exception: pass
for n in range(11, 90): led(n, 0)
try: out and out.close()
except Exception: pass
