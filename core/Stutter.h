// Stutter.h: STUT, the live slice repeat of one Recycler slot. While held, the slot repeats the slice that began on the
// last grid point at or before the press; the timeline keeps running, so a release lands where the song is. Works on the
// forward frame index (before START / REV). No Rack dependency; no allocation.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include <algorithm>
#include <cstddef>
#include <cstdint>

namespace recycler
{
namespace stut
{
constexpr int DIVS[4] = { 4, 8, 16, 32 };   // STUT LEN 0..3: slices per bar (1/4 .. 1/32 bar)

struct Stutter
{
    // One sample. fwd: the forward frame the timeline wants now; frames: the buffer length; slices: grid units in the
    // buffer (its bars x the division), the grid being j * frames / slices so an uneven buffer has no stray remainder;
    // fade: the seam fade in frames (clamped to a quarter slice; a slice under 4 frames is not faded). Returns the
    // forward frame to read and sets gain (0..1, moves at most 1/fade a sample, so it has no steps).
    size_t step (size_t fwd, size_t frames, size_t slices, bool held, size_t fade, float& gain)
    {
        jump = false;
        if (frames == 0) { on = fresh = false; gain = g = 1.f; return 0; }
        slices = std::min (std::max (slices, (size_t) 1), frames);
        fwd %= frames;
        if (! held)
        {
            jump = on && ! fresh;   // back to the timeline: the caller declicks the leap
            on = fresh = false;
            g = std::min (1.f, g + rate);
            gain = g;
            return fwd;
        }
        if (! on || fresh || frames != n) capture (fwd, frames, slices);
        else if (slices != grid) { capture (fwd, frames, slices); jump = true; }

        const size_t f = std::min (fade, len / 4);
        float env = 1.f;
        if (f > 0)
        {
            const size_t tail = len - 1 - k, head = first ? f : k;
            env = std::min (1.f, (float) std::min (head, tail) / (float) f);
            rate = 1.0001f / (float) f;
        }
        else rate = 1.f;
        g = std::min (g + rate, std::max (g - rate, env));
        gain = g;
        const size_t out = start + k;
        if (++k >= len) { k = 0; first = false; }
        return out;
    }

    void recapture() { fresh = true; }        // the slot's buffer changed: the next held sample takes the timeline again
    bool active() const { return on; }        // repeating a slice
    bool jumped() const { return jump; }      // the last step left the timeline's read (release, length change)
    float gain() const { return g; }          // the last gain (held while the slot has no buffer to step)

private:
    void capture (size_t fwd, size_t frames, size_t slices)
    {
        const uint64_t j = (uint64_t) fwd * slices / frames;
        start = (size_t) (j * frames / slices);
        len = (size_t) ((j + 1) * frames / slices) - start;
        k = fwd - start;
        n = frames;
        grid = slices;
        on = first = true;
        fresh = false;
    }

    size_t start = 0, len = 1, k = 0, n = 0, grid = 0;
    float g = 1.f, rate = 1.f;
    bool on = false, first = false, fresh = false, jump = false;
};
} // namespace stut
} // namespace recycler
