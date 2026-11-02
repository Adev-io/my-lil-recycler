// Recycler.cpp: the Rack module: folder scan, combo picks and stem renders on a worker thread, four stems looped on the clock.
// Author: Ari Klopfer / A_Development. MIT
//
// Threads. Audio (process): Transport, each stem's playing buffer (cur) and fading-out buffer (old), outputs, lights. It never
// allocates, locks or touches the library; it talks to the worker only through atomics: pickRequest / dropMask bits (normal
// mode), deckSteps[4] (DECK: audio adds a signed step count per slot, the worker drains it), the loadRequest /
// retargetRequest / deckStartRequest flags, the published
// target (pub*), landed[4] (the gen of each buffer it swaps in; the UI reads it), deck (UI writes; all read it), and per slot
// the pending / retired buffer hand-over (std::atomic<Buf*>: whoever exchanges a pointer out owns it). Worker (run): owns the
// library, the pick history and the scan; runs Scan / Render / Clear / Forget jobs from a deque (renders in front, scans at
// the back) and polls the request atomics at least every 20 ms. UI: folder dialog, menu, text boxes. folder and slots[] are
// under stateMutex (UI + worker).
#include "plugin.hpp"
#include "layout.hpp"
#include "TalkingFace.hpp"
#include "Analysis.h"
#include "Audio.h"
#include "File.h"
#include "Library.h"
#include "Picker.h"
#include "Stretch.h"
#include "Transport.h"
#include "Deck.h"
#include <osdialog.h>
#include <sys/stat.h>
#include <algorithm>
#include <atomic>
#include <cctype>
#include <chrono>
#include <condition_variable>
#include <cstring>
#include <deque>
#include <mutex>
#include <set>
#include <thread>

namespace rc = recycler;
typedef rc::stretch::Stereo Stereo;

// A rendered stem and the loop length (bars) it was rendered for, so it plays at the right speed whatever BARS says now.
struct Buf { Stereo a; int bars = 1; uint32_t gen = 0; };   // gen: the SlotState::gen it was rendered for

// Every Recycler in the process shares one cache file: saves and loads take turns (library::save writes one fixed .tmp).
static std::mutex cacheMutex;

static const int BAR_COUNTS[4] = { 1, 2, 4, 8 };
static const int CAPS[3] = { 30, 60, 120 };
static const char* const ROLE_NAMES[4] = { "Drums", "Bass", "Melody", "Texture" };

// NaN / inf -> 0, by bits so fast-math flags cannot optimise the test away
static inline float finite0 (float x)
{
    uint32_t u;
    std::memcpy (&u, &x, 4);
    return (u >> 23 & 0xFF) == 0xFF ? 0.f : x;
}

// seconds since the epoch; 0 when the file cannot be stat'ed
static int64_t mtimeOf (const std::string& path)
{
#ifdef _WIN32
    struct _stat64 st;
    return _wstat64 (rc::file::detail::toWide (path).c_str(), &st) == 0 ? (int64_t) st.st_mtime : 0;
#else
    struct stat st;
    return stat (path.c_str(), &st) == 0 ? (int64_t) st.st_mtime : 0;
#endif
}

static double clampD (double x, double a, double b) { return std::min (std::max (x, a), b); }   // Rack's clamp is int / float

// forward slashes, no trailing slash: getEntries hands back generic paths, the folder dialog native ones
static std::string normPath (std::string p)
{
    std::replace (p.begin(), p.end(), '\\', '/');
    while (p.size() > 1 && p.back() == '/') p.pop_back();
    return p;
}

static bool sameChar (char a, char b)
{
#ifdef _WIN32
    return std::tolower ((unsigned char) a) == std::tolower ((unsigned char) b);   // Windows paths: ASCII case-insensitive
#else
    return a == b;
#endif
}

// path lies inside normFolder (a normPath'ed folder; "/" and "C:" roots included)
static bool under (const std::string& path, const std::string& normFolder)
{
    const std::string p = normPath (path);
    const size_t n = normFolder.size();
    if (n == 0 || p.size() <= n) return false;
    for (size_t i = 0; i < n; ++i)
        if (! sameChar (p[i], normFolder[i])) return false;
    return normFolder[n - 1] == '/' || p[n] == '/';
}

// What the audio thread renders for (and the worker renders to). A tempo change counts when it is over 1 % of the reference
// b, so a wandering external clock does not re-render every 200 ms.
struct Tgt { float bpm = 120.f; int root = 0; bool minor = true; int bars = 2; int rate = 48000; };
static bool differs (const Tgt& a, const Tgt& b)
{
    return std::fabs (a.bpm - b.bpm) > 0.01f * b.bpm || a.root != b.root || a.minor != b.minor || a.bars != b.bars || a.rate != b.rate;
}

// One stem slot as the UI and the worker see it (stateMutex).
struct SlotState
{
    std::string path;      // empty: no stem
    rc::Info info;         // the cached analysis, when hasInfo
    bool hasInfo = false;
    int k = 0, s = 0;      // octave and semitone shift of the last render
    bool missing = false;  // the file or its analysis is gone, or its render failed: the name is drawn magenta
    int deckPos = -1, deckN = 0;   // DECK: place in the crate order (-1: not in it) and the crate size, for the name box
    uint32_t gen = 0;      // set by each DECK step; the name box shows a cue mark until a buffer of this gen lands
};

// Worker jobs carry copies; the worker never reads params.
struct Job
{
    enum Type { SCAN, RENDER, CLEAR, FORGET };
    Type type = SCAN;
    std::string folder; float cap = 60.f;                    // SCAN
    int slot = 0; std::string path; rc::Info info;           // RENDER
    rc::picker::Choice choice; rc::picker::Target target; int outRate = 48000;
    int role = 0; uint32_t gen = 0;                          // RENDER: stretch kind, SlotState::gen
};

// One stem on the audio thread, which owns cur and old. Two equal-power fades: old -> cur (a swap, a drop, or a fade-in when
// old is null) over fadeLen, and cur's pre-jump head -> cur's head over jumpLen (declicks a phase jump, also mid-swap).
// The old and pre-jump heads advance one frame per sample from where they were.
struct Stem
{
    Buf* cur = nullptr;
    Buf* old = nullptr;
    size_t oldPos = 0, jumpPos = 0, lastIdx = 0;
    int fadeLeft = 0, fadeLen = 1, jumpLeft = 0, jumpLen = 1;
};

struct Recycler : Module
{
    enum ParamId { FOLDER_PARAM, BPM_PARAM, ROOT_PARAM, MODE_PARAM, BARS_PARAM, RUN_PARAM, ENUMS (ROLL_PARAM, 4), ENUMS (LOCK_PARAM, 4),
                   ENUMS (LEVEL_PARAM, 4), BATCH_PARAM, CHAOS_PARAM, PARAMS_LEN };
    enum InputId { CLOCK_INPUT, VOCT_INPUT, RESET_INPUT, RUN_INPUT, ENUMS (ROLL_INPUT, 4), BATCH_INPUT, CHAOS_INPUT, INPUTS_LEN };
    enum OutputId { ENUMS (OUT_L_OUTPUT, 4), ENUMS (OUT_R_OUTPUT, 4), MIX_L_OUTPUT, MIX_R_OUTPUT, OUTPUTS_LEN };
    enum LightId { ENUMS (LIB_LIGHT, 2), RUN_LIGHT, ENUMS (LOCK_LIGHT, 4), ENUMS (RENDER_LIGHT, 2), LIGHTS_LEN };

