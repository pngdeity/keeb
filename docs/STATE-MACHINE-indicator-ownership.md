# The indicator frame-ownership composite

**What this document is.** A *composite relation between decisions*: the set of painters
that write the RGB matrix in one frame pass and the rule that arbitrates which of them
owns the frame. **No file owns it** — it lived in the *order of calls* inside a single
function (`rgb_matrix_indicators_advanced_kb`, `epomaker_split65.c`) plus one early
`return true`. It is `docs/DETERMINATION.md` §II.3 **artefact 2** (the indicator matrix's
ownership chain, `TODO.md` §7).

**What artefact 2 is — and is not.** It is **not** the boot code's latch. That latch was a
real latent hazard (`TODO.md` §7: *a state whose only exit is a call the same state
suppresses*), and it was fixed and pinned separately: `wls_indicator_boot_code_owns_matrix()`
now computes its own deadline (`wls_indicator.c:449-464`), so the claim's expiry is a fact
readable without the paint running. Artefact 2 is the relation **around** that owner: the
arbitration between all painters, which the §7 fix left untouched.

**How it was derived.** By **symptom-directed backward slice** over the frame pass's
control and *positional* structure, per `docs/DETERMINATION.md` §I.9 — not by directory
shape. The slicing criterion is an observable the board states:

