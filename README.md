# My lil Recycler

A sample flipper for VCV Rack 2. Point it at a folder and it scans and analyses every WAV and AIFF in it (tempo, key,
and which role a sound can play), picks a drums + bass + melody + texture combo that fits, stretches and pitches each
stem to your clock and root, and loops all four in sync on four stereo outs and a mix. By A_Development.

## Set up

Press **FOLDER** and choose a folder; its subfolders are scanned too. The box beside it shows the folder and a status
line: `scanning 120 / 1234…` while it works, then `1234 files · 1200 ok · 34 skipped`, or `folder missing`.
Scanning runs in the background and the module keeps playing meanwhile. When it is done and no stem is loaded yet,
the first combo appears by itself.

The **LIB** light: off = no folder, blinking magenta = scanning, lime = ready, steady magenta = folder missing.

What the scan learns is cached in `<Rack user folder>/MyLilRecycler/library.json`, so a rescan only analyses new or
changed files. The cache is shared by every Recycler you have.

## Lock

| Control | What it does |
|---|---|
| **BPM** | Tempo, 40 to 240. |
| **CLOCK** | Quarter-note pulses. Overrides BPM and follows tempo ramps. If the clock stops, the loop free-runs at the last tempo. |
| **ROOT** | Key root, C to B. |
| **V/OCT** | Root from a pitch CV, quantised to the nearest semitone. Overrides ROOT. |
| **MODE** | Major or minor (click to toggle; the tooltip shows which). |
| **BARS** | Loop length: 1, 2, 4 or 8 bars (click to step; the tooltip shows which). |
| **RUN** / RUN gate | Start and stop. A patched gate overrides the button. The light shows running. |
| **RESET** | Back to the top of the loop. With a clock patched, on the next pulse. |

Changing tempo, root, mode or bars re-renders the stems after a short pause (0.2 s of no change). Until the new
renders land, the old ones keep playing in time. Tempo wobble under 1 % is ignored. The **RENDER** light blinks
magenta while stems are being rendered.

## Stems

Four rows: **DRUMS**, **BASS**, **MELODY**, **TEXTURE**.

