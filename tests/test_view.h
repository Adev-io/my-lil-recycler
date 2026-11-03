// test_view.h: View.h: the loop envelope, crate file names, section kinds and crate.json.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include "View.h"

inline void testView()
{
    using namespace recycler::view;
    {   // envelope: a full-scale sine reads peak ~1, rms ~0.707 in every bin; silence reads 0
        std::vector<float> l (48000), r (48000, 0.f);
        for (size_t i = 0; i < l.size(); ++i) l[i] = (float) std::sin (6.283185307179586 * 441.0 * (double) i / 48000.0);
        float pk[BINS], rms[BINS];
        envelope (l, l, pk, rms);
        float minPk = 1.f, maxRms = 0.f, minRms = 1.f;
        for (int b = 0; b < BINS; ++b) { minPk = std::min (minPk, pk[b]); minRms = std::min (minRms, rms[b]); maxRms = std::max (maxRms, rms[b]); }
        check (minPk > 0.99f, "view: sine envelope peak ~1 in every bin", minPk);
        check (near (minRms, 0.7071, 0.02) && near (maxRms, 0.7071, 0.02), "view: sine envelope rms ~0.707", minRms);
        envelope (r, r, pk, rms);
        check (pk[0] == 0.f && rms[BINS - 1] == 0.f, "view: silence envelope is 0");
        std::vector<float> few (5, 0.5f);
        envelope (few, few, pk, rms);   // fewer frames than bins: every bin still reads a frame
        check (pk[BINS - 1] == 0.5f && pk[0] == 0.5f, "view: 5-frame loop fills all bins", pk[BINS - 1]);
        std::vector<float> none;
        envelope (none, none, pk, rms);
        check (pk[3] == 0.f, "view: empty loop reads 0");
    }
    {   // file names: <n>-<stem>-<NN>[_<section>][-<tag>]
        const Name a = parseName ("1-drums-07-120bpm.wav");
        check (a.stem == "1-drums" && a.nn == 7 && a.section.empty(), "view: 1-drums-07-120bpm -> 1-drums, 7, no section", a.nn);
        const Name b = parseName ("4-vocals-19_outro-141bpm.wav");
        check (b.stem == "4-vocals" && b.nn == 19 && b.section == "outro", "view: 4-vocals-19_outro-141bpm -> 4-vocals, 19, outro", b.nn);
        const Name c = parseName ("1-piano-03_verse.wav");
        check (c.stem == "1-piano" && c.nn == 3 && c.section == "verse", "view: 1-piano-03_verse -> 1-piano, 3, verse", c.nn);
        const Name d = parseName ("Amen break.wav");
        check (d.nn < 0, "view: a name with no number is not a crate loop", d.nn);
        const Name e = parseName ("01_intro.wav");
        check (e.nn < 0, "view: a number with no stem before it is not a crate loop", e.nn);
    }
    {   // section kinds: known names by prefix, any case; anything else is OTHER; nothing is NONE
        check (sectionKind ("Verse 2") == VERSE && sectionKind ("pre-chorus") == PRE && sectionKind ("chorus") == CHORUS,
               "view: section kinds by prefix");
        check (sectionKind ("") == NONE && sectionKind ("xyz") == OTHER, "view: empty -> NONE, unknown -> OTHER");
    }
    {   // crate.json: every key optional; wrong types and junk are skipped; broken JSON is no crate
        Crate c;
        const bool ok = parseCrate ("{\"title\": \"Doobie Fool\", \"artist\": 7, \"cover\": \"cover.jpg\", \"extra\": [1, {\"a\": null}],"
                                    " \"sections\": {\"01\": \"intro\", \"2\": \"verse\", \"x\": \"bad\", \"03\": 5, \"04\": \"Caf\\u00e9\"}}", c);
        check (ok && c.title == "Doobie Fool" && c.cover == "cover.jpg", "crate: title and cover read, a numeric artist skipped");
        check (c.sections.size() == 3 && sectionFor (c, 1, "") == "intro" && sectionFor (c, 2, "") == "verse",
               "crate: sections 01 and 2 read, bad keys and values skipped", (double) c.sections.size());
        check (sectionFor (c, 4, "") == "Caf\xC3\xA9", "crate: \\u escapes decode to UTF-8");
        check (sectionFor (c, 9, "verse") == "verse" && sectionFor (c, 9, "").empty(), "crate: no entry -> the file's own section");
        Crate t;
        check (parseCrate ("{\"title\": 3, \"sections\": [\"intro\"]}", t) && t.title.empty() && t.sections.empty(),
               "crate: a numeric title and an array of sections are ignored");
        Crate e;
        check (parseCrate ("{}", e) && e.title.empty() && e.cover.empty(), "crate: {} is an empty crate");
        Crate bad;
        bad.title = "stale";
        check (! parseCrate ("{\"title\": \"x\"", bad) && bad.title.empty(), "crate: broken JSON -> false, empty crate");
        check (! parseCrate ("[1]", bad) && ! parseCrate ("", bad), "crate: not an object -> false");
    }
}
