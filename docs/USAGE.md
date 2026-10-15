# Using the keyboard

A guide for **using** the EPOMAKER Split65 running our firmware — not for
changing the firmware. If you are months away from this project and want to
change something about how the keyboard behaves *at the desk*, this is the file
to read. All facts here are taken from the shipped `nathan` keymap and the board
source; where a value lives in code it is named so you can find it.

Audience: the person typing. For how the firmware is built, see `README.md` and
`docs/`.

> **This file describes what the keyboard does. What it *must* do — the
> user-facing requirements, and the effects a person must be able to infer from
> the board — is `docs/UX-REQUIREMENTS.md`.** Where this guide and the
> requirements differ, the requirements state the intended behaviour and this
> file either follows or is behind. The LED *instrument* contract (a debugging
> channel, not a user message) is `docs/INDICATORS.md`.

> **Which keymap?** Two keymaps exist: `default` (the vendor layout, in the
> `qmk_firmware` submodule) and `nathan` (the personal layout, in the sibling
> `keeb-userspace` repo). This guide describes **`nathan`**, which is the keymap
> the halves run. `keymap.md` in `keeb-userspace/.../keymaps/nathan/` is the
> byte-level companion to this file.

---

## 1. The layers

A *layer* is a parallel keymap; you are always on exactly one. A *layer key*
switches which one while held (or, for `TO()`, makes it the standing default).

| # | Layer | How you get there | Sticky? |
|---|---|---|---|
| 0 | `_BL` — base (Windows) | default; nothing held | — |
| 1 | `_FL` — Fn (Windows) | **hold the RIGHT spacebar** | no (momentary) |
| 2 | `_MBL` — Mac base | **Fn + `S`** | yes (survives reboot) |
| 3 | `_MFL` — Mac Fn | **hold the RIGHT spacebar** while on `_MBL` | no |
| 4 | `_RST` — recovery | **hold Fn + the top-right corner key** | no |

**Fn is on the RIGHT spacebar only** (`nathan` base layer: left space `[5,5]` is
plain `KC_SPC`; right space `[11,1]` is `LT(_FL, KC_SPC)`). Tap the right space =
space; hold it = Fn. Holding the **left** space does **not** engage Fn — it types
space, so e.g. left-space + `Q` yields a literal `q`, not `KC_BT1`. (An earlier
version of this guide said "either spacebar"; that was wrong.)

`TO(_MBL)` and `TO(_BL)` are *sticky*: they change the standing default layer
and the choice is stored in EEPROM, so it survives a power cycle. To go back to
Windows from Mac, press **Fn + `A`** (the switch sits on a different key each
way; `A` and `S` keep typing normally otherwise).

**VIA / live remapping is not enabled.** The board does not enable QMK's
dynamic-keymap (VIA) feature (`features.command` is `false`), so there is no live
over-USB remapping. A VIA definition JSON ships in `host/` for reference, but the
firmware does not serve the raw-HID configuration collection VIA needs. Changing
a layer means editing the keymap and reflashing — see `README.md`.

---

## 2. Backlight (RGB) — how to change it

The keyboard has a per-key RGB matrix over a solid-white default (hue 0, sat 0,
value 128). Backlight is changed with the Fn-layer RGB keys below — **not** the
knob by default (the knob is volume on the base layer and brightness on Fn; see
§7).

### From the Fn layer

Hold the **right** spacebar, then:

| Key (Fn layer) | Effect |
|---|---|
| `RGB⏻` (`RM_TOGG`) | toggle backlight on/off |
| `Hue-` / `Hue+` (`RM_HUED`/`RM_HUEU`) | change colour |
| `Sat-` / `Sat+` (`RM_SATD`/`RM_SATU`) | colour saturation |
| `B+` / `B-` (`RM_VALU`/`RM_VALD`) | brightness up / down |
| `Spd-` / `Spd+` (`RM_SPDD`/`RM_SPDU`) | effect speed |
| `RGB⇄` (`RM_NEXT`) | next lighting effect |

The backlight brightness/speed keys are on the **right** side of the Fn layer;
`Spd-` is on the left half (`[5,2]`), `Spd+` on the right half (`[11,3]`). The
safe toggles (`RGB⏻`, `NKRO`, `GUI⏻`) each appear **twice** — once bottom-right
and once on the left half — so either hand can reach them.

