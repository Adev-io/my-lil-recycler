# Cut disco-crate (Vulfpeck "Disco Ulysses (Instrumental)", BS-Roformer-SW 6 stems) into 8-bar loops on the record's kick.
# Live band, ~134 BPM with +-2 % drift: the beat grid is a kick PLL (four on the floor: every beat = the low-band onset peak
# within +-12 % of a beat of the prediction), first downbeat = the bass entry at 18.98 s (piano/guitar exits and the video's
# chapter cards land on the 32-beat grid from there; snare on grid beats 2 and 4). Each loop start is then moved onto the
# kick by the loop's circular-mean kick offset (as recut_toom.py). Loop 01 = the intro bar group before the bass (no kick:
# grid extrapolated). Loops under -42 dBFS RMS go to crates\_quiet\disco (Recycler normalises renders -> hiss), under -60
# are not written. Crate loops are pinned in library.json (tempo = 1920/len, key G# minor, keyConf 1).
# usage: py -3.11 disco_crate.py --dry   (table only)   |   py -3.11 disco_crate.py   (write crate + pin; library backed up)
import os, sys, json, shutil, time, numpy as np, librosa, soundfile as sf
ST = r"C:\Users\Arikl\Desktop\uvr-loops\disco-ulysses\stems\Vulfpeck - Disco Ulysses (Instrumental)_(%s)_BS-Roformer-SW.wav"
CR = r'C:\Users\Arikl\Desktop\uvr-loops\crates\disco-crate'; Q = r'C:\Users\Arikl\Desktop\uvr-loops\crates\_quiet\disco'
LIB = os.path.expandvars(r'%LOCALAPPDATA%\Rack2\MyLilRecycler\library.json')
STEMS = ['drums', 'bass', 'guitar', 'piano', 'other', 'vocals']
ROLE = {'drums': [1, 0, 0, 0], 'bass': [0, 1, 0, 0], 'other': [0, 0, .5, .5]}
KEY, MINOR = 11, False                    # B major / G# minor pitch set (keys chroma tops B D# G#; bass E G# F# C# D# B + chromatic G, D)
D0 = 18.98                                # first downbeat (bass entry); every loop's bar 1 is E in the bass
# riff A = 'verse' (E G# F# B G# D G# G per bar pair), cadence B = 'chorus' (E B D# C# C# F# G# B = IV iii ii V vi in B),
# break = drums + bass only, bridge = bass out, horns/synth ('other') in. Chapters = the video's title cards (approximate).
SECTIONS = dict(zip([f'{i:02d}' for i in range(1, 17)], 'intro verse chorus chorus verse verse break chorus break break bridge bridge chorus chorus chorus outro'.split()))
CHAPTERS = dict(zip([f'{i:02d}' for i in range(1, 17)], ['Vulf presents', 'Disco Ulysses', 'Suitors', 'Lotus Eaters', 'Lotus Eaters', 'Cyclops', 'Circe', 'Circe',
                    'Underworld', 'Sirens', 'Skylla & Charybdis', 'Helios', 'Helios', "Kalypso's Prison", 'Home', 'Home']))
MP4 = r"G:\My Drive\Archive\Downloads-media\VULFPECK_____Disco_Ulysses_(Instrumental).mp4"
dry = '--dry' in sys.argv
sr = 22050; hop = 64
yd, _ = librosa.load(ST % 'drums', sr=sr, mono=True)
S = np.abs(librosa.stft(yd, n_fft=1024, hop_length=hop)); fr = librosa.fft_frequencies(sr=sr, n_fft=1024)
lo = np.maximum(0, np.diff(S[(fr >= 30) & (fr < 120)].sum(0), prepend=0)); lo /= lo.max()
tt = librosa.frames_to_time(np.arange(len(lo)), sr=sr, hop_length=hop)
def track(t0, d, tend, p0=0.4469):
    beats, per = [t0], [p0] * 8
    while True:
        p = float(np.median(per[-8:])); x = beats[-1] + d * p
        if (d > 0 and x > tend) or (d < 0 and x < tend): return beats
        a, b = np.searchsorted(tt, x - 0.12 * p), np.searchsorted(tt, x + 0.12 * p)
        j = a + int(np.argmax(lo[a:b])) if b > a else -1
        nx = float(tt[j]) if j >= 0 and lo[j] > 0.12 else x
        per.append(abs(nx - beats[-1])); beats.append(nx)
j = np.searchsorted(tt, D0); a = j - 40; seed = float(tt[a + int(np.argmax(lo[a:j + 40]))])
grid = np.array(sorted(set(track(seed, -1, 0.3)[1:] + track(seed, 1, tt[-1] - 0.3))))
i0 = int(np.argmin(np.abs(grid - D0)))
idx = list(range(i0 - 32, len(grid), 32))
kick = librosa.onset.onset_detect(y=librosa.effects.preemphasis(yd, coef=-0.97), sr=sr, units='time', hop_length=64, delta=0.2, backtrack=False)
def off(a, b):
    beat = (b - a) / 32; ks = kick[(kick >= a - beat / 2) & (kick < b - beat / 2)]
    if len(ks) < 8: return 0.0
    pos = (ks - a) / beat; return float(np.angle(np.mean(np.exp(2j * np.pi * (pos % 1)))) / (2 * np.pi) * beat)