    // ---- shared: worker queue and status (atomics are read by the audio thread and the UI)
    std::mutex jobMutex;
    std::condition_variable jobCv;
    std::deque<Job> jobs;
    std::atomic<bool> quit { false }, cancelScan { false }, scanning { false }, folderMissing { false }, hasFolder { false };
    std::atomic<int> filesTotal { 0 }, filesOk { 0 }, filesSkipped { 0 }, renders { 0 }, analysisCap { 60 };
    std::atomic<uint32_t> seed { 1 };
    std::atomic<Buf*> pending[4], retired[4];
    std::atomic<uint32_t> pickRequest { 0 }, dropMask { 0 };
    std::atomic<bool> loadPending { true }, loadRequest { false }, retargetRequest { false };
    std::atomic<float> pubBpm { 120.f }, pubChaos { 0.25f };
    std::atomic<int> pubRoot { 0 }, pubBars { 2 }, pubRate { 48000 };
    std::atomic<bool> pubMinor { true };
    std::atomic<bool> deck { false }, deckStartRequest { false };
    std::atomic<uint32_t> landed[4];   // written by the audio thread: the gen of the buffer each slot plays
    std::atomic<int> deckSteps[4];     // DECK: presses since the worker last drained it (+ next, - previous)

    std::mutex stateMutex;   // UI + worker
    std::string folder;
    SlotState slots[4];

    // ---- worker only
    rc::library::Library lib;
    rc::picker::History history;
    rc::picker::Rng seeder { 1 };
    std::vector<std::string> scanList;
    size_t scanPos = 0;
    float scanCap = 60.f;
    std::string scanFolder, historyFolder;
    int unsaved = 0;
    uint32_t nextGen = 0;
    bool deckWas = false;      // the last retarget saw DECK on (or a DECK load ran): leaving it drops the DRUMS shift
    bool deckRestart = false;  // DECK started during a scan: the crate is partial, so the scan's end starts it again

    // ---- audio thread only
    rc::Transport transport;
    Stem stems[4];
    Tgt seen, applied;
    float debounce = 0.f, runGain = 0.f, blinkTime = 0.f;
    dsp::BooleanTrigger rollBtn[4], batchBtn;
    dsp::SchmittTrigger rollTrig[4], batchTrig, clockTrig, resetTrig;
    dsp::ClockDivider lightDiv;
    FaceTap face;   // the mascot's mouth: MIX L

    std::thread worker;   // last: starts once everything above exists

    Recycler()
    {
        config (PARAMS_LEN, INPUTS_LEN, OUTPUTS_LEN, LIGHTS_LEN);
        configButton (FOLDER_PARAM, "Choose the sample folder (scanned with its subfolders)");
        configParam (BPM_PARAM, 40.f, 240.f, 120.f, "Tempo (a patched CLOCK overrides it)", " BPM");
        configSwitch (ROOT_PARAM, 0.f, 11.f, 0.f, "Root (a patched V/OCT overrides it)", { "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B" });
        configSwitch (MODE_PARAM, 0.f, 1.f, 1.f, "Mode", { "Major", "Minor" });
        configSwitch (BARS_PARAM, 0.f, 3.f, 1.f, "Loop length in bars (click to step)", { "1", "2", "4", "8" });
        configSwitch (RUN_PARAM, 0.f, 1.f, 1.f, "Run (a patched RUN gate overrides it)", { "Stopped", "Running" });
        for (int i = 0; i < 4; ++i)
        {
            const std::string r = ROLE_NAMES[i];
            configButton (ROLL_PARAM + i, r + " re-roll: pick another file");
            configSwitch (LOCK_PARAM + i, 0.f, 1.f, 0.f, r + " lock (BATCH leaves it alone)", { "Unlocked", "Locked" });
            configParam (LEVEL_PARAM + i, 0.f, 1.f, 0.8f, r + " level", " dB", -10.f, 20.f);
            configInput (ROLL_INPUT + i, r + " re-roll trigger");
            configOutput (OUT_L_OUTPUT + i, r + " left (L + R mono while R is unpatched)");
            configOutput (OUT_R_OUTPUT + i, r + " right");
            configLight (LOCK_LIGHT + i, r + " locked");
            paramQuantities[LOCK_PARAM + i]->randomizeEnabled = false;
        }
        configButton (BATCH_PARAM, "Batch: re-roll every unlocked stem");
        configParam (CHAOS_PARAM, 0.f, 1.f, 0.25f, "Chaos (looser tempo and key fit, wilder picks)", "%", 0.f, 100.f);
        configInput (CLOCK_INPUT, "Clock (quarter-note pulses; overrides BPM)");
        configInput (VOCT_INPUT, "Root V/OCT (nearest semitone; overrides ROOT)");
        configInput (RESET_INPUT, "Reset to the loop start");
        configInput (RUN_INPUT, "Run gate (high = running; overrides the RUN button)");
        configInput (BATCH_INPUT, "Batch re-roll trigger");
        configInput (CHAOS_INPUT, "Chaos CV (0..10 V adds 0..100 %)");
        configOutput (MIX_L_OUTPUT, "Mix left (L + R mono while MIX R is unpatched)");
        configOutput (MIX_R_OUTPUT, "Mix right");
        configLight (LIB_LIGHT, "Library (lime: ready, blinking magenta: scanning, magenta: folder missing)");
        configLight (RUN_LIGHT, "Running");
        configLight (RENDER_LIGHT, "Rendering (blinks while stems are being stretched)");
        paramQuantities[RUN_PARAM]->randomizeEnabled = false;
        for (int i = 0; i < 4; ++i) { pending[i].store (nullptr); retired[i].store (nullptr); landed[i].store (0); deckSteps[i].store (0); }
        seed = random::u32() | 1u;
        lightDiv.setDivision (64);
        worker = std::thread ([this] { run(); });
    }

    ~Recycler()
    {
        quit = true;
        cancelScan = true;
        { std::lock_guard<std::mutex> lk (jobMutex); }
        jobCv.notify_all();
        if (worker.joinable()) worker.join();
        for (int i = 0; i < 4; ++i)
        {
            delete stems[i].cur;
            delete stems[i].old;
            delete pending[i].exchange (nullptr);
            delete retired[i].exchange (nullptr);
        }
    }

    // ================================================================ worker

    static std::string cachePath() { return asset::user ("MyLilRecycler/library.json"); }

    rc::picker::Target target() const
    {
        rc::picker::Target t;
        t.bpm = pubBpm.load();
        t.root = pubRoot.load();
        t.minor = pubMinor.load();
        t.bars = pubBars.load();
        t.chaos = pubChaos.load();
        return t;
    }

    // with jobMutex held: removes queued jobs of a type (slot < 0: any slot), returns how many
    int dropQueued (Job::Type type, int slot)
    {
        int n = 0;
        for (std::deque<Job>::iterator it = jobs.begin(); it != jobs.end();)
            if (it->type == type && (slot < 0 || it->slot == slot)) { it = jobs.erase (it); ++n; }
            else ++it;
        return n;
    }

    void post (const Job& j, bool front)
    {
        {
            std::lock_guard<std::mutex> lk (jobMutex);
            if (j.type == Job::RENDER) renders += 1 - dropQueued (Job::RENDER, j.slot);   // a newer render replaces a queued one
            if (j.type == Job::SCAN) dropQueued (Job::SCAN, -1);
            if (front) jobs.push_front (j); else jobs.push_back (j);
        }
        jobCv.notify_one();
    }

    // k / s for a slot's file at target t: k from the tempo, s from the key (drums keep theirs: the picker never keys them)
    static void fit (SlotState& s, int role, const rc::picker::Target& t)
    {
        float cost = 0.f;
        s.k = rc::picker::octaveFor (s.info.tempo, t.bpm, cost);
        if (role != rc::DRUMS) s.s = rc::picker::shiftFor (s.info.key, s.info.minor, t.root, t.minor);
    }

    // fit by the slot's role, or in DECK mode by the file itself (Deck.h)
    void fitSlot (SlotState& s, int slot, const rc::picker::Target& t) const
    {
        if (! deck.load()) { fit (s, slot, t); return; }
        const rc::picker::Choice c = rc::deck::fit (s.info, t);
        s.k = c.k;
        s.s = c.s;
    }

    // the stretch kind: the slot's role, or in DECK mode the file's strongest role (a drum loop slices on any slot)
    void postRender (int slot, const SlotState& s, const rc::picker::Target& t, int rate)
    {
        Job j;
        j.type = Job::RENDER;
        j.slot = slot;
        j.role = deck.load() ? rc::deck::kindOf (s.info) : slot;
        j.gen = s.gen;
        j.path = s.path;
        j.info = s.info;
        j.choice.k = s.k;
        j.choice.s = s.s;
        j.target = t;
        j.outRate = rate;
        post (j, true);
    }

