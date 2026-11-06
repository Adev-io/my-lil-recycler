# One-time rig step for acid.py: a Core MIDI to CV on 'loopMIDI Port 1' -> My lil Acid Bass Play inputs (V/OCT 3, GATE 4,
# ACCENT 5 = velocity; acid.py sends velocity 127 for an accent, 10 otherwise). The sequencer keeps running; both reach the voice.
# Placed on row 1 after Audio 2 (the MCP layout matrix is 4 rows x 120 HP from the MCP module). ID saved to acid.json.
import json, os, sys, time
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import sections as S
call = S.call
before = {m['id'] for m in json.loads(call('vcvrack_list_modules', {}))}
print(call('vcvrack_add_module', {'plugin_slug': 'Core', 'module_slug': 'MIDIToCVInterface', 'x': 30600, 'y': 38000})[:120]); time.sleep(1.0)
new = [m for m in json.loads(call('vcvrack_list_modules', {})) if m['id'] not in before]
assert len(new) == 1, new
MC = new[0]['id']
st = json.loads(call('vcvrack_get_module_state', {'id': MC}))
st['data']['midi'] = {'driver': 4, 'deviceName': 'loopMIDI Port 1', 'channel': -1}       # driver 4 = Windows MIDI (as My lil Drums)
call('vcvrack_set_module_state', {'id': MC, 'state': st})
for oi, ii in ((0, 3), (1, 4), (2, 5)):                                                  # V/OCT, GATE, VELOCITY -> Acid Bass Play ins
    print(' cable', call('vcvrack_add_cable', {'outputModuleId': MC, 'outputId': oi, 'inputModuleId': S.ACID, 'inputId': ii})[:80])
json.dump({'MIDICV': MC}, open(os.path.join(here, 'acid.json'), 'w'))
print('midi', json.loads(call('vcvrack_get_module_state', {'id': MC}))['data'].get('midi'))
print(call('vcvrack_save_patch', {'path': os.path.expandvars(r'%LOCALAPPDATA%\Rack2\patches\dj-set.vcv')})[:110])
