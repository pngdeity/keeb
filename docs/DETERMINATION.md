# Determination: giving the system's relations a home

This document exists because one fault (`TODO.md` §8, the 30 s dark board) cost a
whole session of wrong readings, and the diagnosis of *why* is not about the fault.
It is about a property of the codebase's shape: the relations that make the fault
visible were **underdetermined** — entailed by the parts jointly, stated by none of
them, and checked by nothing.

It is written in two halves. **Part I** synthesizes what reputable, established
sources say about the problem and its remedies, with citations, and says *why* each
is a principle. **Part II** applies that synthesis to this codebase as it stands.

Read it beside `docs/METHOD.md` (how we work) and `docs/FINDINGS.md` (the defect
class). This document is the **architecture** half: what a system's shape owes its
future reader.

---

## Part I — The principles, their reasons, and their sources

### I.0 The one-sentence diagnosis

A codebase is a **specification** of a system, and specifications differ in what
they *determine*. When a rule is entailed by the whole but stated by no part, and
nothing fails when you break it, the rule is **underdetermined** — and the only way
to recover it is to reconstruct it in your head from pieces that were never designed
to imply it.

Three nearby failures are easily confused; distinguish them:

| | What is missing | Why it happens | Fixed by |
| --- | --- | --- | --- |
| **Undocumented** | the fact exists in one place; prose omits it | a writing gap | writing prose |
| **Under-specified** | the fact is ambiguous where stated | a requirements gap | deciding the requirement |
| **Underdetermined** | the fact exists *nowhere*; parts jointly imply it | a **structure** gap | giving it a home |

Only the third cannot be fixed by writing more prose about what is there — there is
nothing to describe. You must first decide *what the rule is*, then create a place
for it. That is the whole subject.

**The decisive test for underdetermination:** *if I broke this rule, would any
artefact fail?* A test that fails, a type that refuses to compile, an assertion that
trips — each means the rule is *determined* (executably or structurally). A document
someone reads is weak determination. **Nothing failing, and no document, means
underdetermined**, however many files mention the pieces. The trap is that this is
*invisible from inside*: every file reads well, so diligence feels rewarded while it
is not.

### I.1 Relations are what a shape owes — information hiding is about decisions

**Principle.** Decompose by the *decisions* you are hiding, not by the steps of a
flowchart. A module should own a design decision and hide it from every other
module. A decision that has no owner becomes an emergent, global property — and
emergent properties are exactly the ones no local reading can verify.

**Source.** David L. Parnas, *On the Criteria To Be Used in Decomposing Systems into
Modules*, Communications of the ACM 15(12):1053–1058, December 1972
(doi:10.1145/361598.361623). Parnas's own words: *"it is almost always incorrect to
begin the decomposition of a system into modules on the basis of a flowchart. We
propose instead that one begins with a list of difficult design decisions or design
decisions which are likely to change. Each module is then designed to hide such a
decision from the others."* The paper's running example (the KWIC index) shows the
flowchart decomposition producing a system that *"will only be comprehensible as a
whole"*, against the information-hiding decomposition which is comprehensible module
by module.

**Why it is a principle.** Parnas's criterion is, restated, *"give the decision a
home."* Underdetermination is the failure mode where a decision has no home, so the
property it governs is entailed by the composition and owned by nobody. The
criterion tells you *where a missing home should have gone* — at the module that
owns the decision — which is more actionable than "coupling is too high".

### I.2 A specification is obligations and guarantees, and it must be checkable

**Principle.** Every routine call is a contract between a client and a supplier.
State the supplier's **precondition** (what the caller must guarantee) and
**postcondition** (what the supplier guarantees in return), and the class
**invariant** (what is true of every observable instance state). Attach the contract
to the code it describes so that it is checkable at runtime and cannot drift from a
separate document.

**Source.** Bertrand Meyer, *Design by Contract* — the theory is in *Object-Oriented
Software Construction*, 2nd ed. (Prentice Hall, 1997), ch. 11, *Design by Contract:
building reliable software*; the practical chapter is *Applying "Design by
Contract"*, IEEE Computer, October 1992. Meyer names the core move: *"if we entertain
any hope of producing correct and robust software, the very least we can do is to
make explicit the obligations and guarantees on any call. The mechanisms for
expressing such conditions are called assertions."* The class invariant is defined as
*"a property that must be satisfied by all instances of the class, transcending
particular routines"* — true after construction and preserved by every exported
routine.