    const rc::Info* byPath (const std::string& path) const
    {
        for (size_t i = 0; i < lib.files.size(); ++i)
            if (lib.files[i].path == path) return &lib.files[i];
        return nullptr;
    }

    // slots with a path but no usable analysis: take it from the library if the file is there, then render; else missing
    void resolve (bool markMissing)
    {
        const rc::picker::Target t = target();
        const int rate = pubRate.load();
        for (int i = 0; i < 4; ++i)
        {
            SlotState s;
            {
                std::lock_guard<std::mutex> lk (stateMutex);
                if (slots[i].path.empty() || (slots[i].hasInfo && ! slots[i].missing)) continue;
                s = slots[i];
            }
            const rc::Info* info = byPath (s.path);
            const bool ok = info && system::isFile (s.path);
            if (ok)
            {
                s.info = *info;
                s.hasInfo = true;
                s.missing = false;
                fitSlot (s, i, t);
            }
            {
                std::lock_guard<std::mutex> lk (stateMutex);
                if (slots[i].path != s.path) continue;   // re-picked meanwhile
                if (ok) slots[i] = s;
                else if (markMissing) slots[i].missing = true;
            }
            if (ok) postRender (i, s, t, rate);
            else if (markMissing) dropStem (i);
        }
    }

    // a slot that is empty, missing or failed plays nothing: its unplayed render goes, the audio thread fades cur out
    void dropStem (int i)
    {
        delete pending[i].exchange (nullptr);
        dropMask.fetch_or (1u << i);
    }

    // patch load (or a new module): the cache, the seed, the saved stems, then the folder scan
    void load()
    {
        if (unsaved > 0) save();   // a preset load or undo mid-scan: keep what was analysed
        try { system::createDirectories (system::getDirectory (cachePath())); }
        catch (const std::exception& e) { WARN ("Recycler: cannot create %s: %s", system::getDirectory (cachePath()).c_str(), e.what()); }
        rc::library::Library fresh;
        bool loaded;
        {
            std::lock_guard<std::mutex> lk (cacheMutex);
            loaded = rc::library::load (cachePath(), fresh);
        }
        if (loaded) { lib.files.swap (fresh.files); history = rc::picker::History(); }
        deckWas = deck.load();   // a patch load sets the mode directly; no transition to undo
        seeder = rc::picker::Rng (seed.load());
        std::string f;
        uint32_t empty = 0;
        {
            std::lock_guard<std::mutex> lk (stateMutex);
            f = folder;
            for (int i = 0; i < 4; ++i)
            {
                slots[i].hasInfo = false;   // re-read from the cache below
                if (slots[i].path.empty()) empty |= 1u << i;
            }
        }
        for (int i = 0; i < 4; ++i)
            if (empty >> i & 1) dropStem (i);
        resolve (true);
        if (! f.empty())
        {
            Job j;
            j.type = Job::SCAN;
            j.folder = f;
            j.cap = (float) analysisCap.load();
            post (j, false);
        }
    }

    // the current folder's files, in library order (indices stay put while the folder does: the scan appends)
    void folderLib (rc::library::Library& out)
    {
        std::string f;
        { std::lock_guard<std::mutex> lk (stateMutex); f = normPath (folder); }
        if (f != historyFolder) { history = rc::picker::History(); historyFolder = f; }   // its indices are this list's
        out.files.clear();
        for (size_t i = 0; i < lib.files.size(); ++i)
            if (under (lib.files[i].path, f)) out.files.push_back (lib.files[i]);
    }

    void pick (uint32_t mask)
    {
        rc::library::Library pool;
        folderLib (pool);
        if (pool.files.empty()) return;
        const rc::picker::Target t = target();
        const int rate = pubRate.load();
        std::string paths[4];
        {
            std::lock_guard<std::mutex> lk (stateMutex);
            for (int j = 0; j < 4; ++j) paths[j] = slots[j].path;
        }
        rc::picker::Choice c[4];
        bool locked[4];
        for (int j = 0; j < 4; ++j)
        {
            locked[j] = ! (mask >> j & 1);
            for (size_t i = 0; i < pool.files.size() && ! paths[j].empty(); ++i)
                if (pool.files[i].path == paths[j]) { c[j].file = (int) i; break; }
        }
        rc::picker::Rng rng (((uint64_t) seeder.next() << 32) | seeder.next());
        rc::picker::pickAll (pool, t, locked, c, history, rng);
        for (int j = 0; j < 4; ++j)
        {
            if (locked[j] || c[j].file < 0) continue;   // -1: no alternative, keep the current file
            const rc::Info& info = pool.files[(size_t) c[j].file];
            if (info.path == paths[j]) continue;
            SlotState s;
            s.path = info.path;
            s.info = info;
            s.hasInfo = true;
            s.k = c[j].k;
            s.s = c[j].s;
            { std::lock_guard<std::mutex> lk (stateMutex); slots[j] = s; }
            postRender (j, s, t, rate);
        }
    }

    // DECK: one slot takes the crate file at pos (render posted; it lands at the next loop wrap)
    void deckLoad (int j, const rc::library::Library& pool, const std::vector<int>& ord, int pos)
    {
        if (pos < 0 || pos >= (int) ord.size()) return;
        const rc::Info& info = pool.files[(size_t) ord[(size_t) pos]];
        const rc::picker::Target t = target();
        SlotState s;
        s.path = info.path;
        s.info = info;
        s.hasInfo = true;
        const rc::picker::Choice c = rc::deck::fit (info, t);
        s.k = c.k;
        s.s = c.s;
        s.deckPos = pos;
        s.deckN = (int) ord.size();
        deckWas = true;
        if (++nextGen == 0) ++nextGen;   // 0 means "never stepped" (landed starts there)
        s.gen = nextGen;
        { std::lock_guard<std::mutex> lk (stateMutex); slots[j] = s; }
        delete pending[j].exchange (nullptr);   // a rendered but unplayed older step must not land at the wrap
        postRender (j, s, t, pubRate.load());
    }

    // DECK: each slot's drained presses (+ next, - previous) step it through the crate; one render per slot that moved
    void deckPick()
    {
        if (! deck.load()) return;
        int want[4];
        bool any = false;
        for (int j = 0; j < 4; ++j) { want[j] = deckSteps[j].exchange (0); any = any || want[j] != 0; }
        if (! any) return;
        rc::library::Library pool;
        folderLib (pool);
        const std::vector<int> ord = rc::deck::order (pool);
        const int n = (int) ord.size();
        if (n == 0) return;
        for (int j = 0; j < 4; ++j)
        {
            if (want[j] == 0) continue;
            std::string path;
            bool missing = false;
            { std::lock_guard<std::mutex> lk (stateMutex); path = slots[j].path; missing = slots[j].missing; }
            const int dir = want[j] > 0 ? 1 : -1;
            int count = want[j] > 0 ? want[j] : -want[j];
            int pos = rc::deck::positionOf (pool, ord, path);
            const int oldPos = pos;
            if (pos < 0) { pos = rc::deck::step (pos, dir, n); --count; }   // off the crate: the first step lands on the first / last file
            count %= n;   // n steps round the crate: back where it was
            for (int c = 0; c < count; ++c) pos = rc::deck::step (pos, dir, n);
            if (pos == oldPos && ! missing) continue;   // a full lap lands on the same file: no new gen, no re-render (a missing file is retried)
            deckLoad (j, pool, ord, pos);
        }
    }

    // DECK switched on, or a scan ended with every slot empty in DECK mode: slot n takes crate file n
    void deckStart()
    {
        if (! deck.load()) return;
        deckRestart = scanning.load();   // a scan in progress: its crate is partial, so the scan's end starts again
        rc::library::Library pool;
        folderLib (pool);
        const std::vector<int> ord = rc::deck::order (pool);
        if (ord.empty())
        {
            std::lock_guard<std::mutex> lk (stateMutex);
            for (int j = 0; j < 4; ++j) { slots[j].deckPos = -1; slots[j].deckN = 0; }   // no crate: no stale NN/NN
            return;
        }
        for (int j = 0; j < 4; ++j) deckLoad (j, pool, ord, rc::deck::startPos (j, (int) ord.size()));
    }

