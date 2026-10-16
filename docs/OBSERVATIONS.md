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

### 2026-10-15 — the channel cue did not appear, and the backlight went out while I watched

Session: both halves flashed with `8ea408a4…` (the A7+A8+X-4 build). Left half has
the USB-C cable to the host.

**The X-4 channel cue, judged first-hand.** Switch on **BT**, not touching any
keys. In the right half's top row **every LED in the row is lit like the
backlight** — solid white, no luminance difference between them and no change over
time. If one of them is supposed to be the channel cue, **I can't tell even looking
closely.** Flipping the switch to **2.4 GHz** changed **nothing** about the right
half's top-row light.

**The backlight went out by itself, twice, while I was only looking.** Once with
the switch on **BT** and no keys touched. My first instinct was to flip the
selector to USB — which I did — and the backlight **did not come on**. I then
unplugged and replugged the USB cable to the host and switched back to BT. Later,
with the switch on **2.4 GHz** and again no keys touched, it went out again.

**Raw, at capture:** the cue is invisible to me; the thing I actually did was
reach for the switch, and it didn't help. I don't know yet whether that instinct
was wrong or the board was.

**Judged (2026-10-15):** _pending — see `TODO.md`; the two facts are being
separated (a painted-but-illegible cue vs. a not-painted cue, and the backlight
extinction as its own finding)._

**Follow-up the same session (raw):**

- **Q1 — USB looks the same as BT.** Switched BT → USB with the backlight on: the
  right-half top row is **not visibly different** from the BT top row. (Prediction
  was: on USB, *no* channel LED lit, so the two rows should differ.)
- **Q2 — nothing dims differently.** Turning the backlight up and down through the
  encoder: **no single LED** can be discerned dimming differently from its
  neighbours. The overall brightness definitely tracks the encoder.
- **Q3 — a keypress does not wake it.** After the backlight came back (by
  switching to BT), letting it go out again, then pressing **one key** — on the
  **left** half, and separately on the **right** half — had **no discernible
  effect on any LEDs on the keyboard.**

**Judged (2026-10-15):** _pending — Q3 is the load-bearing one: the documented
wake source (a keypress, § 6) does not visibly restore the backlight, which is a
larger fault than the missing cue and may be the same one._

**Instrument reading the same session (the diag block, switch on USB, cable in the
left half, backlight on):**

```
battery:   100%  charge=2 (full)  transport=USB
model:     1
host(raw): 2 (USB)
bt profile:0
md fw ver: 1  (0 = module did not answer 0x5D)
md state:  3 (DISCONNECTED)
DIAG:      switch=1 (USB)  devs=0  host=2  usb_line=1  bootcnt=1  link=3
PINS:      C14=1  C15=1  B9=1  (B9: 1 = cable detected)
RESET:     cause_bits=0x30  (power-on, external-pin)
BOOT CODE: 7 amber, 5 white  ->  stage=RSTCAUSE code=5
JUMP:      no journal (our bootloader_jump has not run since power-on)
```

