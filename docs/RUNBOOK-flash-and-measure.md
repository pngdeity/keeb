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
cheapest place to find a defect is a review, not a flash.

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
- The `0xA4` reply's bytes 23..34 are carried intact — *the encoder is unit-tested;
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
== `0x00`. Pressing the `QK_BOOT` chord (Fn layer, right half `[10,6]`) should,
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

### 0.0.5 (filled in) — the walk-close flash (Tier 1, the deliverable batch)

**This is the working pre-flight for the flash that first carries every fix from
the exhaustive walk, and the first session that attempts the Tier-1 battery
measurement with a clean baseline. Unlike § 0.0.4 it is built from a committed,
signed tree, so the runbook's checklist wording "confirmed clean against HEAD" is
now met.**

**1. The artefact.** `qmk_firmware/.build/epomaker_epomaker_split65_nathan.bin`,
**64,736 bytes** (`text 0 / data 64736 / bss 0`, `fce0`), sha256
`a45a97621963b27ebec5cbf93e2f5091b96a98b10c8e2903b9d1a3ebba9566e1`
(md5 `b8e2131c8d8f35a5da67df8d351e7981`, informational). **Rebuilt fresh from the
committed tree during the pre-flight and byte-identical to the reviewed hash** —
the artefact's identity is the signed submodule hash below, not a working-tree
delta.

- **Submodule `split65-overlay` = `8f381870e4…`, signed (`G`)** — *"fix(wireless):
  correct the defects found by the exhaustive reset-to-steady-state walk"*.
- **Root `main` = the commit that carries this runbook section, signed (`G`)** —
  its gitlink pins the submodule above.
- `git status --short` is **empty in both trees** (verified before writing this).

The board currently runs the **Stage-4** build (`2ec21c44…`, 63.5 KB) — the
previous flash. That build **predates every walk fix**, so any `(5 amber, 5
white)` boot reading taken from it describes the old hand-chosen window, not this
source (see `docs/HARDWARE.md`, "the `(5, 5)` reading").

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
- *A cable with the switch on 2.4 GHz leaves the board wireless* — **source done**
  (`hs_transport_arbitrate_cable()` is a no-op) but **never hardware-confirmed**.

**3. The four review questions.**
- *Does any effect feed back into its own trigger?* **No new feedback loop is
  introduced by the walk.** The one loop-shaped site changed is the split device
  index: `wls_split.c` now clamps the wire value in the pure core **before** it
  can reach `wls_module_devs_change()`, so the index that feeds the transport
  decision cannot echo back a value the transport itself would produce. The
  switch-decode consolidation in `wls.c` removes a second decoder rather than
  adding a consumer.
- *Does every signal have a real value (not a constant, not undefined)?* The
  journal is `b wls_journal` at `0x20004fbc` (16 B, `.ram0`); `wls_reset_cause` is
  `T`; `bootloader_jump` and `enter_bootloader_mode_if_requested` are both strong
  `T`. `KB_BATTERY_IDX_DIAG 11`, `_BOOT_CODE 21`, `_JUMP 23` are all emitted
  (`wls.h`). The three new `_Static_assert`s in `wls_battery.c` and the two
  frame-size asserts in the adapters **compiled in this build**.
- *Which code is even compiled?* `wls.mk` lists all 25 sources including
  `split_logic.c` (the new clamp), `wls_module.c`, `wls_transport.c`,
  `wls_jump_journal.c`, `wls_boot_jump.c`. `KB_BATTERY_IDX_JUMP` is under
  `#ifndef VIA_ENABLE`; VIA is not enabled. `G1`'s `devs` default and `E4`'s clamp
  are both in the compiled path.
- *Measured vs inherited?* Listed in §2: the battery level and the
  cable-plus-2.4GHz behaviour are the two genuinely unmeasured claims this session
  attempts; both have a stated prediction below.

