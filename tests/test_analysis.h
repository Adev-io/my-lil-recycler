// test_analysis.h: frames, onsets, features, tempo, loop snap, key, roles, tags and analyse() against synthetic signals.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <string>
#include "Analysis.h"
#include "check.h"
#include "signals.h"

// tempo (ACF of the mean-removed ODF + octave candidates), loop snap (file length as the clock) and the file-name tag
inline void testTempo()
{
    using namespace recycler;
    const int R = analysis::RATE;
    std::printf ("-- tempo\n");
    auto fluxOf = [] (const std::vector<float>& mono) { return analysis::odf (analysis::frames (mono)); };
    auto secondsOf = [&] (const std::vector<float>& mono) { return (float) mono.size() / (float) R; };

    for (float bpm : { 93.f, 120.f, 174.f })
    {
        const std::vector<float> track = sig::clickTrack (bpm, 4, R);
        float conf = 0.f, snapped = 0.f;
        std::vector<float> cand;
        const float t = analysis::tempo (fluxOf (track), conf, &cand);
        char what[96];
        std::snprintf (what, sizeof what, "clicks %.0f BPM: tempo() within +-1 BPM", bpm);
        check (near (t, bpm, 1.0), what, t);
        std::snprintf (what, sizeof what, "clicks %.0f BPM: tempoConf >= 0.8", bpm);
        check (conf >= 0.8f, what, conf);
        const int bars = analysis::loopSnap (secondsOf (track), cand, snapped);
        std::snprintf (what, sizeof what, "clicks %.0f BPM: loopSnap -> 4 bars", bpm);
        check (bars == 4, what, bars);
        std::snprintf (what, sizeof what, "clicks %.0f BPM: snapped tempo within +-0.05", bpm);
        check (near (snapped, bpm, 0.05), what, snapped);
    }
    for (float bpm : { 93.f, 120.f, 174.f })
    {
        const std::vector<float> track = sig::clickTrack (bpm, 4, R, 15.f, 11);
        float conf = 0.f, snapped = 0.f;
        std::vector<float> cand;
        const float t = analysis::tempo (fluxOf (track), conf, &cand);
        char what[96];
        std::snprintf (what, sizeof what, "clicks %.0f BPM, 15 ms jitter: tempo() within +-2 BPM", bpm);
        check (near (t, bpm, 2.0), what, t);
        const int bars = analysis::loopSnap (secondsOf (track), cand, snapped);
        std::snprintf (what, sizeof what, "clicks %.0f BPM, 15 ms jitter: loopSnap -> 4 bars", bpm);
        check (bars == 4, what, bars);
    }
    {
        const std::vector<float> track = sig::clickTrack (100.f, 2, R);
        float conf = 0.f, snapped = 0.f;
        std::vector<float> cand;
        analysis::tempo (fluxOf (track), conf, &cand);
        const int bars = analysis::loopSnap (secondsOf (track), cand, snapped);
        check (bars == 2, "2-bar loop 100 BPM: loopSnap -> 2 bars", bars);
        check (near (snapped, 100.0, 0.05), "2-bar loop 100 BPM: snapped tempo 100 +- 0.05", snapped);
    }
    {
        std::vector<float> shot (sig::len (1.5f, R), 0.f);
        sig::Rng rng (1);
        sig::burst (shot, 0, R, 5.f, 1.f, 0.8f, rng);
        float conf = -1.f, snapped = -1.f;
        std::vector<float> cand;
        const float t = analysis::tempo (fluxOf (shot), conf, &cand);
        check (t == 0.f, "1.5 s one-shot: tempo 0", t);
        check (conf == 0.f, "1.5 s one-shot: tempoConf 0", conf);
        check (analysis::loopSnap (secondsOf (shot), cand, snapped) == 0, "1.5 s one-shot: bars 0");
    }
    {
        std::vector<float> track = sig::clickTrack (120.f, 4, R);
        track.resize ((size_t) sig::len (3.7f * 2.f, R));   // 3.7 bars of 2 s
        float conf = 0.f, snapped = 0.f;
        std::vector<float> cand;
        analysis::tempo (fluxOf (track), conf, &cand);
        const int bars = analysis::loopSnap (secondsOf (track), cand, snapped);
        check (bars == 0, "120 BPM trimmed to 3.7 bars: not a loop (bars 0)", bars);
        check (near (snapped, 120.0, 2.0), "120 BPM trimmed to 3.7 bars: tempo 120 +- 2", snapped);
    }
    {
        // the x1/3 and x3 variants are in the list; list order (best score first) decides among snapping candidates
        const std::vector<float> track = sig::clickTrack (120.f, 4, R);
        float conf = 0.f, snapped = 0.f;
        std::vector<float> cand;
        analysis::tempo (fluxOf (track), conf, &cand);
        auto has = [&] (float bpm) {
            return std::any_of (cand.begin(), cand.end(), [&] (float c) { return near (c, bpm, 0.5); });
        };
        check (! cand.empty() && near (cand[0], 120.0, 0.5), "120 BPM 4 bars: candidates[0] = 120 +- 0.5", cand.empty() ? 0 : cand[0]);
        check (has (40.f) && has (360.f), "120 BPM 4 bars: candidates hold x1/3 (40) and x3 (360)", (double) cand.size());
        const float seconds = secondsOf (track);
        int bars = analysis::loopSnap (seconds, { 40.f, 120.f, 360.f }, snapped);
        check (bars == 4 && near (snapped, 120.0, 0.05), "loopSnap 8 s {40, 120, 360}: 40 no snap, 120 -> 4 bars @ 120", snapped);
        bars = analysis::loopSnap (seconds, { 360.f, 120.f }, snapped);
        check (bars == 12 && near (snapped, 360.0, 0.05), "loopSnap 8 s {360, 120}: list order -> 12 bars @ 360", snapped);
    }
    // a file longer than 16 bars at its tempo is no loop
    for (int barsIn : { 24, 32, 64 })
    {
        const std::vector<float> track = sig::clickTrack (120.f, barsIn, R);
        float conf = 0.f, snapped = 0.f;
        std::vector<float> cand;
        const float t = analysis::tempo (fluxOf (track), conf, &cand);
        const int bars = analysis::loopSnap (secondsOf (track), cand, snapped);
        std::printf ("     clicks 120 BPM, %d bars: tempo() %.3f\n", barsIn, t);
        char what[96];
        std::snprintf (what, sizeof what, "clicks 120 BPM, %d bars: not a loop (bars 0)", barsIn);
        check (bars == 0, what, bars);
        std::snprintf (what, sizeof what, "clicks 120 BPM, %d bars: tempo 120 +- 1", barsIn);
        check (near (snapped, 120.0, 1.0), what, snapped);
    }
    // octave ambiguity is accepted: 174 may read 87, but a snapped loop's tempo always matches its length
    for (int barsIn : { 8, 32 })
    {
        const std::vector<float> track = sig::clickTrack (174.f, barsIn, R);
        float conf = 0.f, snapped = 0.f;
        std::vector<float> cand;
        analysis::tempo (fluxOf (track), conf, &cand);
        const float seconds = secondsOf (track);
        const int bars = analysis::loopSnap (seconds, cand, snapped);
        std::printf ("     clicks 174 BPM, %d bars: tempo %.3f, bars %d\n", barsIn, snapped, bars);
        char what[96];
        std::snprintf (what, sizeof what, "clicks 174 BPM, %d bars: tempo 174 or 87 +- 1", barsIn);
        check (near (snapped, 174.0, 1.0) || near (snapped, 87.0, 1.0), what, snapped);
    }
    // loopSnap edges
    {
        float snapped = -1.f;
        int bars = analysis::loopSnap (8.f, std::vector<float>(), snapped);
        check (bars == 0 && snapped == 0.f, "loopSnap: no candidates -> 0 bars, tempo 0", snapped);
        bars = analysis::loopSnap (0.f, { 120.f, 60.f }, snapped);
        check (bars == 0 && snapped == 120.f, "loopSnap: seconds 0 -> 0 bars, first candidate", snapped);
        bars = analysis::loopSnap (-1.f, { 120.f }, snapped);
        check (bars == 0 && snapped == 120.f, "loopSnap: seconds < 0 -> 0 bars, first candidate", snapped);
        bars = analysis::loopSnap (7.4f, { 120.f, 60.f, 240.f }, snapped);
        check (bars == 0 && snapped == 120.f, "loopSnap: nothing snaps -> 0 bars, first candidate", snapped);
        float conf = -1.f;
        std::vector<float> cand (2, 1.f);
        const float t = analysis::tempo (std::vector<float> (500, 3.f), conf, &cand);
        check (t == 0.f && conf == 0.f && cand.empty(), "tempo: constant flux -> 0, conf 0, no candidates", t);
    }
    {
        float conf = 1.f;
        analysis::tempo (fluxOf (sig::whiteNoise (4.f, R, 3)), conf);
        check (conf <= 0.3f, "white noise 4 s: tempoConf <= 0.3", conf);
    }
    {
        float conf = -1.f;
        std::vector<float> cand (3, 1.f);
        const float a = analysis::tempo (std::vector<float>(), conf, &cand);
        check (a == 0.f && conf == 0.f && cand.empty(), "tempo: empty flux -> 0, conf 0, no candidates", a);
        const float b = analysis::tempo (std::vector<float> (10, 1.f), conf, &cand);
        check (b == 0.f && conf == 0.f && cand.empty(), "tempo: 10-frame flux -> 0, conf 0, no candidates", b);
    }
    {
        struct Case { const char* name; bool found; float bpm; };
        const Case cases[] = { { "Drum_Loop_120bpm.wav", true, 120.f }, { "bass 90 BPM Cmin.wav", true, 90.f },
                               { "loop-128-bpm.wav", true, 128.f },     { "x_140_bpm.wav", true, 140.f },
                               { "song2024.wav", false, 0.f },          { "kick.wav", false, 0.f },
                               { "1000bpm.wav", false, 0.f },           { "20bpm.wav", false, 0.f } };
        for (const Case& c : cases)
        {
            float bpm = 0.f;
            const bool found = analysis::tempoTag (c.name, bpm);
            char what[96];
            std::snprintf (what, sizeof what, "tempoTag \"%s\" -> %s", c.name, c.found ? "tag" : "no tag");
            check (found == c.found && (! found || bpm == c.bpm), what, bpm);
        }
    }
}

