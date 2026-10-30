// Analysis.h: one file's mono mix -> Info: frames, onsets, features, tempo, loop snap, key and roles at 22 050 Hz. No Rack dependency.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <string>
#include <vector>
#include "Audio.h"
#include "Fft.h"
#include "Info.h"

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

// Step 3 constants: the log-Gaussian tempo prior (centre, spread in octaves), the autocorrelation search band, the band
// candidates must stay in after octave expansion, the octave-variant score penalty, the dedupe tolerance, the shortest
// file with a tempo, the loop snap tolerance in bars, the octave factors (Schreiber, Urbano and Mueller 2020), the bar
// counts a loop may have (the last is the longest loop), and the acf smoothing / bump geometry in frames (lags).
constexpr double PRIOR_BPM = 120.0, PRIOR_OCTAVES = 1.4, ACF_LO_BPM = 60.0, ACF_HI_BPM = 200.0, CAND_LO_BPM = 30.0,
                 CAND_HI_BPM = 400.0, OCTAVE_PENALTY = 0.5, SAME_TEMPO = 0.02, MIN_TEMPO_SECONDS = 2.0, SNAP_BARS = 0.04;
constexpr double TEMPO_FACTORS[5] = { 1.0 / 3.0, 0.5, 1.0, 2.0, 3.0 };
constexpr int LOOP_BARS[8] = { 1, 2, 3, 4, 6, 8, 12, 16 };
constexpr double SMOOTH_SIGMA = 1.5;   // the Gaussian that smooths acf for peak picking
constexpr int SMOOTH_HALF = 4,         // that Gaussian's half-width
              BUMP_HALF = 4;           // lags either side of a peak that count as its bump

namespace detail
{
inline double prior (double bpm)
{
    const double o = std::log2 (bpm / PRIOR_BPM) / PRIOR_OCTAVES;
    return std::exp (-0.5 * o * o);
}
} // namespace detail

