# My lil Arpeggio + My lil Acid Bass helpers for the live set (rig ids in sections.py, voice.json, triple.json).
# Phase 1: the arp's keys follow the song page (sections.SCALES), held by the Arpeggio's scale lock so a stray click cannot move them.
import json, os
import sections as S
ARP = json.load(open(os.path.join(S.here, 'voice.json')))['ARP']
TRI = json.load(open(os.path.join(S.here, 'triple.json')))['TRIPLE']
def mask_of(pcs): return sum(1 << p for p in set(pcs))
def getp(mid): return {x['id']: x['value'] for x in json.loads(S.call('vcvrack_get_params', {'moduleId': mid}))}
def setp(mid, vals): S.call('vcvrack_set_params', {'moduleId': mid, 'params': [{'id': k, 'value': v} for k, v in vals.items()]})
def set_scale(page):                     # page 0 Lowdown, 1 Time Out Of Mind; any other page keeps the scale playing
    if page not in S.SCALES: return None
    m = mask_of(S.SCALES[page]); st = json.loads(S.call('vcvrack_get_module_state', {'id': ARP}))
    if st['data'].get('locked') and st['data'].get('lockedMask') == m: return m
    for p in st['params']:
        if p['id'] < 12: p['value'] = 1.0 if (m >> p['id']) & 1 else 0.0       # params 0-11 = the key latches C..B
    st['data'].update(locked=True, lockedMask=m)
    S.call('vcvrack_set_module_state', {'id': ARP, 'state': st}); return m
def scale_now():
    d = json.loads(S.call('vcvrack_get_module_state', {'id': ARP}))['data']
    return d.get('lockedMask') if d.get('locked') else None
