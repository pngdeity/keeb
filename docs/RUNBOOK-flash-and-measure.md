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

### 0.1 Confirm what you are about to flash

```sh
cd /home/nathan/repos/pngdeity/incubating/keeb
git --no-pager log --format='%h %G? %s' -1
git -C qmk_firmware --no-pager log --format='%h %G? %s' -1
md5sum qmk_firmware/epomaker_epomaker_split65_nathan.bin
```

Expected: root `c73e380` and submodule `7d984b781a`, both `G` (signed). The md5
is informational only — record it in the session log so a later build can be
told apart. Do **not** write it into `TODO.md` (it goes stale on every edit).

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
| `EE_CLR` (hold 3 s) | `_RST` layer, right-half bottom-right corner (`[11,7]`) while holding the Fn chord | wipes EEPROM → confinfo re-defaults → back to USB |
| Physical mode switch → USB | flip to the USB position, then **power-cycle** | the switch is only level-authoritative **at boot** on this build's switch-edge path; a flip *after* boot also works via the fixed switch-edge code, but a power cycle is the certain form |
| Spacebar-hole short | `docs/HARDWARE.md` | DFU, for reflashing |

**Bootmagic is NOT a recovery route** — it does `eeconfig_disable()` then
`bootloader_jump()`; it enters DFU, it does not resume typing.

### 0.4 Know the DFU entry gesture (both halves)

- **Left half:** remove the spacebar, short the two metal-plated holes where the
  switch feet insert, **then** plug USB-C while still shorting.
- **Right half:** first flip the hidden toggle (exposed by removing the `R_Shift`
  keycap) **down**, then the same spacebar-hole short, then plug USB-C. Flip the
  toggle **back up** afterwards.

Esc-hold / bootmagic is broken on our build on both halves — do not rely on it.

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

### 2.3 Test C — the defect-7 regression twin (runtime edge)

This is the one that failed on hardware before (`TODO.md` defect 5/7: "switch
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
