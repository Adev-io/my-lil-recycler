// File.h: UTF-8 paths for fopen / atomic replace / remove, so non-ASCII Rack user folders work on Windows. No Rack dependency.
// On _WIN32 the UTF-8 path is decoded by hand to UTF-16 and handed to _wfopen / MoveFileExW / _wremove; elsewhere the
// narrow calls take the UTF-8 bytes directly. <windows.h> is avoided on purpose (its near/far/min/max macros).
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include <cstdio>
#include <string>

#ifdef _WIN32
#include <wchar.h>
extern "C" __declspec(dllimport) int __stdcall MoveFileExW (const wchar_t* from, const wchar_t* to, unsigned long flags);
#endif

namespace recycler { namespace file {

namespace detail {

// UTF-8 -> UTF-16 code units (surrogate pairs above 0xFFFF). Malformed, overlong, surrogate or > 0x10FFFF sequences
// become U+FFFD, consuming one byte, so decoding always finishes.
inline std::wstring toWide (const std::string& s)
{
    std::wstring w;
    w.reserve (s.size());
    const size_t n = s.size();
    size_t i = 0;
    while (i < n)
    {
        const unsigned char c = (unsigned char) s[i];
        int len = c < 0x80 ? 1 : (c >> 5) == 0x6 ? 2 : (c >> 4) == 0xe ? 3 : (c >> 3) == 0x1e ? 4 : 0;
        unsigned long cp = len == 1 ? c : len == 2 ? (c & 0x1f) : len == 3 ? (c & 0x0f) : (c & 0x07);
        bool ok = len > 0 && i + len <= n;
        for (int k = 1; ok && k < len; ++k)
        {
            const unsigned char d = (unsigned char) s[i + k];
            if ((d & 0xc0) != 0x80) ok = false;
            else cp = (cp << 6) | (d & 0x3f);
        }
        static const unsigned long minimum[5] = { 0, 0, 0x80, 0x800, 0x10000 };
        if (ok && (cp < minimum[len] || cp > 0x10ffff || (cp >= 0xd800 && cp <= 0xdfff))) ok = false;
        if (! ok) { w += (wchar_t) 0xfffd; ++i; continue; }
        if (cp >= 0x10000)
        {
            cp -= 0x10000;
            w += (wchar_t) (0xd800 + (cp >> 10));
            w += (wchar_t) (0xdc00 + (cp & 0x3ff));
        }
        else w += (wchar_t) cp;
        i += len;
    }
    return w;
}

} // namespace detail

inline std::FILE* open (const std::string& utf8Path, const char* mode)
{
#ifdef _WIN32
    const std::string m (mode);   // modes are ASCII
    return _wfopen (detail::toWide (utf8Path).c_str(), std::wstring (m.begin(), m.end()).c_str());
#else
    return std::fopen (utf8Path.c_str(), mode);
#endif
}

// atomic move of fromUtf8 over toUtf8, replacing it if it exists
inline bool replace (const std::string& fromUtf8, const std::string& toUtf8)
{
#ifdef _WIN32
    return MoveFileExW (detail::toWide (fromUtf8).c_str(), detail::toWide (toUtf8).c_str(),
                        0x1 | 0x8) != 0;   // MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH
#else
    return std::rename (fromUtf8.c_str(), toUtf8.c_str()) == 0;
#endif
}

inline bool remove (const std::string& utf8Path)
{
#ifdef _WIN32
    return _wremove (detail::toWide (utf8Path).c_str()) == 0;
#else
    return std::remove (utf8Path.c_str()) == 0;
#endif
}

}} // namespace recycler::file