// Step 3, tempo in BPM (0 = none). x = flux minus its mean; acf(L) = sum x[i] x[i+L]. Peaks are positive local maxima of
// acf smoothed by a Gaussian (sigma 1.5 frames, +-4) over the lags of the 60-200 BPM band (L = 60 / BPM * RATE / HOP,
// 25..87 frames). Each peak's bump is the positive part of the raw acf over +-4 lags around it, recentred once on its centre of
// mass: that centre is the lag (the mean beat interval, so jitter averages out instead of moving an integer maximum) and
// its area is the strength (the pair count, so a beat lag outscores its double by (N-1)/(N-2) whatever the jitter).
// Score = area * prior(BPM), prior = exp(-0.5 (log2(BPM / 120) / 1.4)^2). The three best peaks are each tried at x1/3,
// x1/2, x1, x2, x3 (Schreiber, Urbano and Mueller 2020), kept within 30-400 BPM; a variant scores area * prior(its own
// BPM), halved unless x1. Peaks and candidates within 2 % of a better one are dropped; the rest go to `candidates`, best
// first, and the first is the tempo. conf = its bump area / zero-lag bump area (acf over -4..4, positive part), clamped to
// 0..1: the share of the flux's self-similarity that recurs one beat later (clean 4-bar clicks ~0.9, white noise ~0.01).
// Under 2 s of flux: 0, conf 0, no candidates. The "fewer than 4 onsets" rule needs the onsets, so the caller applies it.
inline float tempo (const std::vector<float>& flux, float& conf, std::vector<float>* candidates = nullptr)
{
    conf = 0.f;
    if (candidates) candidates->clear();
    const int n = (int) flux.size();
    if ((double) n * HOP < MIN_TEMPO_SECONDS * RATE) return 0.f;
    constexpr int SH = SMOOTH_HALF, BH = BUMP_HALF;
    const double perMinute = 60.0 * RATE / HOP;   // frames per minute: lag L <-> perMinute / L BPM
    const int lo = (int) std::floor (perMinute / ACF_HI_BPM), hi = (int) std::ceil (perMinute / ACF_LO_BPM);
    const int top = std::max (hi + 1 + SH, hi + 2 * BH);   // the longest lag smoothing or a bump reads (< 2 s of frames)
    const double m = detail::mean (flux);
    std::vector<double> x (n), acf (top + 1, 0.0), s (hi + 2, 0.0);
    for (int i = 0; i < n; ++i) x[i] = flux[i] - m;
    for (int L = 0; L <= top; ++L)   // 0..BH for the zero-lag bump, the rest for the band
        for (int i = 0; i + L < n; ++i) acf[L] += x[i] * x[i + L];
    double g[2 * SH + 1], gSum = 0;
    for (int j = -SH; j <= SH; ++j) gSum += g[j + SH] = std::exp (-0.5 * j * j / (SMOOTH_SIGMA * SMOOTH_SIGMA));
    for (int L = lo - 1; L <= hi + 1; ++L)
        for (int j = -SH; j <= SH; ++j) s[L] += g[j + SH] / gSum * acf[L + j];
    struct Bump { double area, centre; };
    auto bump = [&] (int c) {   // area and centre of the positive part of the raw acf over c +- BH
        Bump b { 0.0, (double) c };
        double wl = 0;
        for (int j = c - BH; j <= c + BH; ++j)
            if (acf[j] > 0) { b.area += acf[j]; wl += acf[j] * j; }
        if (b.area > 0) b.centre = wl / b.area;
        return b;
    };

    struct Peak { double bpm, area, score; };
    // appends p unless `list` already holds one within SAME_TEMPO of it; fed best-first, so the better one stays
    auto keep = [] (std::vector<Peak>& list, const Peak& p) {
        for (const Peak& q : list)
            if (std::fabs (p.bpm - q.bpm) < SAME_TEMPO * q.bpm) return;
        list.push_back (p);
    };
    std::vector<Peak> found, peaks;
    for (int L = lo; L <= hi; ++L)
    {
        if (! (s[L] > 0 && s[L] > s[L - 1] && s[L] >= s[L + 1])) continue;
        const int at = std::max (lo - BH, std::min (hi + BH, (int) std::lround (bump (L).centre)));   // recentre once
        const Bump b = bump (at);
        const double bpm = perMinute / b.centre;
        if (bpm >= ACF_LO_BPM && bpm <= ACF_HI_BPM) found.push_back ({ bpm, b.area, b.area * detail::prior (bpm) });
    }
    std::stable_sort (found.begin(), found.end(), [] (const Peak& a, const Peak& b) { return a.score > b.score; });
    for (const Peak& p : found)
        if (peaks.size() < 3) keep (peaks, p);
    if (peaks.empty()) return 0.f;

    std::vector<Peak> all, kept;
    for (const Peak& p : peaks)
        for (double k : TEMPO_FACTORS)
        {
            const double bpm = p.bpm * k;
            if (bpm >= CAND_LO_BPM && bpm <= CAND_HI_BPM)
                all.push_back ({ bpm, p.area, p.area * detail::prior (bpm) * (k == 1.0 ? 1.0 : OCTAVE_PENALTY) });
        }
    std::stable_sort (all.begin(), all.end(), [] (const Peak& a, const Peak& b) { return a.score > b.score; });
    for (const Peak& c : all) keep (kept, c);
    double zero = std::max (0.0, acf[0]);   // the zero-lag bump over -BH..BH; acf is even
    for (int j = 1; j <= BH; ++j) zero += 2 * std::max (0.0, acf[j]);
    conf = zero > 0 ? (float) std::min (1.0, kept[0].area / zero) : 0.f;
    if (candidates)
        for (const Peak& c : kept) candidates->push_back ((float) c.bpm);
    return (float) kept[0].bpm;
}

