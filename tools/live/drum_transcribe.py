# Transcribe a record's drum loop into a My lil Drums pattern: kick (row 0), snare (row 1), closed hat (row 2), with
# velocities from the record. 2-bar pattern (32 x 16ths), built from the 8-bar loop by taking the 75th percentile across
# its four 2-bar halves (keeps the groove, drops one-off fills). Optional clap (row 4) on 2 and 4.
# usage: drum_transcribe.py <loop.wav> <pattern 1..16> <rows: k|ks|ksh|kshc> [--light]   (--light: hats only on 8ths)
import os, sys, json, numpy as np, soundfile as sf, librosa
from scipy.signal import butter, sosfiltfilt
here = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(here, 'rack.py')).read().split('if sys.argv[1]')[0])
call = lambda n, a: rpc('tools/call', {'name': n, 'arguments': a}, timeout=60)['result']['content'][0]['text']
DRUMS = 7189220493962056
path, patn, rows = sys.argv[1], int(sys.argv[2]), sys.argv[3]; light = '--light' in sys.argv
y, sr = sf.read(path, always_2d=True); m = y.mean(1).astype(np.float32); step = len(m) / 128          # 8 bars x 16 steps
def band(lo, hi):
    sos = butter(4, [lo, min(hi, sr / 2 - 1)], btype='band', fs=sr, output='sos'); return sosfiltfilt(sos, m).astype(np.float32)
def grid_env(sig):                     # onset strength sampled at each 16th (max within +-15 ms)
    oe = librosa.onset.onset_strength(y=sig, sr=sr, hop_length=64); t = librosa.frames_to_time(np.arange(len(oe)), sr=sr, hop_length=64)
    out = np.zeros(128)
    for i in range(128):
        c = i * step / sr; lo, hi = np.searchsorted(t, c - 0.015), np.searchsorted(t, c + 0.015)
        out[i] = oe[lo:hi].max() if hi > lo else 0
    return out
def fold(e):                           # 128 steps -> 32: 75th percentile over the four 2-bar halves
    return np.percentile(e.reshape(4, 32), 75, axis=0)
def vel(e, floor=0.18):               # normalised strength -> hex velocity, ghost notes allowed
    e = e / (e.max() + 1e-9); v = np.where(e >= floor, 0x28 + (0x7F - 0x28) * (e - floor) / (1 - floor), 0).astype(int)
    return v
kick = vel(fold(grid_env(band(40, 130))))
snare = vel(fold(grid_env(band(150, 450)) * grid_env(band(2000, 6000))), floor=0.22)   # body AND crack together
hat = vel(fold(grid_env(band(6000, 16000))), floor=0.15)
snare[kick > 0] = np.where(snare[kick > 0] > 0x60, snare[kick > 0], 0)                    # don't double every kick with a weak snare
if light: hat[1::2] = 0
if '--house' in sys.argv:                                   # dance floor: kick on every beat, backbeat on 2 and 4, record's extras as ghosts
    kick = np.where(kick > 0x60, 0x38, kick); kick[kick > 0x38] = 0x38
    kick[0::4] = np.maximum(kick[0::4], 0x72); kick[0::8] = 0x7e
    snare = np.minimum(snare, 0x40); snare[[4, 12, 20, 28]] = 0x74
clap = np.zeros(32, dtype=int); clap[[4, 12, 20, 28]] = 0x70
sel = {'k': [kick], 'ks': [kick, snare], 'ksh': [kick, snare, hat], 'kshc': [kick, snare, hat, clap]}[rows]
ROW = {0: 0, 1: 1, 2: 2, 3: 4}
st = json.loads(call('vcvrack_get_module_state', {'id': DRUMS}))
pat = st['data']['patterns'][patn - 1]; pat['length'] = 32
pat['rows'] = ['00' * 64 for _ in pat['rows']]
for j, v in enumerate(sel):
    pat['rows'][ROW[j]] = ''.join(f'{int(x):02x}' for x in v) + '00' * 32
call('vcvrack_set_module_state', {'id': DRUMS, 'state': st})
show = lambda v: ''.join('X' if x >= 0x60 else ('x' if x >= 0x40 else ('.' if x else '-')) for x in v)
print(f'pattern {patn} from {os.path.basename(path)} ({rows}{" light" if light else ""}), 32 steps:')
for name, v in zip(['kick ', 'snare', 'hat  ', 'clap '], sel): print(f'  {name} {show(v[:16])} | {show(v[16:])}   hits {int((v > 0).sum())}, vel {v[v > 0].min() if (v > 0).any() else 0:02x}-{v.max():02x}')
