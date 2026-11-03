// View.h: what the deck display draws. The loop envelope (peak / RMS in BINS bins), the parts of a crate file name
// (<n>-<stem>-<NN>[_<section>][-<tag>].wav), section kinds for colour, and the crate's own crate.json.
// No Rack dependency. Author: Ari Klopfer / A_Development. MIT
#pragma once
#include "Library.h"
#include <algorithm>
#include <cctype>
#include <cmath>
#include <string>
#include <utility>
#include <vector>

namespace recycler { namespace view {

const int BINS = 128;

// peak |x| and RMS of (l + r) / 2 per bin over the whole loop; every bin reads at least one frame when there are any
inline void envelope (const std::vector<float>& l, const std::vector<float>& r, float* pk, float* rms)
{
    const size_t n = std::min (l.size(), r.size());
    for (int b = 0; b < BINS; ++b)
    {
        pk[b] = rms[b] = 0.f;
        if (n == 0) continue;
        const size_t i0 = std::min (n - 1, (size_t) b * n / BINS), i1 = std::max (i0 + 1, (size_t) (b + 1) * n / BINS);
        double sum = 0.0;
        float peak = 0.f;
        for (size_t i = i0; i < i1; ++i)
        {
            const float m = 0.5f * (l[i] + r[i]);
            peak = std::max (peak, std::fabs (m));
            sum += (double) m * m;
        }
        pk[b] = peak;
        rms[b] = (float) std::sqrt (sum / (double) (i1 - i0));
    }
}

struct Name { std::string stem; int nn = -1; std::string section; };   // nn < 0: not a crate loop

// file name (no folders): the first '-' token after the stem that starts with digits is NN; "_x" after the digits is the
// section; the tokens before NN are the stem ("1-drums")
inline Name parseName (const std::string& fileName)
{
    Name out;
    std::string s = fileName.substr (0, fileName.rfind ('.'));
    std::vector<std::string> tok;
    for (size_t a = 0;;)
    {
        const size_t b = s.find ('-', a);
        tok.push_back (s.substr (a, b == std::string::npos ? std::string::npos : b - a));
        if (b == std::string::npos) break;
        a = b + 1;
    }
    for (size_t t = 1; t < tok.size(); ++t)
    {
        const std::string& x = tok[t];
        size_t d = 0;
        while (d < x.size() && std::isdigit ((unsigned char) x[d])) ++d;
        if (d == 0 || d > 4 || (d < x.size() && x[d] != '_')) continue;
        out.nn = std::atoi (x.substr (0, d).c_str());
        if (d < x.size()) out.section = x.substr (d + 1);
        for (size_t k = 0; k < t; ++k) out.stem += (k ? "-" : "") + tok[k];
        return out;
    }
    return out;
}

enum Kind { NONE, INTRO, VERSE, PRE, CHORUS, BRIDGE, SOLO, BREAK, OUTRO, OTHER, KINDS };

inline Kind sectionKind (const std::string& name)
{
    std::string s;
    for (char c : name) if (std::isalpha ((unsigned char) c)) s += (char) std::tolower ((unsigned char) c);
    if (s.empty()) return NONE;
    static const std::pair<const char*, Kind> PREFIX[] = {
        { "intro", INTRO }, { "verse", VERSE }, { "pre", PRE }, { "chorus", CHORUS }, { "hook", CHORUS }, { "refrain", CHORUS },
        { "bridge", BRIDGE }, { "middle", BRIDGE }, { "solo", SOLO }, { "inst", SOLO }, { "break", BREAK }, { "drop", BREAK },
        { "outro", OUTRO }, { "coda", OUTRO }, { "end", OUTRO } };
    for (const auto& p : PREFIX)
        if (s.compare (0, std::strlen (p.first), p.first) == 0) return p.second;
    return OTHER;
}

struct Crate
{
    std::string title, cover;
    std::vector<std::pair<int, std::string>> sections;   // NN -> section name
};

namespace detail {

inline void putUtf8 (std::string& s, unsigned v)
{
    if (v < 0x80) s += (char) v;
    else if (v < 0x800) { s += (char) (0xC0 | v >> 6); s += (char) (0x80 | (v & 0x3F)); }
    else if (v < 0x10000) { s += (char) (0xE0 | v >> 12); s += (char) (0x80 | (v >> 6 & 0x3F)); s += (char) (0x80 | (v & 0x3F)); }
    else { s += (char) (0xF0 | v >> 18); s += (char) (0x80 | (v >> 12 & 0x3F)); s += (char) (0x80 | (v >> 6 & 0x3F)); s += (char) (0x80 | (v & 0x3F)); }
}

// a JSON string with any \u escape (surrogate pairs too) as UTF-8; the library reader takes ASCII escapes only
inline bool str (library::detail::Reader& rd, std::string& s)
{
    if (! rd.eat ('"')) return false;
    s.clear();
    auto u4 = [&rd] (unsigned& v) {
        if (rd.end - rd.p < 4) return false;
        v = 0;
        for (int i = 0; i < 4; ++i) { const int h = library::detail::Reader::hex (*rd.p++); if (h < 0) return false; v = v * 16 + (unsigned) h; }
        return true;
    };
    while (rd.p < rd.end)
    {
        const unsigned char c = (unsigned char) *rd.p++;
        if (c == '"') return true;
        if (c < 0x20) return false;
        if (c != '\\') { s += (char) c; continue; }
        if (rd.p >= rd.end) return false;
        const char e = *rd.p++;
        unsigned v;
        if (e == '"' || e == '\\' || e == '/') s += e;
        else if (e == 'n') s += '\n';
        else if (e == 'r') s += '\r';
        else if (e == 't') s += '\t';
        else if (e == 'b') s += '\b';
        else if (e == 'f') s += '\f';
        else if (e == 'u' && u4 (v))
        {
            unsigned lo;
            if (v >= 0xD800 && v < 0xDC00 && rd.end - rd.p >= 6 && rd.p[0] == '\\' && rd.p[1] == 'u')
            {
                rd.p += 2;
                if (! u4 (lo) || lo < 0xDC00 || lo >= 0xE000) return false;
                v = 0x10000 + ((v - 0xD800) << 10) + (lo - 0xDC00);
            }
            putUtf8 (s, v);
        }
        else return false;
    }
    return false;
}

inline bool isNumberKey (const std::string& k)
{
    return ! k.empty() && k.size() <= 4 && std::all_of (k.begin(), k.end(), [] (char c) { return std::isdigit ((unsigned char) c) != 0; });
}

} // namespace detail

// crate.json. Every key is optional; a key with the wrong type, an unknown key, a section key that is not a number or a
// section value that is not a string is skipped. Broken JSON: false, and c is left empty.
inline bool parseCrate (const std::string& text, Crate& c)
{
    c = Crate();
    library::detail::Reader rd { text.data(), text.data() + text.size() };
    Crate out;
    bool ok = rd.eat ('{');
    if (ok && ! rd.eat ('}'))
    {
        do
        {
            std::string k;
            if (! (ok = detail::str (rd, k) && rd.eat (':'))) break;
            if ((k == "title" || k == "cover") && rd.peek ('"')) ok = detail::str (rd, k == "title" ? out.title : out.cover);
            else if (k == "sections" && rd.peek ('{'))
            {
                rd.eat ('{');
                if (rd.eat ('}')) continue;
                do
                {
                    std::string nn, name;
                    if (! (ok = detail::str (rd, nn) && rd.eat (':'))) break;
                    if (detail::isNumberKey (nn) && rd.peek ('"'))
                    {
                        ok = detail::str (rd, name);
                        out.sections.push_back (std::make_pair (std::atoi (nn.c_str()), name));
                    }
                    else ok = rd.skip();
                } while (ok && rd.eat (','));
                ok = ok && rd.eat ('}');
            }
            else ok = rd.skip();
        } while (ok && rd.eat (','));
        ok = ok && rd.eat ('}');
    }
    rd.ws();
    if (! ok || rd.p != rd.end) return false;
    c = out;
    return true;
}

// a loop's section: crate.json first, else the one in its file name
inline std::string sectionFor (const Crate& c, int nn, const std::string& fromName)
{
    for (const auto& s : c.sections)
        if (s.first == nn) return s.second;
    return fromName;
}

// reads <folder>/crate.json; no file or broken JSON: an empty crate
inline Crate readCrate (const std::string& folder)
{
    Crate c;
    std::FILE* f = file::open (folder + "/crate.json", "rb");
    if (! f) return c;
    std::string text;
    char buf[4096];
    size_t n;
    while (text.size() < (1u << 20) && (n = std::fread (buf, 1, sizeof buf, f)) > 0) text.append (buf, n);   // 1 MB is plenty
    std::fclose (f);
    parseCrate (text, c);
    return c;
}

}} // namespace recycler::view
