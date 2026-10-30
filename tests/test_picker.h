// test_picker.h: octave and shift math, soft fits, the Rack smoke folder, chaos bounds, no duplicates, locks, determinism,
// exclusion, fallback and history of Picker.h.
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

const int none[4] = { -1, -1, -1, -1 };

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

// the Rack smoke folder: bass 0..2 and melody 3..5 in G minor / A major / F# minor at 100 / 120 / 140 BPM, roles 0.65 / 0.70 / 0.74;
// 6 is an atonal 100 BPM drum loop with bass and melody 0.15. Against C minor 120 every tonal file needs |s| >= 5.
inline recycler::library::Library smoke()
{
    static const int keys[3] = { 7, 9, 6 };
    static const bool minors[3] = { true, false, true };
    static const float tempos[3] = { 100.f, 120.f, 140.f }, roles[3] = { 0.65f, 0.70f, 0.74f };
    recycler::library::Library lib;
    for (int r = recycler::BASS; r <= recycler::MELODY; ++r)
        for (int i = 0; i < 3; ++i)
        {
            Info f;
            f.tempo = tempos[i]; f.key = keys[i]; f.minor = minors[i];
            f.role[recycler::DRUMS] = 0.05f; f.role[recycler::BASS] = 0.2f; f.role[recycler::MELODY] = 0.2f; f.role[recycler::TEXTURE] = 0.1f;
            f.role[r] = roles[i];
            lib.files.push_back (f);
        }
    Info loop; loop.tempo = 100.f; loop.key = -1;
    loop.role[recycler::DRUMS] = 0.9f; loop.role[recycler::BASS] = 0.15f; loop.role[recycler::MELODY] = 0.15f; loop.role[recycler::TEXTURE] = 0.1f;
    lib.files.push_back (loop);
    return lib;
}

inline Target target (float chaos) { Target t; t.bpm = 120.f; t.root = 0; t.minor = false; t.chaos = chaos; return t; }
inline Target cMinor (float chaos) { Target t = target (chaos); t.minor = true; return t; }

inline void pickAllSeed (const recycler::library::Library& lib, const Target& t, uint64_t seed, Choice slots[4])
{
    bool locked[4] = { false, false, false, false };
    History h; Rng rng (seed);
    for (int j = 0; j < 4; ++j) slots[j] = Choice();
    pickAll (lib, t, locked, slots, h, rng);
}