**Why it is a principle.** Two reasons, both load-bearing here. First, DbC puts the
specification *in the software document itself*, which — Meyer's own words —
*"makes it checkable at runtime and eliminates the document synchronization
problem"*. A separate design doc is a second specification that can drift; a contract
attached to the routine is the same specification the code is executed against.
Second, the invariant is defined as **consistency of observable states**, and the
"observable states" are exactly the states reachable by exported operations — which
is the state-machine view this codebase already uses (see `docs/BOARD-LAYER.md`'s
pure core). The invariant is the missing artefact for a state machine whose safety
rule spans states.

### I.3 Invariants are *derived*, not asserted — the logic underneath

**Principle.** Program properties are proved with respect to an invariant: an
assertion that holds on entry (initiation), is preserved by the body (consecution),
and is strong enough to imply the goal on exit (safety). The rule is a *derivation*
of the property, not a restatement of the code.

**Source.** C. A. R. Hoare, *An Axiomatic Basis for Computer Programming*,
Communications of the ACM 12(10):576–580, October 1969
(doi:10.1145/363235.363259), building on R. W. Floyd, *Assigning Meanings to
Programs* (1967). Hoare's `P {Q} R` means *"if the assertion P is true before
initiation of a program Q, then the assertion R will be true on its completion."*
The rule of iteration (his D3) is the induction step: *if `P ∧ B {S} P` then
`P {while B do S} ¬B ∧ P`*.

**Why it is a principle.** It tells you what an invariant *is for*: it is the
strongest thing you can assume on entry and must re-establish on exit. Hoare's own
framing is that *"all the properties of a program and all the consequences of
executing it in any given environment can, in principle, be found out from the text
of the program itself by means of purely deductive reasoning"* — which is precisely
what the underdetermined case defeats: the deduction needs the invariant as a
premise, and if the invariant is absent, the deduction has no starting point, so the
reader is left to *hypothesise* and be refuted by execution.

### I.4 System behaviour is a state machine; safety and liveness are the two halves

**Principle.** Specify a system as **init ∧ □[next]**, plus liveness. **Safety** is
"nothing bad ever happens" — violated by a finite prefix, so it can be checked by
looking at reachable states. **Liveness** is "something good eventually happens" —
violated only by a whole behaviour. Safety properties catch far more errors; the
guidance from practice is to specify them first.

**Source.** Leslie Lamport, *Specifying Systems: The TLA+ Language and Tools for
Hardware and Software Engineers* (Addison-Wesley, 2002), free from the author;
"Part I ... explains how to specify the class of properties known as safety
properties. These properties ... are all that most engineers need to know about."
Lamport on the empirical priority: *"Experience indicates that specifying safety
properties catches many more errors than specifying liveness properties."* The
safety/liveness dichotomy is standard (Alpern & Schneider, *Defining Liveness*,
1985).

**Why it is a principle.** It gives the *shape* of the missing artefact. The §8 rule
("an effect must not be applied unless its undo is reachable") is a **safety
property**: a bad thing that must never happen, detectable in a finite prefix of
execution — reach PRESLEEP and you have already violated it. It therefore does not
need a model checker to be *stated*, and once stated it becomes checkable by
assertion at the exact state where it can be violated. It also explains why the
hardware was a poor oracle: every flash cycle was a one-bit liveness experiment
("does it ever come back?"), when the property that mattered was a safety property
that could have been stated and checked locally.

**On Lamport's motivation, which is directly on point.** He abandoned "specify the
system as a list of temporal properties" because — his account — *"even if the
individual axioms are comprehensible, what you get by combining a whole bunch of
axioms is totally incomprehensible."* His conclusion: *"the only way to describe the
safety properties of nontrivial systems, precisely and formally, was basically using
some kind of state machines."* The lesson transfers to a set of "locally sensible"
functions: a set of readable functions whose composition nobody states is the same
incomprehensibility in imperative dress.

### I.5 Make the violation impossible to represent

**Principle.** Where you can, choose a representation in which the illegal state
cannot be expressed at all. Then you never write code to handle it and it cannot
slip through. Establish the constraint at the point of *modelling*, not by guarding
at each use.

