# MiniLab 3 Synths mode: the Acid Bass plus the arp's gate and Triple's cutoff (replaces minilab.py while it runs: Windows lets one program hold the MiniLab).
# Keys: play the bass live (forwarded to 'loopMIDI Port 1' -> Rack MIDI to CV -> Acid Bass Play ins; acid_add.py patched it).
#   One octave down (middle C plays C2). Hold a key into the next = slide. Hit hard (velocity >= ACC_VEL) = accent.
#   While a key is held the sequencer stops; it starts again RESUME s after the last key is let go (back in step with the clock).
# Pads: bank A 1-8 = patterns 9-16 (I-B1..B8; pad 3 = 10 the Lowdown vamp, pad 7 = 14), bank B 1-8 = patterns 17-24 (pad 1 = walk-down).
# Faders: cutoff, resonance, env mod, decay.
#   Knobs: 1 accent, 2 volume, 3 gate length, 4 arp gate, 5 high-pass, 6 arp brightness (Triple cutoff), 7 transpose -12..+12 (the arp follows),
#   8 pattern length. Pickup: a control acts once it reaches Rack's value. Stop: acid.stop. Log: acid.log.
import os, sys, time, json, threading, traceback, mido
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
LOG = open(os.path.join(here, 'acid.log'), 'a', buffering=1); sys.stderr = LOG
import sections as S
ACID = S.ACID
STOP, MLSTOP = os.path.join(here, 'acid.stop'), os.path.join(here, 'minilab.stop')
OCT, ACC_VEL, RESUME = -12, 100, 2.0
TICK, REFRESH, TOL = 0.05, 1.0, 0.05
import maps                                   # the map lives in maps.py (shared with the virtual controller page)
MAP = dict(maps.ACID)                         # CC -> (module, param, scale, label): Acid Bass, the arp's gate, Triple's cutoff
TOLS = maps.ACID_TOLS                         # (module, param) -> pickup tolerance
pending, cur, prev, eng, held, lock = {}, {}, {}, set(), set(), threading.Lock()
seq = {'off': False, 'release': 0.0}
log = lambda s: LOG.write(time.ctime() + ' ' + s + '\n')
out = mido.open_output(next(x for x in mido.get_output_names() if x.startswith('loopMIDI Port 1')))
def on_msg(m):
    if m.type == 'control_change' and m.control in MAP:
        mod, pid, f, label = MAP[m.control]; v = f(m.value); k = (mod, pid); tol = TOLS.get(k, TOL)
        with lock:
            c, p = cur.get(k), prev.get(m.control)
            if m.control not in eng and (c is None or abs(v - c) <= tol or (p is not None and (p - c) * (v - c) < 0)):
                eng.add(m.control); log(f'picked up {label} at {v}')
            prev[m.control] = v
            if m.control in eng: pending[k] = v; cur[k] = v
    elif m.type in ('note_on', 'note_off') and m.channel == 9:
        if m.type == 'note_on' and m.velocity and 36 <= m.note <= 51:
            with lock: pending[(ACID, 24)] = 8 + m.note - 36
            log(f'pattern {9 + m.note - 36}')
    elif m.type in ('note_on', 'note_off') and m.channel == 0:
        n = max(0, min(127, m.note + OCT))
        if m.type == 'note_on' and m.velocity:
            out.send(mido.Message('note_on', note=n, velocity=127 if m.velocity >= ACC_VEL else 10))
            with lock:
                held.add(n)
                if not seq['off']: seq['off'] = True; pending[(ACID, 25)] = 0.0       # keys take over: sequencer stops
        else:
            out.send(mido.Message('note_off', note=n))
            with lock:
                held.discard(n)
                if not held: seq['release'] = time.time()
    elif m.type not in ('clock', 'active_sensing', 'polytouch', 'aftertouch'): log(f'unmapped {m}')
def refresh():                                # Rack's values; a control whose value moved elsewhere must be picked up again
    p = {}
    for mod in {mod for mod, *_ in MAP.values()}:   # one module missing or erroring must not stop the others
        try: p[mod] = {x['id']: x['value'] for x in json.loads(S.call('vcvrack_get_params', {'moduleId': mod}))}
        except Exception as e: log(f'refresh: module {mod} unavailable ({str(e)[:80]})')
    with lock:
        for cc, (mod, pid, _, label) in MAP.items():
            k = (mod, pid)
            if k in pending or mod not in p or pid not in p[mod]: continue
            if cc in eng and abs(p[mod][pid] - cur.get(k, p[mod][pid])) > TOLS.get(k, TOL) / 2: eng.discard(cc); log(f'dropped {label}')
            cur[k] = p[mod][pid]
def loop():
    t, failed = 0, set()
    while True:
        time.sleep(TICK)
        try:
            with lock:
                if seq['off'] and not held and time.time() - seq['release'] > RESUME: seq['off'] = False; pending[(ACID, 25)] = 1.0
                batch = dict(pending); pending.clear()
            for mod in {k[0] for k in batch}:
                items = {k: v for k, v in batch.items() if k[0] == mod}
                try: S.call('vcvrack_set_params', {'moduleId': mod, 'params': [{'id': pid, 'value': v} for (_, pid), v in items.items()]})
                except Exception as e:                          # keep the values for the next tick (newer ones win), log once per outage
                    with lock:
                        for k, v in items.items(): pending.setdefault(k, v)
                    if mod not in failed: log(f'set_params: module {mod} failed ({str(e)[:80]}), retrying')
                    failed.add(mod)
                else: failed.discard(mod)
            if time.time() - t > REFRESH:
                try: refresh()
                finally: t = time.time()
        except Exception: LOG.write(traceback.format_exc())
open(MLSTOP, 'w').close(); time.sleep(1.5)    # minilab.py lets go of the MiniLab
inp = None
for _ in range(20):
    try: inp = mido.open_input(next(x for x in mido.get_input_names() if x.startswith('Minilab3 MIDI')), callback=on_msg); break
    except Exception: time.sleep(0.5)
if os.path.exists(MLSTOP): os.remove(MLSTOP)
if inp is None: log('MiniLab not available (still held by minilab.py?)'); sys.exit(1)
open(os.path.join(here, 'minilab.mode'), 'w').write('acid')      # the page labels the MiniLab for this program
try: refresh()
except Exception: LOG.write(traceback.format_exc())
threading.Thread(target=loop, daemon=True).start()
log('start: keys play the bass, pads = acid patterns, faders cutoff/res/env/decay, knobs incl. arp gate / brightness / transpose')
while not os.path.exists(STOP): time.sleep(0.25)
inp.close()
for n in list(held): out.send(mido.Message('note_off', note=n))
S.call('vcvrack_set_params', {'moduleId': ACID, 'params': [{'id': 25, 'value': 1.0}]})
os.remove(STOP); log('stopped')
