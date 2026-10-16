# ADR — Cross-axis relations get assumed-guarantee contracts and shared monitors

**Status:** proposed (2026-10-16). Design only; nothing in this document is
implemented. It is the scoping artefact for the cross-axis residue named at the
end of `TODO.md` "Determination residue" and in `docs/DETERMINATION.md` §II.4.

**Supersedes nothing.** It is not a replacement for the pure-core pattern; it is
the missing home for the *relations between* cores that §II.1 identifies as the
one layer the pure-core pattern deliberately does not cover.

---

## 0. The problem, stated as the codebase states it

`docs/DETERMINATION.md` §II.1, verbatim in substance: the pure-core/shell split
is *"I.1 done correctly at the level of individual files"*, and it paid — the
cores are decisions with owners and tests. What it does **not** cover is *"the
relations between decisions — which is exactly the layer none of I.1–I.8 assigns
to a single file unless you create one."*

`docs/FINDINGS.md` §"the transport WAS three partial state machines" gives the
empirical form of the same fact, from the predecessor of this design:

> "Every symptom we chased lives at a *seam* between these, not in one of them."

So the codebase already contains the correct diagnosis twice, and already closed
nine cross-axis rows (D1–D9 of `TODO.md` "Determination residue"). This ADR is
about **the quality of those closures and the home they lack**, not about whether
they were worth doing.

### 0.1 The worked instance: S2's closure is brittle, and that is the evidence

The clearest instance. `wls_split_can_order_sleep` (`wls/split_logic.c`) is the
whole safety rule for the cross-half sleep order, and its body is:

```c
return sends_wake_on_this_transport;
```

The *content* of the relation — "an order requires a reachable release, and the
release is unreachable exactly on USB" — is not in this function. It is in the
caller, `wls_lifecycle.c`, in the expression
`sends_wake = (wireless_get_current_devs() != DEVS_USB)`. The core receives a
pre-chewed boolean; the fact that makes the boolean correct is stated nowhere
except a comment above the call site.

Compare the *other* half of the same work, S1: `lpwr_transition` was made
`static` in `lowpower.c`, and the unsafe write now **does not typecheck**. That
is genuinely unrepresentable.

The difference is not effort, it is **shape**:

| | S1 (works) | S2 (brittle) |
|---|---|---|
| Relation spans | one axis (`lpwr_state_t` → `lpwr_state_t`) | two axes (transport → sleep-order legality) |
| Strongest available home | a language restriction (`static`) | a predicate whose *input* is computed elsewhere |
| What is enforced | "the unsafe write is not expressible" | "the caller passes the right boolean" |
| What holds it together | the compiler | a shell expression + a textual guard |

**A per-axis relation can be made unrepresentable; a cross-axis relation cannot**,
because its content is a fact about two axes that no single translation unit
owns. The best a cross-axis relation can reach today is a predicate plus a
caller that computes its argument correctly — and the caller's correctness is
enforced, if at all, by a regex over source text (`bin/guard-invariants`).

That is the brittleness. It is not a mistake in S2; it is the ceiling of the
available paradigm. **The ability to apply the brittle solution is evidence that
the paradigm is missing, not that the row was closed badly.**

---

## 1. The invariant this ADR resolves

> **A cross-axis relation must have a home that names the axes it relates, and
> the assumptions it makes about each, in the axes' own vocabulary.**

Corollary, and the reason the current closures fall short: *a relation stated
over a caller-computed boolean has an unstated assumption.* In S2 the assumption
is "`sends_wake_on_this_transport` means `wireless_get_current_devs() != DEVS_USB`"
and the guarantee is "a permitted order is 0xCC-releasable". The guarantee is
formal; the assumption is informal. That is the defect.

---

## 2. Decision

Adopt **assume-guarantee (A/G) contracts** for cross-axis relations, checked by
**shared runtime monitors** (one pure logic core, driven from both the host test
harness and the firmware), and **build the temporal vocabulary** the monitors are
expressed in.

