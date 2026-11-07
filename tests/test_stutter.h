// test_stutter.h: STUT, the live slice repeat (Stutter.h): grid capture, repeats, release, seam fades, length and buffer
// changes, tiny and uneven grids.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include "check.h"
#include "Stutter.h"
#include <cmath>

inline void testStutter()
{
    using recycler::stut::Stutter;
    float g = 0.f;

    // released: the timeline index passes straight through at unity
    {
        Stutter s;
        bool same = true;
        for (size_t f = 0; f < 300; ++f) { same = same && s.step (f, 1000, 10, false, 10, g) == f && g == 1.f; }
        check (same && ! s.active(), "stut: released passes fwd through at gain 1");
    }

    // press mid-slice (1000 frames, 10 slices of 100; press at 257): the first pass carries on from 257, then the slice
    // that began on the grid point before the press (200) repeats
    {
        Stutter s;
        const size_t first = s.step (257, 1000, 10, true, 10, g);
        check (first == 257 && s.active() && ! s.jumped(), "stut: the press continues from the timeline", (double) first);
        bool ok = true;
        for (size_t t = 1; t < 43; ++t) ok = ok && s.step (257 + t, 1000, 10, true, 10, g) == 257 + t;
        const size_t wrap = s.step (300, 1000, 10, true, 10, g);
        check (ok && wrap == 200, "stut: the first pass ends at the slice end, then the slice start (grid 200)", (double) wrap);
    }

    // repeats: three more slices read the same 100 frames, whatever the timeline does
    {
        Stutter s;
        for (size_t t = 0; t < 43; ++t) s.step (257 + t, 1000, 10, true, 10, g);
        bool ok = true;
        for (size_t t = 0; t < 300; ++t) ok = ok && s.step (300 + t, 1000, 10, true, 10, g) == 200 + t % 100;
        check (ok, "stut: three repeats read 200..299 each time");
    }

    // release: back exactly where the timeline is, flagged as a jump for the caller's declick
    {
        Stutter s;
        for (size_t t = 0; t < 400; ++t) s.step (257 + t, 1000, 10, true, 10, g);
        const size_t back = s.step (657, 1000, 10, false, 10, g);
        check (back == 657 && s.jumped() && ! s.active(), "stut: release returns to fwd and flags a jump", (double) back);
        s.step (658, 1000, 10, false, 10, g);
        check (! s.jumped(), "stut: the jump flag lasts one sample");
    }

    // seam gains (fade 10 frames): unity mid-slice, 0 on both sides of a seam, 1/fade steps; the first pass's start is not faded
    {
        Stutter s;
        s.step (200, 1000, 10, true, 10, g);
        check (g == 1.f, "stut: a press on the grid point starts at unity (no fade-in)", g);
        float at50 = 0.f, at99 = 1.f, at0 = 1.f, at5 = 0.f;
        float worst = 0.f, last = g;
        for (size_t t = 1; t < 300; ++t)
        {
            s.step (200 + t, 1000, 10, true, 10, g);
            worst = std::max (worst, std::fabs (g - last));
            last = g;
            if (t == 50) at50 = g;
            if (t == 99) at99 = g;
            if (t == 100) at0 = g;
            if (t == 105) at5 = g;
        }
        check (at50 == 1.f, "stut: mid-slice gain 1", at50);
        check (at99 == 0.f, "stut: last frame of a repeat at 0", at99);
        check (at0 == 0.f, "stut: first frame of the next repeat at 0", at0);
        check (near (at5, 0.5, 1e-5), "stut: fade-in 5 of 10 frames = 0.5", at5);
        check (worst <= 0.1f + 1e-5f, "stut: no gain step over 1/fade", worst);
    }

    // release in a seam dip: the gain climbs back at 1/fade a sample, no step to 1
    {
        Stutter s;
        for (size_t t = 0; t < 197; ++t) s.step (200 + t, 1000, 10, true, 10, g);   // last read 296: gain 0.3
        const float before = g;
        s.step (397, 1000, 10, false, 10, g);
        const float after = g;
        int n = 0;
        while (g < 1.f && n < 100) { s.step (398 + n, 1000, 10, false, 10, g); ++n; }
        check (near (before, 0.3, 1e-5) && near (after, 0.4, 1e-3),"stut: release mid-fade ramps up (0.3 -> 0.4)", after);
        check (n == 6, "stut: unity again within the fade", n);
    }

    // a length change while held: re-captured on the new grid at the timeline, flagged as a jump; no gap
    {
        Stutter s;
        for (size_t t = 0; t < 250; ++t) s.step (200 + t, 1000, 10, true, 10, g);
        const size_t r = s.step (730, 1000, 20, true, 10, g);   // 1/2 the length: slices of 50, 730 is in 700..749
        check (r == 730 && s.jumped() && s.active(), "stut: a length change reads on from the timeline", (double) r);
        bool ok = true;
        for (size_t t = 1; t < 20; ++t) ok = ok && s.step (730 + t, 1000, 20, true, 10, g) == 730 + t;
        const size_t w = s.step (750, 1000, 20, true, 10, g);
        check (ok && w == 700 && ! s.jumped(), "stut: then repeats the new slice (700)", (double) w);
    }

    // a buffer change while held: re-captured on the new buffer's grid at the timeline, no jump (the caller's swap
    // fade covers it); recapture() does the same for a new buffer of the same length
    {
        Stutter s;
        for (size_t t = 0; t < 150; ++t) s.step (200 + t, 1000, 10, true, 10, g);
        const size_t r = s.step (430, 800, 10, true, 10, g);   // 800 frames: slices of 80, 430 is in 400..479
        check (r == 430 && ! s.jumped(), "stut: a new buffer length re-captures without a jump", (double) r);
        for (size_t t = 1; t < 50; ++t) s.step (430 + t, 800, 10, true, 10, g);
        const size_t w = s.step (480, 800, 10, true, 10, g);
        check (w == 400, "stut: and repeats the new buffer's slice (400)", (double) w);
        s.recapture();
        const size_t c = s.step (611, 800, 10, true, 10, g);
        check (c == 611 && ! s.jumped(), "stut: recapture() takes the timeline again", (double) c);
        s.recapture();
        const size_t off = s.step (612, 800, 10, false, 10, g);
        check (off == 612 && ! s.jumped(), "stut: a release on a new buffer is no jump", (double) off);
    }

    // frames not a multiple of the grid: 1000 frames in 3 slices = 0, 333, 666 (the last one 334 long)
    {
        Stutter s;
        bool ok = true;
        for (size_t t = 0; t < 300; ++t) ok = ok && s.step (700 + t, 1000, 3, true, 10, g) == 700 + t;
        const size_t w = s.step (0, 1000, 3, true, 10, g);
        size_t last = w;
        for (size_t t = 1; t < 334; ++t) last = s.step (t, 1000, 3, true, 10, g);
        const size_t w2 = s.step (334, 1000, 3, true, 10, g);
        check (ok && w == 666 && last == 999 && w2 == 666, "stut: uneven grid repeats 666..999", (double) w);
    }

    // tiny: more slices than frames, an empty buffer, a slice too short to fade
    {
        Stutter s;
        bool inRange = true, finite = true;
        for (size_t t = 0; t < 50; ++t)
        {
            inRange = inRange && s.step (t % 5, 5, 32, true, 10, g) < 5;
            finite = finite && std::isfinite (g) && g >= 0.f && g <= 1.f;
        }
        check (inRange && finite, "stut: 5 frames in 32 slices stays in range");
        check (s.step (3, 0, 8, true, 10, g) == 0 && g == 1.f, "stut: an empty buffer reads 0 at unity");
        Stutter t;
        float lo = 1.f;
        for (size_t k = 0; k < 30; ++k) { t.step (k, 30, 10, true, 10, g); lo = std::min (lo, g); }
        check (lo == 1.f, "stut: a 3-frame slice is not faded (would be silence)", lo);
        Stutter z;
        z.step (5, 100, 0, true, 0, g);
        check (std::isfinite (g), "stut: 0 slices / 0 fade do not divide by zero", g);
    }
}
