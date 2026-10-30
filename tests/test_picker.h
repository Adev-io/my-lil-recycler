// test_picker.h: octave and shift math, chaos bounds, locks, determinism, exclusion, fallback and history of Picker.h.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include "check.h"
#include "Picker.h"
#include <cstdlib>
#include <string>

namespace pickertest
{
using recycler::Info;
using namespace recycler::picker;

// 40 files: 10 per role (n = role * 10 + i). i = 0 fits 120 BPM C major exactly; drums 0..3 atonal; texture 8, 9 tempo 0.
inline recycler::library::Library fixture()
{
    static const float tempos[10] = { 120.f, 60.f, 90.f, 180.f, 126.f, 100.f, 150.f, 64.f, 140.f, 170.f };
    static const int keys[10] = { 0, 7, 2, 9, 4, 11, 6, 1, 8, 3 };
    recycler::library::Library lib;
    for (int r = 0; r < 4; ++r)
        for (int i = 0; i < 10; ++i)
        {
            Info f;
            f.path = "f" + std::to_string (r * 10 + i);
            f.tempo = tempos[i];
            f.key = keys[i]; f.minor = i % 2 == 1;
            if (r == recycler::DRUMS && i < 4) f.key = -1;
            if (r == recycler::TEXTURE && i >= 8) f.tempo = 0.f;
            for (int j = 0; j < 4; ++j)
                f.role[j] = j == r ? 0.7f + 0.025f * i : 0.05f + 0.025f * ((i + j) % 10);
            lib.files.push_back (f);
        }
    return lib;
}

inline Target target (float chaos) { Target t; t.bpm = 120.f; t.root = 0; t.minor = false; t.chaos = chaos; return t; }

inline void pickAllSeed (const recycler::library::Library& lib, const Target& t, uint64_t seed, Choice slots[4])
{
    bool locked[4] = { false, false, false, false };
    History h; Rng rng (seed);
    for (int j = 0; j < 4; ++j) slots[j] = Choice();
    pickAll (lib, t, locked, slots, h, rng);
}
} // namespace pickertest