**4. Predicted hardware effect.**
- *After flashing, first cold boot (switch wherever it sits):* the boot LED code
  plays **one full frame** and this time the **amber group renders its true
  count** (panel renders amber as green). Read the pair `(amber, white)` against
  the stage/code rule (amber = stage, 0 = OK; white = code + 1).
- *Switch on USB, cold boot, `python3 host/battery_polybar.py --info`:*
  `transport=USB`, `host(raw)=2`, `DIAG: switch=1`, `DIAG: devs=0`,
  `DIAG: usb_line=1`, `bootcnt` **+1** vs the previous read.
- *2.4 GHz, unplugged, 12 pulls over 60 s:* `battery: N%` **changes away from
  100** and `md state=2` (CONNECTED). If it stays 100 for all twelve samples,
  that is the result: `INQVOL` is never answered on this module revision.
- *Cable in, switch on 2.4 GHz:* the board **stays wireless** (does not switch to
  USB) and the level keeps updating; `charge` reads `1` then `2` as it tops.
- *Runtime BT→USB switch edge (Test C):* with the switch on BT and no host, flip
  to USB **without power-cycling** and type — **it types over USB**, `--info`
  shows `transport=USB`, `usb_line=1`. This is the single highest-value check and
  the fix that has never been hardware-confirmed.

**5. What the build does not explain.** Present and **not** regressions: the `-71
EPROTO` loop; the `342d:e4c6` self-detach (5 enumerations / 5 drops in 5 min, zero
over-current); the pin-lie (`C14`/`C15` readable-but-wrong, which fixes A–D do not
cover); the module's own firmware for BT (Layer 0, no dump/update path). The
`0xA4` reply is **unreachable while the transport is not USB** — the wireless
driver has no `.send_raw_hid` — so the diag/pin block stays silent on 2.4 GHz and
must not be read as a fault.

**6. Non-flashing recovery.** § 0.3: `EE_CLR` (hold Fn + `[7,8]`, then `[11,7]`
for 3 s) re-defaults confinfo to USB; the physical switch to USB then power-cycle;
the spacebar-hole short for DFU. Bootmagic `Esc`-hold is **left-half only** and is
a last resort (it enters DFU, it does not resume typing).

**7. The falsifier.** *Battery still reads exactly 100 after twelve 2.4 GHz
samples with `md state=2`* ⇒ `INQVOL` is unanswered on this revision; the
"default 100" is the module's constant and the honesty fix (defect 1) becomes the
only path — the retry-harder option is closed. *The board switches to USB when a
cable is inserted with the switch on 2.4 GHz* ⇒ `hs_transport_arbitrate_cable()`
is not the only cable consumer and requirement 2 is unmet. *A `(N, 5)` reading
with `N != 7` and a plausible stage* ⇒ the boot-code counts disagree with the
source, reopening the instrument question with the walk's fixes in place. *The
board drops USB while the switch says USB* ⇒ the self-detach path, unchanged by
this build; read the diag block for `bootcnt`/`usb_line` at the drop.

**8. Verify the artefact on disk** matches `a45a9762…` (§ 0.2) before flashing;
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
| `EE_CLR` (hold 3 s) | **hold Fn + the top-right corner key** (`[7,8]`, the base `Mute` position) to arm the `_RST` layer, then — still holding — press the **right half's bottom-right corner** (`[11,7]`, the base `Right` position) and hold 3 s | wipes EEPROM → confinfo re-defaults → back to USB |
| Physical mode switch → USB | flip to the USB position, then **power-cycle** | the switch is only level-authoritative **at boot** on this build's switch-edge path; a flip *after* boot also works via the fixed switch-edge code, but a power cycle is the certain form |
| Spacebar-hole short | `docs/HARDWARE.md` | DFU, for reflashing |

**The arming key is not optional.** Fn alone reaches `_FL`, whose bottom-right
corner is `Home` — harmless, but not the reset. `EE_CLR` lives on `_RST`, which
is reachable *only* by holding `[7,8]` with Fn. Both corners are involved:
`[7,8]` arms, `[11,7]` fires. Sources: the `nathan` keymap's `keymap.md` §5;
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
| `battery` `transport` | `USB` | switch position USB → `hs_mode_switch_pos()` → `apply_switch_transport()` |
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
   (it must NOT switch to USB) and the level keeps updating.
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

