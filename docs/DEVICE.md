# Device reference — EPOMAKER Split65

What this device **is**: its construction, layout, controls, modes, accessories,
and the vocabulary used to refer to all of it. Read this before any capture or
firmware work so that "the top row", "the master", or "the USB port" cannot be
misread.

Ownership of facts across this project:

| Document | Answers |
|---|---|
| `DEVICE.md` (this file) | What and where the device is; how to name its parts. |
| `HARDWARE.md` | Measured electrical and pin facts (USB IDs, GPIOs, DFU, power). |
| `PROTOCOL.md` | The `0xA4` wire format. |
| `FINDINGS.md` | Why the design is shaped the way it is. |
| `TODO.md` | Live status, outstanding work, defects. |

Where a fact could belong to two documents, it lives in one and is linked, not
copied.

## Identity

| | |
|---|---|
| Make / model | EPOMAKER Split65 |
| Form factor | 65% split, 69 keys, 5 physical rows |
| MCU | WB32FQ95 (Artery WB32, Cortex-M3) |
| Bootloader | `wb32-dfu` @ `342d:dfa0` |
| Application VID:PID | `342d:e4c6` (shared by both halves and the dongle) |
| Manufacturer string (our firmware) | `LEO` |
| Manufacturer string (stock firmware) | `MILE` |
| Connectivity | USB-C (wired), 2.4 GHz (dongle), Bluetooth |
| Lighting | per-key RGB, WS2812 over SPI (`B15`), 68 LEDs |
| Inputs besides keys | one rotary encoder ("volume knob") on the right half |

Physical/electrical detail for each of these is in `HARDWARE.md`.

## Nomenclature

Unambiguous vocabulary for referring to the hardware. Use these terms exactly.

### Halves: position vs role are separate axes

- **`left half`** / **`right half`** — **physical position from the operator's
  point of view**, as seated at the keyboard. This is fixed by geometry and is
  the primary identifier for *where* something is. `left half` is the half on
  the operator's left.
- **`master half`** / **`slave half`** — **firmware role**, assigned at runtime.
  The master owns the USB HID device, runs the battery raw HID responder, and
  forwards the slave's matrix; the slave forwards its matrix to the master.
  Role is determined by the handedness pin (`split.handedness.pin` = B9). On this
  board the firmware **overrides `is_keyboard_master()`** to read that pin, so it
  is set by hardware/jumper; QMK core instead derives the role from the USB cable
  (`usb_bus_detected()`), so removing the override would change the semantics.

**Rule: use the side for location, the role for behaviour.** Never write "master"
to mean "left" or vice versa.

> Current observation (not a definition): the **left half is currently the
> master** and the **right half the slave**, as reported by `is_keyboard_master()`
> on the wired half. If the halves were reassembled with swapped handedness this
> would invert while left/right stayed put.

### The three USB-C ports

Name every port by side **and** function. Never say "the USB port".

| Name | Half | Faces | Role |
|---|---|---|---|
| `P1 left-half host USB-C` | left | rear edge | The wired-**host** data port. |
| `P2 left-half charge USB-C` | left | rear edge | The second left-half port. |
| `P3 right-half USB-C` | right | rear edge, at the mode-switch plate | The right half's only port. |

Firmware caveat: there is **one** cable-detect pin (`HS_BAT_CABLE_PIN` = A7), so
on the **left** half the firmware does **not** distinguish `P1` from `P2`. The
distinction above is physical and by intended role, taken from the product
photographs; treat the exact role split as provisional until confirmed (see
`TODO.md`).

The inter-half **link cable** joins the two halves and also carries power (see
`HARDWARE.md` "Split-link power"); it uses the right half's sole port (`P3`).

### Mode switch

`mode switch` — the 3-position knurled slide switch, recessed in a metal plate on
the **rear edge of the right half**. Positions are named after the silk glyph
printed beneath each:

| Position | Glyph | Selects |
|---|---|---|
| `USB position` | monitor/display | Wired USB host. |
| `2.4 GHz position` | device-in-cradle | The 2.4 GHz dongle. |
| `Bluetooth position` | Bluetooth rune | Bluetooth. |

Refer to it as "the mode switch, set to the 2.4 GHz position". It is photographed
in the middle (`2.4 GHz`) position. Firmware reads it via
`hs_modeio_detection()` → `modeio_mode { hs_none, hs_usb, hs_bt, hs_2g4,
hs_wireless }` (`keyboards/linker/wireless/wls/wls.h`).

### Switches and keys

**Canonical form: `<half>, matrix [row,col]`** — for example, "the switch at
right half, matrix `[11,4]`". This is the only form that is unambiguous on this
unit, because the keycap legends have been moved and do not reliably match
matrix positions.

- `[row,col]` is a QMK matrix coordinate. **The columns are per-half**: the left
  half has 7 real columns (`C0 C1 C2 C3 A6 B10 B11`) and the right half 9
  (`B12 B13 B14 C6 C7 C8 C9 C4 C5`); rows `A0 A1 A2 A3 A4 C13` are shared.
  Rows 1-5 are the left half and rows 7-11 the right half; row 6 is unused.
  Therefore the same `[row,col]` names a different physical pin depending on the
  half — **always state the half**.
