# The context map

**Status: current as of 2026-10-16.** This document states, for every decision
core in the firmware, *what model it owns*, *what language it speaks*, and
*which other contexts it depends on and why*. It is the strategic-design
artefact that the module set never had: eleven cores were each extracted from a
fault, so the set is **accreted, not derived**, and its seams have never been
written down as a whole.

Nothing here is a proposal to restructure the code. The map's first job is to
make the *existing* boundaries legible, so that the four boundary defects in §6
can be judged against a stated model rather than against taste. Two of the four
are evidence-gated rows that should be fixed; two are recorded and deliberately
not fixed.

The vocabulary is DDD's *strategic* half — Bounded Context, Context Map,
Conformist, Shared Kernel, Separate Ways — because that is the half that applies
to a set of small subsystems glued together with ad hoc interfaces. The
*tactical* half (Aggregate, Entity, Value Object) does **not** apply: those
patterns are defined for transactional consistency boundaries, and this firmware
is single-threaded with no transactions. The pure cores are a stronger variant
of the same idea, not a mismodelling of it. §7 records that judgement with its
sources so it is not re-litigated.

---

## 0. How to read this map

**A context is a boundary inside which one model is valid.** Its test, in this
codebase, is mechanical: *can this model's decisions be stated without including
another context's vocabulary?* Every core here passes that test — verified, and
it is the property that makes them host-testable (§1).

**An edge is a dependency across a boundary.** Its direction runs
**upstream → downstream**: the upstream context's model is the one that must be
satisfied, and the downstream one conforms to it or translates it. Every edge is
given an **explicitly chosen pattern** — that choice is the point of a context
map. An edge with no pattern is an unmanaged interface.

**Indirection is a first-class fact here.** No core includes another core's
header (§1). Every edge between two cores is therefore *indirect*: it passes
through a shell that reads one core's output and supplies the other's input.
That is deliberate (it is how the cores stay pure) and it is also the mechanism
by which a relation between two contexts can lose its home — the cross-axis
problem `docs/ADR-cross-axis-contracts.md` scopes. Each edge below notes
whether it is direct or shell-mediated, and §6 names the one where the
mediation currently loses information.

---

## 1. The measured facts this map is built on

All measured, none recalled.

- **Eleven cores.** Ten under `qmk_firmware/keyboards/epomaker/epomaker_split65/wls/`
  (`boot_code_logic`, `diag_logic`, `indicator_logic`, `jump_journal_logic`,
  `keymap_logic`, `reset_logic`, `rgb_key_logic`, `sleep_order_logic`,
  `split_logic`, `transport_logic`) and one under
  `qmk_firmware/keyboards/linker/wireless/` (`lowpower_logic`).
- **No core includes another core's header.** Verified by searching every
  `_logic.h` for `#include "..._logic.h"` — zero hits.
- **No core header includes anything outside the C standard library.** Verified
  by searching every `_logic.h` for non-`stdbool`/`stdint`/`stddef` includes —
  zero hits. This is why every core compiles into host tests.
- **Eleven cores, zero core-to-core includes, zero external includes** is the
  whole reason this map is needed: nothing in the code states the relationships,
  because no file can see two contexts at once.
- **`transport_logic` is the hub**: its header is included by twelve files,
  more than twice any other core. It is also the only core that serves more than
  one axis (§6.2).

---

## 2. The contexts

Each row states the context's **model** (the one thing it owns), its **language**
(the vocabulary it defines and exports), and its **inputs** (what it must be
told, and by whom).

