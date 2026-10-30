// signals.h: deterministic synthetic test signals (clicks, tones, noise, simple parts), mono, at any rate.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include <cmath>
#include <cstdint>
#include <vector>

namespace sig
{
const double PI = 3.14159265358979323846;

// xorshift32: same sequence on every platform, never rand()
struct Rng
{
    uint32_t s;
    explicit Rng (uint32_t seed) : s (seed ? seed : 1u) {}
    uint32_t next() { s ^= s << 13; s ^= s >> 17; s ^= s << 5; return s; }
    float uni() { return (float) (next() >> 8) / 16777216.f * 2.f - 1.f; }   // -1 .. 1
};

inline float midiHz (float m) { return 440.f * std::pow (2.f, (m - 69.f) / 12.f); }
inline int len (float seconds, int rate) { return (int) std::lround ((double) seconds * rate); }

// a decaying white-noise burst added at sample `at`
inline void burst (std::vector<float>& out, int at, int rate, float ms, float tauMs, float peak, Rng& rng)
{
    const int n = (int) (ms * 0.001f * rate);
    for (int i = 0; i < n && at + i < (int) out.size(); ++i)
        if (at + i >= 0) out[at + i] += peak * std::exp (-(float) i / (tauMs * 0.001f * rate)) * rng.uni();
}

// a note's amplitude: linear attack and release inside its own span of n samples
inline float env (int i, int n, int attack, int release)
{
    float a = 1.f;
    if (attack > 0 && i < attack) a = (float) i / attack;
    if (release > 0 && i > n - release) a = std::fmin (a, (float) (n - i) / release);
    return a;
}

// 4 clicks per bar; each a 5 ms exponentially decaying noise burst, peak 0.8; jitter shifts each by uniform +-jitterMs
inline std::vector<float> clickTrack (float bpm, int bars, int rate, float jitterMs = 0.f, uint32_t seed = 1)
{
    const double beat = 60.0 / bpm;
    std::vector<float> out (len ((float) (beat * 4 * bars), rate), 0.f);
    Rng rng (seed);
    for (int i = 0; i < 4 * bars; ++i)
    {
        const double t = i * beat + rng.uni() * jitterMs * 0.001;
        burst (out, (int) std::lround (std::fmax (0.0, t) * rate), rate, 5.f, 1.f, 0.8f, rng);
    }
    return out;
}

inline std::vector<float> sine (float hz, float seconds, int rate)
{
    std::vector<float> out (len (seconds, rate));
    for (size_t i = 0; i < out.size(); ++i) out[i] = 0.5f * (float) std::sin (2.0 * PI * hz * (double) i / rate);
    return out;
}

// Band-limited saw at phase p (cycles), -1 .. 1 (+Gibbs ~9 %): additive sum of sin(2 pi k p) / k for k*hz < 0.45 rate.
// Not the naive 2*frac(p) - 1: a naive saw aliases, and its folded partials beat against the true harmonics, which the
// onset detector rightly reads as ~12 attacks/s at some pitches (48 false onsets in 4 s at 329.6 Hz).
inline double blSaw (double p, double hz, int rate)
{
    const double x = 2.0 * PI * (p - std::floor (p)), c = 2.0 * std::cos (x);
    double s = 0, sk = std::sin (x), skm1 = 0;   // sin(k x) by the Chebyshev recurrence
    for (int k = 1; k * hz < 0.45 * rate; ++k)
    {
        s += sk / k;
        const double next = c * sk - skm1;
        skm1 = sk;
        sk = next;
    }
    return -2.0 / PI * s;
}

inline std::vector<float> saw (float hz, float seconds, int rate)
{
    std::vector<float> out (len (seconds, rate));
    for (size_t i = 0; i < out.size(); ++i) out[i] = 0.5f * (float) blSaw (hz * (double) i / rate, hz, rate);
    return out;
}

// evenly spaced 30 ms noise bursts (8 ms decay), peak 0.8
inline std::vector<float> noiseBursts (float perSecond, float seconds, int rate, uint32_t seed)
{
    std::vector<float> out (len (seconds, rate), 0.f);
    Rng rng (seed);
    for (int k = 0; k < (int) std::floor (seconds * perSecond + 1e-6f); ++k)
        burst (out, (int) std::lround (k / (double) perSecond * rate), rate, 30.f, 8.f, 0.8f, rng);
    return out;
}

// root, third, fifth, octave as 8th notes at 120 BPM; band-limited saw, 10 ms attack, 50 ms release, peak ~0.55
inline std::vector<float> arpeggio (int rootMidi, bool minor, float seconds, int rate)
{
    const int steps[4] = { 0, minor ? 3 : 4, 7, 12 };
    const int note = len (0.25f, rate), attack = len (0.01f, rate), release = len (0.05f, rate);
    std::vector<float> out (len (seconds, rate));
    double phase = 0;
    for (size_t i = 0; i < out.size(); ++i)
    {
        const int k = (int) (i / note), j = (int) (i % note);
        const double hz = midiHz ((float) (rootMidi + steps[k % 4]));
        phase += hz / rate;
        out[i] = 0.5f * env (j, note, attack, release) * (float) blSaw (phase, hz, rate);
    }
    return out;
}

// sustained triad of sines, 0.5 s linear fade in and out, peak 0.5
inline std::vector<float> pad (int rootMidi, bool minor, float seconds, int rate)
{
    const float hz[3] = { midiHz ((float) rootMidi), midiHz ((float) rootMidi + (minor ? 3 : 4)), midiHz ((float) rootMidi + 7) };
    std::vector<float> out (len (seconds, rate));
    const int n = (int) out.size(), fade = len (0.5f, rate);
    for (int i = 0; i < n; ++i)
    {
        double s = 0;
        for (float h : hz) s += std::sin (2.0 * PI * h * (double) i / rate);
        out[i] = 0.5f / 3.f * env (i, n, fade, fade) * (float) s;
    }
    return out;
}

inline std::vector<float> whiteNoise (float seconds, int rate, uint32_t seed)
{
    std::vector<float> out (len (seconds, rate));
    Rng rng (seed);
    for (float& v : out) v = 0.5f * rng.uni();
    return out;
}

// a pitch folded into [lo, hi) by octaves
inline float fold (float hz, float lo, float hi)
{
    while (hz >= hi) hz *= 0.5f;
    while (hz < lo) hz *= 2.f;
    return hz;
}

// band-limited saw bass, 8 notes per 4 s built on the root and folded into 55 .. 110 Hz, each followed by a 20 ms gap, peak ~0.55
inline std::vector<float> bassLine (int rootMidi, float seconds, int rate)
{
    const int steps[8] = { 0, 0, 7, 5, 0, 10, 7, 3 };
    const int note = len (0.5f, rate), gap = len (0.02f, rate);
    std::vector<float> out (len (seconds, rate));
    double phase = 0;
    for (size_t i = 0; i < out.size(); ++i)
    {
        const int k = (int) (i / note), j = (int) (i % note);
        if (j >= note - gap) { out[i] = 0.f; phase = 0; continue; }
        const double hz = fold (midiHz ((float) (rootMidi + steps[k % 8])), 55.f, 110.f);
        phase += hz / rate;
        out[i] = 0.5f * (float) blSaw (phase, hz, rate);
    }
    return out;
}

// sine melody folded into 440 .. 880 Hz, 8th notes at 120 BPM, 10 ms fades, peak 0.5
inline std::vector<float> melody (int rootMidi, float seconds, int rate)
{
    const int steps[8] = { 0, 2, 4, 7, 9, 7, 4, 2 };
    const int note = len (0.25f, rate), fade = len (0.01f, rate);
    std::vector<float> out (len (seconds, rate));
    double phase = 0;
    for (size_t i = 0; i < out.size(); ++i)
    {
        const int k = (int) (i / note), j = (int) (i % note);
        phase += fold (midiHz ((float) (rootMidi + steps[k % 8])), 440.f, 880.f) / rate;
        out[i] = 0.5f * env (j, note, fade, fade) * (float) std::sin (2.0 * PI * (phase - std::floor (phase)));
    }
    return out;
}

// 4/4 drum loop built like tools/mkfixtures.py drums(): kick on beats 1 and 3 (120 ms sine, pitch 55 + 55 e^(-t / 25 ms)
// Hz, so it sits on 55 Hz and reads as keyed; amplitude e^(-t / 45 ms)), snare on 2 and 4 (150 ms first-difference noise,
// 40 ms decay), hats on every 8th unless `hats` is false (25 ms second-difference noise, 8 ms decay); scaled to peak 0.7
inline std::vector<float> drumLoop (float bpm, int bars, int rate, bool hats = true)
{
    const double beat = 60.0 / bpm * rate;
    std::vector<float> out (len ((float) (60.0 / bpm * 4 * bars), rate), 0.f);
    const int n = (int) out.size();
    Rng rng (9);
    for (int b = 0; b < 4 * bars; ++b)
    {
        const int at = (int) std::lround (b * beat);
        if (b % 2 == 0)
        {
            double phase = 0;
            for (int i = 0; i < len (0.12f, rate) && at + i < n; ++i)
            {
                const double t = (double) i / rate;
                phase += 2.0 * PI * (55.0 + 55.0 * std::exp (-t / 0.025)) / rate;
                out[at + i] += (float) (std::sin (phase) * std::exp (-t / 0.045));
            }
        }
        else
        {
            float prev = 0.f;
            for (int i = 0; i < len (0.15f, rate) && at + i < n; ++i)
            {
                const float w = rng.uni();
                out[at + i] += (w - prev) * 0.4f * (float) std::exp (-(double) i / rate / 0.04);
                prev = w;
            }
        }
    }
    for (int e = 0; hats && e < 8 * bars; ++e)
    {
        const int at = (int) std::lround (e * beat / 2);
        float p1 = 0.f, p2 = 0.f;
        for (int i = 0; i < len (0.025f, rate) && at + i < n; ++i)
        {
            const float w = rng.uni();
            out[at + i] += (w - 2 * p1 + p2) * 0.125f * (float) std::exp (-(double) i / rate / 0.008);
            p2 = p1;
            p1 = w;
        }
    }
    float peak = 0.f;
    for (float v : out) peak = std::fmax (peak, std::fabs (v));
    if (peak > 0.f)
        for (float& v : out) v *= 0.7f / peak;
    return out;
}
} // namespace sig
