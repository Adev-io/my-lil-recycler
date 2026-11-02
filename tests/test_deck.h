// test_deck.h: DECK mode's crate order, stepping, start positions, file kind and key / octave fit (Deck.h).
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include "check.h"
#include "Deck.h"
#include <string>
#include <vector>

inline void testDeck()
{
    using namespace recycler;
    library::Library lib;
    const char* paths[4] = { "C:/crate/03_c.wav", "C:/crate/01_A.wav", "D:/other/02_b.wav", "C:/crate/02_b.wav" };
    for (int i = 0; i < 4; ++i) { Info f; f.path = paths[i]; lib.files.push_back (f); }

    // order: file name, case-insensitive; equal names fall back to the full path
    const std::vector<int> ord = deck::order (lib);
    check (ord.size() == 4 && ord[0] == 1 && ord[1] == 3 && ord[2] == 2 && ord[3] == 0,
           "deck: order = 01_A, C:/crate/02_b, D:/other/02_b, 03_c", ord.size() == 4 ? ord[1] : -1);
    check (deck::order (library::Library()).empty(), "deck: order of an empty library is empty");

    // case-insensitive: byte order would put "B" before "a"
    library::Library cs;
    const char* csPaths[2] = { "C:/crate/B.wav", "C:/crate/a.wav" };
    for (int i = 0; i < 2; ++i) { Info f; f.path = csPaths[i]; cs.files.push_back (f); }
    const std::vector<int> csOrd = deck::order (cs);
    check (csOrd.size() == 2 && csOrd[0] == 1 && csOrd[1] == 0, "deck: order is case-insensitive (a before B)", csOrd.size() == 2 ? csOrd[0] : -1);

    // backslash paths (the Windows scanner): the name is split on either slash
    check (deck::nameKey ("C:\\a\\B.WAV") == "b.wav", "deck: nameKey splits on a backslash and lower-cases");
    library::Library bs;
    const char* bsPaths[2] = { "C:\\z\\02_x.wav", "D:\\a\\01_y.wav" };
    for (int i = 0; i < 2; ++i) { Info f; f.path = bsPaths[i]; bs.files.push_back (f); }
    const std::vector<int> bsOrd = deck::order (bs);
    check (bsOrd.size() == 2 && bsOrd[0] == 1 && bsOrd[1] == 0, "deck: order by file name on backslash paths", bsOrd.size() == 2 ? bsOrd[0] : -1);

    // positionOf
    check (deck::positionOf (lib, ord, "C:/crate/03_c.wav") == 3, "deck: positionOf 03_c -> 3", deck::positionOf (lib, ord, "C:/crate/03_c.wav"));
    check (deck::positionOf (lib, ord, "C:/crate/01_A.wav") == 0, "deck: positionOf 01_A -> 0", deck::positionOf (lib, ord, "C:/crate/01_A.wav"));
    check (deck::positionOf (lib, ord, "C:/gone.wav") == -1, "deck: positionOf a file not in the crate -> -1");
    check (deck::positionOf (lib, ord, "") == -1, "deck: positionOf an empty path -> -1");

    // step: wrap both ways; -1 or out of range = no file (next -> 0, prev -> last); empty crate -> -1
    check (deck::step (0, 1, 4) == 1, "deck: step 0 next of 4 -> 1", deck::step (0, 1, 4));
    check (deck::step (3, 1, 4) == 0, "deck: step 3 next of 4 wraps -> 0", deck::step (3, 1, 4));
    check (deck::step (0, -1, 4) == 3, "deck: step 0 prev of 4 wraps -> 3", deck::step (0, -1, 4));
    check (deck::step (2, -1, 4) == 1, "deck: step 2 prev of 4 -> 1", deck::step (2, -1, 4));
    check (deck::step (-1, 1, 4) == 0, "deck: step from no file, next -> 0", deck::step (-1, 1, 4));
    check (deck::step (-1, -1, 4) == 3, "deck: step from no file, prev -> 3", deck::step (-1, -1, 4));
    check (deck::step (7, 1, 4) == 0, "deck: step from out of range, next -> 0", deck::step (7, 1, 4));
    check (deck::step (0, 1, 1) == 0, "deck: step in a crate of 1 stays 0", deck::step (0, 1, 1));
    check (deck::step (0, 1, 0) == -1, "deck: step in an empty crate -> -1", deck::step (0, 1, 0));

    // startPos: slot n starts on file n, wrapping in small crates
    check (deck::startPos (0, 4) == 0 && deck::startPos (3, 4) == 3, "deck: startPos 0 and 3 of 4", deck::startPos (3, 4));
    check (deck::startPos (3, 2) == 1, "deck: startPos 3 of 2 wraps -> 1", deck::startPos (3, 2));
    check (deck::startPos (2, 0) == -1, "deck: startPos in an empty crate -> -1", deck::startPos (2, 0));

    // kindOf: the strongest role, ties to the lower role
    Info melody; melody.role[0] = 0.2f; melody.role[1] = 0.1f; melody.role[2] = 0.8f; melody.role[3] = 0.3f;
    Info tie; tie.role[0] = 0.5f; tie.role[1] = 0.5f;
    check (deck::kindOf (melody) == MELODY, "deck: kindOf strongest role -> melody", deck::kindOf (melody));
    check (deck::kindOf (tie) == DRUMS, "deck: kindOf tie -> lower role", deck::kindOf (tie));
    check (deck::kindOf (Info()) == DRUMS, "deck: kindOf no scores -> drums", deck::kindOf (Info()));

    // fit at E minor 110: pitched files are keyed on any slot, drum loops and atonal files keep 0; k from octaveFor
    picker::Target t; t.bpm = 110.f; t.root = 4; t.minor = true;
    melody.key = 9; melody.minor = true; melody.tempo = 55.f;       // A minor at half tempo
    picker::Choice c = deck::fit (melody, t);
    float cost = 0.f;
    check (c.k == picker::octaveFor (55.f, 110.f, cost) && c.k == 1, "deck: fit k from octaveFor (55 -> 110 = k 1)", c.k);
    check (c.s == picker::shiftFor (9, true, 4, true) && c.s != 0, "deck: fit keys a pitched file (A minor -> E minor)", c.s);
    Info drumLoop = melody; drumLoop.role[0] = 0.95f;                 // same key, but drums is its strongest role
    check (deck::fit (drumLoop, t).s == 0, "deck: fit leaves a drum loop unshifted", deck::fit (drumLoop, t).s);
    Info atonal = melody; atonal.key = -1;
    check (deck::fit (atonal, t).s == 0, "deck: fit leaves an atonal file unshifted", deck::fit (atonal, t).s);
    Info noTempo = melody; noTempo.tempo = 0.f;
    check (deck::fit (noTempo, t).k == 0, "deck: fit of a tempo-0 file -> k 0", deck::fit (noTempo, t).k);
}
