# Light the Launchpad Mini MK3 pads (Programmer mode, static colours on channel 1) from launchpad.json.
import json, os, mido
here = os.path.dirname(os.path.abspath(__file__))
leds = {int(k): v for k, v in json.load(open(os.path.join(here, 'launchpad.json')))['leds'].items()}
name = next(n for n in mido.get_output_names() if n.startswith('MIDIOUT2 (LPMiniMK3'))
with mido.open_output(name) as out:
    for note in range(11, 90):
        out.send(mido.Message('note_on', channel=0, note=note, velocity=leds.get(note, 0)))
print('lit', len(leds), 'pads on', name)