// key (chroma + Temperley / Krumhansl profiles), key tags, role scores and the whole analyse() pipeline
inline void testKey()
{
    using namespace recycler;
    const int R = analysis::RATE;
    std::printf ("-- key, roles, analyse\n");
    auto keyOf = [] (const std::vector<float>& mono, int& k, bool& minor, float& conf, const float (*profiles)[12]) {
        const analysis::Frames f = analysis::frames (mono);
        float best = 0.f;
        const std::vector<float> on = analysis::onsets (analysis::odf (f), mono, best);
        const analysis::Features ft = analysis::features (f, on, (float) mono.size() / (float) analysis::RATE);
        analysis::key (f, ft.flatness, k, minor, conf, profiles);
    };

    // arpeggios in all 24 keys
    {
        int right[2] = { 0, 0 };
        float worstConf = 1.f;
        for (int t = 0; t < 2; ++t)
            for (int root = 0; root < 12; ++root)
                for (bool minor : { false, true })
                {
                    int k = -2;
                    bool m = ! minor;
                    float conf = 0.f;
                    keyOf (sig::arpeggio (60 + root, minor, 3.f, R), k, m, conf, t == 0 ? analysis::TEMPERLEY : analysis::KRUMHANSL);
                    if (k == root && m == minor)
                    {
                        ++right[t];
                        if (t == 0) worstConf = std::min (worstConf, conf);
                    }
                }
        std::printf ("     24-key arpeggios: Temperley %d / 24, Krumhansl-Kessler %d / 24\n", right[0], right[1]);
        check (right[0] >= 22, "arpeggios, 24 keys, Temperley: >= 22 right (key and mode)", right[0]);
        check (worstConf > 0.3f, "arpeggios, Temperley: keyConf > 0.3 on every right answer (lowest)", worstConf);
    }
    {
        int k = -2;
        bool m = false;
        float conf = 0.f;
        keyOf (sig::pad (60, true, 4.f, R), k, m, conf, analysis::TEMPERLEY);
        check (k == 0 && m, "pad C minor: key 0 minor", k);
        keyOf (sig::pad (57, false, 4.f, R), k, m, conf, analysis::TEMPERLEY);
        check (k == 9 && ! m, "pad A major: key 9 major", k);
        keyOf (sig::whiteNoise (4.f, R, 3), k, m, conf, analysis::TEMPERLEY);
        check (k == -1, "white noise: key -1", k);
        keyOf (sig::bassLine (48, 8.f, R), k, m, conf, analysis::TEMPERLEY);
        check (k == 0, "bassLine root C: key 0", k);
    }

    // role ordering through the real pipeline
    {
        const char* names[4] = { "drums", "bass", "melody", "texture" };
        struct Case { const char* name; std::vector<float> mono; int want; float atLeast; };   // atLeast 0 = no floor check
        const Case cases[] = { { "noiseBursts 4/s", sig::noiseBursts (4.f, 4.f, R, 5), DRUMS, 0.f },
                               { "bassLine C", sig::bassLine (48, 8.f, R), BASS, 0.f },
                               { "melody A", sig::melody (69, 8.f, R), MELODY, 0.f },
                               { "pad A minor 10 s", sig::pad (57, true, 10.f, R), TEXTURE, 0.f },
                               { "drumLoop 120, 2 bars", sig::drumLoop (120.f, 2, R), DRUMS, 0.55f },
                               { "kick+snare 90, 2 bars", sig::drumLoop (90.f, 2, R, false), DRUMS, 0.35f },
                               // pitched 55 Hz kicks make these read as keyed (keyConf ~0.7): drums must not hang on 1 - t
                               { "drumLoop 90, 2 bars", sig::drumLoop (90.f, 2, R), DRUMS, 0.5f },
                               { "drumLoop 100, 2 bars", sig::drumLoop (100.f, 2, R), DRUMS, 0.5f } };
        for (const Case& c : cases)
        {
            const Info info = analysis::analyse (c.mono, R, 60.f);
            int best = 0;
            for (int r = 1; r < 4; ++r) if (info.role[r] > info.role[best]) best = r;
            std::printf ("     roles %-20s drums %.3f  bass %.3f  melody %.3f  texture %.3f  (key %d, keyConf %.2f)\n", c.name,
                         info.role[0], info.role[1], info.role[2], info.role[3], info.key, info.keyConf);
            char what[96];
            std::snprintf (what, sizeof what, "roles: %s -> %s highest", c.name, names[c.want]);
            check (best == c.want, what, best);
            if (c.atLeast > 0.f)
            {
                std::snprintf (what, sizeof what, "roles: %s -> %s >= %.2f", c.name, names[c.want], c.atLeast);
                check (info.role[c.want] >= c.atLeast, what, info.role[c.want]);
            }
        }
    }

    // key tags
    {
        struct Case { const char* name; bool found; int key; bool minor; };
        const Case cases[] = { { "bass 90 BPM Cmin.wav", true, 0, true },  { "pad F#maj.wav", true, 6, false },
                               { "lead_Am_loop.wav", true, 9, true },      { "Dbmajor chords.wav", true, 1, false },
                               { "Bb min pad.wav", true, 10, true },       { "A minor.wav", true, 9, true },
                               { "Amen_break.wav", false, 0, false },      { "Drums.wav", false, 0, false },
                               { "C.wav", false, 0, false },               { "cmin.wav", false, 0, false },
                               { "Am.wav", true, 9, true },                { "AM.wav", false, 0, false },
                               { "A m.wav", false, 0, false },             { "DM me.wav", false, 0, false },
                               { "Recorded 10 AM.wav", false, 0, false } };
        for (const Case& c : cases)
        {
            int k = -1;
            bool m = false;
            const bool found = analysis::keyTag (c.name, k, m);
            char what[96];
            std::snprintf (what, sizeof what, "keyTag \"%s\" -> %s", c.name, c.found ? "tag" : "no tag");
            check (found == c.found && (! found || (k == c.key && m == c.minor)), what, k);
        }
    }

    // analyse(): the whole pipeline
    {
        const std::vector<float> clicks = sig::clickTrack (120.f, 4, 44100);
        const Info a = analysis::analyse (clicks, 44100, 60.f);
        check (near (a.tempo, 120.0, 0.05), "analyse clicks 120 @ 44.1 kHz: tempo 120 +- 0.05", a.tempo);
        check (a.bars == 4, "analyse clicks 120 @ 44.1 kHz: 4 bars", a.bars);
        check (a.onsets.size() == 16, "analyse clicks 120 @ 44.1 kHz: 16 onsets", (double) a.onsets.size());
        double dc = 0, ss = 0;   // reference rms of the DC-removed input; 16 sparse 5 ms clicks in 8 s sit near -36 dBFS
        for (float v : clicks) dc += v;
        dc /= (double) clicks.size();
        for (float v : clicks) ss += (v - dc) * (v - dc);
        const double ref = 20.0 * std::log10 (std::sqrt (ss / (double) clicks.size()));
        check (near (a.rms, ref, 0.01), "analyse clicks 120 @ 44.1 kHz: rms = DC-removed input rms +- 0.01 dB (dBFS)", a.rms);
        check (a.peak <= 0.f, "analyse clicks 120 @ 44.1 kHz: peak <= 0 dBFS", a.peak);
        check (a.seconds == 8.f && a.frames == (int64_t) clicks.size() && a.sampleRate == 44100,
               "analyse clicks 120 @ 44.1 kHz: seconds 8, frames = input length, sampleRate 44100", a.seconds);

        const Info t = analysis::analyse (clicks, 44100, 60.f, "loop 60bpm.wav");
        check (t.tempo == 60.f, "analyse clicks 120, \"loop 60bpm.wav\": tag wins, tempo 60", t.tempo);
        check (t.bars == 2, "analyse clicks 120, \"loop 60bpm.wav\": 2 bars", t.bars);
        check (t.tempoConf == 1.f, "analyse clicks 120, \"loop 60bpm.wav\": tempoConf 1", t.tempoConf);
    }
    {
        const Info n = analysis::analyse (sig::whiteNoise (4.f, R, 3), R, 60.f, "noise Cmin.wav");
        check (n.key == 0 && n.minor, "analyse noise, \"noise Cmin.wav\": key 0 minor from the tag", n.key);
        check (n.keyConf == 0.6f, "analyse noise, \"noise Cmin.wav\": keyConf 0.6", n.keyConf);
    }
    {
        const std::vector<float> long90 = sig::pad (57, true, 90.f, R);
        const Info p = analysis::analyse (long90, R, 30.f);
        check (p.seconds == 90.f && p.frames == (int64_t) long90.size(), "analyse 90 s pad, cap 30: seconds 90, full frames", p.seconds);
        check (std::all_of (p.onsets.begin(), p.onsets.end(), [] (float s) { return s <= 30.f; }), "analyse 90 s pad, cap 30: no onset past 30 s");
        bool finite = std::isfinite (p.tempo) && std::isfinite (p.tempoConf) && std::isfinite (p.keyConf) && std::isfinite (p.rms)
                      && std::isfinite (p.peak) && std::isfinite (p.bestOnset);
        for (float r : p.role) finite = finite && std::isfinite (r);
        check (finite, "analyse 90 s pad, cap 30: every field finite");
    }
    {
        const Info s = analysis::analyse (std::vector<float> (R, 0.f), R, 60.f);
        check (s.tempo == 0.f, "analyse 1 s silence: tempo 0", s.tempo);
        check (s.key == -1, "analyse 1 s silence: key -1", s.key);
        bool finite = true, zero = true;
        for (float r : s.role) { finite = finite && std::isfinite (r); zero = zero && r == 0.f; }
        check (finite, "analyse 1 s silence: all roles finite");
        check (zero, "analyse 1 s silence: all four roles 0", s.role[TEXTURE]);
        const Info e = analysis::analyse (std::vector<float>(), R, 60.f);
        check (e.role[0] == 0.f && e.role[1] == 0.f && e.role[2] == 0.f && e.role[3] == 0.f, "analyse empty input: all four roles 0");
    }
    {
        std::vector<float> three (sig::len (2.5f, R), 0.f);
        sig::Rng rng (2);
        for (int i = 0; i < 3; ++i) sig::burst (three, sig::len (0.5f * i, R), R, 5.f, 1.f, 0.8f, rng);
        const Info c = analysis::analyse (three, R, 60.f);
        check (c.onsets.size() == 3, "analyse 3 clicks in 2.5 s: 3 onsets", (double) c.onsets.size());
        check (c.tempo == 0.f && c.bars == 0, "analyse 3 clicks in 2.5 s: under 4 onsets -> tempo 0, bars 0", c.tempo);
    }
    {
        // a tempo tag wins over the 2 s and 4-onset gates
        std::vector<float> kick (sig::len (1.5f, R), 0.f);
        sig::Rng rng (3);
        sig::burst (kick, 0, R, 5.f, 1.f, 0.8f, rng);
        const Info k = analysis::analyse (kick, R, 60.f, "kick 120bpm.wav");
        check (k.tempo == 120.f && k.tempoConf == 1.f, "analyse 1.5 s \"kick 120bpm.wav\": tag wins, tempo 120, conf 1", k.tempo);
        check (k.bars == 0, "analyse 1.5 s \"kick 120bpm.wav\": bars 0 (0.75 bar is no loop)", k.bars);
    }
}

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
    testTempo();
    testKey();
}