| Control | What it does |
|---|---|
| **ROLL** button / jack | A new file for that slot. The trigger works too. |
| **LOCK** | Keeps the slot's file when you BATCH. The light is lime while locked. |
| **LEVEL** | Stem volume, up to +6 dB. More per-slot controls: see [Shaping each slot](#shaping-each-slot). |
| **STUT** | Hold to repeat a slice of the slot on the beat grid: see [STUT](#stut). |
| **OUT L / R** | The stem on its own: about ±5 V at 0 dB, up to about ±10 V at +6 dB. L carries the mono sum while R is unpatched. |

A new file comes in on the next loop start, with a short crossfade. The name beside each role: white = playing,
magenta = missing (the file is gone, or could not be read or rendered; the slot goes silent), dim dash = empty.

## Combo

| Control | What it does |
|---|---|
| **BATCH** button / jack | Re-rolls every unlocked stem at once. No file appears twice in a combo. |
| **CHAOS** | Low: only close tempo and key fits, the best-fitting files. High: wider stretch and pitch shift, any file that fits the role at all. |
| **CV** | Chaos CV, 0 to 10 V adds 0 to 100 %. |
| **MIX L / R** | Half the sum of the four stems, so it can go past ±10 V with several stems hot. L carries the mono sum while MIX R is unpatched. |

## File names help

A tempo in the name, like `120bpm` or `90 BPM`, is trusted as the file's tempo. A key in the name, like `Cmin`,
`F#maj`, `Am` or `Eb minor`, is used when the detected key is unsure.

## Saving

The patch stores the folder, the settings, the four file paths, the locks, the levels and the shaping (pitch,
filter, pan, start, reverse). On reopen the module reloads the cache, renders the four stems again and rescans
the folder. A saved file that is gone (or not in the cache) shows magenta and stays silent; a later scan that finds
it brings it back. A patch saved mid-scan keeps what was analysed so far.

## Formats

- WAV: 8 to 32-bit PCM and 32-bit float, mono or stereo.
- AIFF and AIFC: PCM, `sowt` and `fl32`.
- Other formats (MP3, FLAC and so on) are not scanned. A WAV or AIFF that cannot be read counts as skipped.

## Deck mode

Right-click > **Deck mode** plays your own crate in your order instead of re-rolling. The folder's files are the crate,
in file-name order. Each slot is a free deck: **ROLL** (button or jack) goes to the next file, **LOCK** goes back one
(it springs off again). Both wrap around, and every press counts. A step lands on the loop end like any swap; the name
box shows `03/12 name`, and `›` in front while the new file waits for the loop end (stopped, it lands at once). Turning Deck mode on loads files 1-4
into the four slots and releases every LOCK. Tempo and key lock still apply, by the file: a pitched loop is keyed on any
slot, a drum loop never. BATCH and CHAOS do nothing in Deck mode.

Make a crate from a list of paths (one per line) with `py -3 tools/mkcrate.py crate.txt <new folder>`: it copies the
files as `01_name`, `02_name` ... so the list order becomes the deck order. Recycler only reads WAV and AIFF, so other files leave gaps in the numbers.

## Deck display

Right of the transport, four lanes (D, B, M, T: one per slot, in row order) show where each deck is:

- **Waveform**: the playing loop's envelope (peaks faint, RMS solid) in the order you hear it, so START rotates it and REV
  mirrors it, with a white playhead. It changes when a new render lands (ROLL, a DECK step, PITCH, a tempo change).
- **Song map**: one block per loop of that slot's stem in the crate (the NN in `<n>-<stem>-<NN>[_<section>][-<tag>].wav`,
  e.g. `1-drums-07_chorus-120bpm.wav`), coloured by section: intro blue, verse lime, pre-chorus teal, chorus magenta,
  bridge orange, solo yellow, break lavender, outro deep blue, other grey. The playing loop is lit, the cued one outlined.

A `crate.json` in the folder (all keys optional; anything malformed is ignored) adds:

```
{ "title": "Doobie Fool", "cover": "cover.jpg", "sections": { "01": "intro", "02": "verse" } }
```

- `title` names the deck when you pick the folder, and when a patch loads the module unnamed. Name it in the menu
  afterwards and that name stays (it is saved). A new folder without a title leaves the deck unnamed.
- `cover` (else `cover.jpg` / `cover.png`) is drawn as a thumbnail at the right of the header.
- `sections` win over the section in the file name.

## Shaping each slot

Every slot row has its own shaping controls. They belong to the slot, so they stay put when you re-roll or step the deck.

- **LEVEL**: silent to +6 dB.
- **PITCH**: -12 to +12 semitones on top of the key lock. Tempo stays locked; the slot re-renders and the new pitch lands
  on the loop end.
- **FILT**: centre is off. Turn left for a low-pass sweep, right for a high-pass sweep.
- **PAN**: left to right; centre leaves the stem as it is. With the R jack unpatched the L jack carries mono (L + R), so
  PAN then only turns that slot down, up to -6 dB at a hard side.
- **START**: moves where the loop starts, in sixteenths of the loop.
- **REV**: plays the slot backwards.

Patches saved with 2.1 load with these at neutral and sound the same. The panel is 36 HP now: in an older patch, drag the
module to its right out of the way once.

## STUT

Hold a slot's **STUT** button (left of ROLL) and that slot repeats one slice: the slice that began on the last grid point
at or before the press. The grid is the slot's loop cut into **STUT LEN** pieces per bar: 1/4, 1/8 (default), 1/16 or
1/32 bar. The first pass plays on from where you pressed, then the slice repeats, each seam with a 3 ms fade. The loop
keeps running underneath, so on release the slot is back exactly where the song is (with the same short declick as
START and REV).

- START and REV still apply: a reversed slot stutters its reversed audio.
- Turn STUT LEN while holding and the slot jumps onto the new grid where the song is now, with no gap (a slide from 1/4
  to 1/8 keeps going).
- A new file landing while you hold stutters from its own grid point.
- A hold is never saved: a patch always loads with STUT up. Patches from 2.3 and older load with STUT LEN at 1/8.

## Right-click menu

- **Name**: type a name and the panel reads MY LIL <NAME> (for one Recycler per song); empty shows MY LIL RECYCLER. Saved
  with the patch as `title` in the module data; setting only `{"title": ...}` (e.g. over MCP) renames it live and changes nothing else.
- **Deck mode**: play the folder as a crate in file-name order (see Deck mode).
- **Rescan folder**: picks up new, changed and deleted files.
- **Forget library**: deletes the cache and empties the slots. Rescan to start over.
- **Analysis cap**: 30, 60 or 120 seconds analysed per file (default 60). Applies to files analysed after the change;
  Forget library and rescan to redo everything.

## Building

Rack SDK 2.6.6. On Windows (MSYS2, SDK at `C:\dev\Rack-SDK`) from PowerShell: `pwsh -File tools/mk.ps1` builds,
`pwsh -File tools/mk.ps1 test` runs the core checks, `pwsh -File tools/mk.ps1 dist` packs the plugin. Elsewhere:
`make`, `make test`, `make dist` with `RACK_DIR` set. The core (`core/`) and its tests need no Rack.

MIT licence. Author: Ari Klopfer / A_Development.
