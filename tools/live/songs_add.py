# Songs 4+ into dj-set.vcv (2026-11-07): Mixer 2 (My lil Toolbox Mixer, row 6; its OUT L/R -> the Mixer's RETURN 2 L/R,
# inputs 19/20, which sum into the master bus at unity; Mixer 2 master at unity, all its strips 0) and one Recycler deck per song
# (row 5): DECK mode, BARS 8, ROOT = the song's target (major; the Recycler shifts each pinned loop by the nearest way),
# chaos 0, all slot levels 0, clock / reset from Clocked (out 0 / out 4, as decks A-D), MIX L/R -> Mixer 2 strip k.
# Adds only what songs.json lacks; a song dropped from WANT hands its deck + strip to the next new song (crate, key, slots reset). Touches no other module: checks the inputs are free and the room is empty first, then diffs every
# other module's params and the cable list. Patch backup first; writes songs.json. usage: py -3.11 songs_add.py
import json, os, re, sys, time, shutil
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
os.environ['LIVE_SONGS'] = ''
import sections as S
call = S.call
CLOCK = json.load(open(os.path.join(here, 'clock.json')))['CLOCK']
CR = r'C:\Users\Arikl\Desktop\uvr-loops\crates'
WANT = [dict(name='Together', crate=CR + r'\together-crate', root=2),            # C major +2 -> D major
        dict(name='Do the Dance', crate=CR + r'\dothedance-crate', root=2),     # B minor, 130.4 BPM: no shift (2026-11-07, replaces Pusherman)
        dict(name="Let's Groove", crate=CR + r'\letsgroove-crate', root=2)]   # B minor, 125.0 BPM: no shift (replaces Rainmaker)
MX2 = (29910, 39900); DX, DY, DW = 29910, 39520, 540        # rows 5 (decks) + 6 (Mixer 2): the MCP matrix grows from 4 to 6 rows
SONGF = os.path.join(here, 'songs.json'); PATCH = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\patches\dj-set.vcv')
cfg = json.load(open(SONGF)) if os.path.exists(SONGF) else {'MIX2': None, 'songs': []}
def snap():
    mods = json.loads(call('vcvrack_list_modules', {}))
    ps = {m['id']: {p['id']: p['value'] for p in json.loads(call('vcvrack_get_params', {'moduleId': m['id']}))} for m in mods if m['params']}
    cab = {(c['outputModuleId'], c['outputId'], c['inputModuleId'], c['inputId']) for c in json.loads(call('vcvrack_list_cables', {}))}
    return mods, ps, cab
def free(mods, x, y, w): return all(m['x'] + m['width'] <= x or m['x'] >= x + w for m in mods if m['y'] == y)
def add(slug_p, slug_m, x, y, mods0):
    print(call('vcvrack_add_module', {'plugin_slug': slug_p, 'module_slug': slug_m, 'x': x, 'y': y})[:100]); time.sleep(1.0)
    new = [m for m in json.loads(call('vcvrack_list_modules', {})) if m['id'] not in {q['id'] for q in mods0}]
    assert len(new) == 1, new; return new[0]
def cable(o, oi, i, ii): print(' cable', call('vcvrack_add_cable', {'outputModuleId': o, 'outputId': oi, 'inputModuleId': i, 'inputId': ii})[:80])
def slot_loops(crate):                                         # slots 0 bass, 1 piano, 2 other (else guitar), 3 vocals: the first mid-song loop
    fs = sorted(f for f in os.listdir(crate) if f.endswith('.wav'))
    def first(*stems):
        for st in stems:
            c = [f for f in fs if re.match(rf'\d-{st}-\d\d_', f)]; c = [f for f in c if not re.search(r'_(intro|outro)-', f)] or c
            if c: return crate.replace('\\', '/') + '/' + c[0]
        return ''
    return [first('bass'), first('piano', 'other'), first('other', 'guitar'), first('vocals')]
