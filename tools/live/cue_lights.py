# Launchpad relay + lights for the set (Programmer mode). Talks to MIDI only, never to Rack (no load on the engine).
# - Relay: Launchpad presses (LPMiniMK3 MIDI in) -> loopMIDI Port 1 -> Rack MIDI-CAT, forwarded at once.
# - Every pad you hit flashes white for 0.3 s.
# - Cue: the scene you last pressed is white, the NEXT scene pad blinks (off <-> colour), DROP pads pulse when due.
#   Starts at the scene in cue_lights.scene (default 1). Stops when cue_lights.stop exists.
import json, os, sys, time, threading, traceback, mido
here = os.path.dirname(os.path.abspath(__file__))
LOG = open(os.path.join(here, 'cue_lights.log'), 'a', buffering=1); sys.stderr = LOG
LOG.write(time.ctime() + ' start (MIDI only)\n')
STOP = os.path.join(here, 'cue_lights.stop')
leds = {int(k): v for k, v in json.load(open(os.path.join(here, 'launchpad.json')))['leds'].items()}
pad = lambda n: (8 - n // 8) * 10 + n % 8 + 1
SCENE_OF = {pad(n): n for n in range(21)}
DROP = {13: 66, 17: 67}
lp_out = mido.open_output(next(x for x in mido.get_output_names() if x.startswith('MIDIOUT2 (LPMiniMK3')))
relay = mido.open_output(next(x for x in mido.get_output_names() if x.startswith('loopMIDI Port 1')))
lock = threading.Lock()
try: start = int(open(os.path.join(here, 'cue_lights.scene')).read().strip()) - 1
except Exception: start = 0
state = {'cur': start}
def send(ch, note, vel):
    with lock: lp_out.send(mido.Message('note_on', channel=ch, note=note, velocity=vel))
def paint():
    cur = state['cur']; nxt = (cur + 1) % 21
    for note, v in leds.items(): send(0, note, 3 if note == pad(cur) else v)
    send(0, pad(nxt), 0); send(1, pad(nxt), leds[pad(nxt)])
    if cur in DROP: send(2, DROP[cur], 5)
def on_msg(msg):
    try:
        relay.send(msg)                                                    # forward first
        if msg.type == 'note_on' and msg.velocity > 0 and msg.note in leds:
            if msg.note in SCENE_OF:
                state['cur'] = SCENE_OF[msg.note]; LOG.write(time.ctime() + f" scene {state['cur'] + 1}\n")
            send(0, msg.note, 3); send(1, msg.note, 3)                     # white flash
            threading.Timer(0.3, paint).start()
    except Exception:
        LOG.write(traceback.format_exc())
lp_in = mido.open_input(next(x for x in mido.get_input_names() if x.startswith('LPMiniMK3 MIDI')), callback=on_msg)
paint(); t = time.time()
while not os.path.exists(STOP):
    time.sleep(0.25)
    if time.time() - t > 5: paint(); t = time.time()                       # repaint in case something cleared the pads
lp_in.close()
for note, v in leds.items(): send(0, note, v)
lp_out.close(); relay.close()
