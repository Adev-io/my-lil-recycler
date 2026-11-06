# One-time rig step (2026-11-06 arp + acid, phase 1). Bogaudio SWITCH picks the arp's root note: gate = MIDI to CV gate
# (a MiniLab key held), low = Acid Bass SEQ V/OCT, high = MIDI to CV V/OCT -> Arpeggio A CV (in 5). Arpeggio gateOuts:
# already on in the live rig (TRIG outs are gates so Triple's ADSRs open); this step only ensures it.
# Backs up dj-set.vcv first; SWITCH id saved to synths.json. Refuses to run twice.
# `py -3.11 synth_fix.py check` = read-only checks of the rig (only write: one loopMIDI test note).
import json, os, shutil, sys, time
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import sections as S, synths
call = S.call
PATCH = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\patches\dj-set.vcv')
MC = json.load(open(os.path.join(here, 'acid.json')))['MIDICV']
VOX = json.load(open(os.path.join(here, 'voice.json')))['VOX']
SJ = os.path.join(here, 'synths.json')
ARP, TRI = synths.ARP, synths.TRI
def ports(mid, kind): return json.loads(call('vcvrack_get_voltages', {'moduleId': mid}))[0][kind]
def find(mid, kind, *words):
    hit = [p['id'] for p in ports(mid, kind) if all(w in p['name'].lower() for w in words)]
    assert len(hit) == 1, (kind, words, [(p['id'], p['name']) for p in ports(mid, kind)]); return hit[0]
def volts(mid, kind, pid): return next(p['voltages'][0] for p in ports(mid, kind) if p['id'] == pid)
def lufs(mid, out): return json.loads(call('vcvrack_measure', {'moduleId': mid, 'outputId': out, 'seconds': 2.0}))['lufs']
def into_a_cv(): return [c for c in json.loads(call('vcvrack_list_cables', {})) if c['inputModuleId'] == ARP and c['inputId'] == 5]

def check(SW, o):
    wired = 0
    for _ in range(30): wired += abs(volts(SW, 'outputs', o) - volts(S.ACID, 'outputs', 0)) < 1e-3; time.sleep(0.1)
    print(f'wiring: switch out = Acid SEQ V/OCT in {wired}/30 reads'); assert wired >= 27   # step boundaries may miss
    d = json.loads(call('vcvrack_get_module_state', {'id': ARP}))['data']; mask = d['lockedMask']
    pcs = []
    for _ in range(30): pcs += [round(volts(ARP, 'outputs', p) * 12) % 12 for p in (0, 2)]; time.sleep(0.1)
    bad = [pc for pc in pcs if not mask >> pc & 1]
    print(f'scale: {len(pcs) - len(bad)}/{len(pcs)} arp notes in mask {mask}'); assert not bad, bad
    src = [(c['outputModuleId'], c['outputId']) for c in into_a_cv()]
    print('gateOuts', d['gateOuts'], '| Arp in 5 from', src); assert d['gateOuts'] is True and src == [(SW, o)]
    try:
        import mido
        out = mido.open_output(next(n for n in mido.get_output_names() if n.startswith('loopMIDI Port 1')))
    except Exception as e: print('WARNING: held-key path NOT verified (loopMIDI not reachable):', e); return
    try:                                                                    # a held key: the switch hands the arp the key's note
        out.send(mido.Message('note_on', note=45, velocity=10)); time.sleep(0.5); v = volts(SW, 'outputs', o)
    finally: out.send(mido.Message('note_off', note=45)); out.close()
    print('held A2 -> switch out', v); assert abs(v - (45 - 60) / 12) < 0.01

if sys.argv[1:] == ['check']:
    SW = json.load(open(SJ))['SWITCH']; check(SW, find(SW, 'outputs', '1')); print('all checks pass'); sys.exit()

mods = json.loads(call('vcvrack_list_modules', {}))
slug = {m['id']: m.get('slug') for m in mods}
if os.path.exists(SJ) or any(slug.get(c['outputModuleId']) == 'Bogaudio-Switch' for c in into_a_cv()):
    sys.exit('already rigged: a SWITCH feeds Arp in 5 (synths.json)')
bak = PATCH + time.strftime('.bak-%Y%m%d-%H%M%S'); shutil.copy2(PATCH, bak); print('backup', bak)
before = {m: lufs(m, 0) for m in (TRI, VOX)}; print('before', before)
y = next(m['y'] for m in mods if m['id'] == ARP)                            # the arp's row (MCP layout matrix)
x = max(m['x'] + m['width'] for m in mods if m['y'] == y)
print(call('vcvrack_add_module', {'plugin_slug': 'Bogaudio', 'module_slug': 'Bogaudio-Switch', 'x': x, 'y': y})[:120]); time.sleep(1.0)
new = [m for m in json.loads(call('vcvrack_list_modules', {})) if m['id'] not in slug]
assert len(new) == 1, new
SW = new[0]['id']
g, hi, lo, o = find(SW, 'inputs', 'gate'), find(SW, 'inputs', 'high', '1'), find(SW, 'inputs', 'low', '1'), find(SW, 'outputs', '1')
for c in into_a_cv(): print(' unplug', call('vcvrack_delete_cable', {'id': c['id']})[:60])   # nothing else may feed the arp's A CV
for om, oi, im, ii in ((MC, 1, SW, g), (S.ACID, 0, SW, lo), (MC, 0, SW, hi), (SW, o, ARP, 5)):
    print(' cable', call('vcvrack_add_cable', {'outputModuleId': om, 'outputId': oi, 'inputModuleId': im, 'inputId': ii})[:80])
synths.arp_data(gateOuts=True)                                              # data-only write under ARP_LOCK (no params)
json.dump({'SWITCH': SW}, open(SJ, 'w'))
time.sleep(3)
check(SW, o)
after = {m: lufs(m, 0) for m in (TRI, VOX)}; print('after', after)           # report only
print(call('vcvrack_save_patch', {'path': PATCH})[:110])