    // each slot's crate position and the crate size, for the name box (after a scan, a load)
    void deckIndex()
    {
        rc::library::Library pool;
        folderLib (pool);
        const std::vector<int> ord = rc::deck::order (pool);
        std::lock_guard<std::mutex> lk (stateMutex);
        for (int j = 0; j < 4; ++j)
        {
            slots[j].deckPos = rc::deck::positionOf (pool, ord, slots[j].path);
            slots[j].deckN = (int) ord.size();
        }
    }

    void retarget()
    {
        const bool d = deck.load();
        if (! d && deckWas)
        {
            // left DECK: the picker never keys the DRUMS slot; drop the shift DECK gave it
            std::lock_guard<std::mutex> lk (stateMutex);
            slots[rc::DRUMS].s = 0;
        }
        deckWas = d;
        const rc::picker::Target t = target();
        const int rate = pubRate.load();
        for (int i = 0; i < 4; ++i)
        {
            SlotState s;
            {
                std::lock_guard<std::mutex> lk (stateMutex);
                if (slots[i].path.empty() || ! slots[i].hasInfo || slots[i].missing) continue;
                fitSlot (slots[i], i, t);
                s = slots[i];
            }
            postRender (i, s, t, rate);
        }
    }

    void render (const Job& j)
    {
        Buf* buf = nullptr;
        try
        {
            int fileRate = 0, channels = 0;
            int64_t total = 0;
            if (rc::audio::probe (j.path, fileRate, total, channels))
            {
                const rc::stretch::Region g = rc::stretch::regionFor (j.info, j.role, j.choice, j.target, fileRate);
                const int64_t start = std::min (std::max<int64_t> (0, g.start), total - 1);
                const int64_t count = std::min (g.frames, total - start);
                Stereo in;
                int rate = 0;
                if (count > 0 && rc::audio::read (j.path, in.l, in.r, rate, count, start))
                {
                    rc::stretch::RenderIn ri;
                    ri.audio = &in;
                    ri.fileRate = rate;
                    ri.info = &j.info;
                    ri.role = j.role;
                    ri.choice = j.choice;
                    ri.target = j.target;
                    ri.outRate = j.outRate;
                    ri.audioStart = start;
                    Stereo out = rc::stretch::render (ri);
                    if (out.frames() > 0 && out.r.size() == out.l.size())
                    {
                        buf = new Buf;
                        buf->a = std::move (out);
                        buf->bars = std::max (1, j.target.bars);
                        buf->gen = j.gen;
                    }
                }
            }
        }
        catch (const std::exception& e)
        {
            WARN ("Recycler: render of %s failed: %s", j.path.c_str(), e.what());
            delete buf;
            buf = nullptr;
        }
        bool current;
        {
            std::lock_guard<std::mutex> lk (stateMutex);
            current = slots[j.slot].path == j.path && slots[j.slot].gen == j.gen;   // an overtaken render (older step) is dropped
            if (current && ! buf) slots[j.slot].missing = true;
        }
        if (buf && current)
        {
            delete retired[j.slot].exchange (nullptr);
            delete pending[j.slot].exchange (buf);   // an unplayed older render goes
        }
        else
        {
            if (current) dropStem (j.slot);   // failed: missing, plays nothing
            delete buf;
        }
        --renders;
    }

    void startScan (const Job& j)
    {
        endScan (false);
        cancelScan = false;
        filesTotal = filesOk = filesSkipped = 0;
        scanCap = j.cap;
        scanFolder = j.folder;
        folderMissing = ! system::isDirectory (j.folder);
        if (folderMissing) return;
        std::vector<std::string> all;
        try { all = system::getEntries (j.folder, -1); }
        catch (const std::exception& e)
        {
            WARN ("Recycler: cannot list %s: %s", j.folder.c_str(), e.what());
            folderMissing = true;
            return;
        }
        for (size_t i = 0; i < all.size(); ++i)
            if (rc::audio::isAudioPath (all[i])) scanList.push_back (all[i]);
        filesTotal = (int) scanList.size();
        scanning = true;
        if (scanList.empty()) endScan (true);
    }

    bool analyseFile (const std::string& path)
    {
        const uint64_t size = system::getFileSize (path);
        const int64_t mtime = mtimeOf (path);
        if (lib.find (path, size, mtime)) return true;
        int sr = 0, channels = 0;
        int64_t total = 0;
        if (! rc::audio::probe (path, sr, total, channels) || sr <= 0) return false;
        std::vector<float> l, r;
        int rate = 0;
        const int64_t maxFrames = scanCap > 0.f ? (int64_t) std::ceil ((double) scanCap * sr) : INT64_MAX;
        if (! rc::audio::read (path, l, r, rate, maxFrames)) return false;
        std::vector<float> mono = rc::audio::toMono (l, r);
        std::vector<float>().swap (l);
        std::vector<float>().swap (r);
        rc::Info info = rc::analysis::analyse (mono, rate, scanCap, system::getFilename (path));
        info.path = path;
        info.size = size;
        info.mtime = mtime;
        info.frames = total;
        info.seconds = (float) ((double) total / rate);
        lib.put (info);
        if (++unsaved >= 20) save();
        return true;
    }

    void save()
    {
        bool ok;
        {
            std::lock_guard<std::mutex> lk (cacheMutex);
            ok = rc::library::save (lib, cachePath());
        }
        if (! ok) WARN ("Recycler: cannot write %s", cachePath().c_str());
        unsaved = 0;
    }

    void scanOne()
    {
        if (cancelScan.load()) { endScan (false); return; }
        const std::string path = scanList[scanPos++];
        bool ok = false;
        try { ok = analyseFile (path); }
        catch (const std::exception& e) { WARN ("Recycler: cannot analyse %s: %s", path.c_str(), e.what()); }
        if (ok) ++filesOk; else ++filesSkipped;
        if (scanPos >= scanList.size()) endScan (true);
    }

    // finished: drop cache entries under the folder that the scan no longer found, take up waiting slots, and with every
    // slot empty pick a first combo
    void endScan (bool finished)
    {
        const bool restart = deckRestart; deckRestart = false;   // DECK started during this scan
        if (finished)
        {
            std::set<std::string> found;
            for (size_t i = 0; i < scanList.size(); ++i) found.insert (normPath (scanList[i]));
            const std::string f = normPath (scanFolder);
            const size_t before = lib.files.size();
            lib.files.erase (std::remove_if (lib.files.begin(), lib.files.end(), [&] (const rc::Info& i) {
                return under (i.path, f) && ! found.count (normPath (i.path)); }), lib.files.end());
            if (lib.files.size() != before) { history = rc::picker::History(); ++unsaved; }
        }
        if (unsaved > 0) save();
        scanList.clear();
        scanPos = 0;
        scanning = false;
        if (! finished) return;
        resolve (true);
        if (deck.load()) deckIndex();
        bool empty = true;
        {
            std::lock_guard<std::mutex> lk (stateMutex);
            for (int i = 0; i < 4; ++i) empty = empty && slots[i].path.empty();
            empty = empty && ! folder.empty();
        }
        if (deck.load() && restart) deckStart();
        else if (empty)
        {
            if (deck.load()) deckStart();
            else pick (0xF);
        }
    }

    void clearSlots()
    {
        {
            std::lock_guard<std::mutex> lk (jobMutex);
            renders -= dropQueued (Job::RENDER, -1);
            dropQueued (Job::SCAN, -1);   // Initialize / Forget: no scan comes back behind them
        }
        {
            std::lock_guard<std::mutex> lk (stateMutex);
            for (int i = 0; i < 4; ++i) slots[i] = SlotState();
        }
        for (int i = 0; i < 4; ++i) delete pending[i].exchange (nullptr);
        dropMask.fetch_or (0xF);
    }

