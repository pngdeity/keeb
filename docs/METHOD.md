# Method — how this project works

> **Scope.** The disciplined process this project uses to change code and to
> debug faults. It is *generalized from practice*: every rule below was paid for
> by a specific fault this project hit, and each cites the incident that produced
> it. Read this before investigating a fault or starting a change; cite it as the
> authority for *how* we work, exactly as `docs/HARDWARE.md` is cited for *what
> the hardware is*.

This document is deliberately short and durable. The individual lessons are
recorded in `docs/FINDINGS.md` (the discovery narratives), the measured facts in
`docs/HARDWARE.md`, and the long-form working records in `docs/AUDIT.md`,
`docs/AUDIT-fcis.md`, `docs/BOARD-LAYER.md` and `docs/PLAN-fcis-audit.md`. This
file is the *process* those records produced.

## The one sentence

> **Do not build a mechanism on an assumption. Exhaust analysis first; when the
> analysis is dry, make the region observable, take a reading, and let the reading
> pick the mechanism.**

Every rule below is a consequence of that sentence. When a session feels like it
is "reaching for a theory and gathering confirming evidence," it has violated it.
When a session feels like it is about to flash in order to *find out* something
source could have told it, it has violated Part I §0.

---

# Part I — The engineering loop (how the clean code was made)

## 0. The ordering rule — analysis before hardware, and never skipped ahead of

**This is the project's hardest ordering constraint, and it was a correction.**
The plan it came from (`docs/PLAN-fcis-audit.md`) begins with the operator's
verbatim words:

> We have flashed a lot with little durable progress toward a typing keyboard, and
> most of the recent flashes tested mechanisms that software analysis could have
> settled first.
>
> … Only after this software refactor and transformation is complete should we
> then return to software analysis to debug issues and **only after those software
> analyses have run dry ought we turn to flash->observe->reflash test cycles.**

The four stages, **in order; do not skip ahead**:

1. **Research** the standard — what FC/IS *is*, and how its values are *measured*.
2. **Audit and transform** every region we authored or modified, against those
   values, in full — verifying the implementation reflects the values rather than
   claiming them.
3. **Software analysis** — debug the live defects by reading and executing the
   code. **No builds, no flashes.**
4. **Hardware cycles** — flash → observe → reflash. **Only once (3) has run dry**,
   and only with a written falsifier per the pre-flight rule.

**The failure this rule exists to prevent is the expensive one.** A flash that
tests a mechanism source analysis could have settled costs a cycle and, worse,
returns an *ambiguous* reading that then has to be explained — which is exactly
how the "reach for a theory" failure mode (Part II §0) gets its raw material.
**A flash is not a way to find out what the code does. Read the code.**

The right question before any flash is therefore not "what will this show me?" but
"what did analysis leave genuinely undecidable, and what is the falsifier?" If no
such question exists, the flash has no purpose and is not run.

## The engineering loop — six steps, one per defect

The clean code in this tree was **not** produced by writing carefully the first
time. It was produced by a repeatable loop, run once per defect, and the loop is
what made each defect *unrepeatable* rather than merely fixed. The loop has six
steps and they run **in order**. `git log` is the ledger: one commit per step,
each naming the invariant it makes unbreakable.

**Where the clean code came from is not in dispute and must not be re-derived.**
The board layer was rewritten slice by slice (`refactor(board): … (slice N)`),
then audited against an external standard (`docs/PLAN-fcis-audit.md` Stage 2),
then re-audited when the *first* audit's blind spot was found (the "wiring
review", `docs/AUDIT.md`). Both audits are kept. Neither was sufficient alone.

## 1. Research the standard before applying it

**The value must be stated abstractly, and with its measurement, before it is
applied to the code.** "Clean" is not a feeling; it is a set of values each of
which has a check that fails when it is violated.

`docs/PLAN-fcis-audit.md` Stage 1 did this: ten values (V1–V10) distilled from
named sources (Bernhardt, Wlaschin, Seemann, Ousterhout, Feathers, Ford/Parsons,
NASA/JPL *Power of Ten*, Samek, CMU 18-642), each carrying the check that makes
it checkable — a compile-alone test, an `nm` symbol check, a cyclomatic bound, a
sanitizer run. **A value with no measurement is an opinion** and is not admitted.

Recorded lesson: the same review was repeated after the first pass
(`docs/AUDIT.md` "Post-audit FC/IS remediation") and produced a *different*
score because a different source set was used. Research is not one-and-done.