**What this reading is for, raw:** I took it to test whether the left half believed
it was the master (the half with the cable is the master, and B9 is the cable-detect
pin the keymap's `is_keyboard_master()` reads). **`B9=1` says cable detected** — so
the master condition is *true* on the half I am looking at, and that theory is
falsified by measurement. `switch=1 (USB)`, `devs=0`, `host=2`, `usb_line=1` — the
transport is cleanly USB, no split-brain; `bootcnt=1` says the half has not
re-booted, so this is a settled state and not a read taken mid-transition.

**Judged (2026-10-15):** _pending — recorded because it is a **negative result that
removes a candidate**, which is the kind that is otherwise lost. The master gate is
open and the cue still did not paint, so the fault is inside the frame pass or its
render path, not in who owns the half._

---

### 2026-10-15 (investigation note, not testimony) — three candidates tested and discarded; one remains

Recorded here rather than in `FINDINGS.md` because it is **inference, not
measurement**, and `docs/METHOD.md` Part II § 0 forbids writing inference up as a
finding. Each candidate below was checked against the source and **falsified**:

1. **The slave was being looked at / the master gate was shut.** *Falsified by
   the instrument reading above:* `B9=1` (cable detected) on the half under
   observation, and the four channel LEDs (17/18/19/20) are on the **left** half
   (`keyboard.json` layout), which is the half holding the cable. The gate is open.
2. **`WIRELESS_ENABLE` or the frame pass was not reached.** *Falsified:* the build
   flags carry `-DWIRELESS_ENABLE` and `-DRGB_MATRIX_ENABLE`, and carry **no**
   `-DRGBLIGHT_ENABLE`, so the `#ifdef RGBLIGHT_ENABLE` early-returns at the top of
   `rgb_matrix_indicators_advanced_kb` are inert.
3. **The effect repaints after the indicators, discarding the writes.** *Falsified
   in the core:* `quantum/rgb_matrix/rgb_matrix.c` runs `rgb_task_render(effect)` →
   `rgb_matrix_indicators()` / `rgb_matrix_indicators_advanced()` → `rgb_task_flush`.
   Our per-LED writes are between the effect and the flush and survive.

**The surviving candidate — a livelock of the class `FINDINGS.md` already names.**
`epomaker_split65.c:264-268` calls `wls_indicator_boot_code_start()` then
`wls_indicator_boot_code()`, and **returns `true` (abandoning the rest of the pass)
whenever `wls_indicator_boot_code_owns_matrix()` is true**. That predicate is just
`boot_code_active` (`wls_indicator.c:449-451`). The **only** path that clears it
while playing is `wls_indicator_boot_code()` reaching its own deadline check
(`wls_indicator.c:506-509`), which requires **that function to be called**. The
play window is one frame — for the reported `7 amber, 5 white` that is
`2*300*7 + 1500 + 2*300*5 + 3000` = **11,700 ms**.

So if the frame pass stops being called before that window elapses — a suspend, or
the matrix being disabled during idle (`HS_SLEEP_TIMEOUT` is 1 minute) — then
`boot_code_active` is never cleared, and **on every later frame the pass returns at
line 267 and nothing else ever paints**: no channel flash, no link cue, no X-4 cue,
no battery indicator. The user's three observations (no cue at all; USB
indistinguishable from BT; a keypress not restoring the backlight) are all
consistent with that single state.

This is the **feedback shape** of `FINDINGS.md`'s single defect class: *a state
whose only exit is a call the same state suppresses.* It is stated here as a
**hypothesis with a named discriminating test**, not as a conclusion.

**Judged (2026-10-15):** _pending — untested. The discriminating test is: after a
cold boot, leave the board untouched for **under** ~10 s (well inside the 11.7 s
window) and then touch a key to dismiss the code early; if the indicators then
appear and the board is normal, the livelock is confirmed. If the board is still
dead in that case, this candidate is wrong too._

---

### 2026-10-15 — THE INSTRUMENT READING THAT SETTLES IT (the livelock is CONFIRMED)

The discriminating test was run. Raw result:

> After interrupting the boot code with a keypress, **the white solid backlight
> came on immediately.** The right-half top row LEDs are all solid white with no
> luminance changing with time. The right-half bottom row has seven keys, and the
> **fourth and fifth key from the left of the right half are green**, with no
> luminance changing with time.

**How it reads:**

- **The keypress restored the pass — the livelock is real.** Pressing a key runs
  `process_record_kb` → `wls_indicator_boot_code_dismiss()` (`epomaker_split65.c:141`),
  which clears `boot_code_active` and so releases
  `wls_indicator_boot_code_owns_matrix()`. The frame pass then stopped returning
  early at `epomaker_split65.c:267` and every indicator resumed at once. **Before
  that keypress the pass was abandoning every frame.** The hypothesis is confirmed
  by the mechanism it predicted, and the two falsifiers offered both failed to fire
  (the board was *not* still dead).