    void runJob (const Job& j)
    {
        switch (j.type)
        {
            case Job::SCAN: startScan (j); break;
            case Job::RENDER: render (j); break;
            case Job::CLEAR: clearSlots(); break;
            case Job::FORGET:
                unsaved = 0;
                endScan (false);
                lib.files.clear();
                history = rc::picker::History();
                {
                    std::lock_guard<std::mutex> lk (cacheMutex);
                    rc::file::remove (cachePath());
                }
                filesTotal = filesOk = filesSkipped = 0;
                clearSlots();
                break;
        }
    }

    void run()
    {
        while (! quit.load())
        {
            Job job;
            bool have = false;
            {
                std::unique_lock<std::mutex> lk (jobMutex);
                if (jobs.empty() && scanPos >= scanList.size()) jobCv.wait_for (lk, std::chrono::milliseconds (20));
                if (quit.load()) break;
                if (! jobs.empty()) { job = jobs.front(); jobs.pop_front(); have = true; }
            }
            for (int i = 0; i < 4; ++i) delete retired[i].exchange (nullptr);
            try   // one exception escaping a thread takes Rack down
            {
                if (loadRequest.exchange (false)) load();
                if (deckStartRequest.exchange (false)) deckStart();
                if (const uint32_t r = pickRequest.exchange (0))
                {
                    if (! deck.load() && (r & 0xFu)) pick (r & 0xFu);
                }
                deckPick();
                if (retargetRequest.exchange (false)) retarget();
            }
            catch (const std::exception& e) { WARN ("Recycler: worker request: %s", e.what()); }
            try
            {
                if (have) runJob (job);
                else if (scanPos < scanList.size()) scanOne();
            }
            catch (const std::exception& e)
            {
                WARN ("Recycler: worker job: %s", e.what());
                if (have && job.type == Job::RENDER) --renders;
            }
        }
        try { if (unsaved > 0) save(); }   // a patch closed mid-scan keeps what was found
        catch (const std::exception&) {}
    }

    // ================================================================ UI thread

    void rescan()
    {
        Job j;
        j.type = Job::SCAN;
        { std::lock_guard<std::mutex> lk (stateMutex); j.folder = folder; }
        if (j.folder.empty()) return;
        j.cap = (float) analysisCap.load();
        cancelScan = true;
        post (j, false);
    }

    void setFolder (const std::string& f)
    {
        { std::lock_guard<std::mutex> lk (stateMutex); folder = f; }
        hasFolder = ! f.empty();
        folderMissing = false;
        rescan();
    }

    void chooseFolder()
    {
        std::string start;
        { std::lock_guard<std::mutex> lk (stateMutex); start = folder; }
        char* path = osdialog_file (OSDIALOG_OPEN_DIR, start.empty() ? nullptr : start.c_str(), nullptr, nullptr);
        if (! path) return;
        const std::string f = path;
        std::free (path);
        setFolder (f);
    }

    void forget()
    {
        cancelScan = true;
        Job j;
        j.type = Job::FORGET;
        post (j, true);
    }

    // the menu's Deck mode. LOCK becomes a previous button, so every latch starts released, and presses counted for the
    // old mode are dropped. Switching off re-renders every slot by its role (the worker drops the DRUMS shift DECK gave it).
    void setDeck (bool on)
    {
        if (on == deck.load()) return;
        for (int i = 0; i < 4; ++i) { params[LOCK_PARAM + i].setValue (0.f); deckSteps[i].store (0); }
        deck = on;
        if (on) deckStartRequest = true;
        else retargetRequest = true;
    }

    void onReset (const ResetEvent& e) override
    {
        Module::onReset (e);
        { std::lock_guard<std::mutex> lk (stateMutex); folder.clear(); }
        hasFolder = false;
        folderMissing = false;
        deck = false;
        cancelScan = true;
        Job j;
        j.type = Job::CLEAR;
        post (j, true);
    }

    // ================================================================ audio thread

    int barsIndex() { return clamp ((int) std::round (params[BARS_PARAM].getValue()), 0, 3); }

    Tgt targetNow (float sr)
    {
        Tgt t;
        t.bpm = transport.bpm();
        if (inputs[VOCT_INPUT].isConnected())
        {
            const float v = clamp (finite0 (inputs[VOCT_INPUT].getVoltage()), -20.f, 20.f);
            t.root = ((int) std::lround (v * 12.f) % 12 + 12) % 12;
        }
        else t.root = clamp ((int) std::round (params[ROOT_PARAM].getValue()), 0, 11);
        t.minor = params[MODE_PARAM].getValue() > 0.5f;
        t.bars = BAR_COUNTS[barsIndex()];
        t.rate = (int) std::lround (sr);
        return t;
    }

    void publish (const Tgt& t)
    {
        pubBpm = t.bpm;
        pubRoot = t.root;
        pubMinor = t.minor;
        pubBars = t.bars;
        pubRate = t.rate;
    }

    // cur (read at frame lastIdx last sample) becomes old and fades out from the next frame on; null: a fade-in from silence
    static void fadeOut (Stem& st, Buf* from, int len)
    {
        st.old = from;
        st.oldPos = from && from->a.frames() ? (st.lastIdx + 1) % from->a.frames() : 0;
        st.fadeLeft = st.fadeLen = std::max (1, len);
        st.jumpLeft = 0;   // cur changes: its pre-jump head means nothing now
    }

    // frame of b at loop phase: b holds b->bars bars of a loopBars-bar loop, so it plays at its own speed and repeats
    static size_t frameAt (const Buf* b, double phase, double loopBars)
    {
        const size_t n = b->a.frames();
        double x = phase * loopBars / (double) b->bars;
        x -= std::floor (x);
        return std::min ((size_t) (x * (double) n), n - 1);
    }

    void onSampleRateChange (const SampleRateChangeEvent& e) override
    {
        seen.rate = (int) std::lround (e.sampleRate);   // the next light tick re-targets at once
        debounce = 1e-6f;
    }