// Step 4, loop snap: candidate T spans bars = seconds * T / 240. A file longer than the longest loop at the first
// candidate's tempo (over 16 + 0.04 bars) is no loop: otherwise a 48-bar file would snap to "16 bars at a third of its
// tempo". Else the first candidate in list order (best score first, so the prior already favours tempi near 120) with
// |bars - round(bars)| < 0.04 and round(bars) in LOOP_BARS makes the file a loop: returns those bars and tempoOut =
// 240 * bars / seconds (the file length is the better clock). Otherwise 0 and tempoOut = the first candidate (0 when
// there is none).
inline int loopSnap (float seconds, const std::vector<float>& candidates, float& tempoOut)
{
    tempoOut = candidates.empty() ? 0.f : candidates[0];
    if (! (seconds > 0.f) || candidates.empty()) return 0;
    if ((double) seconds * candidates[0] / 240.0 > LOOP_BARS[sizeof LOOP_BARS / sizeof LOOP_BARS[0] - 1] + SNAP_BARS) return 0;
    for (float t : candidates)
    {
        const double bars = (double) seconds * t / 240.0;
        const long whole = std::lround (bars);
        if (std::fabs (bars - (double) whole) >= SNAP_BARS) continue;
        for (int ok : LOOP_BARS)
            if (whole == ok)
            {
                tempoOut = (float) (240.0 * (double) whole / seconds);
                return (int) whole;
            }
    }
    return 0;
}

// A tempo tag in a file name: 2 or 3 digits, then at most one ' ', '-' or '_', then "bpm" in any case ("120bpm",
// "90 BPM", "128-bpm", "140_bpm"), the number in 30..300 and not part of a longer digit run. A bare number is no tag.
// The first tag found wins; `bpm` is left untouched when there is none.
inline bool tempoTag (const std::string& fileName, float& bpm)
{
    auto digit = [] (char c) { return c >= '0' && c <= '9'; };
    auto lower = [] (char c) { return c >= 'A' && c <= 'Z' ? (char) (c - 'A' + 'a') : c; };
    const int n = (int) fileName.size();
    for (int i = 0; i + 3 <= n; ++i)
    {
        if (lower (fileName[i]) != 'b' || lower (fileName[i + 1]) != 'p' || lower (fileName[i + 2]) != 'm') continue;
        int end = i;   // one past the number's last digit
        if (end > 0 && (fileName[end - 1] == ' ' || fileName[end - 1] == '-' || fileName[end - 1] == '_')) --end;
        int start = end, value = 0;
        while (start > 0 && digit (fileName[start - 1])) --start;
        if (end - start < 2 || end - start > 3) continue;
        for (int k = start; k < end; ++k) value = value * 10 + (fileName[k] - '0');
        if (value < 30 || value > 300) continue;
        bpm = (float) value;
        return true;
    }
    return false;
}

// Step 5 key profiles, [major, minor], tonic first: Temperley (the default) and Krumhansl-Kessler (kept for comparison).
constexpr float TEMPERLEY[2][12] = { { 5.0f, 2.0f, 3.5f, 2.0f, 4.5f, 4.0f, 2.0f, 4.5f, 2.0f, 3.5f, 1.5f, 4.0f },
                                     { 5.0f, 2.0f, 3.5f, 4.5f, 2.0f, 4.0f, 2.0f, 4.5f, 3.5f, 2.0f, 1.5f, 4.0f } };
constexpr float KRUMHANSL[2][12] = { { 6.35f, 2.23f, 3.48f, 2.33f, 4.38f, 4.09f, 2.52f, 5.19f, 2.39f, 3.66f, 2.29f, 2.88f },
                                     { 6.33f, 2.68f, 3.52f, 5.38f, 2.60f, 3.53f, 2.54f, 4.75f, 3.98f, 2.69f, 3.34f, 3.17f } };