**Source.** Yaron Minsky (Jane Street), *Effective ML*, 2010 Harvard guest lecture —
the maxim *"make illegal states unrepresentable"*. His framing, from the Lambda the
Ultimate discussion (2007): *"One of our programming maxims at Jane Street is to
'make illegal states unrepresentable'. Algebraic datatypes, parametric polymorphism
and abstraction can be used to great effect in this regard ... one of the things
that is constantly on one's mind is how to pass off as much of the proof burden as
possible to the compiler."* Scott Wlaschin develops the craft (product-vs-sum types,
*Designing with Types*); the general taxonomy of techniques — newtype, typestate,
constructors, parsing-instead-of-validating — is summarized in *Effective Rust* and
in Mahoney, *Applying "Make Invalid States Unrepresentable"* (2020).

**Why it is a principle.** It is the strongest of the three remedies because it
**dissolves** the invariant rather than documenting or checking it: if the unsafe
order cannot be written, there is no rule to state and nothing to remember. It is
also why the remedy for §8 is a *restructure*, not a comment — moving the matrix
save/restore inside the stop/wake pair removes the leak by construction. (Minsky's
"illegal states" is not only mutable state — his canonical example is an immutable
`connection_state` — so the maxim covers protocol and ordering states, not just data
representations; this matters because the §8 violation is an *ordering* state.)

### I.6 Protocol and ordering states can be typed — typestate and session types

**Principle.** When a correct program is a *sequence* of operations, encode the
protocol state in the program's types so that an out-of-order operation is a type
error rather than a runtime bug. The discipline: each state offers a set of
operations, each operation specifies its successor state, and using an operation
outside its state does not compile.

**Source.** For objects: typestate (Strom & Yemini, 1986) implemented for Java in
**Mungo/StMungo** (Dimovski, Kouzapas et al., *Typechecking protocols with Mungo and
StMungo*, PPDP 2016, doi:10.1145/2967973.2968595) — *"a typestate defines an object
protocol, in the form of a state machine. Each state offers a set of methods ... each
method specifies a transition to a successor state."* For concurrent systems:
multiparty **session types** / Scribble (Honda, Yoshida, Carbone), where
*"once each endpoint implementation is known to conform to its local protocol, the
various implementations can be composed into a system free of communication
errors"* — the exact property whose absence made the split-link fault unreadable from
either half's source alone. For C-adjacent practice: the Rust typestate pattern and
embedded HAL APIs, where a device cannot be used before initialization *because the
type says so* (Chombo-Discharge, embedded-hal).

**Why it is a principle.** Session types are the formal statement that **"two halves,
one wire, no single contract" is a solvable shape** — the protocol *is* the type, and
each endpoint is checked against its projection independently, yet the composition is
provably free of mismatch. This is the strongest known answer to the split-link half
of §8.

### I.7 Assertions are the cheap, universal rung — and their limits

**Principle.** An assertion is code that checks the program against a stated
expectation while it runs, and it is the smallest possible specification. Use it
especially for things that "cannot happen" — an assertion that can never fire is a
statement of the invariant, and one that *does* fire localises the fault to a line.
But be honest about the limits: assertions check what they are written to check, not
the composite relations nobody wrote down.

**Source.** Steve McConnell, *Code Complete*, 2nd ed. (Microsoft Press, 2004), ch. 8,
*Assertions*: *"An assertion is code that's used during development ... that allows a
program to check itself as it runs. When an assertion is true, that means everything
is operating as expected. When it's false, that means it has detected an unexpected
error in the code."* Industrial tooling: Microsoft Research **Code Contracts**
(Fähndrich, Barnett, Leino, Logozzo, *Practical verification for the working
programmer with CodeContracts and Abstract Interpretation*, 2011) — preconditions,
postconditions and object invariants as checked documentation, with *"each contract
acts as an oracle, giving a test run a pass/fail indication"*, and a static checker
(Clousot) that verifies them without running. For hardware/embedded, SystemVerilog
Assertions encode temporal relations but deliberately **not** as recreations of the
implementation's own state machine: *"assertions should not simply recreate rules
forced on signals by a particular implementation ... coding assertions relating
events occurring at a module's interface to the behavior of a state machine can be
very powerful"* (Bhattacharya, *Introduction to SVA Assertions for Design
Engineers*, 2011).