- **The invisible indicator** — a cue painted at a call site that the pass's early return
  makes unreachable (`TODO.md` §7's observed session: *"no indicator appeared at all on
  the right half's top row"*).

**The gap, in one sentence.** The rule relating the painters was *entailed by their order*
and stated by none of them, so moving a paint call across one `return` changed which
indicator the board shows, and **nothing failed**.

Every line citation below was read in the file. Nothing here is inferred.

---

## 0. The invariant this document gives a home

> **An exclusive claim on the frame suppresses every other painter, and the claim must be
> decidable from a fact that is readable without any paint running.**

Two consequences:

> **C1 (exclusivity).** While the boot diagnostic code plays, it is the only painter:
> it is the one instrument that must be readable with the USB line down, so nothing may
> overwrite it.

> **C2 (release is a fact).** The claim ends by its deadline or a keypress — both readable
> without the paint that would otherwise be the only thing able to end it. A claim whose
> sole exit is a call the claim itself suppresses can never end.

C2 is the §7 hazard and is fixed. C1 is the arbitration, and it had no home above the
per-frame code until this document; it now has an executable one
(`wls_frame_owner_of`, `indicator_logic.{h,c}`).

---

## 1. The painters, and how each claims the frame

The frame pass (`rgb_matrix_indicators_advanced_kb`) calls, in this order:

| # | Painter | What it writes | Claims the frame? |
|---|---|---|---|
| 1 | `rgb_matrix_indicators_advanced_user` | the keymap's own indices | no — composes |
| 2 | the caps-lock / win-lock cue | two fixed indices | no — composes |
| 3 | `rgb_matrix_indicators_advanced_rgblight` | the rgblight layout | no — composes |
| 4 | `wls_indicator_boot_code_start()` + `wls_indicator_boot_code()` | **every** LED (`rgb_matrix_set_color_all`) | **yes — exclusive** |
| 5 | `wls_indicator_channel_flash` / `_link_state` / `_channel_state` | their own indices | no — composes |
| 6 | `wls_indicator_battery_blink` / `_battery` | their own indices | no — composes |
| 7 | `wls_indicator_set_flash` | its own indices, **or all** (an `0xFF` entry) | **overwrites** |
| 8 | the `confinfo.filp` marker, `query()` | one index / the diag query | no |

**The three facts that were stated nowhere together:**

1. **Only painter 4 is exclusive**, because it writes *every* LED. Every other painter
   writes a subset, so they compose by index rather than by arbitration.
2. **The claim is on the *frame*, not on the LEDs after it** — the suppression is the
   pass's early `return true`, which abandons the *rest of the pass*, not the buffer.
3. **Painter 7 can write *all* LEDs.** `wls_indicator_set_flash()` walks its armed blink
   table and, for any entry whose `index == 0xFF`, calls `rgb_matrix_set_color_all`
   (`wls_indicator.c:258-259`) — otherwise a single `rgb_matrix_set_color` (`:261`). So it
   is not an exclusive *owner* but it can be an exclusive *effect*: such an entry repaints
   the whole matrix. It is kept off the code's frame by coming after the early return.
   **This is the ordering the pass's structure silently defends**, and the reason the
   boot-code design note (`boot_code_logic.h`'s rationale, reason 1: *"it was not
   exclusive: `wls_indicator_set_flash()` ran after it in the same frame pass"*) exists.

---

## 2. Why a call-graph slice does not reach this

A call slice from the frame pass reaches every painter — they are all its callees. What it
does not represent is the **relation between them**: "painter 4 suppresses 5–8" is not an
edge in any graph the tree has. It is a property of one statement's *position*:

```
    wls_indicator_boot_code();                                   // painter 4
    if (wls_indicator_boot_code_owns_matrix()) { return true; }   // <-- the whole rule
    wls_indicator_channel_flash();                                // painter 5
    ...
```

The successor relation of that `return` *is* the arbitration. This is `DETERMINATION.md`
§I.9's second missing relation — `ct` over a refused edge, here a *suppressed* one — and it
is invisible to a traversal that models calls and data but not position.

---

## 3. The arbiter (the home this document creates)

The rule is one decision, so it is one pure function, in the core the indicators already
own (`wls/indicator_logic`):

```c
typedef enum {
    WLS_FRAME_OWNER_NONE = 0,
    WLS_FRAME_OWNER_BOOT_CODE,   /* exclusive */
} wls_frame_owner_t;

bool              wls_frame_owner_is_exclusive(wls_frame_owner_t owner);
wls_frame_owner_t wls_frame_owner_of(bool exclusive_claim_live);
```

- `wls_frame_owner_of()` takes the **claim's liveness as a fact**, not the painter — so the
  caller must decide the claim *before* painting, which is exactly C2. For the boot code
  the fact is `wls_indicator_boot_code_owns_matrix()`, which computes its own deadline.
- `wls_frame_owner_is_exclusive()` is the suppression predicate, kept as a switch over the
  enum rather than an equality test, so adding a second exclusive owner is a decision made
  in the core with tests — not a silent property of a new enum value.
- The frame pass now gates on `wls_frame_owner_is_exclusive(wls_frame_owner_of(...))`.
  The *visible behaviour is identical*; what changes is that the rule is now readable
  without reading the pass's line numbers.

**What the frame arbiter deliberately does not do.** It does not reorder the pass. Painters 5–8
still compose by index in their existing order. Making *that* a rule is the separate LED-index
arbiter (`wls_led_painter_of` and friends, §4 and §5): the frame arbiter decides *who owns the
frame*, the LED arbiter decides *who owns which LED*. The LED rule is determined at the
unrepresentable rung — every painter is forced through the chokepoint (`wls_indicator_led_write`,
§4 and §5) — so the residue this paragraph used to name is closed.

---

## 4. What is determined, weakly determined, and undetermined

| Property | Home | Rung (`II.2`) |
|---|---|---|
| C1: an exclusive claim suppresses the rest | `wls_frame_owner_is_exclusive` + test | **executable** |
| C2: the boot code's claim expires from a fact | `wls_indicator_boot_code_owns_matrix` (`:449-464`) | **executable** |
| The pass gates on the arbiter, not on a position | `bin/guard-invariants` (2 checks) | **executable** |
| The painters and their precedence order | `wls_led_painter_precedence` (`indicator_logic.c`) | **executable** (2026-10-16) |
| **Which painter owns which LED index (overlaps)** | `wls_led_painter_of` + tests + guard | **executable** (2026-10-15) |
| **Whether a painter added later is exclusive** | `wls_led_painter_is_exclusive` + tests | **executable** (2026-10-15) |
| **May painter P write index I (the chokepoint)** | `wls_led_may_write` + `wls_indicator_led_write` + tests + guards | **unrepresentable** (2026-10-16) |
| **The LED index space bound** | `WLS_LED_INDEX_MAX` + guard (`keyboard.json`) | **executable** (2026-10-16) |

The last four rows are D3/D4. The frame arbiter decides *who owns the frame*;
`wls_led_painter_of` decides *who owns which LED*, so two non-exclusive painters that write the
same index no longer resolve by call order. **The chokepoint closes the rung-3 target:** every
board painter (the channel flash, cue, link cue, battery, set-flash, marker, caps, win-lock and
boot code) now writes through `wls_indicator_led_write*`, which asks `wls_led_may_write` first —
so "a painter writes an LED it does not own" is *refused*, not merely caught by a rule test.
`WLS_LED_INDEX_MAX` bounds the scan by the board (68 LEDs, max index 67) and is pinned by a guard.

**What is deliberately out of scope.** `rgb_record.c` (the RGBR_PLAY custom effect, a QMK effect
outside the frame pass) and `wls_keymap.c` are the open-ended painter surfaces the core does not
claim; `rgb_record`'s effect is instead reserved as an **exclusive** painter (`WLS_LED_PAINTER_RGBREC`),
which is why the board's battery suppression is now `!wls_indicator_led_claim_live()` rather than a
positional `!rgbrec_is_started()` test.

---

## 5. What this document implies for the fix of artefact 2

Per `docs/DETERMINATION.md` §II.2, in ascending strength:

1. **Prose (done here).** The painters, their claims, and the arbitration are written down.
2. **Executable (done, 2026-10-15).** `wls_frame_owner_of` / `wls_frame_owner_is_exclusive`
   (`indicator_logic.{h,c}`), pure, with 5 vectors in `tests/indicator_logic` (12 tests)
   pinning the exclusivity, the claim's two outcomes, and the composition the pass relies
   on. Two `bin/guard-invariants` checks keep the pass gating on the arbiter rather than on
   the raw predicate; both were **negative-tested**.
3. **Unrepresentable (reached, 2026-10-16).** Give every painter an index range and arbitrate
   overlaps in the core, so a painter that writes an LED it does not own cannot be written.
   Now done: `wls_led_painter_of` / `wls_led_painter_is_exclusive` / `wls_led_may_write` state
   the rule, `wls_indicator_led_write*` is the one write path and asks it, and three
   `bin/guard-invariants` checks (all **negative-tested**) keep a raw matrix write out of the
   board's LED sources, keep the chokepoint asking the rule, and pin the index bound to the
   board. The precedence order has one home (`wls_led_painter_precedence`), so the winner rule
   and the may-write rule cannot drift apart.

---

## 6. Provenance

- Symptom and session: `TODO.md` §7 (the boot-code latch; the observed invisible
  indicator) and `docs/OBSERVATIONS.md` (the 2026-10-15 session).
- The defect class: `docs/FINDINGS.md` — *a state whose only exit is a call the same state
  suppresses*, and its mirror, *a rule owned by no file*.
- The method: `docs/DETERMINATION.md` §I.9 (the symptom-directed backward slice over data,
  control, shared state **and transition guards**) and §II.3 artefact 2.
- The prior fix this document builds on, and does not replace: `TODO.md` §7's fix
  (`wls_indicator_boot_code_owns_matrix()` computes its own expiry), submodule history.
- The arbiter and its vectors (2026-10-15): `indicator_logic.h` (`wls_frame_owner_t`,
  `wls_frame_owner_of`, `wls_frame_owner_is_exclusive`), `indicator_logic.c`,
  `epomaker_split65.c` (the pass gates on the arbiter),
  `tests/indicator_logic/indicator_logic_tests.cpp` (12 tests),
  `bin/guard-invariants` (2 checks, negative-tested).
- The LED-index arbiter (2026-10-15, D3/D4): `indicator_logic.h` / `.c`
  (`wls_led_painter_t`, `wls_led_painter_of`, `wls_led_painter_is_exclusive`,
  `wls_led_painters_overlap`, `wls_led_can_paint`), `wls_indicator.c`
  (`wls_indicator_channel_state` consults `wls_led_can_paint`),
  `tests/indicator_logic/indicator_logic_tests.cpp` (20 tests),
  `bin/guard-invariants` (3 further checks, negative-tested).
- The chokepoint and the index bound (2026-10-16, D3/D4's unrepresentable rung):
  `indicator_logic.{h,c}` (`wls_led_may_write`, `WLS_LED_INDEX_MAX`,
  `WLS_LED_PAINTER_{RGBREC,CAPS,WIN_LOCK}`, `wls_led_painter_precedence`),
  `wls_indicator.{h,c}` (`wls_indicator_led_write` / `_all` / `_claim_live` /
  `_reject_live`, and every painter migrated to them), `epomaker_split65.c` (the
  caps / win-lock / marker writes and the battery suppression),
  `tests/indicator_logic/indicator_logic_tests.cpp` (28 tests),
  `bin/guard-invariants` (3 further checks, all negative-tested).
- The `sleep_order_logic` type rename (2026-10-16): `wls_sleep_order_t` →
  `wls_sleep_arm_t` (and its `_IDLE`/`_HOLD`/`_NOW`/`_tick` family), because the
  arming timer and `split_logic`'s cross-half order handle shared one name and a
  bare `-fsyntax-only` on `wls_indicator.c` failed on the collision. The
  `split_logic` handle keeps its name (it is the order). Provenance: the two
  types were created the same day by two extraction slices that never knew of
  each other.
