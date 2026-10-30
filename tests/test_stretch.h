// test_stretch.h: WSOLA, slice stretch and the full render (region, pitch, stretch, tile, normalise, fades).
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include "check.h"
#include "signals.h"
#include "Audio.h"
#include "Stretch.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <limits>
#include <vector>

namespace stretchtest
{
using recycler::stretch::Stereo;

inline Stereo stereo (const std::vector<float>& m) { Stereo s; s.l = m; s.r = m; return s; }

// sign changes per second over [a, b)
inline double zcr (const std::vector<float>& y, size_t a, size_t b, int sr)
{
    size_t c = 0;
    for (size_t i = a + 1; i < b; ++i) c += (y[i - 1] >= 0.f) != (y[i] >= 0.f);
    return (double) c / ((double) (b - a) / sr);
}
inline double zcr (const std::vector<float>& y, int sr) { return zcr (y, 0, y.size(), sr); }

inline double maxJump (const std::vector<float>& y, size_t a, size_t b)
{
    double m = 0;
    for (size_t i = a + 1; i < b && i < y.size(); ++i) m = std::max (m, (double) std::fabs (y[i] - y[i - 1]));
    return m;
}
inline double maxAbs (const std::vector<float>& y, size_t a = 0, size_t b = (size_t) -1)
{
    double m = 0;
    for (size_t i = a; i < b && i < y.size(); ++i) m = std::max (m, (double) std::fabs (y[i]));
    return m;
}
inline bool allFinite (const std::vector<float>& y)
{
    for (size_t i = 0; i < y.size(); ++i) if (! (std::fabs (y[i]) <= 1e30f)) return false;
    return true;
}
inline double rmsDb (const Stereo& s)
{
    double e = 0;
    for (size_t i = 0; i < s.frames(); ++i) e += (double) s.l[i] * s.l[i] + (double) s.r[i] * s.r[i];
    return 20.0 * std::log10 (std::sqrt (e / (2.0 * (double) s.frames())) + 1e-30);
}

// local max of |y| above 0.25, then nothing for 50 ms (0.25, not 0.5: each slice's 0.5 ms fade-in trims the 0.8-peak, 1 ms-decay
// noise click to just under 0.5)
inline std::vector<size_t> clicks (const std::vector<float>& y, int sr)
{
    std::vector<size_t> out;
    const size_t gap = (size_t) (0.05 * sr);
    for (size_t i = 0; i < y.size();)
    {
        if (std::fabs (y[i]) <= 0.25f) { ++i; continue; }
        size_t best = i;
        for (size_t j = i; j < std::min (y.size(), i + gap); ++j) if (std::fabs (y[j]) > std::fabs (y[best])) best = j;
        out.push_back (best);
        i = best + gap;
    }
    return out;
}

inline void wsolaCase (double ratio)
{
    const int sr = 48000;
    const std::vector<float> x = sig::sine (100.f, 2.f, sr);
    const size_t n = (size_t) std::lround (x.size() * ratio);
    std::vector<size_t> pos;
    const std::vector<float> y = recycler::stretch::wsola (x, n, sr, &pos);
    char what[128];
    std::snprintf (what, sizeof what, "wsola x%.1f: exactly n frames", ratio);
    check (y.size() == n, what, (double) y.size());
    const double z = zcr (y, sr);
    std::snprintf (what, sizeof what, "wsola x%.1f: zero-crossing rate within 1%% of 200/s", ratio);
    check (std::fabs (z - 200.0) <= 2.0, what, z);
    std::snprintf (what, sizeof what, "wsola x%.1f: max |y| <= 1", ratio);
    check (maxAbs (y) <= 1.0, what, maxAbs (y));
    std::snprintf (what, sizeof what, "wsola x%.1f: no NaN / inf", ratio);
    check (allFinite (y), what);
    const double j = maxJump (y, n / 2 - sr / 2, n / 2 + sr / 2);
    std::snprintf (what, sizeof what, "wsola x%.1f: middle 1 s has no jump > 0.2", ratio);
    check (j <= 0.2, what, j);
    const size_t H = sr / 40;
    std::snprintf (what, sizeof what, "wsola x%.1f: one position per 25 ms block", ratio);
    check (pos.size() >= n / H && pos.size() <= n / H + 2, what, (double) pos.size());
    bool mono = true;
    for (size_t i = 1; i < pos.size(); ++i) mono = mono && pos[i] >= pos[i - 1];
    std::snprintf (what, sizeof what, "wsola x%.1f: positions monotone non-decreasing", ratio);
    check (mono, what);
    const std::vector<float> g = recycler::stretch::wsola (x, n, sr, nullptr, &pos);
    std::snprintf (what, sizeof what, "wsola x%.1f: guided by its own positions = identical output", ratio);
    check (g == y, what);

    // unsearched nominal positions: phases do not line up, only the Hann crossfades keep it smooth (a hard cut jumps 0.23..0.51)
    std::vector<size_t> nominal;
    for (size_t k = 0; k * H < n + H; ++k) nominal.push_back ((size_t) std::llround ((double) (k * H) * x.size() / n));
    const std::vector<float> u = recycler::stretch::wsola (x, n, sr, nullptr, &nominal);
    const double ju = maxJump (u, 0, u.size());
    std::snprintf (what, sizeof what, "wsola x%.1f: nominal positions, crossfades keep every jump <= 0.05", ratio);
    check (u.size() == n && ju <= 0.05, what, ju);
}

inline recycler::picker::Target target (float bpm, int bars)
{
    recycler::picker::Target t;
    t.bpm = bpm; t.root = 0; t.minor = true; t.bars = bars;
    return t;
}

// 8 s 110 Hz saw (4 bars at 120), Info bars 0 / tempo 120 / onsets {0}, role BASS, target 132 / 4 bars
inline Stereo renderSaw (int s, int fileRate, float nanAt = -1.f)
{
    std::vector<float> m = sig::saw (110.f, 8.f, 48000);
    if (fileRate != 48000) m = recycler::audio::resample (m, 48000, fileRate);
    if (nanAt >= 0.f) m[(size_t) (nanAt * fileRate)] = std::numeric_limits<float>::quiet_NaN();
    const Stereo a = stereo (m);
    recycler::Info info;
    info.bars = 0; info.tempo = 120.f; info.bestOnset = 0.f; info.onsets.push_back (0.f);
    recycler::stretch::RenderIn in;
    in.audio = &a; in.fileRate = fileRate; in.info = &info; in.role = recycler::BASS;
    in.choice.s = s; in.target = target (132.f, 4); in.outRate = 48000;
    return recycler::stretch::render (in);
}

inline Stereo renderTexture (int s)
{
    const Stereo a = stereo (sig::sine (440.f, 1.5f, 48000));
    recycler::Info info;   // bars 0, tempo 0, bestOnset 0
    recycler::stretch::RenderIn in;
    in.audio = &a; in.fileRate = 48000; in.info = &info; in.role = recycler::TEXTURE;
    in.choice.s = s; in.target = target (120.f, 4); in.outRate = 48000;
    return recycler::stretch::render (in);
}
} // namespace stretchtest

