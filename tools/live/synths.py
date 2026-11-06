# My lil Arpeggio + My lil Acid Bass helpers for the live set (rig ids in sections.py, voice.json, triple.json).
# Phase 1: the arp's keys follow the song page (sections.SCALES), held by the Arpeggio's scale lock so a stray click cannot move them.
import json, os, threading
import sections as S
ARP = json.load(open(os.path.join(S.here, 'voice.json')))['ARP']
TRI = json.load(open(os.path.join(S.here, 'triple.json')))['TRIPLE']
ARP_LOCK = threading.RLock()                 # every Arpeggio module-state write goes through here (pads.py threads share it)
def mask_of(pcs): return sum(1 << p for p in set(pcs))
def getp(mid): return {x['id']: x['value'] for x in json.loads(S.call('vcvrack_get_params', {'moduleId': mid}))}
def setp(mid, vals): S.call('vcvrack_set_params', {'moduleId': mid, 'params': [{'id': k, 'value': v} for k, v in vals.items()]})
def arp_data(**kv):                          # read-modify-write of the arp's module data only (dir, gateOuts, locked, lockedMask ...)
    with ARP_LOCK:
        st = json.loads(S.call('vcvrack_get_module_state', {'id': ARP})); st['data'].update(kv)
        st.pop('params', None)               # params stay as Rack has them now (checked live 2026-11-06: a state without 'params' leaves OCT and the keys alone)
        S.call('vcvrack_set_module_state', {'id': ARP, 'state': st}); return st['data']
def set_scale(page):                         # page 0 Lowdown, 1 Time Out Of Mind; any other page keeps the scale playing
    if page not in S.SCALES: return None
    m = mask_of(S.SCALES[page])
    with ARP_LOCK:
        d = json.loads(S.call('vcvrack_get_module_state', {'id': ARP}))['data']
        if d.get('locked') and d.get('lockedMask') == m: return m
        arp_data(locked=True, lockedMask=m)  # the module forces the 12 key latches itself while locked
    return m
def follow(get_page):                        # the page is read inside the lock, so the last page turn wins
    with ARP_LOCK: return set_scale(get_page())
def scale_now():
    d = json.loads(S.call('vcvrack_get_module_state', {'id': ARP}))['data']
    return d.get('lockedMask') if d.get('locked') else None