    void process (const ProcessArgs& args) override
    {
        const float sr = args.sampleRate;
        const bool running = inputs[RUN_INPUT].isConnected() ? inputs[RUN_INPUT].getVoltage() > 1.f : params[RUN_PARAM].getValue() > 0.5f;
        transport.setSampleRate (sr);
        transport.setClockConnected (inputs[CLOCK_INPUT].isConnected());
        transport.setKnobBpm (params[BPM_PARAM].getValue());
        transport.setBars (BAR_COUNTS[barsIndex()]);
        transport.setRunning (running);
        if (resetTrig.process (inputs[RESET_INPUT].getVoltage(), 0.1f, 1.f)) transport.reset();
        if (clockTrig.process (inputs[CLOCK_INPUT].getVoltage(), 0.1f, 1.f)) transport.clockPulse();
        const bool wrapped = transport.tick(), jumped = transport.jumped();
        const double phase = transport.phase();

        if (loadPending.load (std::memory_order_relaxed) && loadPending.exchange (false))
        {
            seen = applied = targetNow (sr);
            publish (applied);
            debounce = 0.f;
            pubChaos = clamp (params[CHAOS_PARAM].getValue() + finite0 (inputs[CHAOS_INPUT].getVoltage()) / 10.f, 0.f, 1.f);
            loadRequest = true;
        }

        uint32_t req = 0;
        const bool deckOn = deck.load (std::memory_order_relaxed);
        for (int i = 0; i < 4; ++i)
        {
            const bool b = rollBtn[i].process (params[ROLL_PARAM + i].getValue() > 0.f);
            const bool t = rollTrig[i].process (inputs[ROLL_INPUT + i].getVoltage(), 0.1f, 1.f);
            if (b || t)
            {
                if (deckOn) deckSteps[i].fetch_add (1);   // DECK: each press is a step (pickRequest bits would coalesce)
                else req |= 1u << i;
            }
            if (deckOn && params[LOCK_PARAM + i].getValue() > 0.5f)   // DECK: LOCK is a previous button; the latch springs back
            {
                params[LOCK_PARAM + i].setValue (0.f);
                deckSteps[i].fetch_sub (1);
            }
        }
        const bool bb = batchBtn.process (params[BATCH_PARAM].getValue() > 0.f);
        const bool bt = batchTrig.process (inputs[BATCH_INPUT].getVoltage(), 0.1f, 1.f);
        if ((bb || bt) && ! deckOn)
            for (int i = 0; i < 4; ++i)
                if (params[LOCK_PARAM + i].getValue() < 0.5f) req |= 1u << i;
        if (req) pickRequest.fetch_or (req);

        const float step = 1.f / (0.005f * sr);   // 5 ms run / stop ramp
        runGain = running ? std::min (1.f, runGain + step) : std::max (0.f, runGain - step);
        const int fadeSwap = (int) (0.02f * sr), fadeJump = (int) (0.005f * sr);
        const double loopBars = BAR_COUNTS[barsIndex()];
        const uint32_t drop = dropMask.load (std::memory_order_relaxed);
        float mixL = 0.f, mixR = 0.f;
        for (int i = 0; i < 4; ++i)
        {
            Stem& st = stems[i];
            if (st.old && st.fadeLeft == 0 && ! retired[i].load (std::memory_order_relaxed))
            {
                retired[i].store (st.old);
                st.old = nullptr;
            }
            if (drop >> i & 1)
            {
                if (! st.old)
                {
                    if (st.cur) fadeOut (st, st.cur, fadeSwap);
                    st.cur = nullptr;
                    dropMask.fetch_and (~(1u << i));
                }
            }
            else if (! st.old && pending[i].load (std::memory_order_relaxed) && (wrapped || ! running || ! st.cur))
            {
                Buf* prev = st.cur;
                st.cur = pending[i].exchange (nullptr);
                if (st.cur) landed[i].store (st.cur->gen, std::memory_order_relaxed);
                fadeOut (st, prev, fadeSwap);   // no prev: fade in from silence
            }
            else if (jumped && st.cur && st.cur->a.frames())
            {
                // declick the jump; landing mid-declick, keep whichever head is louder now
                if (st.jumpLeft == 0 || 2 * st.jumpLeft < st.jumpLen) st.jumpPos = (st.lastIdx + 1) % st.cur->a.frames();
                st.jumpLeft = st.jumpLen = std::max (1, fadeJump);
            }

            float l = 0.f, r = 0.f;
            if (st.cur && st.cur->a.frames())
            {
                const Stereo& c = st.cur->a;
                const size_t idx = frameAt (st.cur, phase, loopBars);
                l = c.l[idx];
                r = c.r[idx];
                st.lastIdx = idx;
                if (st.jumpLeft > 0)
                {
                    const float a = 0.5f * (float) M_PI * (1.f - (float) st.jumpLeft / (float) st.jumpLen);
                    const float gIn = std::sin (a), gOut = std::cos (a);
                    l = l * gIn + c.l[st.jumpPos] * gOut;
                    r = r * gIn + c.r[st.jumpPos] * gOut;
                    st.jumpPos = (st.jumpPos + 1) % c.frames();
                    --st.jumpLeft;
                }
            }
            if (st.fadeLeft > 0)
            {
                const float a = 0.5f * (float) M_PI * (1.f - (float) st.fadeLeft / (float) st.fadeLen);
                const float gIn = std::sin (a), gOut = std::cos (a);
                float ol = 0.f, orr = 0.f;
                if (st.old && st.old->a.frames())
                {
                    ol = st.old->a.l[st.oldPos];
                    orr = st.old->a.r[st.oldPos];
                    st.oldPos = (st.oldPos + 1) % st.old->a.frames();
                }
                l = l * gIn + ol * gOut;
                r = r * gIn + orr * gOut;
                --st.fadeLeft;
            }

            const float g = params[LEVEL_PARAM + i].getValue() * 5.f * runGain;
            l = finite0 (l * g);
            r = finite0 (r * g);
            outputs[OUT_L_OUTPUT + i].setVoltage (outputs[OUT_R_OUTPUT + i].isConnected() ? l : 0.5f * (l + r));
            outputs[OUT_R_OUTPUT + i].setVoltage (r);
            mixL += l;
            mixR += r;
        }
        mixL = finite0 (0.5f * mixL);   // the four stems summed at half level
        mixR = finite0 (0.5f * mixR);
        outputs[MIX_L_OUTPUT].setVoltage (outputs[MIX_R_OUTPUT].isConnected() ? mixL : 0.5f * (mixL + mixR));
        outputs[MIX_R_OUTPUT].setVoltage (mixR);
        face.push (clamp (mixL / 10.f, -1.f, 1.f), sr);

        if (lightDiv.process()) slow (sr, args.sampleTime * lightDiv.getDivision(), running);
    }

    // every 64 samples: the debounced target, the chaos the picker reads, lights
    void slow (float sr, float dt, bool running)
    {
        const Tgt now = targetNow (sr);
        if (differs (now, seen)) { seen = now; debounce = 0.2f; }
        else if (debounce > 0.f)
        {
            debounce -= dt;
            if (debounce <= 0.f && differs (seen, applied))
            {
                applied = seen;
                publish (applied);
                retargetRequest = true;
            }
        }
        pubChaos = clamp (params[CHAOS_PARAM].getValue() + finite0 (inputs[CHAOS_INPUT].getVoltage()) / 10.f, 0.f, 1.f);

        blinkTime = std::fmod (blinkTime + dt, 1.f);
        const bool blink = std::fmod (blinkTime, 0.5f) < 0.25f;   // 2 Hz
        const bool lib = hasFolder.load(), scan = scanning.load(), missing = folderMissing.load();
        lights[LIB_LIGHT].setBrightness (lib && ! scan && ! missing ? 1.f : 0.f);
        lights[LIB_LIGHT + 1].setBrightness (lib && (scan ? blink : missing) ? 1.f : 0.f);
        lights[RUN_LIGHT].setBrightness (running ? 1.f : 0.f);
        const bool deckOn = deck.load (std::memory_order_relaxed);
        for (int i = 0; i < 4; ++i) lights[LOCK_LIGHT + i].setBrightness (! deckOn && params[LOCK_PARAM + i].getValue() > 0.5f ? 1.f : 0.f);
        lights[RENDER_LIGHT].setBrightness (0.f);
        lights[RENDER_LIGHT + 1].setBrightness (renders.load() > 0 && blink ? 1.f : 0.f);
    }

    // ================================================================ patch state

    json_t* dataToJson() override
    {
        json_t* root = json_object();
        std::string f;
        SlotState s[4];
        {
            std::lock_guard<std::mutex> lk (stateMutex);
            f = folder;
            for (int i = 0; i < 4; ++i) { s[i].path = slots[i].path; s[i].k = slots[i].k; s[i].s = slots[i].s; }
        }
        json_object_set_new (root, "folder", json_stringn_nocheck (f.data(), f.size()));
        json_object_set_new (root, "run", json_boolean (params[RUN_PARAM].getValue() > 0.5f));
        json_object_set_new (root, "bpm", json_real (params[BPM_PARAM].getValue()));
        json_object_set_new (root, "root", json_integer (clamp ((int) std::round (params[ROOT_PARAM].getValue()), 0, 11)));
        json_object_set_new (root, "minor", json_boolean (params[MODE_PARAM].getValue() > 0.5f));
        json_object_set_new (root, "bars", json_integer (BAR_COUNTS[barsIndex()]));
        json_object_set_new (root, "chaos", json_real (params[CHAOS_PARAM].getValue()));
        json_object_set_new (root, "seed", json_integer ((json_int_t) seed.load()));
        json_object_set_new (root, "analysisCap", json_integer (analysisCap.load()));
        json_object_set_new (root, "deck", json_boolean (deck.load()));
        json_t* arr = json_array();
        for (int i = 0; i < 4; ++i)
        {
            json_t* o = json_object();
            json_object_set_new (o, "path", json_stringn_nocheck (s[i].path.data(), s[i].path.size()));
            json_object_set_new (o, "locked", json_boolean (params[LOCK_PARAM + i].getValue() > 0.5f));
            json_object_set_new (o, "level", json_real (params[LEVEL_PARAM + i].getValue()));
            json_object_set_new (o, "k", json_integer (s[i].k));
            json_object_set_new (o, "s", json_integer (s[i].s));
            json_array_append_new (arr, o);
        }
        json_object_set_new (root, "slots", arr);
        return root;
    }

