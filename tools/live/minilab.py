# Arturia MiniLab 3 (factory map, channel 1) -> the layer step. Faders = row volumes, knobs = row filters.
# Fader 1-4: vocals, keys, horns, bass (deck A slots 3, 1, 2, 0). Knob 1-4: the same rows' filters (centre off, left LP, right HP).
# Knob 5: drums filter, knob 6: drums volume (deck C). My lil Drums (house beats): pads 1-8 = pattern 1-8, keys = its volume
# (Mixer strip 1; far-left key silent, far-right full). Other unmapped messages are logged once per kind.
# Pickup: a control does nothing until it reaches (or crosses) the value Rack already has, so nothing jumps. Rack is re-read
# every REFRESH s; a value changed elsewhere (Launchpad pad, mouse) drops that control until it is picked up again.
# Moves are coalesced: one MCP batch per deck every TICK s, latest value wins. Stops when minilab.stop exists.
import os, sys, time, json, threading, traceback, mido
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
LOG = open(os.path.join(here, 'minilab.log'), 'a', buffering=1); sys.stderr = LOG
import sections as S
C = json.load(open(os.path.join(here, 'deckc.json')))['C']
STOP = os.path.join(here, 'minilab.stop')
KEYS_LO, KEYS_HI = 48, 72                     # the 25 keys at the default octave (C2..C4 in Arturia naming); other octaves clamp
TICK, REFRESH, TOL = 0.08, 1.0, 0.05          # TOL ~ 4 MIDI steps either side of Rack's value counts as caught
import maps                                   # the map lives in maps.py (shared with the virtual controller page)
MAP = dict(maps.mix_map())                    # CC -> (deck, param, scale, label); follows the Launchpad page (refresh)
PG = [maps.page_now()]
pending, cur, prev, eng, seen, lock = {}, {}, {}, set(), set(), threading.Lock()
log = lambda s: LOG.write(time.ctime() + ' ' + s + '\n')
def on_msg(m):
    if m.type == 'control_change' and m.control in MAP:
        cc = m.control; deck, pid, f, label = MAP[cc]; v, k = f(m.value), (deck, pid)
        with lock:
            c, p = cur.get(k), prev.get(cc)
            if cc not in eng and (c is None or abs(v - c) <= TOL or (p is not None and (p - c) * (v - c) < 0)):
                eng.add(cc); log(f'picked up {label} at {v}')
            prev[cc] = v
            if cc in eng: pending[k] = v; cur[k] = v
    elif m.type == 'note_on' and m.velocity and m.channel == 9 and 36 <= m.note <= 43:      # pads 1-8 -> My lil Drums pattern 1-8
        i = m.note - 36                                                                     # pick / switch beat; the playing one again = off
        threading.Thread(target=lambda: log(f'drums beat {i + 1} ' + ('off' if maps.drum_pad(i) else 'on')), daemon=True).start()
    elif m.type == 'note_on' and m.velocity and m.channel == 0:                             # keys: far left silent .. far right full
        v = round(max(0, min(KEYS_HI - KEYS_LO, m.note - KEYS_LO)) / (KEYS_HI - KEYS_LO), 3)
        with lock: pending[(S.MIX, 0)] = v                                                    # Mixer strip 1 = My lil Drums
        log(f'drum machine vol {v} (key {m.note})')
    elif m.type == 'note_off' or (m.type == 'note_on' and not m.velocity): pass
    elif m.type == 'note_on': log(f'unmapped {m}')
    elif m.type not in ('clock', 'active_sensing'):
        d = m.dict(); key = (m.type, d.get('channel'), d.get('control', d.get('note')))
        if key not in seen: seen.add(key); log(f'unmapped {m}')
def refresh():                                # Rack's values; a control whose value moved elsewhere must be picked up again
    pg = maps.page_now()
    if pg != PG[0]:                           # page turned: faders / knobs 1-4 now the other song's tracks, all picked up afresh
        with lock: MAP.clear(); MAP.update(maps.mix_map(pg)); eng.clear(); prev.clear(); PG[0] = pg
        log(f'page {pg + 1}: ' + ', '.join(l for _, _, _, l in MAP.values()))
    for deck in {d for d, _, _, _ in MAP.values()}:
        p = {x['id']: x['value'] for x in json.loads(S.call('vcvrack_get_params', {'moduleId': deck}))}
        with lock:
            for cc, (d, pid, _, label) in MAP.items():
                if d != deck or (d, pid) in pending: continue
                if cc in eng and abs(p[pid] - cur.get((d, pid), p[pid])) > 0.02: eng.discard(cc); log(f'dropped {label}: Rack moved it to {round(p[pid], 3)}')
                cur[(d, pid)] = p[pid]
def loop():
    t = 0
    while True:
        time.sleep(TICK)
        try:
            with lock: batch = dict(pending); pending.clear()
            for deck in {d for d, _ in batch}:
                S.call('vcvrack_set_params', {'moduleId': deck, 'params': [{'id': p, 'value': v} for (d, p), v in batch.items() if d == deck]})
            if time.time() - t > REFRESH: refresh(); t = time.time()
        except Exception: LOG.write(traceback.format_exc())
refresh()
threading.Thread(target=loop, daemon=True).start()
inp = mido.open_input(next(x for x in mido.get_input_names() if x.startswith('Minilab3 MIDI')), callback=on_msg)
open(os.path.join(here, 'minilab.mode'), 'w').write('mix')       # the page labels the MiniLab for this program
log('start (pickup) ' + ', '.join(f'CC{c} {l}' for c, (_, _, _, l) in MAP.items()))
while not os.path.exists(STOP): time.sleep(0.25)
inp.close()
