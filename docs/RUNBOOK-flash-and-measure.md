# Runbook: flash both halves and take the first real measurements

One session, four goals:

1. **Flash both halves** with the current build (Tier 1 item 4).
2. **Cold-boot check of the boot-site seeding** — the firmware now seeds the
   connection host from the physical switch *level* at boot, not from the
   persisted index. Confirm a power cycle lands on the switch's own transport.
3. **The battery measurement** (Tier 1 items 5/6) — capture the first real
   percentage and confirm the charge byte moves `1 -> 2`.
4. **The USB self-detach instrument** (open defect) — the `wls_diag` block
   reports `usb_line`, `switch_pos`, `devs`, `host`, `boot_count`, `link_state`,
   which is the disambiguator the original investigation lacked.

A fifth, unavoidable one rides along: **the 2.4 GHz dongle**.

**Updated 2026-10-15:** the current pre-flight is **§ 0.0.5**, whose artefact
carries two requirement fixes landed since this runbook was first written — **A7**
(the refused-link cue, `X-30`) and **A8** (the backlight floor, `X-7`). Their
predictions are in § 0.0.5 § 4 and their falsifiers in § 7; read § 0.0.5 before
this overview, which still describes the earlier walk-close session's four goals.

This runbook is written to be executed top to bottom. Commands are copy-paste
ready; every "expected" value is derived from the source, and the source of
truth for each is named in `code:` form so it can be re-checked rather than
trusted.

---

## 0. Before you touch the hardware

### 0.0 The pre-flight checklist (required, and it is not "it compiled")

**"Ready to flash" means airworthy, not green tests.** The rule (`TODO.md`
"Pre-flight discipline for a hardware test") is that a hardware session must not
begin until every assumption is stated and every effect predicted — closer to an
aviation pre-flight than to "run the test set and see." Three live livelocks in
the transport work were caught by this review rather than on hardware; the
cheapest place to find a defect is a review, not a flash. **The general process
this belongs to is `docs/METHOD.md`; this section is its hardware-session form.**

Leave the artefact — **§ 0.0.1-0.0.4 written out** — in the session notes or a
`docs/` file before flashing. The checklist:

1. **State the artefact.** Its path, size, and sha256; the exact submodule hash
   it was built from (§ 0.1); and that the working tree was confirmed clean
   against HEAD (`git status --short` shows only intended edits).
2. **List the untested assumptions.** For each: is it *measured* (cite
   `docs/HARDWARE.md`) or *inherited* (a guess carried from another board)?
3. **Answer the four review questions** (`TODO.md` "Pre-flight discipline"):
   does any effect feed back into its own trigger; does every signal have a real
   value here (not a constant, not undefined — check the ELF); which code is even
   compiled (a `#if` can delete the path you rely on); measured vs inherited.
4. **Predict each test case's hardware effect**, in a table, *before* running it.
   Name the observable and the **specific predicted value** (a colour, a byte, a
   count) — not "it works". This makes each case falsifiable.
5. **Name what the build does *not* explain.** Open faults (e.g. `-71 EPROTO`)
   and unmeasured facts (e.g. the switch-pin lie) that will still be present and
   must not be mistaken for a regression.
6. **Establish the non-flashing recovery first** (§ 0.3) if anything persists.
7. **State the falsifier.** "If X happens, the hypothesis was wrong and the next
   move is Y" — so a surprise changes the model instead of prompting a guess.
8. **Verify the artifact on disk** matches what was reviewed: rebuild fresh
   (§ 0.2) and compare the sha256, rather than assuming the file is current.

A pre-flight is legitimate to skip only when nothing on the board's behaviour is
being asserted — e.g. flashing a build identical to the one already running.

### 0.0.4 (filled in) — the Stage-4 jump-journal flash

**This is the working pre-flight for the flash that carries the jump journal and
the strong `bootloader_jump()` override. It is the build specified in
`docs/AUDIT-fcis.md` "Stage 4 — the discriminating build and its falsifier".**

**1. The artefact.** `qmk_firmware/.build/epomaker_epomaker_split65_nathan.bin`,
63.5 KB, sha256
`2ec21c449dcb775e69663210c9768986b6db61ad4b0272ff5ef91d91fe705ce6`. Built from the
working tree (this arc is **uncommitted**), so the identity is the working tree,
not a signed submodule hash. **Submodule HEAD is
`75a5ee699ea0cca42cf29ec08de7157cdfe360c6`** (root `ee3ad13`), but the build
carries a large uncommitted delta on top of it — the runbook's checklist wording
"the working tree was confirmed clean against HEAD" is **not** met and cannot be
until the arc is committed. What actually pins the reviewed source is the
sha256 above plus these **11 untracked files under
`keyboards/epomaker/epomaker_split65/wls/`** (a `git diff` would not show them;
they are in `wls.mk` and in the build):
`boot_code_logic.{c,h}`, `jump_journal_logic.{c,h}`, `wls_jump_journal.{c,h}`,
`wls_boot_jump.c`, `wls_module.{c,h}`, `wls_transport.{c,h}` — plus the untracked
test dirs `tests/boot_code_logic/` and `tests/wls_jump_journal/`. Record
`git -C qmk_firmware status --short` in the session log, not just a diff. The
board currently runs `usbguard.bin`
(`7659464ddc2153364f6476471d294661b650e49367b0c19d500cd6974902f81e`).

**2. Untested assumptions (all inherited, none measured).**
- The `.ram0` object survives a `NVIC_SystemReset` — *verified from the linker
  script and `crt1.c` (`__init_ram_areas` stops at `no_init_area`) and the ELF's
  own `wls_journal` placement, but not observed on silicon across a real reset*.
