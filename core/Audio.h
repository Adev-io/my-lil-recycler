// Audio.h: WAV and AIFF/AIFC decoding to float (header probe, whole file or a frame range), mono mix and linear
// resampling. No Rack dependency.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include "File.h"
#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <memory>
#include <string>
#include <vector>

namespace recycler
{
namespace audio
{
namespace detail
{
inline uint32_t le16 (const uint8_t* p) { return (uint32_t) p[0] | (uint32_t) p[1] << 8; }
inline uint32_t le32 (const uint8_t* p) { return le16 (p) | le16 (p + 2) << 16; }
inline uint32_t be16 (const uint8_t* p) { return (uint32_t) p[0] << 8 | (uint32_t) p[1]; }
inline uint32_t be32 (const uint8_t* p) { return be16 (p) << 16 | be16 (p + 2); }

// How the sample data is laid out: interleaved frames of `channels` samples of `bytes` bytes each.
struct Layout
{
    int channels = 0, bytes = 0, sampleRate = 0;
    bool bigEndian = false, isFloat = false, unsigned8 = false;
};

inline bool valid (const Layout& f)
{
    return (f.channels == 1 || f.channels == 2) && f.bytes >= 1 && f.bytes <= 4 && f.sampleRate >= 1000 && f.sampleRate <= 768000;
}

// Bytes per sample for a bit depth of 1..32 (depths that are not a multiple of 8 are stored left-justified), else 0.
inline int depthBytes (uint32_t bits) { return bits >= 1 && bits <= 32 ? (int) (bits + 7) / 8 : 0; }

// One sample to float. Integers: bytes assembled most-significant first into the top of 32 bits (sign extension for
// free, left-justified depths need nothing more), scaled by 2^-31. Floats: NaN / infinity become 0, the rest is clamped
// to +-64 (garbage protection: a damaged file must not blow up the analysis or the output).
inline float sample (const uint8_t* p, const Layout& f)
{
    uint32_t u = 0;
    for (int i = 0; i < f.bytes; ++i) u |= (uint32_t) p[f.bigEndian ? i : f.bytes - 1 - i] << (24 - 8 * i);
    if (f.isFloat)
    {
        if ((u >> 23 & 0xFF) == 0xFF) return 0.f;
        float x;
        std::memcpy (&x, &u, 4);
        return std::max (-64.f, std::min (64.f, x));
    }
    if (f.unsigned8) u ^= 0x80000000u;
    return (float) ((double) (int32_t) u * (1.0 / 2147483648.0));
}

// WAV fmt chunk body (len bytes, at most the first 40 read into b): PCM 1..32-bit (8-bit and below unsigned), float32,
// or extensible wrapping either.
inline bool wavFormat (const uint8_t* b, uint32_t len, Layout& f)
{
    if (len < 16) return false;
    uint32_t tag = le16 (b);
    const uint32_t ch = le16 (b + 2), rate = le32 (b + 4), align = le16 (b + 12), bits = le16 (b + 14);
    if (tag == 0xFFFE)
    {
        if (len < 40) return false;
        tag = le16 (b + 24);   // the sub-format GUID's first two bytes
    }
    if (tag != 1 && ! (tag == 3 && bits == 32)) return false;
    f = Layout();
    f.channels = (int) std::min (ch, 3u);
    f.bytes = depthBytes (bits);
    f.sampleRate = (int) std::min (rate, 1000000u);
    f.isFloat = tag == 3;
    f.unsigned8 = f.bytes == 1;
    return valid (f) && align == ch * (uint32_t) f.bytes;
}

// AIFF sample rate: 80-bit IEEE extended (sign + 15-bit exponent, 64-bit mantissa with explicit integer bit), rounded;
// 0 when negative, not finite or outside 1 000..768 000.
inline int extendedRate (const uint8_t* p)
{
    const int expo = (int) (be16 (p) & 0x7FFF);
    if ((p[0] & 0x80) || expo < 16383 || expo > 16383 + 30) return 0;
    uint64_t m = 0;
    for (int i = 0; i < 8; ++i) m = m << 8 | p[2 + i];
    const double rate = std::ldexp ((double) m, expo - 16383 - 63);
    return rate >= 1000.0 && rate <= 768000.0 ? (int) std::lround (rate) : 0;
}

// AIFF/AIFC COMM chunk body (len bytes, at most the first 40 read into b): signed PCM 1..32-bit, big-endian (AIFF,
// AIFC 'NONE' / 'twos' / 'in24' / 'in32') or little-endian (AIFC 'sowt'), or AIFC 'fl32' / 'FL32' big-endian float32.
inline bool aiffFormat (const uint8_t* b, uint32_t len, bool aifc, Layout& f, uint32_t& frames)
{
    if (len < (aifc ? 22u : 18u)) return false;
    const uint32_t ch = be16 (b), bits = be16 (b + 6);
    frames = be32 (b + 2);
    f = Layout();
    f.channels = (int) std::min (ch, 3u);
    f.bytes = depthBytes (bits);
    f.sampleRate = extendedRate (b + 8);
    f.bigEndian = true;
    if (aifc)
    {
        const uint8_t* c = b + 18;
        if (std::memcmp (c, "sowt", 4) == 0) f.bigEndian = false;
        else if (std::memcmp (c, "fl32", 4) == 0 || std::memcmp (c, "FL32", 4) == 0) f.isFloat = true;
        else if (std::memcmp (c, "in24", 4) == 0) { if (bits != 24) return false; }
        else if (std::memcmp (c, "in32", 4) == 0) { if (bits != 32) return false; }
        else if (std::memcmp (c, "NONE", 4) != 0 && std::memcmp (c, "twos", 4) != 0) return false;
        if (f.isFloat && bits != 32) return false;
    }
    return valid (f);
}

// Walks the chunks (absolute seeks, every size checked against the file size) until both the format and the data chunk
// are found, so trailing junk does not matter. True when the layout is supported and at least one frame is there; then
// dataPos is where frame 0 starts and totalFrames the frame count.
inline bool parse (std::FILE* file, long size, Layout& f, uint64_t& dataPos, int64_t& totalFrames)
{
    uint8_t h[12];
    if (size < 12 || size >= INT32_MAX || std::fseek (file, 0, SEEK_SET) != 0 || std::fread (h, 1, 12, file) != 12) return false;
    const bool riff = std::memcmp (h, "RIFF", 4) == 0 && std::memcmp (h + 8, "WAVE", 4) == 0;
    const bool aifc = std::memcmp (h + 8, "AIFC", 4) == 0;
    const bool form = std::memcmp (h, "FORM", 4) == 0 && (aifc || std::memcmp (h + 8, "AIFF", 4) == 0);
    if (! riff && ! form) return false;

    uint32_t commFrames = 0;
    uint64_t dataLen = 0;
    bool haveFmt = false, haveData = false;
    for (uint64_t pos = 12; pos + 8 <= (uint64_t) size && ! (haveFmt && haveData);)
    {
        uint8_t c[8 + 40];   // chunk header + at most 40 bytes of body
        if (std::fseek (file, (long) pos, SEEK_SET) != 0 || std::fread (c, 1, 8, file) != 8) return false;
        const uint32_t len = riff ? le32 (c + 4) : be32 (c + 4);
        if (pos + 8 + len > (uint64_t) size) return false;   // chunk claims more than the file holds
        const size_t want = std::min (len, 40u);
        if (riff && std::memcmp (c, "fmt ", 4) == 0)
        {
            if (std::fread (c + 8, 1, want, file) != want || ! wavFormat (c + 8, len, f)) return false;
            haveFmt = true;
        }
        else if (form && std::memcmp (c, "COMM", 4) == 0)
        {
            if (std::fread (c + 8, 1, want, file) != want || ! aiffFormat (c + 8, len, aifc, f, commFrames)) return false;
            haveFmt = true;
        }
        else if (riff && std::memcmp (c, "data", 4) == 0)
        {
            dataPos = pos + 8;
            dataLen = len;
            haveData = true;
        }
        else if (form && std::memcmp (c, "SSND", 4) == 0)
        {
            if (len < 8 || std::fread (c + 8, 1, 8, file) != 8) return false;
            const uint32_t offset = be32 (c + 8);   // then blockSize, unused
            if (offset > len - 8) return false;
            dataPos = pos + 16 + offset;
            dataLen = len - 8 - offset;
            haveData = true;
        }
        pos += 8 + (uint64_t) len + (len & 1);
    }
    if (! haveFmt || ! haveData) return false;
    uint64_t frames = dataLen / ((uint64_t) f.bytes * f.channels);
    if (form) frames = std::min (frames, (uint64_t) commFrames);
    totalFrames = (int64_t) frames;
    return frames > 0;
}

// Decodes n frames from the current file position. Touches l and r only on success.
inline bool decode (std::FILE* file, const Layout& f, size_t n, std::vector<float>& l, std::vector<float>& r)
{
    std::vector<float> a, b;
    try { a.resize (n); b.resize (n); }
    catch (...) { return false; }
    const size_t frameBytes = (size_t) f.bytes * f.channels;
    uint8_t buf[8192];
    for (size_t i = 0; i < n;)   // in pieces: never the whole file at once
    {
        const size_t k = std::min (n - i, sizeof buf / frameBytes);
        if (std::fread (buf, frameBytes, k, file) != k) return false;
        for (size_t j = 0; j < k; ++j, ++i)
        {
            const uint8_t* p = buf + j * frameBytes;
            a[i] = sample (p, f);
            b[i] = f.channels == 2 ? sample (p + f.bytes, f) : a[i];
        }
    }
    l.swap (a);
    r.swap (b);
    return true;
}

typedef std::unique_ptr<std::FILE, int (*) (std::FILE*)> FilePtr;
inline FilePtr openRead (const std::string& path) { return FilePtr (file::open (path, "rb"), std::fclose); }
inline long sizeOf (std::FILE* file) { return std::fseek (file, 0, SEEK_END) == 0 ? std::ftell (file) : -1; }   // -1 past 2 GB where long is 32-bit
}

// Formats read and probed:
// WAV: RIFF/WAVE, fmt 1 (PCM 8-bit unsigned / 16 / 24 / 32-bit signed, and odd depths such as 12 or 20 stored
// left-justified in (bits + 7) / 8 bytes) or 3 (float32), or 0xFFFE WAVE_FORMAT_EXTENSIBLE wrapping either (sub-format
// GUID's first two bytes 1 or 3); mono or stereo.
// AIFF/AIFC: FORM/AIFF or FORM/AIFC with COMM + SSND chunks, signed PCM 8/16/24/32-bit (odd depths left-justified)
// big-endian, AIFC compression 'NONE' / 'twos' / 'in24' / 'in32' (big-endian), 'sowt' (little-endian), 'fl32' / 'FL32'
// (big-endian float32). Sample rate is the 80-bit IEEE extended in COMM.
// Float samples: NaN / infinity read as 0, the rest clamped to +-64. Anything else is false. read and probe never throw,
// never read past the file and never allocate more than the data chunk claims and the file can hold. Paths are UTF-8.

// Header only, no sample decoding: rate, frame count and channel count (1 or 2). Outputs change only on success.
inline bool probe (const std::string& path, int& sampleRate, int64_t& frames, int& channels)
{
    const detail::FilePtr f = detail::openRead (path);
    detail::Layout fmt;
    uint64_t dataPos = 0;
    int64_t total = 0;
    if (! f || ! detail::parse (f.get(), detail::sizeOf (f.get()), fmt, dataPos, total)) return false;
    sampleRate = fmt.sampleRate;
    frames = total;
    channels = fmt.channels;
    return true;
}

// Decodes frames [startFrame, startFrame + maxFrames) of the file, cut at its end; mono fills both l and r. False when
// startFrame < 0, startFrame >= the frame count or no frame would be kept. l, r, sampleRate change only on success.
inline bool read (const std::string& path, std::vector<float>& l, std::vector<float>& r, int& sampleRate,
                  int64_t maxFrames = INT64_MAX, int64_t startFrame = 0)
{
    const detail::FilePtr f = detail::openRead (path);
    detail::Layout fmt;
    uint64_t dataPos = 0;
    int64_t total = 0;
    if (! f || ! detail::parse (f.get(), detail::sizeOf (f.get()), fmt, dataPos, total)) return false;
    if (startFrame < 0 || startFrame >= total || maxFrames <= 0) return false;
    const size_t n = (size_t) std::min (total - startFrame, maxFrames);
    const uint64_t at = dataPos + (uint64_t) startFrame * (uint64_t) (fmt.bytes * fmt.channels);   // < file size < 2 GB
    if (std::fseek (f.get(), (long) at, SEEK_SET) != 0 || ! detail::decode (f.get(), fmt, n, l, r)) return false;
    sampleRate = fmt.sampleRate;
    return true;
}

// .wav .wave .aif .aiff .aifc, case-insensitive.
inline bool isAudioPath (const std::string& path)
{
    const size_t dot = path.find_last_of ('.');
    if (dot == std::string::npos) return false;
    std::string e = path.substr (dot + 1);
    for (size_t i = 0; i < e.size(); ++i) e[i] = (char) std::tolower ((unsigned char) e[i]);
    return e == "wav" || e == "wave" || e == "aif" || e == "aiff" || e == "aifc";
}

// (l + r) / 2, over the shorter of the two. May throw bad_alloc like any vector (inputs are already in memory).
inline std::vector<float> toMono (const std::vector<float>& l, const std::vector<float>& r)
{
    std::vector<float> m (std::min (l.size(), r.size()));
    for (size_t i = 0; i < m.size(); ++i) m[i] = 0.5f * (l[i] + r[i]);
    return m;
}

// Linear resample of one channel to exactly n frames, endpoint-aligned: first and last output = first and last input,
// step = (size - 1) / (n - 1). n = 1 gives { x[0] }, size 1 gives n copies of x[0], n = 0 an empty vector, empty input n zeros.
// May throw bad_alloc for an absurd n: callers bound it.
inline std::vector<float> resample (const std::vector<float>& x, size_t n)
{
    if (n == x.size()) return x;
    std::vector<float> y (n);
    if (x.empty() || n == 0) return y;
    if (n == 1) { y[0] = x[0]; return y; }
    const double last = (double) (x.size() - 1);
    for (size_t i = 0; i < n; ++i)
    {
        const double t = (double) i * last / (double) (n - 1);
        const size_t a = std::min ((size_t) t, x.size() - 1), b = std::min (a + 1, x.size() - 1);
        const float k = (float) (t - (double) a);
        y[i] = x[a] + k * (x[b] - x[a]);
    }
    y[n - 1] = x.back();   // exact even if the compiler turns the division into a reciprocal multiply
    return y;
}

// Linear resample of one channel from rate `from` to rate `to`: round(len * to / from) frames, at least one for a
// non-empty input. Non-positive rates return the input. May throw bad_alloc for absurd rate ratios: callers bound them.
inline std::vector<float> resample (const std::vector<float>& x, int from, int to)
{
    if (from == to || from <= 0 || to <= 0 || x.empty()) return x;
    return resample (x, (size_t) std::max (1LL, std::llround ((double) x.size() * to / from)));
}
}
}
