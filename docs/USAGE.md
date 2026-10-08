# Using the keyboard

A guide for **using** the EPOMAKER Split65 running our firmware — not for
changing the firmware. If you are months away from this project and want to
change something about how the keyboard behaves *at the desk*, this is the file
to read. All facts here are taken from the shipped `nathan` keymap and the board
source; where a value lives in code it is named so you can find it.

Audience: the person typing. For how the firmware is built, see `README.md` and
`docs/`.

> **Which keymap?** Two keymaps exist: `default` (the vendor layout, in the
> `qmk_firmware` submodule) and `nathan` (the personal layout, in the sibling
> `keeb-userspace` repo). This guide describes **`nathan`**, which is what the
> halves are flashed with. `keymap.md` in
> `keeb-userspace/.../keymaps/nathan/` is the byte-level companion to this file.

---

## 1. The layers

A *layer* is a parallel keymap; you are always on exactly one. A *layer key*
switches which one while held (or, for `TO()`, makes it the standing default).

| # | Layer | How you get there | Sticky? |
|---|---|---|---|
| 0 | `_BL` — base (Windows) | default; nothing held | — |
| 1 | `_FL` — Fn (Windows) | **hold either spacebar** | no (momentary) |
| 2 | `_MBL` — Mac base | **Fn + `S`** | yes (survives reboot) |
| 3 | `_MFL` — Mac Fn | **hold either spacebar** while on `_MBL` | no |
| 4 | `_RST` — recovery | **hold Fn + the top-right corner key** | no |

**Fn is on both spacebars.** Tap a spacebar = space; hold it = Fn. Either hand
can engage the layer.

`TO(_MBL)` and `TO(_BL)` are *sticky*: they change the standing default layer
and the choice is stored in EEPROM, so it survives a power cycle. To go back to
Windows from Mac, press **Fn + `A`** (the switch sits on a different key each
way; `A` and `S` keep typing normally otherwise).

**VIA / live remapping is not available.** The board does not enable QMK's
dynamic-keymap (VIA) feature (`features.command` is `false` and there is no VIA
definition), so there is no host program that can change the layers over USB.
Changing a layer means editing the keymap and reflashing — see `README.md`.

---

## 2. Backlight (RGB) — how to change it

The keyboard has a per-key RGB matrix over a solid-white default (hue 0, sat 0,
value 128). There are two easy controls and a set of keycode adjustments.

### Easiest: the volume knob

The rotary knob is on the **right half**, top-right corner (turn only, no click).

| Layer | Turn |
|---|---|
| base (`_BL` / `_MBL`) | volume down / up |
| Fn (`_FL` / `_MFL`) | **backlight brightness** down / up |

So: **to dim or brighten the backlight, hold a spacebar (Fn) and turn the knob.**

### From the Fn layer

Hold a spacebar, then:

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

- **Battery check — hold Fn and press `BatQ`** (bottom row of the right half,
  the position under the left spacebar, matrix `[11,1]`). It lights the number
  keys `1`…`0` to show the percentage. It is **master-only** (the left half
  answers).
- **Charge indicator LED** — one LED on the right half's bottom row
  (matrix `[11,4]`): it blinks red when the battery is **low** and shows charge
  colour while charging (green while charging, red when charging *and* full).
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

There is a physical **mode switch** on the left half; it is the single control
for which radio is active.

| Want | Do |
|---|---|
| USB (wired) | switch to the USB position and plug in |
| 2.4 GHz dongle | switch to the 2.4 GHz position; plug the dongle into the host |
| Bluetooth | switch to the BT position |

On the Fn layer (hold a spacebar):

- **`BT1` / `BT2` / `BT3`** (`Fn` + `Q`/`W`/`E`) — pair or switch Bluetooth
  device 1/2/3. (Hold for the long-press re-pair/reset behaviour.)
- **`2.4G`** (`Fn` + `R`) — select the 2.4 GHz dongle.

Mode selection belongs to the **physical switch**; a cable plugged in while the
switch is on 2.4 GHz or BT leaves the keyboard on that wireless link.

---

## 5. Sleep and waking

- The keyboard has a low-power sleep. On an idle timeout the **master (left)**
  half decides to sleep; the slave's wake sources arm at that moment.
- **To wake it, press a key**, or move the mode switch, or plug/unplug a cable.
- The backlight goes off in low-power mode and comes back on wake (it returns at
  your saved brightness).

---

## 6. Recovery — the two destructive keys

These are the only keys that destroy saved state. They are deliberately
separated so a single fumble cannot hit both.

| Combo | Effect |
|---|---|
| **Fn + top-right corner key, tapped** | nothing (the recovery layer is hold-only) |
| **Fn + top-right corner key (hold), then bottom-right corner** | `EE_CLR` — **factory reset**: wipes the emulated EEPROM (default layer, RGB settings, key overrides) |
| **`Esc` held at plug-in** (left half) | enter the `wb32-dfu` bootloader for flashing; **also clears EEPROM** |

- The recovery layer is armed only by a **hold** of Fn + the top-right corner key
  (the base-layer `Mute` key, matrix `[7,8]`). `EE_CLR` sits on the right half's
  bottom-right corner (matrix `[11,7]`) — the far corner, reachable only with a
  held Fn chord from the left hand plus a press on the opposite half.
- **`QK_BOOT`** (enter the bootloader) is on the **Fn** layer at the right half's
  third row (matrix `[10,4]`).

**If a half drops into the bootloader**, flash it or power-cycle it — it comes
back. Note the two halves are flashed **separately**, and **neither half needs
its case opened**: both enter DFU by shorting the two metal-plated holes under
the spacebar while plugging in USB-C (the right half also needs its hidden
toggle flipped first, exposed by removing the `R_Shift` keycap). See
`docs/HARDWARE.md`.

---

## 7. Everyday keys and shortcuts

- **Shift + Esc** = `~`; **GUI/Cmd + Esc** = `` ` ``; **Shift + Backspace** =
  Delete (key overrides).
- **Fn + number row = F1–F12**, done in firmware (works on any OS and in the
  BIOS).
- **`Flip`** on the Fn layer (left half) swaps the Fn-row and the number row
  (OEM behaviour); the left Ctrl LED lights red while it is on.
- **Encoder** on the base layer = volume; on Fn = backlight brightness.

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
