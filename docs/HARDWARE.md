# Hardware reference — EPOMAKER Split65

Physical and electrical facts established by measuring the real hardware. These
are **not** derivable from the source tree, so they are recorded here to avoid
re-discovering them. What the device *is* and how to name its parts is in
`DEVICE.md`; source-derived behaviour is in `FINDINGS.md`; the wire format is
`PROTOCOL.md`; live status and open work are in `TODO.md`.

Terminology: `left half` / `right half` name physical position (operator's point
of view); `master half` / `slave half` name the firmware role. See
`DEVICE.md` "Nomenclature". This file uses the role word only where the
behaviour is a role behaviour (e.g. "only the master answers").

## USB identities

| Device | VID:PID | Mode | Manufacturer string | Product string |
|---|---|---|---|---|
| Left half (`LEO`) | `342d:e4c6` | application | `LEO` | `EPOMAKER Split65` |
| Right half (`LEO`) | `342d:e4c6` | application | `LEO` | `EPOMAKER Split65` |
| 2.4 GHz dongle | `342d:e4c6` | application | `MILE` | `2.4G Dongle` |
| Any half | `342d:dfa0` | WB32 DFU bootloader | `Westberry Tech.` | `WB Device in DFU Mode` |

- The keyboard and the dongle share the **same VID:PID** (`342d:e4c6`). They are
  distinguishable only by the manufacturer/product string and by which
  interfaces they expose.
- `bcdDevice` for this firmware is `0.3.0` (`keyboard.json` `usb.device_version`,
  reported `0.30`); stock firmware reported `0.0b` with manufacturer `MILE`.
- **Manufacturer string is the quickest "is our firmware on it" check:** `LEO` =
  ours, `MILE` = stock.
- The bootloader is at `342d:dfa0` in both halves.

## Battery indicator LED

One LED, on the **right half** bottom row. Its index is into
`keyboard.json`'s `rgb_matrix.layout` (68 LEDs).

| Constant | Index | Matrix | Position | Role |
|---|---|---|---|---|
| `HS_MATRIX_BLINK_INDEX_BAT` | 63 | `[11,4]` | 4th from the right | Charging/full colour, and periodic blink at level `<= 15` |

- Drawn by `bat_indicators()` on the **master half only**, even though the LED is
  physically on the right half.
- Behaviour (vendor `default`): while charging, red; while charging *and* full,
  green; while discharging at `<= BATTERY_CAPACITY_LOW` (15), a red blink every
  `250 ms`; at `<= BATTERY_CAPACITY_STOP` (0) it also lowers the sleep timeout.
- The red/green charging colours are drawn only while a battery query is active
  (`im_bat_req_charging_flag`, set by `KC_BATQ`); they are not continuously
  shown.
- This is **not a level display**: no key and no LED renders a percentage bar.
- The tree **additionally** carries our own always-on "soft" indicator: two
  adjacent right-half bottom-row LEDs at indices 64 and 65 (`[11,5]`/`[11,6]`,
  `HS_MATRIX_BAT_SOFT_INDEX`/`HS_MATRIX_BAT_SOFT_INDEX2`) drawn at full channel
  intensity, alongside the vendor `bat_indicators()` behaviour above. Colours:
  green ≥50 %, amber ≥30 %, red ≤15 %, green while charging-to-full, blue while
  charging. It is part of the battery work committed in the submodule (see
  `TODO.md`).

## Raw HID interfaces

- Usage page `0xFF60`, usage `0x61`, `RAW_EPSIZE` = **32 bytes** in both
  directions, on all transports.
- **A raw HID write through hidapi must be 33 bytes**: a leading Report ID `0x00`
  followed by the 32-byte report. The descriptor declares **no report IDs**, but
  hidapi still requires the leading byte. A bare 32-byte write is silently
  accepted and never answered.
- Each half exposes three interfaces; the raw collection is **interface 1** on a
  half and **interface 2** on the dongle. With both attached, selecting by usage
  page alone picks the wrong one (see `TODO.md` defect 3).

## Split-link power

- **The inter-half link carries power.** A single USB-C cable into *either* half
  charges the whole keyboard, so both halves do not need to be plugged in.
- Confirmed by the master's `charging_state` (A7) reading true with no cable in
  the master's own port — only the slave half's cable and the inter-half link.
- Consequence: `charging_state` is effectively a shared "power present" bit, not
  a per-half cable-detection bit.

## Batteries

- **Only one half carries a battery.** Observed directly with the right half's
  backplate removed: the **right half has no battery**. The battery is therefore
  in the **left half** (the half that is currently master). This supersedes the
  earlier firmware-inferred guess that both halves had cells.
- **Quirk, not a defect: the firmware models per-half charge state that the
  right half cannot have.** Both halves run identical firmware, so the right
  half still reads a local `BAT_FULL_PIN` (A15) and keeps a `bat_full_flag`
  whose value is meaningless on a battery-less half. This is harmless: every
  consumer is either master-gated (`bat_indicators()` returns early when not
  master) or link-powered, and the `0xA4` report carries only the master's own
  module value, so no phantom value can reach a host. Do **not** add a
  right-half special case — the guard would be dead code over a value nothing
  reads.
- **Open:** whether the right half has any charging circuitry at all, or is
  purely bus/link powered. Record it when known.