inline void testPicker()
{
    using namespace pickertest;
    const recycler::library::Library lib = fixture();
    float cost = 0.f;

    // octave / shift math
    int k = octaveFor (60.f, 120.f, cost);
    check (k == 1 && near (cost, 0.0, 1e-6), "picker: octaveFor(60, 120) -> k 1, cost 0", k);
    k = octaveFor (130.f, 120.f, cost);
    check (k == 0 && near (cost, 0.1155, 1e-3), "picker: octaveFor(130, 120) -> k 0, cost 0.1155", cost);
    k = octaveFor (250.f, 120.f, cost);
    check (k == -1, "picker: octaveFor(250, 120) -> k -1", k);
    k = octaveFor (120.f, 0.f, cost);
    check (k == 0 && cost >= 1e8f, "picker: octaveFor(120, bpm 0) -> k 0, huge cost", cost);
    check (shiftFor (9, true, 0, false) == 0, "picker: shiftFor A minor vs C major -> 0", shiftFor (9, true, 0, false));
    check (shiftFor (0, false, 7, false) == -5, "picker: shiftFor C to G -> -5", shiftFor (0, false, 7, false));
    check (shiftFor (0, false, 6, false) == -6, "picker: shiftFor C to F# -> -6 (wrap)", shiftFor (0, false, 6, false));
    check (shiftFor (-1, false, 5, true) == 0, "picker: shiftFor atonal -> 0", shiftFor (-1, false, 5, true));
    check (shiftFor (0, false, 0, true) == 3, "picker: shiftFor C major to C minor (Eb major) -> 3", shiftFor (0, false, 0, true));
    bool wrapOk = true;
    for (int f = 0; f < 12; ++f)
        for (int tk = 0; tk < 12; ++tk)
            for (int m = 0; m < 4; ++m)
            {
                const bool fm = (m & 1) != 0, tm = (m & 2) != 0;
                const int s = shiftFor (f, fm, tk, tm);
                const int fMaj = fm ? (f + 3) % 12 : f, tMaj = tm ? (tk + 3) % 12 : tk;
                if (s < -6 || s > 5 || ((fMaj + s - tMaj) % 12 + 12) % 12 != 0) wrapOk = false;
            }
    check (wrapOk, "picker: shiftFor in -6..5 and lands on target for all 576 key/mode pairs");

    // score exclusions
    {
        History h; int sk = 9, ss = 9;
        Info f = lib.files[10]; f.tempo = 0.f;        // bass with no tempo
        check (score (f, recycler::BASS, target (1.f), h, sk, ss) == 0.f, "picker: score 0 for tempo-0 non-texture");
        check (score (lib.files[38], recycler::TEXTURE, target (1.f), h, sk, ss) > 0.f && sk == 0, "picker: tempo-0 texture scores, k 0");
        check (score (lib.files[0], recycler::DRUMS, target (0.f), h, sk, ss) > 0.f && ss == 0, "picker: drum scores with s 0");
        check (score (lib.files[13], recycler::BASS, target (0.f), h, sk, ss) == 0.f, "picker: chaos 0 excludes 180 BPM vs 120");
    }

    // chaos 0: safe bounds, drums unshifted
    {
        bool safe = true, drumsZero = true; int chosen = 0;
        for (uint64_t seed = 1; seed <= 50; ++seed)
        {
            Choice slots[4]; pickAllSeed (lib, target (0.f), seed, slots);
            for (int j = 0; j < 4; ++j)
            {
                if (slots[j].file < 0) continue;
                ++chosen;
                const Info& f = lib.files[slots[j].file];
                float e = 0.f;
                if (f.tempo > 0.f) octaveFor (f.tempo, 120.f, e);
                if (e > 0.11f || std::abs (slots[j].s) > 2) safe = false;
                if (j == recycler::DRUMS && slots[j].s != 0) drumsZero = false;
            }
        }
        check (chosen == 200, "picker: chaos 0 fills every slot of the fixture", chosen);
        check (safe, "picker: chaos 0 -> cost <= 0.11 and |s| <= 2 for every pick");
        check (drumsZero, "picker: chaos 0 -> drums s = 0");
    }

    // chaos 1: leaves the safe zone, drums get shifted, texture may use tempo-0 files and nobody else does
    {
        bool wildTempo = false, wildKey = false, drumShift = false, textureZero = false, otherZero = false;
        for (uint64_t seed = 1; seed <= 50; ++seed)
        {
            Choice slots[4]; pickAllSeed (lib, target (1.f), seed, slots);
            for (int j = 0; j < 4; ++j)
            {
                if (slots[j].file < 0) continue;
                const Info& f = lib.files[slots[j].file];
                float e = 0.f;
                if (f.tempo > 0.f) octaveFor (f.tempo, 120.f, e);
                if (j != recycler::DRUMS && e > 0.11f) wildTempo = true;
                if (j != recycler::DRUMS && std::abs (slots[j].s) > 2) wildKey = true;
                if (j == recycler::DRUMS && slots[j].s != 0) drumShift = true;
                if (f.tempo <= 0.f) { if (j == recycler::TEXTURE) textureZero = true; else otherZero = true; }
            }
        }
        check (wildTempo, "picker: chaos 1 -> some bass/melody/texture pick has cost > 0.11");
        check (wildKey, "picker: chaos 1 -> some bass/melody/texture pick has |s| > 2");
        check (drumShift, "picker: chaos 1 -> some drum pick has s != 0");
        check (textureZero, "picker: chaos 1 -> texture picks a tempo-0 file");
        check (! otherZero, "picker: drums/bass/melody never pick a tempo-0 file");
    }

    // locks
    {
        bool locked[4] = { false, true, false, false };
        Choice slots[4]; slots[1].file = 7; slots[1].k = 1; slots[1].s = -2;
        History h; Rng rng (3);
        pickAll (lib, target (0.5f), locked, slots, h, rng);
        check (slots[1].file == 7 && slots[1].k == 1 && slots[1].s == -2, "picker: locked slot unchanged", slots[1].file);
        check (! h.seen (1, 7), "picker: locked slot not pushed to history");
        check (slots[0].file >= 0 && h.seen (0, slots[0].file), "picker: pickAll pushes picks to history", slots[0].file);
    }

    // determinism
    {
        const float chaos[2] = { 0.6f, 1.f };
        for (int ci = 0; ci < 2; ++ci)
        {
            bool same = true;
            for (uint64_t seed = 1; seed <= 10; ++seed)
            {
                Choice a[4], b[4];
                pickAllSeed (lib, target (chaos[ci]), seed, a);
                pickAllSeed (lib, target (chaos[ci]), seed, b);
                for (int j = 0; j < 4; ++j)
                    if (a[j].file != b[j].file || a[j].k != b[j].k || a[j].s != b[j].s) same = false;
            }
            check (same, ci ? "picker: same seed -> same slots (chaos 1, drum shift draw)" : "picker: same seed -> same slots (chaos 0.6)", chaos[ci]);
        }
    }

    // tie rule: twins at 5 and 12 tie for 16th place behind 15 slightly better files; the lower index survives the cut
    {
        recycler::library::Library tie;
        for (int i = 0; i < 17; ++i)
        {
            Info f = lib.files[10];                      // bass, 120 BPM, C major: score = role at chaos 0
            f.role[recycler::BASS] = i == 5 || i == 12 ? 0.70f : 0.71f;
            tie.files.push_back (f);
        }
        History h; int low = 0, high = 0;
        for (uint64_t seed = 1; seed <= 200; ++seed)
        {
            Rng r (seed);
            const int f = pickOne (tie, recycler::BASS, target (0.f), -1, h, r).file;
            if (f == 5) ++low;
            if (f == 12) ++high;
        }
        check (low > 0 && high == 0, "picker: top-16 tie keeps the lower index", low * 1000 + high);
    }

    // currentFile exclusion
    {
        recycler::library::Library one; one.files.push_back (lib.files[10]);
        History h; Rng rng (5);
        check (pickOne (one, recycler::BASS, target (0.25f), 0, h, rng).file == -1, "picker: only candidate is current -> -1");
        check (pickOne (one, recycler::BASS, target (0.25f), -1, h, rng).file == 0, "picker: one-file library picks it");
        bool never = true;
        for (uint64_t seed = 1; seed <= 50; ++seed)
        {
            Rng r (seed);
            for (int j = 0; j < 4; ++j)
                if (pickOne (lib, j, target (0.25f), j * 10, h, r).file == j * 10) never = false;
        }
        check (never, "picker: pickOne never returns currentFile");
    }

    // novelty: a file in history is picked less often than when fresh
    {
        int freshHits = 0, seenHits = 0;
        History fresh, seen; seen.push (recycler::BASS, 10);
        for (uint64_t seed = 1; seed <= 200; ++seed)
        {
            Rng a (seed), b (seed);
            if (pickOne (lib, recycler::BASS, target (0.5f), -1, fresh, a).file == 10) ++freshHits;
            if (pickOne (lib, recycler::BASS, target (0.5f), -1, seen, b).file == 10) ++seenHits;
        }
        check (seenHits < freshHits, "picker: history lowers the chance of a repeat", seenHits - freshHits);
    }

    // fallback: a weak bass still gets picked at chaos 0
    {
        recycler::library::Library weak; weak.files.push_back (lib.files[10]); weak.files[0].role[recycler::BASS] = 0.3f;
        History h; Rng rng (9);
        check (pickOne (weak, recycler::BASS, target (0.f), -1, h, rng).file == 0, "picker: below-threshold falls back to best role files");
    }

    // empty library
    {
        recycler::library::Library empty;
        bool locked[4] = { false, false, false, false };
        Choice slots[4]; History h; Rng rng (1);
        pickAll (empty, target (0.5f), locked, slots, h, rng);
        check (slots[0].file == -1 && slots[1].file == -1 && slots[2].file == -1 && slots[3].file == -1, "picker: empty library -> all -1");
        check (pickOne (empty, recycler::TEXTURE, target (1.f), -1, h, rng).file == -1, "picker: empty library pickOne -> -1");
    }

    // history
    {
        History h;
        for (int i = 0; i < 9; ++i) h.push (2, 100 + i);
        check (! h.seen (2, 100), "picker: 9 pushes forget the first");
        check (h.seen (2, 101) && h.seen (2, 108), "picker: last 8 remembered");
        check (! h.seen (1, 105), "picker: history is per role");
        check (h.recent[2].size() == 8, "picker: history keeps 8", (double) h.recent[2].size());
    }

    // rng
    {
        Rng a (1), b (1);
        bool same = true;
        for (int i = 0; i < 5; ++i) if (a.next() != b.next()) same = false;
        check (same, "picker: Rng(1) deterministic");
        Rng z (0);
        bool nonzero = false;
        for (int i = 0; i < 5; ++i) if (z.next() != 0u) nonzero = true;
        check (nonzero && z.state != 0, "picker: Rng(0) not stuck at 0");
        Rng u (42);
        bool inRange = true; double sum = 0.0;
        for (int i = 0; i < 1000; ++i) { const float x = u.uniform(); if (! (x >= 0.f && x < 1.f)) inRange = false; sum += x; }
        check (inRange, "picker: uniform in [0, 1)");
        check (near (sum / 1000.0, 0.5, 0.05), "picker: uniform mean ~0.5", sum / 1000.0);
    }
}
