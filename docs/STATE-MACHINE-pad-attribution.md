# The pad → wake-code attribution

*Artefact 3 of `docs/DETERMINATION.md` §II.3. Derived by the §I.9 symptom-directed backward
slice over data, control, and the two relations off-the-shelf slicing misses: shared mutable
state (`dd`) and transition guards (`ct`). The symptom is a wake that does not wake.*

## 0. The invariant

> **A wake code may be excluded from the board's armed mask only when the pad that code is
> reported on is still reachable through a code the board arms.**

The board's `lpwr_wakeup_armed_mask()` returns a *set* of codes it claims to arm. The machine
then treats a fired code as real only if it intersects that set
(`lpwr_wakeup_is_real`, `lowpower_logic.h`). Excluding a code is therefore a promise: *"an
edge that arrives stamped with this code is not a wake I care about."* The invariant is the
condition under which that promise is true rather than a discarded real keypress.

## 1. Why the promise can be false (the mechanism)

The WB32 EXTI is **pad-numbered, port-discarded**:

- `PAL_PAD(line) = line & 0x0F` — chibios-contrib `os/hal/ports/WB32/LLD/GPIOv1/hal_pal_lld.h`.
  The line identifier encodes the port in the upper bits and the pad in the low four; the
  decode keeps only the low four.
- `pal_events_init()` (`epomaker_split65/wireless/lpwr_wb32.c:82-87`) registers **one callback
  per pad index 0-15**, `_pal_events[16]`, and the callback receives that index.
- `palcallback()` (:59-80) classifies by **which pin was registered under that pad**: it
  switches on `PAL_PAD(UART_RX_PIN)` and `PAL_PAD(A12)`, and everything else falls to the
  `default` that stamps `LPWR_WAKEUP_MATRIX`.

Consequence: **two pins on different ports with the same pad number are indistinguishable.**
This board's UART RX is `C11` (`config.h:76`) and a left matrix column is `B11`
(`keyboard.json` `matrix_pins.cols`); both are **pad 11**. An edge on either arrives as pad
11 and is stamped `LPWR_WAKEUP_UART`, because pad 11 is the pad UART registered under.

So a UART-stamped code can come from the matrix. If the board armed UART, a matrix keypress
on `B11` would be acted on as a *module* wake. The board does **not** arm UART (its own
traffic would defeat deep sleep), so that phantom is discarded — and the question the whole
artefact turns on is: **does discarding UART-costs discard a real key?** Only `B11`'s edges
are mislabelled; every other matrix pad reports `MATRIX` and wakes. The exclusion is sound
**because UART's pad is itself covered by an armed code.**

## 2. The attribution table (measured, not asserted)

Read from `palEnableLineEvent` sites and the `palcallback` classification switch:

| Code | Reporting pad | Pin(s) | Registered at |
|---|---|---|---|
| `LPWR_WAKEUP_UART` | 11 | `C11` (UART RX) | not registered (see below) |
| `LPWR_WAKEUP_USB` | 12 | `A12` | `lpwr_wb32.c:153` |
| `LPWR_WAKEUP_CABLE` | 7 | `HS_BAT_CABLE_PIN` = `A7` | `wls.c:356` |
| `LPWR_WAKEUP_SWITCH` | 14, 15 | `HS_BT_DEF_PIN` `C14`, `HS_2G4_DEF_PIN` `C15` | `wls.c:323,331` |
| `LPWR_WAKEUP_MATRIX` | *default* | every other registered pad | `lpwr_wb32.c:108,123,139,150` |

Two facts this table makes plain, which the comment referred to but no file stated:

1. **MATRIX is the catch-all.** It is not a pin; it is the classifier's `default`. Every pad
   that some other code did not claim reports MATRIX.