- **The inter-half link carries power** (`## Split-link power` below), so a cable
  into **either** half reaches both PCBs. That is a power distribution fact, not
  evidence of two cells.
- **Reporting is the battery half's level.** The master (currently the left /
  battery-bearing half) answers `0xA4` with its own module's value. One battery,
  one reported number; there is no second cell whose level could differ.

## Charging and battery sensing

- There is **no ADC and no charge-controller telemetry**. The firmware cannot
  measure voltage, current, or charge; it reads two GPIO bits only.
- `HS_BAT_CABLE_PIN` = A7 = "USB insertion detection pin" (power present).
- `BAT_FULL_PIN` = A15, active-high (`BAT_FULL_STATE 1`) = the FULL line.
- The keyboard cannot measure its own charge; the level only ever arrives from
  the wireless module over the module UART (`MD_REV_CMD_BATVOL` `0x5C`).
- On USB the module does not answer the level inquiry, so `md_info.bat` keeps its
  compile-time init of `100` (see `TODO.md` defect 1).

## Halves and handedness

- Both halves run **identical firmware**; there is no left/right build variant.
  Handedness is a physical pin (`split.handedness.pin` = B9). QMK **core** derives
  the master from the USB role (`usb_bus_detected()`), but this board **overrides
  `is_keyboard_master()`** to `readPin(SPLIT_HAND_PIN)` — so on this firmware the
  pin determines the role too, and the two questions coincide. Removing that
  override would restore the core USB-role semantics.
- The **left half is currently the master** and the **right half the slave**,
  joined by the link cable. Role is pin-determined, not positional; see
  `DEVICE.md` "Nomenclature".
- Only the master answers the battery raw HID command; a pull addressed to the
  slave never gets a reply.

## DFU entry

- **Left half (master):** hold **Esc** while plugging in USB (bootmagic; this also
  erases EEPROM settings, which is expected). The physical reset switch also works.
- **RIGHT half — the case must be opened.** Esc-hold does **not** work, and there
  is no keymap route into the right half's own bootloader (the `nathan` Fn-layer
  `QK_BOOT` at `[10,4]` is on the Fn layer; the WB32 bootloader samples the boot
  pin only at reset, so a warm keypress may not enumerate). Use the
  firmware-independent route: open the case, remove `R_Shift`, flip the hidden
  toggle switch, remove the spacebar, short the two holes where the spacebar
  switch's plastic feet insert, then plug in USB-C **while still shorting**.
  Restore the toggle and keycaps afterwards.
- The WB32 bootloader samples the boot pin **only at reset**, and powering the
  board *is* the reset. Short first, plug second, hold the short until
  enumeration completes. Bridging an already-powered board does nothing.
- DFU therefore requires a **cold plug**: the reset and the enumeration window
  must coincide. A warm entry (a keypress on an already-powered half, or jumping
  from a sleeping slave) may not enumerate; if the device does not appear as
  `342d:dfa0`, unplug and replug it.
- A marginal cable or port shows up as an EPROTO (`-71`) storm in the kernel log
  (`device descriptor read/64, error -71`), not as a clean failure. Retry on a
  different port/cable.
- The bootloader lives at `0x1FFFE000`, outside the 128 KB application region
  written at `0x08000000`, so a normal flash cannot damage it.

## Sleep and wake

- The right (slave) half **is woken by its own keys in the current tree**: the
  board-local `wireless/lpwr_wb32.c` arms the right half's `MATRIX_ROW_PINS_RIGHT`
  and `lpwr_stop_hook_post()` accepts `LPWR_WAKEUP_MATRIX` and `LPWR_WAKEUP_SWITCH`.
  **Not yet verified on hardware** — the halves have not been reflashed with this
  build (see `TODO.md` defect 2). Until a flash confirms it, waking the right half
  still relies on toggling its 2.4 GHz/BT mode switch or replugging its USB cable.
- The master wakes the slave over the inter-half UART, which *is* an accepted
  cause.
- The deep-sleep entry/exit path (`PRE_LP()`/`POST_LP()` in `lpwr_wb32.c`) is a
  pair of raw-Thumb `uint32_t[]` blobs. They are fully deobfuscated — ANCTL write
  unlock, a trim-field clamp/sync, and a short analog-settling loop — in
  `FINDINGS.md` "the deep-sleep `PRE_LP()`/`POST_LP()` blobs are raw Thumb".

## Keycaps vs matrix

- Keycap legends do **not** reliably match the matrix positions, so physical key
  identification on this unit must be positional: "right half, matrix `[11,4]`".
  Never identify a key by its legend. See `DEVICE.md` "Nomenclature".

## Flash targeting

- Flashing requires **wired USB**. 2.4 GHz and Bluetooth cannot flash.
- `wb32-dfu-updater_cli -t -s 0x08000000 -D <bin>` then `wb32-dfu-updater_cli -R`.
- Required udev rules (both in `/etc/udev/rules.d/`):
  - `50-qmk-wb32.rules`: `SUBSYSTEMS=="usb", ATTRS{idVendor}=="342d", ATTRS{idProduct}=="dfa0", TAG+="uaccess"`
  - `50-epomaker-split65.rules`: `KERNEL=="hidraw*", SUBSYSTEM=="hidraw", ATTRS{idVendor}=="342d", ATTRS{idProduct}=="e4c6", MODE="0660", TAG+="uaccess"`
