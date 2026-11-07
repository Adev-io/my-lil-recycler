# The set's sections for dj-set.vcv. apply(i) moves the rig there over MCP; drum_pattern(n) sets My lil Drums' pattern 1..16.
# CLI: py -3 sections.py <0..9> | drums <1..16>
import json, os, re, sys, time
here = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(here, 'rack.py')).read().split('if sys.argv[1]')[0])
call = lambda n, a: rpc('tools/call', {'name': n, 'arguments': a}, timeout=60)['result']['content'][0]['text']
A, ACID, MIX, DRUMS = 5192219511640844, 8333663024495709, 2874844741614313, 7189220493962056
B = json.load(open(os.path.join(here, 'deckb.json')))['B']
CR = r'C:\Users\Arikl\Desktop\uvr-loops\crates\lowdown2-crate'; CRB = r'C:\Users\Arikl\Desktop\uvr-loops\crates\toom-crate'
U = 0.707; DR = 0.80                                     # mixer unity; drums strip after the balance pass (+2 dB)
CHOP_V = CR.replace('\\', '/') + '/6-vocals-14-115bpm-chop4.wav'; CHOP_G = CR.replace('\\', '/') + '/3-guitar-14-115bpm-chop4.wav'
HORNS = CR.replace('\\', '/') + '/5-other-16-115bpm.wav'
VC = 'C:/Users/Arikl/Desktop/uvr-loops/crates/vocal-cuts/'      # vocal_cuts.py: first words, verse and roll pads (4 bars, pinned; outside the deck crates)
# deck slots: 1 bass stem, 2 piano, 3 guitar, 4 vocals. levels = (bass, piano, guitar, vocals). strips = (drums, acid, deck A, deck B).
# Acid: 10 = I-B3 (Lowdown E/A vamp), 14 = I-B7 (Time Out Of Mind A vamp), 16 = I-C1 (TOOM walk-down).
SECTIONS = [
    # 2026-11-04: samples only. Drums and Acid strips stay at 0; every pad is Recycler deck A, one sample added per pad.
    dict(name='0 vocal chop',   acid=10, loop=14, levels=(0.0, 0.0, 0.0, 1.0), strips=(0.0, 0.0, U, 0.0), override={3: CHOP_V}),
    dict(name='1 +piano',       acid=10, loop=14, levels=(0.0, 1.2, 0.0, 1.0), strips=(0.0, 0.0, U, 0.0), override={3: CHOP_V}),
]
# Old pads 4-10 (locked 2026-11-03 under the many-changes-per-press method), kept on file, not on the Launchpad.
OLD_SECTIONS = [
    dict(name='0 vocal solo',   acid=10, loop=14, levels=(0.0, 0.0, 0.0, 1.0), strips=(0.0, 0.0, U, 0.0), override={3: CHOP_V}, drums=1),
    dict(name='1 kick',         acid=10, loop=14, levels=(0.0, 0.0, 0.0, 1.0), strips=(DR, 0.0, U, 0.0), override={3: CHOP_V}, drums=16),   # pattern 16 = pattern 12's house kick alone (pattern 1 had a snare pickup every bar)
    dict(name='2 kick+acid',    acid=10, loop=14, levels=(0.0, 0.0, 0.0, 1.0), strips=(DR, U, U, 0.0), override={3: CHOP_V}, drums=12),   # Acid I-B3 over the Lowdown hats (kick-only under it: no lock 22:30)
    dict(name='3 +piano',       acid=10, loop=14, levels=(0.0, 1.2, 0.0, 1.0), strips=(DR, U, U, 0.0), override={3: CHOP_V}, drums=12),    # pad 3 + piano 14, nothing else
    dict(name='3 intro',        acid=10, loop=3,  levels=(0.0, 1.2, 1.0, 0.0), strips=(DR, U, U, 0.0), drums=12),   # Lowdown groove, light hats
    dict(name='4 chorus',       acid=10, loop=14, levels=(0.0, 1.2, 1.0, 0.0), strips=(DR, U, U, 0.0), drums=11),   # Lowdown groove, full
    dict(name='5 chorus+bass',  acid=10, loop=14, levels=(0.5, 1.2, 1.0, 0.0), strips=(DR, U, U, 0.0), drums=13),   # + clap on 2 and 4
    dict(name='6 vocals chop',  acid=10, loop=14, levels=(0.5, 1.2, 1.0, 1.0), strips=(DR, U, U, 0.0), override={2: CHOP_G, 3: CHOP_V}, drums=13),
    dict(name='7 horn bridge',  acid=10, loop=16, levels=(0.0, 0.6, 1.2, 0.0), strips=(DR, U, U, 0.0), override={2: HORNS}, drums=13,     # horns in the guitar slot
         b_loop=5, b_levels=(0.0, 1.0, 1.0, 1.0)),                                                                                # deck B armed on the TOOM verse
    dict(name='8 Steely Mind',  acid=14, loop=16, levels=(0.0, 0.6, 1.2, 0.0), strips=(DR, U, 0.0, U), override={2: HORNS}, drums=14,   # TOOM verse groove
         b_loop=5, b_levels=(0.0, 1.0, 1.0, 1.0)),                                                                                # Lowdown out, TOOM in, Acid I-B7
    dict(name='9 walk-down',    acid=16, loop=16, levels=(0.0, 0.6, 1.2, 0.0), strips=(DR, U, 0.0, U), override={2: HORNS}, drums=15,   # TOOM chorus groove + clap
         b_loop=4, b_levels=(0.0, 1.0, 1.0, 1.0)),                                                                                # TOOM chorus loop 04, Acid I-C1 (A G F# E D)
]
def set_slots(mid, crate, loop, override, pat):
    files = sorted(f for f in os.listdir(crate) if f.endswith('.wav') and 'chop' not in f)
    st = json.loads(call('vcvrack_get_module_state', {'id': mid})); changed = False
    for k, s in enumerate(st['data']['slots']):
        stem = ['bass', 'piano', 'guitar', 'vocals'][k]
        c = [f for f in files if re.match(rf'\d-{stem}-(\d\d){pat}', f)]
        p = crate.replace('\\', '/') + '/' + min(c, key=lambda f: abs(int(re.search(r'-(\d\d)', f).group(1)) - loop))
        p = override.get(k, p)
        if s['path'] != p: s['path'] = p; changed = True
    st.pop('params', None)                                                       # data only: params stay as Rack has them (STUT holds)
    if changed: call('vcvrack_set_module_state', {'id': mid, 'state': st})     # lands at the next loop start