**The instrument:** the `wls_diag` block on the `0xA4` reply at byte 11. Its six
bytes are, in order (`wls/diag_logic.h`):

| Byte | Field | Meaning |
| --- | --- | --- |
| 11 | `switch_pos` | `0`=UNKNOWN `1`=USB `2`=BT `3`=2.4G |
| 12 | `devs` | `0`=USB `1..5`=BT1..5 `6`=2.4G |
| 13 | `host` | raw `connection_host_t` |
| 14 | `boot_count` | increments once per MCU boot |
| 15 | `usb_line` | 1 if the USB data line is connected |
| 16 | `link_state` | module `MD_STATE_*` (`0` NONE `1` PAIRING `2` CONNECTED `3` DISCONNECTED `4` REJECT) |

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

| # | Check | Expected | Observed | Verdict |
| --- | --- | --- | --- | --- |
| 1 | Both halves flash, both return as `342d:e4c6` | yes | | |
| 2.1 | Cold boot, switch USB: transport/host/diag | USB / 2 / switch=1, usb_line=1 | | |
| 2.1 | `bootcnt` advances by exactly 1 on clean replug | +1 | | |
| 2.2 | Cold boot, switch 2.4G | 2.4G / 4 / switch=3, devs=6 | | |
| 2.3 | **Runtime BT→USB switch edge types over USB** | types, no power cycle | | |
| 3.1 | 2.4 GHz: real percentage != 100 | a changing value | | |
| 3.1 | 2.4 GHz: `md state` = CONNECTED | 2 | | |
| 3.2 | Cable in, switch 2.4G: stays wireless, level updates | yes | | |
| 3.2 | `charge` moves 1 → 2 | 1 then 2 | | |
| 4 | Dongle enumerates with keyboard on 2.4G | yes, iface 2 | | |
| 5 | Self-detach: `bootcnt` unchanged across a drop | unchanged (line drop, not reset) | | |

Afterwards: record the durable findings in `docs/FINDINGS.md` (battery
semantics, the self-detach trace, the switch-edge confirmation), and update the
`## Status` block in `TODO.md` — but no artifacts/hashes, per that file's own
rule.

---

## Appendix: the code each expected value comes from

| Expectation | Source of truth |
| --- | --- |
| 0xA4 byte indices (level 1, charge 4, transport 5, model 6, host 7, btsub 8, md_ver 9, md_state 10, **diag 11..16**) | `wls/wls.h` `KB_BATTERY_IDX_*` |
| 6-byte diag layout | `wls/diag_logic.h` `wls_diag_t` |
| `transport` byte: `0x01` USB, `0x02` BT, `0x04` 2.4G | `wls/wls.h` `KB_BATTERY_TRANSPORT_*` |
| `switch_pos` 0/1/2/3 = UNKNOWN/USB/BT/2.4G | `wls/diag_logic.h` comment; `WLS_SWITCH_NAMES` in `battery_polybar.py` |
| charge 0/1/2 = discharging/charging/full | `CHARGE_NAMES` in `battery_polybar.py` |
| host raw 0/1/2/3/4 = AUTO/NONE/USB/BLUETOOTH/2P4GHZ | `HOST_NAMES` in `battery_polybar.py` |
| md state 0..4 = NONE/PAIRING/CONNECTED/DISCONNECTED/REJECT | `MD_STATE_NAMES` in `battery_polybar.py` |
| `BATTERY_CAPACITY_LOW` 15, `BATTERY_CAPACITY_STOP` 0 | board `config.h` |
| BT names `Split65-1/2/3` | board `config.h` `MD_BT{n}_NAME` |
| VID:PID `342d:e4c6`, DFU `342d:dfa0` | `split65.py` `KEYBOARD_VID/_PID/_DFU_PID` |
