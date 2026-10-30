// Transport.h: tempo (CLOCK median or BPM knob), bar phase over the B-bar loop, RUN, RESET and the swap point. No Rack dependency.
// Tempo: bpm() = 60 / median of the last (up to) four accepted pulse intervals (unpatched: the knob, clamped 40..240).
// An interval outside 40..240 BPM is dropped before it enters the ring. A too-long one (the clock stopped, then
// restarted) also makes the next pulse land on the nearest beat. Meanwhile the phase free-runs at the last rate.
// Phase rate: the newest accepted interval when it lies within 10 % of the median (follows ramps), else the median
// (ignores one-off glitches); after a jump the newest interval is trusted at once, so a tempo step costs one jump.
// Snapping: each pulse while running is the next quarter note (beat = beat + 1 mod 4B; beat 0 after a pending RESET;
// the nearest beat on the first pulse after the clock connects, after setBars(), after a RESET landed while stopped,
// and after a dropped too-long interval). On that pulse's tick the phase is pulled to beat / 4B: an error under 5 %
// of a beat is slewed out over one beat, a larger one jumps (jumped() is true on that tick).
// clockPulse() acts only while patched. Pulses while stopped only measure tempo; they never move the beat counter
// or the phase. RESET: unpatched and running -> at once; patched and running -> at the next pulse; stopped (or
// stopped before that pulse) -> on the next stopped tick; unpatching the clock lands a pending RESET at once.
// Landing a RESET is a jump but not a wrap. setSampleRate() clears the interval ring but keeps the tempo.
// Wrap: tick() is true when the phase crosses 1 going forward (advance or forward jump), once per loop: a backward
// jump across the loop end (a pulse over a beat late) un-reports that wrap, so the next forward crossing stays silent.
// Call order per sample: clockPulse() (on a rising edge) then tick(); phase() then reads that sample's position.
// Audio thread only: no allocation, no locks.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include <algorithm>
#include <cmath>

namespace recycler {

struct Transport
{
    void setSampleRate (float sr)
    {
        if (! (sr > 0.f) || sr == rate) return;
        rate = sr;
        count = pos = 0;   // intervals in samples are stale; the tempo in BPM is not
        heard = false;
    }
    void setBars (int bars)   // phase is kept; the next pulse lands on the nearest beat of the new loop
    {
        const int n = 4 * (bars > 1 ? bars : 1);
        if (n == nBeats) return;
        nBeats = n;
        beat %= nBeats;
        resync = true;
    }
    void setKnobBpm (float bpm) { knob = bpm >= 40.f ? (bpm <= 240.f ? bpm : 240.f) : 40.f; }   // NaN -> 40
    void setClockConnected (bool on)
    {
        if (on && ! clock) { count = pos = 0; heard = false; clockBpm = rateBpm = knob; resync = true; }
        if (! on && zeroPending) { zeroPending = false; jumpToZero(); }   // unpatched: a pending RESET lands now
        clock = on;
    }

    void clockPulse()
    {
        if (! clock) return;
        newInterval = false;
        if (heard) addInterval (sinceLast);
        heard = true;
        sinceLast = 0;
        if (! run) return;
        if (zeroPending) { zeroPending = false; jumpToZero(); resync = false; return; }
        if (resync) { resync = false; beat = (int) std::floor ((phi + inc()) * nBeats + 0.5) % nBeats; }
        else beat = (beat + 1) % nBeats;
        pulsed = true;
    }

    void reset()
    {
        if (clock || ! run) zeroPending = true;
        else jumpToZero();
    }

    void setRunning (bool on) { run = on; }

    bool tick()
    {
        if (sinceLast < (1 << 30)) ++sinceLast;
        const bool p = pulsed, h = hold;
        pulsed = hold = false;
        didJump = h;
        if (! run)
        {
            if (zeroPending) { zeroPending = false; jumpToZero(); hold = false; didJump = true; }
            return false;
        }
        if (h) return false;

        const double step = inc();
        double m = step;
        if (slewLeft > 0) { m += slewStep; --slewLeft; }
        if (p)
        {
            const double target = (double) beat / nBeats;
            double err = target - (phi + m);
            err -= std::floor (err + 0.5);                       // shortest way round the loop
            if (std::fabs (err) < 0.05 / nBeats)                 // under 5 % of a beat: slew over one beat
            {
                slewLeft = std::max (1, (int) (1.0 / (step * nBeats) + 0.5));
                slewStep = err / slewLeft;
            }
            else                                                 // jump
            {
                double d = target - phi;
                d -= std::floor (d + 0.5);
                bool wrapped = false;
                if (d > 0.0 && target < phi) wrapped = crossEnd();   // forward across the loop end
                else if (d < 0.0 && target > phi) unwrapped = true;  // backward across it: un-report the last wrap
                phi = target;
                slewLeft = 0;
                didJump = true;
                if (newInterval) rateBpm = newestBpm;                // the grid moved: trust the interval that moved it
                return wrapped;
            }
        }
        phi += std::max (m, 0.0);
        if (phi >= 1.0) { phi -= 1.0; return crossEnd(); }
        if (phi < 0.0) { phi += 1.0; unwrapped = true; }
        return false;
    }

    double phase() const { return phi; }
    float bpm() const { return clock ? clockBpm : knob; }
    bool running() const { return run; }
    bool jumped() const { return didJump; }   // the last tick moved the phase discontinuously (clock jump or RESET)

private:
    double phi = 0.0, slewStep = 0.0;
    float rate = 48000.f, knob = 120.f, clockBpm = 120.f, rateBpm = 120.f, newestBpm = 120.f;
    int nBeats = 16, beat = 0, slewLeft = 0, sinceLast = 0;
    int ring[4] = {};
    int pos = 0, count = 0;
    bool clock = false, run = false, heard = false, resync = true, zeroPending = false, pulsed = false, hold = false;
    bool unwrapped = false;   // a backward jump re-crossed the loop end: the next forward crossing is not a new wrap
    bool didJump = false, newInterval = false;

    double inc() const { return (clock ? rateBpm : knob) / 60.0 / nBeats / rate; }

    bool crossEnd()
    {
        if (! unwrapped) return true;
        unwrapped = false;
        return false;
    }

    // phase 0, beat 0; the next tick reports 0 instead of advancing. A pulse that lands it clears resync again.
    void jumpToZero() { phi = 0.0; beat = 0; slewLeft = 0; hold = true; unwrapped = false; resync = true; }

    void addInterval (int n)
    {
        if (n < 1) return;   // two pulses with no tick between them
        const double perMin = 60.0 * rate;
        if ((double) n * 40.0 > perMin) { resync = true; return; }   // too long: the clock stopped; dropped
        if ((double) n * 240.0 < perMin) return;                      // too short: dropped
        ring[pos] = n;
        pos = (pos + 1) % 4;
        if (count < 4) ++count;
        int s[4];
        for (int i = 0; i < count; ++i)
        {
            int j = i;
            for (; j > 0 && s[j - 1] > ring[i]; --j) s[j] = s[j - 1];
            s[j] = ring[i];
        }
        const double med = count % 2 ? s[count / 2] : 0.5 * (s[count / 2 - 1] + s[count / 2]);
        clockBpm = (float) (perMin / med);   // a median of in-range intervals is in range
        newestBpm = (float) (perMin / n);
        newInterval = true;
        rateBpm = std::fabs (n - med) <= 0.1 * med ? newestBpm : clockBpm;
    }
};

}
