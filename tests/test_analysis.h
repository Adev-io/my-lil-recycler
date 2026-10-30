// test_analysis.h: spectral frames, onset detection and the five features against synthetic signals at 22 050 Hz.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include <algorithm>
#include <cmath>
#include "Analysis.h"
#include "check.h"
#include "signals.h"

inline void testAnalysis()
{
    using namespace recycler;
    const int R = analysis::RATE;
    std::printf ("-- analysis\n");

    auto onsetsOf = [] (const std::vector<float>& mono, float& best) {
        return analysis::onsets (analysis::odf (analysis::frames (mono)), mono, best);
    };
    auto countOf = [&] (const std::vector<float>& mono) {
        float best = 0.f;
        return (int) onsetsOf (mono, best).size();
    };

    // frame count rule: one frame per hop, ceil(len / HOP), so frame times cover 0 .. len
    {
        const analysis::Frames one = analysis::frames (std::vector<float> (R, 0.f));
        check (one.count == (R + analysis::HOP - 1) / analysis::HOP, "frames: count = ceil(len / HOP) for 1 s", one.count);
        check (one.samples == (size_t) R, "frames: samples = input length", (double) one.samples);
        check (analysis::frames (std::vector<float> (512, 0.f)).count == 2, "frames: 512 samples -> 2 frames");
        check (analysis::frames (std::vector<float> (513, 0.f)).count == 3, "frames: 513 samples -> 3 frames");
        check (analysis::frames (std::vector<float>()).count == 0, "frames: empty input -> 0 frames");
        const analysis::Frames f = analysis::frames (sig::whiteNoise (2.f, R, 7));
        check ((int) f.mag.size() == f.count * analysis::BINS, "frames: mag holds count x BINS values", (double) f.mag.size());
        bool finite = true;
        for (int i = 0; i < f.count; ++i)
            for (int b = 0; b < analysis::BINS; ++b)
                if (! std::isfinite (f.at (i, b)) || f.at (i, b) < 0.f) finite = false;
        check (finite, "frames: at(f, b) finite and >= 0 everywhere for noise");
    }

    // click track: exactly 16 onsets, each cut at most 2 ms early and at most 0.5 ms late; bestSec is one of them
    {
        const std::vector<float> clicks = sig::clickTrack (120.f, 4, R);
        const analysis::Frames f = analysis::frames (clicks);
        const std::vector<float> o = analysis::odf (f);
        check ((int) o.size() == f.count, "odf: one value per frame", (double) o.size());
        check (std::all_of (o.begin(), o.end(), [] (float v) { return v >= 0.f && std::isfinite (v); }), "odf: >= 0 and finite");
        float best = -1.f;
        const std::vector<float> on = analysis::onsets (o, clicks, best);
        check (on.size() == 16, "click track 120 BPM 4 bars: exactly 16 onsets", (double) on.size());
        // signed cut error on the 120 and 174 BPM tracks: at most one hop early, at most 0.5 ms late
        double lo = 1, hi = -1;
        bool all16 = true;
        for (float bpm : { 120.f, 174.f })
        {
            const std::vector<float> track = sig::clickTrack (bpm, 4, R);
            float b = 0.f;
            const std::vector<float> t = onsetsOf (track, b);
            all16 = all16 && t.size() == 16;
            for (size_t i = 0; i < t.size() && i < 16; ++i)
            {
                const double e = t[i] - std::lround (i * 60.0 / bpm * R) / (double) R;
                lo = std::min (lo, e);
                hi = std::max (hi, e);
            }
        }
        check (all16 && lo >= -0.002, "clicks 120 + 174 BPM: earliest signed error >= -2 ms (s)", lo);
        check (all16 && hi <= 0.0005, "clicks 120 + 174 BPM: latest signed error <= +0.5 ms (s)", hi);
        bool bestIsOnset = false;
        for (float t : on) bestIsOnset = bestIsOnset || t == best;
        check (bestIsOnset, "click track: bestSec is one of the onsets", best);

        std::vector<float> quiet = clicks;
        for (float& v : quiet) v *= 0.0316f;
        check (countOf (quiet) == 16, "click track at -30 dB: exactly 16 onsets", countOf (quiet));
        const int jittered = countOf (sig::clickTrack (174.f, 4, R, 15.f, 11));
        check (jittered == 16, "click track 174 BPM, 15 ms jitter: exactly 16 onsets", jittered);
    }

    // an 808-style kick over a sustained pad is cut at its start, at every sub-hop placement
    {
        std::vector<float> bed = sig::pad (57, true, 4.f, R);
        for (float& v : bed) v *= 0.8f;   // pad peak 0.5 -> 0.4
        const int kickLen = (int) (0.15 * R), base = 172 * analysis::HOP;   // ~2 s in, well past the fade-in
        double lo = 1, hi = -1;
        bool found = true;
        for (int offset = 0; offset < analysis::HOP; offset += 8)
        {
            std::vector<float> mix = bed;
            double phase = 0;
            for (int i = 0; i < kickLen; ++i)   // sine sweeping 150 -> 50 Hz exponentially, linear decay from 0.8
            {
                mix[base + offset + i] += 0.8f * (1.f - (float) i / kickLen) * (float) std::sin (2.0 * sig::PI * phase);
                phase += 150.0 * std::pow (50.0 / 150.0, (double) i / kickLen) / R;
            }
            float best = 0.f;
            const std::vector<float> on = onsetsOf (mix, best);
            const double at = (base + offset) / (double) R;
            double e = 1;
            for (float t : on) if (std::fabs (t - at) < std::fabs (e)) e = t - at;
            found = found && std::fabs (e) < 0.02;
            lo = std::min (lo, e);
            hi = std::max (hi, e);
        }
        check (found && lo >= -0.002, "kick over pad, 32 placements: earliest signed error >= -2 ms (s)", lo);
        check (found && hi <= 0.001, "kick over pad, 32 placements: latest signed error <= +1 ms (s)", hi);
    }

    // no false onsets on sustained and stationary material; one per note on parts
    {
        const int pad = countOf (sig::pad (57, true, 10.f, R));
        check (pad <= 1, "pad 10 s: <= 1 onset", pad);
        const int sine = countOf (sig::sine (440.f, 4.f, R));
        check (sine <= 1, "sine 4 s: <= 1 onset", sine);
        const int noise = countOf (sig::whiteNoise (4.f, R, 3));
        check (noise <= 1, "white noise 4 s: <= 1 onset", noise);
        const int arp = countOf (sig::arpeggio (57, true, 4.f, R));
        check (std::abs (arp - 16) <= 1, "arpeggio 16 notes: 16 +- 1 onsets", arp);
        const int bass = countOf (sig::bassLine (33, 8.f, R));
        check (std::abs (bass - 16) <= 1, "bassLine 16 notes: 16 +- 1 onsets", bass);
    }

    // a DC offset changes nothing: same onsets, same low-band share
    {
        const std::vector<float> clean = sig::noiseBursts (4.f, 4.f, R, 5);
        std::vector<float> offset = clean;
        for (float& v : offset) v += 0.05f;
        float best = 0.f;
        const std::vector<float> on = onsetsOf (offset, best);
        check (on.size() == 16, "noiseBursts + 0.05 DC: exactly 16 onsets", (double) on.size());
        const float a = analysis::features (analysis::frames (clean), on, 4.f).lowShare;
        const float b = analysis::features (analysis::frames (offset), on, 4.f).lowShare;
        check (std::fabs (a - b) <= 1e-3f, "noiseBursts + 0.05 DC: lowShare within 1e-3 of no-DC (diff)", std::fabs (a - b));
    }

    // silence: no onsets, bestSec 0, every feature finite
    {
        const std::vector<float> zero (R, 0.f);
        const analysis::Frames f = analysis::frames (zero);
        float best = -1.f;
        const std::vector<float> on = analysis::onsets (analysis::odf (f), zero, best);
        check (on.empty(), "silence: 0 onsets", (double) on.size());
        check (best == 0.f, "silence: bestSec 0", best);
        const analysis::Features x = analysis::features (f, on, 1.f);
        check (std::isfinite (x.onsetDensity) && std::isfinite (x.lowShare) && std::isfinite (x.centroid)
                   && std::isfinite (x.sustain) && std::isfinite (x.flatness) && x.tonalness == 0.f,
               "silence: all features finite");
    }

    // shorter than one window: no crash, finite features, at most one onset
    {
        const std::vector<float> tiny = sig::whiteNoise (300.f / R, R, 4);
        const analysis::Frames f = analysis::frames (tiny);
        float best = 0.f;
        const std::vector<float> on = analysis::onsets (analysis::odf (f), tiny, best);
        check (tiny.size() == 300 && on.size() <= 1, "300 samples: 0 or 1 onset", (double) on.size());
        const analysis::Features x = analysis::features (f, on, 300.f / R);
        check (std::isfinite (x.onsetDensity) && std::isfinite (x.lowShare) && std::isfinite (x.centroid)
                   && std::isfinite (x.sustain) && std::isfinite (x.flatness),
               "300 samples: all features finite");
    }

    // features
    auto featuresOf = [&] (const std::vector<float>& mono) {
        float best = 0.f;
        return analysis::features (analysis::frames (mono), onsetsOf (mono, best), (float) mono.size() / (float) R);
    };
    {
        const analysis::Features noise = featuresOf (sig::whiteNoise (4.f, R, 3));
        check (noise.flatness > 0.6f, "whiteNoise: flatness > 0.6", noise.flatness);
        const analysis::Features pad = featuresOf (sig::pad (60, false, 4.f, R));
        check (pad.flatness < 0.2f, "pad: flatness < 0.2", pad.flatness);
        std::vector<float> tailed = sig::pad (60, false, 4.f, R);
        const std::vector<float> hiss = sig::whiteNoise (12.f, R, 8);   // +-0.5 -> peak -90 dBFS
        for (float v : hiss) tailed.push_back (v * 2.f * 3.16228e-5f);
        const analysis::Features gated = featuresOf (tailed);
        check (gated.flatness < 0.2f, "pad + 12 s of -90 dB noise tail: flatness < 0.2", gated.flatness);
    }
    {
        const analysis::Features bass = featuresOf (sig::bassLine (33, 8.f, R));
        check (bass.lowShare > 0.5f, "bassLine: lowShare > 0.5", bass.lowShare);
        check (bass.centroid < 300.f, "bassLine: centroid < 300 Hz", bass.centroid);
    }
    {
        const analysis::Features mel = featuresOf (sig::melody (69, 8.f, R));
        check (mel.centroid >= 400.f && mel.centroid <= 1200.f, "melody: centroid in 400..1200 Hz", mel.centroid);
        check (mel.lowShare < 0.1f, "melody: lowShare < 0.1", mel.lowShare);
    }
    {
        const analysis::Features pad = featuresOf (sig::pad (57, true, 10.f, R));
        check (pad.sustain > 0.8f, "pad 10 s: sustain > 0.8", pad.sustain);
        check (pad.tonalness == 0.f, "features: tonalness stays 0 in part 1", pad.tonalness);
    }
    {
        const std::vector<float> b = sig::noiseBursts (4.f, 4.f, R, 5);
        float best = 0.f;
        const std::vector<float> on = onsetsOf (b, best);
        check (on.size() == 16, "noiseBursts 4/s over 4 s: exactly 16 onsets", (double) on.size());
        const analysis::Features bursts = analysis::features (analysis::frames (b), on, 4.f);
        check (bursts.sustain < 0.3f, "noiseBursts 4/s: sustain < 0.3", bursts.sustain);
        check (bursts.onsetDensity == 4.f, "noiseBursts 4/s: onsetDensity == 4", bursts.onsetDensity);
    }
}