Three parts, in the order they depend on each other:

1. **A cross-axis contract home** that may include the real axis headers (the
   "no mirror" choice). Each relation is a pair `(A, G)` whose expressions are in
   axis terms.
2. **A pure monitor core** (`monitor_logic.{h,c}`) holding the temporal
   vocabulary and the monitor state, so every relation's logic is host-testable.
3. **Two drivers for that core**: the test harness (existing pattern) and a
   firmware driver, so a violation is observable live as well as in a test.

### 2.1 Why A/G, and not the alternatives

Rejected alternatives, in the order they were considered (see §5 for the full
list and each rejection's warrant):

- **A single product state chart.** Combinatorial: five axes (low-power,
  transport, module link, boot instrument, painter) give ~4×5×5×5×8 ≈ 4000
  nodes, and the axes are *not* independent (many pairs are illegal by
  construction), so the reachable subset is a small, non-obvious part of it. More
  decisively: a product chart puts each cross-axis relation *somewhere in the
  graph*, to be reconstructed by tracing edges. Nothing fails if a relation is
  violated. That is the "rule with no home" shape the determination work exists
  to remove.
- **Mirrored axis enums in a pure cross-axis core** (the previously-considered
  option (a)). Preserves host-testability by duplicating each axis's vocabulary
  and asserting the mirror matches with a guard. Rejected as the *primary* home
  because the project has repeatedly found duplicate vocabularies to be a defect
  class in its own right (`FINDINGS.md` "one rule written three times"; the
  `hsm_link_state_t` mirror is a live example). It also does not fix the actual
  problem: a mirror still cannot say "these two axes cannot be in this
  combination" — it only makes the *values* checkable, which was never the gap.
- **Guarding the fragments instead of removing them** (option (c)): record each
  cross-axis relation as a `bin/guard-invariants` entry asserting its fragments
  still agree. Cheap and honest, but it **enshrines** the brittleness: it makes
  the split checkable rather than making the relation whole. Useful as a
  stopgap; not a home.
- **A hierarchical state chart** as the *structure*. The hierarchy already
  exists in the code (see §2.2), so drawing it adds a document rather than a
  constraint. Hierarchy also does not address the case that matters: two
  orthogonal axes with a relation *between* them, which in a hierarchical chart
  is expressed as a cross-region constraint — i.e. exactly the thing that needs
  a home, drawn rather than built.

### 2.2 What the codebase already has, so the doc does not over-claim

The hierarchy and the per-axis machines are real and stay:

| Hierarchical role | Already exists as |
|---|---|
| Parallel regions | the pure cores: `lpwr_state_t`, `HSM_HOST_*`, `hsm_link_state_t`, `wls_boot_code_t`, `wls_frame_owner_t` / `wls_led_painter_t` |
| Substate nesting | `lpwr_state_t` is already a statechart (NORMAL → PRESLEEP → STOP → WAKEUP), with PRESLEEP the pre-commit phase and STOP the committed one |
| Guarded transitions | `lpwr_presleep_is_allowed_decide`, `lpwr_stop_is_allowed`, `wls_sleep_order_permitted` |
| Entry/exit actions | `lpwr_presleep_cb` / `lpwr_wakeup_cb` (the matrix off/on pair) |
| Local transitions | S1's refusal: returns to NORMAL *without* taking exit actions |

This ADR adds **only** the cross-axis layer. It changes no core.

---

## 3. Design

### 3.1 The contract home

A new header, `wls/axis_contracts.h`, with one translation unit
`wls/axis_contracts.c`. Unlike the pure cores, **it may include the axis
headers** — that is the point of the "no mirror" decision. It contains, per
relation, an `assume` expression and a `guarantee` expression in axis terms.

Worked example — the S2 relation, which today is a caller-computed boolean:

```
relation: cross-half sleep order
  axes:     transport (HSM_HOST_*), sleep order (wls_sleep_order_t)
  assume:   transport_reachable_release(transport) is decidable here, from the
            transport axis itself, not from a caller's boolean
  guarantee: order_permitted ⇒ transport_reachable_release(transport)
```

The critical property: `transport_reachable_release()` is defined **here**, over
`HSM_HOST_*`, so the fact "the release is unreachable on USB" is *in the
contract*, not in a shell expression. `wls_lifecycle.c` then supplies
`wls_transport_current_may_release(transport)` and the contract decides — the
`!= DEVS_USB` comparison moves out of the shell and into the relation's home.

**Cost accepted:** `axis_contracts.c` includes firmware headers, so it is not
host-testable *as a unit*. That is why the relation's *logic* does not live here
— it is expressed in §3.2's pure core, and this file only binds the axes to it.

### 3.2 The monitor core (the temporal vocabulary)

`wls/monitor_logic.{h,c}` — pure, no firmware includes, in the same shape as
`transport_logic` / `lowpower_logic` / `indicator_logic`. It holds:

**The vocabulary**, a small set of relation *kinds* (safety only, as §3.3
argues is sufficient here):

| Kind | Reads as | Literature pattern |
|---|---|---|
| `MON_IMPLIES(trigger, condition)` | whenever `trigger` holds, `condition` must hold now | `Everytime [E] then [C]` |
| `MON_UNTIL(condition, boundary)` | `condition` must hold at least until `boundary` | `[φ] during [I]` |
| `MON_NEVER(a, b)` | `a` and `b` must not hold together | mutual-exclusion |
| `MON_LATCH_IMPLIES(trigger, condition)` | once `trigger` holds, `condition` must hold from then on | `Everytime [E] then [C]`, latching |

Each is a pure function of `(inputs, monitor state)` returning
`{OK | VIOLATED | PENDING}` plus the next state — the same shape as
`wls_blink_tick` and `wls_sleep_order_watch`, so it is already the codebase's
idiom rather than a new one.

**The monitor instances**, one per relation, each a small struct carrying its
state and the relation's axis-typed inputs.

**The verdict surface**: a monitor is *passive and has no outputs*
(the property that makes monitors safe to run live — the literature's argument
is identical to this project's own for `USB_ACTIVE`-as-an-event, D11). It reports
a verdict; it never acts.

### 3.3 Why safety only, and why the vocabulary is still worth building

Every cross-axis relation this codebase has named (D1–D9, plus the two plant
premises) is a **safety** property — "something bad never happens" — not a
liveness one. The one exception is D1 (an order is *eventually* released), which
is already handled differently and deliberately: as a **deadline predicate**
(`wls_sleep_order_outlived_release`) rather than a temporal operator, because
liveness cannot be decided from a finite trace prefix and the codebase's honest
answer there was a timeout, not a monitor.

So the vocabulary is finite and small. The four kinds above cover every relation
listed in §4. Building it as a core — rather than writing each relation as
ad-hoc `static bool` latching in the shell — buys three things:

1. **One home for "how a relation is checked"**, so the relation's meaning is
   not re-derived per site (the defect class the project keeps finding).
2. **Host-testability of the checking**, including the crossing cases, without
   the axis headers.
3. **A place for the latching bit**, which is the part every relation would
   otherwise reinvent and get subtly wrong (the `started_ms == 0` / boot-time
   trap `wls_sleep_order_outstanding` already documents is exactly this class of
   bug).

### 3.4 The two drivers

Per the decision (iii): one logic core, two drivers.

**Driver A — the host test harness.** Existing pattern: a `test.mk` naming
`monitor_logic.c`, a `tests/monitor_logic/` with vectors that drive the axis
inputs directly and assert verdicts. Includes the *negative* vector per relation
(the project's standing requirement that every new check be broken and confirmed
to fail). This is where the temporal semantics get pinned.

**Driver B — the firmware.** A `wls/axis_monitor.c` that gathers the axis facts
(transport, low-power mode, arm mask, link state) each frame/tick, feeds the pure
core, and on `VIOLATED` emits a diagnostic — `dprintf` and, where the diagnostic
seam allows, a bite in the `0xA4` snapshot. **It never acts on a verdict**: a
monitor that changed behaviour would be able to perturb the trace it observes,
which is precisely the livelock shape (D11) the ADR on transport authority
exists to prevent.

Gated behind a build flag so the timing cost is zero in a shipping build, and so
the monitor's presence is a decision, not an accident.

---

## 4. The relation census (the doc's concrete payload)

Before implementation, the relations must be enumerated rather than recalled.
This is the list the design is sized against; each is stated as `(A, G)` in the
implementation, and each gets one monitor instance and one negative vector.

**The relations are the *edges* of `docs/CONTEXT-MAP.md`.** That document states
which context owns each model and which chosen pattern relates each pair; this
census states which *facts* cross those edges. Read together, the map gives R1–R6
their owners and this table gives them their content. Where the two disagree, the
map is authoritative for ownership and this table for the relation itself.

| # | Relation | Axes | Today's home | Fragments today |
|---|---|---|---|---|
| R1 | an order requires a reachable release | transport × sleep-order | `split_logic` predicate + shell boolean | 4 (2 shell exprs, 1 predicate, 1 test) |
| R2 | a teardown requires the line not in use | transport × low-power(line) | `transport_logic` predicates | 2 rules (D5, D9) that are one fact at two levels |
| R3 | an order implies an arm | sleep-order × low-power arming | `lpwr_arm_is_coherent` + guard | 1 predicate + a textual guard over sites |
| R4 | an exclusive claim suppresses the frame | boot instrument × painter | `indicator_logic` arbiter + pass gate | arbiter + gate + guard |
| R5 | the wake mask covers every registered pad | pad attribution × arm mask | `lpwr_excluded_code_is_safe` + guard | predicate + guard + prose table (D6/D7) |
| R6 | the transport decision reads no line state | transport × line | `hsm_transport_input_is_pure` + guard | predicate + 2 guards (D-ADR input half) |

Six relations. That number is the sizing input for §3.2's vocabulary: four kinds
for six relations is right-sized, and confirms the vocabulary is worth a core
rather than four ad-hoc latchings.

**R1 and R2 are the same relation** seen from two sides (order vs teardown, both
"do not act on a line/half whose counterpart is unreachable"). The census is
where that is discovered; the implementation should state it once with two
instantiations.

---

## 5. Rejected alternatives, with warrants

| Alternative | Rejected because |
|---|---|
| One product state chart | Never says *which* combinations are illegal; relations become implicit in edges; nothing fails on violation |
| Hierarchical chart as structure | The hierarchy already exists in code; drawing it is a document, not a constraint; orthogonal-axis relations still need a home |
| Mirrored enums (prior option (a)) | Duplicate vocabularies are a known defect class here; and a mirror makes values checkable, not *combinations* |
| Fragment guards (prior option (c)) | Enshrines the split; makes brittleness checkable rather than removing it |
| All relations as firm pro- argument predicates | Does not fix the real defect: the *assumption* stays unstated, and latching gets reinvented per site |
| Model-check the composition | State explosion is the thing being avoided; retained only as the residual-gap closure for the pairs where a fault lived (§7) |

---

## 6. What this must not become

Three failure modes, named so the implementation can be judged against them:

1. **A second statement of the cores.** If a monitor's relation can be expressed
   *entirely* within one axis, it belongs in that axis's core, not here. The
   contract home is only for relations that genuinely span axes.
2. **An acting monitor.** A monitor that changes behaviour re-introduces the
   perturbation cycle. Verdict only; the action, if any, stays with the owner.
3. **A completeness claim.** A/G composition is *sound but not complete* for
   global reachability: satisfying every contract does not prove no illegal
   combination is reachable. This ADR buys explicit assumptions and modular
   checking; it does not buy the product-space proof, and §7 keeps that gap
   named rather than implied closed.

---

## 7. Residual gap, kept explicit

The literature is unambiguous that pair-wise contract compatibility is sound but
not complete: `docs/DETERMINATION.md`'s own framing (I.5) says the strongest home
is "unrepresentable", and A/G + monitors reach only "executable". Two closures
remain available and are **not** part of this ADR:

- **Refinement obligations** (ModP-style): for the one or two axis pairs where a
  fault actually lived (low-power × transport is the §8 pair; link × arm is D8),
  assert a trace-containment obligation that a *new* illegal combination fails.
  This is the only mechanism that catches a combination nobody thought to write a
  contract for.
- **A witness-trace test per relation**: construct the forbidden combination,
  assert the monitor fires. This is the negative test the project already
  requires, applied at the relation level.

If either is taken up, it is a separate ADR; naming them here keeps this one from
reading as a completeness claim.

---

## 8. Implementation plan

Sequenced so each step is independently verifiable and nothing lands unverified.

**Step 1 — the vocabulary core.** `wls/monitor_logic.{h,c}` with the four kinds,
pure. `tests/monitor_logic/` with vectors for each kind, including the latching
bit and the boot-time-zero trap. No board changes.
*Verify:* new test group green; existing groups unchanged; `-fsyntax-only`.

**Step 2 — the first contract, end to end.** R1 (the S2 relation) expressed in
`wls/axis_contracts.{h,c}` over `HSM_HOST_*`, its logic in `monitor_logic`, its
firmware driver gathering the transport axis, and `wls_lifecycle.c` supplying the
axis value instead of the pre-chewed boolean. This is the *only* behaviour-bearing
step in the whole ADR and must be behaviour-preserving: the `!= DEVS_USB`
comparison moves from the shell into the contract's home, nothing else changes.
*Verify:* `split_logic` and `transport_logic` counts unchanged; a negative vector
that breaks the relation and confirms the monitor fires; the shell no longer
contains the transport comparison; `bin/guard-invariants` extended to keep the
contract home authoritative (the shell must not reintroduce the boolean).

**Step 3 — the remaining five relations**, one commit each, each with its
negative vector and its guard.
*Verify:* per relation as Step 2.

**Step 4 — the firmware driver's diagnostic bite**, and the build flag.
*Verify:* flag-off build is byte-comparable to today (the flash-preflight rule);
flag-on build compiles and the monitor's verdict appears in the diagnostic.

**Step 5 — the census reconciliation.** State R1/R2 as one relation with two
instantiations; update `TODO.md` "Determination residue" and the five composite
docs to point at the contract home instead of scattering fragments.
*Verify:* every fragment listed in §4 is either deleted or is an input to the
contract.

---

## 9. Provenance

- The diagnosis (relations have no home; the pure-core pattern stops at the file
  boundary): `docs/DETERMINATION.md` §II.1, §II.4.
- The empirical form (every symptom is a seam): `docs/FINDINGS.md` "the transport
  WAS three partial state machines".
- The brittle instance: `wls/split_logic.c` (`wls_split_can_order_sleep`) and its
  caller `wls/wls_lifecycle.c`; the contrast case is `lowpower.c`'s `static
  lpwr_transition`.
- The closed rows this generalises: `TODO.md` "Determination residue" D1–D9; the
  composites `docs/STATE-MACHINE-*.md`.
- The paradigm and its vocabulary: assume-guarantee contracts and contract
  compatibility (Benveniste et al.; Ferrante et al., SIES 2014, "Monitor-Based
  Run-Time Contract Verification"); runtime monitors and temporal patterns
  (Torrents 2011; the BCL pattern set); passive/trace-based testing (Hallal et
  al., 2006); compositional reasoning and refinement obligations (ModP, OOPSLA
  2018, assume-guarantee with circular validation).
- The three-rung strength ordering this sits inside: `docs/DETERMINATION.md`
  §II.2; the determination method §II.4 (still a candidate, not process).