2. **UART is not registered at all** on this board: `lpwr_wb32.c`'s `lpwr_exti_init()` never
   calls `palEnableLineEvent(UART_RX_PIN)` (the upstream `linker/wireless/lpwr_wb32.c:107`
   does; this board's `:144-146` deliberately omits it). Yet `C11` is still *reachable as a
   pad* — through `B11`, the matrix column that shares it.

Pad 11 is therefore **covered**: an edge there is stamped UART and dropped, but the same
physical pad is registered as matrix column `B11`, so a real key on that column *also* fires
its own matrix line event and reports MATRIX. Both stamps can fire for one press; the mask
keeps the one that matters. This is exactly the multi-bit case `lpwr_wakeup_is_real` is built
for (`wake_set & armed_mask`, not the last code seen).

Every pad on this board has collisions at some pad number (measured across `matrix_pins` plus
the special pins; pads 0-4, 6-7, 9-15 all carry two or more roles). That is the general
condition, and it is why the rule must relate the mask to the attribution rather than be
evaluated on the mask alone.

## 3. Why a call-graph slice misses it

UART's *exclusion* is one token in one function (`wls.c` `lpwr_wakeup_armed_mask`). A
call-only traversal sees the mask and stops: the function returns a constant, the constant is
consumed by `lpwr_wakeup_is_real`, and nothing in that chain references a pin. The relation
that makes the constant *correct* is between:

- the mask (a set of wake codes), in `wls.c`, and
- the pad registration + classification (which pin maps to which code), in
  `epomaker_split65/wireless/lpwr_wb32.c` and `wls.c`'s `palcallback_cb`,

and it is carried by **a pad number** — a shared fact (`dd` over the pad numbering) that
neither file owns. The mask's comment was the only place the two were even mentioned
together, and a comment cannot fail. This is the §I.9 gap the slice had to add by hand, plus
the `ct` relation: the `default` arm is a *guard-like* catch-all, an edge the slice assumed
was "the matrix case" and which is in fact "every pad nobody claimed."

## 4. The determined / undetermined ledger

| Property | Home | Rung (`II.2`) |
|---|---|---|
| An excluded code's pad must be covered by an armed code | `lpwr_excluded_code_is_safe` + test | **executable** |
| The board's mask is built through that predicate | `wls.c` `lpwr_wakeup_armed_mask` + `bin/guard-invariants` | **unrepresentable** (the hand-written form is refused) |
| Which pin each code is *registered* under (the attribution itself) | `lpwr_code_of_pad` / `lpwr_pad_of_code` + tests + `bin/guard-invariants` | **executable** + guard |
| That no *other* pad collision drops a wake | composed test from the attribution | **executable** |
| Whether the WB32 EXTI truly reports port-agnostically on this silicon | `lowpower.h` comment; no check | **undetermined** |

The attribution and the collision argument (§2) are no longer prose. Both were *derived by reading the `palEnableLineEvent` sites*, and that derivation is now a function: `lpwr_code_of_pad(attr, pad, is_master)` returns the code a pad reports (with `MATRIX` as the `default_code` field rather than a firmware macro, so the pure core keeps its no-`lowpower.h` contract), and the board's `palcallback_cb` is a **caller** of it rather than a second `switch`. That closes **D6** at the executable rung: a pin move now updates the code and the classifier together, and a `switch` that restated the pads fails a guard. **D7** closes with it — the "no other collision drops a wake" argument becomes two composed tests over the derived map: every *registered* pad reports either an armed code or the one covered exclusion (UART), and every *unregistered* pad reports the armed default. A future pin move that put an unarmed code on a registered pad fails those tests, which the prose could not enforce.

Two consequences this makes plain, and one honest floor:

- The **inverse lookup** (`lpwr_pad_of_code`) is the mask's question ("which pad does this code claim") and is pinned consistent with the forward map by a round-trip test, so the two cannot drift.
- The **`is_master` gate** is part of the attribution, not a property of the classifier: the mode-switch pads exist only on the master, so on the slave a pad-14/15 edge reports the default. A test pins that, because arming a wake source the slave never registered is a phantom in the other direction.
- **Port-agnostic reporting** stays a premise. It is a property of the WB32 EXTI hardware, read from the ChibiOS LLD source (`PAL_PAD`), not measured on this part. It is **D10** below.

The attribution-table row is **D6**, the collision argument **D7**, and port-agnostic
reporting **D10** in `TODO.md` "Determination residue".

## 5. The three-rung path

Per `docs/DETERMINATION.md` §II.2, in ascending strength:

1. **Prose (was the state).** The rule lived in the mask's comment: "UART is deliberately
   absent ... the module UART RX pad is aliased to a matrix column."
2. **Executable (done, 2026-10-15).** `lpwr_excluded_code_is_safe(excluded, covered)` in
   `lowpower_logic.{h,c}`: `!excluded || covered`. Four vectors in `tests/lowpower_logic`
   (26 tests), including the composed case the board builds its mask with. **And the
   attribution itself (D6/D7):** `lpwr_code_of_pad` / `lpwr_pad_of_code` /
   `lpwr_pads_collide` state which code each pad reports and which pads collide, with the
   board's classifier a *caller* of the first (so a fourth rung is not needed for it — the
   second copy is refused by the guard, below). Nine new vectors cover the map, the master
   gate, the inverse round trip, the collisions, and the two composed "no collision drops a
   wake" checks.