    static bool number (json_t* o, const char* key, double& v)
    {
        json_t* j = json_object_get (o, key);
        if (! j || ! json_is_number (j)) return false;
        v = json_number_value (j);
        return std::isfinite (v);
    }

    static bool flag (json_t* o, const char* key, bool& v)
    {
        json_t* j = json_object_get (o, key);
        if (j && json_is_boolean (j)) { v = json_is_true (j); return true; }
        double d;
        if (number (o, key, d)) { v = d != 0.0; return true; }
        return false;
    }

    // every key optional; the params it names are set too (the rig patch carries no params)
    void dataFromJson (json_t* root) override
    {
        double v;
        bool b;
        bool deckJson = false;
        if (flag (root, "deck", b)) deckJson = b;
        deck = deckJson;   // patches from 2.0.0 have no key: off
        for (int i = 0; i < 4; ++i) deckSteps[i].store (0);   // presses counted before a load never apply after it
        if (deckJson) for (int i = 0; i < 4; ++i) params[LOCK_PARAM + i].setValue (0.f);   // a deck patch never fires a previous step
        if (number (root, "bpm", v)) params[BPM_PARAM].setValue ((float) clampD (v, 40.0, 240.0));
        if (number (root, "root", v)) params[ROOT_PARAM].setValue ((float) std::round (clampD (v, 0.0, 11.0)));
        if (flag (root, "minor", b)) params[MODE_PARAM].setValue (b ? 1.f : 0.f);
        if (number (root, "bars", v))
        {
            int best = 1;
            for (int i = 0; i < 4; ++i)
                if (std::fabs (v - BAR_COUNTS[i]) < std::fabs (v - BAR_COUNTS[best])) best = i;
            params[BARS_PARAM].setValue ((float) best);
        }
        if (number (root, "chaos", v)) params[CHAOS_PARAM].setValue ((float) clampD (v, 0.0, 1.0));
        if (flag (root, "run", b)) params[RUN_PARAM].setValue (b ? 1.f : 0.f);
        if (number (root, "seed", v)) seed = (uint32_t) clampD (v, 0.0, 4294967295.0);
        if (number (root, "analysisCap", v))
        {
            int best = 1;
            for (int i = 0; i < 3; ++i)
                if (std::fabs (v - CAPS[i]) < std::fabs (v - CAPS[best])) best = i;
            analysisCap = CAPS[best];
        }
        std::string f;
        bool haveFolder = false;
        if (json_t* j = json_object_get (root, "folder"))
            if (json_is_string (j)) { f = json_string_value (j); haveFolder = true; }
        json_t* arr = json_object_get (root, "slots");
        if (arr && ! json_is_array (arr)) arr = nullptr;
        SlotState s[4];
        for (int i = 0; arr && i < 4; ++i)
        {
            json_t* o = json_array_get (arr, (size_t) i);
            if (! o || ! json_is_object (o)) continue;
            if (json_t* p = json_object_get (o, "path"))
                if (json_is_string (p)) s[i].path = json_string_value (p);
            if (flag (o, "locked", b)) params[LOCK_PARAM + i].setValue (b && ! deckJson ? 1.f : 0.f);   // DECK: LOCK is a button
            if (number (o, "level", v)) params[LEVEL_PARAM + i].setValue ((float) clampD (v, 0.0, 1.0));
            if (number (o, "k", v)) s[i].k = (int) clampD (v, -1.0, 1.0);
            if (number (o, "s", v)) s[i].s = (int) clampD (v, -12.0, 12.0);
        }
        {
            std::lock_guard<std::mutex> lk (stateMutex);
            if (haveFolder) folder = f;
            if (arr) for (int i = 0; i < 4; ++i) slots[i] = s[i];
            hasFolder = ! folder.empty();
        }
        folderMissing = false;
        loadPending = true;   // the next process() asks the worker for the cache, the stems and the scan
    }
};

// ================================================================ widgets

static NVGcolor cWhite() { return nvgRGB (0xf2, 0xf2, 0xf4); }
static NVGcolor cDim() { return nvgRGB (0x8d, 0x8d, 0x96); }
static NVGcolor cMagenta() { return nvgRGB (0xff, 0x3d, 0x9a); }
static float px (float mm) { return mm2px (Vec (mm, 0.f)).x; }

static bool boxFont (NVGcontext* vg, float size)
{
    std::shared_ptr<window::Font> font = APP->window->loadFont (asset::system ("res/fonts/DejaVuSans.ttf"));
    if (! font || font->handle < 0) return false;
    nvgFontFaceId (vg, font->handle);
    nvgFontSize (vg, size);
    return true;
}

static float textWidth (NVGcontext* vg, const std::string& s)
{
    float b[4];
    return nvgTextBounds (vg, 0.f, 0.f, s.c_str(), nullptr, b);
}

// s with its middle replaced by an ellipsis until it fits maxW, cut on UTF-8 character boundaries
static std::string fitMiddle (NVGcontext* vg, const std::string& s, float maxW)
{
    if (textWidth (vg, s) <= maxW) return s;
    static const char* const ELLIPSIS = "\xE2\x80\xA6";
    std::string best = ELLIPSIS;
    size_t lo = 0, hi = s.size();
    while (lo < hi)
    {
        const size_t keep = (lo + hi + 1) / 2;
        size_t head = keep / 2, tail = s.size() - (keep - keep / 2);
        while (head > 0 && ((unsigned char) s[head] & 0xC0) == 0x80) --head;
        while (tail < s.size() && ((unsigned char) s[tail] & 0xC0) == 0x80) ++tail;
        const std::string t = s.substr (0, head) + ELLIPSIS + s.substr (tail);
        if (textWidth (vg, t) <= maxW) { best = t; lo = keep; }
        else hi = keep - 1;
    }
    return best;
}

static void line (NVGcontext* vg, const std::string& s, float x, float y, NVGcolor c)
{
    nvgFillColor (vg, c);
    nvgTextAlign (vg, NVG_ALIGN_LEFT | NVG_ALIGN_MIDDLE);
    nvgText (vg, x, y, s.c_str(), nullptr);
}

// Folder path (middle-ellipsised) over the scan status. Drawn on the light layer so it stays lit in a dimmed room.
struct PathBox : TransparentWidget
{
    Recycler* m = nullptr;

    void drawLayer (const DrawArgs& a, int layer) override
    {
        if (layer == 1 && boxFont (a.vg, 9.f))
        {
            std::string f;
            if (m) { std::lock_guard<std::mutex> lk (m->stateMutex); f = m->folder; }
            const float x = px (1.f), w = box.size.x - 2 * x;
            if (f.empty()) line (a.vg, "no folder", x, box.size.y * 0.28f, cDim());
            else line (a.vg, fitMiddle (a.vg, f, w), x, box.size.y * 0.28f, cWhite());
            std::string status;
            if (m && ! f.empty())
            {
                const int total = m->filesTotal.load(), ok = m->filesOk.load(), skipped = m->filesSkipped.load();
                if (m->folderMissing.load()) status = "folder missing";
                else if (m->scanning.load()) status = string::f ("scanning %d / %d\xE2\x80\xA6", ok + skipped, total);
                else status = string::f ("%d files \xC2\xB7 %d ok \xC2\xB7 %d skipped", total, ok, skipped);
            }
            if (! status.empty()) line (a.vg, fitMiddle (a.vg, status, w), x, box.size.y * 0.74f, cDim());
        }
        TransparentWidget::drawLayer (a, layer);
    }
};

// One stem's file name, right of the role caption the panel prints.
struct NameBox : TransparentWidget
{
    Recycler* m = nullptr;
    int slot = 0;