| Context | Owns | Its language (exports) | Told by the shell |
|---|---|---|---|
| **`lowpower_logic`** | whether a stop may proceed, and whether the wake codes count as a real wake | `lpwr_presleep_is_allowed_decide`, `lpwr_stop_is_allowed`, `lpwr_excluded_code_is_safe`, `lpwr_code_of_pad` / `lpwr_pad_of_code`, `lpwr_pads_collide`, `lpwr_arm_is_coherent` | the pad a line landed on, whether mode switches order a sleep, whether an arm accompanied it |
| **`transport_logic`** | which transport the board is on, and what the module link is doing | `hsm_transport_input_is_pure`, `hsm_boot_devs`, `hsm_switch_pos_of_mode`, `hsm_devs_is_bt`, `hsm_btdev_or`, `hsm_confinfo_needs_default`, the `hsm_link_*` watch/cue family, `hsm_usb_teardown_is_safe`, `hsm_usb_teardown_refused` | switch position, the module's reported state, host events |
| **`split_logic`** | what a split-link command byte means, and whether the master may order the slave to stop | `wls_split_decide_slave`, `wls_split_decide_master`, `wls_sleep_order_open`/`_permitted`, `wls_sleep_release_open`/`_permitted`, `wls_split_can_order_sleep`, `wls_split_can_send_relay` | the command byte and body; **whether a release is reachable on the current transport** |
| **`sleep_order_logic`** | the low-battery sleep order's time rule | `wls_sleep_order_tick`, `wls_sleep_order_t` (arming timer) | battery is at/below the stop threshold; the clock |
| **`indicator_logic`** | who owns the LED frame, and who owns which LED index | `wls_frame_owner_of`, `wls_frame_owner_is_exclusive`, `wls_led_painter_of`, `wls_led_painter_is_exclusive`, `wls_led_painters_overlap`, `wls_led_can_paint`, the blink and battery-colour rules | whether the boot code is live; the painter asking |
| **`boot_code_logic`** | the boot diagnostic code: what to paint, when, on the LED rail with no host | `wls_boot_code_at`, `wls_boot_code_owns_matrix`, `wls_boot_stage_*` | the reset cause and the boot facts |
| **`rgb_key_logic`** | the RGB / rgblight keycodes' thresholds and effects | the `QK_RGB_MATRIX_*` decision family | the keycode and the led state |
| **`keymap_logic`** | the `confinfo.filp` key-remap decision | the filp remap family | the key, the active layer, the system |
| **`reset_logic`** | the settings reset as a pure ordered plan | `hs_reset_*` plan steps | triggers: eeprom-clear hold, keycode, tooling |
| **`diag_logic`** | encoding/decoding the firmware's own state snapshot | the diag encode/decode family | the snapshot fields |
| **`jump_journal_logic`** | mapping the jump-journal record to wire bytes | the journal encode family | the record the shell holds in `section(".ram0")` |

**Two of these own no domain axis at all**, and that is a fact worth stating:
`diag_logic` and `jump_journal_logic` exist because *the shell had no way to be
observed* — they are tooling contexts, extracted from an observability fault,
not from a domain fault. Keeping that distinction visible is what stops the map
from implying eleven domain boundaries where there are nine and two tools.

---

## 3. The upstream boundaries (not ours)

Three upstream models bound this design. Each gets an explicitly chosen
relationship — this is the decision the map exists to record.

### 3.1 QMK upstream — **Conformist**

Upstream's `connection` model (`connection_host_t`, `connection_set_host`) and
its host-driver contract are *the* transport vocabulary. This board does not
translate them; it adopts them. That is correct: the model is stable, upstream
owns it, and we have no leverage over it. `docs/FINDINGS.md` "the transport WAS
three partial state machines" records the resolution — the vendor selector was
deleted and `host_get_active_driver()` became the single sink chooser, i.e. we
**conformed**, and the partial machines went away.

*What conformance obliges:* changes to upstream's connection model are not ours
to soften. A mismatch is a finding to record, not a translation layer to add.

### 3.2 The vendor module (WB32 / CH582F) — **Conformist, with one ours-side contract**