// Step 5 constants: the chroma band, the flatness above which a file is atonal, the weakest correlation that is a key,
// and the keyConf a file-name key tag gets when it overrides a weak detection.
constexpr double CHROMA_LO_HZ = 55.0, CHROMA_HI_HZ = 2000.0, ATONAL_FLATNESS = 0.6, MIN_KEY_R = 0.3, WEAK_KEY = 0.5,
                 PEAK_FLOOR = 0.03;   // spectral peaks below 0.03 x (-30 dB) the frame's loudest are leakage, not notes
constexpr float TAG_KEY_CONF = 0.6f;

// Step 5, key. Chroma: in every frame, each spectral peak in 55..2000 Hz (a local maximum within 30 dB of the frame's
// loudest bin there) adds its |X| to pitch class (round(12 log2(f / 440)) + 69) mod 12, f = its parabola-refined
// frequency; the 12 sums are normalised to sum 1. Peaks, not bins: bins are 21.5 Hz apart, wider than a semitone below
// ~370 Hz, so a bin's own frequency puts Eb4 into D or E. Linear |X|, not log: log lifts the upper partials of a saw to
// the fundamental's level and a C bass line reads as G. Pearson r against the 24 rotations of `profiles`; key (0 = C)
// and minor = the best, conf = r_best clamped to 0..1 (how strongly the chroma is a key; the r_best - r_second margin
// stays near 0 on any triad or pentatonic line, since neighbouring keys share most notes). key -1, conf 0 when flatness
// > 0.6 (noise), r_best < 0.3, or the band holds no peak.
inline void key (const Frames& f, float flatness, int& keyOut, bool& minor, float& conf, const float (*profiles)[12] = TEMPERLEY)
{
    keyOut = -1;
    minor = false;
    conf = 0.f;
    if (flatness > ATONAL_FLATNESS) return;
    const int lo = (int) std::ceil (CHROMA_LO_HZ * WIN / RATE), hi = (int) std::floor (CHROMA_HI_HZ * WIN / RATE);
    double chroma[12] = {}, sum = 0;
    for (int i = 0; i < f.count; ++i)
    {
        float top = 0.f;
        for (int b = lo; b <= hi; ++b) top = std::max (top, f.at (i, b));
        const float peakFloor = (float) std::log1p (std::expm1 ((double) top) * PEAK_FLOOR);   // PEAK_FLOOR x the loudest |X|
        for (int b = lo; b <= hi; ++b)
        {
            const float l = f.at (i, b - 1), m = f.at (i, b), r = f.at (i, b + 1);
            if (! (m > l && m >= r && m > peakFloor)) continue;
            const double curve = l - 2.0 * m + r, d = curve < 0 ? 0.5 * (l - r) / curve : 0.0;
            const double hz = (b + d) * RATE / WIN;
            const int pc = (int) ((std::lround (12.0 * std::log2 (hz / 440.0)) + 69) % 12 + 12) % 12;
            chroma[pc] += std::expm1 ((double) m) / 10.0;   // |X|
        }
    }
    for (double v : chroma) sum += v;
    if (! (sum > 0)) return;
    for (double& v : chroma) v /= sum;
    const double cMean = 1.0 / 12.0;
    double best = -2;
    for (int mode = 0; mode < 2; ++mode)
    {
        double pMean = 0;
        for (int i = 0; i < 12; ++i) pMean += profiles[mode][i] / 12.0;
        for (int tonic = 0; tonic < 12; ++tonic)
        {
            double sxy = 0, sxx = 0, syy = 0;
            for (int pc = 0; pc < 12; ++pc)
            {
                const double x = chroma[pc] - cMean, y = profiles[mode][(pc - tonic + 12) % 12] - pMean;
                sxy += x * y;
                sxx += x * x;
                syy += y * y;
            }
            const double r = sxx > 1e-12 && syy > 0 ? sxy / std::sqrt (sxx * syy) : 0.0;
            if (r > best)
            {
                best = r;
                keyOut = tonic;
                minor = mode == 1;
            }
        }
    }
    if (best < MIN_KEY_R)
    {
        keyOut = -1;
        minor = false;
        return;
    }
    conf = (float) std::min (1.0, best);
}

