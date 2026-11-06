# Launchpad Mini MK3 (Programmer mode: pad note = row*10 + col, row 1 = bottom) -> MIDI-CAT maps over the whole set.
# Rows 8-6: TRANSIT scenes 1-21 + drops (Arrow RESET, Body RESET, main RESET). Row 5: main mixer mutes 1-8.
# Rows 4-1: DECK next (ROLL) per deck: column = deck A..H, row 4 = slot 1 ... row 1 = slot 4.
import json, os, sys, time
here = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(here, 'rack.py')).read().split('if sys.argv[1]')[0])
def call(n, a, t=60):
    r = rpc('tools/call', {'name': n, 'arguments': a}, timeout=t)
    if 'error' in r or r['result'].get('isError'): raise RuntimeError(str(r)[:400])
    return r['result']['content'][0]['text']
ids = json.load(open(os.path.join(here, 'set_ids.json')))
MIX, CLKD = 2874844741614313, 7081946395008297
mods = json.loads(call('vcvrack_list_modules', {}))
by = lambda slug: [m for m in mods if m['slug'] == slug]
TR, EX = by('Transit')[0]['id'], by('TransitEx')[0]['id']
DECKS = [5192219511640844, 2698402179324496, 2032352601824354] + [ids['ids'][k] for k in ('peg', 'winning', 'westend', 'arrow', 'mcferrin')]
NAMES = ['Boz', 'Steely', 'Doobie', 'Peg', 'Winning', 'WestEnd', 'Arrow', 'Body']
st_tr = json.loads(call('vcvrack_get_module_state', {'id': TR}))['data']; st_ex = json.loads(call('vcvrack_get_module_state', {'id': EX}))['data']
labels = [p.get('textLabel', '') for p in st_tr['presets'] + st_ex['presets']]
def m(note, mid, pid, label, mode=0):
    return {'cc': -1, 'ccMode': 0, 'cc14bit': False, 'note': note, 'noteMode': mode, 'moduleId': mid, 'paramId': pid, 'label': label[:20],
            'midiOptions': 0, 'slew': 0.0, 'min': 0.0, 'max': 1.0, 'curve': 0.0, 'clockMode': 0, 'clockSource': 0, 'lightFirstId': -1, 'lightNumColors': 0}
maps, leds = [], {}
for n in range(21):                                   # scenes
    row, col = 8 - n // 8, n % 8 + 1; note = row * 10 + col
    maps.append(m(note, TR if n < 12 else EX, n if n < 12 else n - 12, labels[n]))
    leds[note] = 9 if any(w in labels[n] for w in ('Echo', 'send', 'drop')) else (45 if 'Home' in labels[n] else 21)
for col, (mid, lab) in zip((6, 7, 8), ((ids['CLK_A'], 'DROP Arrow (RESET)'), (ids['CLK_M'], 'DROP Body (RESET)'), (CLKD, 'Main RESET'))):
    maps.append(m(60 + col, mid, 4, lab)); leds[60 + col] = 5
STRIPS = ['Drums', 'Acid', 'Boz', 'Steely', 'Doobie', 'Peg', 'Winning', 'Guest bus']
for i in range(8):                                    # mutes, toggle
    maps.append(m(50 + i + 1, MIX, 40 + i, 'Mute ' + STRIPS[i], mode=2)); leds[51 + i] = 13
COL = [45, 37, 57, 53, 17, 3, 5, 9]                   # one colour per deck
for c, mid in enumerate(DECKS):
    for slot in range(4):
        note = (4 - slot) * 10 + c + 1
        maps.append(m(note, mid, 6 + slot, f'{NAMES[c]} next s{slot + 1}')); leds[note] = COL[c]
assert len({x['note'] for x in maps}) == len(maps) == 64
# MIDI-CAT module in row 0 after the reverb
if not by('MidiCat'):
    rv = next(x for x in mods if x['slug'] == 'SurgeXTFXReverb2')
    call('vcvrack_add_module', {'plugin_slug': 'Stoermelder-P1', 'module_slug': 'MidiCat', 'x': rv['x'] + rv['width'], 'y': 38000}); time.sleep(1)
    mods = json.loads(call('vcvrack_list_modules', {}))
mc = next(x for x in mods if x['slug'] == 'MidiCat')
st = json.loads(call('vcvrack_get_module_state', {'id': mc['id']}))
st['data'].update(maps=maps, midiInput={'driver': 4, 'deviceName': 'MIDIIN2 (LPMiniMK3 MIDI)', 'channel': -1},
                  midiOutput={'driver': -1, 'deviceName': '', 'channel': 0}, locked=False)
call('vcvrack_set_module_state', {'id': mc['id'], 'state': st}, 60); time.sleep(1)
g = json.loads(call('vcvrack_get_module_state', {'id': mc['id']}))['data']
print('MIDI-CAT', mc['id'], 'maps', len([x for x in g['maps'] if x.get('moduleId', -1) > 0]), 'input', g.get('midiInput'), 'output', g.get('midiOutput'))
json.dump({'midicat': mc['id'], 'leds': leds}, open(os.path.join(here, 'launchpad.json'), 'w'), indent=1)
# a Notes module with the pad map, right of MIDI-CAT
if not any(x['slug'] == 'Notes' and x['y'] == 38000 for x in mods):
    call('vcvrack_add_module', {'plugin_slug': 'Core', 'module_slug': 'Notes', 'x': mc['x'] + mc['width'], 'y': 38000}); time.sleep(1)
    nt = next(x for x in json.loads(call('vcvrack_list_modules', {})) if x['slug'] == 'Notes' and x['y'] == 38000)
    s2 = json.loads(call('vcvrack_get_module_state', {'id': nt['id']}))
    s2['data']['text'] = ('LAUNCHPAD MINI (Programmer mode)\n'
        'TOP 3 ROWS: TRANSIT scenes 1-21 (green = section, orange = echo / send / drop, blue = Home).\n'
        'Row 6, last 3 pads (red): DROP Arrow = 89 clock RESET, DROP Body = 97 clock RESET, main clock RESET.\n'
        'ROW 5 (yellow): mute main strips 1-8: Drums, Acid, Boz, Steely, Doobie, Peg, Winning, Guest bus.\n'
        'BOTTOM 4 ROWS: next loop. Column = deck A-H (Boz, Steely, Doobie, Peg, Winning, West End, Arrow, Body); '
        'row 4 = slot 1 (top slot) ... row 1 = slot 4.\n'
        'Lights gone? Ask Claude to rerun launchpad_leds.py.')
    call('vcvrack_set_module_state', {'id': nt['id'], 'state': s2}); print('pad-map note added')
