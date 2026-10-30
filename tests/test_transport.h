// test_transport.h: clock tempo, bar phase, slew vs jump, RUN, RESET and the bar-0 wrap of Transport.h.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include "check.h"
#include "Transport.h"
#include <algorithm>
#include <cstdlib>

inline void tpRun (recycler::Transport& t, int n) { for (int i = 0; i < n; ++i) t.tick(); }
inline bool tpPulse (recycler::Transport& t) { t.clockPulse(); return t.tick(); }

// bpm() after two pulses n samples apart at 48 kHz, knob 90 (= the clock tempo before any accepted interval)
inline double tpOneInterval (int n)
{
    recycler::Transport t;
    t.setSampleRate (48000.f); t.setKnobBpm (90.f); t.setClockConnected (true); t.setRunning (true);
    tpPulse (t);
    tpRun (t, n - 1);
    tpPulse (t);
    return t.bpm();
}

// drives n ticks, pulsing on each tick where pulseNow(i) is true; counts jumps, wraps, reversals (dphase <= 0)
// and the largest |dphase - step| from tick `devFrom` on
struct TpStats { int jumps = 0, wraps = 0, reversals = 0, gapMin = 1 << 30, gapMax = 0; double maxDev = 0.0; };
template <class F>
TpStats tpDrive (recycler::Transport& t, int n, F pulseNow, double step = 0.0, int devFrom = 0)
{
    TpStats s;
    int last = -1;
    double prev = t.phase();
    for (int i = 0; i < n; ++i)
    {
        if (pulseNow (i)) t.clockPulse();
        const bool w = t.tick();
        const double d = t.phase() - prev + (w ? 1.0 : 0.0);
        prev = t.phase();
        if (t.jumped()) ++s.jumps;
        if (d <= 0.0) ++s.reversals;
        if (i >= devFrom) s.maxDev = std::max (s.maxDev, std::fabs (d - step));
        if (w)
        {
            ++s.wraps;
            if (last >= 0) { s.gapMin = std::min (s.gapMin, i - last); s.gapMax = std::max (s.gapMax, i - last); }
            last = i;
        }
    }
    return s;
}

inline recycler::Transport tpClocked (int bars = 4)
{
    recycler::Transport t;
    t.setSampleRate (48000.f); t.setBars (bars); t.setKnobBpm (120.f);
    t.setClockConnected (true); t.setRunning (true);
    return t;
}

// ticks n times; returns the wrap count, the 1-based tick of the first wrap and the largest gap between wraps
inline int tpWraps (recycler::Transport& t, int n, int& first, int& gapMin, int& gapMax, bool& inRange)
{
    int wraps = 0, last = -1;
    first = -1; gapMin = 1 << 30; gapMax = 0; inRange = true;
    for (int i = 1; i <= n; ++i)
    {
        if (t.tick())
        {
            ++wraps;
            if (first < 0) first = i;
            if (last > 0) { gapMin = std::min (gapMin, i - last); gapMax = std::max (gapMax, i - last); }
            last = i;
        }
        if (! (t.phase() >= 0.0 && t.phase() < 1.0)) inRange = false;
    }
    return wraps;
}

