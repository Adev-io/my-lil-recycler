# Record what Ari hears (Yamaha MG-XU USB return, WASAPI) for N seconds and measure the groove: hat off-16th position
# (swing), and kick-to-grid offset. usage: tap.py [seconds]
import sys, os, time, numpy as np, sounddevice as sd, soundfile as sf, librosa
secs = float(sys.argv[1]) if len(sys.argv) > 1 else 12
dev = next(i for i, d in enumerate(sd.query_devices()) if 'MG-XU' in d['name'] and d['max_input_channels'] > 0 and sd.query_hostapis(d['hostapi'])['name'] == 'Windows WASAPI')
sr = 48000; y = sd.rec(int(secs * sr), samplerate=sr, channels=2, device=dev, dtype='float32'); sd.wait()
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tap.wav'); sf.write(out, y, sr); m = y.mean(1)
peak = 20 * np.log10(np.abs(m).max() + 1e-9); print(f'recorded {secs:.0f} s, peak {peak:.1f} dBFS')
if peak < -50: print('silent: the MG-XU USB return is not carrying the mix'); sys.exit(1)
beat = 60 / 120; e8 = beat / 2; e16 = beat / 4
hp = librosa.effects.preemphasis(m, coef=0.97)
on = librosa.onset.onset_detect(y=hp, sr=sr, units='time', hop_length=128, delta=0.1, backtrack=False)
# lock the grid phase to the strongest onsets (kick-ish, low band)
lo = m - librosa.effects.preemphasis(m, coef=0.999) if False else m
onk = librosa.onset.onset_detect(y=librosa.effects.preemphasis(m, coef=-0.97), sr=sr, units='time', hop_length=128, delta=0.3, backtrack=False)
ph = np.angle(np.mean(np.exp(2j * np.pi * (onk / beat)))) / (2 * np.pi) * beat
pos = ((on - ph) / e8) % 1.0; off = pos[(pos > 0.3) & (pos < 0.85)]; onb = pos[(pos < 0.12) | (pos > 0.92)]
print(f'grid phase {ph * 1000:+.0f} ms | {len(on)} onsets: {len(onb)} on the 8th, {len(off)} off-16ths at median {np.median(off):.2f} of an 8th (0.50 straight, 0.67 triplet)' if len(off) else 'no off-16th onsets found')
kk = ((onk - ph) / beat); kk = kk - np.round(kk); print(f'kick onsets {len(onk)}, median offset from the beat {np.median(kk) * beat * 1000:+.0f} ms, spread {np.median(abs(kk)) * beat * 1000:.0f} ms')
