// test_audio.h: Audio.h against files written here byte by byte (WAV, AIFF, AIFC), plus mono mix and resampling.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include "check.h"
#include "Audio.h"
#include "File.h"
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#ifdef _WIN32
#include <direct.h>
#else
#include <sys/stat.h>
#endif

namespace audiotest
{
typedef std::vector<unsigned char> Bytes;
const std::string dir = "../build/audio/";

inline void le (Bytes& b, uint64_t v, int n) { for (int i = 0; i < n; ++i) b.push_back ((unsigned char) (v >> (8 * i))); }
inline void be (Bytes& b, uint64_t v, int n) { for (int i = n - 1; i >= 0; --i) b.push_back ((unsigned char) (v >> (8 * i))); }
inline void tag (Bytes& b, const char* s) { b.insert (b.end(), s, s + 4); }
inline void putLe32 (Bytes& b, size_t at, uint32_t v) { for (int i = 0; i < 4; ++i) b[at + i] = (unsigned char) (v >> (8 * i)); }
inline void putBe32 (Bytes& b, size_t at, uint32_t v) { for (int i = 0; i < 4; ++i) b[at + i] = (unsigned char) (v >> (24 - 8 * i)); }
inline int32_t bitsOf (float x) { int32_t v; std::memcpy (&v, &x, 4); return v; }
inline size_t find4 (const Bytes& b, const char* id)   // index of the first 4-byte id, or b.size()
{
    for (size_t i = 0; i + 4 <= b.size(); ++i) if (std::memcmp (&b[i], id, 4) == 0) return i;
    return b.size();
}

inline std::string save (const std::string& name, const Bytes& b)   // name is UTF-8
{
    const std::string path = dir + name;
    std::FILE* f = recycler::file::open (path, "wb");
    if (f) { if (! b.empty()) std::fwrite (b.data(), 1, b.size(), f); std::fclose (f); }
    return path;
}

// RIFF/WAVE with an odd-sized JUNK chunk first (exercises the pad byte). s: interleaved raw sample values, each written in
// (bits + 7) / 8 little-endian bytes. dataFirst puts the data chunk before fmt.
inline Bytes wav (int fmtTag, int bits, int ch, int sr, const std::vector<int32_t>& s, bool extensible = false, bool dataFirst = false)
{
    const int bytes = (bits + 7) / 8;
    Bytes fmt, data;
    tag (fmt, "fmt "); le (fmt, extensible ? 40 : 16, 4);
    le (fmt, extensible ? 0xFFFE : fmtTag, 2); le (fmt, ch, 2); le (fmt, sr, 4); le (fmt, sr * ch * bytes, 4); le (fmt, ch * bytes, 2); le (fmt, bits, 2);
    if (extensible)
    {
        static const unsigned char guidTail[14] = { 0, 0, 0, 0, 0x10, 0, 0x80, 0, 0, 0xAA, 0, 0x38, 0x9B, 0x71 };
        le (fmt, 22, 2); le (fmt, bits, 2); le (fmt, ch == 2 ? 3 : 4, 4); le (fmt, fmtTag, 2); fmt.insert (fmt.end(), guidTail, guidTail + 14);
    }
    tag (data, "data"); le (data, s.size() * bytes, 4);
    for (size_t i = 0; i < s.size(); ++i) le (data, (uint32_t) s[i], bytes);
    if ((s.size() * bytes) & 1) data.push_back (0);
    Bytes b;
    tag (b, "RIFF"); le (b, 0, 4); tag (b, "WAVE");
    tag (b, "JUNK"); le (b, 3, 4); b.push_back (1); b.push_back (2); b.push_back (3); b.push_back (0);
    const Bytes& first = dataFirst ? data : fmt;
    const Bytes& second = dataFirst ? fmt : data;
    b.insert (b.end(), first.begin(), first.end()); b.insert (b.end(), second.begin(), second.end());
    putLe32 (b, 4, (uint32_t) (b.size() - 8));
    return b;
}

// 80-bit IEEE extended for a positive integer rate.
inline void ext80 (Bytes& b, int rate)
{
    int e = 0;
    while ((rate >> (e + 1)) != 0) ++e;
    be (b, 16383 + e, 2); be (b, (uint64_t) rate << (63 - e), 8);
}

// FORM/AIFF, or FORM/AIFC when comp is given (then SSND comes before COMM, which a reader must accept). Samples in
// (bits + 7) / 8 bytes, big-endian except for 'sowt'. commFrames >= 0 overrides COMM's frame count; ssndOffset bytes of
// filler go between SSND's offset/blockSize and the samples.
inline Bytes aiff (int bits, int ch, int sr, const std::vector<int32_t>& s, const char* comp = nullptr, int64_t commFrames = -1,
                   int ssndOffset = 0)
{
    const int bytes = (bits + 7) / 8;
    const bool sowt = comp && std::memcmp (comp, "sowt", 4) == 0;
    Bytes d;
    for (size_t i = 0; i < s.size(); ++i) { if (sowt) le (d, (uint32_t) s[i], bytes); else be (d, (uint32_t) s[i], bytes); }
    Bytes comm, ssnd;
    tag (comm, "COMM"); be (comm, comp ? 24 : 18, 4);
    be (comm, ch, 2); be (comm, commFrames >= 0 ? (uint64_t) commFrames : (uint64_t) (s.size() / ch), 4); be (comm, bits, 2); ext80 (comm, sr);
    if (comp) { tag (comm, comp); comm.push_back (0); comm.push_back (0); }   // empty pascal-string name + pad
    tag (ssnd, "SSND"); be (ssnd, 8 + ssndOffset + d.size(), 4); be (ssnd, ssndOffset, 4); be (ssnd, 0, 4);
    ssnd.insert (ssnd.end(), (size_t) ssndOffset, (unsigned char) 0xEE);
    ssnd.insert (ssnd.end(), d.begin(), d.end());
    if ((ssndOffset + d.size()) & 1) ssnd.push_back (0);
    Bytes b;
    tag (b, "FORM"); be (b, 0, 4); tag (b, comp ? "AIFC" : "AIFF");
    if (comp) { tag (b, "FVER"); be (b, 4, 4); be (b, 0xA2805140u, 4); }
    const Bytes& first = comp ? ssnd : comm;
    const Bytes& second = comp ? comm : ssnd;
    b.insert (b.end(), first.begin(), first.end()); b.insert (b.end(), second.begin(), second.end());
    putBe32 (b, 4, (uint32_t) (b.size() - 8));
    return b;
}

// Largest |got[i] - want[ch * i + c] * scale| over the frames, or 1e9 when the sizes disagree.
inline double maxErr (const std::vector<float>& got, const std::vector<int32_t>& want, int ch, int c, double scale)
{
    if (got.size() * ch != want.size()) return 1e9;
    double e = 0.0;
    for (size_t i = 0; i < got.size(); ++i) e = std::max (e, std::abs (got[i] - want[ch * i + c] * scale));
    return e;
}
// Both channels of a stereo read-back exact.
inline bool exact2 (const std::vector<float>& l, const std::vector<float>& r, const std::vector<int32_t>& want, double scale)
{
    return maxErr (l, want, 2, 0, scale) == 0.0 && maxErr (r, want, 2, 1, scale) == 0.0;
}
inline bool differ (const std::vector<float>& a, const std::vector<float>& b)
{
    for (size_t i = 0; i < a.size() && i < b.size(); ++i) if (a[i] != b[i]) return true;
    return false;
}
}

