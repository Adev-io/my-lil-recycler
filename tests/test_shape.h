// test_shape.h: the per-slot live shaping maths (Shape.h): read index (START, REV), state-variable filter, pan gains.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include "check.h"
#include "Shape.h"
#include <cmath>

namespace shapetest
{
// RMS in dB of the second half of a 1 s sine at hz through the filter at knob value f (sample rate sr)
inline double sineDb (float f, double hz, float sr = 48000.f)
{
    using namespace recycler::shape;
    const int n = (int) sr;
    Svf s;
    double in = 0.0, out = 0.0;
    for (int i = 0; i < n; ++i)
    {
        float l = (float) std::sin (2.0 * 3.14159265358979 * hz * i / sr), r = l;
        const float x = l;
        filter (s, f, sr, l, r);
        if (i >= n / 2) { in += (double) x * x; out += (double) l * l; }
    }
    return 10.0 * std::log10 (out / in);
}

// Largest |out - in| over the 64 samples after the knob leaves bypass (0) for f, on a full-scale 100 Hz sine
inline double reentryError (float f, float sr)
{
    using namespace recycler::shape;
    Svf s;
    double worst = 0.0;
    for (int i = 0; i < 1064; ++i)
    {
        float l = (float) std::sin (2.0 * 3.14159265358979 * 100.0 * i / sr), r = l;
        const float x = l;
        filter (s, i < 1000 ? 0.f : f, sr, l, r);
        const double e = std::fabs ((double) l - x);
        if (i >= 1000 && e > worst) worst = e;
    }
    return worst;
}
}