### Effects available

Ten effects are compiled in: `solid_color`, `solid_reactive`,
`solid_reactive_wide`, `breathing`, `cycle_left_right`, `cycle_up_down`,
`digital_rain`, `rainbow_moving_chevron`, `raindrops`, `typing_heatmap`. Cycle
with `RGB⇄` / `RM_NEXT`.

### What is saved

Brightness, hue, saturation, effect, and speed are **saved to EEPROM** — they
survive a power cycle. The only exception is the boot default: every time the
keyboard powers on, the firmware re-applies solid white at half brightness
(`keyboard_post_init_user()`, using the `*_noeeprom` calls so it is not written
back). Your in-session changes override it until the next power-on.

---

## 3. Battery

- **Battery check — hold Fn and press `BatQ`** (on the Fn layer, right half matrix
  `[11,1]`, the right-spacebar column). It lights the number keys `1`…`0` to show
  the percentage. It is **master-only** (the left half answers).
- **Charge indicator LED** — one LED on the right half's bottom row
  (matrix `[11,4]`): its colour is a pure function of `(charging, full, level)`
  (`wls_bat_colour_of()`): **green when charging *and* full**, **blue while
  charging**, and when not charging green at ≥50%, orange at ≥30%, red below.
  It also blinks red at a low level.
- **Which half has the battery?** Only the **left** half. The right half is
  powered over the link cable.
- **Charging:** a single USB-C cable into **either** half charges the keyboard;
  both halves are powered from either port.

> **Known caveat (over USB):** the reported percentage is currently the
> firmware's compile-time default of `100` whenever the link is USB, because the
> wireless module does not answer the level query on USB. A real number appears
> only over 2.4 GHz. See `TODO.md` defect 1.

---

## 4. Wireless

