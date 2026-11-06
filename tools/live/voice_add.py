# My lil Arpeggio -> My lil Acid Voice -> Mixer strip 6, on a new row under the rig. Clock = Clocked out 1 (16ths, same as
# My lil Drums), reset = Clocked out 4. Scale locked to A B D E (no third: safe on the Lowdown E/A vamp either way).
# Arp mode, up, 2 octaves, gate outs on (the voice holds a note on the gate). IDs saved to voice.json.
import json, os, sys, time
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import sections as S
call = S.call
CL = json.load(open(os.path.join(here, 'clock.json')))['CLOCK']
mods = json.loads(call('vcvrack_list_modules', {}))
# the MCP layout matrix is 4 rows x 120 HP from the MCP module: free space at the right end of rows 3 and 4
def add(plugin, slug, x, y):
    before = {m['id'] for m in json.loads(call('vcvrack_list_modules', {}))}
    print(call('vcvrack_add_module', {'plugin_slug': plugin, 'module_slug': slug, 'x': x, 'y': y})[:100]); time.sleep(1.0)
    new = [m for m in json.loads(call('vcvrack_list_modules', {})) if m['id'] not in before]
    assert len(new) == 1, new
    return new[0]['id']
ARP = add('MyLilToolbox', 'Arpeggio', 31000, 39140)
VOX = add('MyLilAcidBass', 'AcidVoice', 30900, 38760)
KEYS = (2, 4, 9, 11)                                                     # D E A B (C = 0)
call('vcvrack_set_params', {'moduleId': ARP, 'params': [{'id': k, 'value': 1.0 if k in KEYS else 0.0} for k in range(12)]
                            + [{'id': 14, 'value': 1.0}, {'id': 16, 'value': 2.0}]})   # MODE arp, OCT 2
st = json.loads(call('vcvrack_get_module_state', {'id': ARP}))
st['data'].update(gateOuts=True, locked=True, lockedMask=sum(1 << k for k in KEYS))
call('vcvrack_set_module_state', {'id': ARP, 'state': st})
for o, oi, i, ii in ((CL, 1, ARP, 6), (CL, 4, ARP, 4), (ARP, 0, VOX, 0), (ARP, 1, VOX, 1), (VOX, 0, S.MIX, 5)):
    print(' cable', call('vcvrack_add_cable', {'outputModuleId': o, 'outputId': oi, 'inputModuleId': i, 'inputId': ii})[:80])
call('vcvrack_set_params', {'moduleId': S.MIX, 'params': [{'id': 5, 'value': S.U}]})
json.dump({'ARP': ARP, 'VOX': VOX}, open(os.path.join(here, 'voice.json'), 'w'))
time.sleep(2)
print('arp data', {k: v for k, v in json.loads(call('vcvrack_get_module_state', {'id': ARP}))['data'].items()})
print('voice out', call('vcvrack_measure', {'moduleId': VOX, 'outputId': 0, 'seconds': 1.0})[:120])
