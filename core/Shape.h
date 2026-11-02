// Shape.h: per-slot live shaping for Recycler: read position (START, REV), a TPT state-variable filter (FILTER) and
// pan gains (PAN). No Rack dependency.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include <algorithm>
#include <cmath>
#include <cstddef>

namespace recycler
{
namespace shape
{
constexpr int START_STEPS = 16;   // START moves the loop start in 1/16 steps of the stem's buffer (= the loop)
constexpr float DEAD = 0.05f;     // FILTER: |f| below this is a bit-exact bypass
constexpr float PI_F = 3.14159265358979f;

// The frame to read: fwd is the forward index (frameAt), START shifts it by start/16 of n, REV mirrors it. 0 when n is 0.
inline size_t readIndex (size_t fwd, size_t n, int start, bool rev)
{
    if (n == 0) return 0;
    const size_t off = (size_t) (((start % START_STEPS) + START_STEPS) % START_STEPS) * n / START_STEPS;
    const size_t i = (fwd % n + off) % n;
    return rev ? n - 1 - i : i;
}

// The frame after i for a head playing forward or in reverse, wrapping. Needs n > 0.
inline size_t stepIndex (size_t i, bool rev, size_t n)
{
    if (! rev) return (i + 1) % n;
    return i == 0 ? n - 1 : i - 1;
}

// Cutoff in Hz for knob f outside the dead zone: left 20 kHz -> 20 Hz (low-pass), right 20 Hz -> 20 kHz (high-pass).
inline float cutoffFor (float f)
{
    const float a = std::min (1.f, std::max (0.f, (std::fabs (f) - DEAD) / (1.f - DEAD)));
    return f < 0.f ? 20000.f * std::pow (1e-3f, a) : 20.f * std::pow (1e3f, a);
}

// Stereo TPT state-variable filter state (Zavalishin), 12 dB/oct, Q 0.707.
struct Svf
{
    float ic1[2] = { 0.f, 0.f }, ic2[2] = { 0.f, 0.f };
    void reset() { ic1[0] = ic1[1] = ic2[0] = ic2[1] = 0.f; }
};

// One stereo sample at knob f (-1 .. 1). The dead zone passes l, r untouched and clears the state, so leaving it
// starts clean. Cutoff clamped to 0.45 * sr.
inline void filter (Svf& s, float f, float sr, float& l, float& r)
{
    if (std::fabs (f) < DEAD) { s.reset(); return; }
    const float fc = std::min (cutoffFor (f), 0.45f * sr);
    const float g = std::tan (PI_F * fc / sr), k = 1.41421356f;   // k = 1 / Q
    const float a1 = 1.f / (1.f + g * (g + k)), a2 = g * a1, a3 = g * a2;
    float* io[2] = { &l, &r };
    for (int c = 0; c < 2; ++c)
    {
        const float v0 = *io[c];
        const float v3 = v0 - s.ic2[c];
        const float v1 = a1 * s.ic1[c] + a2 * v3;
        const float v2 = s.ic2[c] + a2 * s.ic1[c] + a3 * v3;
        s.ic1[c] = 2.f * v1 - s.ic1[c];
        s.ic2[c] = 2.f * v2 - s.ic2[c];
        *io[c] = f < 0.f ? v2 : v0 - k * v1 - v2;   // low-pass : high-pass
    }
}

// Pan p (-1 left .. +1 right, clamped): centre unity, the far side falls on a cosine law, nothing above 1.
inline void panGains (float p, float& gl, float& gr)
{
    p = std::min (1.f, std::max (-1.f, p));
    gl = p <= 0.f ? 1.f : std::max (0.f, std::cos (p * 0.5f * PI_F));
    gr = p >= 0.f ? 1.f : std::max (0.f, std::cos (-p * 0.5f * PI_F));
}
} // namespace shape
} // namespace recycler