- The `0xA4` reply's bytes 23..31 are carried intact — *the encoder is unit-tested;
  the transport of the wider report is not*.
- The strong `bootloader_jump()` performs the same jump the weak one did — *the
  body reuses the real `enter_bootloader_mode_if_requested()`, so the jump code is
  upstream's, but the override-replaces-weak linkage is assumed to hold on this
  toolchain* (the ELF shows `T bootloader_jump`, one symbol).

**3. The four review questions.**
- *Does any effect feed back into its own trigger?* No. Stamping the journal is a
  one-way write before the reset; it is read only by the `0xA4` encoder, which
  does not feed the jump path.
- *Does every signal have a real value (not a constant, not undefined)?* The
  journal is `b` in `.ram0` at `0x20004fbc` (16 B) in the ELF; `wls_reset_cause()`
  returns retained bits; `timer_read32()` is live. `bootloader_jump` and
  `enter_bootloader_mode_if_requested` are both strong `T` in the ELF.
- *Which code is even compiled?* `wls_jump_journal.c`, `jump_journal_logic.c` and
  `wls_boot_jump.c` are all in `wls/wls.mk`; `KB_BATTERY_IDX_JUMP 23` is emitted
  in `wls_battery.c` under `#ifndef VIA_ENABLE` (VIA is not enabled).
- *Measured vs inherited?* The `.ram0` survival is reasoned from the linker +
  startup, not watched; treat the first reset as the measurement.

**4. Predicted hardware effect.** After flashing and a normal boot, a
`python3 host/battery_polybar.py --info` should print
`JUMP:      no journal (our bootloader_jump has not run since power-on)` — byte 23
== `0x00`. Pressing the `QK_BOOT` chord (Fn layer, right half `[10,4]`) should,
on the next boot, print `JUMP:      our QK_BOOT ran  gen=1 stage=… code=…
reset=0x… uptime=… ms` with byte 23 == `0x01`.

