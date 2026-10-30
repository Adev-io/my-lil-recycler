// Info.h: everything the scanner learns about one sample file, cached per path. No Rack dependency.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace recycler
{
enum Role { DRUMS = 0, BASS = 1, MELODY = 2, TEXTURE = 3 };

struct Info
{
    std::string path; uint64_t size = 0; int64_t mtime = 0;
    int sampleRate = 0; int64_t frames = 0; float seconds = 0.f;
    float tempo = 0.f, tempoConf = 0.f; int bars = 0;
    int key = -1; bool minor = false; float keyConf = 0.f;
    std::vector<float> onsets; float bestOnset = 0.f;      // seconds
    float role[4] = { 0.f, 0.f, 0.f, 0.f };
    float rms = -99.f, peak = -99.f;                        // dBFS
};
} // namespace recycler