def apply(i):
    S = SECTIONS[i]
    set_slots(A, CR, S['loop'], S.get('override', {}), '-')
    call('vcvrack_set_params', {'moduleId': A, 'params': [{'id': 14 + k, 'value': v} for k, v in enumerate(S['levels'])]})
    if 'b_loop' in S:
        set_slots(B, CRB, S['b_loop'], {}, '_')
        call('vcvrack_set_params', {'moduleId': B, 'params': [{'id': 14 + k, 'value': v} for k, v in enumerate(S['b_levels'])]})
    call('vcvrack_set_params', {'moduleId': ACID, 'params': [{'id': 24, 'value': S['acid']}]})
    if S.get('drums'): drum_pattern(S['drums'])
    call('vcvrack_set_params', {'moduleId': MIX, 'params': [{'id': k, 'value': v} for k, v in enumerate(S['strips'])] + [{'id': 40 + k, 'value': 0} for k in range(4)]})
    return S['name']
def drum_pattern(n):
    call('vcvrack_set_params', {'moduleId': DRUMS, 'params': [{'id': 3, 'value': n - 1}]})
    return n
def current_drum_pattern():
    return int(round(next(p['value'] for p in json.loads(call('vcvrack_get_params', {'moduleId': DRUMS})) if p['id'] == 3))) + 1
def save():
    return call('vcvrack_save_patch', {'path': os.path.expandvars(r'%LOCALAPPDATA%\Rack2\patches\dj-set.vcv')})
if __name__ == '__main__':
    if sys.argv[1] == 'drums': print('drums pattern', drum_pattern(int(sys.argv[2])))
    else: print('section', apply(int(sys.argv[1])))
    print(save())

