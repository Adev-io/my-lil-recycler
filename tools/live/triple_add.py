# My lil Triple as a second voice for My lil Arpeggio (Ari 2026-11-06: "adsr capabilities for my lil arpeggio"). Triple has an amp
# ADSR and a filter ADSR. Arp A_CV (out 0) -> Triple V/OCT, arp A_TRIG gate (out 1) -> Triple GATE; Triple L/R -> Mixer strip 7
# (inputs 6 / 14). The Acid Voice stays on strip 6, so the two can be blended or swapped. Row 1 after the MIDI to CV (MCP layout
# matrix: 4 rows x 120 HP from the MCP module). Starting sound: plucky arp. ID saved to triple.json.
import json, os, sys, time
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import sections as S
call = S.call
ARP = json.load(open(os.path.join(here, 'voice.json')))['ARP']
before = {m['id'] for m in json.loads(call('vcvrack_list_modules', {}))}
print(call('vcvrack_add_module', {'plugin_slug': 'MyLilTriple', 'module_slug': 'Triple', 'x': 30735, 'y': 38000})[:120]); time.sleep(1.0)
new = [m for m in json.loads(call('vcvrack_list_modules', {})) if m['id'] not in before]
assert len(new) == 1, new
TRI = new[0]['id']
A_ATK, A_DEC, A_SUS, A_REL, FTYPE, CUT, RES, ENV, KEY, F_ATK, F_DEC, F_SUS, F_REL = range(23, 36)
SOUND = {A_ATK: 0.005, A_DEC: 0.25, A_SUS: 0.35, A_REL: 0.35,            # amp: quick attack, short decay, low sustain, soft tail
         FTYPE: 0, CUT: 11.29, RES: 0.25, ENV: 0.35, KEY: 0.5,            # low-pass at ~2.5 kHz, the envelope opens it
         F_ATK: 0.002, F_DEC: 0.2, F_SUS: 0.2, F_REL: 0.25}
call('vcvrack_set_params', {'moduleId': TRI, 'params': [{'id': k, 'value': v} for k, v in SOUND.items()]})
for o, oi, i, ii in ((ARP, 0, TRI, 0), (ARP, 1, TRI, 1), (TRI, 0, S.MIX, 6), (TRI, 1, S.MIX, 14)):
    print(' cable', call('vcvrack_add_cable', {'outputModuleId': o, 'outputId': oi, 'inputModuleId': i, 'inputId': ii})[:80])
call('vcvrack_set_params', {'moduleId': S.MIX, 'params': [{'id': 6, 'value': 0.5}]})
json.dump({'TRIPLE': TRI}, open(os.path.join(here, 'triple.json'), 'w'))
time.sleep(2)
ps = {p['id']: p['displayValue'] for p in json.loads(call('vcvrack_get_params', {'moduleId': TRI}))}
print('amp ADSR', [ps[k] for k in (A_ATK, A_DEC, A_SUS, A_REL)], '| cutoff', ps[CUT], '| filter ADSR', [ps[k] for k in (F_ATK, F_DEC, F_SUS, F_REL)])
print('triple out', call('vcvrack_measure', {'moduleId': TRI, 'outputId': 0, 'seconds': 2.0})[:200])
print(call('vcvrack_save_patch', {'path': os.path.expandvars(r'%LOCALAPPDATA%\Rack2\patches\dj-set.vcv')})[:110])
