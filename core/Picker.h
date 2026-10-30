// Picker.h: chooses a file, octave and semitone shift per role slot for a target tempo/key, loosened by chaos. No Rack dependency.
// role indices (0..3) and Info::role[] scores are trusted: the scanner produces them finite and in range; nothing here checks.
// A re-roll with no alternative to currentFile returns file -1; the module keeps the current file in that case.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include "Info.h"
#include "Library.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <utility>
#include <vector>

namespace recycler { namespace picker {

struct Target { float bpm = 120.f; int root = 0; bool minor = true; int bars = 4; float chaos = 0.25f; };
struct Choice { int file = -1; int k = 0; int s = 0; };     // index into Library::files, octave, semitone shift

// xorshift64*
struct Rng
{
    uint64_t state;
    explicit Rng (uint64_t seed) : state (seed ? seed : 0x9E3779B97F4A7C15ULL) {}
    uint32_t next()
    {
        state ^= state >> 12; state ^= state << 25; state ^= state >> 27;
        return (uint32_t) ((state * 0x2545F4914F6CDD1DULL) >> 32);
    }
    float uniform() { return (float) (next() >> 8) * (1.f / 16777216.f); }   // 24 bits: exact in float, < 1
};

// the last 8 picks per role
struct History
{
    std::vector<int> recent[4];
    void push (int role, int file)
    {
        recent[role].push_back (file);
        if (recent[role].size() > 8) recent[role].erase (recent[role].begin());
    }
    bool seen (int role, int file) const
    {
        return std::find (recent[role].begin(), recent[role].end(), file) != recent[role].end();
    }
};

namespace detail {
inline float lerp (float a, float b, float c) { return a + (b - a) * c; }
inline float chaosOf (const Target& t) { return std::min (1.f, std::max (0.f, t.chaos)); }
inline bool usable (const Info& i, int role) { return i.tempo > 0.f || (role == TEXTURE && i.tempo == 0.f); }
// score desc, index asc
inline bool better (const std::pair<float, int>& a, const std::pair<float, int>& b)
{
    return a.first > b.first || (a.first == b.first && a.second < b.second);
}
} // namespace detail

// k in -1..1 minimising cost = |log2(bpm / (fileTempo * 2^k))|; ties prefer k = 0.
// bpm <= 0: k 0, cost 1e9 (nothing fits). fileTempo <= 0 (plays at native speed): k 0, cost 0.
inline int octaveFor (float fileTempo, float bpm, float& cost)
{
    cost = 0.f;
    if (bpm <= 0.f) { cost = 1e9f; return 0; }
    if (fileTempo <= 0.f) return 0;
    const float base = std::log2 (bpm / fileTempo);
    int best = 0; cost = std::fabs (base);
    for (int k = -1; k <= 1; k += 2)
    {
        const float e = std::fabs (base - (float) k);
        if (e < cost) { cost = e; best = k; }
    }
    return best;
}

// semitones from the file's key to the target key in -6..5, compared on the major side (relative keys equal); 0 when atonal
inline int shiftFor (int fileKey, bool fileMinor, int root, bool minor)
{
    if (fileKey < 0) return 0;
    const int fileMajor = fileMinor ? (fileKey + 3) % 12 : fileKey % 12;
    const int targetMajor = minor ? (root + 3) % 12 : root % 12;
    const int d = ((targetMajor - fileMajor) % 12 + 12) % 12;
    return d >= 6 ? d - 12 : d;
}

// role[j] * tempoFit * keyFit * novelty; 0 when excluded. Does not apply the chaos > 0.8 drum randomisation (pickOne does).
// index: the file's index in the library, for the novelty lookup in h; -1 (unknown) counts as fresh.
inline float score (const Info& i, int role, const Target& t, const History& h, int& k, int& s, int index = -1)
{
    k = 0; s = 0;
    if (! detail::usable (i, role)) return 0.f;
    const float c = detail::chaosOf (t);

    float tempoFit = 0.5f;
    if (i.tempo > 0.f)
    {
        float e = 0.f;
        k = octaveFor (i.tempo, t.bpm, e);
        const float eMax = detail::lerp (0.11f, 1.f, c);
        if (e > eMax) return 0.f;
        tempoFit = std::exp (-(e / eMax) * (e / eMax));
    }

    float keyFit = 1.f;
    if (role != DRUMS)
    {
        if (i.key < 0) keyFit = 0.5f;
        else
        {
            s = shiftFor (i.key, i.minor, t.root, t.minor);
            const int shiftMax = (int) std::lround (detail::lerp (2.f, 6.f, c));
            if (std::abs (s) > shiftMax) return 0.f;
            const float r = (float) s / (float) shiftMax;
            keyFit = std::exp (-r * r);
        }
    }

    const float novelty = index >= 0 && h.seen (role, index) ? 0.2f : 1.f;
    return i.role[role] * tempoFit * keyFit * novelty;
}

inline Choice pickOne (const library::Library& lib, int role, const Target& t, int currentFile, const History& h, Rng& rng)
{
    const float c = detail::chaosOf (t);
    const float threshold = detail::lerp (0.6f, 0.f, c);
    const int n = (int) lib.files.size();
    std::vector<std::pair<float, int> > pool;      // (score, index)
    int k = 0, s = 0;

    for (int i = 0; i < n; ++i)
    {
        if (i == currentFile || lib.files[i].role[role] < threshold) continue;
        const float sc = score (lib.files[i], role, t, h, k, s, i);
        if (sc > 0.f) pool.push_back (std::make_pair (sc, i));
    }

    if (pool.empty())    // fall back to the five best role[j] files
    {
        std::vector<std::pair<float, int> > best;
        for (int i = 0; i < n; ++i)
            if (i != currentFile && detail::usable (lib.files[i], role)) best.push_back (std::make_pair (lib.files[i].role[role], i));
        const size_t five = std::min<size_t> (5, best.size());
        std::partial_sort (best.begin(), best.begin() + five, best.end(), detail::better);
        for (size_t b = 0; b < five; ++b)
        {
            const float sc = score (lib.files[best[b].second], role, t, h, k, s, best[b].second);
            if (sc > 0.f) pool.push_back (std::make_pair (sc, best[b].second));
        }
    }

    Choice out;
    if (pool.empty()) return out;

    const size_t top = std::min<size_t> (16, pool.size());
    std::partial_sort (pool.begin(), pool.begin() + top, pool.end(), detail::better);

    // softmax(score / tau) over the top scores; pool[0] holds the max
    const double tau = detail::lerp (0.15f, 1.f, c);
    double w[16], sum = 0.0;
    for (size_t i = 0; i < top; ++i) { w[i] = std::exp ((pool[i].first - pool[0].first) / tau); sum += w[i]; }
    double u = rng.uniform() * sum;
    size_t pick = top - 1;
    for (size_t i = 0; i < top; ++i)
    {
        if (u < w[i]) { pick = i; break; }
        u -= w[i];
    }

    out.file = pool[pick].second;
    score (lib.files[out.file], role, t, h, out.k, out.s, out.file);
    if (role == DRUMS && c > 0.8f) out.s = (int) (rng.next() % 7u) - 3;
    return out;
}

// picks every unlocked slot in role order with one rng; each slot's current file is excluded from its re-roll
inline void pickAll (const library::Library& lib, const Target& t, const bool locked[4], Choice slots[4], History& h, Rng& rng)
{
    for (int j = 0; j < 4; ++j)
    {
        if (locked[j]) continue;
        slots[j] = pickOne (lib, j, t, slots[j].file, h, rng);
        if (slots[j].file >= 0) h.push (j, slots[j].file);
    }
}

}} // namespace recycler::picker
