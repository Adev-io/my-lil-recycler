// Library.h: the scanner's per-library cache of Info, keyed by path + size + mtime, as one JSON file. No Rack dependency.
// Format: a JSON array, one flat object per file, keys named exactly as the Info fields; onsets and role are number arrays,
// minor is true/false. The reader is a strict recursive-descent parser for this schema (unknown keys of any JSON type are
// skipped, missing keys keep the Info defaults, a known key of the wrong type or any malformed input fails the whole parse).
// \uXXXX is read for the ASCII range only; non-ASCII UTF-8 bytes pass through raw in both directions.
// save() writes path + ".tmp" then file::replace()s it over path. Paths are UTF-8 (File.h).
// Numbers go through snprintf / strtod, which assume the "C" numeric locale.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include "File.h"
#include "Info.h"
#include <cerrno>
#include <cfloat>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#ifdef _WIN32
#include <io.h>
#else
#include <unistd.h>
#endif

namespace recycler { namespace library {

struct Library
{
    std::vector<Info> files;

    // ponytail: linear scan; add an unordered_map<path, index> if scans of large libraries feel slow
    const Info* find (const std::string& path, uint64_t size, int64_t mtime) const
    {
        for (size_t i = 0; i < files.size(); ++i)
            if (files[i].path == path) return files[i].size == size && files[i].mtime == mtime ? &files[i] : 0;
        return nullptr;
    }

    void put (const Info& info)
    {
        for (size_t i = 0; i < files.size(); ++i)
            if (files[i].path == info.path) { files[i] = info; return; }
        files.push_back (info);
    }
};

namespace detail {

inline void putStr (std::string& out, const std::string& s)
{
    out += '"';
    for (size_t i = 0; i < s.size(); ++i)
    {
        const unsigned char c = (unsigned char) s[i];
        if (c == '"') out += "\\\"";
        else if (c == '\\') out += "\\\\";
        else if (c == '\n') out += "\\n";
        else if (c == '\r') out += "\\r";
        else if (c == '\t') out += "\\t";
        else if (c < 0x20) { char b[8]; std::snprintf (b, sizeof b, "\\u%04x", (unsigned) c); out += b; }
        else out += (char) c;
    }
    out += '"';
}

inline void putF (std::string& out, float v)
{
    char b[32];
    std::snprintf (b, sizeof b, "%.9g", std::isfinite (v) ? (double) v : 0.0);   // nan/inf are not JSON
    out += b;
}

inline void putI (std::string& out, long long v) { char b[32]; std::snprintf (b, sizeof b, "%lld", v); out += b; }
inline void putU (std::string& out, unsigned long long v) { char b[32]; std::snprintf (b, sizeof b, "%llu", v); out += b; }

inline void key (std::string& out, const char* k, bool first = false)
{
    if (! first) out += ',';
    out += '"'; out += k; out += "\":";
}

struct Reader
{
    const char* p;
    const char* end;