inline void testStretch()
{
    using namespace stretchtest;
    namespace st = recycler::stretch;
    const int sr = 48000;
    const double fadeLen = 0.005 * sr;

    // framesFor
    check (st::framesFor (120.f, 4, sr) == 384000, "framesFor(120, 4, 48000) == 384 000", (double) st::framesFor (120.f, 4, sr));
    check (st::framesFor (132.f, 4, sr) == (size_t) std::lround (4.0 * 4 * 60 / 132 * sr), "framesFor(132, 4, 48000) rounded",
           (double) st::framesFor (132.f, 4, sr));

    // WSOLA on a sine, longer and shorter
    wsolaCase (1.5);
    wsolaCase (0.7);

    // stereo image follows the left channel's positions
    {
        const std::vector<float> m = sig::saw (110.f, 1.f, sr);
        Stereo a = stereo (m);
        const Stereo y = st::wsolaStereo (a, 60000, sr);
        check (y.frames() == 60000 && y.r.size() == 60000, "wsolaStereo: exactly n frames", (double) y.frames());
        check (y.l == y.r, "wsolaStereo: r = l stays identical");
        for (size_t i = 0; i < a.r.size(); ++i) a.r[i] = -a.l[i];
        const Stereo z = st::wsolaStereo (a, 60000, sr);
        bool neg = z.l.size() == z.r.size();
        for (size_t i = 0; neg && i < z.l.size(); ++i) neg = z.r[i] == -z.l[i];
        check (neg, "wsolaStereo: r = -l stays r == -l (image preserved)");
    }

    // slice stretch: 8 clicks 0.25 s apart, to 1.25x
    {
        const Stereo a = stereo (sig::clickTrack (240.f, 2, sr));
        std::vector<float> on;
        for (int i = 0; i < 8; ++i) on.push_back (0.25f * i);
        const size_t n = (size_t) std::lround (a.frames() * 1.25);
        const Stereo y = st::slice (a, on, n, sr);
        check (y.frames() == n && y.r.size() == n, "slice x1.25: exactly n frames", (double) y.frames());
        const std::vector<size_t> c = clicks (y.l, sr);
        check (c.size() == 8, "slice x1.25: exactly 8 clicks", (double) c.size());
        double err = c.size() == 8 ? 0.0 : 1.0;
        for (size_t i = 0; i < c.size() && i < 8; ++i) err = std::max (err, std::fabs ((double) c[i] / sr - 0.3125 * i));
        check (err <= 0.001, "slice x1.25: clicks at 0.3125 i s +- 1 ms (worst error, s)", err);
        // a sustained tone: each 0.25 s slice ends 62.5 ms before the next starts
        const Stereo sus = st::slice (stereo (sig::sine (100.f, 2.f, sr)), on, n, sr);
        const double mid = maxAbs (sus.l, (size_t) (0.28 * sr), (size_t) (0.29 * sr));
        check (maxAbs (sus.l, (size_t) (0.2 * sr), (size_t) (0.24 * sr)) > 0.4 && mid < 1e-4,
               "slice x1.25 on a tone: silence after a slice shorter than its new gap", mid);

        // unsorted, duplicated onsets give the same result
        std::vector<float> messy (on.rbegin(), on.rend());
        messy.push_back (0.5f); messy.push_back (0.f);
        const Stereo m = st::slice (a, messy, n, sr);
        check (m.l == y.l && m.r == y.r, "slice: unsorted / duplicate onsets = sorted result");

        // overlapping tails at 0.5x, on a tone peaking at the cut points: cut with a fade, no jump
        std::vector<float> tone = sig::sine (98.f, 2.f, sr);
        for (size_t i = 0; i < tone.size(); ++i) tone[i] *= 1.8f;
        const Stereo h = st::slice (stereo (tone), on, tone.size() / 2, sr);
        check (h.frames() == tone.size() / 2, "slice x0.5: exactly n frames", (double) h.frames());
        const double j = maxJump (h.l, 0, h.frames());
        check (j <= 0.5, "slice x0.5: overlapping tails cut with a fade (no jump > 0.5)", j);

        // onsets on the tone's peaks (100 Hz x 1.8, 0.2525 s = 25.25 cycles): each slice starts at 0.9 after a cut to 0
        std::vector<float> peaks;
        for (int i = 1; i < 8; ++i) peaks.push_back (0.2525f * i);
        std::vector<float> sus100 = sig::sine (100.f, 2.f, sr);
        for (size_t i = 0; i < sus100.size(); ++i) sus100[i] *= 1.8f;
        const Stereo pk = st::slice (stereo (sus100), peaks, sus100.size() / 2, sr);
        const double jp = maxJump (pk.l, 0, pk.frames());
        check (jp <= 0.1, "slice x0.5: a slice starting mid-tone fades in over 0.5 ms (no step from 0)", jp);
    }

    // render: 2-bar 120 BPM click loop into 4 bars, DRUMS
    {
        const Stereo a = stereo (sig::clickTrack (120.f, 2, sr));
        recycler::Info info;
        info.bars = 2; info.tempo = 120.f; info.bestOnset = 0.f;
        for (int i = 0; i < 8; ++i) info.onsets.push_back (0.5f * i);
        st::RenderIn in;
        in.audio = &a; in.fileRate = sr; in.info = &info; in.role = recycler::DRUMS;
        in.target = target (120.f, 4); in.outRate = sr;
        const Stereo y = st::render (in);
        check (y.frames() == 384000 && y.r.size() == 384000, "render drums: N == 384 000", (double) y.frames());
        const size_t half = y.frames() / 2, f = (size_t) fadeLen;
        double d = 0;
        for (size_t i = f; i < half - f && half * 2 == y.frames(); ++i)
            d = std::max (d, (double) std::max (std::fabs (y.l[i] - y.l[i + half]), std::fabs (y.r[i] - y.r[i + half])));
        check (half * 2 == y.frames() && d <= 1e-6, "render drums: second half tiles the first (outside the fades)", d);
        const double pk = std::max (maxAbs (y.l), maxAbs (y.r));
        check (pk <= 0.891 + 1e-6, "render drums: peak <= 0.891", pk);
        // fade-in gain = y / the same loop phase in the unfaded second half; must rise
        bool mono = y.frames() == 384000 && y.l[0] == 0.f;
        double last = 0; int pts = 0;
        for (size_t i = 0; mono && i < f; ++i)
        {
            const float ref = y.l[i + half];
            if (std::fabs (ref) < 1e-3f) continue;
            const double g = y.l[i] / ref;
            mono = g >= last - 1e-6 && g <= 1.0 + 1e-6;
            last = g; ++pts;
        }
        check (mono && pts > 20, "render drums: first 5 ms is a monotone fade in from 0", (double) pts);
    }

    // render: saw, BASS, 120 -> 132 BPM
    const size_t N132 = st::framesFor (132.f, 4, sr);
    {
        const Stereo y = renderSaw (0, sr);
        check (y.frames() == N132 && y.r.size() == N132, "render bass: N == framesFor(132, 4)", (double) y.frames());
        const double db = rmsDb (y);
        check (std::fabs (db + 18.0) <= 1.0, "render bass: RMS -18 dBFS +- 1 dB", db);
        const double z = zcr (y.l, sr);
        check (std::fabs (z / 220.0 - 1.0) <= 0.02, "render bass: zero-crossing rate 220/s +- 2%", z);
    }
    {
        // fade-out: a 1 kHz tone (one period per 1 ms window), the 1 ms RMS windows over the last 5 ms must fall
        const Stereo a = stereo (sig::sine (1000.f, 8.f, sr));
        recycler::Info info;
        info.tempo = 120.f; info.onsets.push_back (0.f);
        st::RenderIn in;
        in.audio = &a; in.fileRate = sr; in.info = &info; in.role = recycler::MELODY;
        in.target = target (120.f, 4); in.outRate = sr;
        const Stereo y = st::render (in);
        const size_t N = y.frames(), w = (size_t) (0.001 * sr);
        bool fade = N == 384000 && y.l[N - 1] == 0.f && y.r[N - 1] == 0.f;
        double prevRms = 1e9, firstRms = 0, lastRms = 0;
        for (size_t b = N - 5 * w; fade && b < N; b += w)
        {
            double e = 0;
            for (size_t i = b; i < b + w; ++i) e += (double) y.l[i] * y.l[i];
            const double r = std::sqrt (e / w);
            fade = r < prevRms;
            if (b == N - 5 * w) firstRms = r;
            prevRms = lastRms = r;
        }
        check (fade && lastRms < 0.2 * firstRms, "render: last 5 ms is a monotone fade out to 0 (1 ms RMS windows)", lastRms / firstRms);
    }
    {
        const Stereo up = renderSaw (12, sr), down = renderSaw (-12, sr);
        check (up.frames() == N132, "render bass s=+12: N unchanged", (double) up.frames());
        const double zu = zcr (up.l, sr);
        check (std::fabs (zu / 440.0 - 1.0) <= 0.02, "render bass s=+12: zero-crossing rate doubles (440/s +- 2%)", zu);
        check (down.frames() == N132, "render bass s=-12: N unchanged", (double) down.frames());
        const double zd = zcr (down.l, sr);
        check (std::fabs (zd / 110.0 - 1.0) <= 0.02, "render bass s=-12: zero-crossing rate halves (110/s +- 2%)", zd);
    }
    {
        const Stereo y = renderSaw (0, 44100);
        check (y.frames() == N132, "render bass from 44.1 kHz: same N", (double) y.frames());
        const double z = zcr (y.l, sr);
        check (std::fabs (z / 220.0 - 1.0) <= 0.02, "render bass from 44.1 kHz: zero-crossing rate 220/s +- 2%", z);
    }

    // render: 1.5 s one-shot TEXTURE, tempo 0: native speed, silence after
    {
        const Stereo y = renderTexture (0);
        check (y.frames() == 384000, "render texture: N frames", (double) y.frames());
        const double tail = std::max (maxAbs (y.l, (size_t) (1.6 * sr)), maxAbs (y.r, (size_t) (1.6 * sr)));
        check (tail < 1e-5, "render texture: silent after 1.6 s", tail);
        check (maxAbs (y.l, 0, (size_t) (1.4 * sr)) > 0.1, "render texture: sound before 1.4 s", maxAbs (y.l, 0, (size_t) (1.4 * sr)));
        const Stereo u = renderTexture (12);
        const double tu = std::max (maxAbs (u.l, (size_t) (1.6 * sr)), maxAbs (u.r, (size_t) (1.6 * sr)));
        check (u.frames() == 384000 && tu < 1e-5, "render texture s=+12: still native length (silent after 1.6 s)", tu);
        const double zu = zcr (u.l, (size_t) (0.1 * sr), (size_t) (1.4 * sr), sr);
        check (std::fabs (zu / 1760.0 - 1.0) <= 0.02, "render texture s=+12: one octave up (1760 crossings/s)", zu);
    }

    // sanitising and empty input
    {
        const Stereo y = renderSaw (0, sr, 1.f);
        check (y.frames() == N132, "render with a NaN input: N frames", (double) y.frames());
        check (allFinite (y.l) && allFinite (y.r), "render with a NaN input: no NaN out");
        const Stereo a;
        recycler::Info info;
        st::RenderIn in;
        in.audio = &a; in.fileRate = sr; in.info = &info; in.role = recycler::MELODY;
        in.target = target (120.f, 4); in.outRate = sr;
        const Stereo e = st::render (in);
        check (e.frames() == 384000 && e.r.size() == 384000, "render of empty audio: N frames", (double) e.frames());
        check (maxAbs (e.l) == 0.0 && maxAbs (e.r) == 0.0, "render of empty audio: silence");
    }

    // regionFor + audioStart: rendering from only the decoded region equals rendering from the whole file
    {
        const Stereo whole = stereo (sig::saw (110.f, 10.f, sr));
        recycler::Info info;
        info.bars = 0; info.tempo = 120.f; info.bestOnset = 4.f; info.onsets.push_back (1.f); info.onsets.push_back (4.f);
        const recycler::picker::Target t2 = target (120.f, 2);
        const st::Region g = st::regionFor (info, recycler::BASS, recycler::picker::Choice(), t2, sr);
        check (g.start == 4 * sr && g.frames == 5 * sr, "regionFor non-loop: snapped onset, 2 bars at 120 + 1 s", (double) g.frames);

        // the caller's job: decode [start, start + frames) clamped to the file
        const auto cut = [&] (const st::Region& r) -> Stereo
        {
            Stereo s;
            const size_t a = std::min (whole.frames(), (size_t) r.start), b = std::min (whole.frames(), (size_t) (r.start + r.frames));
            s.l.assign (whole.l.begin() + a, whole.l.begin() + b);
            s.r.assign (whole.r.begin() + a, whole.r.begin() + b);
            return s;
        };
        const auto diff = [] (const Stereo& a, const Stereo& b) -> double
        {
            if (a.frames() != b.frames() || a.frames() == 0) return 1.0;
            double d = 0;
            for (size_t i = 0; i < a.frames(); ++i)
                d = std::max (d, (double) std::max (std::fabs (a.l[i] - b.l[i]), std::fabs (a.r[i] - b.r[i])));
            return d;
        };
        st::RenderIn in;
        in.fileRate = sr; in.info = &info; in.target = t2; in.outRate = sr;
        for (int role = 0; role < 2; ++role)
        {
            in.role = role ? recycler::DRUMS : recycler::BASS;
            in.audio = &whole; in.audioStart = 0;
            const Stereo full = st::render (in);
            const Stereo part = cut (g);
            in.audio = &part; in.audioStart = g.start;
            const double d = diff (full, st::render (in));
            check (d <= 1e-6, role ? "render drums from the decoded region == from the whole file"
                                   : "render bass from the decoded region == from the whole file", d);
        }

        // region past the end of the file: clamped by the caller, render pads with silence
        info.bestOnset = 8.f; info.onsets.push_back (8.f);
        const st::Region late = st::regionFor (info, recycler::BASS, recycler::picker::Choice(), t2, sr);
        const Stereo tail = cut (late);
        check (late.start == 8 * sr && tail.frames() == (size_t) (2 * sr), "regionFor past the end: caller clamps to 2 s", (double) tail.frames());
        in.role = recycler::BASS; in.audio = &tail; in.audioStart = late.start;
        const Stereo y = st::render (in);
        check (y.frames() == st::framesFor (120.f, 2, sr), "render from a short region: N frames", (double) y.frames());
        check (maxAbs (y.l, 0, (size_t) (1.9 * sr)) > 0.1, "render from a short region: sound in the covered 2 s", maxAbs (y.l, 0, (size_t) (1.9 * sr)));
        const double pad = std::max (maxAbs (y.l, (size_t) (2.1 * sr)), maxAbs (y.r, (size_t) (2.1 * sr)));
        check (pad < 1e-5, "render from a short region: silence padded after it", pad);
        in.audio = &whole; in.audioStart = 0;
        const double dw = diff (y, st::render (in));
        check (dw <= 1e-6, "render from a short region == from the whole file", dw);

        // loops: the whole file
        recycler::Info loop;
        loop.bars = 2; loop.tempo = 120.f; loop.frames = 96000;
        const st::Region lg = st::regionFor (loop, recycler::DRUMS, recycler::picker::Choice(), t2, sr);
        check (lg.start == 0 && lg.frames == 96000, "regionFor loop: whole file", (double) lg.frames);
        loop.frames = 0;
        const st::Region lu = st::regionFor (loop, recycler::DRUMS, recycler::picker::Choice(), t2, sr);
        check (lu.start == 0 && lu.frames == INT64_MAX, "regionFor loop, frames unknown: INT64_MAX");

        // tempo 0: the native excerpt (4 bars at 120 = 8 s) from bestOnset, plus 1 s, independent of the shift
        recycler::Info tex;
        tex.bestOnset = 0.5f;
        recycler::picker::Choice up;
        up.s = 7;
        const st::Region tg = st::regionFor (tex, recycler::TEXTURE, up, target (120.f, 4), 44100);
        check (tg.start == 22050 && tg.frames == 9 * 44100, "regionFor tempo 0: native 8 s + 1 s from bestOnset", (double) tg.frames);
    }

    // tonal loops: a seamless 3-bar 100 Hz sine loop (6 s at 120 = 600 periods) tiled into 4 bars has no click at the seam
    {
        const Stereo a = stereo (sig::sine (100.f, 6.f, sr));
        recycler::Info info;
        info.bars = 3; info.tempo = 120.f; info.frames = (int64_t) a.frames();
        const float bpms[3] = { 126.f, 120.f, 120.f };
        const int shifts[3] = { 0, 5, -6 };
        for (int c = 0; c < 3; ++c)
        {
            st::RenderIn in;
            in.audio = &a; in.fileRate = sr; in.info = &info; in.role = recycler::MELODY;
            in.choice.s = shifts[c]; in.target = target (bpms[c], 4); in.outRate = sr;
            const Stereo y = st::render (in);
            const size_t N = st::framesFor (bpms[c], 4, sr), unit = st::framesFor (bpms[c], 3, sr);
            char what[128];
            std::snprintf (what, sizeof what, "loop 3 -> 4 bars at %g, s=%+d: exactly N frames", bpms[c], shifts[c]);
            check (y.frames() == N && y.r.size() == N, what, (double) y.frames());
            const double seam = y.frames() == N ? std::fabs (y.l[unit] - y.l[unit - 1]) : 1.0;
            std::snprintf (what, sizeof what, "loop 3 -> 4 bars at %g, s=%+d: seam jump <= 0.02", bpms[c], shifts[c]);
            check (seam <= 0.02, what, seam);
            const double all = maxJump (y.l, 0, y.frames());
            std::snprintf (what, sizeof what, "loop 3 -> 4 bars at %g, s=%+d: no jump > 0.02 anywhere", bpms[c], shifts[c]);
            check (all <= 0.02, what, all);
        }
    }

    // loops longer than B take the first B bars: 4 bars of 100 Hz then 4 bars of 300 Hz, 8 -> 4 at 120
    {
        std::vector<float> m = sig::sine (100.f, 8.f, sr);
        const std::vector<float> hi = sig::sine (300.f, 8.f, sr);
        m.insert (m.end(), hi.begin(), hi.end());
        const Stereo a = stereo (m);
        recycler::Info info;
        info.bars = 8; info.tempo = 120.f; info.frames = (int64_t) a.frames();
        st::RenderIn in;
        in.audio = &a; in.fileRate = sr; in.info = &info; in.role = recycler::BASS;
        in.target = target (120.f, 4); in.outRate = sr;
        const Stereo y = st::render (in);
        check (y.frames() == 384000, "loop 8 -> 4 bars: exactly N frames", (double) y.frames());
        const double z = zcr (y.l, sr);
        check (std::fabs (z / 200.0 - 1.0) <= 0.02, "loop 8 -> 4 bars: the first 4 bars (100 Hz, 200 crossings/s)", z);
        check (maxJump (y.l, 0, y.frames()) <= 0.02, "loop 8 -> 4 bars: no jump > 0.02", maxJump (y.l, 0, y.frames()));
    }

    // the 1 s margin is right-hand context: a 60 Hz tone stretched 2.5x (1 bar at 120 = 2 s -> 1 bar at 48 = 5 s) keeps its level
    // to the end. 25 ms = 3 half-periods of 60 Hz, so window RMS does not depend on phase; the window ends before the 5 ms fade.
    {
        const Stereo a = stereo (sig::sine (60.f, 10.f, sr));
        recycler::Info info;
        info.tempo = 120.f; info.onsets.push_back (0.f);
        st::RenderIn in;
        in.audio = &a; in.fileRate = sr; in.info = &info; in.role = recycler::BASS;
        in.target = target (48.f, 1); in.outRate = sr;
        const Stereo y = st::render (in);
        const size_t N = y.frames(), w = (size_t) (0.025 * sr), f = (size_t) fadeLen;
        const auto winDb = [&] (size_t b)
        {
            double e = 0;
            for (size_t i = b; i < b + w; ++i) e += (double) y.l[i] * y.l[i];
            return 10.0 * std::log10 (e / w + 1e-30);
        };
        check (N == 240000, "r = 2.5 tail: N frames (1 bar at 48)", (double) N);
        const double d = N == 240000 ? winDb (N - f - w) - winDb (N / 2) : -99.0;
        check (std::fabs (d) <= 1.0, "r = 2.5 tail: last 25 ms within 1 dB of the middle (dB)", d);
    }

    // octave k: a 4-bar 120 BPM click loop (16 clicks 0.5 s apart, 8 s) analysed as "2 bars @ 60"; the effective tempo is 60 * 2^k
    {
        const Stereo a = stereo (sig::clickTrack (120.f, 4, sr));
        const auto loopInfo = [&] (float tempo, int bars)
        {
            recycler::Info i;
            i.tempo = tempo; i.bars = bars; i.frames = (int64_t) a.frames();
            for (int c = 0; c < 16; ++c) i.onsets.push_back (0.5f * c);
            return i;
        };
        const auto renderK = [&] (const recycler::Info& info, int k, float bpm)
        {
            st::RenderIn in;
            in.audio = &a; in.fileRate = sr; in.info = &info; in.role = recycler::DRUMS;
            in.choice.k = k; in.target = target (bpm, 4); in.outRate = sr;
            return st::render (in);
        };
        // every click past the 5 ms fade-in sits on the 0.5 s grid (+- 1 ms), and every grid point has one
        const auto grid = [&] (const Stereo& y, const char* what)
        {
            std::vector<size_t> c = clicks (y.l, sr);
            c.erase (std::remove_if (c.begin(), c.end(), [&] (size_t v) { return v < (size_t) fadeLen; }), c.end());
            const size_t want = (y.frames() - 1) / (sr / 2);   // grid points 0.5 j s, j >= 1, inside the buffer
            double err = c.size() == want ? 0.0 : 1.0;
            for (size_t j = 0; j < c.size() && j < want; ++j) err = std::max (err, std::fabs ((double) c[j] / sr - 0.5 * (j + 1)));
            check (err <= 0.001, what, err);
        };
        const auto diff = [] (const Stereo& p, const Stereo& q) -> double
        {
            if (p.frames() != q.frames() || p.frames() == 0) return 1.0;
            double d = 0;
            for (size_t i = 0; i < p.frames(); ++i)
                d = std::max (d, (double) std::max (std::fabs (p.l[i] - q.l[i]), std::fabs (p.r[i] - q.r[i])));
            return d;
        };

        const recycler::Info half = loopInfo (60.f, 2);
        const Stereo up = renderK (half, 1, 120.f);
        check (up.frames() == 384000, "k=+1, '2 bars @ 60' into 4 bars at 120: N frames", (double) up.frames());
        grid (up, "k=+1: clicks at 0.5 i s +- 1 ms (not 0.25 i), 15 after the fade-in");
        const double du = diff (up, renderK (loopInfo (120.f, 4), 0, 120.f));
        check (du <= 1e-6, "k=+1 render == the same audio as '4 bars @ 120', k=0", du);

        // k = -1 against 30 BPM: effective tempo 30, the 8 s file is 1 effective bar, tiled to 4 (r = 1)
        const Stereo down = renderK (half, -1, 30.f);
        check (down.frames() == st::framesFor (30.f, 4, sr), "k=-1 into 4 bars at 30: N frames (32 s)", (double) down.frames());
        grid (down, "k=-1: clicks at 0.5 i s +- 1 ms through 4 tiles of the whole file");
        const double dd = diff (down, renderK (loopInfo (30.f, 1), 0, 30.f));
        check (dd <= 1e-6, "k=-1 render == the same audio as '1 bar @ 30', k=0", dd);

        // non-loop: tempo 60, k=+1, 4 bars at 120 -> 8 s (+ 1 s), not 16 s; the pitch is untouched
        const Stereo saw = stereo (sig::saw (110.f, 20.f, sr));
        recycler::Info info;
        info.tempo = 60.f; info.onsets.push_back (0.f);
        recycler::picker::Choice ch;
        ch.k = 1;
        const st::Region g1 = st::regionFor (info, recycler::BASS, ch, target (120.f, 4), sr);
        check (g1.start == 0 && g1.frames == 9 * sr, "regionFor non-loop, tempo 60, k=+1: (8 s + 1 s) frames", (double) g1.frames);
        ch.k = 0;
        const st::Region g0 = st::regionFor (info, recycler::BASS, ch, target (120.f, 4), sr);
        check (g0.frames == 17 * sr, "regionFor non-loop, tempo 60, k=0: (16 s + 1 s) frames", (double) g0.frames);
        st::RenderIn in;
        in.audio = &saw; in.fileRate = sr; in.info = &info; in.role = recycler::BASS;
        in.choice.k = 1; in.target = target (120.f, 4); in.outRate = sr;
        const Stereo y = st::render (in);
        const double z = zcr (y.l, sr);
        check (y.frames() == 384000 && std::fabs (z / 220.0 - 1.0) <= 0.02, "render non-loop k=+1: N frames, 220 crossings/s", z);
    }
}
