// Analysis.h: pure spectral frames, onsets and role features from a mono mix already at 22 050 Hz. No Rack dependency.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include <algorithm>
#include <cmath>
#include <complex>
#include <vector>
#include "Fft.h"

namespace recycler
{
namespace analysis
{
constexpr int RATE = 22050, WIN = 1024, HOP = 256, BINS = WIN / 2 + 1;

// Log-compressed magnitude spectra, frame-major: count x BINS values of log(1 + 10|X|). samples = the input length.
struct Frames
{
    int count = 0;
    size_t samples = 0;
    std::vector<float> mag;
    float& at (int f, int b) { return mag[(size_t) f * BINS + b]; }
    float at (int f, int b) const { return mag[(size_t) f * BINS + b]; }
};

namespace detail
{
inline double mean (const std::vector<float>& x)
{
    double s = 0;
    for (float v : x) s += v;
    return x.empty() ? 0.0 : s / (double) x.size();
}

// Sum of v[i] over |i - c| <= half for every c, divided by the window length actually inside the signal.
inline std::vector<double> movingMean (const std::vector<float>& v, int half)
{
    const int n = (int) v.size();
    std::vector<double> sum (n + 1, 0.0), out (n, 0.0);
    for (int i = 0; i < n; ++i) sum[i + 1] = sum[i] + v[i];
    for (int c = 0; c < n; ++c)
    {
        const int lo = std::max (0, c - half), hi = std::min (n, c + half + 1);
        out[c] = (sum[hi] - sum[lo]) / (hi - lo);
    }
    return out;
}

// Onset sample in [lo, hi] from a 2 ms RMS envelope (centred window) of the DC-removed signal: the FIRST sample whose
// rise is at least half the largest rise in the range, so a kick over a sustained bed is cut where it starts, not at a
// later, louder cycle. A centred window starts rising ~1 ms before the hit, so the cut lands just ahead of the
// transient. `fallback` when nothing rises.
inline int steepestRise (const std::vector<float>& x, double dc, int lo, int hi, int fallback)
{
    const int n = (int) x.size(), half = (int) (0.001 * RATE);   // 22 samples each side
    lo = std::max (lo, 0);
    hi = std::min (hi, n - 1);
    if (lo > hi) return std::min (std::max (fallback, 0), std::max (n - 1, 0));
    auto sq = [&] (int i) { return i >= 0 && i < n ? (x[i] - dc) * (x[i] - dc) : 0.0; };
    double e = 0;
    for (int i = lo - 1 - half; i < lo - 1 + half; ++i) e += sq (i);   // energy of the window centred on lo - 1
    double prev = std::sqrt (e / (2 * half)), best = 0;
    std::vector<double> rise (hi - lo + 1);
    for (int s = lo; s <= hi; ++s)
    {
        e += sq (s + half - 1) - sq (s - 1 - half);
        const double r = std::sqrt (std::max (0.0, e) / (2 * half));
        rise[s - lo] = r - prev;
        best = std::max (best, r - prev);
        prev = r;
    }
    if (best > 0)
        for (int s = lo; s <= hi; ++s)
            if (rise[s - lo] >= 0.5 * best) return s;
    return std::min (std::max (fallback, lo), hi);
}
} // namespace detail

// Steps 0 + 1. Step 0 ("subtract the mean before anything else") lives here and in onsets(), the two functions that read
// samples, so callers hand in the plain mono mix. Frame f stands for time f*HOP/RATE. Its Hann window covers samples
// [f*HOP - 3*WIN/4, f*HOP + WIN/4), zero-padded at both ends: a transient's flux peaks as it crosses the window's leading
// quarter, so onset times read straight off the frame index (centred windows would report every onset ~10-20 ms late).
// count = ceil(len / HOP).
inline Frames frames (const std::vector<float>& mono22k)
{
    const int n = (int) mono22k.size();
    const double dc = detail::mean (mono22k);
    Frames out;
    out.count = (n + HOP - 1) / HOP;
    out.samples = mono22k.size();
    out.mag.assign ((size_t) out.count * BINS, 0.f);
    std::vector<double> hann (WIN);
    for (int i = 0; i < WIN; ++i) hann[i] = 0.5 - 0.5 * std::cos (2.0 * 3.14159265358979323846 * i / WIN);
    std::vector<std::complex<double>> buf (WIN);
    for (int f = 0; f < out.count; ++f)
    {
        const int start = f * HOP - 3 * WIN / 4;
        for (int i = 0; i < WIN; ++i)
        {
            const int s = start + i;
            buf[i] = std::complex<double> (s >= 0 && s < n ? (mono22k[s] - dc) * hann[i] : 0.0, 0.0);
        }
        fft (buf);
        for (int b = 0; b < BINS; ++b) out.at (f, b) = (float) std::log1p (10.0 * std::abs (buf[b]));
    }
    return out;
}

// Step 2, raw SuperFlux-style ODF: per bin b >= 1, max(0, mag[f][b] - max(mag[f-1][b-2..b+2])), summed (frame -1 is
// silence). The +-2-bin max on the previous frame ignores vibrato and beating. Frames whose window runs past the end of
// the signal get 0, so a file that ends loud has no ghost onset. No mean removal: the tempo step does its own.
inline std::vector<float> odf (const Frames& f)
{
    std::vector<float> flux (f.count, 0.f);
    for (int i = 0; i < f.count; ++i)
    {
        if ((size_t) (i * HOP + WIN / 4) > f.samples) continue;
        double s = 0;
        for (int b = 1; b < BINS; ++b)
        {
            float prev = 0.f;
            if (i > 0)
                for (int k = std::max (0, b - 2); k <= std::min (BINS - 1, b + 2); ++k) prev = std::max (prev, f.at (i - 1, k));
            s += std::max (0.f, f.at (i, b) - prev);
        }
        flux[i] = (float) s;
    }
    return flux;
}

// Onsets in seconds. A frame is an onset when it is the maximum over +-3 frames and beats all of: 2x the local mean of
// the flux over +-0.5 s, 0.1x the global reference, and 2.0 (silence ripple). The global reference is the flux maximum
// over frames whose previous frame is not silent (its windowed energy within 60 dB of the loudest frame's): a frame
// measured against silence (the file start, or a hit after a gap longer than the window) reads the whole spectrum as
// flux and would set the bar far above every later attack. Such frames can still be onsets; they just don't set the
// bar. The +-3-frame maximum keeps onsets >= 4 frames (46 ms) apart, so the 30 ms minimum gap holds by construction.
// Each time starts at t0 = frame time - HOP/2 and is refined by detail::steepestRise within [t0 - HOP, t0 + HOP]: the
// flux peak lands up to ~140 samples either side of the hit, so a narrower window can miss it. bestSec = time of the
// highest-flux onset, 0 when there is none.
inline std::vector<float> onsets (const std::vector<float>& flux, const std::vector<float>& mono22k, float& bestSec)
{
    const int n = (int) flux.size();
    const std::vector<double> local = detail::movingMean (flux, (int) (0.5 * RATE / HOP));
    const double dc = detail::mean (mono22k);
    std::vector<double> energy (n, 0.0), hann (WIN);   // Hann-windowed energy of each frame's span, as frames() sees it
    for (int i = 0; i < WIN; ++i) hann[i] = 0.5 - 0.5 * std::cos (2.0 * 3.14159265358979323846 * i / WIN);
    for (int f = 0; f < n; ++f)
        for (int i = 0, start = f * HOP - 3 * WIN / 4; i < WIN; ++i)
        {
            const int s = start + i;
            if (s < 0 || s >= (int) mono22k.size()) continue;
            const double v = (mono22k[s] - dc) * hann[i];
            energy[f] += v * v;
        }
    const double loudest = n ? *std::max_element (energy.begin(), energy.end()) : 0.0;
    float top = 0.f;
    for (int f = 1; f < n; ++f)
        if (energy[f - 1] > 0.0 && energy[f - 1] >= loudest * 1e-6) top = std::max (top, flux[f]);
    std::vector<int> peaks;
    for (int i = 0; i < n; ++i)
    {
        const float v = flux[i];
        if (! (v > 2.0 * local[i] && v > 0.1f * top && v > 2.f)) continue;
        bool isMax = true;
        for (int j = std::max (0, i - 3); j <= std::min (n - 1, i + 3) && isMax; ++j)
            isMax = j < i ? v > flux[j] : v >= flux[j];   // a plateau counts once, at its first frame
        if (isMax) peaks.push_back (i);   // no 30 ms merge needed: two +-3-frame maxima are >= 4 frames apart
    }
    std::vector<float> out;
    bestSec = 0.f;
    float best = 0.f;
    for (int i : peaks)
    {
        const int t0 = i * HOP - HOP / 2;
        out.push_back ((float) detail::steepestRise (mono22k, dc, t0 - HOP, t0 + HOP, t0) / RATE);
        if (flux[i] > best) { best = flux[i]; bestSec = out.back(); }
    }
    return out;
}

struct Features { float onsetDensity = 0, tonalness = 0, lowShare = 0, centroid = 0, sustain = 0, flatness = 0; };

// Linear power is recovered exactly from the stored magnitudes (|X| = (e^m - 1) / 10), so Frames stays the only spectrum.
// Every spectral feature skips bin 0 (DC). lowShare and centroid are taken over all frames' power; sustain = fraction of
// frames within 20 dB of the loudest frame. flatness = mean, over frames within 60 dB of the loudest (a dithered tail must
// not read as noise), of geometric / arithmetic mean of the per-bin magnitude |X| (the square root of the power): on
// power, white noise would only reach e^-0.577 = 0.56, below the 0.6 "flat" line the key step uses.
// tonalness stays 0 here; the key step fills it.
inline Features features (const Frames& f, const std::vector<float>& onsetsSec, float seconds)
{
    const int lowBins = (int) std::ceil (200.0 * WIN / RATE);   // bins 1..9 lie below 200 Hz
    Features x;
    x.onsetDensity = seconds > 0.f ? (float) onsetsSec.size() / seconds : 0.f;
    std::vector<double> energy (f.count, 0.0), frameFlat (f.count, 0.0);
    double total = 0, low = 0, weighted = 0;
    for (int i = 0; i < f.count; ++i)
    {
        double logSum = 0, magSum = 0;
        for (int b = 1; b < BINS; ++b)
        {
            const double a = std::expm1 ((double) f.at (i, b)) / 10.0, p = a * a;
            energy[i] += p;
            if (b < lowBins) low += p;
            weighted += p * b * RATE / WIN;
            logSum += std::log (a + 1e-12);
            magSum += a;
        }
        total += energy[i];
        if (magSum > 0) frameFlat[i] = std::exp (logSum / (BINS - 1)) / (magSum / (BINS - 1));
    }
    if (total > 0)
    {
        x.lowShare = (float) (low / total);
        x.centroid = (float) (weighted / total);
        const double loudest = *std::max_element (energy.begin(), energy.end());
        double flat = 0;
        int counted = 0, sustained = 0;
        for (int i = 0; i < f.count; ++i)
        {
            if (energy[i] >= loudest * 0.01) ++sustained;
            if (energy[i] >= loudest * 1e-6) { flat += frameFlat[i]; ++counted; }
        }
        x.sustain = (float) sustained / f.count;
        x.flatness = (float) std::min (1.0, flat / counted);
    }
    return x;
}
} // namespace analysis
} // namespace recycler
