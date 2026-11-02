// test_shape.h: the per-slot live shaping maths (Shape.h): read index (START, REV), state-variable filter, pan gains.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include "check.h"
#include "Shape.h"
#include <cmath>
#include <vector>

namespace shapetest
{
// RMS in dB of the second half of a 1 s sine at hz through the filter at knob value f (48 kHz)
inline double sineDb (float f, double hz)
{
    using namespace recycler::shape;
    const float sr = 48000.f;
    Svf s;
    double in = 0.0, out = 0.0;
    for (int i = 0; i < 48000; ++i)
    {
        float l = (float) std::sin (2.0 * 3.14159265358979 * hz * i / sr), r = l;
        const float x = l;
        filter (s, f, sr, l, r);
        if (i >= 24000) { in += (double) x * x; out += (double) l * l; }
    }
    return 10.0 * std::log10 (out / in);
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
    check (stepIndex (4, false, 10) == 5, "shape: step forward");
    check (stepIndex (9, false, 10) == 0, "shape: step forward wraps");
    check (stepIndex (4, true, 10) == 3, "shape: step in reverse");
    check (stepIndex (0, true, 10) == 9, "shape: step in reverse wraps");

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
    {
        Svf s;
        bool finite = true;
        for (int i = 0; i < 96000; ++i)
        {
            float l = (float) std::sin (0.05 * i), r = -l;
            filter (s, -1.f + 2.f * (float) i / 96000.f, 48000.f, l, r);
            if (! std::isfinite (l) || ! std::isfinite (r)) finite = false;
        }
        check (finite, "shape: a full sweep stays finite");
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