**5. What the build does not explain.** The `(5,5)` vs `(7,5)` reading (the
instrument window exceeds the subject's lifetime); the `-71 EPROTO` loop; the
open green-rendering of the amber group. None is a regression and none should be
read as one.

**6. Non-flashing recovery.** § 0.3 stands: `QK_BOOT` from the keymap, or the
bootmagic `Esc`-hold at plug-in on the left half. A dark board recovers by the
same route.

**7. The falsifier.** See `docs/AUDIT-fcis.md` "Stage 4": **journal present** =
our `QK_BOOT` path ran, which Stage 3 says is impossible without a key — that
falsifies Stage 3 and redirects to the keycode/matrix path. **`dfa0` window with
no journal** = the magic word was written outside our path, exonerating the
keymap. **Journal present but no DFU entry** = the fault is in the bootloader
entry mechanics, not the writer.

**8. Verify the artefact on disk** matches the reviewed sha256 (§ 0.2) before
flashing.

The flash is a **human action**: `wb32-dfu-updater_cli -t -s 0x08000000 -D
<bin>` then `-R` (or `./split65.py flash`). Do not run it from an agent.

### 0.0.5 (filled in) — the Tier-1 batch, carrying A7 and A8 (the current pre-flight)

**This is the working pre-flight for the next flash, and it supersedes the
walk-close draft that stood here before 2026-10-15.** That draft pinned
`aec731388c…` (64,600 B); requirement fixes have landed since (A7, A8, and the
X-4 channel cue), so the predictions below are rebuilt from the current tree —
**but the pinned hash still names the A7+A8 build and has not been regenerated for
the X-4 cue (see § 1's staleness note).** It is built from a committed, signed
tree, so the checklist wording "confirmed clean against HEAD" is met.

**What is new in this build over the walk-close artefact, and why each is here:**

- **A7 — the refused-link cue (`X-30`).** The module reports five link states and
  the board mapped all five, but the render **and** the watch flattened
  `REJECT` into an actionless start-up state — so "the module refused this
  connection" was painted **exactly like** "the link is not up", and those need
  opposite actions (fix the host's pairing vs. wait/re-pair). The core fix is
  `hsm_link_cue_of()` / `hsm_link_state_of_md()` (a `switch` with **no
  `default:`**, so a future state fails to compile — the class fix, since the
  original defect *was* a `default:` swallowing `REJECT`). The render is
  `wls_indicator_link_state()` (`wls_indicator.c:344`, called from
  `epomaker_split65.c:271`): master-gated, and it paints **only** on `REJECT`,
  leaving the LEDs to their owners otherwise. See § 4's REJECT prediction and § 2.
- **A8 — the backlight floor (`X-7`).** The value-down key (`RM_VALD`, the
  Fn-layer encoder CCW) previously drove the value to **zero** in five clicks
  (128→98→68→38→8→0, `RGB_MATRIX_VAL_STEP` 30 — see § 4), and at zero the LED
  rail drops (`wls_led_rail_apply()` keys the rail off `rgb_matrix_get_val() !=
  0`), so "intentionally dialled to zero" and "the board is dead" rendered
  identically. Now `WLS_RGB_VAL_FLOOR` (= 1) refuses the change and the shell
  consumes the record (`return false`), so upstream's `rgb_matrix_decrease_val()`
  never runs. **This changes the 2026-10-14 dark-board recovery**: CCW now stops
  at 1 rather than going dark. See § 2 and § 7.
- **A17 — the at-rest channel cue (`X-4`).** The channel was shown **only when it
  changed** (`wls_indicate_devs` fires from the switch edge, the keycode path and
  the re-pair long-press, then the LEDs return to the fill), so at rest the board
  said nothing about which channel was live — while X-4 requires the mode be
  indicated *"while the switch is in that position"*. The core fix is
  `hsm_chan_cue_of()` (`transport_logic.{c,h}`, one arm per `DEVS_*`, no
  `default:`), and the render is `wls_indicator_channel_state()`
  (`wls_indicator.c`, called from `epomaker_split65.c:272`): master-gated, it paints
  a **steady dim `{0x10,0x10,0x10}` on the one channel LED** for the live device
  index, and **defers to `wls_indicator_link_state()` on REJECT** (that cue owns the
  BT LEDs). See § 4's channel-cue prediction and § 5.

**1. The artefact.** `qmk_firmware/.build/epomaker_epomaker_split65_nathan.bin`,
**64,760 bytes**, sha256
**`8ea408a432dc47fc332e89d5ba0a45d40f7720c81e75d8d27f7148c5297319b9`**. This is
the walk-close build **plus A7 (the REJECT cue), A8 (the value floor) and the X-4
at-rest channel cue**, and is **160 bytes larger** than the walk-close
`aec73138…` (64,600 → 64,760). Verify the hash **before** flashing; if it differs,
the tree moved and this pre-flight is stale — regenerate it (§ 0.2) and update the
hash here.

- **Submodule `split65-overlay` = `b370a3b2f1`** (the X-4 cue; A8 is `a4878e7bfe`
  beneath it, A7 is `5819516e2c` beneath that), signed (`G`).
- **Root `main` = the commit that carries this runbook section, signed (`G`)**.
- `git status --short` shows **only** the benign untracked `qmk_firmware/lib/lufa`
  in the submodule; nothing else.

The board currently runs the **walk-close** build (`a45a9762…`, 64,736 B) — the
build whose flash **restored USB typing** and which reported `(7 amber, 5 white)`
over USB. It does **not** carry A7 or A8.

**2. Untested assumptions (state each as measured or inherited).**
- *`.ram0` survives a `NVIC_SystemReset` across a real reset* — **inherited**
  (reasoned from the linker script and `crt1.c`; never watched on silicon).
  Predicted consequence if false: the jump journal reads `no journal` even after
  a `QK_BOOT`, which is itself a finding.
- *The strong `bootloader_jump()` performs the same jump the weak one did* —
  **inherited**, but the ELF shows `T bootloader_jump` (strong, one symbol) and
  `T enter_bootloader_mode_if_requested`; the body reuses upstream's real entry.
- *The `0xA4` reply's bytes 11–22 and 23–31 are transported intact* — **measured
  on the encoder side only** (unit-tested); the wider report over USB in a stable
  link is not.
- *The battery level will move off 100 on 2.4 GHz* — **inherited** (only the radio
  path is known to answer `INQVOL`); this session is the measurement.
- *A cable with the switch on 2.4 GHz leaves the board wireless* — **now true by
  construction** (`hsm_input_rule`; the cable is no longer a transport input at
  all) but **never hardware-confirmed**. Note it was **falsified** on the
  pre-reform build: the old `hsm_switch_apply_with_cable` forced USB on any cable
  read, and the board measurably went to USB with `switch=3 (2.4G)`
  (`host(raw)=2`). See `docs/FINDINGS.md` engineering mode 2 and `TODO.md`.
- *A7's `REJECT` cue is reachable and correct* — **the sight is a CHOICE, never
  observed on hardware.** `REJECT` has not been produced on this board; the cue
  is a stage-4 UX choice (`docs/UX-REQUIREMENTS.md` § 0.5) awaiting a person's eye.
  Only the *requirement* (REJECT must not share a sight with DISCONNECTED, and not
  by colour alone) is proven; the dim-red-on-BT1/2/3 render is an opinion. This
  session is where it first meets a person, if a REJECT can be provoked at all.
- *A8's floor is reachable and is refused, not clamped* — **unit-tested, never
  hardware-confirmed.** The decider returns FLOOR at/below 1 and the shell
  consumes the record; whether the visible result is "the key stops responding at
  the dimmest setting" is the prediction in § 4.
- *The at-rest channel cue is right (X-4), and its intensity/read are a CHOICE* —
  **unit-tested, never hardware-confirmed.** `wls_indicator_channel_state()` paints
  a steady dim `{0x10,0x10,0x10}` on the one channel LED for the live device index;
  the pure `hsm_chan_cue_of()` is proven exhaustive and injective on the surfaced
  channels, but whether "one small steady LED whose position tells you the channel"
  is *legible at a glance* is a stage-4 UX opinion needing a person's eye (the same
  reservation as A7's REJECT sight). The arbitration -- the cue defers to the REJECT
  paint on BT1/2/3 -- is proven by construction but not on hardware.

**3. The four review questions.**
- *Does any effect feed back into its own trigger?* **No new feedback loop is
  introduced by the walk, and A7/A8/A17 add none.** The one loop-shaped site changed
  by the walk is the split device index: `wls_split.c` clamps the wire value in the
  pure core **before** it can reach `wls_module_devs_change()`, so the index that
  feeds the transport decision cannot echo back a value the transport itself would
  produce. A7's cue is a read of the module's state byte (`md_getp_state()`) with
  no write back; A8's floor is a read of `rgb_matrix_get_val()` with the *record*
  consumed rather than a value written; the X-4 channel cue **reads**
  `wireless_get_current_devs()` and paints an LED -- a read, not a transport write,
  so it cannot move the transport it displays. None modifies a signal it depends on.
  The one interaction to name is A7 vs the channel cue: both may want the BT1/2/3
  LEDs, and it is resolved by ordering, not feedback (the cue defers to REJECT).
- *Does every signal have a real value (not a constant, not undefined)?* The
  journal is `b wls_journal` at `0x20004fbc` (16 B, `.ram0`); `wls_reset_cause` is
  `T`; `bootloader_jump` and `enter_bootloader_mode_if_requested` are both strong
  `T`. `KB_BATTERY_IDX_DIAG 11`, `_BOOT_CODE 21`, `_JUMP 23` are all emitted
  (`wls.h`). A7 reads `*md_getp_state()` (the live module byte), A8 reads
  `rgb_matrix_get_val()` (live), and the X-4 cue reads
  `wireless_get_current_devs()` (live); all three are values, not constants. The
  three new `_Static_assert`s in `wls_battery.c` and the two frame-size asserts in
  the adapters **compiled in this build**.
- *Which code is even compiled?* `wls.mk` lists all 25 sources. `wls_indicator.c`
  and `transport_logic.c` are compiled with A7's and the X-4 cue's additions (both
  in the build; `nm` shows `hsm_link_cue_of`/`hsm_link_state_of_md`/`hsm_chan_cue_of`
  as `T`), and `wls_keymap.c`/`rgb_key_logic.c` with A8's.
  `KB_BATTERY_IDX_JUMP` is under `#ifndef VIA_ENABLE`; VIA is not enabled.
- *Measured vs inherited?* Listed in §2: the battery level and the
  cable-plus-2.4GHz behaviour are the two genuinely unmeasured claims the earlier
  session attempted; **A7's REJECT cue, A8's floor, and the X-4 channel cue are
  newly unmeasured** and have predictions below.

**4. Predicted hardware effect.**
- *After flashing, first cold boot (switch wherever it sits):* the boot LED code
  plays **one full frame**, amber group correct (`WS2812_BYTE_ORDER_RGB` is in this
  build). Read `(amber, white)` against the stage/code rule (amber = stage, 0 =
  OK; white = code + 1).
- *Switch on USB, cold boot, `python3 host/battery_polybar.py --info`:*
  `transport=USB`, `host(raw)=2`, `DIAG: switch=1`, `DIAG: devs=0`,
  `DIAG: usb_line=1`, `bootcnt` **+1** vs the previous read.
- *2.4 GHz, unplugged, 12 pulls over 60 s:* `battery: N%` **changes away from
  100** and `md state=2` (CONNECTED). If it stays 100 for all twelve samples,
  that is the result: `INQVOL` is never answered on this module revision.
- *Cable in, switch on 2.4 GHz:* the board **stays wireless** (does not switch to
  USB) and the level keeps updating; `charge` reads `1` then `2` as it tops.
  *(Engineering mode 2, serving X-20; the reading that falsified the old build.)*
- *Runtime BT→USB switch edge (Test C):* with the switch on BT and no host, flip
  to USB **without power-cycling** and type — **it types over USB**, `--info`
  shows `transport=USB`, `usb_line=1`. Highest-value check; never hardware-confirmed.
- **A8 — the value floor (`X-7`).** On the Fn layer, turn the encoder **CCW**
  repeatedly from the default. Predicted: the backlight steps 128→98→68→38→8 (four
  clicks, visibly dimming) and then the **fifth click does nothing** — the value
  **stops at 8**, it does **not** reach 0, and the board stays lit. `rgb_matrix_get_val()`
  never reads 0 by this path, so the LED rail stays up. *Falsifier:* the backlight
  goes **fully dark** after five-or-so clicks (the floor is not taking effect), or
  it keeps dimming past 8 (the refusal is not reaching upstream). Note this is the
  **behaviour change to the 2026-10-14 recovery**: a board dialled all the way down
  now rests at 8, dim but alive, and the same CCW key can no longer make it dark.
  Turning it back **CW** restores brightness normally.
- **A7 — the REJECT cue (`X-30`).** *Conditional and possibly unreachable this
  session*: if a Bluetooth connection is **refused** by the host (e.g. pair a BT
  slot to a host that rejects it, or a paired host that declines), the four
  BT-channel LEDs (indices 17/18/19) paint a **dim steady red** (`0x40,0,0`) while
  `REJECT` holds, distinctly from the "nothing painted" of DISCONNECTED. If no
  REJECT can be provoked, record that — it stays an unmeasured choice, per § 2.
  *Falsifier:* a refused connection renders **identically** to a non-connection
  (the cue is not firing, or the state byte never reaches `HSM_LINK_REJECT`).
- **The at-rest channel cue (`X-4`, A17).** With the switch on **BT** (any of
  BT1/2/3) or **2.4 GHz**, and *no key pressed and nothing changing*, one of the
  four channel LEDs (17/18/19/20) should be **steadily lit, dim**
  (`0x10,0x10,0x10`) — the one matching the live channel — while the rest of the
  matrix is the fill. Which LED is lit **is** the readout. On **USB** no channel LED
  is lit (the cable is the mode). Flipping the switch should move the lit LED to the
  new channel within a frame, and the transition flash should still be visible on
  top of it. *Falsifier:* at rest **no** LED is lit on a wireless channel (the cue
  is not firing / not called), or **more than one** channel LED is lit, or the cue
  paints over the REJECT red (the arbitration is wrong), or it is bright enough to
  read as "something just happened". The *legibility* of "one small steady LED" is
  a stage-4 UX choice — this is where it first meets a person's eye; record whether
  it is readable at a glance from typing posture.

**5. What the build does not explain.** Present and **not** regressions: the `-71
EPROTO` loop; the `342d:e4c6` self-detach (5 enumerations / 5 drops in 5 min, zero
over-current); the pin-lie (`C14`/`C15` readable-but-wrong, which fixes A–D do not
cover); the module's own firmware for BT (Layer 0, no dump/update path). The
`0xA4` reply is **unreachable while the transport is not USB** — the wireless
driver has no `.send_raw_hid` — so the diag/pin block stays silent on 2.4 GHz and
must not be read as a fault. **Also still open, and asked of this session:**
- **B15 — does a brightness-zero board still show its charge?** The soft battery
  indicator is gated on `rgb_matrix_get_val() != 0` (`wls_indicator.c:146`), so a
  board dialled to brightness 0 loses its charge readout — the X-7/X-5 seam. But
  A8's floor now **refuses** the value-down key at 1, so a board **cannot reach 0
  by that path**. The question therefore narrows to: *can the value reach 0 by any
  other route* (a saved EEPROM value of 0, `RGB_VAD`, `rgb_matrix_disable()`), and
  if so, is the charge cue then lost? Record whichever route exists.
- **The X-4 channel cue — now implemented in this build (`TODO.md`, A17).**
  Previously the active channel was indicated **only at its transition**
  (`wls_indicate_devs`), not while it was in effect; this build adds the at-rest
  cue (see § 4's prediction). While at the keyboard, judge the *legibility* the
  prediction cannot: is "one small steady dim LED whose position names the channel"
  readable at a glance from a typing posture, and does it conflict with anything
  else on the matrix? That judgement is the stage-4 UX input and can only come from
  a person at the board.

**6. Non-flashing recovery.** § 0.3: `EE_CLR` (hold Fn + `[7,8]`, then `[11,8]`
for 3 s) re-defaults confinfo to USB; the physical switch to USB then power-cycle;
the spacebar-hole short for DFU. Bootmagic `Esc`-hold is **left-half only** and is
a last resort (it enters DFU, it does not resume typing). **A8 changes one recovery
assumption:** the old "dim the backlight to zero" reflex can no longer darken the
board (the value stops at 8), so the value-down key is **not** a way to make the
board look dead — if the board still looks dead after A8, the cause is elsewhere,
and the same CCW key will not have been what darkened it.

**7. The falsifier.** *Battery still reads exactly 100 after twelve 2.4 GHz
samples with `md state=2`* ⇒ `INQVOL` is unanswered on this revision; the
"default 100" is the module's constant and the honesty fix (defect 1) becomes the
only path — the retry-harder option is closed. *At rest on a wireless channel, no
channel LED is lit, or more than one is, or the cue overwrites the REJECT red* ⇒
the X-4 cue is not firing, is not exclusive, or its arbitration with A7 is wrong;
compare against § 4's prediction. *The board switches to USB when a
cable is inserted with the switch on 2.4 GHz* ⇒ **this has already fired once**
(against the pre-reform build: `hsm_switch_apply_with_cable` forced USB on any
cable read, measured as `switch=3 (2.4G)` with `host(raw)=2`). It is what the
reform fixes; if it fires again on the new build, the cable still reaches the
transport decision by some path not yet found, and engineering mode 2 is unmet. *A
`(N, 5)` reading
with `N != 7` and a plausible stage* ⇒ the boot-code counts disagree with the
source, reopening the instrument question with the walk's fixes in place. *The
board drops USB while the switch says USB* ⇒ the self-detach path, unchanged by
this build; read the diag block for `bootcnt`/`usb_line` at the drop. *The
backlight reaches 0 (goes fully dark) under repeated CCW on the value-down key* ⇒
A8's floor is not taking effect, and the X-7 defect is not fixed. *A refused BT
connection renders the same as no connection* ⇒ A7's cue is not firing, or
`HSM_LINK_REJECT` is never reached.

**8. Verify the artefact on disk** matches `8ea408a4…` (§ 0.2) before flashing;
it was rebuilt from the committed tree during this pre-flight and matched.

The flash is a **human action** — see the note above.

### 0.1 Confirm what you are about to flash

```sh
cd /home/nathan/repos/pngdeity/incubating/keeb
git --no-pager log --format='%h %G? %s' -1
git -C qmk_firmware --no-pager log --format='%h %G? %s' -1
md5sum qmk_firmware/epomaker_epomaker_split65_nathan.bin
```

Expected: submodule signed (`G`) at whatever `split65-overlay` tip is current —
**do not pin a stale hash**; § 0.0.5 names the one this pre-flight reviewed. The
board source lives **in the submodule**, so the submodule hash is the firmware's
identity; the root hash is whatever `main` tip is current — check it is signed,
but do not pin it in advance.

The md5 is informational only — record it in the session log so a later build
can be told apart. Do **not** write it into `TODO.md` (it goes stale on every
edit).

### 0.2 Build the artifact fresh (recommended)

The `.bin` on disk was verified `63,532 B` / `md5 1d5a12cece195da0aa2d50b92fddc0f4`
at HEAD `c73e380`. Rebuild to be certain the artifact matches the source you
just logged:

```sh
./bin/make epomaker/epomaker_split65:nathan
```

Expect a clean build ending in `0  63[0-9]{3}  0  ...  epomaker_epomaker_split65_nathan.bin`
and the copy to the tree + userspace folders. **Note:** `bin/make` prints a
benign `qmk: error: argument ...: invalid choice: 'env'` line every run — it is
a PATH probe, not a failure.

### 0.3 Establish the non-flashing recovery BEFORE flashing (standing rule)

Per `TODO.md`'s pre-flight rule, a state-persisting path needs a recovery that
needs no reflash. Here the relevant hazard is **the board coming up on a
transport that types nowhere**.

| Recovery | How | What it does |
| --- | --- | --- |
| `EE_CLR` (hold 3 s) | **hold Fn + the top-right corner key** (`[7,8]`, the base `Mute` position) to arm the `_RST` layer, then — still holding — press the **right half's bottom-right corner** (`[11,8]`, the base `Right` position) and hold 3 s | wipes EEPROM → confinfo re-defaults → back to USB |
| Physical mode switch → USB | flip to the USB position, then **power-cycle** | the switch is only level-authoritative **at boot** on this build's switch-edge path; a flip *after* boot also works via the fixed switch-edge code, but a power cycle is the certain form |
| Spacebar-hole short | `docs/HARDWARE.md` | DFU, for reflashing |

**The arming key is not optional.** Fn alone reaches `_FL`, whose bottom-right
corner is `Home` — harmless, but not the reset. `EE_CLR` lives on `_RST`, which
is reachable *only* by holding `[7,8]` with Fn. Both corners are involved:
`[7,8]` arms, `[11,8]` fires. Sources: the `nathan` keymap's `keymap.md` §5;
`wls/wls_keymap.c` (`EE_CLR` arms `wls_ee_clr_timer` on press, clears on
release); `epomaker_split65.c` (`timer_elapsed32(...) > 3000` →
`wls_reset_settings(WLS_RESET_CAUSE_LOCAL)`); `wls/wls_eeprom.c`
(`wls_eeprom_wipe_config()`).

**Bootmagic/`Esc`-hold is NOT a typing recovery** — it does `eeconfig_disable()`
then `bootloader_jump()`; it enters DFU, it does not resume typing. It works on
the **left half only** (bootmagic.matrix `[1,0]` = the left `Esc`, per the
`nathan` keymap's `rules.mk`); the right half has no keymap route to its own
bootloader at all. Treat it as a fallback of last resort, because it needs
another flash to get back to typing.

### 0.4 Know the DFU entry gesture (both halves)

- **Left half:** remove the spacebar, short the two metal-plated holes where the
  switch feet insert, **then** plug USB-C while still shorting.
- **Right half:** first flip the hidden toggle (exposed by removing the `R_Shift`
  keycap) **down**, then the same spacebar-hole short, then plug USB-C. Flip the
  toggle **back up** afterwards.

Esc-hold (bootmagic) enters DFU on the **left** half only; it does not restore
typing, so it is a fallback of last resort, not a recovery. The right half has
no keymap route to its own bootloader — use the spacebar-hole short above (or
`QK_BOOT`, which sits on the base layer at the **left** half's `Esc` position,
matrix `[1,0]`).

---

## 1. Flash

### 1.1 Left half

Enter DFU on the left half (gesture above), then:

```sh
lsusb | rg -i '342d:dfa0'      # must show the DFU bootloader
./split65.py flash
```

`split65.py flash` calls `doas` and prompts with `input()` — this is a **human**
action. It checks for `wb32-dfu-updater_cli`, verifies DFU is present, flashes
`-t -s 0x08000000 -D <bin>`, then resets with `-R`.

> **Why this is manual, not for the agent:** `split65.py flash` invokes `doas`,
> and an unanswered `doas` prompt locks your account. The agent never runs it.

### 1.2 Right half

Repeat: DFU gesture on the right half (toggle down first), `lsusb` check,
`./split65.py flash`. **Flip the toggle back up.**

### 1.3 Confirm both came back

```sh
lsusb | rg -i '342d'
```

Expected: `342d:e4c6` ("LEO EPOMAKER Split65"). The dongle, if attached, also
reports `342d:e4c6` but with `bcdDevice=20.04` — see §4.

---

## 2. Cold-boot check of the boot-site seeding

**Goal:** prove the firmware boots onto the *switch's own transport*, not the
persisted index.

### 2.1 Test A — switch on USB, cold boot

1. Set the physical switch to **USB**.
2. Unplug and replug the left half's USB-C (a cold start).
3. Read the report:

```sh
python3 host/battery_polybar.py --info
```

**Expected (from source):**

| Field | Value | Why |
| --- | --- | --- |
| `battery` `transport` | `USB` | switch position USB → `hs_mode_switch_pos()` → the transport owner (`wls_transport_decide()` / `hsm_input_rule()`) |
| `host(raw)` | `2` (USB) | `hsm_host_of_devs(DEVS_USB)` = USB. Raw `connection_host_t` USB = 2 (`HOST_NAMES` in `host/battery_polybar.py`) |
| `DIAG: switch=` | `1` (USB) | `hsm_switch_pos_t` USB = 1 |
| `DIAG: devs=` | `0` | `DEVS_USB` = 0 |
| `DIAG: host=` | `2` | the raw host |
| `DIAG: usb_line=` | `1` | the USB data line is up |
| `DIAG: bootcnt=` | **incremented by exactly 1** vs the previous read | `wls_note_boot()` — one per MCU boot |

**The discriminating check:** `bootcnt` must advance by **1** on a clean
replug. If it advances by more, the board is reset-looping (a different fault,
and the reason the counter exists).

### 2.2 Test B — switch on 2.4 GHz, cold boot

1. Set the switch to **2.4 GHz**.
2. Cold-boot the left half (unplug/replug, or toggling the switch then power
   cycling).
3. Read again. Expected: `transport=2.4G`, `host(raw)=4` (2P4GHZ),
   `DIAG: switch=3`, `DIAG: devs=6` (`DEVS_2G4`), `usb_line=0`, `link=` grows
   toward `2` (`CONNECTED`) once the dongle links.

### 2.3 Test C — the transport-switch regression twin (runtime edge)

This is the one that failed on hardware before (`TODO.md` defects 4/5: "switch
to USB does nothing until a reboot"):

1. Boot with the switch on **BT** and no BT host connected (module not
   connected).
2. **Without power-cycling**, flip the switch to **USB**.
3. Type. Expected: **it types over USB**, and `--info` now shows
   `transport=USB`, `usb_line=1`.

Pre-fix this typed nothing until a power cycle. This is the single highest-value
check in the session — it is the fix that has never been hardware-confirmed.

---

## 3. The battery measurement (Tier 1 items 5/6) — the decisive test

**The standing defect:** every `100` ever seen is the module's compile-time init
constant (`module.c` `md_info.bat = 100`). It is written in exactly one place —
`case MD_REV_CMD_BATVOL: md_info.bat = md_rev_payload[1];` — which only fires
when the module answers `MD_SND_CMD_DEVCTRL_INQVOL` (0x53). That send is
**dropped whenever the module send queue is busy** (`smsg_is_busy()`), and on USB
the board pushes two devctrl frames a second, so it is frequently dropped. Only
the **radio** path (`2.4 GHz`) is known to populate it.

### 3.1 On 2.4 GHz, unplugged

1. Switch to **2.4 GHz**, unplug USB (run on battery).
2. Confirm the dongle is live (§4).
3. Pull repeatedly over ~60 s:

```sh
for i in $(seq 1 12); do
  python3 host/battery_polybar.py --info
  echo '---'
  sleep 5
done
```

**What you are looking for:** the level byte (`battery: N%`) changing away from
`100`, and `md state` reading `2` (`CONNECTED`). `--info` prints the formatted
readback including the `DIAG:` line; it does **not** print raw bytes
(`--info` and `--pull` are mutually exclusive — `--pull` prints only the
polybar one-liner). Record the formatted `battery:` line plus the `transport`/
`charge`/`md state` fields for each sample; that is the measurement.

To watch passively instead (the dongle pushes reports without being asked):

```sh
python3 host/battery_polybar.py --listen
```

If the level **never** moves off 100, record that as the result: it means
`INQVOL` is never answered on this module revision, which is itself a finding
(closes off the "just retry harder" fix option and forces the honesty fix).

### 3.2 Confirm `chg` moves `1 -> 2`

Same session, cable in:

1. Stay on **2.4 GHz** (this is also requirement-2 verification, item 8): plug
   USB while the switch is on 2.4 GHz. Expected: **the keyboard stays wireless**
   (it must NOT switch to USB) and the level keeps updating. This is the check
   that failed on the pre-reform build.
2. Watch `charge`: `1` (charging) while charging, then `2` (full) once topped.
   `CHARGE_NAMES = {0: discharging, 1: charging, 2: full}`.

Record both observations in `docs/FINDINGS.md` (the runbook does not — findings
belong in the findings doc).

---

## 4. The 2.4 GHz dongle (unavoidable rider)

**Trigger artifact, not a fault.** The dongle only enumerates once it is powered
*and* the keyboard is actively on the 2.4 GHz link; with the keyboard in 2.4 GHz
mode it enumerates as `342d:e4c6`, exposes the raw-HID collection at
**interface 2**, and round-trips `0xA4` (byte 5 = `0x04`).

```sh
lsusb -d 342d: | rg -i e4c6      # dongle present?
python3 host/battery_polybar.py --info  # prefers the dongle (interface 2) by default
python3 host/battery_polybar.py --info --transport usb   # forces the keyboard's own
```

`--transport` choices are `dongle` | `usb` (`host/battery_polybar.py`). If
`--info` fails to find the dongle, `--transport usb` still reads the keyboard's
own raw HID — use it to prove the keyboard side is alive while the dongle is
being troubleshot.

**Caveat:** both devices share VID:PID `342d:e4c6`. If the dongle does not
enumerate, `--info` may land on the keyboard's interface and report `usb`. The
`transport` byte tells you which side answered: `0x04` = 2.4 GHz (dongle),
`0x01` = USB (keyboard's own).

---

## 5. The USB self-detach instrument (open defect)

**The defect, for context:** the keyboard enumerates fully then drops USB ~1 s
later, cycles separated by multi-minute gaps. Only `wls_usb_connect(false)`
drops the line. It was never root-caused; the original bisect found no
behavioral delta, so the cause is environmental (EEPROM), hardware, or an
undiffed path.

**The instrument:** the `wls_diag` block on the `0xA4` reply at byte 11. Its ten
bytes are, in order (`wls/diag_logic.h`):

| Byte | Field | Meaning |
| --- | --- | --- |
| 11 | `switch_pos` | `0`=UNKNOWN `1`=USB `2`=BT `3`=2.4G |
| 12 | `devs` | `0`=USB `1..5`=BT1..5 `6`=2.4G |
| 13 | `host` | raw `connection_host_t` |
| 14 | `boot_count` | increments once per MCU boot |
| 15 | `usb_line` | 1 if the USB data line is connected |
| 16 | `link_state` | module `MD_STATE_*` (`0` NONE `1` PAIRING `2` CONNECTED `3` DISCONNECTED `4` REJECT) |
| 17 | `pin_c14` | raw `HS_BT_DEF_PIN` level (audits `switch_pos`) |
| 18 | `pin_c15` | raw `HS_2G4_DEF_PIN` level (audits `switch_pos`) |
| 19 | `pin_b9` | raw cable-detect (`SPLIT_HAND_PIN`) level |
| 20 | `reset_cause` | MCU latched `RCC->RSTSTAT` bits, consumed once at boot |

**The disambiguation the old investigation lacked** — read the diag block
*immediately after a detach*:

- **`boot_count` unchanged** across the detach ⇒ the MCU did **not** reset. It
  is a **USB-line drop**, not a reset loop.
- **`boot_count` advanced** ⇒ a reset loop — a different fault entirely.
- **`switch_pos`/`host`/`usb_line` at boot** show what the board *thought* the
  transport was when it tore the line down. If `usb_line=0` while
  `switch_pos=1 (USB)`, the actuator ran when the switch said USB — a logic
  fault in the boot path, not a hardware drop.

**Procedure:**

1. With the switch on USB, watch the enumeration and the diag together:

```sh
# terminal 1
while true; do
  echo "=== $(date +%H:%M:%S) ==="
  lsusb -d 342d: | rg -i e4c6 || echo "(no keyboard)"
  python3 host/battery_polybar.py --info 2>/dev/null || echo "(no reply)"
  sleep 2
done
```

2. Power-cycle the left half and watch. Capture the **last successful reply
   before each drop** — its `bootcnt`, `switch`, and `usb_line` are the data.

3. Record the transition sequence. This is the first real instrument reading on
   this defect; it does not need a root cause in this session, only a recorded
   trace.

---

## 6. Optional in the same session

- **BT bond/connect** (the narrowed open question): use `host/bt_reconnect.py`,
  which does the whole scan→pair→connect against the module's **new random
  address per advertising session** (a stored bond never matches):

  ```sh
  python3 host/bt_reconnect.py --name Split65-2 --scan-secs 20
  ```

  It may still fail at the GATT layer (the module's HID server rejects the
  notification-enabling writes with ATT `0x0E`) — that failure is itself the
  finding.
- **Defect 2 (right-half wake)**: cannot be run as-is — the board will not sleep
  on USB, and a plain idle timeout is deliberately refused. Skip unless you
  drain the pack or accept a scratch threshold bump.

---

## 7. Session log (fill in)

**Session 2026-10-14: the `aec73138…` flash** (walk fixes + byte-order + req-2
reform), left half, switch left on USB then flipped to 2.4 GHz. The board typed
over USB throughout.

| # | Check | Expected | Observed | Verdict |
| --- | --- | --- | --- | --- |
| 0 | Boot code colour: amber renders amber | amber | **amber** | **PASS** — byte order was the cause; closes `HARDWARE.md` |
| 1 | Flash returns as `342d:e4c6` | yes | `342d:e4c6` `mfr=LEO`, dev 060 | PASS |
| 2.1 | Cold boot, switch USB: transport/host/diag | USB / 2 / switch=1, usb_line=1 | USB / 2 / `switch=1 devs=0 host=2 usb_line=1` | PASS |
| 2.1 | `bootcnt` advances by exactly 1 on clean replug | +1 | read `1` before and after | **UNRESOLVED** — see note |
| 2.2 | Cold boot, switch 2.4G | 2.4G / 4 / switch=3, devs=6 | not read cold (switch flipped at runtime) | not run |
| 2.3 | **Runtime BT→USB switch edge types over USB** | types, no power cycle | not run this session | not run |
| 3.1 | 2.4 GHz: real percentage != 100 | a changing value | **blocked** — no dongle enumerates | blocked (tooling) |
| 3.1 | 2.4 GHz: `md state` = CONNECTED | 2 | `md state=0 (NONE)` | blocked (no dongle) |
| 3.2 | Cable in, switch 2.4G: **stays wireless** | yes | **stays wireless** — `0xA4` unanswered, still enumerated | **PASS** — closes req 2; was `host=2 (USB)` pre-reform |
| 3.2 | `charge` moves 1 → 2 | 1 then 2 | `charge=2 (full)` while cabled | partial |
| 4 | Dongle enumerates with keyboard on 2.4G | yes, iface 2 | **no `MILE` device ever** | blocked (tooling) |
| 5 | Self-detach: `bootcnt` unchanged across a drop | unchanged (line drop, not reset) | not run this session | not run |

**Note on 2.1 — `bootcnt`.** Read `1` both before and after the flash. `.bss`/
`.data` do not survive a reset, so an identical value across a flash means either
the counter lives in `.ram0` (which does survive, and would be the intended
design) or it is re-seeded to the same value each boot. One deliberate
power-cycle settles it; it is an instrument question, not a defect.

**Bearing of this session.** Both software fixes waiting on this flash are
**confirmed on hardware**: the boot code renders amber, and a cable with the
switch on 2.4 GHz leaves the board on the radio. The Tier-1 battery measurement
remains **blocked at the tooling level** — no dongle has ever enumerated on this
host, so `3.1`/`4` could not be attempted and the reading stays at the module's
init constant `100`, which is *not* a firmware finding.

Afterwards: record the durable findings in `docs/FINDINGS.md` (battery
semantics, the self-detach trace, the switch-edge confirmation), and update the
`## Status` block in `TODO.md` — but no artifacts/hashes, per that file's own
rule.

---

## Appendix: the code each expected value comes from

| Expectation | Source of truth |
| --- | --- |
| 0xA4 byte indices (level 1, charge 4, transport 5, model 6, host 7, btsub 8, md_ver 9, md_state 10, **diag 11..20**) | `wls/wls.h` `KB_BATTERY_IDX_*` |
| 10-byte diag layout | `wls/diag_logic.h` `wls_diag_t` |
| `transport` byte: `0x01` USB, `0x02` BT, `0x04` 2.4G | `wls/wls.h` `KB_BATTERY_TRANSPORT_*` |
| `switch_pos` 0/1/2/3 = UNKNOWN/USB/BT/2.4G | `wls/diag_logic.h` comment; `WLS_SWITCH_NAMES` in `battery_polybar.py` |
| charge 0/1/2 = discharging/charging/full | `CHARGE_NAMES` in `battery_polybar.py` |
| host raw 0/1/2/3/4 = AUTO/NONE/USB/BLUETOOTH/2P4GHZ | `HOST_NAMES` in `battery_polybar.py` |
| md state 0..4 = NONE/PAIRING/CONNECTED/DISCONNECTED/REJECT | `MD_STATE_NAMES` in `battery_polybar.py` |
| `BATTERY_CAPACITY_LOW` 15, `BATTERY_CAPACITY_STOP` 0 | board `config.h` |
| BT names `Split65-1/2/3` | board `config.h` `MD_BT{n}_NAME` |
| VID:PID `342d:e4c6`, DFU `342d:dfa0` | `split65.py` `KEYBOARD_VID/_PID/_DFU_PID` |