    void ws() { while (p < end && (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r')) ++p; }
    bool eat (char c) { ws(); if (p < end && *p == c) { ++p; return true; } return false; }
    bool peek (char c) { ws(); return p < end && *p == c; }
    bool word (const char* w)
    {
        const size_t n = std::strlen (w);
        if ((size_t) (end - p) < n || std::strncmp (p, w, n) != 0) return false;
        p += n; return true;
    }

    static int hex (char c)
    {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'f') return c - 'a' + 10;
        if (c >= 'A' && c <= 'F') return c - 'A' + 10;
        return -1;
    }

    bool str (std::string& s)
    {
        if (! eat ('"')) return false;
        s.clear();
        while (p < end)
        {
            const unsigned char c = (unsigned char) *p++;
            if (c == '"') return true;
            if (c < 0x20) return false;
            if (c != '\\') { s += (char) c; continue; }
            if (p >= end) return false;
            const char e = *p++;
            if (e == '"' || e == '\\' || e == '/') s += e;
            else if (e == 'n') s += '\n';
            else if (e == 'r') s += '\r';
            else if (e == 't') s += '\t';
            else if (e == 'b') s += '\b';
            else if (e == 'f') s += '\f';
            else if (e == 'u')
            {
                if (end - p < 4) return false;
                int v = 0;
                for (int i = 0; i < 4; ++i) { const int h = hex (*p++); if (h < 0) return false; v = v * 16 + h; }
                if (v > 0x7f) return false;   // only the ASCII range is ever written
                s += (char) v;
            }
            else return false;
        }
        return false;   // unterminated
    }

    // scans one JSON number; integral = no fraction or exponent. Returns the span start or nullptr.
    const char* number (bool& integral)
    {
        ws();
        const char* s = p;
        if (p < end && *p == '-') ++p;
        if (p >= end || *p < '0' || *p > '9') return nullptr;
        if (*p == '0') ++p; else while (p < end && *p >= '0' && *p <= '9') ++p;
        integral = true;
        if (p < end && *p == '.')
        {
            ++p; integral = false;
            if (p >= end || *p < '0' || *p > '9') return nullptr;
            while (p < end && *p >= '0' && *p <= '9') ++p;
        }
        if (p < end && (*p == 'e' || *p == 'E'))
        {
            ++p; integral = false;
            if (p < end && (*p == '+' || *p == '-')) ++p;
            if (p >= end || *p < '0' || *p > '9') return nullptr;
            while (p < end && *p >= '0' && *p <= '9') ++p;
        }
        return s;
    }

    bool real (float& v)
    {
        bool integral; const char* s = number (integral);
        if (! s) return false;
        const double d = std::strtod (std::string (s, p).c_str(), nullptr);
        if (! std::isfinite (d) || std::fabs (d) > FLT_MAX) return false;   // 1e400 etc. would become inf
        v = (float) d;
        return true;
    }

    bool integer (long long& v)
    {
        bool integral; const char* s = number (integral);
        if (! s || ! integral) return false;
        errno = 0;
        v = std::strtoll (std::string (s, p).c_str(), nullptr, 10);
        return errno != ERANGE;
    }

    bool unsig (uint64_t& v)
    {
        bool integral; const char* s = number (integral);
        if (! s || ! integral || *s == '-') return false;
        errno = 0;
        v = std::strtoull (std::string (s, p).c_str(), nullptr, 10);
        return errno != ERANGE;
    }

    bool small (int& v)
    {
        long long w;
        if (! integer (w) || w < -2147483647ll - 1 || w > 2147483647ll) return false;
        v = (int) w; return true;
    }

    bool boolean (bool& v)
    {
        ws();
        if (word ("true")) { v = true; return true; }
        if (word ("false")) { v = false; return true; }
        return false;
    }

    bool reals (std::vector<float>& v)
    {
        v.clear();
        if (! eat ('[')) return false;
        if (eat (']')) return true;
        do { float x; if (! real (x)) return false; v.push_back (x); } while (eat (','));
        return eat (']');
    }

    // skips any JSON value (unknown keys); depth-capped so hostile nesting cannot blow the stack
    bool skip (int depth = 0)
    {
        if (depth > 32) return false;
        ws();
        if (p >= end) return false;
        if (*p == '"') { std::string s; return str (s); }
        if (*p == '[')
        {
            ++p;
            if (eat (']')) return true;
            do { if (! skip (depth + 1)) return false; } while (eat (','));
            return eat (']');
        }
        if (*p == '{')
        {
            ++p;
            if (eat ('}')) return true;
            do { std::string k; if (! str (k) || ! eat (':') || ! skip (depth + 1)) return false; } while (eat (','));
            return eat ('}');
        }
        if (word ("true") || word ("false") || word ("null")) return true;
        bool integral; return number (integral) != nullptr;
    }

    bool field (const std::string& k, Info& f)
    {
        long long w;
        if (k == "path") return str (f.path);
        if (k == "size") return unsig (f.size);
        if (k == "mtime") { if (! integer (w)) return false; f.mtime = w; return true; }
        if (k == "sampleRate") return small (f.sampleRate);
        if (k == "frames") { if (! integer (w)) return false; f.frames = w; return true; }
        if (k == "seconds") return real (f.seconds);
        if (k == "tempo") return real (f.tempo);
        if (k == "tempoConf") return real (f.tempoConf);
        if (k == "bars") return small (f.bars);
        if (k == "key") return small (f.key);
        if (k == "minor") return boolean (f.minor);
        if (k == "keyConf") return real (f.keyConf);
        if (k == "onsets") return reals (f.onsets);
        if (k == "bestOnset") return real (f.bestOnset);
        if (k == "role")
        {
            std::vector<float> r;
            if (! reals (r) || r.size() != 4) return false;
            for (int i = 0; i < 4; ++i) f.role[i] = r[i];
            return true;
        }
        if (k == "rms") return real (f.rms);
        if (k == "peak") return real (f.peak);
        return skip();
    }

    bool info (Info& f)
    {
        if (! eat ('{')) return false;
        if (eat ('}')) return true;
        do { std::string k; if (! str (k) || ! eat (':') || ! field (k, f)) return false; } while (eat (','));
        return eat ('}');
    }
};

} // namespace detail

inline std::string toJson (const Library& lib)
{
    using namespace detail;
    std::string out;
    out.reserve (64 + lib.files.size() * 512);
    out += '[';
    for (size_t i = 0; i < lib.files.size(); ++i)
    {
        const Info& f = lib.files[i];
        out += i ? ",\n{" : "\n{";
        key (out, "path", true); putStr (out, f.path);
        key (out, "size"); putU (out, f.size);
        key (out, "mtime"); putI (out, f.mtime);
        key (out, "sampleRate"); putI (out, f.sampleRate);
        key (out, "frames"); putI (out, f.frames);
        key (out, "seconds"); putF (out, f.seconds);
        key (out, "tempo"); putF (out, f.tempo);
        key (out, "tempoConf"); putF (out, f.tempoConf);
        key (out, "bars"); putI (out, f.bars);
        key (out, "key"); putI (out, f.key);
        key (out, "minor"); out += f.minor ? "true" : "false";
        key (out, "keyConf"); putF (out, f.keyConf);
        key (out, "onsets"); out += '[';
        for (size_t j = 0; j < f.onsets.size(); ++j) { if (j) out += ','; putF (out, f.onsets[j]); }
        out += ']';
        key (out, "bestOnset"); putF (out, f.bestOnset);
        key (out, "role"); out += '[';
        for (int r = 0; r < 4; ++r) { if (r) out += ','; putF (out, f.role[r]); }
        out += ']';
        key (out, "rms"); putF (out, f.rms);
        key (out, "peak"); putF (out, f.peak);
        out += '}';
    }
    out += "\n]\n";
    return out;
}

inline bool fromJson (const std::string& text, Library& lib)
{
    detail::Reader r = { text.data(), text.data() + text.size() };
    std::vector<Info> files;
    if (! r.eat ('[')) return false;
    if (! r.eat (']'))
    {
        do { Info f; if (! r.info (f)) return false; files.push_back (f); } while (r.eat (','));
        if (! r.eat (']')) return false;
    }
    r.ws();
    if (r.p != r.end) return false;   // trailing garbage
    lib.files.swap (files);
    return true;
}

inline bool save (const Library& lib, const std::string& path)
{
    const std::string json = toJson (lib);
    const std::string tmp = path + ".tmp";
    std::FILE* f = file::open (tmp, "wb");
    if (! f) return false;
    bool wrote = std::fwrite (json.data(), 1, json.size(), f) == json.size() && std::fflush (f) == 0;
#ifdef _WIN32
    wrote = wrote && _commit (_fileno (f)) == 0;   // on disk before the rename, so a power cut cannot leave an empty target
#else
    wrote = wrote && fsync (fileno (f)) == 0;
#endif
    const bool closed = std::fclose (f) == 0;
    const bool moved = wrote && closed && file::replace (tmp, path);
    if (! moved) file::remove (tmp);
    return moved;
}

inline bool load (const std::string& path, Library& lib)
{
    std::FILE* f = file::open (path, "rb");
    if (! f) return false;
    std::string text;
    char buf[65536];
    size_t n;
    while ((n = std::fread (buf, 1, sizeof buf, f)) > 0) text.append (buf, n);
    const bool bad = std::ferror (f) != 0;
    std::fclose (f);
    return ! bad && fromJson (text, lib);
}

}} // namespace recycler::library
