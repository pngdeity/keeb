# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Battery reporting over Raw HID command `0xA4` (`KC_GET_BATTERY_LEVEL`),
  returning percentage, charging state, and active transport; documented in
  `docs/PROTOCOL.md`.
- Firmware responder `wls/wls_battery.c` implementing a strong
  `raw_hid_receive()` override, master-half only.
- 2.4 GHz push mode (`kb_battery_push_task()`) as a fallback to host pull.
- Host polybar module `host/battery_polybar.py` with `--pull`, `--listen`, and
  `--bluetooth` (BLE Battery Service `0x180F`/`0x2A19`) modes.
- Build/flash/diagnostics helper `split65.py`.
- VIA keyboard definition `host/epomaker-split65-via.json`.
- Build wrappers `bin/make` and `bin/qmk`, and a userspace repo for the personal
  `nathan` keymap (sibling `../keeb-userspace/`).
- CI (`.github/workflows/build.yml`) building `epomaker/epomaker_split65:all` in
  QMK's official container, plus whitespace and canonical-`keyboard.json` checks.

### Fixed

- **Deep sleep on the split.** A board-local copy of the wireless stack
  (`keyboards/epomaker/epomaker_split65/wireless/`, ported from carlosedp's fix)
  sizes the wake pin arrays to the per-half matrix, arms the right half's own
  matrix pins, uses falling-edge events (matching `ROW2COL`), stops arming the
  UART-RX wake (the module's own traffic was defeating the 30-minute sleep), and
  accepts `SWITCH`/`MATRIX` wake causes. Scoped to this board; no shared file is
  touched. Awaiting a hardware keypress-wake test.
- Host tool now prefers the 2.4 GHz dongle's raw HID interface (interface 2) and
  exposes `--transport usb`, so a 2.4 GHz read is no longer silently the
  keyboard's USB interface.

### Changed

- **`qmk_firmware/` is a pinned git submodule** (`pngdeity/cleave-keeb`, branch
  `split65-overlay`, vendor revision `580665f7` + our commits). Board changes are
  commits inside the submodule; the root repo pins the result by gitlink.
- `bootmagic.matrix` corrected from `[0,0]` to `[1,0]` (the top-left key's real
  matrix position; row 0 is unused).
- Board `keyboard.json` gained a `url` and the `readme.md` a hardware link.
- Documentation restructured under `docs/` (`DEVICE.md`, `HARDWARE.md`,
  `PROTOCOL.md`, `DEPENDENCIES.md`, `FINDINGS.md`); `AGENTS.md` added.

### Removed

- `local-patches.diff`, now redundant with the tracked sources.

[Unreleased]: https://github.com/pngdeity/keeb/commits/main
