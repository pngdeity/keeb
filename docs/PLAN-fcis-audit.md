# Plan: the FC/IS audit, then software analysis, then hardware

**This is the governing plan for the next phase.** It is recorded here because the
process is long and must survive a context loss. Read it before touching code.

## Why this phase exists

We have flashed a lot with little durable progress toward a typing keyboard, and
most of the recent flashes tested mechanisms that software analysis could have
settled first. The operator's correction, verbatim:

> We need to focus on software analysis; this is correct. How we go about this is
> the part we need to now shift to. As a starting point, we need to revisit the
> research from reputable sources (e.g. Google) on what well-executed
> functional-core, imperative-shell is composed of in the abstract and how to
> express and measure those abstract values in a codebase. Then, for all parts of
> the code where any changes have been made by us, we must rigourous analyze the
> existing code, apply the FC/IS values and principles in full, and verify the
> implementation is reflective of the values. Only after this software refactor
> and transformation is complete should we then return to software analysis to
> debug issues and only after those software analyses have run dry ought we turn
> to flash->observe->reflash test cycles.

## The four-stage sequence (in order; do not skip ahead)

1. **Research** — what FC/IS *is* in the abstract, and how its abstract values are
   expressed and **measured** in a codebase. (DONE — findings distilled below.)
2. **Audit and transform** — for every region we have authored or modified:
   analyze against the values, apply FC/IS in full, verify the implementation
   actually reflects the values rather than claiming them.
3. **Software analysis** — debug the live defects (starting with: can `QK_BOOT` be
   dispatched without a physical key?). No builds, no flashes.
4. **Hardware cycles** — flash → observe → reflash. Only after (3) has run dry,
   and only with a written falsifier per the pre-flight rule.

## Stage 1 findings: the abstract values, and how each is measured

