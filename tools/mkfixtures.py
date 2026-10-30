"""Writes 14 synthetic WAV fixtures (44.1 kHz, 16-bit, stereo, peak 0.7) for the Recycler smoke test.

Usage: py -3.11 tools/mkfixtures.py <folder>

Three drum loops, bass lines and melodies (2 bars at 90 / 120 / 140 BPM in C minor / G minor / A major), three 8 s pads
in the same keys, and two file-name-tagged extras (break_100bpm.wav, sub_100bpm_F#min.wav). Stdlib only, deterministic.
All synthesis is band-limited (sines, additive saws) so nothing aliases into false onsets.
"""
import math
import os
import random
import struct
import sys
import wave
from array import array

RATE = 44100
PEAK = 0.7
TWO_PI = 2.0 * math.pi


def midi_hz(n):
    return 440.0 * 2.0 ** ((n - 69) / 12.0)


def loop_len(bpm):
    return int(round(8 * 60.0 / bpm * RATE))   # 2 bars of 4/4


def fade(x, start, length, ramp):
    """In-place linear fade in/out of `ramp` samples on x[start:start+length]."""
    ramp = max(1, min(ramp, length // 2))
    for i in range(ramp):
        g = i / ramp
        x[start + i] *= g
        x[start + length - 1 - i] *= g


# --- drums -----------------------------------------------------------------------------------------------------------
def drums(bpm):
    n = loop_len(bpm)
    out = [0.0] * n
    beat = 60.0 / bpm * RATE
    for b in range(8):                                          # kick on 1 and 3, snare on 2 and 4
        at = int(round(b * beat))
        if b % 2 == 0:
            ln = int(0.120 * RATE)
            ph = 0.0
            for i in range(min(ln, n - at)):
                t = i / RATE
                f = 55.0 + 55.0 * math.exp(-t / 0.025)          # 110 -> 55 Hz pitch drop
                ph += TWO_PI * f / RATE
                out[at + i] += math.sin(ph) * math.exp(-t / 0.045) * 1.0
        else:
            ln = int(0.150 * RATE)
            prev = 0.0
            for i in range(min(ln, n - at)):
                w = random.uniform(-1.0, 1.0)
                out[at + i] += (w - prev) * 0.5 * math.exp(-i / RATE / 0.04) * 0.8   # 2-tap difference = crude HP
                prev = w
    eighth = beat / 2
    for e in range(16):                                         # closed hat every 8th
        at = int(round(e * eighth))
        ln = int(0.025 * RATE)
        p1 = p2 = 0.0
        for i in range(min(ln, n - at)):
            w = random.uniform(-1.0, 1.0)
            out[at + i] += (w - 2 * p1 + p2) * 0.25 * math.exp(-i / RATE / 0.008) * 0.5   # 2nd difference: brighter
            p2, p1 = p1, w
    return out


# --- bass: band-limited saw from an additive one-cycle table ---------------------------------------------------------
T = 4096
SIN_TAB = [math.sin(TWO_PI * i / T) for i in range(T)]
_saw_cache = {}


def saw_table(f):
    tab = _saw_cache.get(f)
    if tab is None:
        tab = [0.0] * T
        k = 1
        while k * f < 0.45 * RATE:
            inv = 1.0 / k
            tab = [a + SIN_TAB[(k * i) % T] * inv for i, a in enumerate(tab)]
            k += 1
        tab.append(tab[0])                                      # guard point for interpolation
        _saw_cache[f] = tab
    return tab


def bass(bpm, root, minor):
    n = loop_len(bpm)
    out = [0.0] * n
    eighth = 30.0 / bpm * RATE
    third = 3 if minor else 4
    pattern = [root, root + 7, root + 12, root + third]         # root - fifth - octave - third
    gap = int(0.020 * RATE)
    for e in range(16):
        at = int(round(e * eighth))
        end = min(n, int(round((e + 1) * eighth)) - gap)
        f = midi_hz(pattern[e % 4])
        tab = saw_table(f)
        ph = 0.0
        inc = f / RATE * T
        for i in range(at, end):
            j = int(ph)
            fr = ph - j
            out[i] = tab[j] + (tab[j + 1] - tab[j]) * fr
            ph += inc
            if ph >= T:
                ph -= T
        fade(out, at, end - at, int(0.010 * RATE))
    return out


# --- melody: sine arpeggio --------------------------------------------------------------------------------------------
def melody(bpm, root, minor):
    n = loop_len(bpm)
    out = [0.0] * n
    eighth = 30.0 / bpm * RATE
    third = 3 if minor else 4
    pattern = [root, root + third, root + 7, root + 12]         # root - third - fifth - octave
    for e in range(16):
        at = int(round(e * eighth))
        end = min(n, int(round((e + 1) * eighth)))
        w = TWO_PI * midi_hz(pattern[e % 4]) / RATE
        for i in range(at, end):
            out[i] = math.sin(w * (i - at))
        fade(out, at, end - at, int(0.010 * RATE))
    return out


# --- pad: sustained triad with a slow wobble --------------------------------------------------------------------------
def pad(root, minor):
    n = 8 * RATE
    third = 3 if minor else 4
    ws = [TWO_PI * midi_hz(root + d) / RATE for d in (0, third, 7, 12)]
    wob = TWO_PI * 0.5 / RATE
    out = [(math.sin(ws[0] * i) + math.sin(ws[1] * i) + math.sin(ws[2] * i) + math.sin(ws[3] * i))
           * (0.75 + 0.25 * math.sin(wob * i)) for i in range(n)]
    fade(out, 0, n, int(0.5 * RATE))
    return out


# --- output -----------------------------------------------------------------------------------------------------------
def write(path, x):
    peak = max(abs(v) for v in x) or 1.0
    g = PEAK / peak * 32767.0
    pcm = array('h')
    for v in x:
        s = int(round(v * g))
        pcm.append(s)
        pcm.append(s)                                           # identical L/R
    if sys.byteorder == 'big':
        pcm.byteswap()
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())
    return len(x) / RATE


def main():
    if len(sys.argv) != 2:
        sys.exit('usage: py -3.11 tools/mkfixtures.py <folder>')
    folder = sys.argv[1]
    os.makedirs(folder, exist_ok=True)
    random.seed(1)
    # (suffix, bpm, key name, bass root midi, melody root midi, pad root midi, minor)
    sets = [('a', 90, 'C minor', 36, 72, 60, True),             # C2 65 Hz / C5 523 Hz / C4
            ('b', 120, 'G minor', 31, 67, 55, True),            # G1 49 Hz / G4 392 Hz / G3
            ('c', 140, 'A major', 33, 69, 57, False)]           # A1 55 Hz / A4 440 Hz / A3
    jobs = []
    for s, bpm, key, rb, rm, rp, mi in sets:
        jobs.append(('beat_%s.wav' % s, bpm, '-', lambda bpm=bpm: drums(bpm)))
    for s, bpm, key, rb, rm, rp, mi in sets:
        jobs.append(('low_%s.wav' % s, bpm, key, lambda bpm=bpm, rb=rb, mi=mi: bass(bpm, rb, mi)))
    for s, bpm, key, rb, rm, rp, mi in sets:
        jobs.append(('lead_%s.wav' % s, bpm, key, lambda bpm=bpm, rm=rm, mi=mi: melody(bpm, rm, mi)))
    for s, bpm, key, rb, rm, rp, mi in sets:
        jobs.append(('air_%s.wav' % s, '-', key, lambda rp=rp, mi=mi: pad(rp, mi)))
    jobs.append(('break_100bpm.wav', 100, '-', lambda: drums(100)))
    jobs.append(('sub_100bpm_F#min.wav', 100, 'F# minor', lambda: bass(100, 30, True)))   # F#1 46 Hz
    for name, bpm, key, make in jobs:
        secs = write(os.path.join(folder, name), make())
        print('%-22s %6.3f s  bpm %-4s key %s' % (name, secs, bpm, key))


if __name__ == '__main__':
    main()