void testAudio()
{
    using namespace audiotest;
    namespace au = recycler::audio;
#ifdef _WIN32
    _mkdir ("../build"); _mkdir (dir.c_str());
#else
    mkdir ("../build", 0755); mkdir (dir.c_str(), 0755);
#endif
    std::vector<float> l, r;
    int sr = 0;
    bool ok = false;
    const double q8 = 1.0 / 128, q16 = 1.0 / 32768, q24 = 1.0 / 8388608, q32 = 1.0 / 2147483648.0;

    // WAV PCM16 stereo
    const std::vector<int32_t> s16 = { 0, 1000, 16384, -16384, -32768, 32767, 32767, -32768, -1, 7 };
    ok = au::read (save ("pcm16.wav", wav (1, 16, 2, 44100, s16)), l, r, sr);
    check (ok && sr == 44100 && l.size() == 5, "wav pcm16 stereo: reads 5 frames at 44100", (double) l.size());
    check (exact2 (l, r, s16, q16), "wav pcm16: both channels exact", maxErr (l, s16, 2, 0, q16));
    check (differ (l, r), "wav pcm16: stereo channels distinct");

    // Frame ranges
    ok = au::read (dir + "pcm16.wav", l, r, sr, 2);
    check (ok && l.size() == 2 && r.size() == 2 && l[1] == 16384.0 / 32768, "wav maxFrames 2 keeps the first 2 frames", (double) l.size());
    std::vector<int32_t> ramp16;
    for (int i = 0; i < 8; ++i) { ramp16.push_back (1000 * i); ramp16.push_back (-1000 * i - 1); }
    const std::string rampPath = save ("ramp16.wav", wav (1, 16, 2, 44100, ramp16));
    ok = au::read (rampPath, l, r, sr, 2, 3);
    check (ok && l.size() == 2 && l[0] == 3000.0 / 32768 && l[1] == 4000.0 / 32768 && r[0] == -3001.0 / 32768 && r[1] == -4001.0 / 32768,
           "read startFrame 3, maxFrames 2: exactly frames 3 and 4", (double) l.size());
    check (! au::read (rampPath, l, r, sr, INT64_MAX, 8), "read startFrame = total frames: false");
    check (! au::read (rampPath, l, r, sr, INT64_MAX, -1), "read startFrame < 0: false");
    check (! au::read (rampPath, l, r, sr, -5), "read maxFrames < 0: false");
    l.assign (1, 9.f); r.assign (1, 9.f); sr = 1234;
    ok = au::read (dir + "pcm16.wav", l, r, sr, 0);
    check (! ok && l.size() == 1 && l[0] == 9.f && r[0] == 9.f && sr == 1234, "maxFrames 0: false, outputs untouched", (double) l.size());

    // WAV PCM24 mono
    const std::vector<int32_t> s24 = { 0, 4194304, -8388608, 8388607, -3, 12345 };
    ok = au::read (save ("pcm24.wav", wav (1, 24, 1, 48000, s24)), l, r, sr);
    check (ok && sr == 48000 && l.size() == 6, "wav pcm24 mono: reads 6 frames at 48000", (double) l.size());
    check (maxErr (l, s24, 1, 0, q24) == 0.0, "wav pcm24: exact (sign extended)", maxErr (l, s24, 1, 0, q24));
    check (! differ (l, r) && r.size() == l.size(), "wav pcm24 mono fills both channels");

    // WAV PCM32 stereo (float keeps 24 bits of it)
    const std::vector<int32_t> s32 = { 0, INT32_MIN, INT32_MAX, 65536, -65536, 1 << 30 };
    ok = au::read (save ("pcm32.wav", wav (1, 32, 2, 44100, s32)), l, r, sr);
    check (ok && l.size() == 3 && maxErr (l, s32, 2, 0, q32) <= 6e-8 && maxErr (r, s32, 2, 1, q32) <= 6e-8,
           "wav pcm32 stereo: within float precision", maxErr (r, s32, 2, 1, q32));

    // WAV float32 stereo, clamping, NaN / Inf
    const float fv[8] = { 0.5f, -0.25f, 1.f, -1.f, 0.f, 0.125f, -0.75f, 0.333f };
    std::vector<int32_t> sf;
    for (int i = 0; i < 8; ++i) sf.push_back (bitsOf (fv[i]));
    ok = au::read (save ("float.wav", wav (3, 32, 2, 96000, sf)), l, r, sr);
    bool exact = ok && l.size() == 4;
    for (size_t i = 0; exact && i < 4; ++i) exact = l[i] == fv[2 * i] && r[i] == fv[2 * i + 1];
    check (exact && sr == 96000, "wav float32 stereo: sample-exact at 96000", (double) l.size());
    const std::vector<int32_t> huge = { bitsOf (3.4e38f), bitsOf (-3.4e38f), bitsOf (65.f), bitsOf (-63.f) };
    ok = au::read (save ("huge.wav", wav (3, 32, 2, 44100, huge)), l, r, sr);
    check (ok && l.size() == 2 && l[0] == 64.f && r[0] == -64.f && l[1] == 64.f && r[1] == -63.f, "wav float32: clamped to +-64",
           ok ? (double) l[0] : 0.0);
    const std::vector<int32_t> bad = { 0x7FC00000, 0x7F800000, (int32_t) 0xFF800000u, bitsOf (0.5f) };
    ok = au::read (save ("nan.wav", wav (3, 32, 1, 44100, bad)), l, r, sr);
    check (ok && l.size() == 4 && l[0] == 0.f && l[1] == 0.f && l[2] == 0.f && l[3] == 0.5f, "wav float32: NaN and +-Inf read as 0");

    // WAV extensible wrapping PCM16 stereo, and wrapping float32
    ok = au::read (save ("ext16.wav", wav (1, 16, 2, 22050, s16, true)), l, r, sr);
    check (ok && sr == 22050 && exact2 (l, r, s16, q16), "wav extensible pcm16: exact", (double) l.size());
    ok = au::read (save ("extf.wav", wav (3, 32, 2, 44100, sf, true)), l, r, sr);
    check (ok && l.size() == 4 && l[3] == fv[6] && r[3] == fv[7], "wav extensible float32: sample-exact", (double) l.size());

    // WAV 8-bit: unsigned, 128 = 0
    const std::vector<int32_t> s8u = { 128, 255, 0, 192, 64 };
    const float want8u[5] = { 0.f, 127.f / 128, -1.f, 0.5f, -0.5f };
    ok = au::read (save ("pcm8.wav", wav (1, 8, 1, 8000, s8u)), l, r, sr);
    bool good = ok && l.size() == 5;
    for (size_t i = 0; good && i < 5; ++i) good = l[i] == want8u[i] && r[i] == l[i];
    check (good, "wav 8-bit unsigned: 128 is 0, exact", (double) l.size());

    // WAV 20-bit in 3 bytes, left-justified
    const std::vector<int32_t> v20 = { 0, 524287, -524288, 12345, -1, 300000 };
    std::vector<int32_t> s20;
    for (size_t i = 0; i < v20.size(); ++i) s20.push_back (v20[i] * 16);
    ok = au::read (save ("pcm20.wav", wav (1, 20, 2, 44100, s20)), l, r, sr);
    check (ok && l.size() == 3 && exact2 (l, r, v20, 1.0 / 524288), "wav 20-bit in 3 bytes: exact to 2^-19", maxErr (l, v20, 2, 0, 1.0 / 524288));

    // WAV chunk order and broken fmt / data
    ok = au::read (save ("datafirst.wav", wav (1, 16, 2, 44100, s16, false, true)), l, r, sr);
    check (ok && exact2 (l, r, s16, q16), "wav data chunk before fmt: still decodes", (double) l.size());
    check (! au::read (save ("nodata.wav", wav (1, 16, 2, 44100, std::vector<int32_t>())), l, r, sr), "wav 0-byte data chunk: false");
    Bytes align = wav (1, 16, 2, 44100, s16);
    align[find4 (align, "fmt ") + 8 + 12] = 6;   // blockAlign 6 for 16-bit stereo
    check (! au::read (save ("align.wav", align), l, r, sr), "wav blockAlign mismatch: false");

    // AIFF 16-bit stereo, big-endian, 48000 from the 80-bit extended
    ok = au::read (save ("pcm16.aiff", aiff (16, 2, 48000, s16)), l, r, sr);
    check (ok && sr == 48000 && l.size() == 5, "aiff 16 stereo: reads 5 frames at 48000", (double) sr);
    check (exact2 (l, r, s16, q16) && differ (l, r), "aiff 16: both channels exact, distinct", maxErr (l, s16, 2, 0, q16));

    // UTF-8 path (é and 音), written and read through file::open
    ok = au::read (save ("caf\xC3\xA9_\xE9\x9F\xB3.wav", wav (1, 16, 2, 44100, s16)), l, r, sr);
    check (ok && exact2 (l, r, s16, q16), "wav at a UTF-8 path (e-acute, CJK): reads back exact", (double) l.size());

    // AIFF 32-bit stereo, 24-bit mono, 12-bit in 2 bytes, 8-bit signed
    ok = au::read (save ("pcm32.aiff", aiff (32, 2, 44100, s32)), l, r, sr);
    check (ok && l.size() == 3 && maxErr (l, s32, 2, 0, q32) <= 6e-8 && maxErr (r, s32, 2, 1, q32) <= 6e-8,
           "aiff 32 stereo: within float precision", (double) l.size());
    ok = au::read (save ("pcm24.aif", aiff (24, 1, 44100, s24)), l, r, sr);
    check (ok && sr == 44100 && maxErr (l, s24, 1, 0, q24) == 0.0, "aiff 24 mono: 44100, exact", (double) sr);
    check (! differ (l, r) && r.size() == 6, "aiff 24 mono fills both channels", (double) r.size());
    const std::vector<int32_t> v12 = { 0, 2047, -2048, 1000 };
    std::vector<int32_t> s12;
    for (size_t i = 0; i < v12.size(); ++i) s12.push_back (v12[i] * 16);
    ok = au::read (save ("pcm12.aiff", aiff (12, 1, 44100, s12)), l, r, sr);
    check (ok && maxErr (l, v12, 1, 0, 1.0 / 2048) == 0.0, "aiff 12-bit in 2 bytes: exact to 2^-11", maxErr (l, v12, 1, 0, 1.0 / 2048));
    const std::vector<int32_t> s8 = { 0, 127, -128, 64, -64 };
    ok = au::read (save ("pcm8.aiff", aiff (8, 1, 22050, s8)), l, r, sr);
    check (ok && sr == 22050 && maxErr (l, s8, 1, 0, q8) == 0.0, "aiff 8-bit signed: exact", maxErr (l, s8, 1, 0, q8));

    // AIFC sowt (little-endian), SSND before COMM
    ok = au::read (save ("sowt.aifc", aiff (16, 2, 96000, s16, "sowt")), l, r, sr);
    check (ok && sr == 96000 && exact2 (l, r, s16, q16), "aifc sowt 16 stereo: 96000, exact", (double) l.size());
    ok = au::read (save ("sowt24.aifc", aiff (24, 2, 44100, s24, "sowt")), l, r, sr);
    check (ok && l.size() == 3 && exact2 (l, r, s24, q24), "aifc sowt 24 stereo: exact", (double) l.size());
    ok = au::read (save ("sowt8.aifc", aiff (8, 1, 22050, s8, "sowt")), l, r, sr);
    check (ok && l.size() == 5 && maxErr (l, s8, 1, 0, q8) == 0.0, "aifc sowt 8 mono: exact", (double) l.size());
    ok = au::read (save ("sowt32.aifc", aiff (32, 2, 48000, s32, "sowt")), l, r, sr);
    check (ok && l.size() == 3 && maxErr (l, s32, 2, 0, q32) <= 6e-8 && maxErr (r, s32, 2, 1, q32) <= 6e-8,
           "aifc sowt 32 stereo: within float precision", (double) l.size());

    // AIFC big-endian variants: NONE, twos, in24, fl32
    ok = au::read (save ("none.aifc", aiff (24, 2, 44100, s24, "NONE")), l, r, sr);
    check (ok && l.size() == 3 && exact2 (l, r, s24, q24), "aifc NONE 24 stereo: exact", (double) l.size());
    ok = au::read (save ("none8.aifc", aiff (8, 1, 44100, s8, "NONE")), l, r, sr);   // 5 bytes: odd SSND, then a pad byte before COMM
    check (ok && l.size() == 5 && maxErr (l, s8, 1, 0, q8) == 0.0, "aifc NONE 8 mono, odd-length SSND: exact", (double) l.size());
    ok = au::read (save ("twos.aifc", aiff (16, 2, 44100, s16, "twos")), l, r, sr);
    check (ok && exact2 (l, r, s16, q16), "aifc twos 16 stereo: exact", (double) l.size());
    ok = au::read (save ("in24.aifc", aiff (24, 2, 44100, s24, "in24")), l, r, sr);
    check (ok && exact2 (l, r, s24, q24), "aifc in24 stereo: exact", (double) l.size());
    ok = au::read (save ("fl32.aifc", aiff (32, 2, 44100, sf, "fl32")), l, r, sr);
    exact = ok && l.size() == 4;
    for (size_t i = 0; exact && i < 4; ++i) exact = l[i] == fv[2 * i] && r[i] == fv[2 * i + 1];
    check (exact, "aifc fl32 stereo (big-endian float): sample-exact", (double) l.size());

    // AIFF COMM frames fewer than SSND holds: min wins; nonzero SSND offset
    ok = au::read (save ("commshort.aiff", aiff (16, 2, 44100, s16, nullptr, 3)), l, r, sr);
    check (ok && l.size() == 3 && l[2] == s16[4] * q16 && r[2] == s16[5] * q16, "aiff COMM frames < SSND frames: COMM wins", (double) l.size());
    ok = au::read (save ("offset.aiff", aiff (16, 2, 44100, s16, nullptr, -1, 4)), l, r, sr);
    check (ok && exact2 (l, r, s16, q16), "aiff SSND offset 4: decodes after the offset", (double) l.size());

    // Truncated files: data chunk cut short
    Bytes cut = wav (1, 16, 2, 44100, s16);
    cut.resize (cut.size() - 6);
    check (! au::read (save ("cut.wav", cut), l, r, sr), "truncated wav: false");
    cut = aiff (16, 2, 44100, s16);
    cut.resize (cut.size() - 6);
    check (! au::read (save ("cut.aiff", cut), l, r, sr), "truncated aiff: false");

    // Not audio, empty, missing
    const char* text = "hello, this is not a wav file at all, just text\n";
    const std::string textPath = save ("text.wav", Bytes (text, text + std::strlen (text)));
    check (! au::read (textPath, l, r, sr), "text file: false");
    check (! au::read (save ("empty.wav", Bytes()), l, r, sr), "0-byte file: false");
    check (! au::read (dir + "missing.wav", l, r, sr), "missing file: false");

    // Unsupported variants
    check (! au::read (save ("ch3.wav", wav (1, 16, 3, 44100, std::vector<int32_t> (9, 0))), l, r, sr), "wav 3 channels: false");
    check (! au::read (save ("bits0.wav", wav (1, 0, 1, 44100, std::vector<int32_t> (4, 0))), l, r, sr), "wav 0-bit: false");
    check (! au::read (save ("bits40.wav", wav (1, 40, 1, 44100, std::vector<int32_t> (4, 0))), l, r, sr), "wav 40-bit: false");
    check (! au::read (save ("bits40.aiff", aiff (40, 1, 44100, std::vector<int32_t> (4, 0))), l, r, sr), "aiff 40-bit: false");
    check (! au::read (save ("ima4.aifc", aiff (16, 1, 44100, std::vector<int32_t> (4, 0), "ima4")), l, r, sr), "aifc ima4: false");
    check (! au::read (save ("rate.wav", wav (1, 16, 1, 500, std::vector<int32_t> (4, 0))), l, r, sr), "wav rate 500: false");

    // probe: header only
    int psr = 0, pch = 0;
    int64_t pframes = 0;
    ok = au::probe (dir + "pcm16.wav", psr, pframes, pch);
    check (ok && psr == 44100 && pframes == 5 && pch == 2, "probe wav pcm16 stereo: 44100, 5 frames, 2 ch", (double) pframes);
    ok = au::probe (dir + "float.wav", psr, pframes, pch);
    check (ok && psr == 96000 && pframes == 4 && pch == 2, "probe wav float32: 96000, 4 frames, 2 ch", (double) pframes);
    ok = au::probe (dir + "pcm24.aif", psr, pframes, pch);
    check (ok && psr == 44100 && pframes == 6 && pch == 1, "probe aiff 24 mono: 44100, 6 frames, 1 ch", (double) pframes);
    ok = au::probe (dir + "sowt.aifc", psr, pframes, pch);
    check (ok && psr == 96000 && pframes == 5 && pch == 2, "probe aifc sowt: 96000, 5 frames, 2 ch", (double) pframes);
    check (! au::probe (textPath, psr, pframes, pch), "probe text file: false");

    // Mini fuzz: single-byte mutations and truncations of valid files (seeded xorshift32)
    const Bytes seeds[3] = { wav (1, 16, 2, 44100, s16), wav (1, 16, 2, 22050, s16, true), aiff (16, 2, 48000, s16) };
    uint32_t x = 2463534242u;
    int runs = 0, accepted = 0, wrong = 0;
    for (int s = 0; s < 3; ++s)
        for (int it = 0; it < 200; ++it)
        {
            Bytes m = seeds[s];
            x ^= x << 13; x ^= x >> 17; x ^= x << 5;
            const uint32_t a = x;
            x ^= x << 13; x ^= x >> 17; x ^= x << 5;
            if (a % 4 == 0) m.resize (x % m.size());
            else m[a % m.size()] = (unsigned char) x;
            // one name per file: rewriting a single name 600 times raced something outside the test on Windows
            // (antivirus, most likely) and now and then read a stale copy
            const std::string path = save ("fuzz_" + std::to_string (s) + "_" + std::to_string (it) + ".bin", m);
            const bool got = au::read (path, l, r, sr);
            if (got && (l.size() != r.size() || l.empty() || sr < 1000 || sr > 768000)) ++wrong;
            if (au::probe (path, psr, pframes, pch) != got) ++wrong;
            accepted += got;
            ++runs;
        }
    check (runs == 600 && wrong == 0, "mini fuzz: 600 mutated files, no crash, accepted ones sane, probe agrees", (double) accepted);

    // isAudioPath
    check (au::isAudioPath ("x.WAV") && au::isAudioPath ("y.aiff") && au::isAudioPath ("z.Aif") && au::isAudioPath ("w.aifc")
           && au::isAudioPath ("dir/v.Wave"), "isAudioPath: .WAV .aiff .Aif .aifc .Wave");
    check (! au::isAudioPath ("a.mp3") && ! au::isAudioPath ("b.wav.txt") && ! au::isAudioPath ("wav") && ! au::isAudioPath ("c.wav/"),
           "isAudioPath: false for .mp3, .wav.txt, no extension");

    // resample to exactly n frames: first and last samples exactly the input's
    std::vector<float> wave (100);
    for (size_t i = 0; i < wave.size(); ++i) wave[i] = std::sin (0.1f * i) + 0.01f * i;
    const std::vector<float> up = au::resample (wave, (size_t) 250), down = au::resample (wave, (size_t) 37);
    check (up.size() == 250 && up[0] == wave[0] && up.back() == wave.back(), "resample up 100 -> 250: length, exact endpoints",
           up.empty() ? 0.0 : up.back() - wave.back());
    check (down.size() == 37 && down[0] == wave[0] && down.back() == wave.back(), "resample down 100 -> 37: length, exact endpoints",
           down.empty() ? 0.0 : down.back() - wave.back());
    std::vector<float> ramp (100);
    for (size_t i = 0; i < ramp.size(); ++i) ramp[i] = (float) i;
    const std::vector<float> half = au::resample (ramp, (size_t) 199);
    bool interior = half.size() == 199;
    for (size_t i = 0; interior && i < half.size(); ++i) interior = half[i] == 0.5f * i;
    check (interior, "resample ramp 0..99 -> 199: y[i] == i / 2 exactly", (double) half.size());
    const std::vector<float> one = au::resample (wave, (size_t) 1), four = au::resample (std::vector<float> (1, 0.7f), (size_t) 4);
    check (one.size() == 1 && one[0] == wave[0] && au::resample (std::vector<float>(), (size_t) 0).empty(), "resample to 1 and empty");
    check (four == std::vector<float> (4, 0.7f), "resample 1 frame -> 4 copies", four.empty() ? 0.0 : four[3]);

    // resample by rate: length = round(len * to / from)
    check (au::resample (std::vector<float> (1000, 0.f), 44100, 22050).size() == 500, "resample 44100 -> 22050 halves 1000",
           (double) au::resample (std::vector<float> (1000, 0.f), 44100, 22050).size());
    check (au::resample (std::vector<float> (441, 0.f), 44100, 48000).size() == 480, "resample 44100 -> 48000: 441 -> 480");
    check (au::resample (std::vector<float> (1001, 0.f), 48000, 44100).size() == 920, "resample 48000 -> 44100: 1001 -> 920");

    // toMono
    const std::vector<float> m = au::toMono (std::vector<float> (1, 1.f), std::vector<float> (1, -1.f));
    check (m.size() == 1 && m[0] == 0.f, "toMono (1, -1) = 0");
    const std::vector<float> m2 = au::toMono (std::vector<float> (1, 0.5f), std::vector<float> (1, 0.25f));
    check (m2.size() == 1 && m2[0] == 0.375f, "toMono (0.5, 0.25) = 0.375");
    const std::vector<float> m3 = au::toMono (std::vector<float> (5, 1.f), std::vector<float> (3, 1.f));
    check (m3.size() == 3 && m3[2] == 1.f, "toMono of 5 and 3 frames: 3 frames", (double) m3.size());
}