**Why it is a principle.** It is the rung the pure core can always afford, and it
converts a prose invariant into a fact the build or the test run enforces. The
caution is the useful half: an assertion written by reconstructing the
implementation's own state machine verifies nothing, which is how assertion suites
come to pass while the composite rule is still violated. (Cf. I.0's test: if the
assertion mirrors the code, breaking either changes both, and neither fails.)

### I.8 The engineering case: a specification is not ceremony

**Principle.** A model/specification is cheaper than a defect. The value is not
proof for its own sake; it is that the *act* of stating the system surfaces the
relations you had not decided, and the *artefact* then answers counterfactuals
without execution.

**Source.** Lamport, *Who Builds a House Without Drawing Blueprints?*,
Communications of the ACM 58(4):38–41, April 2015 (doi:10.1145/2736348) — the title is
rhetorical and the answer is "most of us, most of the time". Lamport: *"Writing a
specification takes time, but it takes less time than debugging a system that was
built on a flawed design."* And: *"If we do not start with a specification, every
line of code we write is a patch."* The industrial evidence: Newcombe, Rath, Zhang,
Munteanu, Brooker, Deardeuff, *How Amazon Web Services Uses Formal Methods*,
Communications of the ACM 58(4):66–73, April 2015 — *"In each [of S3, DynamoDB and
others], TLA+ has added significant value, either finding subtle bugs we are sure we
would not have found by other means, or giving us enough understanding and confidence
to make aggressive performance optimizations without sacrificing correctness."* One
DynamoDB bug's shortest error trace was **35 high-level steps** — unreachable by
conventional testing. AWS also found the concrete follow-on: a specification that is
never connected to the implementation loses most of its value, hence runtime
observers that check production traces against the specification (PObserve).

**Why it is a principle.** It answers the objection that this is ceremony. The
35-step trace is the quantitative version of the argument: the *reachable* state space
of a composed system is far larger than any single reader's head, so the relations
that matter are precisely the ones local reading cannot cover — which is why "writing
a specification is cheaper than debugging a flawed design" is an engineering claim,
not an aesthetic one. It also supplies the second half of the discipline: a
specification that is not tied back to the running system is a second document that
drifts. **The artefact must be executable, or attached to what is executed.**

### I.9 How to traverse an underdetermined codebase — and a citation this document got wrong

I.0–I.8 say what determination *is* and how to create it. They do not say **in what
order to work through an existing codebase**, which is the practical question once you
decide to determine a system rather than design one from scratch. This section answers
it, and records a failed attribution made while researching it — kept deliberately, per
this repo's rule that a refuted reading is filed rather than deleted, because the
failure is as instructive as the answer.

**The naive answer, and why it is wrong.** The obvious traversal is the *directory
layout* — the two-level pure-core/shell split the tree already has. That is a
decomposition by flowchart, which is the exact error I.1 (Parnas) warns against; a
directory tree is a flowchart drawn on a filesystem. Worse, it is **circular as a
diagnostic**: a map derived from the artefact cannot reveal a *systematic* omission in
the artefact. If the tree systematically leaves a class of relations unstated, a map
built from the tree inherits the omission silently. So the traversal order cannot come
from the structure being audited.

**What the literature supports.** Three bodies of work, in ascending usefulness:

1. **Program slicing** — Weiser, *Program Slicing*, ICSE 1981, pp. 439–449 (previously
   presented at the 5th ICSE, San Diego; journal version IEEE TSE 10(4):352–357, July
   1984). Definition, verbatim: *"a slicing criterion of a program P is a tuple (i, V),
   where i is a statement in P and V is a subset of the variables in P"*; a slice is
   *"any executable program with the following two properties: (1) S can be obtained
   from P by deleting zero or more statements from P; (2) Whenever P halts on an input I
   with state trajectory T, then S also halts on input I with state trajectory T', and
   PROJ(T) = PROJ(T')"*. The mechanism is **data-flow and control-flow reachability**:
   `R⁰(n)` is defined over `DEF(n)`/`REF(n)` per statement and propagates backward, and
   branch statements are added via **control dependence** on the nearest *inverse
   dominator* (`INFL(b)` — Weiser cites Denning & Denning for that construct).
   Interprocedural slicing is two-phase (`UP`/`DOWN` over callers/callees). Honest
   limits, both stated by Weiser: **statement-minimal slices are uncomputable** (finding
   one would decide the halting problem), so slices are *conservative* approximations,
   and the interprocedural method is *"interprocedurally imprecise because it does not
   model calling contexts."* Weiser's empirical claim is the one that matters here and
   it is a *debugging* claim: *"debugging programmers, working backwards from the
   variable and statement of a bug's appearance, use that variable and statement as a
   slicing criterion to construct mentally the corresponding program slice."*
2. **Slicing over a dependence graph built from source** — *Slicing for architectural
   analysis*, Science of Computer Programming, 2010 (doi:10.1016/j.scico.2010.02.002).
   Builds an **MSDG** (Managed System Dependence Graph) directly from source with typed
   edges — `cf` (control flow), `ct` (control), `mc` (method call), `dd` (data) — then
   **backward-slices** from nodes labelled as **interaction/communication primitives**,
   pruning everything irrelevant to the coordination layer. This is the usable form for
   a tree with no architectural specification: the labels stand in for the missing ADL
   ports, and the graph comes from code.
3. **Feature location** — Dit, Revelle, Gethers, Poshyvanyk, *Feature location in source
   code: a taxonomy and survey*, Journal of Software: Evolution and Process 25(1):53–95,
   2013 (first published online 28 November 2011; doi:10.1002/smr.567). Verified: a
   systematic survey of **89 articles from 25 venues** (Nov 1992 – Feb 2011), a
   nine-dimension taxonomy. Definition, verbatim: *"feature location is the activity of
   identifying an initial location in the source code that implements functionality in a
   software system."* The survey's own distinction is the one to carry: *"Feature
   location is one of the most important and common activities performed by programmers
   during software maintenance ... the full extent of the change is then handled by
   impact analysis, which starts with the source code identified by feature location."*
   **Why this is the top of the three:** it is a survey of *how to find the slice's
   starting point*, and it is about **features/concerns**, which cross-cut structure —
   the unit of traversal is therefore a thread, not a directory. It is also the source
   that says plainly that this is a *search* activity, which is what a long debug is.

**A citation this document got wrong (recorded, not deleted).** Working from recall, I
attributed "architectural slicing" to **Wei & Garlan** and proposed it as the best
traversal. Checking the sources falsified this twice over:

- **The attribution is wrong.** Architectural slicing is **Jianjun Zhao's** —
  *Applying slicing technique to software architectures*, ICECCS 1998
  (doi:10.1109/iceccs.1998.706659), and *A slicing-based approach to extracting reusable
  software architectures*, CSMR 2000/2002 (doi:10.1109/csmr.2000.827330). Garlan appears
  in those bibliographies via Allen & Garlan's Wright/Acme work; I attached the concept
  to the name nearest it in recall. This is precisely the failure mode I.3 names — a
  plausible reading standing in for a checked one.
- **The concept is circular for this purpose.** Zhao's architectural slicing *"directly
  operates on the architectural specification of a software system"* — an ADL
  specification `P = (Cm; Cn; cg)` (components, connectors, configuration), sliced over
  an Architecture Information Flow Graph. It contrasts itself explicitly with *"the
  source code of a program."* So it **presupposes the artefact we do not have.** Slicing
  an architecture requires an architecture; citing it to traverse an underdetermined
  codebase is asking the technique to supply the determination it consumes. The
  direction of dependencies is the other way: the slice is a *product* of determination,
  not a route to it.

**The corrected method, as it applies here.** Traverse by **backward slice, threaded by
state**, ordered by **symptom**:

1. The **slicing criterion is the symptom**, not a function: the dark panel (the
   observable end-state "`rgb_matrix_enable_noeeprom()` was not reached") and the silent
   slave (the `USER_SYNC_MMS` wake that was never sent). Both are Weiser's `<i, V>` shape
   with `V` being an *observable*, so the criterion is a fact the hardware can state.
2. Build the dependence relation from what the tree already supports: `bin/compiledb`
   produces the compile database, so `mc` (calls) is available at no cost.
3. **The two relations the off-the-shelf technique does not supply, and which must be
   added by hand — this is the honest gap, and it is not cited because it is ours:**
   - `dd` over the *shared mutable state* the machines communicate through —
     `ordered_sleep`, `lpwr_state`, `manual_timeout`, `boot_code_active`. These are
     file-static, so a call-graph slice does not reach them; the §8 slice is *invisible*
     to a call-only traversal.
   - `ct` over **state-transition guards** (`lpwr_stop_is_allowed`,
     `lpwr_presleep_is_allowed_decide`) — a guard that *refuses* an edge the slice
     assumed taken. This is the relation that made the §8 fault unreachable by reading:
     the edge existed in the graph, was named in the code, and was declined at runtime.
   Weiser's `R⁰` handles `dd` only for *variables at a statement*, not for state that
   outlives the statement — the same class of gap that makes the fault invisible.
4. Where a slice crosses to the other half of a split, the criterion must be stated on
   **both** sides, because (I.6) neither half's local protocol says what the compositor
   assumes.

**Why symptom-directed ordering, honestly scored.** It is a *search* discipline, and it
finds the gaps that have already bitten. It is therefore biased toward the known. The
mitigation is to run it on a **working** trace (the clean boot, §7's neighbours) as well
as the failing one, so the traversal also covers determined-looking paths; that is the
weakest and least defensible step, and it is stated here as such rather than dressed up.

**The one-line rule this section yields, to sit beside I.0's test:**

> Do not traverse the codebase by its shape. Choose the symptom, slice backward over
> data and control **and the shared state and transition guards**, and let the slice
> define the section. Verify a citation before it becomes a method.

---

## Part II — Applied to this codebase

### II.0 The summary, in the language of the sources

Using Part I's vocabulary, the §8 session's finding is:

- The board's stop/wake × split behaviour is a **composed state machine** (I.4) whose
  safety property — *an effect must not be applied unless its undo is reachable* —
  had **no owner** (I.1: a decision with no home), was **entailed but not stated**
  (I.3: no invariant to deduct from), and its violation was **representable** (I.5:
  the unsafe order compiles and runs).
- The reading failure was that there was no contract to check (I.2) and no assertion
  to trip (I.7), so the only oracle was the board, at one flash cycle per
  counterfactual.

### II.1 Where things already stand (be fair to the codebase)

The pure-core/shell split is **I.1 done correctly at the level of individual files**,
and it paid: `lowpower_logic`, `transport_logic`, `rgb_key_logic` are decisions with
owners and tests. `docs/BOARD-LAYER.md` states the layer contract. This is not a
codebase that ignored the principles; it applied them *per decision* and left the
**relations between decisions** — which is exactly the layer none of I.1–I.8 assigns
to a single file unless you create one.

### II.2 The three remedying moves, ordered by strength (I.5, I.2, I.7)

For each composite relation, prefer the strongest home you can afford:

1. **Unrepresentable** (I.5, I.6) — restructure so the bad order cannot be written.
   For §8: move the matrix save/restore *inside* the stop/wake pair, so PRESLEEP has
   no side effect to leak; or make the state machine expose a handle that cannot
   enter PRESLEEP unless the STOP transition is available (typestate in C: an opaque
   handle type only the completed transition produces). Expensive, permanent.
2. **Executable** (I.2, I.7) — if it cannot be made unrepresentable, assert it where
   it can be violated, and test it. For §8 this is done: the rule is now the pure
   predicate `lpwr_presleep_is_allowed_decide`, with a test composed from the real
   deciders ("timeout_allowed ∧ ¬stop_allowed ⇒ refuse"), so a reordering fails the
   test rather than the board.
3. **Prose** (I.4) — a composite diagram plus the rule in one sentence, when neither
   of the above is affordable. Weakest: it helps a human and nothing fails if it
   goes stale.

And the judgement call from earlier sessions, now with a source: **not every relation
earns a home** (I.5's cost; I.8's ceremony). Give homes to **safety properties** and
to the **seams that compose independent machines**. Everything else stays
underdetermined on purpose.

### II.3 What is *not* yet determined in this tree (the candidate artefacts)

The concrete gaps, each a relation with no home:

1. **The stop/wake × split composite.** Two machines (lowpower, wls split) whose
   product holds the §8 fault: master refuses-or-takes a stop while the slave is
   ordered asleep and released only over a USB-gated command. Its safety rule and its
   cross-half contract exist nowhere. ***This is the primary artefact.* → now created
   as `docs/STATE-MACHINE-stop-wake-split.md` (2026-10-15)**, derived by the §I.9
   symptom-directed slice, with S1 (panel) determined executably and S2 (slave) still
   on the prose rung.
2. **The indicator matrix's ownership chain** (`TODO.md` §7): ownership of the RGB
   matrix passes between the boot code and the indicators; the rule "ownership must
   be readable without the paint running" was implicit. *Now determined* — the §7 fix
   made the boot code's *own* expiry a fact (`wls_indicator_boot_code_owns_matrix`), and
   the **arbitration between painters** (which had no home above the frame pass's call
   order) is now executable: `wls_frame_owner_of` / `wls_frame_owner_is_exclusive` in
   `indicator_logic.{h,c}`, with the composite written down in
   **`docs/STATE-MACHINE-indicator-ownership.md` (2026-10-15)**. Still undetermined
   there: *which painters overlap which LEDs*.
3. **The pad → wake-code attribution** (`wls.c` armed mask × `lpwr_wb32.c` aliasing):
   the rule "the mask must include every pad the board arms, and the alias is why
   UART is excluded" is comment prose, not a check.
4. **The transport authority** — see `docs/ADR-transport-authority.md` for the
   decision; whether its rule is determined executably is open.

### II.4 The method this document implies (to be folded into `docs/METHOD.md`)

A candidate, not yet adopted — for the user to judge before it becomes process:

> **For every safety property that spans more than one file, name its home before
> writing the fix.** State the property in one sentence; apply I.0's test (*what
> fails if I break it?*); if nothing fails, create the cheapest home from II.2. A fix
> that leaves the property's home uncreated is a patch (Lamport, I.8) — it repairs
> the instance and leaves the class.

---

## Sources consulted

- Parnas, D. L. *On the Criteria To Be Used in Decomposing Systems into Modules.*
  CACM 15(12):1053–1058, 1972. doi:10.1145/361598.361623.
- Meyer, B. *Object-Oriented Software Construction*, 2nd ed., Prentice Hall, 1997,
  ch. 11; and *Applying "Design by Contract"*, IEEE Computer, Oct 1992.
- Hoare, C. A. R. *An Axiomatic Basis for Computer Programming.* CACM 12(10):576–580,
  1969. doi:10.1145/363235.363259. (After Floyd, R. W., *Assigning Meanings to
  Programs*, 1967.)
- Lamport, L. *Specifying Systems: The TLA+ Language and Tools for Hardware and
  Software Engineers.* Addison-Wesley, 2002. (Free from the author.)
- Lamport, L. *Who Builds a House Without Drawing Blueprints?* CACM 58(4):38–41,
  2015. doi:10.1145/2736348.
- Newcombe, C., Rath, T., Zhang, F., Munteanu, B., Brooker, M., Deardeuff, M. *How
  Amazon Web Services Uses Formal Methods.* CACM 58(4):66–73, 2015.
  doi:10.1145/2699417.
- Minsky, Y. *Effective ML* (2010 Harvard lecture); the maxim *"make illegal states
  unrepresentable"*, discussed at Lambda the Ultimate, 2007.
- Wlaschin, S. *Designing with Types: Making Illegal States Unrepresentable* (2013).
- Dimovski, A., Kouzapas, D. et al. *Typechecking protocols with Mungo and StMungo.*
  PPDP 2016. doi:10.1145/2967973.2968595.
- Honda, K., Yoshida, N., Carbone, M. Multiparty session types / Scribble protocol
  language.
- McConnell, S. *Code Complete*, 2nd ed., Microsoft Press, 2004, ch. 8 (Assertions).
- Microsoft Research. *Code Contracts* (RiSE); Fähndrich et al., *Practical
  verification for the working programmer with CodeContracts and Abstract
  Interpretation*, 2011.
- Alpern, B., Schneider, F. B. *Defining Liveness*, Information Processing Letters,
  1985.
- Bhattacharya, P. *Introduction to SVA Assertions for Design Engineers*, 2011.

### Tool sources for a state-machine artefact (if one is built)

- **TLA+ / TLC / PlusCal** (Lamport) — the canonical tool; model-checks `Init ∧
  □[Next] ∧ Liveness` and reports the minimal-length error trace (I.8).
- **P** (Microsoft, used by AWS) — same modelling discipline, closer to a
  programming language; PObserve checks production traces against the spec.
- **Quint** (Informal Systems) — a modern, more ergonomic surface over TLA-style
  modelling.
- **Spin / Promela** (Holzmann) — LTL and safety testers, if LTL is wanted directly.
