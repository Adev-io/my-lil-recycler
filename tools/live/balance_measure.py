# Loudness per source (Rack-side) + spectrum of what Ari hears (MG-XU return). Prints numbers only.
import json, os, sys, numpy as np, sounddevice as sd, librosa
here = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(here, 'rack.py')).read().split('if sys.argv[1]')[0])
call = lambda n, a: rpc('tools/call', {'name': n, 'arguments': a}, timeout=40)['result']['content'][0]['text']
A, ACID, MIX, DRUMS = 5192219511640844, 8333663024495709, 2874844741614313, 7189220493962056
def meas(mid, out, s=4):
    m = json.loads(call('vcvrack_measure', {'moduleId': mid, 'outputId': out, 'seconds': s})); return m['lufs'], m['left']['rmsDb'], m['left']['peakDb']
for name, mid, out in (('drums', DRUMS, 0), ('acid', ACID, 3), ('deckA mix', A, 8), ('A1 bass stem', A, 0), ('A2 piano', A, 1), ('A3 guitar chop', A, 2), ('A4 vocal chop', A, 3), ('MASTER', MIX, 0)):
    l, r, p = meas(mid, out); print(f'{name:15s} LUFS {l:6.1f}  rms {r:6.1f}  peak {p:6.1f}')
mx = {p['id']: p for p in json.loads(call('vcvrack_get_params', {'moduleId': MIX}))}
print('mixer strips 1-3 level', [mx[i]['displayValue'][:6] for i in range(3)], 'pan', [mx[8 + i]['displayValue'][:5] for i in range(3)], 'master', mx[56]['displayValue'][:6])
da = {p['id']: p for p in json.loads(call('vcvrack_get_params', {'moduleId': A}))}
print('deck A levels', [da[i]['displayValue'][:6] for i in (14, 15, 16, 17)])
print('deck A shaping:', ' | '.join(f"{i}:{da[i]['name'][:16]}={da[i]['displayValue'][:6]}" for i in range(20, 40)))
dr = {p['id']: p for p in json.loads(call('vcvrack_get_params', {'moduleId': DRUMS}))}
print('drums: mix', dr[5]['displayValue'], 'LP', dr[14]['displayValue'], 'HP', dr[15]['displayValue'], 'comp thr', dr[16]['displayValue'], 'ratio', dr[17]['displayValue'])
ac = {p['id']: p for p in json.loads(call('vcvrack_get_params', {'moduleId': ACID}))}
print('acid: volume', ac[6]['displayValue'], 'cutoff', ac[1]['displayValue'], 'res', ac[2]['displayValue'], 'wave', ac[7]['displayValue'], 'HP', ac[15]['displayValue'])
# what Ari hears
dev = next(i for i, d in enumerate(sd.query_devices()) if 'MG-XU' in d['name'] and d['max_input_channels'] > 0 and sd.query_hostapis(d['hostapi'])['name'] == 'Windows WASAPI')
sr = 48000; y = sd.rec(int(10 * sr), samplerate=sr, channels=2, device=dev, dtype='float32'); sd.wait(); m = y.mean(1)
S = np.abs(librosa.stft(m, n_fft=4096)) ** 2; f = librosa.fft_frequencies(sr=sr, n_fft=4096)
bands = [('sub <60', 0, 60), ('low 60-150', 60, 150), ('lowmid 150-400', 150, 400), ('mid 400-2k', 400, 2000), ('himid 2k-6k', 2000, 6000), ('air >6k', 6000, 20000)]
tot = S.sum(); e = {n: 10 * np.log10(S[(f >= lo) & (f < hi)].sum() / tot + 1e-12) for n, lo, hi in bands}
print('heard: peak %.1f dBFS, rms %.1f dBFS' % (20 * np.log10(np.abs(m).max() + 1e-9), 20 * np.log10(np.sqrt(np.mean(m ** 2)) + 1e-9)))
print('heard band energy (dB of total):', '  '.join(f'{n} {v:5.1f}' for n, v in e.items()))
print('pink reference (dB of total)    :', '  '.join(f'{n} {v:5.1f}' for n, v in zip(e.keys(), [-11.9, -7.9, -7.3, -5.3, -7.1, -7.6])))
