// Deck.h: DECK mode. A crate is the folder's accepted files in file-name order (case-insensitive, the full path breaks
// ties). Each slot steps through it on its own: next / prev with wrap; a slot with no file (or one not in the crate) goes
// to the first file on next and the last on prev. Slot n starts on file n (mod the crate size). A crate file's octave comes
// from the picker's octaveFor; its key shift from shiftFor unless its strongest role is DRUMS (drum loops are never keyed,
// on any slot). No Rack dependency.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include "Info.h"
#include "Library.h"
#include "Picker.h"
#include <algorithm>
#include <cctype>
#include <string>
#include <vector>

namespace recycler { namespace deck {

// the lower-cased file name of a path (either slash)
inline std::string nameKey (const std::string& path)
{
    const size_t cut = path.find_last_of ("/\\");
    std::string n = cut == std::string::npos ? path : path.substr (cut + 1);
    for (size_t i = 0; i < n.size(); ++i) n[i] = (char) std::tolower ((unsigned char) n[i]);
    return n;
}

// indices into lib.files in crate order
inline std::vector<int> order (const library::Library& lib)
{
    std::vector<int> o (lib.files.size());
    for (size_t i = 0; i < o.size(); ++i) o[i] = (int) i;
    std::vector<std::string> keys (lib.files.size());
    for (size_t i = 0; i < keys.size(); ++i) keys[i] = nameKey (lib.files[i].path);
    std::sort (o.begin(), o.end(), [&] (int a, int b) {
        return keys[(size_t) a] != keys[(size_t) b] ? keys[(size_t) a] < keys[(size_t) b] : lib.files[(size_t) a].path < lib.files[(size_t) b].path; });
    return o;
}

// the position of path in ord, -1 when it is not in the crate
inline int positionOf (const library::Library& lib, const std::vector<int>& ord, const std::string& path)
{
    if (path.empty()) return -1;
    for (size_t p = 0; p < ord.size(); ++p)
        if (lib.files[(size_t) ord[p]].path == path) return (int) p;
    return -1;
}

// the next (dir > 0) or previous (dir < 0) position in a crate of n, wrapping; -1 when the crate is empty
inline int step (int pos, int dir, int n)
{
    if (n <= 0) return -1;
    if (pos < 0 || pos >= n) return dir < 0 ? n - 1 : 0;
    return ((pos + (dir < 0 ? -1 : 1)) % n + n) % n;
}

// where slot starts in a crate of n; -1 when the crate is empty
inline int startPos (int slot, int n) { return n > 0 ? slot % n : -1; }

// the file's strongest role (ties go to the lower role): its stretch kind in DECK mode
inline int kindOf (const Info& info)
{
    int k = 0;
    for (int j = 1; j < 4; ++j)
        if (info.role[j] > info.role[k]) k = j;
    return k;
}

// octave and key shift of a crate file at target t
inline picker::Choice fit (const Info& info, const picker::Target& t)
{
    picker::Choice c;
    float cost = 0.f;
    c.k = picker::octaveFor (info.tempo, t.bpm, cost);
    c.s = kindOf (info) == DRUMS ? 0 : picker::shiftFor (info.key, info.minor, t.root, t.minor);
    return c;
}

}} // namespace recycler::deck
