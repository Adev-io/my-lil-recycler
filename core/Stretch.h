// Stretch.h: renders one stem to exactly the target bar length: region, pitch by resample, WSOLA / slice stretch, normalise. No Rack dependency.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include "Audio.h"
#include "Info.h"
#include "Picker.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <utility>
#include <vector>

namespace recycler { namespace stretch {

struct Stereo { std::vector<float> l, r; size_t frames() const { return l.size(); } };

namespace detail {
const double PI = 3.14159265358979323846;

// WSOLA synthesis hop (window = 2 hops) and search radius in seconds, and the coarse search grid in Hz. Tune on the rig.
const double HOP_S = 0.025, SEARCH_S = 0.010;
const int COARSE_HZ = 8000;

// NaN / inf -> 0, by bits so fast-math flags cannot optimise the test away
inline float clean (float x)
{
    uint32_t u;
    std::memcpy (&u, &x, 4);
    return (u >> 23 & 0xFF) == 0xFF ? 0.f : x;
}

// raised-cosine gain m samples from the silent end of a fade of length f: 0 at m = 0, rising to 1 at m = f
inline float fadeGain (size_t m, size_t f) { return m >= f ? 1.f : (float) (0.5 - 0.5 * std::cos (PI * (double) m / (double) f)); }

inline size_t roundSize (double v) { return v > 0.0 ? (size_t) std::llround (v) : 0; }
inline size_t hopFor (int sr) { return std::max<size_t> (1, roundSize (HOP_S * sr)); }

// 2^k, the picker's octave: tempo is only known up to an octave, so the effective file tempo is tempo * 2^k
inline double octave (int k) { return std::ldexp (1.0, std::max (-3, std::min (3, k))); }

// WSOLA core: nUnit output frames span x[0, S); nOut frames are synthesised (past nUnit the mapping runs on into x[S, size),
// the right-hand context, which the search and the last blocks read instead of zeros). Positions are block centres in x.
inline std::vector<float> wsola (const std::vector<float>& x, size_t S, size_t nUnit, size_t nOut, int sr,
                                 std::vector<size_t>* positionsOut, const std::vector<size_t>* guide)
{
    std::vector<float> y (nOut, 0.f);
    if (positionsOut) positionsOut->clear();
    if (nOut == 0 || nUnit == 0 || sr <= 0 || S == 0 || x.empty()) return y;
    const size_t H = hopFor (sr), W = 2 * H;
    const size_t D = roundSize (SEARCH_S * sr), q = (size_t) std::max (1, sr / COARSE_HZ);
    const size_t top = x.size();   // positions lie in [0, top]; reads outside x are zeros

    std::vector<float> w (W);   // periodic Hann: w[i] + w[i + H] = 1, so 50 % overlap-add needs no normalisation
    for (size_t i = 0; i < W; ++i) w[i] = (float) (0.5 - 0.5 * std::cos (2.0 * PI * (double) i / (double) W));

    std::vector<float> xp (top + 2 * H, 0.f);   // x[i] = xp[i + H]; a block centred at c <= top reads xp[c, c + W)
    std::copy (x.begin(), x.end(), xp.begin() + H);

    const auto score = [&] (size_t at, size_t from, size_t step) -> float
    {
        const float* a = &xp[at];            // candidate first half: x[at - H, at)
        const float* b = &xp[from + H];      // previous block's second half: x[from, from + H)
        float xy = 0.f, xx = 0.f;
        for (size_t j = 0; j < H; j += step) { xy += a[j] * b[j]; xx += a[j] * a[j]; }
        return xy / std::sqrt (xx + 1e-20f);
    };

    size_t prev = 0;
    for (size_t k = 0; k * H < nOut + H; ++k)
    {
        const size_t cs = k * H;   // synthesis centre
        const size_t nom = std::min (top, roundSize ((double) cs * (double) S / (double) nUnit));
        size_t c = nom;
        if (guide) c = k < guide->size() ? std::min ((*guide)[k], top) : nom;
        else if (k > 0)
        {
            const size_t hi = std::min (nom + D, top);
            const size_t lo = std::min (hi, std::max (nom > D ? nom - D : 0, prev));
            c = std::min (std::max (nom, lo), hi);
            float best = score (c, prev, 1);
            size_t coarse = lo;
            float coarseBest = -1e30f;
            for (size_t o = lo; o <= hi; o += q)
            {
                const float v = score (o, prev, q);
                if (v > coarseBest) { coarseBest = v; coarse = o; }
            }
            const size_t a = std::max (lo, coarse >= q ? coarse - q + 1 : 0), b = std::min (hi, coarse + q - 1);
            for (size_t o = a; o <= b; ++o)
            {
                const float v = score (o, prev, 1);
                if (v > best) { best = v; c = o; }
            }
        }
        if (positionsOut) positionsOut->push_back (c);
        prev = c;

        // overlap-add x[c - H, c + H) at output [cs - H, cs + H), clipped to [0, nOut)
        const size_t i0 = cs < H ? H - cs : 0, i1 = std::min (W, nOut + H - cs);
        const float* src = &xp[c];
        for (size_t i = i0; i < i1; ++i) y[cs + i - H] += w[i] * src[i];   // cs + i >= H from i0 on
    }
    return y;
}

// both channels on the left channel's positions, so the stereo image holds
inline Stereo wsolaStereo (const Stereo& x, size_t S, size_t nUnit, size_t nOut, int sr)
{
    Stereo y;
    std::vector<size_t> pos;
    y.l = wsola (x.l, S, nUnit, nOut, sr, &pos, nullptr);
    y.r = wsola (x.r, S, nUnit, nOut, sr, nullptr, &pos);
    return y;
}
} // namespace detail

// WSOLA to exactly n frames. window 50 ms, synthesis hop 25 ms, search ±10 ms (all from sr). positionsOut receives the chosen
// analysis positions (one per synthesis block); guide, when given, replaces the search with those positions (right channel follows left).
// A position is the analysis block's centre in x; block k's centre sits at k * hop in the output and nominally at k * hop / r in x.
// The search maximises sum(c * t) / sqrt(sum(c * c)) between the candidate's first half c and the previous block's second half t
// (what was written there), never moving before the previous position. Coarse pass on a COARSE_HZ grid, then full resolution
// around its winner, so the cost per block stays flat at any sample rate.
inline std::vector<float> wsola (const std::vector<float>& x, size_t n, int sr, std::vector<size_t>* positionsOut = nullptr,
                                 const std::vector<size_t>* guide = nullptr)
{
    return detail::wsola (x, x.size(), n, n, sr, positionsOut, guide);
}

inline Stereo wsolaStereo (const Stereo& x, size_t n, int sr) { return detail::wsolaStereo (x, x.frames(), n, n, sr); }

// Slice stretch. Slices start at each onset (and at 0); slice i plays at native speed from round(onset_i * r), r = n / frames.
// A slice that runs into the next one is cut there; one that ends before the next starts is followed by silence. Either way its
// last 5 ms get a raised-cosine fade-out, and the next slice a 0.5 ms fade-in; a slice that exactly meets its successor (as at
// r = 1) is left untouched. The first slice always fades in (it follows the previous loop's end).
// ponytail: silence, not tail stretch; upgrade = WSOLA the tail if gaps sound gappy.
inline Stereo slice (const Stereo& x, const std::vector<float>& onsetsSec, size_t n, int sr)
{
    Stereo y;
    y.l.assign (n, 0.f);
    y.r.assign (n, 0.f);
    const size_t F = std::min (x.l.size(), x.r.size());
    if (F == 0 || n == 0 || sr <= 0) return y;
    const double r = (double) n / (double) F;

    std::vector<size_t> s (1, 0);
    for (size_t i = 0; i < onsetsSec.size(); ++i)
    {
        const double f = std::floor ((double) onsetsSec[i] * sr + 0.5);
        if (f >= 0.0 && f < (double) F) s.push_back ((size_t) f);   // also drops NaN
    }
    std::sort (s.begin(), s.end());
    s.erase (std::unique (s.begin(), s.end()), s.end());

    const size_t fadeOut = std::max<size_t> (1, detail::roundSize (0.005 * sr)), fadeIn = std::max<size_t> (1, detail::roundSize (0.0005 * sr));
    bool contiguous = false;   // the previous slice ran exactly into this one
    for (size_t i = 0; i < s.size(); ++i)
    {
        const bool last = i + 1 == s.size();
        const size_t d = std::min (n, detail::roundSize ((double) s[i] * r));
        const size_t dn = last ? n : std::min (n, detail::roundSize ((double) s[i + 1] * r));
        if (dn <= d) { contiguous = false; continue; }
        const size_t L = (last ? F : s[i + 1]) - s[i], G = dn - d, len = std::min (L, G);
        const size_t fo = L == G ? 0 : std::min (fadeOut, len), fi = contiguous ? 0 : std::min (fadeIn, len);
        for (size_t j = 0; j < len; ++j)
        {
            float gain = j + fo >= len ? detail::fadeGain (len - 1 - j, fo) : 1.f;
            if (j < fi) gain *= detail::fadeGain (j, fi);
            y.l[d + j] = x.l[s[i] + j] * gain;
            y.r[d + j] = x.r[s[i] + j] * gain;
        }
        contiguous = L == G;
    }
    return y;
}

// N = bars * 4 beats * 60 / bpm seconds at outRate, rounded
inline size_t framesFor (float bpm, int bars, int outRate)
{
    if (! (bpm > 0.f) || bars <= 0 || outRate <= 0) return 0;
    return detail::roundSize ((double) bars * 4.0 * 60.0 / (double) bpm * (double) outRate);
}

struct Region { int64_t start = 0, frames = 0; };   // in file frames at fileRate

// What render needs decoded. Loops (info.bars > 0): the whole file, {0, info.frames} (INT64_MAX frames when info.frames is 0).
// Non-loop with a tempo: from bestOnset snapped back to the nearest onset at or before it (0 if none), B bars at the effective
// tempo info.tempo * 2^c.k (the tempo clamped to 30..400 BPM against a corrupt cache first): it depends on choice.k, which
// resolves the analysis's octave ambiguity against the target. Tempo 0: B bars of the target from bestOnset, at native speed.
// Both plus a 1 s margin (render's right-hand context). The region may run past the end of the file: the caller clamps it to
// what the file holds and render pads the rest with silence. role and c.s do not change it (the pitch shift keeps the length).
inline Region regionFor (const Info& info, int role, const picker::Choice& c, const picker::Target& t, int fileRate)
{
    (void) role;
    Region g;
    if (info.bars > 0) { g.frames = info.frames > 0 ? info.frames : INT64_MAX; return g; }
    if (fileRate <= 0 || t.bars <= 0) return g;
    double at = info.bestOnset >= 0.f ? std::min (info.bestOnset, 1e6f) : 0.0;   // NaN -> 0
    double sec = 0.0;
    if (info.tempo > 0.f)
    {
        double snap = 0.0;
        for (size_t i = 0; i < info.onsets.size(); ++i)
            if (info.onsets[i] <= at && info.onsets[i] > snap) snap = info.onsets[i];
        at = snap;
        sec = t.bars * 4.0 * 60.0 / (std::min (400.0, std::max (30.0, (double) info.tempo)) * detail::octave (c.k));
    }
    else if (t.bpm > 0.f) sec = t.bars * 4.0 * 60.0 / t.bpm;
    g.start = std::max<int64_t> (0, std::llround (at * fileRate));
    g.frames = std::llround (sec * fileRate) + fileRate;
    return g;
}

struct RenderIn
{
    const Stereo* audio = nullptr; int fileRate = 0; const Info* info = nullptr;
    int role = 0; picker::Choice choice; picker::Target target; int outRate = 48000;
    int64_t audioStart = 0;   // file frame at which audio begins; onsets and bestOnset stay file-relative
};

// exactly framesFor(target.bpm, target.bars, outRate) frames, normalised, faded
inline Stereo render (const RenderIn& in)
{
    const picker::Target& t = in.target;
    const int sr = in.outRate;
    const size_t N = framesFor (t.bpm, t.bars, sr);
    Stereo out;
    const size_t F = in.audio ? std::min (in.audio->l.size(), in.audio->r.size()) : 0;
    const auto silence = [&]() { out.l.assign (N, 0.f); out.r.assign (N, 0.f); return out; };
    if (N == 0 || F == 0 || ! in.info || in.fileRate <= 0) return silence();
    const Info& info = *in.info;
    const double fr = in.fileRate, p = std::pow (2.0, in.choice.s / 12.0);

    // 1. region in file frames (regionFor's), the right-hand context after it, and the output length it renders to before tiling.
    //    Non-loop: the 1 s margin is the context. Loops cut to B bars: the audio after the cut. Loops of B bars or fewer are
    //    circular: their context is their own head, added after the resample.
    const int64_t a0 = in.audioStart;
    const Region reg = regionFor (info, in.role, in.choice, t, in.fileRate);
    const int64_t start = reg.start;
    int64_t span = reg.frames - in.fileRate, right = in.fileRate;
    size_t unit = N;
    bool circular = false;
    if (info.bars > 0)
    {
        // the file in effective bars (at tempo * 2^k): B of them is the region; fewer tile, more are cut. Fractions are fine.
        const double bars = (double) info.bars * detail::octave (in.choice.k);
        const int64_t whole = info.frames > 0 ? info.frames : a0 + (int64_t) F;
        span = whole;
        right = 0;
        if (bars > t.bars)
        {
            span = std::llround ((double) whole * t.bars / bars);
            right = std::min<int64_t> (in.fileRate, whole - span);
        }
        else
        {
            circular = true;
            if (bars < t.bars) unit = detail::roundSize (bars * 4.0 * 60.0 / (double) t.bpm * (double) sr);
        }
    }
    if (span <= 0 || unit == 0) return silence();
    const int64_t total = span + right;

    Stereo x;   // sanitised; silence wherever audio does not cover the region
    x.l.assign ((size_t) total, 0.f);
    x.r.assign ((size_t) total, 0.f);
    const int64_t i0 = std::max<int64_t> (0, a0 - start), i1 = std::min<int64_t> (total, a0 + (int64_t) F - start);
    for (int64_t i = i0; i < i1; ++i)
    {
        const size_t j = (size_t) (start + i - a0);
        x.l[(size_t) i] = detail::clean (in.audio->l[j]);
        x.r[(size_t) i] = detail::clean (in.audio->r[j]);
    }

    // 2. pitch: resample by sr / fileRate / p; the region becomes S frames, the context follows it
    const double k = (double) sr / fr / p;
    const size_t S = std::max<size_t> (1, detail::roundSize ((double) span * k));
    const size_t m = std::max (S, detail::roundSize ((double) total * k));
    x.l = audio::resample (x.l, m);
    x.r = audio::resample (x.r, m);

    // 3. stretch S frames to unit frames
    std::vector<float> ons;
    if (in.role == DRUMS)
    {
        const double s0 = (double) start / fr, s1 = s0 + (double) span / fr, first = std::max (s0, (double) a0 / fr);
        for (size_t i = 0; i < info.onsets.size(); ++i)   // onsets before audioStart are dropped
            if (info.onsets[i] >= first && info.onsets[i] < s1) ons.push_back ((float) ((info.onsets[i] - s0) / p));
    }
    Stereo y;
    if (! ons.empty())
    {
        x.l.resize (S);
        x.r.resize (S);
        y = slice (x, ons, unit, sr);
    }
    else if (circular)
    {
        // Synthesise one window past the unit on the loop's own head, then crossfade that overhang into the unit's start:
        // the unit's end then runs straight into its start, so the tiles (and the player's loop) have no seam. Context alone
        // cannot do it: WSOLA's output is phase-continuous, so a unit that is not a whole number of periods would still jump.
        const size_t H = detail::hopFor (sr), X = std::min (2 * H, unit);
        const size_t C = detail::roundSize ((double) (X + 2 * H) * (double) S / (double) unit) + detail::roundSize (detail::SEARCH_S * sr) + 2 * H;
        x.l.resize (S + C);
        x.r.resize (S + C);
        for (size_t i = S; i < S + C; ++i) { x.l[i] = x.l[i % S]; x.r[i] = x.r[i % S]; }
        y = detail::wsolaStereo (x, S, unit, unit + X, sr);
        for (size_t i = 0; i < X; ++i)
        {
            const float a = detail::fadeGain (i, X);
            y.l[i] = y.l[i] * a + y.l[unit + i] * (1.f - a);
            y.r[i] = y.r[i] * a + y.r[unit + i] * (1.f - a);
        }
        y.l.resize (unit);
        y.r.resize (unit);
    }
    else y = detail::wsolaStereo (x, S, unit, unit, sr);
    std::vector<float>().swap (x.l);   // free before the output exists
    std::vector<float>().swap (x.r);

    // tile (bit-identical repeats); a unit of N frames becomes the output in place
    if (unit == N)
    {
        out = std::move (y);
        for (size_t i = 0; i < N; ++i) { out.l[i] = detail::clean (out.l[i]); out.r[i] = detail::clean (out.r[i]); }
    }
    else
    {
        out.l.resize (N);
        out.r.resize (N);
        for (size_t i = 0; i < N; ++i)
        {
            out.l[i] = detail::clean (y.l[i % unit]);
            out.r[i] = detail::clean (y.r[i % unit]);
        }
    }

    // 4. -18 dBFS RMS over both channels, peak at most 0.891, 5 ms raised-cosine fades
    double e = 0.0;
    float peak = 0.f;
    for (size_t i = 0; i < N; ++i)
    {
        e += (double) out.l[i] * out.l[i] + (double) out.r[i] * out.r[i];
        peak = std::max (peak, std::max (std::fabs (out.l[i]), std::fabs (out.r[i])));
    }
    const double rms = std::sqrt (e / (2.0 * (double) N));
    if (rms > 1e-9 && peak > 0.f)
    {
        float gain = (float) (0.12589254117941673 / rms);   // 10^(-18/20)
        if (peak * gain > 0.891f) gain = 0.891f / peak;
        for (size_t i = 0; i < N; ++i) { out.l[i] *= gain; out.r[i] *= gain; }
    }
    const size_t fade = std::min (N / 2, detail::roundSize (0.005 * sr));
    for (size_t i = 0; i < fade; ++i)
    {
        const float fg = detail::fadeGain (i, fade);
        out.l[i] *= fg; out.r[i] *= fg;
        out.l[N - 1 - i] *= fg; out.r[N - 1 - i] *= fg;
    }
    return out;
}

}} // namespace recycler::stretch