3. **Unrepresentable (done, 2026-10-15, for the mask's *shape* and the classifier).** The board's
   `lpwr_wakeup_armed_mask()` no longer returns a hand-written constant: it classifies UART
   (`uart_is_armed`, `uart_pad_is_covered_by_matrix`) and computes the code through the
   predicate. Two checks in `bin/guard-invariants` — the mask must be built through
   `lpwr_excluded_code_is_safe`, and must not be a bare `return LPWR_WAKEUP...` constant —
   each negative-tested. The hand-written form is now unwritable without failing the guard.
   **The classifier too:** `palcallback_cb` may not restate the pads — a `switch` with
   `case PAL_PAD(...)` cases fails a third guard — so the classifier is a *caller* of
   `lpwr_code_of_pad`, and "the attribution has a second copy" is unwritable (D6).

The rung-3 form is deliberately *not* a hard failure at runtime: an unsound exclusion falls
through to **arming the code**, so the board fails toward waking on a phantom rather than
toward discarding a real key. The guard is what turns a wrong attribution into a build-time
complaint; the runtime behaviour is the safe floor.

## 6. Provenance

- Symptom and session context: `TODO.md` §8 and the `lpwr_wakeup_armed_mask` comment history
  (`wls.c`).
- The mechanism: `PAL_PAD` in
  `qmk_firmware/lib/chibios-contrib/os/hal/ports/WB32/LLD/GPIOv1/hal_pal_lld.h:180`; the
  pad-indexed callback array `_pal_events[16]` and `pal_events_init()` in
  `epomaker_split65/wireless/lpwr_wb32.c:82-87`; the classifier `palcallback()` at `:59-80`;
  the board overrides in `wls.c:359-378` (`palcallback_cb`).
- The pads: `keyboard.json` `matrix_pins` (and `split.matrix_pins.right`),
  `config.h:9,75,76,81,82` (`HS_BAT_CABLE_PIN`, `UART_TX/RX_PIN`, `SERIAL_USART_TX/RX_PIN`),
  `wls.h:17,18` (`HS_BT_DEF_PIN`, `HS_2G4_DEF_PIN`).
- The predicate and its home: `keyboards/linker/wireless/lowpower_logic.{h,c}`
  (`lpwr_excluded_code_is_safe`, `lpwr_wakeup_is_real`, and now `lpwr_attribution_t`,
  `lpwr_code_of_pad`, `lpwr_pad_of_code`, `lpwr_pads_collide`); the mask
  (`wls.c` `lpwr_wakeup_armed_mask`); the classifier (`wls.c` `palcallback_cb`, a caller of
  `lpwr_code_of_pad`); the tests (`tests/lowpower_logic/lowpower_logic_tests.cpp`, 26 tests);
  the guards (`bin/guard-invariants`, three checks for the attribution). The attribution row
  is D6 and the collision argument D7 in `TODO.md` "Determination residue".
- The weak default on the other side: `lowpower.c:252-258` (`lpwr_wakeup_armed_mask` weak
  decl/def, default `-1` = every code armed), and its contract comment,
  `lowpower.h:42-58`.
