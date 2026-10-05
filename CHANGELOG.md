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
- Personal keymap `keymaps/nathan/`.

> The battery firmware and the `nathan` keymap are **not in the current tree**:
> it was later reverted to the vendor source. They live in the old inner repo
> (branch `split65-battery`) and in `/tmp/opencode/pre-vendor-revert/`. See
> `TODO.md` Status.

### Changed

- Reverted the tree to the **vendor** board source, keeping only the vendor
  `default` keymap; the battery reporter and personal keymap are parked outside
  the tree.
- Consolidated the former standalone `keeb` project into this repository; all
  keyboard assets now live in one place.
- Flattened `qmk_firmware/` from a submodule into ordinary tracked files and
  pruned it (`keyboards/` reduced to the two trees this board needs).

### Removed

- `local-patches.diff`, now redundant with the tracked sources.

[Unreleased]: https://github.com/pngdeity/keeb/commits/main