    void drawLayer (const DrawArgs& a, int layer) override
    {
        if (layer == 1 && boxFont (a.vg, 9.5f))
        {
            std::string path;
            bool missing = false, cued = false, deckOn = false;
            int pos = -1, n = 0;
            if (m)
            {
                std::lock_guard<std::mutex> lk (m->stateMutex);
                path = m->slots[slot].path;
                missing = m->slots[slot].missing;
                pos = m->slots[slot].deckPos;
                n = m->slots[slot].deckN;
                const uint32_t gen = m->slots[slot].gen;
                cued = gen != 0 && gen != m->landed[slot].load (std::memory_order_relaxed);
                deckOn = m->deck.load();
            }
            const float x = px (16.f), w = box.size.x - x - px (1.f);
            if (path.empty()) line (a.vg, "\xE2\x80\x94", x, box.size.y / 2, cDim());
            else
            {
                std::string label = system::getFilename (path);
                if (deckOn && pos >= 0) label = string::f ("%02d/%02d ", pos + 1, n) + label;   // 03/12 name
                if (deckOn && cued && ! missing) label = "\xE2\x80\xBA " + label;              // > cued: lands on the loop end
                line (a.vg, fitMiddle (a.vg, label, w), x, box.size.y / 2, missing ? cMagenta() : cWhite());
            }
        }
        TransparentWidget::drawLayer (a, layer);
    }
};

// FOLDER: a momentary button that opens the folder dialog when released.
struct FolderButton : VCVButton
{
    void onDragEnd (const DragEndEvent& e) override
    {
        VCVButton::onDragEnd (e);
        if (e.button != GLFW_MOUSE_BUTTON_LEFT) return;
        if (Recycler* m = dynamic_cast<Recycler*> (module)) m->chooseFolder();
    }
};

struct RecyclerWidget : ModuleWidget
{
    RecyclerWidget (Recycler* module)
    {
        setModule (module);
        setPanel (createPanel (asset::plugin (pluginInstance, "res/Recycler.svg")));
        namespace L = layout::recycler;
        {
            TalkingFace* f = createWidget<TalkingFace> (mm2px (Vec (L::FACE[0] - L::FACE[2], L::FACE[1] - L::FACE[2])));
            f->box.size = mm2px (Vec (2 * L::FACE[2], 2 * L::FACE[2]));
            if (module) f->tap = &module->face;
            addChild (f);
        }
        addChild (createWidget<ScrewBlack> (Vec (RACK_GRID_WIDTH, 0)));
        addChild (createWidget<ScrewBlack> (Vec (box.size.x - 2 * RACK_GRID_WIDTH, 0)));
        addChild (createWidget<ScrewBlack> (Vec (RACK_GRID_WIDTH, RACK_GRID_HEIGHT - RACK_GRID_WIDTH)));
        addChild (createWidget<ScrewBlack> (Vec (box.size.x - 2 * RACK_GRID_WIDTH, RACK_GRID_HEIGHT - RACK_GRID_WIDTH)));

        auto at = [] (const float* mm) { return mm2px (Vec (mm[0], mm[1])); };
        auto region = [] (Widget* w, const float* r) {
            w->box.pos = mm2px (Vec (r[0], r[1]));
            w->box.size = mm2px (Vec (r[2], r[3]));
        };
        PathBox* pathBox = new PathBox;
        region (pathBox, L::PATH_BOX);
        pathBox->m = module;
        addChild (pathBox);
        for (int i = 0; i < 4; ++i)
        {
            NameBox* n = new NameBox;
            region (n, L::NAME_BOX[i]);
            n->m = module;
            n->slot = i;
            addChild (n);
        }

        addParam (createParamCentered<FolderButton> (at (L::FOLDER_PARAM), module, Recycler::FOLDER_PARAM));
        addChild (createLightCentered<SmallLight<LimeMagentaLight>> (at (L::LIB_LIGHT), module, Recycler::LIB_LIGHT));
        addParam (createParamCentered<Rogan1PSWhite> (at (L::BPM_PARAM), module, Recycler::BPM_PARAM));
        addParam (createParamCentered<Rogan1PSWhite> (at (L::ROOT_PARAM), module, Recycler::ROOT_PARAM));
        addParam (createParamCentered<VCVLatch> (at (L::MODE_PARAM), module, Recycler::MODE_PARAM));
        addParam (createParamCentered<VCVLatch> (at (L::BARS_PARAM), module, Recycler::BARS_PARAM));
        addParam (createParamCentered<VCVLatch> (at (L::RUN_PARAM), module, Recycler::RUN_PARAM));
        addChild (createLightCentered<SmallLight<LimeLight>> (at (L::RUN_LIGHT), module, Recycler::RUN_LIGHT));
        addInput (createInputCentered<PJ301MPort> (at (L::CLOCK_INPUT), module, Recycler::CLOCK_INPUT));
        addInput (createInputCentered<PJ301MPort> (at (L::VOCT_INPUT), module, Recycler::VOCT_INPUT));
        addInput (createInputCentered<PJ301MPort> (at (L::RESET_INPUT), module, Recycler::RESET_INPUT));
        addInput (createInputCentered<PJ301MPort> (at (L::RUN_INPUT), module, Recycler::RUN_INPUT));
        for (int i = 0; i < 4; ++i)
        {
            addParam (createParamCentered<VCVButton> (at (L::ROLL_PARAM[i]), module, Recycler::ROLL_PARAM + i));
            addParam (createParamCentered<VCVLatch> (at (L::LOCK_PARAM[i]), module, Recycler::LOCK_PARAM + i));
            addChild (createLightCentered<SmallLight<LimeLight>> (at (L::LOCK_LIGHT[i]), module, Recycler::LOCK_LIGHT + i));
            addParam (createParamCentered<RoundSmallBlackKnob> (at (L::LEVEL_PARAM[i]), module, Recycler::LEVEL_PARAM + i));
            addInput (createInputCentered<PJ301MPort> (at (L::ROLL_INPUT[i]), module, Recycler::ROLL_INPUT + i));
            addOutput (createOutputCentered<PJ301MPort> (at (L::OUT_L_OUTPUT[i]), module, Recycler::OUT_L_OUTPUT + i));
            addOutput (createOutputCentered<PJ301MPort> (at (L::OUT_R_OUTPUT[i]), module, Recycler::OUT_R_OUTPUT + i));
        }
        addParam (createParamCentered<VCVButton> (at (L::BATCH_PARAM), module, Recycler::BATCH_PARAM));
        addInput (createInputCentered<PJ301MPort> (at (L::BATCH_INPUT), module, Recycler::BATCH_INPUT));
        addParam (createParamCentered<Rogan1PSWhite> (at (L::CHAOS_PARAM), module, Recycler::CHAOS_PARAM));
        addInput (createInputCentered<PJ301MPort> (at (L::CHAOS_INPUT), module, Recycler::CHAOS_INPUT));
        addChild (createLightCentered<SmallLight<LimeMagentaLight>> (at (L::RENDER_LIGHT), module, Recycler::RENDER_LIGHT));
        addOutput (createOutputCentered<PJ301MPort> (at (L::MIX_L_OUTPUT), module, Recycler::MIX_L_OUTPUT));
        addOutput (createOutputCentered<PJ301MPort> (at (L::MIX_R_OUTPUT), module, Recycler::MIX_R_OUTPUT));
    }

    void appendContextMenu (Menu* menu) override
    {
        Recycler* m = dynamic_cast<Recycler*> (module);
        if (! m) return;
        menu->addChild (new MenuSeparator);
        menu->addChild (createBoolMenuItem ("Deck mode", "", [=] { return m->deck.load(); }, [=] (bool on) { m->setDeck (on); }));
        menu->addChild (createMenuLabel ("Deck: files in name order; ROLL = next, LOCK = previous, swaps on the loop end"));
        menu->addChild (new MenuSeparator);
        menu->addChild (createMenuItem ("Rescan folder", "", [=] { m->rescan(); }));
        menu->addChild (createMenuItem ("Forget library", "", [=] { m->forget(); }));
        menu->addChild (createIndexSubmenuItem ("Analysis cap", { "30 s", "60 s", "120 s" },
            [=] { for (size_t i = 0; i < 3; ++i) if (CAPS[i] == m->analysisCap.load()) return i; return (size_t) 1; },
            [=] (size_t i) { m->analysisCap = CAPS[i]; }));
        menu->addChild (createMenuLabel ("The cap applies to files analysed after a change (Forget library + Rescan to redo all)"));
    }
};

Model* modelRecycler = createModel<Recycler, RecyclerWidget> ("Recycler");
