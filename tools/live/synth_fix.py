# One-time rig step (2026-11-06 arp + acid, phase 1). Bogaudio SWITCH picks the arp's root note: gate = MIDI to CV gate
# (a MiniLab key held), low = Acid Bass SEQ V/OCT, high = MIDI to CV V/OCT -> Arpeggio A CV (in 5). Arpeggio gateOuts on:
# TRIG outs become gates so Triple's ADSRs open. Backs up dj-set.vcv first; SWITCH id saved to synths.json.
import json, os, shutil, sys, time
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import sections as S, synths
call = S.call
PATCH = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\patches\dj-set.vcv')
MC = json.load(open(os.path.join(here, 'acid.json')))['MIDICV']
VOX = json.load(open(os.path.join(here, 'voice.json')))['VOX']
ARP, TRI = synths.ARP, synths.TRI
bak = PATCH + time.strftime('.bak-%Y%m%d-%H%M%S'); shutil.copy2(PATCH, bak); print('backup', bak)
def ports(mid, kind): return json.loads(call('vcvrack_get_voltages', {'moduleId': mid}))[0][kind]
def find(mid, kind, *words):
    hit = [p['id'] for p in ports(mid, kind) if all(w in p['name'].lower() for w in words)]
    assert len(hit) == 1, (kind, words, [(p['id'], p['name']) for p in ports(mid, kind)]); return hit[0]
def volts(mid, kind, pid): return next(p['voltages'][0] for p in ports(mid, kind) if p['id'] == pid)
def lufs(mid, out): return json.loads(call('vcvrack_measure', {'moduleId': mid, 'outputId': out, 'seconds': 2.0}))['lufs']
before = {m: lufs(m, 0) for m in (TRI, VOX)}; print('before', before)
mods = json.loads(call('vcvrack_list_modules', {}))
row = [m for m in mods if m['y'] == 38760]                                  # the arp's row (MCP layout matrix row 3)
x = max(m['x'] + m['width'] for m in row)
print(call('vcvrack_add_module', {'plugin_slug': 'Bogaudio', 'module_slug': 'Bogaudio-Switch', 'x': x, 'y': 38760})[:120]); time.sleep(1.0)
new = [m for m in json.loads(call('vcvrack_list_modules', {})) if m['id'] not in {m['id'] for m in mods}]
assert len(new) == 1, new
SW = new[0]['id']
g, hi, lo, o = find(SW, 'inputs', 'gate'), find(SW, 'inputs', 'high', '1'), find(SW, 'inputs', 'low', '1'), find(SW, 'outputs', '1')
for c in json.loads(call('vcvrack_list_cables', {})):                       # nothing else may feed the arp's A CV
    if c['inputModuleId'] == ARP and c['inputId'] == 5: print(' unplug', call('vcvrack_delete_cable', {'id': c['id']})[:60])
for om, oi, im, ii in ((MC, 1, SW, g), (S.ACID, 0, SW, lo), (MC, 0, SW, hi), (SW, o, ARP, 5)):
    print(' cable', call('vcvrack_add_cable', {'outputModuleId': om, 'outputId': oi, 'inputModuleId': im, 'inputId': ii})[:80])
synths.arp_data(gateOuts=True)                                              # data-only write under ARP_LOCK (no params)
json.dump({'SWITCH': SW}, open(os.path.join(here, 'synths.json'), 'w'))
time.sleep(3)
assert json.loads(call('vcvrack_get_module_state', {'id': ARP}))['data']['gateOuts'] is True
assert next(p for p in ports(ARP, 'inputs') if p['id'] == 5)['connected']
octs = round(synths.getp(ARP)[16]); good = 0
for _ in range(30):
    d = round((volts(ARP, 'outputs', 0) - volts(S.ACID, 'outputs', 0)) * 12); good += -1 <= d <= 12 * octs; time.sleep(0.1)
print(f'arp on the bass: {good}/30 reads'); assert good >= 24
after = {m: lufs(m, 0) for m in (TRI, VOX)}; print('after', after)           # gate outs were already on: report only
v = None
try:                                                                        # a held key: the switch hands the arp the key's note
    import mido
    out = mido.open_output(next(n for n in mido.get_output_names() if n.startswith('loopMIDI Port 1')))
    out.send(mido.Message('note_on', note=45, velocity=10)); time.sleep(0.5)
    v = volts(SW, 'outputs', o); out.send(mido.Message('note_off', note=45)); out.close()
except Exception as e: print('SKIP held-key check (loopMIDI not reachable):', e)
if v is not None: print('held A2 -> switch out', v); assert abs(v - (45 - 60) / 12) < 0.01
print(call('vcvrack_save_patch', {'path': PATCH})[:110])
