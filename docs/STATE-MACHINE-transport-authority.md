# The transport-authority composite

The relation no single file owns: **which facts the transport decision may read.**
The decision record is `docs/ADR-transport-authority.md`; this document is the
*composite* it implies — the two halves of its invariant, where each lives, and
what is still undetermined. It is artefact 4 of `docs/DETERMINATION.md` §II.3,
derived by the §I.9 symptom-directed slice.

## 0. The invariant, and its two halves

> **`wls_usb_connect` may only be called as the consequence of a decision
> change, and nothing in the line's own state may cause a decision change.**
> (`docs/ADR-transport-authority.md` "The invariant".)

The sentence has two independent halves, and conflating them is what made the
2026-10-13 livelock hard to see:

- **The actuator half** — *the line is driven only on a decision change, from one
  place.* This is a rule about **call sites**.
- **The input half** — *nothing in the line's own state may cause a decision
  change.* This is a rule about the **input alphabet**.

The cycle the ADR records needed **both to be wrong at once**: `USB_ACTIVE` was an
input (input half violated) *and* driving the line restarted the driver that
cleared `USB_ACTIVE` (actuator half was correct in form, but its effect fed the
input). Fixing either one alone breaks the loop; the ADR fixes both, and this
document records where each is determined.

---

## 1. The actuator half (guarded)

`wls_usb_connect()` has **exactly one call site**: `drive_line_for()` in
`wls/wls_transport.c`, reached only from `wls_transport_decide()` on a committed
change. The direction rule is applied there (`hsm_transport_may_drive_line`
allows an unconfirmed decision to PROMOTE only), so no caller can re-derive
`if (changed) wls_usb_connect(...)` and get the direction wrong.

**Home: `bin/guard-invariants` F5** — a call-site count (`wls_usb_connect` call
expressions, comments and the definition excluded) must equal 1. A second call
site fails the guard, not the board.

The actuator is further protected at the *effect*: `wls_usb_connect(false)`
early-returns when `usb_connected_state()` is true (`wls_usb.c`), so even a
mis-directed teardown cannot cut a confirmed host. That gate is a second,
independent statement of the same "a confirmed host is never torn down" rule, at
the actuator rather than at the caller.

---

## 2. The input half (guarded)

The owner's inputs are, exhaustively, three:

| Input | Source | Kind |
|---|---|---|
| switch position | `hs_mode_switch_pos()` | intent |
| persisted BT index | `last_btdev_from_confinfo()` | intent (the switch cannot express BT1..5) |
| host presence | `host_confirmed`, set by `wls_transport_host_event()` | a **fact**, delivered as an **event** |

`hints()` (`wls_transport.c`) folds those three into `hsm_input_rule()`. **None
reads the USB line.** The host fact arrives through
`notify_usb_device_state_change_kb()` → `wls_transport_host_event()`, i.e. from
the USB stack's event, not from a poll of `usb_connected_state()`. That is the
substitution the ADR makes: an *event* is not perturbed by the owner's own
effect, so it cannot recurse.

**Home: `hsm_transport_input_is_pure(bool reads_line_state)`** (`transport_logic`)
— the rule as a pure predicate, with four vectors in `tests/transport_logic`
(53 tests). **And `bin/guard-invariants`** — two checks: the owner reads no
live USB-line symbol (`usb_connected_state`, `USB_ACTIVE`, `USB_DRIVER.state`,
`usbGetDriverState`), and the predicate keeps its definition in the core.

The predicate is deliberately **total and monotone**: *every* line-state read is
impure, and every input in use today is pure. It does not enumerate the allowed
inputs (that would go stale); it names the one thing that may never be one.

---

## 3. Why a call-graph slice misses the input half

A slice taken from the symptom ("the board re-enumerates at ~1 Hz") follows calls
*out* of the decision into `wls_usb_connect` → `restart_usb_driver` → the driver
state. It finds the actuator readily. What it does **not** supply is the edge
back: `USB_ACTIVE` entering `hints()` is a read of **shared mutable state**
(`USB_DRIVER.state`, written by `usb_main.c`), and the dependency is
`dd` over a variable the slice has no reason to follow — the same gap §I.9 names
for the stop/wake slice. The relation is state-carried, not call-carried:
nothing in the *call graph* says the two halves are the same signal. It takes
reading the **alphabet** of the decision as a set, not the body of any function.

