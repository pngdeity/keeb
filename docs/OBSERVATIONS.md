# Observations — the owner using the board

**What this file is for.** A dated, first-person record of **real reactions to the
real keyboard**, captured as they happen. It exists because every other document
here runs one direction — *derive the requirement from the person, then implement
the requirement* (`docs/UX-REQUIREMENTS.md` § 1.5: `experience → requirement →
interface → implementation`). That direction produces honest requirements and
cannot, by itself, discover that a requirement is wrong or that something should
not exist. This file is the other direction: **the concrete thing is judged, and
the requirement is what is judged** — which is the only move that can make this
product better rather than merely verified. The distinction is stated in
`docs/METHOD.md` Part II § 0 ("observe before you explain") applied to the
*experience* rather than to a fault.

**Why it is a separate file.** The requirements set is a *contract*; this is
*testimony*. Mixing them would let a raw reaction read as a settled requirement,
and would let the contract's tidy shape quietly smooth over what was actually
felt. The two are reconciled deliberately, at the bottom of this file, after the
fact — never at the moment of capture.

## The rule for this file (read before adding an entry)

1. **Capture raw, judge later.** An entry is *what happened and what it felt
   like*, in the owner's own voice. **Do not map it to an X-n at capture time, do
   not tidy it, do not make it consistent with the requirements.** The
   inconsistency is the data.
2. **First person, concrete, dated.** "I" and "today", not "the user" and "in
   general". "I reached for the right spacebar and got a space" — not "Fn
   discoverability may be suboptimal".
3. **Record the annoyance, not only the fault.** A thing that *works but irritates*
   is more valuable here than a thing that is broken: a fault has a home already
   (`TODO.md` defects); an irritation has none.
4. **Record the reflex, not only the failure.** "I did X without thinking" is a
   finding about the design even when X worked.
5. **One entry per event, timestamped.** The date is the whole provenance; there
   is no other structure to keep.
6. **Never delete an entry.** If it is later judged wrong, it gets a
   `**Contradicted (date):**` line beneath it (a contradiction is itself a finding
   about how the board reads). Deletion loses the only record of what it was like
   to meet the board for the first time.

## How entries are reconciled (the only place the vector runs the other way)

Periodically — or when an entry has sat long enough to be sure it is not a mood —
read the log and put each entry in one of four buckets. **This is done in a
separate pass, never while capturing:**

- **A defect** → `TODO.md`, with the entry cited as the *observation* that found it.
  This is a real finding: the board did something wrong.
- **A requirement gap or a wrong requirement** → `docs/UX-REQUIREMENTS.md`,
  **including the case where the entry contradicts an existing X-n.** A
  requirement that a real session contradicts is the most valuable entry in this
  file; it is corrected, or given a `> **SUPERSEDED (date).**` note per § 1.5.
- **A subtraction** — the entry says a feature, indicator, or key should *not*
  exist. → the trim decision (§ 8 of the requirements) and a `TODO.md` item. **The
  1992-era and Jobs first-principle this file is built on is subtractive: "the
  most important decisions you make are the things you decide not to do."** An
  additions-only log has failed; actively look for the "why is this here at all"
  entries.
- **Nothing** → left here, marked `**Judged: noise (date)**`, kept for the record.

## The known gaps in this file (so it does not overclaim)

- **It is not an observation *session*.** Apple's own protocol (*Some Techniques
  for Observing Users*, Gomoll, Apple ATG, 1992 — the same 1992 body this project
  cites) is a third-party observer watching a user work **unhelped**, with the
  rule *"attribute the difficulties to faulty design, not to the participant."*
  This file is self-observation, which has a known bias: **the owner reflexively
  compensates for the board's flaws and so will not notice them.** Where an entry
  records *not* noticing something, that is the most reliable kind here.
- **The unhelped session is the missing half, and it is not writable.** It needs
  the board in hand and a second person watching, which is the same gate as the
  flash-gated work in `TODO.md`. When it happens, it gets its own dated section
  below, with the observer as author.
- **The four circumstances are the task list** (`docs/UX-REQUIREMENTS.md` § 1.1).
  An observation session, when it runs, uses *those* as the literal tasks — not
  invented ones — because they are the owner's own stated situations.

---

## The log

<!-- New entries at the top. Format:

### YYYY-MM-DD — <one-line title>
<what happened, first person, raw>

**Judged (YYYY-MM-DD):** <bucket, and where it went>
-->

_No entries yet. This file was created 2026-10-15, before its first entry, so the
rule is fixed in advance and the first entry cannot quietly invent one._
