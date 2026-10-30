// test_library.h: JSON round trip, find/put, malformed input, atomic save/load and truncation of Library.h.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include "check.h"
#include "Library.h"
#include <cstdio>
#include <fstream>
#include <string>
#ifdef _WIN32
#include <direct.h>
#else
#include <sys/stat.h>
#endif

namespace librarytest
{
using recycler::Info;
const std::string dir = "../build/library/";

inline Info first()
{
    Info a;
    a.path = "C:/samples/my \"loops\" \\ caf\xc3\xa9\tbreak\r\n\x01" "x.wav";
    a.size = 1234567890123ull; a.mtime = 1700000000123ll;
    a.sampleRate = 44100; a.frames = 529200; a.seconds = 12.f;
    a.tempo = 120.5f; a.tempoConf = 0.875f; a.bars = 4;
    a.key = 9; a.minor = true; a.keyConf = 0.66f;
    a.onsets.push_back (0.f); a.onsets.push_back (0.5f); a.onsets.push_back (1.25f);
    a.onsets.push_back (2.125f); a.onsets.push_back (3.0001f);
    a.bestOnset = 0.5f;
    a.role[0] = 0.7f; a.role[1] = 0.1f; a.role[2] = 0.15f; a.role[3] = 0.05f;
    a.rms = -18.25f; a.peak = -0.5f;
    return a;
}

inline Info second()
{
    Info b;
    b.path = "D:/one shot/kick.aiff";
    b.size = 42; b.mtime = -5;
    b.sampleRate = 48000; b.frames = 4800; b.seconds = 0.1f;
    b.tempo = 0.f; b.key = -1; b.minor = false;
    b.rms = -99.f; b.peak = -3.f;
    return b;
}

inline bool same (const Info& x, const Info& y)
{
    bool ok = x.path == y.path && x.size == y.size && x.mtime == y.mtime && x.sampleRate == y.sampleRate
           && x.frames == y.frames && near (x.seconds, y.seconds, 1e-4) && near (x.tempo, y.tempo, 1e-4)
           && near (x.tempoConf, y.tempoConf, 1e-4) && x.bars == y.bars && x.key == y.key && x.minor == y.minor
           && near (x.keyConf, y.keyConf, 1e-4) && x.onsets.size() == y.onsets.size()
           && near (x.bestOnset, y.bestOnset, 1e-4) && near (x.rms, y.rms, 1e-4) && near (x.peak, y.peak, 1e-4);
    for (size_t i = 0; ok && i < x.onsets.size(); ++i) ok = near (x.onsets[i], y.onsets[i], 1e-4);
    for (int r = 0; ok && r < 4; ++r) ok = near (x.role[r], y.role[r], 1e-4);
    return ok;
}

inline bool sameLib (const recycler::library::Library& x, const recycler::library::Library& y)
{
    if (x.files.size() != y.files.size()) return false;
    for (size_t i = 0; i < x.files.size(); ++i) if (! same (x.files[i], y.files[i])) return false;
    return true;
}

inline void writeRaw (const std::string& path, const std::string& text)
{
    std::ofstream f (path.c_str(), std::ios::binary); f << text;
}

inline bool exists (const std::string& path)
{
    std::FILE* f = std::fopen (path.c_str(), "rb");
    if (f) std::fclose (f);
    return f != nullptr;
}

// existence through the UTF-8 path layer (File.h)
inline bool opens (const std::string& utf8Path)
{
    std::FILE* f = recycler::file::open (utf8Path, "rb");
    if (f) std::fclose (f);
    return f != nullptr;
}

#ifdef _WIN32
inline bool wideOpens (const wchar_t* path)
{
    std::FILE* f = _wfopen (path, L"rb");
    if (f) std::fclose (f);
    return f != nullptr;
}
#endif
} // namespace librarytest