mods0, ps0, cab0 = snap()
todo = [w for w in WANT if w['name'] not in {s['name'] for s in cfg['songs']} and os.path.isdir(w['crate'])]
assert todo or not cfg['MIX2'], 'nothing to add'
spare = [s for s in cfg['songs'] if s['name'] not in {w['name'] for w in WANT}]   # songs taken out of the set
bk = os.path.join(os.path.dirname(PATCH), '_archive-20261103', time.strftime('dj-set-%Y%m%d-%H%M%S-before-songs.vcv'))
shutil.copy2(PATCH, bk); print('patch backup', bk)
mods = list(mods0)
if not cfg['MIX2']:
    assert not [c for c in cab0 if c[2] == S.MIX and c[3] in (19, 20)], 'Mixer return 2 is taken'
    assert free(mods, *MX2, 510), f'no room for Mixer 2 at {MX2}'
    m2 = add('MyLilToolbox', 'Mixer', *MX2, mods); mods.append(m2); cfg['MIX2'] = m2['id']; print('Mixer 2', m2['id'])
    call('vcvrack_set_params', {'moduleId': m2['id'], 'params': [{'id': k, 'value': 0.0} for k in range(8)] + [{'id': 56, 'value': S.U}]})   # strips 0, master unity
    cable(m2['id'], 0, S.MIX, 19); cable(m2['id'], 1, S.MIX, 20)
used = {s['strip'] for s in cfg['songs']}
for w in todo:
    new = not spare
    if spare:                                                  # reuse a dropped song's deck: same strip and cables, new crate / key / slots
        old = spare.pop(0); D, k = old['deck'], old['strip']; cfg['songs'].remove(old); print(old['name'], '->', w['name'], 'on deck', D)
    else:
        k = next(i for i in range(8, 16) if i not in used); used.add(k); x = DX + DW * (k - 8)
        assert free(mods, x, DY, DW), f'no room for {w["name"]} at x {x}'
        assert not [c for c in cab0 if c[2] == cfg['MIX2'] and c[3] in (k - 8, k)], f'Mixer 2 strip {k - 7} inputs taken'
        d = add('MyLilRecycler', 'Recycler', x, DY, mods); mods.append(d); D = d['id']
    call('vcvrack_set_params', {'moduleId': D, 'params': [{'id': i, 'value': 0.0} for i in (14, 15, 16, 17)]})   # silent first
    st = json.loads(call('vcvrack_get_module_state', {'id': D}))
    st['data'].update(folder=w['crate'], deck=True, run=True, root=w['root'], minor=False, bars=8, chaos=0.0, title=w['name'],
                      slots=[{'path': p, 'locked': False, 'level': 0.0, 'k': 0, 's': 0} for p in slot_loops(w['crate'])])
    for q in st['params']:
        if q['id'] in (2, 3, 4, 19): q['value'] = {2: float(w['root']), 3: 0.0, 4: 3.0, 19: 0.0}[q['id']]
        if q['id'] in (14, 15, 16, 17): q['value'] = 0.0
    for q in st['params']:
        if 40 <= q['id'] < 44: q['value'] = 0.0                   # a reused deck: no STUT hold carried over
    call('vcvrack_set_module_state', {'id': D, 'state': st})
    if new:
        for o, oi, i, ii in ((CLOCK, 0, D, 0), (CLOCK, 4, D, 2), (D, 8, cfg['MIX2'], k - 8), (D, 9, cfg['MIX2'], k)): cable(o, oi, i, ii)
    cfg['songs'].append(dict(name=w['name'], crate=w['crate'], deck=D, strip=k, root=w['root'])); print(w['name'], 'deck', D, 'strip', k)
json.dump(cfg, open(SONGF, 'w'), indent=1); print('songs.json', cfg)
time.sleep(25)
for s in cfg['songs']:
    d = json.loads(call('vcvrack_get_module_state', {'id': s['deck']}))['data']; ps = {p['id']: p for p in json.loads(call('vcvrack_get_params', {'moduleId': s['deck']}))}
    print(s['name'], '| root', ps[2]['displayValue'], ps[3]['displayValue'], 'bars', ps[4]['displayValue'], '| levels', [ps[i]['value'] for i in (14, 15, 16, 17)],
          '| slots', [os.path.basename(x['path']) for x in d['slots']])
mods1, ps1, cab1 = snap()
print('cables added', sorted(cab1 - cab0), '| removed', sorted(cab0 - cab1))
diff = {m: {k: (ps0[m][k], v) for k, v in ps1[m].items() if abs(v - ps0[m].get(k, v)) > 1e-6} for m in ps1 if m in ps0}
print('other modules param changes during the add:', {m: v for m, v in diff.items() if v} or 'none')
print(S.save()[:120])