**"The standard" is not only a coding value — it is also the capability set.** A
value says the code must *be* a certain way; a capability says what the artefact
can *do*. Both are research findings, and both may be asserted only with their
evidence. The derivation for capabilities is **four stages — intended (the
vendor's documentation) → actual (our measurements + the vendor source) →
possible (their intersection) → surfaced (the 80% subset)** — and it is stated in
full at `docs/UX-REQUIREMENTS.md` § 0.5. **The vendor's documentation is a
*claim*, not a fact:** an OEM manual is aspirational at worst and approximate at
best, so a documented capability is a hypothesis to test against the hardware,
never a requirement. This is § 1's rule — *a value with no measurement is an
opinion* — applied to capability rather than to code, and it is the rule that
caught the pre-reform `USAGE.md` text and the stale `DEVICE.md` dongle row.

## 2. Audit the existing code against the standard — and write the verdict last

**Depth-first, cores before shells. A verdict is only written after the
measurement named in the plan has been run — not after a read.** The working
record is `docs/AUDIT-fcis.md`; it states the measurement actually used per value
per module, not the impression the code gave.

Two audit shapes, and they see different things — this is why both exist:

- **The state audit** (`docs/AUDIT.md`): per *state*, enumerate the writers.
  It finds N-writers, two-cadence functions, stale-time reads, duplicated
  decoders. It cannot see a *rule* written three times (defect 7) or an effect
  that retriggers itself (defect 8) — neither has two writers of one state.
- **The fitness-function check** (V10): for each value, name the automated check
  that fails when the value is violated. **Where no check exists, that is itself
  an audit finding.**

The blind spot is structural and must be stated: **a proven core does not mean a
proven feature.** A correct decision applied wrongly is still a bug, and the
first audit's framing ("the fix strategy is FC/IS") invited the too-strong
reading that it did. See §4.

## 3. Refactor in slices, one invariant per commit

The board-layer rewrite ran as numbered slices (`slice 1` … `slice 7`), each
extracting one concern behind one interface with its own pure core. Each slice:
**one commit, a stated invariant, the shell reduced to effect-selection, a test
that would fail if the rule regressed.**

A slice is not "move code into a file." It is "name the decision, make it pure,
prove it on the host, leave the shell humble." If the slice cannot state the
invariant it makes unbreakable, it is not a slice — it is a rewrite in disguise.

## 4. Retire the fault *class*, never the instance

**Gating one actuator's call sites is not gating the class.** Four defects found
in one session shared one structure (`FINDINGS.md` "the recurring defect is one
class"):

> An effect is derived from state whose value the effect itself can change — or
> whose validity depends on a lifecycle stage the effect's trigger can precede.

Two shapes, two remedies: **feedback** (break the loop) and **ordering** (a gate
the component that owns the effect enforces, so no caller can reach it early).
The fix belongs where the invariant lives, so every present *and future* caller
is safe.

The class-level work is ordered by **risk × provability** and done in phases
(`docs/AUDIT.md` "The plan — eliminate the fault classes, not the instances"):
Phase A retires "rule stated N times", Phase B retires "effect on time", Phase C
makes the shell humble and the *toolchain* enforce it. Each phase names the
invariant it makes unbreakable.

## 5. Make the toolchain enforce it (the fitness function)

**A fix without a fitness function is a fix that will regress silently.** The
mechanism is chosen per value, and it must cost nothing to run:

- a **compile-time assert** (frame sizes, wire layouts);
- a **host-executed test** in `tests/<name>/` for every rule — not just the pure
  arithmetic; a rule with no test is an audit finding;
- an **`nm`/symbol check** for V1 (dependency direction) — the core compiles
  alone with no undefined symbols;
- a **structural guard** (`bin/guard-invariants`) for shapes that must not
  reappear;
- a **sanitizer run** (`bin/test-sanitized`, ASan+UBSan) — which found a real
  stack-buffer-overflow on first use;
- **warning cleanliness by construction** (`-Wextra`, with `-Werror` already
  active) for our files.

## 6. Close the loop on hardware — with a pre-flight and a falsifier

Source-level proof is not hardware proof. The last step of a fix is a hardware
session that carries a **written falsifier** (not a prediction of success) and
the full pre-flight (**Part II §4**). Only then is the defect closed.

## Acceptance — what "done" means (the three bars)

A fix is **not** done when the symptom disappears; it is done when the rule is
*provable*. Every fix must meet all three, checked before commit
(`docs/AUDIT.md` "Acceptance criteria"):

1. **Single authority.** Exactly one writer per state, or the state is *derived*
   and never mirrored. A second writer is a defect even if it currently agrees —
   it will diverge.
2. **One job per function / one cadence per variable.** Bookkeeping (runs always)
   and effect (runs on a transition) never share a body. A timer has one meaning.
   A change handler does not act on a no-op.
3. **Testable rule.** The decision lives in a pure function (no I/O, no globals,
   no timers) covered by a test; the shell only selects effects from its result.
   **"It works" is not evidence — a test that states *why* it is right is.**

And the shell-side complement (the four-part shell test, `docs/AUDIT.md` "The
wiring review"): a shell function may exist only if it is **humble** (selects
effects, decides nothing — "so simple we don't bother testing it"), **one
authority**, **stated once** (the same idiom at N call sites is one rule with N
copies), and **effect on transition, never on time**.

---

# Part II — The debugging loop (how a fault is run to ground)

> **Read Part I §0 first.** This loop comes *after* software analysis has run dry.
> When a fault appears, the first move is not to instrument or flash — it is to
> read and execute the code (Part I §0 stage 3). The instrument and the flash are
> for what analysis provably cannot settle.

## 0. The failure mode this process exists to prevent

The project has repeated the same failure shape three times, each in a new
domain. Naming it is the point:

> **We reach a state reliably, then lose the process at the point that matters
> and explain it after the fact with a plausible mechanism that was never
> measured.**

- **Boot-code arc.** The instrument played `(5 amber, 5 white)` where the core
  emitted `(7, 5)`. The explanation reached for first — frame starvation, an
  amber undercount, a hardware quirk — was wrong; the cause was a *bound in the
  shell*, found only by executing the pure core. (`FINDINGS.md` "the shell held
  policy".)
- **BT session (2026-10-14).** The board went dark on Bluetooth and the
  mechanism was reached for from a *reconstructed* sequence — `md state 3` →
  `HSM_LINK_ACT_SLEEP`, or the split `ORDER_SLEEP` path — before the observation
  existed. The board was dark, the LED was off, and the only evidence was a
  level-triggered report with no timing.

The tell is always the same: **a mechanism proposed before an observation that
could falsify it.** The remedy is not "be more careful"; it is the instrumental
step below.

## 1. Make the region observable before you touch it (the instrument rule)

When the fault lives where nothing can see it — before a console, before USB, or
behind a rail the fault itself cuts — **the instrument comes first, and it must
be trustworthy before it is used.** An instrument that races other output, whose
timing is not what its comment claims, or that plays once from an arbitrary
phase is not an instrument; it is a second source of ambiguity.

A trustworthy instrument is (full statement in `docs/INDICATORS.md` §5):

1. **Exclusive** — the only thing painting while it plays.
2. **Uniform in timing** — the count carries the value, not the width.
3. **Delimited and repeating** — a distinguishable frame boundary and a loop, so
   a missed start is recoverable.
4. **Started where the frame is live** — not before its paint path exists.

**Prefer the chip's own latch to an instrument that infers.** A counter is a
proxy for a fact the silicon already records; the proxy needs a ritual, the latch
needs one read. (`FINDINGS.md` "a reset loop is proved by the chip's own latch".)

**The channel must be independent of the fault.** A reset destroys any channel
that needs the running application; the LED rail and the reset-cause latch both
survive it. If the fault can cut the channel you are reading on, you are reading
the wrong channel.

**A diagnostic that is unreachable exactly when it is needed is not a
diagnostic.** The `0xA4` reply needs the USB line the self-detach fault kills;
that is why the retained boot report and the host-less LED blink exist
(`docs/AUDIT.md` measure D). Give the reading a second exporter.

## 2. Measurement before mechanism

- **For any behavior question, the readback is the first move, not the last.**
  The `--info` snapshot, the raw bytes, the LED code — take the reading before
  proposing any explanation.
- **A constant is not a measurement.** `battery: 100%` on USB is the module's
  compile-time init constant, not a reading; `usb_vbus_state()` with no
  `USB_VBUS_PIN` is constant `true`, not a signal. Verify against the ELF, and
  against whether the path that populates the field can even run.
- **Never assert a measured hardware constant from memory, and never act on an
  unverified second-hand constant.** Cite `docs/HARDWARE.md`.
- **Do not draw an A/B conclusion from a single boot** of an intermittent fault.

## 3. Locate the layer before choosing the remedy

A reading tells you *what* happened; the remedy depends on *which layer* it
happened in. Before fixing, answer: is this our code, an upstream contract, the
vendor stack, or the hardware module's own firmware (Layer 0)? A fix applied at
the wrong layer is a re-derivation of the fault. The Layer boundary is stated in
`docs/HARDWARE.md` "The Layer boundary".

**When a reading contradicts the code, execute the core.** If the pure function
is right and the reading is wrong, the explanation is a shell defect or an
instrument defect — not a hardware quirk. (`FINDINGS.md` "the shell held
policy" §3.)

## 4. Pre-flight a hardware session (state it before you flash)

**"Ready to flash" means airworthy, not "it compiled."** A hardware session must
not begin until every assumption is stated and every effect predicted. The
canonical eight-item checklist with the artefact to leave in `docs/` is
`docs/RUNBOOK-flash-and-measure.md` §0.0. It is legitimate to skip only when
nothing about the board's behavior is being asserted.

The review questions that caught three live livelocks *before* hardware (the
single most productive question in this project's history is the first):

1. **Does this effect feed back into its own trigger?** A trigger must not
   depend on a signal the triggered effect modifies.
2. **Does every signal have a real value here?** Not a constant, not undefined.
3. **Which code is even compiled?** A `#if` can delete the path you rely on.
4. **Is that assumption measured, or inherited?**

A **state-persisting** path additionally requires the **non-flashing recovery**
to be established first (EEPROM write, `confinfo`, a persisted host) — the
worked example is defect 4.

## 5. Keep policy in the core, not the shell

A bound, a clock origin, a threshold, or an ordering that the shell supplies is
*policy*; keep it where a pure test can reach it. The test: **if the behavior is
only reachable by flashing, a policy input is in the shell.** A comment that
asserts a guarantee no test enforces is the same defect — a claim where a proof
belongs. Full principle set in `docs/BOARD-LAYER.md`.

## 6. The decision/effect split (what a fixed fault looks like here)

For every area touched, answer in the audit's form: **what is the decision (a
pure function, tested), and what is the effect (may be imperative)?** A defect
class cannot surface where the decision is pure and tested and the shell only
selects effects. This is where the debugging loop **hands back to Part I** — a
fault run to ground becomes a slice, a class fix, and a fitness function.

---

# Checklist — the process, condensed

**Before changing code (Part I):**

- [ ] **Exhaust analysis before hardware** (§I.0) — the four stages in order:
      research, audit/transform, software analysis, and only then a flash. Read
      the code; do not flash to find out what it does.
- [ ] **Is the standard stated with its measurement?** (§I.1) A value with no
      check is an opinion.
- [ ] **Audit against it and write the verdict last** (§I.2) — after the
      measurement, not after the read. State which audit shape you are running
      and what it cannot see.
- [ ] **Slice it** (§I.3) — one invariant per commit; the shell left humble.
- [ ] **Retire the class, not the instance** (§I.4) — fix where the invariant
      lives, so no future caller can re-derive the fault.
- [ ] **Ship the fitness function** (§I.5) — the test/assert/guard that keeps it
      fixed. No fitness function, no fix.
- [ ] **Meet the three bars** (Acceptance) — single authority, one cadence,
      testable rule. "It works" is not evidence.

**Before proposing a mechanism (Part II):**

- [ ] **Has analysis run dry?** (§I.0) If source reading or executing the pure
      core can settle it, do that — do not instrument and do not flash.
- [ ] **Observe first.** Take the reading. If the region is unobservable, build
      the instrument first (§II.1) and verify it is trustworthy.
- [ ] **State the layer** (§II.3) — ours, upstream, vendor, or module firmware.
- [ ] **Separate measurement from constant** (§II.2) — is the field's populating
      path even reachable?
- [ ] **Ask the four review questions** (§II.4), starting with "does this feed
      back into its own trigger?"
- [ ] **Name the falsifier** — "if X, the hypothesis was wrong and the next move
      is Y" — so a surprise changes the model instead of prompting a guess.
- [ ] **Only then** name the mechanism and the remedy, at the layer the class
      lives in (§II.4), as a pure decision with a test (§II.5, §II.6).
