# TODO

## Status

- **The tree holds our battery firmware, committed inside the `qmk_firmware`
  submodule.** `qmk_firmware/` is a **pinned submodule** of
  `pngdeity/cleave-keeb` branch `split65-overlay` (pinned at vendor revision
  `580665f777` plus our commits `e8f49af339` "feat: battery over raw HID",
  `641fd27392` "correct bootmagic matrix and readme", `01528d1c5d` "add info.json
  url and readme hardware link", and `059cd8bdf1` "math.py Python 3.12+"). The
  board source therefore **contains the battery responder** (`wls/wls_battery.c`)
  and the corrected `bootmagic.matrix [1,0]`.
- The personal `nathan` keymap is **not** in the tree: it lives in the sibling
  userspace repo `../keeb-userspace/`. Build with `./bin/make ...:nathan`
  (`bin/make` supplies `QMK_USERSPACE`).
- **Current build artifacts** (host toolchain `arm-none-eabi-gcc` 16.2.0):
  `nathan` = **64932 bytes (`fda4`), md5 `0e3f05d2cc2d9a398b3244222eb72e94`**;
  `default` = **63160 bytes (`f6b8`), md5 `4f24953fa88acf14afe2107eb9ea9dba`**.
  (CI builds with the container's gcc 15.2.0, so its bytes differ — CI asserts
  "it builds", not a fixed md5.)
- Both halves enumerate as `342d:e4c6`, manufacturer `LEO` (stock is `MILE`).
- **The halves have NOT been reflashed with the current build.** They run an
  older `nathan` build (63168 bytes md5 `3d0d47d9737c4209d2a7000cb8909033`), so
  the tree and the hardware disagree. Reflashing is Tier 1 item 3.
- Right-half DFU entry uses the R_Shift toggle + spacebar-pin short (see
  `docs/HARDWARE.md`). Key-based DFU is still future work (a section below).
- **The prune was discarded and the canonical tree restored.** `qmk_firmware/` is
  a submodule again (the earlier flatten/prune/`layouts`+`lib/lufa` casualties are
  resolved by P0). Both repos are pushed and CI is green. Device context and
  vocabulary: `docs/DEVICE.md`.

## Priority order

Ordered by what unblocks what. Rationale and detail for each item follow in the
sections below.

**Tier 0 — blockers / one-way doors (do first, cheap, affect everything after):**

1. ~~**Fix defect 3** (`find_raw_hid_interface()` picks the wrong interface) and
   **contain it in `split65.py check`.**~~ **DONE** — `find_raw_hid_interface()`
   now prefers the dongle (interface 2) and accepts `--transport usb`;
   `split65.py check` reports the collections present. A confirmation run with
   the dongle attached remains (it needs the dongle and the user).
2. **Decide and apply the critical ergonomics changes** (a pull-forward from
   Tier 3, abbreviated to only the items that are cheap and that a flash would
   otherwise force you to repeat):
  - **`QK_BOOT` / `EE_CLR` placement.** `EE_CLR` sitting at the Backspace
    position on the Fn layer is a genuine footgun (an accidental hold wipes
    settings). Move it somewhere deliberate. One-line change, and it must be in
    the same flash as everything else.
   - **Decide the battery-indicator question.** With a uniform white fill the
     indicator is the only LED that differs; decide whether that single-LED
     exception stays, is made more prominent (it is the only per-half charge
     readout), or is disabled — and do it now, because it is the same
     `config.h`/keymap edit and the same flash.
   - **Decide whether to trim the compiled-in animation list**
     (`keyboard.json` `rgb_matrix.animations`, ~44 entries, still reachable via
     `RGB_MOD`). If trimming, it must be before the flash.
   The rest of the UX audit (layer ergonomics, mode-switch discoverability,
   legends) stays in Tier 3 — it needs thought, not a flash.

**Tier 1 — the deliverable (the project exists for this):**

3. **Reflash both halves** with the current build. Cheap, and it gives a clean
   baseline for the measurement below. Do it *after* all the cheap pre-flash
   decisions are in, so the flash is done once.
4. **2.4 GHz: capture a real percentage** (the decisive test; needs the user at
   the keyboard). Depends on 1 and 3.
5. **2.4 GHz: confirm `chg` moves `1 -> 2` while charging.** Same session as 4.
6. **Decide and implement the honesty fix for the fake 100** (defect 1).
   Depends on 4 — you need to know what a real reading looks like before choosing
   how to represent "unknown".

**Tier 2 — feature completeness (in scope, not yet probed):**

7. **Probe Bluetooth at all**, then update `docs/PROTOCOL.md` and `README.md`.
   Independent of Tier 1 except that it wants a fixed host tool (1).
8. **Wireless-while-charging investigation** (`## Other`). Independent; needs
   hardware and the user.

**Tier 3 — quality / ergonomics (valuable, not blocking):**

9. **Firmware unit tests** for the pure battery helpers. Best done after 4/6 so
   the tests encode settled semantics, not the current fake-100 behaviour.
10. **Key-based right-half DFU.** Removes the case-opening procedure. Only worth
    doing if the physical short is a real pain point; the short stays documented
    as the recovery path regardless.
11. **The rest of the UX / usability review** (whole section below) — layer
    ergonomics, held-modifier comfort, mode-switch discoverability, legends.
    Largest, most subjective; depends on 6 and 9 for what is even possible.

**Tier 4 — long-horizon, high-cost, low-urgency:**

12. **Re-base onto newer upstream QMK.** See `## Other`; invalidates all hardware
    verification and would re-do 4–5. Do not start before Tier 1 is closed.

**Dependency notes (why the order is not free):**

- 1 blocks 4/5/7 (interface selection is the read path).
- 3 must come after 2 so the flash is done once, and before 4 so a mid-measurement
  reflash cannot invalidate the result.
- 2 must precede 3: every one of those decisions changes bytes that get flashed.
- 12 invalidates 4–6, so it must come last or not at all.

## Outstanding verification (the deliverable is not yet proven)

The host can read a report, but **no real battery percentage has ever been
observed**. Until the items below are done, treat every displayed value as
unverified.

- [ ] **Fix defect 3** (`find_raw_hid_interface()` picks the wrong interface) and
      cover it in `split65.py check`. **Do this before measuring** — it is the
      read path, and with keyboard and dongle both attached the probe would
      otherwise read the keyboard's USB interface.
- [ ] **Flash both halves with the current build** and confirm the manufacturer
      string is `LEO` and the `0xA4` responder answers. Left via Esc-hold, right
      via the toggle + spacebar-pin short; see `docs/HARDWARE.md`.
- [ ] **2.4 GHz: capture a real percentage.** Every `100` seen so far is the
      module's compile-time init constant (defect 1). The radio path is the only
      transport known to populate `md_info.bat`, so this is where the first real
      number must come from. Record the observed value and raw bytes in
      `docs/FINDINGS.md`.
- [ ] **2.4 GHz: confirm the value changes while charging.** Re-run the probe with
      a cable in and watch `chg` go `1` -> `2` (full).
- [ ] **USB: decide and implement the honesty fix for the fake 100** (defect 1).
      The report must not claim `100%` when the value was never refreshed.
- [ ] **Bluetooth: probe the transport at all.** Unknown whether the BT link
      exposes the raw HID collection (`0xFF60`/`0x61`) and whether `*md_getp_bat()`
      is populated over BT. If raw HID is absent, the BLE Battery Service
      (`0x180F`/`0x2A19`) fallback in `host/battery_polybar.py` is the path.
      Pairing is interactive, so the user must run `bluetoothctl`. **Update
      `docs/PROTOCOL.md`** and `README.md` once known.

### Unmeasured device facts (fill into `docs/DEVICE.md`)

`docs/DEVICE.md` was written from `keyboard.json` and the product photographs.
These facts are **not yet proven** and must be measured before the doc claims
them:

- [ ] **Which of `P2`/`P3` on the right half is the host data port vs the charge
      port.** Firmware has one cable-detect pin (`A7`) and cannot tell them
      apart; the roles in `DEVICE.md` are provisional.
- [ ] **Confirm the current master/slave assignment** with the cable in the right
      half's `P2` — record which half reports as master.
- [ ] **Stock (`MILE`) factory configuration**: default layer, lighting, and
      keymap as shipped. Unverified; `DEVICE.md` "Stock vs ours" marks these
      unknown.
- [ ] **Physical form of the mode switch** — confirm the three glyph-to-position
      mapping against the actual unit.
- [ ] **Layout count check**: re-derive key count (69) and row widths
      (15/15/14/14/11) from `keyboard.json` and confirm `DEVICE.md` matches.

## Defects found on hardware (pre-existing vendor issues, not regressions)

### 1. USB report always says 100%

`md_info.bat` is initialised to `100` at compile time
(`qmk_firmware/keyboards/linker/wireless/module.c:72-77`) and is written in
exactly one place, `case MD_REV_CMD_BATVOL: md_info.bat = md_rev_payload[1];`
(`module.c:220-222`). The keyboard has no ADC: it can only learn the level by
asking the wireless module (`md_inquire_bat()` ->
`MD_SND_CMD_DEVCTRL_INQVOL` 0x53). That call silently gives up whenever the
module send queue is non-empty — `smsg.c:115-122 smsg_is_busy()`. On USB,
`housekeeping_task_user()` (`epomaker_split65.c:1257-1260`) pushes two devctrl
frames every second, so the queue is frequently busy and `INQVOL` is dropped.
Result: the report shows the never-updated init `100`, and the vendor's own soft
indicator also shows a full-looking colour while on USB regardless of true level.

Fix options (not yet chosen): have `kb_battery_percent()` return a sentinel
meaning "unknown" instead of a fake 100 when the value has never been refreshed,
and/or retry `md_inquire_bat()` more aggressively.

### 2. The right (slave) half cannot be woken by its own keys

Documented vendor behaviour, confirmed in source:

- `lpwr_exti_init()` (`keyboards/linker/wireless/lpwr_wb32.c:68-112`) arms the
  matrix row/col lines as edge events before `WB32_STOP_MODE`, and the callback
  (`lpwr_wb32.c:34-56`) maps them to `LPWR_WAKEUP_MATRIX`.
- The board's `lpwr_stop_hook_pre()` (`wls.c:191-201`) arms the wake cause as
  `LPWR_WAKEUP_UART`, and `lpwr_stop_hook_post()` (`wls.c:204-216`) only accepts
  `LPWR_WAKEUP_USB` and `LPWR_WAKEUP_CABLE`. Any other cause (including
  `MATRIX` from a keypress) falls to `default:` and returns straight to
  `LPWR_STOP`.
- The mode-switch and cable events that *are* accepted are set in
  `palcallback_cb()` (`wls.c:168-185`), and the switch lines are only armed on
  the master (`if (is_keyboard_master())`, `wls.c:112/:124/:134`).

**Wake the right half by:** toggling its 2.4 GHz/BT mode switch, or unplugging and
replugging its USB cable. Keys will not do it; that is by design (the master
wakes the slave over the inter-half UART).

### 3. Host tooling picks the wrong raw HID interface

`host/battery_polybar.py:find_raw_hid_interface()` used to return the first
`hid.enumerate()` entry matching usage page `0xFF60` / usage `0x61`. When both the
keyboard's own USB interface (interface 1) and the 2.4 GHz dongle (interface 2)
are attached, it grabbed the keyboard's USB interface, so the module reported USB
while the user was on 2.4 GHz.

**Fixed.** `find_raw_hid_interface(prefer=...)` now enumerates all matching
collections and prefers interface 2 (the dongle) by default, falling back to the
only collection present when just one exists; `--transport usb` selects the
keyboard's own collection. `split65.py check` gained a "Raw HID interface
selection" step that lists the collections found and warns when more than one is
present. Remaining: a hardware run with the dongle attached to confirm the
2.4 GHz read is not silently satisfied by USB.

## Right-half DFU without hardware shorting

Goal: let the right half enter the WB32 DFU bootloader by holding a key, like the
left half, instead of opening the case and shorting the spacebar switch pins
(remove `R_Shift`, toggle the hidden switch, short the two holes where the
spacebar switch feet insert, plug USB-C).

Rationale / evidence:

- `QK_BOOT` is handled in the application firmware at
  `qmk_firmware/keyboards/epomaker/epomaker_split65/epomaker_split65.c:1059`:
  it calls `eeconfig_disable()` then `bootloader_jump()`. `bootloader_jump()` is
  a **local MCU operation** and the handler is **not** gated on
  `is_keyboard_master()`, so a `QK_BOOT` key pressed on the right half should jump
  *that half* into its own bootloader.
- Both halves run identical firmware, so adding `QK_BOOT` to the keymap adds it
  to both. The keymap maps `QK_BOOT` on the **base** layer at the left half's
  `Esc` position (matrix `[1,0]`).
- Esc-hold (bootmagic) does **not** work on the right half today; that asymmetry
  is why the physical short is currently required.

Plan:

1. Add a `QK_BOOT` binding to a convenient Fn position in
   `qmk_firmware/keyboards/epomaker/epomaker_split65/keymaps/default/keymap.c`.
2. Rebuild and flash both halves.
3. Verify: with the right half connected over USB, press the key and confirm it
   enumerates as `342d:dfa0` (`wb32-dfu-updater_cli -l`).
4. If it works, document the key-based method as primary in `docs/DEPENDENCIES.md` and
   keep the spacebar-pin short as the hardware fallback.

Caveats to confirm empirically:

- The right half must be connected directly to the host over USB when the key is
  pressed (DFU enumerates on the USB port).
- **Cold-plug requirement:** the WB32 bootloader samples the boot pin only at
  reset, so the jump must land the half in DFU during a fresh enumeration. A
  `QK_BOOT` press on a sleeping slave may not enumerate; if the half does not
  appear as `342d:dfa0`, unplug and replug it (or fall back to the short).
- Untested on this board whether the slave half processes `QK_BOOT` while not
  master; expected to work because the jump is local, but verify before relying
  on it.
- Hardware shorting remains the firmware-independent recovery path and must stay
  documented even if the key-based method works.

## User experience / usability review of the keyboard mappings

The mappings and indicators are inherited from the vendor and were designed for
the stock firmware; they have never been reviewed against how this keyboard is
actually used. Audit and question each of the following, then decide what (if
anything) to change in the `nathan` keymap (userspace repo — see Status) and
whether the vendor defaults deserve an upstream report.

Three of these were pulled forward into **Tier 0, item 2** because they are
cheap and must land in the same flash as other pre-flash decisions: the
`QK_BOOT`/`EE_CLR` placement, the battery-indicator-vs-fill decision, and whether
to trim the compiled-in animation list. The remainder stay here.

- **Charging/battery LED placement.** The only per-half-charge renderer is the
  master-only soft indicator at `HS_MATRIX_BAT_SOFT_INDEX 64` (right half, bottom
  row, `[11,5]`, fourth from the right). Question whether that is discoverable at
  all: it sits on the *opposite* half from the half it describes, is master-only,
  and is invisible when RGB brightness is zero. Consider a better location or a
  dedicated indicator, and whether the level colours are distinguishable.
- **Default RGB effects.** Partly addressed: the vendor rainbow is gone; the
  default is now solid white at 50%, declared in `keyboard.json`
  (`rgb_matrix.default`) with the keymaps re-applying it persistently in
  `keyboard_post_init_user()`. Open questions remain: the effects are still
  compiled in and reachable via `RGB_MOD`, the stock wave drains battery, and the
  soft battery indicator blends into the fill rather than overriding it. Decide
  whether to review/trim the enabled animation list
  (`keyboard.json` `rgb_matrix.animations`, ~44 entries) and whether the battery
  indicator should override the fill.
- **Battery indicator vs solid fill.** With a uniform white fill, the battery
  indicator is the only thing that breaks it (one LED on the right half shows the
  charge colour). Decide whether that single-LED exception is wanted, and whether
  it should be more prominent given it is the only per-half charge readout.
- **Connection-mode switching.** `KC_BT1`/`KC_BT2`/`KC_BT3`/`KC_2G4` (Fn layer,
  row 1) and the physical mode switch both exist. Question the discoverability of
  the keycodes, whether the currently-selected channel is visible, and whether
  the switch-and-keys interaction is coherent.
- **Keycap legends vs matrix.** Legends do not reliably match matrix positions
  (see `docs/HARDWARE.md`), so any mapping work must identify keys positionally
  ("right half, bottom row, fourth from the right"), never by legend.
- **`QK_BOOT` / `EE_CLR` placement.** `QK_BOOT` sits on the **base** layer at the
  left `Esc` position (matrix `[1,0]`) and `EE_CLR` on the Fn layer over the
  `Bksp` position (right half, matrix `[7,7]`). Both are easy to hit by accident;
  question whether destructive actions are placed safely, especially given
  `EE_CLR` sits on the Backspace key position.
- **Layers and ergonomics.** `_FL` is reached by holding right Spacebar
  (`LT(_FL, KC_SPC)`); `_MBL`/`_MFL` are the Mac variants. Question reachability,
  whether the held-modifier arrangement is comfortable, and whether the Mac/PC
  split is worth the complexity.
- **Battery-related keycodes.** `KC_BATQ` is disabled on USB
  (`confinfo.devs == DEVS_USB`) and only blinks when level <= 15, so it is nearly
  useless as a query key. Question whether it should report a real level instead
  (ties into the `md_info.bat` staleness defect above).

Deliverable: a reviewed mapping with a written rationale for every deviation
from the vendor default. Record findings here and in `docs/FINDINGS.md`.

## Other

- **Wireless while charging: can the two coexist?** Source reading is
  inconclusive. The physical three-position switch appears authoritative
  (`hs_modeio_detection()` in `wls/wls.c` reads it every scan and forces
  `DEVS_USB` when in the USB position; `wls_process_long_press()` makes the
  `KC_BT*`/`KC_2G4` keycodes no-ops unless the switch already reports
  BT/wireless). Nothing found gates wireless operation on `charging_state`, so
  plugging a cable with the switch on BT/2.4 GHz *should* leave the keyboard
  wireless while charging — but this is unverified on hardware, and the
  cable-insert auto-switch in `housekeeping_task_user()` (a policy choice, not a
  hardware limit) deliberately moves to USB on cable insert, which would defeat
  it. Also unknown whether VBUS presence disturbs the module UART or the radio
  link. Investigate: with the switch on 2.4 GHz, plug a charging cable and
  confirm the keyboard stays wireless and the level still updates; decide
  whether the cable-insert auto-switch should be suppressed while the switch is
  in a wireless position. Document the verdict in `docs/HARDWARE.md`.

- Firmware unit tests for the pure battery helpers (`kb_battery_percent`,
  `kb_charging_state`, `kb_transport_byte`) — deferred pending the hardware probe.
- Bluetooth transport: confirm whether the BT link exposes the raw HID
  collection (`0xFF60`/`0x61`) and whether `*md_getp_bat()` is populated over BT;
  BLE Battery Service `0x180F`/`0x2A19` is the host fallback.
- Consider re-basing onto a newer upstream QMK. This tree is a 1-commit
  squashed vendor snapshot (`hangshengkeji/qmk_firmware` `tri-mode`,
  2026-01-20); a full-history upstream tree (`qmk/qmk_firmware` master) is
  ~4.5 months newer but lacks the wireless stack. Any re-base would require
  rebuilding, re-flashing **and** re-verifying the battery work on hardware.
  See the consolidation note in `docs/FINDINGS.md`.
