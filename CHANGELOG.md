# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Battery reporting over Raw HID command `0xA4` (`KC_GET_BATTERY_LEVEL`),
  returning percentage, charging state, and active transport; documented in
  `PROTOCOL.md`.
- Firmware responder `wls/wls_battery.c` implementing a strong
  `raw_hid_receive()` override, master-half only.
- 2.4 GHz push mode (`kb_battery_push_task()`) as a fallback to host pull.
- Host polybar module `host/battery_polybar.py` with `--pull`, `--listen`, and
  `--bluetooth` (BLE Battery Service `0x180F`/`0x2A19`) modes.
- Build/flash/diagnostics helper `split65.py`.
- VIA keyboard definition `EPOMAKER Split65.json`.
- Personal keymap `keymaps/nathan/`.

### Fixed

- `wls/wls.c` and `wls/wls.h` had no license headers, which failed
  `qmk lint`.

### Changed

- Consolidated the former standalone `keeb` project into this repository; all
  keyboard assets now live in one place.

### Removed

- `local-patches.diff`, now redundant with the tracked sources.

[Unreleased]: https://github.com/pngdeity/keeb/compare/v0.1.0...HEAD