inline bool distinct (const Choice slots[4])
{
    for (int a = 0; a < 4; ++a)
        for (int b = a + 1; b < 4; ++b)
            if (slots[a].file >= 0 && slots[a].file == slots[b].file) return false;
    return true;
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

    // score: soft fits with the floor f = lerp(0.05, 0.5, chaos)
    {
        History h; int sk = 9, ss = 9;
        Info f = lib.files[10]; f.tempo = 0.f;        // bass with no tempo
        check (score (f, recycler::BASS, target (1.f), h, sk, ss) == 0.f, "picker: score 0 for tempo-0 non-texture");
        check (near (score (lib.files[38], recycler::TEXTURE, target (1.f), h, sk, ss), 0.9 * 0.5 * (0.5 + 0.5 * std::exp (-16.0 / 36.0)), 1e-4) && sk == 0,
               "picker: tempo-0 texture: tempoFit = f, k 0", score (lib.files[38], recycler::TEXTURE, target (1.f), h, sk, ss));
        check (score (lib.files[0], recycler::DRUMS, target (0.f), h, sk, ss) > 0.f && ss == 0, "picker: drum scores with s 0");
        const float far = score (lib.files[13], recycler::BASS, target (0.f), h, sk, ss);   // 180 vs 120, A minor = C major
        check (near (far, 0.775 * 0.05, 1e-3), "picker: chaos 0, 180 BPM vs 120 floors at role * 0.05 (not 0)", far);
        Info atonal = lib.files[10]; atonal.key = -1;   // 120 BPM, role 0.7
        const float at = score (atonal, recycler::BASS, target (0.25f), h, sk, ss);
        check (near (at, 0.7 * 0.1625, 1e-4) && ss == 0, "picker: atonal bass keyFit = f (0.1625 at chaos 0.25)", at);
        Info offKey = lib.files[10]; offKey.key = 6;     // F# major vs C major: s = -6, way past shiftMax 2
        const float ok = score (offKey, recycler::BASS, target (0.f), h, sk, ss);
        check (ok > 0.f && ss == -6, "picker: |s| > shiftMax still scores > 0", ok);
    }

    // the Rack smoke folder at C minor 120, chaos 0.25: bass and melody slots get bass and melody files, not the drum loop
    {
        const recycler::library::Library sm = smoke();
        int bassOk = 0, melodyOk = 0;
        for (uint64_t seed = 1; seed <= 200; ++seed)
        {
            Choice slots[4]; pickAllSeed (sm, cMinor (0.25f), seed, slots);
            if (slots[1].file >= 0 && slots[1].file <= 2) ++bassOk;
            if (slots[2].file >= 3 && slots[2].file <= 5) ++melodyOk;
        }
        check (bassOk >= 196, "picker: smoke folder -> bass slot holds a bass file >= 98 % (count of 200)", bassOk);
        check (melodyOk >= 196, "picker: smoke folder -> melody slot holds a melody file >= 98 % (count of 200)", melodyOk);

        int hits[7] = { 0, 0, 0, 0, 0, 0, 0 };
        History h;
        for (uint64_t seed = 1; seed <= 200; ++seed)
        {
            Rng r (seed);
            const int f = pickOne (sm, recycler::BASS, cMinor (1.f), -1, none, h, r).file;
            if (f >= 0) ++hits[f];
        }
        check (hits[0] >= 20, "picker: chaos 1 -> G minor bass picked >= 10 % (count of 200)", hits[0]);
        check (hits[1] >= 20, "picker: chaos 1 -> A major bass picked >= 10 % (count of 200)", hits[1]);
        check (hits[2] >= 20, "picker: chaos 1 -> F# minor bass picked >= 10 % (count of 200)", hits[2]);
    }

    // chaos 0 with one perfect bass (120, C minor) among two stronger but off ones: the perfect one wins >= 80 %
    {
        recycler::library::Library three = smoke();
        three.files.resize (3);
        three.files[1].tempo = 120.f; three.files[1].key = 0; three.files[1].minor = true; three.files[1].role[recycler::BASS] = 0.65f;
        three.files[0].role[recycler::BASS] = 0.74f; three.files[2].role[recycler::BASS] = 0.74f;
        int perfect = 0; History h;
        for (uint64_t seed = 1; seed <= 200; ++seed)
        {
            Rng r (seed);
            if (pickOne (three, recycler::BASS, cMinor (0.f), -1, none, h, r).file == 1) ++perfect;
        }
        check (perfect >= 160, "picker: chaos 0 -> perfect bass picked >= 80 % (count of 200)", perfect);
    }

    // chaos 0: picks stay in the safe zone, drums unshifted
    {
        int safe = 0, drumsShifted = 0, chosen = 0;
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
                if (e <= 0.11f && std::abs (slots[j].s) <= 2) ++safe;
                if (j == recycler::DRUMS && slots[j].s != 0) ++drumsShifted;
            }
        }
        check (chosen == 200, "picker: chaos 0 fills every slot of the fixture", chosen);
        check (safe >= 190, "picker: chaos 0 -> cost <= 0.11 and |s| <= 2 for >= 95 % of picks (count of 200)", safe);
        check (drumsShifted == 0, "picker: chaos 0 -> drums s = 0", drumsShifted);
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

    // no file twice in a combo
    {
        int dup = 0;
        for (uint64_t seed = 1; seed <= 200; ++seed)
        {
            Choice slots[4]; pickAllSeed (lib, target (1.f), seed, slots);
            if (! distinct (slots)) ++dup;
        }
        check (dup == 0, "picker: pickAll never puts one file in two slots (200 seeds, chaos 1)", dup);
        const int others[4] = { 10, 11, 19, 25 };
        bool clean = true; History h;
        for (uint64_t seed = 1; seed <= 200; ++seed)
        {
            Rng r (seed);
            const int f = pickOne (lib, recycler::BASS, target (1.f), 12, others, h, r).file;
            if (f == 10 || f == 11 || f == 19 || f == 25 || f == 12) clean = false;
        }
        check (clean, "picker: pickOne never returns a file in otherFiles or currentFile");
    }

    // locks
    {
        bool locked[4] = { false, true, false, false };
        Choice slots[4]; slots[1].file = 7; slots[1].k = 1; slots[1].s = -2;    // a strong drum file locked in the bass slot
        History h; Rng rng (3);
        pickAll (lib, target (0.5f), locked, slots, h, rng);
        check (slots[1].file == 7 && slots[1].k == 1 && slots[1].s == -2, "picker: locked slot unchanged", slots[1].file);
        check (! h.seen (1, 7), "picker: locked slot not pushed to history");
        check (slots[0].file >= 0 && h.seen (0, slots[0].file), "picker: pickAll pushes picks to history", slots[0].file);
        int leaks = 0;
        for (uint64_t seed = 1; seed <= 200; ++seed)
        {
            Choice s[4]; s[1].file = 7;
            History hh; Rng r (seed);
            pickAll (lib, target (0.5f), locked, s, hh, r);
            if (s[0].file == 7 || s[2].file == 7 || s[3].file == 7) ++leaks;
        }
        check (leaks == 0, "picker: locked slot's file never appears in another slot (200 seeds)", leaks);
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
            const int f = pickOne (tie, recycler::BASS, target (0.f), -1, none, h, r).file;
            if (f == 5) ++low;
            if (f == 12) ++high;
        }
        check (low > 0 && high == 0, "picker: top-16 tie keeps the lower index", low * 1000 + high);
    }

    // currentFile exclusion
    {
        recycler::library::Library one; one.files.push_back (lib.files[10]);
        History h; Rng rng (5);
        check (pickOne (one, recycler::BASS, target (0.25f), 0, none, h, rng).file == -1, "picker: only candidate is current -> -1");
        check (pickOne (one, recycler::BASS, target (0.25f), -1, none, h, rng).file == 0, "picker: one-file library picks it");
        bool never = true;
        for (uint64_t seed = 1; seed <= 50; ++seed)
        {
            Rng r (seed);
            for (int j = 0; j < 4; ++j)
                if (pickOne (lib, j, target (0.25f), j * 10, none, h, r).file == j * 10) never = false;
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
            if (pickOne (lib, recycler::BASS, target (0.5f), -1, none, fresh, a).file == 10) ++freshHits;
            if (pickOne (lib, recycler::BASS, target (0.5f), -1, none, seen, b).file == 10) ++seenHits;
        }
        check (seenHits < freshHits, "picker: history lowers the chance of a repeat", seenHits - freshHits);
    }

    // fallback: a weak bass still gets picked at chaos 0
    {
        recycler::library::Library weak; weak.files.push_back (lib.files[10]); weak.files[0].role[recycler::BASS] = 0.3f;
        History h; Rng rng (9);
        check (pickOne (weak, recycler::BASS, target (0.f), -1, none, h, rng).file == 0, "picker: below-threshold falls back to best role files");
    }

    // fallback floor lerp(0.3, 0, chaos): with the only real drum file current, no wrong-kind file fills the drums slot
    {
        recycler::library::Library sm = smoke();                  // drum loop 6 is the only strong drums file
        sm.files[0].role[recycler::DRUMS] = 0.2f;                 // best other drums score, under the 0.225 floor at chaos 0.25
        History h; int filled = 0, any = 0;
        for (uint64_t seed = 1; seed <= 50; ++seed)
        {
            Rng a (seed), b (seed);
            if (pickOne (sm, recycler::DRUMS, cMinor (0.25f), 6, none, h, a).file >= 0) ++filled;
            if (pickOne (sm, recycler::DRUMS, cMinor (1.f), 6, none, h, b).file >= 0) ++any;
        }
        check (filled == 0, "picker: chaos 0.25, drums 0.2 under the fallback floor -> -1 (count filled of 50)", filled);
        check (any == 50, "picker: chaos 1 -> drums re-roll still returns a file (count of 50)", any);
        sm.files[0].role[recycler::DRUMS] = 0.26f;                // over the 0.225 floor: the fallback may take it
        Rng r (1);
        check (pickOne (sm, recycler::DRUMS, cMinor (0.25f), 6, none, h, r).file == 0, "picker: chaos 0.25, drums 0.26 is over the floor -> fallback takes it");
    }

    // pickAll: a slot whose re-roll comes back -1 keeps its file, and later slots cannot take it
    {
        recycler::library::Library two;
        Info a; a.tempo = 120.f; a.key = 0; a.role[recycler::BASS] = 0.9f; a.role[recycler::MELODY] = 0.9f;   // the only bass file
        Info b = a; b.role[recycler::BASS] = 0.1f; b.role[recycler::MELODY] = 0.7f;
        two.files.push_back (a); two.files.push_back (b);
        const bool locked[4] = { false, false, false, false };
        int stolen = 0, kept = 0;
        for (uint64_t seed = 1; seed <= 200; ++seed)
        {
            Choice slots[4]; slots[recycler::BASS].file = 0; slots[recycler::BASS].k = 0; slots[recycler::BASS].s = 2;
            History h; Rng r (seed);
            pickAll (two, target (0.25f), locked, slots, h, r);
            if (slots[recycler::BASS].file == 0 && slots[recycler::BASS].s == 2 && ! h.seen (recycler::BASS, 0)) ++kept;
            if (slots[recycler::MELODY].file == 0 || slots[recycler::DRUMS].file == 0 || slots[recycler::TEXTURE].file == 0) ++stolen;
        }
        check (kept == 200, "picker: pickAll keeps a slot's Choice when its re-roll returns -1 (count of 200)", kept);
        check (stolen == 0, "picker: that kept file is not picked by a later slot (count of 200)", stolen);
    }

    // empty library
    {
        recycler::library::Library empty;
        bool locked[4] = { false, false, false, false };
        Choice slots[4]; History h; Rng rng (1);
        pickAll (empty, target (0.5f), locked, slots, h, rng);
        check (slots[0].file == -1 && slots[1].file == -1 && slots[2].file == -1 && slots[3].file == -1, "picker: empty library -> all -1");
        check (pickOne (empty, recycler::TEXTURE, target (1.f), -1, none, h, rng).file == -1, "picker: empty library pickOne -> -1");
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
