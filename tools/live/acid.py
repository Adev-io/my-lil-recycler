# MiniLab 3 -> My lil Acid Bass only (replaces minilab.py while it runs: Windows lets one program hold the MiniLab).
# Keys: play the bass live (forwarded to 'loopMIDI Port 1' -> Rack MIDI to CV -> Acid Bass Play ins; acid_add.py patched it).
#   One octave down (middle C plays C2). Hold a key into the next = slide. Hit hard (velocity >= ACC_VEL) = accent.
#   While a key is held the sequencer stops; it starts again RESUME s after the last key is let go (back in step with the clock).
# Pads: bank A 1-8 = patterns 9-16 (I-B1..B8; pad 3 = 10 the Lowdown vamp, pad 7 = 14), bank B 1-8 = patterns 17-24 (pad 1 = walk-down).
# Faders: cutoff, resonance, env mod, decay. Knobs: 1 accent, 2 volume, 3 gate length, 4 swing, 5 high-pass, 6 saw/square,
#   7 transpose -12..+12, 8 pattern length 1-32. Pickup: a control acts once it reaches Rack's value. Stop: acid.stop. Log: acid.log.
import os, sys, time, json, threading, traceback, mido
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
LOG = open(os.path.join(here, 'acid.log'), 'a', buffering=1); sys.stderr = LOG
import sections as S
ACID = S.ACID
STOP, MLSTOP = os.path.join(here, 'acid.stop'), os.path.join(here, 'minilab.stop')
OCT, ACC_VEL, RESUME = -12, 100, 2.0
TICK, REFRESH, TOL = 0.05, 1.0, 0.05
import maps                                   # the map lives in maps.py (shared with the virtual controller page)
MAP = {cc: (pid, f, label) for cc, (_, pid, f, label) in maps.ACID.items()}   # CC -> (param, scale, label)
TOLS = maps.ACID_TOLS
pending, cur, prev, eng, held, lock = {}, {}, {}, set(), set(), threading.Lock()
seq = {'off': False, 'release': 0.0}
log = lambda s: LOG.write(time.ctime() + ' ' + s + '\n')
out = mido.open_output(next(x for x in mido.get_output_names() if x.startswith('loopMIDI Port 1')))
def on_msg(m):
    if m.type == 'control_change' and m.control in MAP:
        pid, f, label = MAP[m.control]; v = f(m.value); tol = TOLS.get(pid, TOL)
        with lock:
            c, p = cur.get(pid), prev.get(m.control)
            if m.control not in eng and (c is None or abs(v - c) <= tol or (p is not None and (p - c) * (v - c) < 0)):
                eng.add(m.control); log(f'picked up {label} at {v}')
            prev[m.control] = v
            if m.control in eng: pending[pid] = v; cur[pid] = v
    elif m.type in ('note_on', 'note_off') and m.channel == 9:
        if m.type == 'note_on' and m.velocity and 36 <= m.note <= 51:
            with lock: pending[24] = 8 + m.note - 36
            log(f'pattern {9 + m.note - 36}')
    elif m.type in ('note_on', 'note_off') and m.channel == 0:
        n = max(0, min(127, m.note + OCT))
        if m.type == 'note_on' and m.velocity:
            out.send(mido.Message('note_on', note=n, velocity=127 if m.velocity >= ACC_VEL else 10))
            with lock:
                held.add(n)
                if not seq['off']: seq['off'] = True; pending[25] = 0.0          # keys take over: sequencer stops
        else:
            out.send(mido.Message('note_off', note=n))
            with lock:
                held.discard(n)
                if not held: seq['release'] = time.time()
    elif m.type not in ('clock', 'active_sensing', 'polytouch', 'aftertouch'): log(f'unmapped {m}')
def refresh():                                # Rack's values; a control whose value moved elsewhere must be picked up again
    p = {x['id']: x['value'] for x in json.loads(S.call('vcvrack_get_params', {'moduleId': ACID}))}
    with lock:
        for cc, (pid, _, label) in MAP.items():
            if pid in pending: continue
            if cc in eng and abs(p[pid] - cur.get(pid, p[pid])) > TOLS.get(pid, 0.04) / 2: eng.discard(cc); log(f'dropped {label}')
            cur[pid] = p[pid]
def loop():
    t = 0
    while True:
        time.sleep(TICK)
        try:
            with lock:
                if seq['off'] and not held and time.time() - seq['release'] > RESUME: seq['off'] = False; pending[25] = 1.0
                batch = dict(pending); pending.clear()
            if batch: S.call('vcvrack_set_params', {'moduleId': ACID, 'params': [{'id': p, 'value': v} for p, v in batch.items()]})
            if time.time() - t > REFRESH: refresh(); t = time.time()
        except Exception: LOG.write(traceback.format_exc())
open(MLSTOP, 'w').close(); time.sleep(1.5)    # minilab.py lets go of the MiniLab
inp = None
for _ in range(20):
    try: inp = mido.open_input(next(x for x in mido.get_input_names() if x.startswith('Minilab3 MIDI')), callback=on_msg); break
    except Exception: time.sleep(0.5)
if os.path.exists(MLSTOP): os.remove(MLSTOP)
if inp is None: log('MiniLab not available (still held by minilab.py?)'); sys.exit(1)
open(os.path.join(here, 'minilab.mode'), 'w').write('acid')      # the page labels the MiniLab for this program
refresh(); threading.Thread(target=loop, daemon=True).start()
log('start: keys play, pads = patterns, faders cutoff/res/env/decay')
while not os.path.exists(STOP): time.sleep(0.25)
inp.close()
for n in list(held): out.send(mido.Message('note_off', note=n))
S.call('vcvrack_set_params', {'moduleId': ACID, 'params': [{'id': 25, 'value': 1.0}]})
os.remove(STOP); log('stopped')
