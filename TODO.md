# TODO

## Status

- Left half: flashed and verified (`--pull` returns `CHG 100%`; firmware shows as
  manufacturer `LEO`, `bcdDevice 0.30` vs stock `MILE` / `0.0b`). **The artifact
  is now 63168 bytes (`f6c0`) after the master-gate fix; the flashed left half is
  one commit behind and should be re-flashed during the right-half session.**
- Right half: **not yet flashed** — enter DFU via the R_Shift toggle +
  spacebar-pin short (see `DEPENDENCIES.md`).
- 2.4 GHz pull path: proven end-to-end with stock firmware; needs a real battery
  report once both halves are on our firmware.
- Bluetooth: not yet probed on hardware.

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
  to both. The previous custom keymap put `QK_BOOT` at Fn layer `[0,0]`.
- Esc-hold (bootmagic) does **not** work on the right half today; that asymmetry
  is why the physical short is currently required.

Plan:

1. Add a `QK_BOOT` binding to a convenient Fn position in
   `qmk_firmware/keyboards/epomaker/epomaker_split65/keymaps/default/keymap.c`.
2. Rebuild and flash both halves.
3. Verify: with the right half connected over USB, press the key and confirm it
   enumerates as `342d:dfa0` (`wb32-dfu-updater_cli -l`).
4. If it works, document the key-based method as primary in `DEPENDENCIES.md` and
   keep the spacebar-pin short as the hardware fallback.

Caveats to confirm empirically:

- The right half must be connected directly to the host over USB when the key is
  pressed (DFU enumerates on the USB port).
- Untested on this board whether the slave half processes `QK_BOOT` while not
  master; expected to work because the jump is local, but verify before relying
  on it.
- Hardware shorting remains the firmware-independent recovery path and must stay
  documented even if the key-based method works.

## Other

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
  See the consolidation note in `FINDINGS.md`.