inline void testShape()
{
    using namespace recycler::shape;

    // read index: START 0 forward is the index itself; START 8 of 16 shifts by n/2; REV mirrors; always < n
    check (readIndex (5, 100, 0, false) == 5, "shape: start 0 forward keeps the index", (double) readIndex (5, 100, 0, false));
    check (readIndex (5, 100, 8, false) == 55, "shape: start 8 shifts by n/2", (double) readIndex (5, 100, 8, false));
    check (readIndex (60, 100, 8, false) == 10, "shape: start 8 wraps past the end", (double) readIndex (60, 100, 8, false));
    check (readIndex (0, 100, 0, true) == 99, "shape: rev maps 0 to n-1", (double) readIndex (0, 100, 0, true));
    check (readIndex (99, 100, 0, true) == 0, "shape: rev maps n-1 to 0", (double) readIndex (99, 100, 0, true));
    check (readIndex (5, 100, 8, true) == 44, "shape: start 8 + rev = n-1-(i+n/2)", (double) readIndex (5, 100, 8, true));
    check (readIndex (3, 0, 4, true) == 0, "shape: an empty buffer reads 0");
    bool inRange = true;
    for (size_t n = 1; n < 40; ++n)
        for (size_t i = 0; i < n; ++i)
            for (int st = 0; st < 16; ++st)
                if (readIndex (i, n, st, st & 1) >= n) inRange = false;
    check (inRange, "shape: readIndex is always < n");

    // stepIndex: the next frame a head reads, forward or in reverse, wrapping
    check (stepIndex (4, 10, false) == 5, "shape: step forward");
    check (stepIndex (9, 10, false) == 0, "shape: step forward wraps");
    check (stepIndex (4, 10, true) == 3, "shape: step in reverse");
    check (stepIndex (0, 10, true) == 9, "shape: step in reverse wraps");
    check (stepIndex (13, 10, false) == 4, "shape: step reduces an index past n first", (double) stepIndex (13, 10, false));
    check (stepIndex (5, 0, true) == 0, "shape: step on an empty buffer is 0");

    // filter: the dead zone passes the input bit-exact
    {
        Svf s;
        bool exact = true;
        for (int i = 0; i < 1000; ++i)
        {
            const float x = (float) std::sin (0.01 * i), y = (float) std::cos (0.02 * i);
            float l = x, r = y;
            filter (s, 0.04f, 48000.f, l, r);
            if (l != x || r != y) exact = false;
            l = x; r = y;
            filter (s, -0.04f, 48000.f, l, r);
            if (l != x || r != y) exact = false;
        }
        check (exact, "shape: |f| < 0.05 is a bit-exact bypass");
    }
    const double lpFull = shapetest::sineDb (-1.f, 10000.0), hpFull = shapetest::sineDb (1.f, 50.0);
    check (lpFull < -24.0, "shape: full low-pass cuts 10 kHz by more than 24 dB", lpFull);
    check (hpFull < -24.0, "shape: full high-pass cuts 50 Hz by more than 24 dB", hpFull);
    const double lpOpen = shapetest::sineDb (-0.051f, 1000.0), hpOpen = shapetest::sineDb (0.051f, 1000.0);
    check (std::fabs (lpOpen) < 0.5, "shape: low-pass just past the dead zone passes 1 kHz", lpOpen);
    check (std::fabs (hpOpen) < 0.5, "shape: high-pass just past the dead zone passes 1 kHz", hpOpen);
    const double lp441 = shapetest::sineDb (-0.051f, 1000.0, 44100.f);
    check (std::fabs (lp441) < 0.5, "shape: low-pass just past the dead zone passes 1 kHz at 44.1 kHz (clamped)", lp441);
    // knob values whose cutoff is exactly 1 kHz: Butterworth (Q 0.707) is -3.01 dB there
    const float lpAt1k = -(0.05f + 0.95f * (float) (std::log (20.0) / std::log (1000.0)));
    const float hpAt1k = 0.05f + 0.95f * (float) (std::log (50.0) / std::log (1000.0));
    const double lp3 = shapetest::sineDb (lpAt1k, 1000.0), hp3 = shapetest::sineDb (hpAt1k, 1000.0);
    check (std::fabs (lp3 + 3.01) < 0.1, "shape: low-pass is -3 dB at its 1 kHz cutoff", lp3);
    check (std::fabs (hp3 + 3.01) < 0.1, "shape: high-pass is -3 dB at its 1 kHz cutoff", hp3);
    // leaving the dead zone into low-pass must not tick: the state starts at the input's steady state
    const double click48 = shapetest::reentryError (-0.06f, 48000.f), click96 = shapetest::reentryError (-0.06f, 96000.f);
    check (click48 < 0.05, "shape: low-pass re-entry from bypass is click-free at 48 kHz (max |out - in|)", click48);
    check (click96 < 0.05, "shape: low-pass re-entry from bypass is click-free at 96 kHz (max |out - in|)", click96);
    {
        Svf s;
        bool finite = true, bounded = true;
        for (int i = 0; i < 96000; ++i)
        {
            float l = (float) std::sin (0.05 * i), r = -l;
            filter (s, -1.f + 2.f * (float) i / 96000.f, 48000.f, l, r);
            if (! std::isfinite (l) || ! std::isfinite (r)) finite = false;
            if (std::fabs (l) >= 4.f || std::fabs (r) >= 4.f) bounded = false;
        }
        check (finite, "shape: a full sweep stays finite");
        check (bounded, "shape: a full sweep stays below 4 in magnitude");
    }
    {
        Svf s;
        bool finite = true;
        for (int i = 0; i < 200; ++i)
        {
            float l = i == 99 ? std::nanf ("") : (float) std::sin (0.05 * i), r = (float) std::cos (0.05 * i);
            filter (s, -0.5f, 48000.f, l, r);
            if (i > 99 && (! std::isfinite (l) || ! std::isfinite (r))) finite = false;
        }
        check (finite, "shape: a NaN sample does not stick in the filter state");
    }
    {
        // quiet: a low-pass tail keeps ringing after its input stops; the slot only resets the filter once it has decayed
        Svf s;
        check (s.quiet(), "shape: a fresh filter is quiet");
        for (int i = 0; i < 4800; ++i)
        {
            float l = (float) std::sin (2.0 * 3.14159265358979 * 50.0 * i / 48000.0), r = -l;
            filter (s, -1.f, 48000.f, l, r);
        }
        check (! s.quiet(), "shape: a full low-pass after a burst is not quiet");
        for (int i = 0; i < 48000; ++i)
        {
            float l = 0.f, r = 0.f;
            filter (s, -1.f, 48000.f, l, r);
        }
        check (s.quiet(), "shape: a full low-pass tail is quiet after 1 s of zeros");
    }
    check (std::fabs (cutoffFor (-1.f) - 20.f) < 0.01f, "shape: full low-pass cutoff is 20 Hz", cutoffFor (-1.f));
    check (std::fabs (cutoffFor (1.f) - 20000.f) < 1.f, "shape: full high-pass cutoff is 20 kHz", cutoffFor (1.f));

    // pan: centre unity, hard sides mute the far side, never above 1
    float gl = 0.f, gr = 0.f;
    panGains (0.f, gl, gr);
    check (gl == 1.f && gr == 1.f, "shape: pan centre is (1, 1)");
    panGains (-1.f, gl, gr);
    check (gl == 1.f && gr < 1e-6f, "shape: pan hard left is (1, 0)", gr);
    panGains (1.f, gl, gr);
    check (gl < 1e-6f && gr == 1.f, "shape: pan hard right is (0, 1)", gl);
    bool capped = true;
    for (int i = -20; i <= 20; ++i)
    {
        panGains (i / 10.f, gl, gr);   // also out of range: clamped
        if (gl > 1.f || gr > 1.f || gl < 0.f || gr < 0.f) capped = false;
    }
    check (capped, "shape: pan gains stay in 0 .. 1");
}