The module's wire (`module.h`, `smsg.c`, `md_frame.h`) is a fixed hardware fact
and is kept as-is; `module.h`'s `DEVS_*` vocabulary is the device-index language
and we adopt its values. The CH582F's GATT/address faults are worked around
**board-locally**, never patched into an upstream-shaped contract (the doctrine
in `AGENTS.md` "Priority of code sources" and `docs/HARDWARE.md` "The Layer
boundary").

*The one deliberate exception:* the wireless-module abstraction we added
(`drivers/wireless/wireless_2p4ghz.*` and the `CONNECTION_HOST_2P4GHZ` cases) is
a **generic model gap** — a transport upstream forgot to enumerate — and is
written to be upstreamable. That is the split: vendor faults stay local, generic
model gaps are shaped for upstream.

### 3.3 The bootloader (wb32-dfu) — **Separate Ways**

The DFU bootloader shares no model with the firmware; the only interface is the
jump itself (`bootloader_jump()` and the journal that survives it). There is
nothing to conform to and nothing to translate. `jump_journal_logic` is the sole
artefact that acknowledges the boundary, and only because the reset erases RAM.

---

## 4. The context map

Edges run **upstream → downstream**; the pattern is the chosen relationship.

```
                        ┌──────────────────────────────────────────┐
   QMK upstream  ────►  │  shells (wls.c, wls_transport.c,          │
   (Conformist)         │  wls_lifecycle.c, wls_keymap.c,           │
                        │  wls_usb.c, wls_split.c, wls_indicator.c) │
   vendor module ────►  │  — the only place two contexts meet —     │
   (Conformist)         └───────┬───────────────┬──────────────────┘
                                │               │
             ┌──────────────────┴───┐       ┌───┴────────────────────┐
             │  lowpower_logic      │       │  transport_logic       │
             │  (low-power axis)    │       │  (transport + link +   │
             └──────────┬───────────┘       │   device-index model)  │
                        │  E1               └───┬──────────┬─────────┘
                        │                       │ E2       │ E3
             ┌──────────┴───────────┐       ┌───┴──────┐  ┌┴─────────────┐
             │  split_logic         │◄──────┤          │  │indicator_logic│
             │  (split protocol +   │  E4   │          │  └──────┬───────┘
             │   order/release)     │       │          │         │ E5
             └──────────────────────┘       │          │  ┌──────┴───────┐
                                            │          │  │boot_code_logic│
                                            │          │  └──────────────┘
                                            │          │
   ┌──────────────┐  ┌───────────────┐  ┌───┴──────┐  ┌┴──────────────┐
   │rgb_key_logic │  │ keymap_logic  │  │reset_logic│  │sleep_order_   │
   │(keycode axis)│  │ (remap axis)  │  │           │  │logic (battery)│
   └──────────────┘  └───────────────┘  └──────────┘  └───────────────┘
        all four read only the shell; they have no cross-axis edge
```

| Edge | Direction | Pattern | Mediation |
|---|---|---|---|
| **E1** `transport_logic` → `lowpower_logic` | transport supplies the arm context | **Shared facts, no translation** — both speak of pads/codes and the shell supplies them | shell-mediated |
| **E2** `transport_logic` → `indicator_logic` | transport decides the link state; indicator decides how to show it | **Customer/Supplier, with a misplaced render vocabulary** — see §6.2 and its §6.2a: the cue family (`hsm_link_cue_of`, `hsm_chan_cue_of`) is a *render* projection sitting in the transport core, and `hsm_link_cue_of` has no painter at all | shell-mediated |
| **E3** `transport_logic` → `split_logic` | transport decides reachability; split decides whether an order is legal | **the unmanaged edge** — see §6.1: the boolean is computed in `wls_lifecycle.c` and the relation therefore has no whole statement | shell-mediated, **lossy** |
| **E4** `split_logic` → `indicator_logic` | the split link's cues are painted | **Separate Ways via the shell** — `split_logic` never names an LED | shell-mediated |
| **E5** `boot_code_logic` → `indicator_logic` | the boot code claims the frame | **Published Language, one-way and exclusive** — `wls_boot_code_owns_matrix` is read once by the frame pass | direct (via the frame pass) |
| **E6** `lowpower_logic` ↔ `reset_logic` | both respond to the eeprom-clear / bootmagic path | **Separate Ways** — they meet only at the boot reset, where one plan runs | shell-mediated |

**The four keycode/remap/reset/battery cores** (`rgb_key_logic`,
`keymap_logic`, `reset_logic`, `sleep_order_logic`) have **no edge to any other
core**. They read a shell-supplied fact and return a decision. That is their
correct shape and the map's reason for drawing them apart: they are per-axis
rules with no cross-axis content, and the strategic exercise does not apply to
them (a source-backed caution, §7).

---

## 5. What the map shows that the code does not

Four structural facts, none of them visible from any single file:

1. **`transport_logic` is the hub** (§1). Every cross-axis relation in the tree
   passes through it: E1, E2, E3. That concentration is why it accumulated three
   vocabularies (§6.2) — and it is also why 6.2 is the highest-value fix:
   correcting it improves three edges at once.
2. **No edge is unmediated except E5.** The shells are the universal mediator.
   That is the design working as intended (it is how purity survives) and it is
   also why a lost relation is invisible: a shell can compute an input
   *incorrectly* and no core can notice. E3 is the one place that has happened.
3. **The `sends_wake` boolean is the map's only lossy edge** (§6.1), and it is
   the *only* one in the tree — 1 site, not a class. The map makes that size
   legible, which matters: it downgrades a suspected systemic problem to a single
   defect fix.
4. **A vocabulary can survive on its tests alone** (§6.2a). `hsm_link_cue_of` is
   exercised by six assertions and consumed by nobody; the shipped renderer
   paints the same distinction by another route. No single file shows this — the
   core looks used, because tests are not a consumer and `-Wswitch` exhaustiveness
   is not a painter. This is the map's clearest demonstration of its own value:
   the *edges* reveal what the *nodes* cannot.

---

## 6. The boundary defects, as evidence-gated rows

Four were found by the census. Two are gated **open** (evidence demands a fix);
two are gated **held** (evidence permits leaving them, and the decision is
recorded rather than deferred by omission).

Each row is stated so a reviewer can check it: the *evidence*, the *test*, and
what **failing** the test would mean.

### 6.1 OPEN — the `sends_wake` boolean: the one lossy edge (E3)

- **Evidence.** `wls_lifecycle.c:242` computes `bool sends_wake =
  (wireless_get_current_devs() != DEVS_USB);` and passes it to
  `wls_sleep_order_open` (`:243`) and `wls_note_sleep_order_sent` (`:253`).
  `wls_split_can_order_sleep` is `return sends_wake_on_this_transport;`. The
  relation "an order needs a reachable release, unreachable on USB" is therefore
  split between a caller expression and a core predicate, with no file stating it
  whole. This is the ADR's §0.1 worked instance.
- **Test.** Is there any *other* site in the tree that computes an externally-
  sourced boolean as a core predicate's argument? Verified by search: **no** —
  this is the only instance. So the defect is one site, not a class.
- **Fix.** `docs/ADR-cross-axis-contracts.md` Step 2 — state the relation in the
  contract home over the axis vocabulary (`HSM_HOST_*`), and have the shell
  supply the axis value instead of the pre-chewed boolean. That is the ADR's
  **only behaviour-bearing step** and it is required to be behaviour-preserving.
- **Failing this test** (a second such site appearing) would promote the defect
  from "one site" to "a class", and would justify building the monitor core
  before fixing sites.

### 6.2 OPEN — `transport_logic` owns three models (E1, E2, E3)

- **Evidence.** One core serves the transport axis (`HSM_HOST_*`), the module
  link axis (`HSM_LINK_*` plus `hsm_link_watch` timers and `hsm_link_cue_of`),
  and the device-index vocabulary (file-static `HSM_DEVS_*` in
  `transport_logic.c:8-13`, a hand-written mirror of `module.h`'s `DEVS_*`). Its
  header is included by twelve files, more than twice any other core. Its own
  prose admits the mirror: `transport_logic.h:60` ("values 0..6, matching
  `module.h`") and `transport_logic.c:82` (the zero-is-valid-`DEVS_USB` trap).
- **Test.** Does the mirror ever diverge from `module.h`? And does a *render*
  concern (`HSM_LINK_CUE_*`, `hsm_link_cue_of`, `HSM_CHAN_CUE_*`) belong in a
  transport core — answered by measurement in §6.2a.
- **Fix — two parts, in order of evidence strength:**
  1. **The device-index mirror → conform.** `transport_logic.h` *deliberately
     does not include `module.h`* — it takes a bare `uint8_t devs` and only
     documents the values. The mirror lives in the `.c` as file-static defines
     with the same values. Under the Conformist choice (§3.2), the honest form is
     to name the values as the module's (a comment naming `module.h` as the
     source of truth is *already there*), and the guard-able invariant is
     **"the mirror's values equal `module.h`'s"** — a check that currently does
     not exist and that would fail silently if either side moved.
  2. **The cue family (`HSM_LINK_CUE_*`, `hsm_link_cue_of`, `HSM_CHAN_CUE_*`,
     `hsm_chan_cue_of`) → the indicator context.** Decided by **measured usage**,
     not by aesthetics — see §6.2a, which corrects this row's original premise.

**A note on what `transport_logic` legitimately owns here.** The correction
narrows the row: what stays is `hsm_link_state_of_md(uint8_t) → hsm_link_state_t`
(the decode of the module's `MD_STATE_*` byte into *transport* vocabulary) and the
whole `hsm_link_watch` action family. Only the *render projection* moves.

- **Failing this test** (the mirror has already diverged) would make 6.2 the
  highest-priority fix in the tree, ahead of 6.1.

#### 6.2a The cue question, driven by measurement (not by taste)

This row's original premise — "`HSM_LINK_CUE_*` is an indicator concern living in
the transport core" — was **wrong in a way worth recording**, because the error is
instructive. Measurement says:

- **`hsm_link_cue_of` has no consumer anywhere in the tree.** Its only references
  outside `transport_logic` are six assertions in `transport_logic_tests.cpp`.
  The shell never calls it.
- The shell paints REJECT by branching on **state**, not cue:
  `wls_indicator.c:349` reads `hsm_link_state_of_md(...) != HSM_LINK_REJECT`.
- The *sibling* function **does** have a consumer, and consumes it through a
  **raw `switch` over `HSM_CHAN_CUE_*`** (`wls_indicator.c:408`) — i.e. the shell
  uses the channel cue's *cases* but never the three-shape vocabulary the link cue
  defines.

So `HSM_LINK_CUE_*` is not "a concern in the wrong core"; it is **a vocabulary
with no painter**, kept alive by its own unit tests. That is a different and worse
finding.

**The decision rule this row establishes, stated so it applies to any future
case:**

> **A function belongs to the context that owns the decision's *language*, not the
> context that owns its *input*.**

Applied:

| Function | Input's owner | Its output's language | Belongs to |
|---|---|---|---|
| `hsm_link_state_of_md(uint8_t)` | vendor module | `hsm_link_state_t` — **transport** | `transport_logic` ✔ (correct today) |
| `hsm_link_cue_of(hsm_link_state_t)` | transport | `hsm_link_cue_t` — **painting shapes** (steady / blink / no-paint) | `indicator_logic` |
| `hsm_chan_cue_of(uint8_t devs)` | vendor module | `hsm_chan_cue_t` — **which LED is owed**, the arbiter's index domain | `indicator_logic` |

The rule is why "it takes `hsm_link_state_t`, so it belongs with
`hsm_link_state_t`" is the *same error* as putting `wls_split_can_order_sleep` in
`split_logic` because it takes a sleep-order flag: cohesion by input is what
produced the accretion. It is also why cheapness is not evidence — the
`sends_wake` edge (6.1) is one line and the worst defect in the tree — and why
six test assertions are not a consumer.

**Feasibility (so the move cannot be hand-waved).** The cue functions can move
without breaking core purity, exactly as `hsm_link_state_of_md` already avoids
including the vendor header: take the state/devs as a **bare value** and keep the
mapping exhaustive-with-no-`default:` (`-Wswitch`). The test that the boundary was
right is the one already used elsewhere: **after the move, `indicator_logic.h`'s
non-libc include list must still be empty.** If the move forced it to include a
transport header, the boundary was right and this row is wrong.

**The evidence that would reverse it:** a consumer that is *not* a painter — e.g.
the module layer needing to know "is this state shown as steady" — would make the
cue a shared vocabulary crossing three contexts, and the correct pattern would be
Published Language rather than relocation. Check:
`rg 'hsm_link_cue_of' --glob '!*transport_logic*' --glob '!tests/*'` must stay
empty.

#### 6.2b Two sub-questions the row exposes, recorded rather than buried

The boundary defect is *why* nobody noticed either of these. They are named here
so the move does not quietly close over them.

1. **Is `hsm_link_cue_of` dead code to delete rather than move?** The shipped
   renderer never consults it; it branches on state. Moving it would carry a
   no-consumer function into a second core without giving it a painter. The honest
   choice is: **wire it up** (make the renderer paint what the cue says) or
   **delete it**. Moving it unchanged is the one option that solves nothing.
2. **Does the shipped `wls_indicator_link_state()` actually satisfy X-30?** This
   is a *requirement* question, not a boundary one — and the answer is **not
   clearly yes**, which is the substantive finding behind this whole row.

   X-30's measured case *is* the link cue: REJECT must not be reduced to "an
   ordinary non-connection", because the two need **opposite user actions** (fix
   the host's pairing vs wait/re-pair). The requirement is per the doc "settled by
   the cue" — `hsm_link_cue_of` maps `REJECT → NONE` ("terminal until the person
   acts"), deliberately **not** the `DISCONNECTED → BLINK` sight.

   But the *shipped* painter does not paint through the cue. It paints REJECT as
   **three LEDs at once (17/18/19) in dim red** (`0x40,0,0`,
   `wls_indicator.c:355-357`), while the at-rest channel cue paints **whichever
   single channel is live** in neutral dim (`0x10,0x10,0x10`). Those two *are*
   distinguishable — three red vs one grey — so X-30's "opposite actions" test is
   arguably met **by the painter, not by the cue**. The cue's `REJECT → NONE`
   mapping is then *inert documentation*: it describes a difference the renderer
   achieves by another route, and the six unit tests assert a mapping nothing
   observes.

   So the requirement may be satisfied while the artefact that claims to satisfy
   it is unused. That is precisely the "a rule with no home" shape this project
   exists to remove, and it is why sub-question 1 must be answered *before*
   relocating: the move is only correct if the cue is given a painter (making the
   requirement's home real), or if it is deleted and the requirement's home is
   recorded as the painter's own X-30 citation.

### 6.3 OPEN (cheapest) — the `wls_sleep_order_t` collision

- **Evidence.** Two **different types** share one name, both in the sleep-order
  domain. `sleep_order_logic.h:25-27` defines `wls_sleep_order_t` as a struct
  with one field (`uint32_t armed_ms`) — the low-battery arming timer — while
  `split_logic.h:110` defines a *different* `wls_sleep_order_t` (the cross-half
  order executor). They were created on the same day by two extraction slices
  (`7d984b781a`, `701484bf0c`) that never knew about each other. A bare
  `-fsyntax-only` on `wls_indicator.c` **fails** because of it, with
  `sleep_order_logic.h:27:3: error: conflicting types for 'wls_sleep_order_t'`
  (pre-existing) — so a translation unit that merely *includes* both headers
  cannot compile. They were created on the same day by two extraction slices
  (`7d984b781a`, `701484bf0c`) that never knew about each other. A bare
  `-fsyntax-only` on `wls_indicator.c` **fails** because of it (pre-existing).
- **Why this is the strongest signal.** In strategic DDD, "same term, different
  meanings" is *the* context-boundary detector — Evans' requirement that a model
  be "logically consistent throughout, without contradictory or overlapping
  definitions." The collision is not hygiene; it is the boundary line showing
  itself.
- **Fix.** Rename one type. Pure naming, behaviour-preserving, no invariant
  touched. It must happen **before** the ADR's contract home adds a third party
  to that vocabulary. This is the only defect whose fix is free.

### 6.4 HELD — the LED axis is not enclosed (E4)

- **Evidence.** `indicator_logic` owns the LED-index arbiter, but raw matrix
  writes exist outside its owner: `wls_indicator.c` 28, `rgb_record/rgb_record.c`
  7, `epomaker_split65.c` 3, `wls/wls_keymap.c` 3, `indicator_logic.c` 1.
  `rgb_record` is a whole subsystem (the vendor's recorded-effect player) whose
  painters are not in the `wls_led_painter_t` enum; `HS_RGB_INDEX_CAPS`,
  `HS_RGB_INDEX_WIN_LOCK`, `HS_RGB_BLINK_INDEX_WIN/_MAC` have no arbiter home.
- **Test.** Does a painter that writes an LED it does not own produce an
  observable fault? **No observed symptom exists.** The rule is already
  *executable* (a wrong winner fails an `indicator_logic` test); only the
  unrepresentable rung is unreached, and the residue ledger D3/D4 records it as
  stated residue.
- **Decision: held, and stated rather than omitted.** The literature's own
  caution applies directly — "splitting too early … split when you have evidence
  of diverging language or diverging rates of change" — and there is no such
  evidence here. Fixing it is a genuine multi-file refactor (a single
  arbiter-aware choke point plus an extended enum plus a drop-vs-assert policy
  decision), justified only if a symptom appears or if a third cross-axis
  relation needs `rgb_record` in the arbiter. Both are recorded conditions, not
  intuitions.

---

## 7. Why the strategic half applies and the tactical half does not

Recorded so this is not re-derived. Sources are named for each claim.

**The strategic half applies.** Evans' stated problem for large models is
verbatim this tree's: a monolith is "unwieldy and loaded with subtle duplications
and contradictions"; a set of small subsystems "glued together with ad hoc
interfaces … allows consistency problems to arise at every integration point."
Our cores are that set. The three strategic ideas transfer: **Bounded Context**
(where a model is valid), the **language-conflict signal** (the collision in
§6.3, and the mirrors), and the **context map** itself (this document).

**The tactical half does not.** Vernon's "Model True Invariants In Consistency
Boundaries" defines an Aggregate as a **transactional** consistency boundary, and
the test for membership is "must these change in the same transaction?" This
firmware is single-threaded with no transactions, so the question is never asked
and the taxonomy (Aggregate / Entity / Value Object / Repository) has nothing to
attach to. The pure-function core reaches the same goal — true invariants with
one owner — by a **stronger** mechanism here: a pure function cannot be
concurrently corrupted, so it needs no transactional envelope. Treating the
tactical patterns as a checklist would be cargo-culting.

**One caution both sources carry, and this map heeds it:** "there's no
mechanical process that produces the correct design," and DDD "should be applied
only if you are implementing complex [behaviour] with significant business
rules." This map therefore covers the **cross-axis subsystem**, where the
strategic questions are real (E1–E5), and states plainly that the four per-axis
keycode/remap/reset/battery cores have no cross-axis content and are out of
scope. `rgb_key_logic` and `keymap_logic` are correct as they are.

---

## 8. What this map does not do

- **It is not a proposal.** §6's OPEN rows are the only scoped changes; all are
  already named in the determination residue and the ADR, and none is started
  here.
- **It does not claim completeness for cross-axis behaviour.** Stating the edges
  does not prove *no illegal combination is reachable*. That is the residual
  `docs/ADR-cross-axis-contracts.md` §7 keeps explicitly open, and it stays open
  here.
- **It does not replace the composites.** `docs/STATE-MACHINE-*.md` state the
  per-relation ledgers; this map states the *boundaries between* them. Where they
  overlap, the composites are authoritative for a single relation's status and
  this map is authoritative for which context owns it.
- **It does not adjudicate requirements.** §6.2b2 finds that X-30's *artefact*
  (the cue mapping) and X-30's *painter* are two different things, and that the
  requirement looks met by the painter while the artefact that claims to satisfy
  it is unused. Whether X-30 is actually **verified** is a question for
  `docs/UX-REQUIREMENTS.md` and its §0 derivation, not for a boundary map. This
  map only reports that the boundary defect is why the gap was invisible; it does
  not close it.

---

## 9. Provenance

- The models and their languages: the eleven `_logic.h` headers in the tree.
- Accretion confirmed by `git log --diff-filter=A` over each core: every one was
  created 2026-10-08..10-14 by a refactor slice named for the fault it removed
  (`ee92b6d878`, `2174d3d711`, `701484bf0c`, `7d984b781a`, `62def38f74`,
  `0faf870126`, `7c7593bc55`, `85466122cd`). The `<fault-name>_logic` naming is
  the accretion made structural.
- The measured census (core count, inclusion graph, the absence of core-to-core
  and external includes, the `sends_wake` single site): run against the tree at
  `1a49de197d`.
- The cross-axis relation set and the S2 worked instance:
  `docs/ADR-cross-axis-contracts.md`; the composite ledgers
  `docs/STATE-MACHINE-*.md`; `TODO.md` "Determination residue".
- The seam doctrine: `docs/FINDINGS.md` "the transport WAS three partial state
  machines" ("Every symptom we chased lives at a *seam* between these, not in one
  of them") and its "poorly **factored**, not poorly understood".
- The strategic vocabulary: Evans, *Domain-Driven Design*, Part IV (Context,
  Distillation, Large-Scale Structure); Fowler's BoundedContext bliki; Microsoft
  Azure Architecture Center ("Identify microservice boundaries" — a service
  "shouldn't span more than one bounded context"; "Anti-Corruption Layer"
  pattern, whose Conformist/Shared-Kernel/ACL decision table fixes §3's choices);
  Vernon, *Effective Aggregate Design* I–III (the transactional test, and the
  relocation of invariants into consistency boundaries).