inline void testLibrary()
{
    using namespace librarytest;
    using namespace recycler::library;

    Library lib; lib.files.push_back (first()); lib.files.push_back (second());

    {   // JSON round trip
        const std::string js = toJson (lib);
        Library back;
        const bool ok = fromJson (js, back);
        check (ok && back.files.size() == 2, "library: toJson -> fromJson parses 2 files", (double) back.files.size());
        check (ok && same (back.files[0], lib.files[0]), "library: file 1 round trips (quotes, backslash, tab, CR LF, 0x01, UTF-8, 5 onsets)");
        check (ok && same (back.files[1], lib.files[1]), "library: file 2 round trips (no onsets, key -1, tempo 0)");
        check (ok && back.files[1].onsets.empty() && back.files[1].key == -1, "library: empty onsets and key -1 kept");
        check (js.find ("\"onsets\":[") != std::string::npos && js.find ("\"minor\":true") != std::string::npos,
               "library: flat keys, onsets array, minor as true");
    }

    {   // find
        const Info& a = lib.files[0];
        check (lib.find (a.path, a.size, a.mtime) == &lib.files[0], "library: find hits with stored size/mtime");
        check (lib.find (a.path, a.size + 1, a.mtime) == nullptr, "library: find misses with size+1");
        check (lib.find (a.path, a.size, a.mtime + 1) == nullptr, "library: find misses with mtime+1");
        check (lib.find ("nope.wav", a.size, a.mtime) == nullptr, "library: find misses on unknown path");
    }

    {   // put
        Library l = lib;
        Info a = first(); a.tempo = 98.f;
        l.put (a);
        check (l.files.size() == 2 && near (l.files[0].tempo, 98.0, 1e-6), "library: put same path replaces", l.files[0].tempo);
        Info c = second(); c.path = "E:/new.wav";
        l.put (c);
        check (l.files.size() == 3 && l.files[2].path == "E:/new.wav", "library: put new path appends", (double) l.files.size());
    }

    {   // malformed input leaves lib untouched
        const char* bad[] = { "{", "[{\"path\":1}]", "[1,]", "[{},]", "[{\"path\":\"a\",}]", "[{\"path\":\"a\"}", "[{\"path\":\"a\"}] x",
                              "", "[{\"bars\":1.5e}]", "[{\"onsets\":[1,]}]", "[{\"path\":\"a\\q\"}]", "[{\"minor\":tru}]",
                              "[{\"path\":\"a\",\"tempo\":1e400}]", "[{\"mtime\":123456789012345678901}]" };
        for (size_t i = 0; i < sizeof (bad) / sizeof (bad[0]); ++i)
        {
            Library l = lib;
            const bool ok = fromJson (bad[i], l);
            const std::string what = std::string ("library: rejects malformed ") + bad[i] + ", lib untouched";
            check (! ok && l.files.size() == 2 && l.files[0].path == lib.files[0].path && near (l.files[0].tempo, lib.files[0].tempo, 0),
                   what.c_str());
        }
    }

    {   // well-formed edge cases
        Library l = lib;
        check (fromJson ("[]", l) && l.files.empty(), "library: [] -> true, empty");
        l = lib;
        check (fromJson (" \n[ \t] \r\n", l) && l.files.empty(), "library: whitespace [ ] -> true, empty");
        l = lib;
        const bool ok = fromJson ("[{\"path\":\"a\",\"zzz\":5,\"obj\":{\"x\":[1,\"y\",null]}}]", l);
        check (ok && l.files.size() == 1 && l.files[0].path == "a", "library: unknown keys ignored");
        check (ok && l.files.size() == 1 && l.files[0].key == -1 && near (l.files[0].rms, -99.0, 0), "library: missing keys keep Info defaults");
        l = lib;
        const bool esc = fromJson ("[{\"path\":\"\\u0041\\/\\b\\f\\n\"}]", l);
        check (esc && l.files.size() == 1 && l.files[0].path == "A/\b\f\n", "library: reads \\u0041 \\/ \\b \\f \\n");
    }

    {   // save / load
#ifdef _WIN32
        _mkdir ("../build"); _mkdir (dir.c_str());
#else
        mkdir ("../build", 0755); mkdir (dir.c_str(), 0755);
#endif
        const std::string path = dir + "test.json";
        std::remove (path.c_str());

        Library l = lib;
        check (! load (dir + "missing.json", l) && l.files.size() == 2, "library: load missing file -> false, lib untouched");

        check (save (lib, path), "library: save to fresh path");
        check (! exists (path + ".tmp"), "library: no .tmp left after save");
        Library back;
        check (load (path, back) && sameLib (back, lib), "library: load after save equals saved");

        Library other; other.files.push_back (second()); other.files[0].tempo = 77.f;
        check (save (other, path), "library: save over existing file");
        back = lib;
        const bool loaded = load (path, back);
        check (loaded && back.files.size() == 1 && near (back.files[0].tempo, 77.0, 1e-4),
               "library: load shows the new content", (double) back.files.size());

        const std::string js = toJson (lib);
        writeRaw (path, js.substr (0, js.size() / 2));
        back = lib;
        check (! load (path, back) && sameLib (back, lib), "library: truncated file -> false, lib untouched");
        std::remove (path.c_str());

        const std::string wide = dir + "t\xc3\xa9st_\xe9\x9f\xb3.json";   // tést_音.json
        recycler::file::remove (wide);
        check (save (lib, wide), "library: save to a non-ASCII path");
        check (opens (wide), "library: non-ASCII file exists (file::open)");
#ifdef _WIN32
        check (wideOpens (L"../build/library/t\u00e9st_\u97f3.json"), "library: _wfopen finds the real (e-acute, CJK) name on disk");
        check (! exists (wide), "library: narrow fopen of the UTF-8 bytes finds nothing");
#endif
        back = Library();
        const bool wideLoaded = load (wide, back);
        check (wideLoaded && sameLib (back, lib), "library: load from the non-ASCII path equals saved", (double) back.files.size());
        check (! opens (wide + ".tmp"), "library: no .tmp left after the non-ASCII save");
        recycler::file::remove (wide);
    }
}