starts = [float(grid[i]) for i in idx]
new = [s + (off(s, starts[k + 1]) if k + 1 < len(starts) else off(starts[k - 1], s)) for k, s in enumerate(starts)]
print('downbeat', round(grid[i0], 3), 's | loops', len(new) - 1, '| boundary moves (ms):', [round((n - s) * 1000) for n, s in zip(new, starts)])
Y = {s: sf.read(ST % s, always_2d=True) for s in STEMS}
fs = Y['drums'][1]
db = lambda x: float(20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12))
rows = []
for k in range(len(new) - 1):
    a, b = int(round(new[k] * fs)), int(round(new[k + 1] * fs))
    rows.append((k + 1, new[k], (b - a) / fs, {s: db(Y[s][0][a:b]) for s in STEMS}))
print(' NN   start   len  bpm  ' + ' '.join(f'{s:>7s}' for s in STEMS))
for n, t, L, r in rows: print(f' {n:02d} {t:7.2f} {L:6.2f} {1920 / L:5.1f} ' + ' '.join(f'{r[s]:7.1f}' for s in STEMS), SECTIONS.get(f'{n:02d}', ''))
if dry: sys.exit(0)
assert SECTIONS, 'fill SECTIONS after the dry run'
assert not os.path.exists(CR) or not os.listdir(CR), CR + ' not empty'
os.makedirs(CR, exist_ok=True); os.makedirs(Q, exist_ok=True)
bk = LIB + time.strftime('.bak-%Y%m%d-%H%M%S'); shutil.copy2(LIB, bk); print('library backup', bk)
lib = [e for e in json.load(open(LIB, encoding='utf-8')) if '/disco-crate/' not in e['path']]
bpm = int(round(60 / np.median(np.diff(grid[i0:]))))
made, quiet, silent = [], [], []
fade = int(0.003 * fs); ramp = np.linspace(0, 1, fade)[:, None]
for si, stem in enumerate(STEMS, 1):
    y = Y[stem][0]
    for n, t, L, r in rows:
        a = int(round(new[n - 1] * fs)); b = int(round(new[n] * fs)); seg = y[a:b].copy(); v = r[stem]
        if v < -60: silent.append(f'{si}-{stem}-{n:02d}'); continue
        seg[:fade] *= ramp; seg[-fade:] *= ramp[::-1]
        name = f'{si}-{stem}-{n:02d}_{SECTIONS[f"{n:02d}"]}-{bpm}bpm.wav'
        if v < -42: sf.write(os.path.join(Q, name), seg, fs, subtype='PCM_16'); quiet.append((name, round(v, 1))); continue
        p = os.path.join(CR, name); sf.write(p, seg, fs, subtype='PCM_16'); made.append(name)
        st = os.stat(p); secs = len(seg) / fs
        lib.append(dict(path=p.replace('\\', '/'), size=st.st_size, mtime=int(st.st_mtime), sampleRate=fs, frames=len(seg), seconds=secs,
                        tempo=round(1920.0 / secs, 3), tempoConf=1.0, bars=8, key=KEY, minor=MINOR, keyConf=1.0, onsets=[], bestOnset=0.0,
                        role=[float(x) for x in ROLE.get(stem, [0, 0, 1, 0])], rms=v, peak=float(20 * np.log10(np.abs(seg).max() + 1e-12))))
with open(LIB, 'w', encoding='utf-8') as f: json.dump(lib, f, ensure_ascii=False)
with open(os.path.join(CR, 'crate.json'), 'w', encoding='utf-8') as f:
    json.dump(dict(title='Disco Ulysses', artist='Vulfpeck', song='Disco Ulysses (Instrumental)', cover='cover.jpg', sections=SECTIONS, chapters=CHAPTERS), f, indent=1, ensure_ascii=False)
import subprocess                          # cover: the 'ulysses / book Homer / music Vulfpeck' card at 0:30, square 600
r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '30', '-i', MP4, '-frames:v', '1', '-vf', 'crop=720:720:280:0,scale=600:600', '-q:v', '2',
                    os.path.join(CR, 'cover.jpg')], stdin=subprocess.DEVNULL); print('cover.jpg', 'ok' if r.returncode == 0 else f'FAILED {r.returncode}')
print('crate files', len(made), '| quiet', len(quiet), quiet, '| not written (< -60 dB)', len(silent))
print('cache entries for disco-crate:', sum('/disco-crate/' in e['path'] for e in json.load(open(LIB, encoding='utf-8'))))
for f in sorted(x for x in made if x.startswith('1-drums')):     # verify: kick offset inside each drum loop vs its own 32-beat grid
    yy, _ = librosa.load(os.path.join(CR, f), sr=sr, mono=True); d = len(yy) / sr; beat = d / 32
    ks = librosa.onset.onset_detect(y=librosa.effects.preemphasis(yy, coef=-0.97), sr=sr, units='time', hop_length=64, delta=0.2, backtrack=False)
    ph = np.exp(2j * np.pi * ((ks / beat) % 1)); bars = [np.angle(np.mean(ph[(ks >= q * 4 * beat) & (ks < (q + 1) * 4 * beat)])) / (2 * np.pi) * beat * 1000 for q in range(8)]
    print(f'  {f}: kick off-beat {np.angle(np.mean(ph)) / (2 * np.pi) * beat * 1000:+4.0f} ms, per bar {[round(x) for x in bars]}')