Source discipline: these are the claims that recurred across the sources read
(Gary Bernhardt's *Boundaries*; the Google Testing Blog's FC/IS article; Scott
Wlaschin's *Moving IO to the Edges*; Mark Seemann's impureim sandwich and
dependency rejection; John Ousterhout's *A Philosophy of Software Design*;
Neal Ford/Rebecca Parsons *Building Evolutionary Architectures*; Felipe Balbi's
embedded FC/IS write-up; Michael Feathers' seam model). Each value carries the
measurement that makes it checkable — a value with no measurement is an opinion.

### V1 — Dependency direction
- **Value.** A function in the functional core never calls back into the shell.
  Dependencies point inward: shell → core, never core → shell.
- **Measure.** For each module, can it be compiled and executed with no I/O
  symbol reachable? Concretely: does the translation unit reference any driver,
  HAL, HAL-adjacent, timer, or global-state symbol? `nm`/include-graph check.

### V2 — Explicit inputs, explicit output
- **Value.** A core function takes what it needs as parameters and returns the
  decision as a value. No parameterless functions, no `void` returns, no reading
  of ambient state (globals, `timer_read32()`, `usb_connected_state()`).
- **Measure.** Every public core function has ≥1 parameter and a non-`void`
  return. No core function body dereferences a global or calls a clock.

### V3 — Decision/effect separation
- **Value.** The core answers "what should happen"; the shell does it. The core
  returns a *description* of effects (a decision value, an enum, a command
  struct), never performs them. This is Wlaschin's "dependency rejection" taken
  to its conclusion; Seemann calls the result an impureim sandwich.
- **Measure.** Enumerate every effect kind in the codebase (GPIO write, UART
  write, timer arm, RGB paint, USB connect/disconnect, EEPROM write, reset).
  Each must have exactly one owning shell module, and no core module may name it.

### V4 — The shell holds no policy
- **Value.** Shell functions are "trivial one-liners" with few possible paths —
  ideally cyclomatic complexity 1. A shell that branches on domain conditions has
  stolen policy from the core.
- **Measure.** Cyclomatic complexity of each shell function (target ≈1), and
  count of `if`/`switch`/ternary per shell function. A shell function with more
  than ~3 I/O operations needs its own decomposition.

### V5 — Deep modules (Ousterhout)
- **Value.** Interface much simpler than implementation; information hidden, not
  leaked. A module's *interface* includes side effects, preconditions, and
  ordering expectations — not just signatures.
- **Measure.** Count (a) exported functions/parameters and their coupling per
  module against (b) the functionality hidden behind it. Flag **pass-through
  methods** (little more than a call with the same signature) and **information
  leakage** (one design decision reflected in two modules' interfaces — the
  checkable failure mode: changing one decision forces edits in >1 module).

### V6 — Seam for every non-determinism
- **Value.** Feathers: a seam is a place where behaviour can be substituted
  without editing that place; every seam has an enabling point. In this codebase
  the enabling point is the host build (the pure core compiles for the host).
- **Measure.** Every non-determinism (clock, pin read, EEPROM, USB state, module
  UART) must be a *parameter* of the core, not a call. If a core test needs a
  mock of a driver, the seam is in the wrong place. If the parse/decision cannot
  be exercised by `gcc` on the host, it is not in the core.

### V7 — Parse, don't validate
- **Value.** Bytes are parsed once, at the edge, into a type that cannot be
  wrong; the core operates only on parsed form. Checks are not repeated
  downstream because there is no check left to perform.
- **Measure.** For each boundary (the CH582F UART wire, `0xA4` on the host side,
  EEPROM layout, pin levels): is there exactly one parse function, and does it
  return a *distinct type* from its input? Count repeated range/validity checks
  for the same fact — any repetition proves validation rather than parsing.

### V8 — Illegal states unrepresentable
- **Value.** The state set is an enumeration; the transition function is total
  over `(state, event)`; "nothing happens" is an explicit, named outcome, not a
  fall-through. Firmware sources are consistent that the transition must be
  separable from the action it triggers, and that this purity is what makes
  exhaustive testing possible.
- **Measure.** For each state machine: does every `(state, event)` pair have a
  defined outcome (including explicit ignore)? Are the state and event sets
  `COUNT`-terminated enums? Is the state variable written in exactly one place?

### V9 — The error kernel / crash-only region
- **Value.** The minimal core that must not fail is small, simple, and explicit;
  everything else is allowed to crash and be restarted to a known-good state.
  Error recovery belongs to a supervisor, never to the worker that failed.
  Recovery policy (restart intensity, escalation, circuit breaking) is a shell
  concern, and a crash-only region must be *designed* to restart cleanly.
- **Measure.** Name the region that must not fail; verify it has no dynamic
  allocation, no unbounded loops, and no dependence on a subsystem that can be
  absent. Conversely: any defensive `if` in a worker that silently swallows a
  fault is a *measurement being destroyed* — flag it.

### V10 — Each value carries a fitness function
- **Value.** Ford/Parsons: an architectural fitness function is any mechanism
  giving an objective, repeatable integrity assessment of an architectural
  characteristic; without one the decision degrades silently. Prefer objective
  numbers over subjective judgement. Useful mechanism types: a compile-time
  assert, a host-executed test, an `nm`/symbol check, a static-analysis rule.
- **Measure.** For each of V1–V9, name the automated check that fails when the
  value is violated. Where no check exists yet, that is an audit finding in its
  own right.

### Language of the domain, not of the hardware
A recurring concrete lesson (Balbi): the shell translates bytes ↔ domain values
**once in each direction**. The core speaks the narrowest type that expresses the
idea; the edge is a translation, not a representation choice. All fallibility
lives in that one parse.

### The honest limits (record them; do not pretend otherwise)
- The pattern is **not all-or-nothing**: any logic pulled into the core is logic
  tested cheaply, even if the whole program cannot be a sandwich.
- It is a poor fit where **the logic is mostly I/O** or **performance forces
  interleaving**. On this project the first exception applies to the shell only:
  the shell should be thin, not eliminated.
- **Hardware errata workarounds belong in the shell**, attributed to a specific
  erratum and deletable when the die revision changes. The restored WB32
  `restart_usb_driver` guard is exactly such a workaround and is correctly placed
  — but it must then be the only logic in that shell, and the core must not know
  it exists.
- Referential transparency is what makes a function "fit in your head": a pure
  call can be replaced by its result.

## Stage 2: what gets audited

Every region we have authored or modified. The candidate set (to be confirmed
against `git status`/diff at audit time for both the root repo and the submodule):

- **The transport-owner arc:** `wls/wls_transport.{c,h}`, `wls/transport_logic.{c,h}`,
  `wls/wls_module.{c,h}`, `wls/wls_usb.{c,h}`, `wls/wls_eeprom.{c,h}`,
  `wls/wls_bluetooth.c`, `wls/wls_2p4ghz.c`, `wls/wls_split.c`,
  `wls/wls_lifecycle.c`.
- **The instrument:** `wls/boot_code_logic.{c,h}`, `wls/diag_logic.{c,h}`,
  `wls/wls_indicator.{c,h}`.
- **Board glue:** `wls/wls.c`, `wls/wls.h`, `wls/wls_keymap.c`,
  `wls/wls_battery.c`, `epomaker_split65.c`, `wls/wls.mk`.
- **The restored shell workaround:** `platforms/chibios/boards/GENERIC_WB32_FQ95XX/board/board.c`.
- **Host tooling:** `host/battery_polybar.py` and siblings.
- **Not ours:** the untouched vendor stack and upstream QMK. Do not audit them;
  only audit the **boundary** where our code meets them, which must be clean and
  explicitly named (the operator's "ensure the line is clean" instruction).

## Stage 2 exit criteria

For each audited module, a written verdict against V1–V10 stating: which values
hold, which are violated, the measurement used, and — where a value is violated —
either the fix or a recorded decision to leave it with the reason. Violations
become work items; each fix carries the fitness function that keeps it fixed.

## Stage 3: software analysis (no build, no flash)

Queued questions, in order:

1. **Can `QK_BOOT` be dispatched without a physical key?** Trace every path that
   reaches `process_record_wls` and ask whether a corrupted matrix read, a
   split-transaction payload, an RPC, or any synthesised keycode can produce it.
   A `dfa0` window means `bootloader_jump()` ran, i.e. the DFU magic word was
   written; the only board-reachable writer is `QK_BOOT` at `wls/wls_keymap.c`.
   Since this was written, the board gained a **strong `bootloader_jump()`
   override** (`wls/wls_boot_jump.c:49`) that stamps a cross-reset journal
   *before* the weak implementation resets — so "our `QK_BOOT` ran" is now
   distinguishable from "something else reset us", which is the instrument this
   question needed (`wls/wls_jump_journal.h`).
   If a path exists, it is a firmware bug to fix with no flash. If no path
   exists, the answer is memory corruption or electrical — and *then* a flash
   with the magic-word capture earns its keep.
2. Anything else the audit surfaces as un-analysed.

## Stage 4: preconditions for any further flash

- Stage 3 has run dry.
- The build carries a written **falsifier**, not a prediction of success.
- The pre-flight checklist in `docs/RUNBOOK-flash-and-measure.md` § 0.0 is
  complete and the rationale is stated in writing.

## Standing constraints

- Flashing is human-only: **never** run `./split65.py flash`, `doas`,
  `wb32-dfu-updater_cli`, `sudo`, `su`, `pkexec`.
- Commits require signing, and each states an outcome. **Note (2026-10-14): this
  plan's "nothing is committed yet" phase is over** — the transport arc, the
  instrument, and the UX requirements are committed; see `TODO.md` "Status" for
  the current tips.
- Clean code is the deliverable, not merely the means: "We want a CLEAN codebase
  when we're done."