---

## 4. Determined / undetermined

| Property | Home | Rung (`II.2`) |
|---|---|---|
| the line is driven from one place, on a change | `bin/guard-invariants` F5 | **unrepresentable** |
| the decision reads no live USB-line state | `hsm_transport_input_is_pure` + guard | **executable** + guard |
| a confirmed host is never torn down at the actuator | `wls_usb_connect(false)`'s early return | prose (in-code, enforced by the same guard family) |
| **the presleep hook's line read** (`wls_lifecycle.c` `:256`) | nothing | **undetermined** |
| whether the USB event queue delivers every transition | nothing (code) | **undetermined** (a plant premise) |

The two undetermined rows are honest and loaded:

- **`wls_lifecycle.c:256`** decides a *line effect* (tear down the driver before sleep) by reading **the line's own state** — `USB_DRIVER.state != USB_ACTIVE`.
  This is the ADR's invariant one level out: not "may the line's state cause a
  *decision* change" but "may the line's state cause a *line effect*". It is a
  different question, it is **not** covered by the input-half rule (which is
  scoped to `wls_transport.c`), and it currently rests on a comment. It is the
  same *shape* the ADR exists to remove, so it is the natural next home — but it
  is also a *deliberate* read (the comment argues tearing down a live host is
  never a low-power action), so the honest remedy is to state *that* rule, not to
  forbid the read.
- **Event-queue completeness.** The ADR's "Costs and risks" names it: moving host
  lifecycle onto the USB event queue means a *missed* event leaves the transport
  uncorrected until the next input changes. No code can assert the queue delivers
  every transition — that is a property of the USB stack on this silicon, so it
  is a **plant premise** and belongs to a batched hardware session, not a test.

The presleep-hook row is **D5** and event-queue completeness **D11** in `TODO.md`
"Determination residue"; the in-code "a confirmed host is never torn down" prose
(§1) is **D9** there.

---

## 5. The three-rung path

Per `docs/DETERMINATION.md` §II.2, ascending:

1. **Prose (done).** `docs/ADR-transport-authority.md` states the invariant and
   the reasoning; `wls_transport.h` and `wls_usb.c` repeat it at the code.
2. **Executable (done, 2026-10-15).** `hsm_transport_input_is_pure()` names the
   allowed alphabet; four vectors pin it; two guards make the alphabet a checked
   set. The predicate is the cheapest home that fails on the *class* rather than
   on the instance.
3. **Unrepresentable (the actuator half is already here).** F5 makes a second
   call site fail at the guard; `wls_usb_connect` is *only* reachable as the
   consequence of a decision, and no caller can drive it another way. For the
   *input* half the rung-3 form would be a type: a decision function whose
   parameter list cannot mention the line — e.g. an opaque `hsm_inputs_t` the
   caller may only construct from intent and events. Not built; the predicate +
   guard is the honest stopping point unless a second line-state input appears.

**Not to be done in this document:** writing the `:256` fix. `docs/DETERMINATION.md`
§II.4 (a candidate, not yet adopted) says *name the property's home before
writing the fix*; this document names the `:256` site and its rule, and leaves
the fix to a separate, aimed change.

---

## 6. Provenance

- The decision and its rejected alternatives: `docs/ADR-transport-authority.md`.
- The actuator rule and its guard: `wls/wls_transport.c` (`drive_line_for`), the
  `bin/guard-invariants` F5 block, `wls/wls_usb.h`.
- The input rule and its vectors (2026-10-15): `transport_logic.{h,c}`
  (`hsm_transport_input_is_pure`), `tests/transport_logic/transport_logic_tests.cpp`
  (53 tests, 4 new), `bin/guard-invariants` (two new checks, negative-tested).
- The undetermined `:256` site: `wls/wls_lifecycle.c` (the presleep hook's
  `USB_DRIVER.state != USB_ACTIVE` read).
- The traversal method: `docs/DETERMINATION.md` §I.9; the rungs §II.2; the
  artefact list §II.3 (this is artefact 4).