There is a physical **mode switch** on the **right half** (the same plate as its
`P3` port — see `DEVICE.md`); it is the single control for which radio is active.
Note it lives on the right half even though the *master* is normally the left
half — do not read "master" as "left" (see `DEVICE.md`'s naming rule).

| Want | Do |
|---|---|
| USB (wired) | switch to the USB position and plug in |
| 2.4 GHz dongle | switch to the 2.4 GHz position; plug the dongle into the host |
| Bluetooth | switch to the BT position |

On the Fn layer (hold the **right** spacebar):

- **`BT1` / `BT2` / `BT3`** (`Fn` + `2`/`3`/`4`) — pair or switch Bluetooth
  device 1/2/3. (Hold for the long-press re-pair/reset behaviour.)
- **`2.4G`** (`Fn` + `5`) — select the 2.4 GHz dongle.

Mode selection belongs to the **physical switch**; a cable plugged in while the
switch is on 2.4 GHz or BT leaves the keyboard on that wireless link.

---

## 5. Sleep and waking

- The keyboard has a low-power sleep. On an idle timeout the **master (left)**
  half decides to sleep; the slave's wake sources arm at that moment. The idle
  timeout is **30 minutes**; the backlight dims off earlier, after **5 minutes**.
- **To wake it, press a key**, or move the mode switch, or plug/unplug a cable.
- The backlight goes off in low-power mode and comes back on wake (it returns at
  your saved brightness).

---

## 6. Recovery — the two destructive keys

These are the only keys that destroy saved state. They are deliberately
separated so a single fumble cannot hit both.

> This recovery layer exists in the **`nathan`** keymap only. The vendor
> `default` keymap has no `_RST` layer; do not expect these chords on stock
> firmware.

> **Transport is chosen by the switch, not by stored state.** The mode keys
> (`Fn`+`2`/`3`/`4` = BT 1/2/3, `Fn`+`5` = 2.4 GHz) select *which host within the
> switch's position* — they persist only the BT sub-slot (`confinfo.last_btdevs`),
> which the firmware consults **only when the switch reads BT**, and only to pick
> among BT1..5. The physical switch is authoritative: see
> `wls/transport_logic.c` `hsm_input_rule()`. So flipping the switch to USB
> recovers a stuck wireless session — the cable is a *power* fact and never
> forces USB (engineering requirement 2).
>
> There is one case where nothing in the firmware can type: a wireless mode whose
> link is not up, with no cable. The board is then alive and correctly on the
> radio, but has nothing to talk to. The recovery is the switch, the cable, or
> re-pairing — and `EE_CLR` clears all persisted state if the stored BT sub-slot
> is wrong. (Hold Esc at plug-in does **not** help — bootmagic enters the
> bootloader rather than clearing settings.)

| Combo | Effect |
|---|---|
| **Fn + top-right corner key, tapped** | nothing (the recovery layer is hold-only) |
| **Fn + top-right corner key (hold), then bottom-right corner** | `EE_CLR` — **factory reset**: wipes the emulated EEPROM (default layer, RGB settings, key overrides) |
| **Fn + top-right corner key, tapped alone** | `QK_BOOT` — enter the `wb32-dfu` bootloader for flashing |

- The recovery layer is armed only by a **hold** of Fn + the top-right corner key
  (the base-layer `Mute` key, matrix `[7,8]`). `EE_CLR` sits on the right half's
  bottom-right corner (matrix `[11,8]`) — the far corner, reachable only with a
  held Fn chord from the left hand plus a press on the opposite half.
- **`QK_BOOT`** (enter the bootloader) is on the **Fn** layer at the Fn-layer
  top-right corner key, matrix `[10,4]`. It is **not** on the base layer, so a
  stray `Esc` tap cannot drop a half into the bootloader.
- **Bootmagic is enabled, and `Esc`-hold at plug-in enters the bootloader.** The
  `nathan` keymap sets `BOOTMAGIC_ENABLE = yes` with `bootmagic.matrix` `[1,0]`
  (the left half's `Esc` position), so holding `Esc` while plugging in the left
  half enters its `wb32-dfu` bootloader. It is a *flashing* route, not a settings
  reset — `EE_CLR` is the reset (above). The right half has no keyboard route to
  its own bootloader; use `QK_BOOT` or the hardware short (below).

**If a half drops into the bootloader**, flash it or power-cycle it — it comes
back. Note the two halves are flashed **separately**, and **neither half needs
its case opened**: both enter DFU by shorting the two metal-plated holes under
the spacebar while plugging in USB-C (the right half also needs its hidden
toggle — exposed by removing the `R_Shift` keycap — flipped **down** first, and
back **up** afterwards). See
`docs/HARDWARE.md`.

---

## 7. Everyday keys and shortcuts

- **Shift + Esc** = `~`; **GUI/Cmd + Esc** = `` ` ``; **Shift + Backspace** =
  Delete (key overrides).
- **Fn + number row = F1–F12**, done in firmware (works on any OS and in the
  BIOS).
- **`Flip`** on the Fn layer (left half) swaps the Fn-row and the number row
  (OEM behaviour); the left Ctrl LED lights red while it is on.
- **Encoder** — the knob sends **volume up/down on the base and Mac base
  layers**, and **backlight brightness** on the Fn layers. The `encoder_map[]` in
  the keymap is compiled in (`ENCODER_MAP_ENABLE = yes` in the `nathan` keymap's
  `rules.mk`): base/Mac = `KC_VOLD`/`KC_VOLU`, Fn/MacFn = `RM_VALD`/`RM_VALU`
  (`RM_VALD` on CCW, `RM_VALU` on CW — matching the "B-" = down, "B+" = up
  convention on the Fn-layer RGB keys).

---

## 8. Where to change things you cannot change at the desk

Anything not reachable by a key above is a firmware change:

| Want to change | Where |
|---|---|
| A key's function, layers | `keeb-userspace/.../keymaps/nathan/keymap.c` |
| Backlight default colour/brightness | `keymap.c` `keyboard_post_init_user()` and `keyboard.json` `rgb_matrix.default` |
| Which effects are compiled in | `keyboard.json` `rgb_matrix.animations` |
| Enable VIA / live remapping | `keyboard.json` features + a VIA definition (not currently enabled) |
| Sleep timings, wireless behaviour | board `wls/`, `wireless/` — see `docs/FINDINGS.md` |

Rebuild and flash per `README.md` (`./bin/make epomaker/epomaker_split65:nathan`)
and `docs/HARDWARE.md` (flashing).