# 2026-11-04 row layout (Ari): each Launchpad row is one instrument = one deck A slot. A pad picks that row's sample, the lit
# pad pressed again mutes the row. Rows play together on deck A's loop grid. Samples only: Drums and Acid strips stay 0.
P = lambda f: CR.replace('\\', '/') + '/' + f
ROWS = {
    81: dict(name='vocals', slot=3, level=1.0, color=53,               # Ari kept pads 1-2 (09:10); 2026-11-06 + the first verse he sings and rolls
             samples=[CHOP_V, P('6-vocals-14-115bpm.wav'), VC + '6-vocals-02_verse-115bpm-chop4.wav', P('6-vocals-03-115bpm.wav'),
                      VC + '6-vocals-02_build-115bpm-chop4.wav', VC + '6-vocals-03_heyboy-115bpm-chop4.wav',
                      VC + '6-vocals-04_choir-115bpm-chop4.wav', VC + '6-vocals-12_choir-115bpm.wav'],   # verse, verse 03, "Baby's" roll, "Hey boy" roll, then the choir ALONE (karaoke split, no lead): "Ooh... oh I wonder wonder wonder who" (04, 4 bars), "Oh wonder... ooh" (12)
             samples2=[P('6-vocals-15-115bpm.wav'), P('6-vocals-16-115bpm.wav'), P('6-vocals-12-115bpm.wav'), P('6-vocals-04-115bpm.wav'),   # row page 2 (round button at the
                       VC + '6-vocals-04_choir-115bpm.wav', VC + '6-vocals-14_choir-115bpm.wav', VC + '6-vocals-15_choir-115bpm.wav']),   # row's end, CC 89): loops 15, 16, 12, 04, then the choir alone 04 / 14 / 15
    71: dict(name='keys',   slot=1, level=1.2, color=45, samples=[P(f'4-piano-{n}-115bpm.wav') for n in ('14', '15', '16', '13', '03', '09', '10', '17')]),
    61: dict(name='bridge keys', slot=1, level=1.2, color=21,          # same slot as keys: a bridge pad swaps the row 2 piano out
             samples=[P(f'4-piano-{n}-115bpm-chop4.wav') for n in ('08', '09', '10', '13')]),   # 4-bar bridge halves: 08 C#-C-B-G#, 09/10 F#-B, 13 D-C#-C-A#
    51: dict(name='horns', slot=2, level=1.2, color=9,                 # 'other' stem in the guitar slot; vamp loops with sound in all 8 bars
             samples=[P(f'5-other-{n}-115bpm.wav') for n in ('15', '16', '14')]),   # Ari kept pads 1-3 (11:05); 17, 12, 18, 07 dropped
    31: dict(name='crescendo', slot=2, level=1.0, color=5,             # same slot as horns. Pads 1-2 strings only ('other' 08/13 walk-down swell),
             samples=[P('5-other-08-115bpm-chop4.wav'), P('5-other-13-115bpm-chop4.wav')]           # pads 3-6 whole bridge = all stems but drums
                     + [P(f'7-mix-{n}-115bpm-chop4.wav') for n in ('08', '13', '09', '10')]),        # summed (7-mix-*): 08/13 swells, 09 b5-8 build, 10 b1-4
    21: dict(name='drums', slot=0, level=1.0, color=13, deck=json.load(open(os.path.join(here, 'deckc.json')))['C'],   # deck C = the record's drum stem
             samples=[P(f'1-drums-{n}-115bpm.wav') for n in ('15', '16', '12')] + [P('1-drums-13-115bpm-chop4.wav')]),   # Ari kept old pads 2, 3, 6, 8 (10:25); pad 4 = bridge walk-down 13a
    41: dict(name='bass', slot=0, level=1.0, color=37,                 # pads 1-4 vamp loops, pads 5-8 the bridge halves (same as row 3)
             samples=[P(f'2-bass-{n}-115bpm.wav') for n in ('14', '15', '16', '03')] + [P(f'2-bass-{n}-115bpm-chop4.wav') for n in ('08', '09', '10', '13')]),
}
# 2026-11-06 page 2 (Launchpad right arrow): Time Out Of Mind on deck B (toom-crate, 124 BPM loops locked to the clock).
# Pads only: turning the page changes no sound; a pad brings that row in. Horns, guitar and solo share deck B's guitar slot.
# Drums row (2026-11-06, Ari): the TOOM drum stem in deck C's slot, the same slot as page 1's Lowdown drums row, so a TOOM drum
# pad replaces the Lowdown drums at the next loop start (toom-crate re-cut on the kick since the old set's groove trouble).
Q = lambda stem, *nn: [CRB.replace('\\', '/') + '/' + next(f for f in os.listdir(CRB) if re.match(rf'\d-{stem}-{n}_', f)) for n in nn]
ROWS_TOOM = {
    81: dict(name='vocals', slot=3, level=1.0, color=53, deck=B,       # 2026-11-06: "Son" roll build -> "Son, you better be ready for love" -> verses -> "Time" roll -> choruses
             samples=[VC + '6-vocals-02_build-124bpm-chop4.wav', VC + '6-vocals-02_first-124bpm-chop4.wav', *Q('vocals', '02', '03', '05'),
                      VC + '6-vocals-04_time-124bpm-chop4.wav', *Q('vocals', '04', '07')]),   # 06, 11 (near empty), 12 dropped for room
    71: dict(name='piano',  slot=1, level=1.0, color=45, deck=B, samples=Q('piano', '05', '02', '03', '06', '12', '04', '07', '01')),
    61: dict(name='horns',  slot=2, level=1.0, color=9,  deck=B, samples=Q('other', '05', '02', '03', '06', '04', '07', '15', '01')),
    51: dict(name='guitar', slot=2, level=1.0, color=21, deck=B, samples=Q('guitar', '05', '02', '03', '06', '04', '07')),
    41: dict(name='bass',   slot=0, level=1.0, color=37, deck=B, samples=Q('bass', '05', '02', '03', '06', '04', '07', '13', '15')),   # 04/07/13 = walk-down
    31: dict(name='solo',   slot=2, level=1.0, color=5,  deck=B, samples=Q('guitar', '08', '09', '10', '14')),
    21: dict(name='drums',  slot=0, level=1.0, color=13, deck=ROWS[21]['deck'], samples=Q('drums', '05', '02', '03', '06', '04', '07', '08', '15')),   # 16 outro near silent
}
# 2026-11-06 page 3: Vulfpeck "Disco Ulysses" on deck D (disco-crate, 134 BPM loops on the record's kick, key B major; deckd_add.py).
# Deck D slots: 0 bass, 1 piano, 2 guitar, 3 other (horns/synth, bridge 11-12 only). No vocals: the top row is the horns/synth slot.
# Drums row = the Disco drum stem in deck C's slot 0, shared with the Lowdown and TOOM drums rows (as page 2 does it).
# Deck D's strip (Mixer strip 8, index 7) rests at 0: a page 3 pad cues its row silently, the moves row 'transition' fades it in.
D = json.load(open(os.path.join(here, 'deckd.json')))['D']
CRD = r'C:\Users\Arikl\Desktop\uvr-loops\crates\disco-crate'
QD = lambda stem, *nn: [CRD.replace('\\', '/') + '/' + next(f for f in os.listdir(CRD) if re.match(rf'\d-{stem}-{n}_', f)) for n in nn]
ROWS_DISCO = {
    81: dict(name='horns/synth', slot=3, level=1.0, color=9, deck=D, samples=QD('other', '11', '12')),   # the 'other' stem plays only in the bridge
    71: dict(name='piano',  slot=1, level=1.0, color=45, deck=D, samples=QD('piano', '15', '13', '14', '08', '06', '05', '02', '12')),    # choruses, verses, bridge
    51: dict(name='guitar', slot=2, level=1.0, color=21, deck=D, samples=QD('guitar', '14', '15', '13', '08', '02', '05', '06', '12')),
    41: dict(name='bass',   slot=0, level=1.0, color=37, deck=D, samples=QD('bass', '08', '13', '03', '05', '06', '02', '07', '15')),     # 07 = the break
    21: dict(name='drums',  slot=0, level=1.0, color=13, deck=ROWS[21]['deck'], samples=QD('drums', '08', '13', '05', '06', '03', '14', '09', '10')),   # 09-10 break: half-time kicks
}
PAGES = [dict(name='Lowdown', rows=ROWS, deck=A), dict(name='Time Out Of Mind', rows=ROWS_TOOM, deck=B), dict(name='Disco Ulysses', rows=ROWS_DISCO, deck=D)]   # deck = the song's own deck
# Arp keys per song page (pitch classes, C = 0). scale_scan.py 2026-11-06: both songs' bass sits in D major (D E F# G A B C#).
# Disco Ulysses: B major (B C# D# E F# G# A#, mask 3418; the crate's pin, key 11). If A# rubs: (1, 3, 4, 6, 8, 11) = mask 2394.
SCALES = {0: (1, 2, 4, 6, 7, 9, 11), 1: (1, 2, 4, 6, 7, 9, 11), 2: (1, 3, 4, 6, 8, 10, 11)}
# Acid patterns per song for the Synths page row 8 and phrase auto-change. acid_slots.py 2026-11-06: 8, 9, 15, 16, 19 sit inside
# the arp scale; 11, 12, 13, 17, 18 fall outside it and are dropped. The vamps stay first though outside too (10 has G# + A#,
# 14 has A#: chromatic passing notes against D major).
# Disco (2026-11-06, all 32 slots read against B major at TRANSPOSE 0; no page turn changes TRANSPOSE): 25 (starts on B: B C# E F# G#)
# and 12 (F#/B pump) sit inside B major; 2 (E D F# B, starts on E like the record's bar 1) and 22 (C# D F# B) add only D natural,
# the blue note of the record's own verse riff. No vamp for this song: the tonic pattern goes first.
ACID_SONG = {0: [10, 8, 9], 1: [14, 15, 16, 19], 2: [25, 12, 2, 22]}
PAGES.append(dict(name='Synths', rows={}, synth=True))   # page 4: arp + acid controls (synths.py); it and its moves act on the song playing
def base(strips=True):                                         # deck A + deck B strips; deck A slots without a row silent (strips=False: mixer strips untouched, a crash respawn)
    mix = {p['id']: p['value'] for p in json.loads(call('vcvrack_get_params', {'moduleId': MIX}))}
    if mix[3] < 0.05:                                          # deck B was closed: its page starts silent, then the strip opens
        call('vcvrack_set_params', {'moduleId': B, 'params': [{'id': 14 + k, 'value': 0.0} for k in range(4)]})
    if mix[7] < 0.05:                                          # deck D (Disco) closed: its slots silent; its strip stays where it is
        call('vcvrack_set_params', {'moduleId': D, 'params': [{'id': 14 + k, 'value': 0.0} for k in range(4)]})   # (rests at 0: transition opens it)
    if strips: call('vcvrack_set_params', {'moduleId': MIX, 'params': [{'id': k, 'value': v} for k, v in enumerate((0.0, 0.0, U, U))] + [{'id': 40 + k, 'value': 0} for k in range(4)]})
    rows = {r['slot'] for r in ROWS.values()}
    call('vcvrack_set_params', {'moduleId': A, 'params': [{'id': 14 + k, 'value': 0.0} for k in range(4) if k not in rows]})
