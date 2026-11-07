# Song-to-song transitions — design

Date: 2026-11-06 · Author: Ari Klopfer / A_Development · Sub-project 3 of the live-set work (1 = arp + acid, 2 = stutter, both done).
Approved by Ari 2026-11-06: "Each pair its own".

## Trigger

No new buttons. The existing fx 'transition' pad runs the move for the pair (song playing -> song on show). Ari turns to the next
song's page and presses it. Songs: Lowdown (page 1, deck A, D major), TOOM (page 2, deck B, D major), Disco Ulysses (page 3, deck D,
B major). Set clock 128. Every move starts on the next bar line of the set clock and counts bars on it.

## Moves

- **Blend** (same key: Lowdown <-> TOOM), 16 bars.
  - Bars 1-8: incoming drums + bass come in under the outgoing song (their rows' first pads, rising).
  - Bars 9-16: outgoing filters away (the existing high-pass sweep) and fades; incoming keys / vocals come in.
- **Break & drop** (key change: anything <-> Disco), 4 bars + a drop.
  - Bars 1-4: the outgoing song's slots stutter (Recycler STUT): 1/4 for bars 1-2, 1/8 for bar 3, 1/16 for bar 4, with an echo tail
    under it if the rig has an echo send (else a filter close).
  - Beat 4 of bar 4: air (outgoing strips at 0, STUT released).
  - Bar 5 downbeat: the incoming song full on (its first pads at their row levels, strip at unity).
  - While the key changes, the arp plays only the notes the two keys share (D major and B major share B C# E F#), then takes the new
    song's scale on the drop.
- Unlisted pairs use the move for their keys (same key = blend, different = break & drop).

## Rules

- A newer press cuts a running move off cleanly (the existing `alive()` guard): nothing writes after it, held STUT released.
- After a move: the old song's pads go dark, its deck is silent and reset for next time (as now).
- The table of moves is data (pair -> move name + bars), so a pair can be retuned without code.

## Checks

board_check offline: pair -> move choice, bar math, cut-off writes nothing after, STUT always released. test_live: one blend and
one break & drop on the rig (strips, STUT params and scale at each stage).
