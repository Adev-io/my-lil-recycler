# Read only: Acid Bass slots 8-23 as pitch classes, inside / outside each song's arp scale -> sections.ACID_SONG.
import json, sections as S
N = 'C C# D D# E F F# G G# A A# B'.split()
pats = json.loads(S.call('vcvrack_get_module_state', {'id': S.ACID}))['data']['patterns']
for i in range(8, 24):
    p = pats[i]; pcs = sorted({(36 + s['note'] + 12 * s['oct']) % 12 for s in p['steps'][:p['len']] if s['gate'] == 'note'})
    print(i, [N[c] for c in pcs], {song: all(c in S.SCALES[song] for c in pcs) for song in S.SCALES})
