// test_file.h: UTF-8 path open / replace / remove of File.h, and its UTF-8 -> UTF-16 decoder.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include "check.h"
#include "File.h"
#include <cstdio>
#include <string>
#ifdef _WIN32
#include <direct.h>
#else
#include <sys/stat.h>
#endif

namespace filetest
{
inline bool writeAll (const std::string& path, const std::string& text)
{
    std::FILE* f = recycler::file::open (path, "wb");
    if (! f) return false;
    const bool ok = std::fwrite (text.data(), 1, text.size(), f) == text.size();
    return std::fclose (f) == 0 && ok;
}

// returns false when the file cannot be opened
inline bool readAll (const std::string& path, std::string& text)
{
    std::FILE* f = recycler::file::open (path, "rb");
    if (! f) return false;
    text.clear();
    char buf[256];
    size_t n;
    while ((n = std::fread (buf, 1, sizeof buf, f)) > 0) text.append (buf, n);
    std::fclose (f);
    return true;
}
} // namespace filetest

inline void testFile()
{
    using namespace filetest;
    namespace file = recycler::file;

#ifdef _WIN32
    _mkdir ("../build"); _mkdir ("../build/file");
#else
    mkdir ("../build", 0755); mkdir ("../build/file", 0755);
#endif
    const std::string a = "../build/file/caf\xc3\xa9_\xe9\x9f\xb3_a.bin";   // café_音_a.bin
    const std::string b = "../build/file/caf\xc3\xa9_\xe9\x9f\xb3_b.bin";
    file::remove (a); file::remove (b);

    const std::string one ("first\0\xff bytes", 13), two = "second content";
    check (writeAll (a, one), "file: open/write/close a non-ASCII path");
    std::string got;
    check (readAll (a, got) && got == one, "file: read gives the same bytes back", (double) got.size());
#ifdef _WIN32
    {   // the name on disk is the real Unicode one, not the UTF-8 bytes read as the ANSI codepage
        std::FILE* f = _wfopen (L"../build/file/café_音_a.bin", L"rb");
        check (f != nullptr, "file: _wfopen finds the real (e-acute, CJK) name on disk");
        if (f) std::fclose (f);
        std::FILE* g = std::fopen (a.c_str(), "rb");
        check (g == nullptr, "file: narrow fopen of the UTF-8 bytes finds nothing");
        if (g) std::fclose (g);
    }
#endif

    check (writeAll (b, two), "file: write a second non-ASCII file");
    check (file::replace (b, a), "file: replace over an existing target");
    check (readAll (a, got) && got == two, "file: target holds the new content");
    check (! readAll (b, got), "file: source is gone after replace");

    check (file::remove (a), "file: remove an existing file -> true");
    check (! file::remove (a), "file: remove it again -> false");
    std::FILE* missing = file::open ("../build/file/missing.bin", "rb");
    check (missing == nullptr, "file: open of a missing file -> null");
    if (missing) std::fclose (missing);

#ifdef _WIN32
    const std::wstring w = file::detail::toWide ("a\xc3\xa9\xe9\x9f\xb3\xf0\x9f\x98\x80");   // aé音😀
    check (w.size() == 5 && w[0] == 0x61 && w[1] == 0xE9 && w[2] == 0x97F3 && w[3] == 0xD83D && w[4] == 0xDE00,
           "file: toWide(\"a\\u00e9\\u97f3\\U0001F600\") = 61 E9 97F3 D83D DE00", (double) w.size());
    const std::wstring bad = file::detail::toWide ("x\xff\xc3(\xe9\x9f");   // invalid byte, bad continuation, truncated
    check (bad == std::wstring (L"x\xfffd\xfffd(\xfffd\xfffd"), "file: invalid UTF-8 bytes -> U+FFFD each", (double) bad.size());
#endif
}
