# Loop 14: chords (piano stem), bass notes (bass stem), swing of the record (off-16th position), and what Acid I-B5 plays.
import os, sys, json, collections, numpy as np, librosa, soundfile as sf
sys.path.insert(0, r"C:\Users\Arikl\dev\mcp-servers\my-lil-uvr-mcp")
from uvrcore import notes
here = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(here, 'rack.py')).read().split('if sys.argv[1]')[0])
call = lambda n, a: rpc('tools/call', {'name': n, 'arguments': a}, timeout=30)['result']['content'][0]['text']
CR = r'C:\Users\Arikl\Desktop\uvr-loops\crates\lowdown2-crate'
N = 'C C# D D# E F F# G G# A A# B'.split()
piano, bass, drums = (os.path.join(CR, f'{n}-14-115bpm.wav') for n in ('4-piano', '2-bass', '1-drums'))
r = notes.grab(piano, mode='loop', outputs=('json',))
d = collections.Counter()
for c in r['chords']:
    if c['chord'] != 'N.C.': d[c['chord']] += c['end'] - c['start']
tot = sum(d.values()) or 1
print('loop 14 piano key', r['key'], '| chords by time:', ', '.join(f'{k} {v / tot * 100:.0f}%' for k, v in d.most_common(6)))
print('   chord order:', [c['chord'] for c in r['chords'] if c['chord'] != 'N.C.'][:16])
y, sr = librosa.load(bass, sr=22050, mono=True)
f0, v, _ = librosa.pyin(y, fmin=40, fmax=330, sr=sr, hop_length=512, frame_length=4096)
m = np.round(librosa.hz_to_midi(f0[v])).astype(int); pc = np.bincount(m % 12, minlength=12)
print('loop 14 bass pitch classes:', ', '.join(f'{N[i]} {pc[i] / pc.sum() * 100:.0f}%' for i in np.argsort(pc)[::-1][:5]))
# swing: off-16th position inside each 8th, from the drum stem (hats) and from the bass
for name, path, pre in (('drums', drums, 0.97), ('bass', bass, None)):
    yy, _ = librosa.load(path, sr=22050, mono=True); beat = len(yy) / 22050 / 32; e8 = beat / 2
    if pre: yy = librosa.effects.preemphasis(yy, coef=pre)
    on = librosa.onset.onset_detect(y=yy, sr=22050, units='time', delta=0.08)
    ph = ((on / e8) % 1.0); off = ph[(ph > 0.3) & (ph < 0.85)]
    print(f'swing from {name}: {len(on)} onsets, {len(off)} off-16ths, median position {np.median(off):.2f} of an 8th (0.50 straight, 0.67 triplet)' if len(off) else f'swing from {name}: no off-16ths')
# what Acid I-B5 plays
st = json.loads(call('vcvrack_get_module_state', {'id': 8333663024495709}))['data']['patterns'][12]
steps = [s for s in st['steps'] if s['gate'] == 'note']
print('Acid I-B5 notes:', collections.Counter(N[(36 + s['note'] + 12 * s['oct']) % 12] for s in steps).most_common())
ps = {p['id']: p for p in json.loads(call('vcvrack_get_params', {'moduleId': 7189220493962056}))}
print('drums pattern now', ps[3]['displayValue'], '| acid swing', [p['displayValue'] for p in json.loads(call('vcvrack_get_params', {'moduleId': 8333663024495709})) if p['id'] == 22][0])