- **The two green LEDs are the battery indicator, working correctly.** Their
  indices are 64 and 65 (`config.h:57-58` `HS_MATRIX_BAT_SOFT_INDEX`/`_INDEX2`),
  painted by `wls_indicator_battery()` (`wls_indicator.c:146-149`), described in
  the source as "two adjacent right-half bottom-row LEDs". That is the fourth and
  fifth key of the right half's bottom row, exactly as observed. Steady and green
  is the design (charged; not a blink). **Not a fault** — it is the *evidence* that
  the rest of the pass had been starved, because it is the first indicator that had
  ever appeared.
- **The top row remained uniform white, with no channel cue.** Read carefully, this
  does **not** re-open the cue question: at that moment the transport was USB
  (`switch=1`), and the X-4 prediction is that on USB **no** channel LED is lit, so
  a uniform top row is the *predicted* result. What the run proves is narrower and
  sufficient: the pass now runs and the battery indicator paints, so an indicator
  **can** reach the matrix. Whether the cue paints on BT/2.4 GHz is still unmeasured
  and must be re-tested now that the pass is unblocked.

**Judged (2026-10-15): REAL DEFECT.** The fault is not in the X-4 cue at all: it is
that `boot_code_active` is cleared **only** by a call the same state suppresses, so
any frame-pass interruption inside the 11.7 s boot-code window latches the whole
indicator system off permanently. It is the **feedback shape** of `FINDINGS.md`'s
single defect class ("a state whose only exit is a call the same state suppresses")
and it **silently masked** the X-4 cue, the A7 link cue and the A8 behaviour on the
very flash meant to verify them. Recorded in `TODO.md` as its own defect; the X-4
cue's own verdict stays *pending* and must be retried on an unblocked pass.

---

### 2026-10-15 — **CORRECTION: the mechanism above is WRONG.** The observation stands; the reading was mine

Two further answers settled it, and they refute the livelock reading:

1. **The board had been idle for 30 seconds** (measured by wristwatch) when the
   backlight went out.
2. **On a fresh cold boot with the switch on USB, the boot code finishes cleanly on
   its own** — and afterwards the green battery LEDs are present on the right half's
   bottom row, while the top row shows no indicator.

**Why (2) is the refutation.** The play window is 11,700 ms and expires unaided; 30 s
> 11.7 s, so `boot_code_active` clears by itself and the pass is **not** starved. The
livelock reading of the keypress test was therefore **wrong**: the keypress did not
*release* a stuck latch. The instrument reading (a keypress restoring the backlight)
is still real and reproducible — only my explanation of it was wrong, which is
exactly the failure mode `docs/METHOD.md` Part II § 0 names.

**The boot-code latch is a latent hazard, not the observed fault.** The code really
does depend on the paint function being called to expire (`wls_indicator.c:506` is the
only clear), so the hazard is worth closing on its own merits — but it must **not** be
recorded as what happened on this board.

**Where the suspect moves.** The idle figure is **30 s**, and `HS_LBACK_TIMEOUT` is
**exactly `30 * 1000` ms** (`wls/wls.h:26`) while `HS_SLEEP_TIMEOUT` is `60 * 1000` ms
(`:27`). The board darkened at the **link-back** deadline, not the sleep deadline, so
the thing to chase is the link watch / low-power path (`hs_rgb_blink_hook` →
`hsm_link_watch`, `wls.c:288-319`), not the boot code. Both deadlines live in
`hs_link_timers` and `hsm_link_restart` is called from `hs_link_activity`; whether the
30 s countdown can order a stop on a link that is merely *disconnected* is the
question.

**Corrected verdicts:**
- **The boot-code latch:** latent hazard; close it, but it did not cause this.
- **The 30 s darkening:** **OPEN** — real, reproducible, mechanism unidentified.
- **The X-4 cue:** **still unverified.** Its "no channel LED on USB" prediction is
  *consistent* with the clean-boot observation (top row uniform on USB), but BT and
  2.4 GHz have not been retested on a board that is behaving.