def play(slot, path, level, deck=None):                        # path None = mute the slot; a new path lands at the next loop start
    deck = deck or A
    if path:
        st = json.loads(call('vcvrack_get_module_state', {'id': deck}))
        if st['data']['slots'][slot]['path'] != path:
            st['data']['slots'][slot]['path'] = path; st.pop('params', None)   # data only: a STUT press between the get and the set stays
            call('vcvrack_set_module_state', {'id': deck, 'state': st})
    call('vcvrack_set_params', {'moduleId': deck, 'params': [{'id': 14 + slot, 'value': level if path else 0.0}]})
CHOPS = os.path.join(here, 'chops.json')                       # source path -> [4-bar half A, half B] (null = none); written by the chop cutter
_chops = {'m': None, 'd': {}}
def chops():                                                   # read when it changes; missing or half-written = no chop pages
    try:
        m = (CHOPS, os.path.getmtime(CHOPS))
        if _chops['m'] != m: _chops.update(d=json.load(open(CHOPS)), m=m)
        return _chops['d']
    except (OSError, ValueError): return {}
def pages(r):                                                  # a row's pad pages (row-end round button cycles them): samples, samples2,
    ch = chops(); src = r['samples'] + r.get('samples2', [])   # then the 4-bar A/B halves of those samples, 8 pads (4 samples) a page
    halves = list(dict.fromkeys(h for s in src for h in (ch.get(s) or []) if h))
    return [r['samples']] + ([r['samples2']] if r.get('samples2') else []) + [halves[k:k + 8] for k in range(0, len(halves), 8)]
def kind(r, k):                                                # 'main' / 'extra' (samples2) / 'chop'
    return 'main' if not k else 'extra' if k == 1 and r.get('samples2') else 'chop'
def cur(r, k=0):                                               # a row's sample list on show: its row page k (gone = page 1)
    P = pages(r); return P[k] if 0 <= k < len(P) else P[0]
def now(rows=None, pages_=None, paths=None):                   # row -> index of the sample playing (None = muted), read from the rig.
    out = {}                                                   # pages_: row -> row page on show (default 0); the index is in that
    for b, r in (rows or ROWS).items():                        # list, None when the sample playing sits on another row page.
        st = json.loads(call('vcvrack_get_module_state', {'id': r.get('deck', A)})); lv = {p['id']: p['value'] for p in st['params']}
        path = st['data']['slots'][r['slot']]['path']; L = cur(r, (pages_ or {}).get(b, 0))
        on = lv[14 + r['slot']] > 0.01 and any(path in P for P in pages(r))
        out[b] = L.index(path) if on and path in L else None
        if paths is not None: paths[b] = path if on else None  # paths: filled with row -> the row's sample playing (None = muted)
    return out