inline void testTransport()
{
    using recycler::Transport;
    const double inc = 1.0 / (16.0 * 24000.0);   // 120 BPM, 4 bars, 48 kHz

    {   // clock connected: tempo, reset, on-time / early / late pulses, RUN
        Transport t;
        t.setSampleRate (48000.f); t.setBars (4); t.setKnobBpm (90.f);
        t.setClockConnected (true); t.setRunning (true);
        for (int k = 0; k < 4; ++k) { tpPulse (t); tpRun (t, 23999); }
        check (near (t.bpm(), 120.0, 0.1), "transport: 4 pulses 24000 apart -> 120 BPM (knob 90 ignored)", t.bpm());

        t.reset();
        tpPulse (t);
        check (t.phase() == 0.0, "transport: reset lands phase exactly 0 on the next pulse's tick", t.phase());
        double prev = t.phase(), dev = 0.0;
        for (int i = 0; i < 23999; ++i) { t.tick(); dev = std::max (dev, std::fabs (t.phase() - prev - inc)); prev = t.phase(); }
        tpPulse (t);   // on time: beat 1
        check (dev < 1e-12, "transport: phase advances 1/(16*24000) per tick", dev);
        check (near (t.phase(), 1.0 / 16, 1e-6), "transport: phase after 24000 ticks = 1/16", t.phase());

        // beat 2 arrives 48 samples (1 ms) early: slewed over the next beat, never a jump
        tpRun (t, 24000 - 48 - 1);
        prev = t.phase();
        tpPulse (t);
        double step = std::fabs (t.phase() - prev - inc), least = t.phase() - prev;
        bool jumped = t.jumped();
        prev = t.phase();
        for (int i = 0; i < 23999; ++i)
        {
            t.tick();
            step = std::max (step, std::fabs (t.phase() - prev - inc));
            least = std::min (least, t.phase() - prev);
            jumped |= t.jumped();
            prev = t.phase();
        }
        check (step <= 1e-7, "transport: 1 ms early pulse slews (|dphase - step| <= 1e-7 every tick)", step);
        check (least > 0.0 && ! jumped, "transport: 1 ms early pulse -> phase always moves forward, no jump", least);

        // beat 3 arrives 2400 samples (10 % of a beat) late: jumps on that tick
        tpRun (t, 24000 + 48 + 2400 - 1 - 23999);
        prev = t.phase();
        tpPulse (t);
        check (std::fabs (t.phase() - prev) > 1e-4 && t.jumped(), "transport: 2400 samples late pulse jumps", t.phase() - prev);
        check (near (t.phase(), 3.0 / 16, 1e-9), "transport: late pulse lands on beat 3", t.phase());
        check (near (t.bpm(), 120.0, 0.1), "transport: median ignores one early and one late pulse", t.bpm());

        // RUN off: phase frozen, pulses do not move it, no wrap
        t.setRunning (false);
        const double frozen = t.phase();
        bool wrapped = false;
        for (int i = 0; i < 10000; ++i) { if (i % 2000 == 0) t.clockPulse(); wrapped |= t.tick(); }
        check (t.phase() == frozen && ! t.running(), "transport: stopped -> phase frozen over 10000 ticks with pulses", t.phase() - frozen);
        check (! wrapped, "transport: stopped -> tick() never true");
    }

    {   // knob 120, no clock: 16 beats = 384000 ticks, one wrap per loop, none while stopped
        Transport t;
        t.setSampleRate (48000.f); t.setBars (4); t.setKnobBpm (120.f); t.setRunning (true);
        int first, gapMin, gapMax; bool inRange;
        const int wraps = tpWraps (t, 800000, first, gapMin, gapMax, inRange);
        check (wraps == 2, "transport: knob 120 -> exactly one wrap per 384000 ticks", wraps);
        check (std::abs (first - 384000) <= 1, "transport: knob 120 -> first wrap at 384000 +- 1", first);
        check (std::abs (gapMin - 384000) <= 1 && std::abs (gapMax - 384000) <= 1, "transport: knob 120 -> loop = 384000 +- 1", gapMax);
        check (inRange, "transport: phase stays in [0, 1)");
        check (near (t.bpm(), 120.0, 1e-9), "transport: unpatched bpm() = knob", t.bpm());

        t.setRunning (false);
        const double frozen = t.phase();
        check (tpWraps (t, 400000, first, gapMin, gapMax, inRange) == 0 && t.phase() == frozen, "transport: stopped -> no wrap, phase frozen");

        t.setRunning (true);
        double prev = t.phase();
        t.clockPulse();   // unpatched: ignored
        t.tick();
        check (near (t.phase() - prev, inc, 1e-12) && ! t.jumped(), "transport: clockPulse() while unpatched is ignored", t.phase() - prev);
        tpRun (t, 1000);
        t.reset();   // no clock: immediate
        t.tick();
        check (t.phase() == 0.0, "transport: unpatched reset -> phase 0 at once", t.phase());
    }

    {   // knob 60
        Transport t;
        t.setSampleRate (48000.f); t.setBars (4); t.setKnobBpm (60.f); t.setRunning (true);
        int first, gapMin, gapMax; bool inRange;
        const int wraps = tpWraps (t, 800000, first, gapMin, gapMax, inRange);
        check (wraps == 1 && std::abs (first - 768000) <= 1, "transport: knob 60 -> wrap at 768000 +- 1", first);
    }

    {   // 1 bar: wrap every 4 beats
        Transport t;
        t.setSampleRate (48000.f); t.setBars (1); t.setKnobBpm (120.f); t.setRunning (true);
        int first, gapMin, gapMax; bool inRange;
        const int wraps = tpWraps (t, 300000, first, gapMin, gapMax, inRange);
        check (wraps == 3 && std::abs (first - 96000) <= 1 && std::abs (gapMin - 96000) <= 1 && std::abs (gapMax - 96000) <= 1,
               "transport: setBars(1) -> wrap every 96000 +- 1 ticks", gapMax);
    }

    {   // out-of-range intervals never enter the median: a 720 BPM burst and a stopped clock both leave 120
        Transport t;
        t.setSampleRate (48000.f); t.setBars (4); t.setKnobBpm (90.f);
        t.setClockConnected (true); t.setRunning (true);
        for (int k = 0; k < 5; ++k) { tpPulse (t); tpRun (t, 23999); }
        bool held = true;
        double worst = 120.0;
        for (int k = 0; k < 8; ++k)
        {
            tpPulse (t); tpRun (t, 3999);   // 4000 samples = 720 BPM
            if (! near (t.bpm(), 120.0, 0.1)) { held = false; worst = t.bpm(); }
        }
        check (held, "transport: 720 BPM pulses -> bpm() stays 120 after every pulse", worst);
        tpRun (t, 480000);                  // clock stops 10 s, then restarts
        tpPulse (t);
        check (near (t.bpm(), 120.0, 0.1), "transport: clock restart gap dropped -> bpm() stays 120", t.bpm());
    }

    // a beat-15 pulse `late` samples late (clock keeps going from there): one wrap per loop, never two
    for (int late = 12000; late <= 36000; late += 24000)
    {
        Transport t;
        t.setSampleRate (48000.f); t.setBars (4); t.setKnobBpm (120.f);
        t.setClockConnected (true); t.setRunning (true);
        const int p15 = 15 * 24000 + late, end1 = p15 + 36000, end2 = end1 + 16 * 24000;
        int next = 0, w1 = 0, w2 = 0;
        for (int i = 0; i < end2; ++i)
        {
            if (i == next) { t.clockPulse(); next = next + 24000 == 15 * 24000 ? p15 : next + 24000; }
            if (t.tick()) ++(i < end1 ? w1 : w2);
        }
        check (w1 == 1, late > 24000 ? "transport: beat 15 pulse 1.5 beats late (after the wrap) -> one wrap in that loop"
                                     : "transport: beat 15 pulse 12000 samples late -> one wrap in that loop", w1);
        check (w2 == 1, late > 24000 ? "transport: ... and one wrap in the next loop (1.5 beats late)"
                                     : "transport: ... and one wrap in the next loop (12000 late)", w2);
    }

    {   // setBars mid-run with the clock: the next pulse does not jump half a loop
        Transport t;
        t.setSampleRate (48000.f); t.setBars (4); t.setKnobBpm (120.f);
        t.setClockConnected (true); t.setRunning (true);
        for (int k = 0; k < 8; ++k) { tpPulse (t); tpRun (t, 23999); }   // next pulse is beat 8: phase 0.5
        t.setBars (1);
        const double before = t.phase();
        tpPulse (t);
        check (std::fabs (t.phase() - before) < 1e-3, "transport: setBars(1) at phase 0.5 -> next pulse does not jump", t.phase() - before);
        check (t.phase() >= 0.0 && t.phase() < 1.0, "transport: setBars(1) -> phase stays in [0, 1)", t.phase());
    }

    {   // RESET pending when the clock is unpatched: lands at once
        Transport t;
        t.setSampleRate (48000.f); t.setBars (4); t.setKnobBpm (120.f);
        t.setClockConnected (true); t.setRunning (true);
        tpPulse (t); tpRun (t, 30000);
        t.reset();
        t.setClockConnected (false);
        t.tick();
        check (t.phase() == 0.0, "transport: reset pending + clock unpatched -> phase 0 on the next tick", t.phase());
    }

    // tempo range edges at 48 kHz: 72000 = 40 BPM and 12000 = 240 BPM accepted, one sample outside rejected
    check (near (tpOneInterval (72000), 40.0, 1e-4), "transport: 72000-sample interval accepted (40 BPM)", tpOneInterval (72000));
    check (near (tpOneInterval (12000), 240.0, 1e-4), "transport: 12000-sample interval accepted (240 BPM)", tpOneInterval (12000));
    check (near (tpOneInterval (72001), 90.0, 1e-9), "transport: 72001-sample interval rejected", tpOneInterval (72001));
    check (near (tpOneInterval (11999), 90.0, 1e-9), "transport: 11999-sample interval rejected", tpOneInterval (11999));

    // tempo ramps 120 -> 100 over 8 beats and 120 -> 110 over 16 beats: followed by slewing, never a jump
    for (int ramp = 0; ramp < 2; ++ramp)
    {
        Transport t = tpClocked();
        const int beats = ramp ? 16 : 8;
        const double to = ramp ? 110.0 : 100.0, endI = 48000.0 * 60.0 / to;
        int next = 0, k = 0;
        auto pulse = [&] (int i) -> bool
        {
            if (i != next) return false;
            const int r = ++k - 6;   // intervals into the ramp (6 steady ones first)
            const double iv = r <= 0 ? 24000.0 : r >= beats ? endI : 24000.0 + (endI - 24000.0) * r / beats;
            next += (int) (iv + 0.5);
            return true;
        };
        const TpStats s = tpDrive (t, 6 * 24000 + (beats + 8) * 29000, pulse);
        std::printf ("      transport ramp 120 -> %g over %d beats: %d jump(s), %d reversal(s)\n", to, beats, s.jumps, s.reversals);
        check (s.jumps == 0, ramp ? "transport: ramp 120 -> 110 over 16 beats -> 0 jumps" : "transport: ramp 120 -> 100 over 8 beats -> 0 jumps", s.jumps);
        check (s.reversals == 0, ramp ? "transport: ramp 120 -> 110 -> phase moves forward every tick" : "transport: ramp 120 -> 100 -> phase moves forward every tick", s.reversals);
        check (near (t.bpm(), to, 0.1), ramp ? "transport: ramp ends at 110 BPM" : "transport: ramp ends at 100 BPM", t.bpm());
    }

    {   // tempo step 120 -> 100 (one pulse 4800 samples late, then 28800 apart): exactly one jump, on that pulse
        Transport t = tpClocked();
        int next = 0, k = 0, jumps = 0;
        bool onStep = false;
        const int stepAt = 5 * 24000 + 28800;
        for (int i = 0; i < 6 * 24000 + 10 * 28800; ++i)
        {
            if (i == next) { t.clockPulse(); next += ++k < 6 ? 24000 : 28800; }
            t.tick();
            if (t.jumped()) { ++jumps; if (i == stepAt) onStep = true; }
        }
        std::printf ("      transport step 120 -> 100: %d jump(s)\n", jumps);
        check (jumps == 1 && onStep, "transport: tempo step 120 -> 100 -> exactly one jump, jumped() on the step pulse", jumps);
        check (near (t.bpm(), 100.0, 0.1), "transport: tempo step -> 100 BPM", t.bpm());
    }

    {   // reconnect: the ring restarts from empty, so a 90 BPM clock reads 90 after its first interval
        Transport t = tpClocked();
        for (int k = 0; k < 6; ++k) { tpPulse (t); tpRun (t, 23999); }   // 5 intervals: ring position is not 0
        t.setClockConnected (false);
        tpRun (t, 10000);
        t.setClockConnected (true);
        tpPulse (t); tpRun (t, 31999); tpPulse (t);
        check (near (t.bpm(), 90.0, 0.1), "transport: repatched 90 BPM clock -> bpm() 90 after the first interval", t.bpm());
        int next = 31999;
        const TpStats s = tpDrive (t, 8 * 32000, [&] (int i) -> bool { if (i != next) return false; next += 32000; return true; },
                                   90.0 / 60.0 / 16.0 / 48000.0);
        check (s.maxDev <= 1e-6 && s.jumps == 0, "transport: repatched 90 BPM clock -> no jumps after it (|dphase - step| <= 1e-6)", s.maxDev);
    }

    {   // sample rate change: the ring restarts, the tempo in BPM holds
        Transport t = tpClocked();
        for (int k = 0; k < 6; ++k) { tpPulse (t); tpRun (t, 23999); }
        tpPulse (t);
        t.setSampleRate (96000.f);
        int next = 47999, jumps = 0;
        bool held = true;
        double worst = 120.0;
        for (int i = 0; i < 8 * 48000; ++i)
        {
            if (i == next) { t.clockPulse(); next += 48000; }
            t.tick();
            if (t.jumped()) ++jumps;
            if (! near (t.bpm(), 120.0, 0.1)) { held = false; worst = t.bpm(); }
        }
        check (held, "transport: 48k -> 96k with the clock at 120 -> bpm() stays 120 every tick", worst);
        check (jumps == 0, "transport: 48k -> 96k -> no jumps", jumps);
    }

    {   // clock stops 10 s (+ a quarter beat) and restarts without RESET: lands on the nearest beat
        Transport t = tpClocked();
        for (int k = 0; k < 6; ++k) { tpPulse (t); tpRun (t, 23999); }
        tpRun (t, 486000 - 24000);
        const double prev = t.phase();
        tpPulse (t);
        double d = t.phase() - prev;
        d -= std::floor (d + 0.5);
        check (std::fabs (d) <= 1.0 / 32, "transport: clock restart after 10 s -> |dphase| <= half a beat", d);
    }

    {   // beat-0 pulse 4800 samples early jumps forward across the loop end: one wrap, reported by that jump
        Transport t = tpClocked();
        const int p16 = 16 * 24000 - 4800, end1 = p16 + 12000, end2 = end1 + 16 * 24000;
        int next = 0, w1 = 0, w2 = 0;
        bool byJump = false;
        for (int i = 0; i < end2; ++i)
        {
            if (i == next) { t.clockPulse(); next = next + 24000 == 16 * 24000 ? p16 : next + 24000; }
            const bool w = t.tick();
            if (w) ++(i < end1 ? w1 : w2);
            if (i == p16 && w && t.jumped()) byJump = true;
        }
        check (w1 == 1 && byJump, "transport: early bar pulse jumps across the loop end -> one wrap, on the jump", w1);
        check (w2 == 1, "transport: ... and one wrap in the next loop", w2);
    }

    {   // RESET while stopped (clock patched) lands on the next stopped tick; the first pulse after RUN does not jump
        Transport t = tpClocked();
        tpPulse (t); tpRun (t, 30000);
        t.setRunning (false);
        t.reset();
        t.tick();
        check (t.phase() == 0.0 && t.jumped(), "transport: reset while stopped -> phase 0 on the next stopped tick", t.phase());
        t.setRunning (true);
        tpPulse (t);
        check (! t.jumped() && t.phase() < 1e-4, "transport: ... first pulse after RUN lands on beat 0 without a jump", t.phase());
    }

    {   // 10 minutes at 120 with +-1 sample clock jitter: no reversal, no jump, one wrap per loop
        Transport t = tpClocked();
        unsigned lcg = 12345u;
        int next = 0, k = 0;
        auto pulse = [&] (int i) -> bool
        {
            if (i != next) return false;
            lcg = lcg * 1664525u + 1013904223u;
            next = ++k * 24000 + (int) ((lcg >> 16) % 3u) - 1;
            return true;
        };
        const TpStats s = tpDrive (t, 1200 * 24000 + 12000, pulse);
        check (s.reversals == 0 && s.jumps == 0, "transport: 10 min +-1 sample jitter -> no reversal, no jump", s.reversals + s.jumps);
        check (s.wraps == 75 && std::abs (s.gapMin - 384000) <= 24 && std::abs (s.gapMax - 384000) <= 24,
               "transport: 10 min jitter -> 75 wraps, one per 384000 +- 24 ticks", s.gapMax - s.gapMin);
    }

    {   // defaults: no setSampleRate, knob 0 -> no NaN, bpm() never 0
        Transport t;
        t.setKnobBpm (0.f); t.setRunning (true);
        tpRun (t, 1000);
        check (t.bpm() > 0.f, "transport: bpm() never 0", t.bpm());
        check (t.phase() >= 0.0 && t.phase() < 1.0, "transport: default sample rate -> finite phase", t.phase());
    }
}