---

### 2026-10-15 — the 30 s darkening: the link watch reaches both arms, and the guard is USB-only

Read from source after the correction above; **this is a candidate with a source
argument, not a measurement.**

The two deadlines are separate (`wls/wls.h:26-27`): `HS_LBACK_TIMEOUT` = **30 s**,
`HS_SLEEP_TIMEOUT` = **60 s**. They are watched by `hs_rgb_blink_hook`
(`wls/wls.c:287-313`), which runs in steady state (`hs_mode_scan` calls it whenever
the switch has *not* moved, `:249-255`), master-gated only.

The pure core returns exactly one action (`transport_logic.c:248-278`):
- `HSM_LINK_DISCONNECTED` + 30 s elapsed → `HSM_LINK_ACT_RECONNECT`;
- `HSM_LINK_CONNECTED` + 60 s elapsed → `HSM_LINK_ACT_SLEEP`.

**Both arms arm the low-power stop** — the shell calls
`lpwr_set_timeout_manual(true)` in *each* (`wls.c:305` and `:308`). So a merely
**disconnected** link, on the 30 s deadline, arms a stop as well as poking the module.
That is the arithmetic coincidence: the board darkened at ~30 s, which is
`HS_LBACK_TIMEOUT`, not the 60 s sleep deadline.

**Why USB was unaffected, and why that fits.** `wls_lifecycle_lpwr_allow_timeout()`
(`wls_lifecycle.c:198-214`) refuses the stop when
`wireless_get_current_devs() == DEVS_USB`. So on USB the arm is harmless; on **BT or
2.4 GHz it is not**. The darkenings happened with the switch on **BT**, and later on
**2.4 GHz** — never on USB. The guard is real and USB-shaped, which is exactly the
seam the observation falls on.