- Legend-only references ("the Fn key", "the fourth key on the top row") are
  **not acceptable** on their own. If a legend is used, pair it with the
  coordinate.

Common reference points:

| Matrix | Half | Layer-0 legend | Physical position |
|---|---|---|---|
| `[5,5]` | left | `KC_SPC` | left spacebar (3u) |
| `[11,1]` | right | `KC_SPC` | right spacebar (3u) |
| `[11,3]` | right | `KC_RALT` | 1st key right of the right spacebar |
| `[11,4]` | right | `MO(_FL)` (`Fn`) | 2nd key right of the right spacebar |
| `[11,5]` | right | `KC_RCTL` | 3rd key right of the right spacebar |
| `[11,6]` | right | `KC_LEFT` | 4th key right of the right spacebar |
| `[11,7]` | right | `KC_DOWN` | 5th key right of the right spacebar |
| `[11,8]` | right | `KC_RGHT` | 6th key right of the right spacebar |
| `[3,1]` | left | `KC_A` | `Fn`+this = `TO(_MBL)`, switches the default layer to Mac |

The full coordinate table is generated from `keyboard.json` (see "Physical
layout").

### Legends and key parts

- **`printed legend`** — what is moulded/printed on the keycap. Not authoritative
  for function on this unit.
- **`layer-0 legend`** — what the key does on the base layer (as declared in the
  keymap).
- **`keycap`**, **`switch`** (the mechanical switch under the cap), **`position`**
  (the physical location, identified by matrix coordinate).

Where these disagree, the matrix coordinate wins.

### Other parts

- **`volume knob`** — the rotary encoder on the **right half**, top-right corner
  (encoder `pin_a B7`, `pin_b B6`). Not a switch.
- **`per-key LED`** — one of the 68 WS2812 LEDs; indices are into
  `keyboard.json` `rgb_matrix.layout`.
- **`battery indicator LED`** — one specific per-key LED on the right half's
  bottom row; see `HARDWARE.md` for its index and colours.
- **`plate`** — the recessed metal fitting on the rear of the right half that
  holds the mode switch and `P3`.

## Physical layout

69 keys in 5 physical rows: **15 / 15 / 14 / 14 / 11**.

```
row 0  (15): [1,0][1,1][1,2][1,3][1,4][1,5][1,6] | [7,0][7,1][7,2][7,3][7,4][7,5]  [7,7]   [7,8]
row 1  (15): [2,0] [2,1][2,2][2,3][2,4][2,5]   | [8,0][8,1][8,2][8,3][8,4][8,5][8,6]  [8,7] [8,8]
row 2  (14): [3,0] [3,1][3,2][3,3][3,4][3,5]   | [9,0][9,1][9,2][9,3][9,4][9,5]  [9,7]     [9,8]
row 3  (14): [4,0]  [4,1][4,2][4,3][4,4][4,5]  | [10,0][10,1][10,2][10,3][10,4] [10,6] [10,7] [10,8]
row 4  (11): [5,0][5,1][5,2]  [5,5]            | [11,1]  [11,3][11,4][11,5][11,6][11,7] [11,8]
                 left half (rows 1-5)              right half (rows 7-11)
```

- Row widths and coordinates are generated from `keyboard.json`
  `layouts.LAYOUT`, which is the **authoritative** source; if this table and
  `keyboard.json` ever disagree, `keyboard.json` is correct and this table is
  stale. Verify with the count check in `TODO.md`.
- Several keys are wider than 1u (left `Shift` 2.25u, right `Shift` 1.75u,
  `Backspace`/`Enter`/right space 2-3u, `Tab`/`Caps` 1.5-1.75u); widths are in
  `keyboard.json` (`w` fields), not repeated here.
- A photograph of the assembled board is at `docs/assets/split65-overview.jpg`.

## Ports and controls

Rear-edge photograph: `docs/assets/split65-rear-ports.webp`.

Reading that photograph left to right:

1. **Left half** rear: `P1 left-half host USB-C`.
2. **Left half** rear: `P2 left-half charge USB-C`.
3. **Plate**: the 3-position `mode switch`, photographed in the `2.4 GHz`
   position, with the `USB`, `2.4 GHz` and `Bluetooth` glyphs beneath it.
4. **Right half** rear: `P3 right-half USB-C`, at the plate.

Not visible from the rear: the per-key LEDs (under the keycaps), the `volume
knob` (top-right of the right half), the inter-half link cable.

The left half has two ports (`P1`, `P2`); the right half has one (`P3`) — see
"Nomenclature" for the firmware caveat that `P1` and `P2` are not
distinguishable to the firmware.

## Modes of operation

Selected by the `mode switch`; the active mode is reported by firmware as
`modeio_mode`:

| Mode | Switch position | Host sees the keyboard as | Flashing |
|---|---|---|---|
| Wired USB | `USB position` | A `342d:e4c6` USB HID device. | Yes (wired only). |
| 2.4 GHz | `2.4 GHz position` | A `342d:e4c6` HID device via the dongle. | No. |
| Bluetooth | `Bluetooth position` | A Bluetooth HID device. | No. |

- Which half is the USB/host-facing side depends on the role, not the side (see
  "Nomenclature").
- The keys that switch transport at runtime: `KC_BT1`, `KC_BT2`, `KC_BT3`,
  `KC_2G4` — but these are gated on the mode switch, so the physical switch is
  authoritative. They are on the Fn layer (see `DEPENDENCIES.md`).
- Flashing requires wired USB in both halves; 2.4 GHz and Bluetooth cannot flash
  (see `HARDWARE.md` "Flash targeting").

## Accessories

### 2.4 GHz dongle

| | |
|---|---|
| VID:PID | `342d:e4c6` (same as the keyboard) |
| Manufacturer string | `MILE` |
| Product string | `2.4G Dongle` |
| HID interfaces | 3 (keyboard/mouse/consumer/system/LEDs; a 120-key bitmap; the raw HID tunnel) |
| Raw HID tunnel | usage page `0xFF60`, usage `0x61`, 32-byte IN/OUT — the same collection QMK exposes |

- The dongle and the keyboard share a VID:PID, so they are told apart only by the
  manufacturer/product string and by their interfaces. A raw HID write addressed
  by usage page alone can therefore hit the wrong device (see `TODO.md` defect 3).
- Dongle firmware is **not** in the QMK tree and is not required for this work
  (see `FINDINGS.md` "Dongle recon").

### Inter-half link cable

Connects the two halves (`P3` on the right half); carries both data and power.
A single USB-C cable into **either** half charges the whole keyboard, so
`charging_state` is a shared power-present bit, not per-half (see `HARDWARE.md`
"Split-link power").

## Stock vs ours

Two columns, with only source- or measurement-proven entries filled. Anything
unproven is marked, not guessed.

| Property | Stock (`MILE`) | Our firmware (`LEO`) | Proven? |
|---|---|---|---|
| Manufacturer string | `MILE` | `LEO` | Measured |
| VID:PID | `342d:e4c6` | `342d:e4c6` | Measured |
| Battery raw HID `0xA4` | absent | present (master only), committed in the tree | Source |
| Default lighting | vendor rainbow (`cycle_left_right`, speed 135, val 150) | solid white 0/0/128 (set in `keyboard.json`; re-applied in `keyboard_post_init_user()`) | Source (tree) |
| Default layer at first boot | unknown | unknown (persisted in EEPROM) | **Unverified** |
| Keymap / layers as shipped | unknown | vendor `default` keymap in the tree; `nathan` in the userspace repo | **Unverified** for stock |

Notes:

- The tree holds the vendor board **plus the battery feature** (`wls/wls_battery.c`,
  `0xA4` responder, solid-white default). The personal `nathan` keymap is **not**
  in the tree — it is in the sibling userspace repo `../keeb-userspace/`. State
  which firmware a half runs by its manufacturer string (`LEO` = ours, `MILE` =
  stock); the halves currently run an older `nathan` build.
- The default layer is **persisted in EEPROM** and survives power cycles and
  reflashes; a board can therefore be on a past operator's chosen default layer.

## Host machine

| | |
|---|---|
| Host | Lenovo ThinkPad T480 |
| OS | Arch Linux |
| Internal keyboard | six-row keyboard (it is the **laptop**, not the Split65) |
| Display integration | polybar module (`host/battery_polybar.py`) |

- The host's own keyboard is a **six-row** laptop keyboard. Do not confuse its
  row count with the Split65's five rows when reasoning about captures.
- The host sees two keyboards at once (its own and the Split65) plus, when
  present, the dongle — which shares the Split65's VID:PID. Interface selection
  by usage page alone is therefore ambiguous; see `TODO.md` defect 3 and
  `FINDINGS.md` "Dongle recon".

## Immutable vs mutable

| Immutable (hardware / pin-defined) | Mutable (firmware / EEPROM) |
|---|---|
| 69 keys, 5 rows, physical row widths | Keymap: base, `_FL`, `_MBL`, `_MFL` layers |
| Matrix pins and per-half column maps | Custom keycodes (`KC_BT1`..`KC_BATQ`; `MOR_1..MOR_5` are declared but unused) mapping |
| Handedness pin (`B9`) | Default layer selection (`set_single_persistent_default_layer`) |
| `HS_BAT_CABLE_PIN` (`A7`), `BAT_FULL_PIN` (`A15`) | RGB default animation / brightness |
| Encoder pins (`B7`,`B6`), WS2812 pin (`B15`) | `confinfo.filp` (Cmd/Alt swap) |
| USB VID:PID `342d:e4c6` / bootloader `342d:dfa0` | EEPROM contents (wear-levelled, SPI flash) |
| `mode switch` (physical position) | Runtime transport (`KC_BT1/2/3`, `KC_2G4`) |

The `mode switch` is physical, but the *selection* it implies is read and acted
on by firmware, so a mode change is partly a firmware behaviour.