// A key tag in a file name: an upper-case note letter A-G on a word boundary (not after a letter or digit), an optional
// '#' or 'b', then a quality word not followed by a letter: "min", "minor" (minor) or "maj", "major" (major) in any case
// after at most one space, or a lower-case "m" (minor) attached to the note. "Cmin", "C#maj", "Am", "F#m", "Dbmajor",
// "Gminor", "A minor", "Bb min" are tags; "Amen", "Drums", "AM", "A m", "DM me", "10 AM", a bare "C" and a lower-case
// "cmin" are not. key 0 = C. The first tag found wins.
inline bool keyTag (const std::string& fileName, int& key, bool& minor)
{
    static const int natural[7] = { 9, 11, 0, 2, 4, 5, 7 };   // A B C D E F G
    auto letter = [] (char c) { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z'); };
    auto alnum = [&] (char c) { return letter (c) || (c >= '0' && c <= '9'); };
    auto lower = [] (char c) { return c >= 'A' && c <= 'Z' ? (char) (c - 'A' + 'a') : c; };
    const int n = (int) fileName.size();
    auto wordAt = [&] (int at, const char* w) {   // w (lower case) at `at`, case-insensitive, not followed by a letter
        int k = 0;
        for (; w[k]; ++k)
            if (at + k >= n || lower (fileName[at + k]) != w[k]) return 0;
        return at + k < n && letter (fileName[at + k]) ? 0 : k;
    };
    for (int i = 0; i < n; ++i)
    {
        const char c = fileName[i];
        if (c < 'A' || c > 'G' || (i > 0 && alnum (fileName[i - 1]))) continue;
        int at = i + 1, pc = natural[c - 'A'];
        if (at < n && (fileName[at] == '#' || fileName[at] == 'b'))
        {
            pc += fileName[at] == '#' ? 1 : -1;
            ++at;
        }
        if (at < n && fileName[at] == 'm' && (at + 1 >= n || ! letter (fileName[at + 1])))   // "Am": lower case, attached
        {
            key = (pc + 12) % 12;
            minor = true;
            return true;
        }
        if (at < n && fileName[at] == ' ') ++at;
        static const char* words[4] = { "minor", "major", "min", "maj" };
        for (const char* w : words)
            if (wordAt (at, w))
            {
                key = (pc + 12) % 12;
                minor = w[1] == 'i';
                return true;
            }
    }
    return false;
}

// Step 6 tonalness for the role formulas: keyConf (a raw correlation) mapped so r 0.35 -> 0 and r 0.75 -> 1, clamped;
// 0 when atonal. A drum loop's tonal kick correlates ~0.4 with some key; unmapped, that would halve its drums score.
constexpr double TONAL_FROM = 0.35, TONAL_SPAN = 0.4;
inline float tonalness (int key, float keyConf)
{
    return key < 0 ? 0.f : (float) std::max (0.0, std::min (1.0, (keyConf - TONAL_FROM) / TONAL_SPAN));
}

// Step 6, role scores from the five features; s(x) = 1 / (1 + e^-x), t = tonalness. Not normalised across roles. Drums
// = density (centred at 1.5 onsets/s: 8th-note hats at 100 BPM, 3.3/s, give 0.97) x percussiveness (1 - sustain, the
// share of frames more than 20 dB under the loudest). Not (1 - t): a pitched 55 Hz kick makes a drum loop correlate
// 0.65-0.75 with some key, and (1 - t) scored such loops 0.00-0.23. Sustain splits the fixtures cleanly (drums 0.15-0.23,
// every bass, lead and pad >= 0.98).
inline void roles (const Features& ft, float role[4])
{
    auto s = [] (double x) { return 1.0 / (1.0 + std::exp (-x)); };
    const double d = ft.onsetDensity, t = ft.tonalness, b = ft.lowShare, c = ft.centroid, u = ft.sustain;
    role[DRUMS] = (float) (s (2 * (d - 1.5)) * (1 - u));
    role[BASS] = (float) (t * s (10 * (b - 0.35)) * (c < 400 ? 1.0 : 0.2));
    role[MELODY] = (float) (t * (1 - b) * (c >= 300 && c <= 4000 ? 1.0 : 0.3) * s (d - 0.5));
    role[TEXTURE] = (float) (u * (1 - s (d - 2)) * 0.5 + (1 - t) * (1 - s (d - 1)) * 0.5);
}

// Step 7, the whole analysis of one file's mono mix at its own rate. The first capSeconds (all of it when <= 0) are DC-
// removed (mean of that span), resampled to RATE and analysed: onsets, features, tempo, key and roles. A tempo tag in
// fileName replaces the candidates with the one within 2 % of it (else the tag value) at conf 1; loopSnap then uses the
// FULL length as the clock. Under 4 onsets with no tag: tempo, bars, conf 0. A key tag replaces a detected key with
// keyConf < 0.5 and sets keyConf 0.6. Features::tonalness = tonalness(key, keyConf). rms and peak are dBFS over the analysed span
// (-99 for silence). Empty input or a silent span (rms -99) leaves all four roles 0. seconds, frames and sampleRate
// describe the full input; path, size and mtime are the caller's.
inline Info analyse (const std::vector<float>& mono, int sampleRate, float capSeconds, const std::string& fileName = "")
{
    Info info;
    info.sampleRate = sampleRate;
    info.frames = (int64_t) mono.size();
    info.seconds = sampleRate > 0 ? (float) ((double) mono.size() / sampleRate) : 0.f;
    if (mono.empty() || sampleRate <= 0) return info;
    size_t span = mono.size();
    if (capSeconds > 0.f) span = std::min (span, (size_t) std::llround ((double) capSeconds * sampleRate));
    std::vector<float> x (mono.begin(), mono.begin() + span);
    const float dc = (float) detail::mean (x);
    double energy = 0, top = 0;
    for (float& v : x)
    {
        v -= dc;
        energy += (double) v * v;
        top = std::max (top, (double) std::fabs (v));
    }
    auto dB = [] (double a) { return a > 0 ? (float) std::max (-99.0, 20.0 * std::log10 (a)) : -99.f; };
    info.rms = dB (std::sqrt (energy / (double) span));
    info.peak = dB (top);

    const std::vector<float> x22 = audio::resample (x, sampleRate, RATE);
    const Frames f = frames (x22);
    const std::vector<float> flux = odf (f);
    info.onsets = onsets (flux, x22, info.bestOnset);
    Features ft = features (f, info.onsets, (float) ((double) x22.size() / RATE));

    std::vector<float> cand;
    info.tempo = tempo (flux, info.tempoConf, &cand);
    float tagBpm = 0.f;
    const bool tagged = tempoTag (fileName, tagBpm);
    if (tagged)
    {
        float pick = tagBpm;
        for (float c : cand)
            if (std::fabs (c - tagBpm) < SAME_TEMPO * tagBpm) { pick = c; break; }
        cand.assign (1, pick);
        info.tempoConf = 1.f;
    }
    info.bars = loopSnap (info.seconds, cand, info.tempo);
    if (info.onsets.size() < 4 && ! tagged)
    {
        info.tempo = info.tempoConf = 0.f;
        info.bars = 0;
    }

    key (f, ft.flatness, info.key, info.minor, info.keyConf);
    int tagKey = -1;
    bool tagMinor = false;
    if (info.keyConf < WEAK_KEY && keyTag (fileName, tagKey, tagMinor))
    {
        info.key = tagKey;
        info.minor = tagMinor;
        info.keyConf = TAG_KEY_CONF;
    }
    ft.tonalness = tonalness (info.key, info.keyConf);
    if (info.rms > -99.f) roles (ft, info.role);   // a silent span plays no role
    return info;
}
} // namespace analysis
} // namespace recycler