**What this does not yet explain.** The user's instrument read had `md state: 3
(DISCONNECTED)`, so the reconnect arm is the likely one; but the darkening was also
observed once while the board was *not* being read, and a second time on 2.4 GHz (where
`md state` was not captured). Whether the same `RECONNECT`-arms-a-stop path fires on
2.4 GHz is **unverified**. Also unresolved: whether the stop is a true STOP (RGB task
suspended, which would look exactly like "the backlight went out") and whether any wake
source restores it — the user reported a keypress not restoring it, and `lpwr_exti_init_hook`
(`wls.c:318`) drives the columns high specifically so a keypress *can* wake the board,
so a keypress that does nothing is itself a question.

**Judged (2026-10-15): the leading suspect, stated as a hypothesis.** The test that
would settle it: with the switch on **BT** and **no host connected** (so `md state` is
DISCONNECTED), leave the board idle past 30 s and watch for the darkening; then repeat
with the switch on **USB** (`lpwr` must refuse). If BT darkens and USB does not, the
arm is confirmed. The other question to answer first is the simple one: **how long
after a cold boot, untouched, until it darkens** — and whether the boot-code keypress
that "fixed" it earlier was in fact just *activity* resetting the countdown rather than
dismissing anything.

---

### 2026-10-15 — the board does not come back: after the 30 s darkening, USB is half-dead

A clean reproduction and, more importantly, **what happens next.** Verbatim:

> When I execute cold boot, let the boot code finish, then switch the switch from USB
> to BT and let the backlight turn off after 30 seconds, after flipping the switch from
> BT back to USB, the backlight does not come back on and **only the left half types
> and the right half does not type.**

**Raw, as it reads to me:** the darkening is not just cosmetic — the board enters a
state it does not leave. Flipping the switch back to USB does not recover it, and
**the right half stops typing.** That is worse than a missing indicator: the keyboard
is half-functioning in the mode I switched *to*.

**What this is evidence for (not yet a cause):**
- The 30 s darkening is now **reproduced on demand** from a cold boot (USB → BT, idle
  30 s), so the timing is confirmed rather than inferred from a wristwatch coincidence.
- The recovery failure is the **new** fact. Flipping to USB leaves the backlight off and
  kills the right half's input, so whatever the 30 s deadline arms is **not** undone by
  the switch returning to USB.
- The right half not typing points at the **split link**, not at the LEDs: the two
  halves communicate over `SERIAL_USART_DRIVER SD1`, and the master relays the slave's
  keycodes. A right half that types nothing while the left types suggests the **slave is
  stopped or the split link is down** — which would be consistent with a low-power stop
  having been armed and the slave having been *told* to power down
  (`wls_split_send(WLS_SPLIT_CMD_POWER_DOWN)` in `wls_lifecycle_suspend_power_down_user`,
  `wls_lifecycle.c:191`) without a matching wake.

**A mechanism was proposed here and then REFUTED by the source — do not re-derive it.**
The claim was that both halves set the split-link pins to open-drain on the way into the
stop and that the wake path skips the restore on USB. It is refuted: `usart_init()`
(`wls_eeprom.c:11-15`) is called at `wls_lifecycle.c:170`, **before** the USB
early-return at `:175`, so the pins *are* restored; and a BT→USB switch flip runs
`suspend_wakeup_init()` at `wls.c:212`, reaching that same restore. So the split pins are
not the fault. This is the second time in this session that a mechanism was written
before its gates were checked, which is exactly what `docs/METHOD.md` Part II § 0 warns
against.

**The reflex, raw:** I flipped the switch expecting the board to come back, the way it
always has — and it did not, and then half the keyboard was gone. My instinct was to
flip it back and forth; that did not help either.

**Judged (2026-10-15):** _pending — this is the most serious finding of the session and
it supersedes the darkening as the thing to chase. The question is no longer "why does
the backlight go out" but **"what state does the 30 s deadline put the board in, and why
does the switch back to USB not clear it"**. **A mechanism is now identified in source
(not measured):** the low-power stop's wake set is filtered by
`lpwr_wakeup_armed_mask` (`wls/wls.c:423-431`), which deliberately omits
`LPWR_WAKEUP_UART` because this board's WB32 EXTI aliases the module UART RX pad onto a
matrix column — so a legitimately-firing edge can arrive stamped UART and be **discarded
as a phantom**, and the discard path (`lowpower.c:284-288`) re-enters `LPWR_STOP`
**without ever calling `lpwr_wakeup_cb()`** — the only place that re-enables the matrix
and runs `suspend_wakeup_init()`. The tree's own documentation (`lowpower.h:44-58`) names
the consequence as *"the half comes to rest dark and unresponsive"*, which is the symptom
observed. The source-verified facts, the refuted candidate, this mechanism and the tests
that would confirm it are in `TODO.md` § 8. **Do not treat the mechanism as the cause
until the keypress-vs-switch test there has run** — this session has already recorded two
mechanisms written before their gates were checked._

---

### 2026-10-15 — test (A) run: the mechanism is FALSIFIED, and the halves are separated

The keypress-vs-switch test the mechanism predicted on was run. Verbatim results:

> 1. Backlight still off. 2. Backlight still off. 3. Backlight is off. Typing on left
> half. No typing on right half. 4. backlight off.

(1 = one key on the **left** half while stranded; 2 = one key on the **right** half while
stranded; 3 = the switch flipped BT → USB while still stranded; 4 = a second strand, then
the switch flipped **with no keypress first**.)

**The mechanism is dead.** It predicted that a **keypress** would be accepted (a genuine
`LPWR_WAKEUP_MATRIX` edge, which the armed mask *does* include) and would run
`lpwr_wakeup_cb()`, restoring the backlight — while the **switch flip** would arrive
stamped `LPWR_WAKEUP_UART` and be discarded as a phantom. The observation is the
opposite of usable: **neither** a left-half keypress nor a switch flip restored the
backlight, and step 4 (flip alone) matched step 3. If the mask had been the trap, step 1
would have recovered the board. It did not.

**The new fact that is load-bearing — step 3 separates the halves.** After the flip to
USB, **the left half types and the right half does not.** That is not a whole-board STOP:
the master is **alive and running on USB** (its USB is up, its matrix scans, it types)
while the slave is not. So the fault is narrowed to **the slave's state, or the split link
between the halves** — not to the low-power stop on the master, and not to a shared wake
path.

**Judged (2026-10-15):** _mechanism FALSIFIED by measurement; the surviving fact is the
master/slave asymmetry. Recorded here so the refuted mechanism is not re-derived. Next:
the `wls_split` slave path and the split command set — specifically whether the slave is
ever **sent** a wake after the 30 s arm sends it to sleep, and whether the master's
transport change re-establishes the split link at all. `docs/METHOD.md` Part II § 0
applies: the next step is an observation of *which half's state is wrong*, not another
armchair mechanism._

---

### 2026-10-15 — the dark board explained: `presleep` turns the matrix off, and the refused stop never turns it back on

Source reading, not testimony, and **not a measurement** — recorded here because it is the
answer to "which half's state is wrong" that the entry above asked for, and because it
replaces a reading this session had already written down.

**It is one mechanism, and it is not a sleep.** `lpwr_task` walks NORMAL → PRESLEEP →
STOP → WAKEUP → NORMAL. The darkening happens in **PRESLEEP**, one state *before* the
stop: `lpwr_presleep_cb()` runs `rgb_matrix_disable_noeeprom()` unconditionally
(`lowpower.c:230`). Then, in STOP, `lpwr_stop_cb()` opens with
`if (!lpwr_stop_is_allowed()) { set_state(LPWR_NORMAL); return; }` (`:267-268`) — and on
this path the stop **is refused**, because the board's policy
(`wls/wls.c:389-421`, `lpwr_stop_is_allowed_decide(is_master, wls_sleep_ordered())`) only
permits a stop that has been *ordered*, and the 30 s idle path orders nothing. On the
refusal the machine returns to NORMAL and **`LPWR_WAKEUP` is never entered** — and
`lpwr_wakeup_cb()`, the **only** place `rgb_matrix_enable_noeeprom()` is called
(`lowpower.c:301`), lives there. The matrix therefore stays off **until a power cycle**,
and the MCU never actually slept.

**Why this is the satisfying kind of answer:** no wake code, no armed mask, no phantom
UART and no pin mode is involved — all four of them can be exactly as intended and the
board still goes dark and stays dark. **It is the feedback shape of the class
`docs/FINDINGS.md` names**, in its purest form yet: an effect whose *undo* is reachable
only through a state transition that the guard refusing the action makes unreachable.

**What it does not explain, stated plainly:** the **right half's silence**. This is the
master's matrix. The slave's half is a separate chain that stands on its own — the master
orders the slave to sleep over the split link (`0xAA` → `wls_order_sleep()` +
`lpwr_set_timeout_manual(true)`, `wls_split.c:53-61`), and the only command that would
release it (`0xCC`) is never sent, because its one call site
(`wls_lifecycle.c:179`) sits behind a `return` on the USB transport (`:175-177`) — chosen
deliberately, *"while cabled the rail must stay up on both halves"*. The two compose.

**Judged (2026-10-15):** _source-verified on every line; consistent with all four of test
(A)'s readings; **NOT** isolated by a measurement, and per `docs/METHOD.md` Part II § 0
it does not become a finding on source-reading strength. It is the strongest candidate
this session has produced, and the next step is a **code change** (order the stop, or move
the matrix re-enable out of `lpwr_wakeup_cb()`), not another hardware probe. Three earlier
readings this session were written before their gates were checked; this is the first
produced by checking gates first, and it was found *because* gate-checking the third
reading showed the master never stops._
