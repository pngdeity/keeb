# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Battery reporting over Raw HID command `0xA4` (the `KC_GET_BATTERY_LEVEL`
  convention), returning percentage, charging state, and active transport;
  documented in `docs/PROTOCOL.md`. The percentage value is upstream's
  (`quantum/battery`, via the `custom` driver `wls/wls_battery_driver.c`).
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

- **Deep sleep on the split — the unrecoverable-STOP class.** Three faults (a
  slave reset-loop, a slave dark-out, and a master dark-out on Bluetooth) were
  one defect: a half could enter low power with no guaranteed way back. The fix
  has two layers in the shared `keyboards/linker/wireless/` stack: a
  **sleep-policy contract** (`lpwr_stop_is_allowed()`, checked at the single
  commitment point in `lpwr_stop_cb()`) and a
  **wake-code set** (wake causes are bit flags accumulated and compared as a set
  against a board-supplied armed mask, so a phantom event cannot discard a real
  one). The WB32 EXTI is pad-numbered and port-agnostic, so pads are aliased
  (e.g. module UART RX `C11` with matrix column `B11`); the set form is what
  makes that safe. The two decisions are extracted into a dependency-free core
  (`lowpower_logic.c`) with unit tests (`tests/lowpower_logic/`). The earlier
  board-local `wireless/lpwr_wb32.c` fix (per-half wake arrays, falling-edge
  events, UART-RX wake no longer armed) remains. **Not yet flashed.**
- **Redundant USB wake init removed.** `usb_remote_host()` no longer calls
  `suspend_wakeup_init()` on every USB action; the QMK USB core already calls it
  once per real `USB_EVENT_WAKEUP`. Behaviour-preserving (the compiler had
  already folded the call), now architecturally correct.
- **EEPROM schema is versioned.** `confinfo_t` gained a `version` field; a
  stored block from an older layout is re-defaulted once instead of being
  patched per-field heuristically.
- **A CI guard for the raw-HID line coupling**: the vendor stack remaps
  `raw_hid_send` by hardcoded line number, so CI now asserts those two lines
  still hold the expected code and fails loudly if a submodule bump moves them.
- Host tool prefers the collection with `interface_number == 2` (assumed to be the
  2.4 GHz dongle; unverified — the dongle shares the keyboard's VID:PID) and
  exposes `--transport usb`, so a 2.4 GHz read is attempted rather than silently
  using the keyboard's USB interface.
- Battery push now sends on change (level/charge/transport) with a slow
  keepalive, instead of an unconditional 2-second heartbeat.

### Changed

- **`qmk_firmware/` is a pinned git submodule** (`pngdeity/cleave-keeb`, branch
  `split65-overlay`, rebased onto `qmk/qmk_firmware` master). Board changes are
  commits inside the submodule; the root repo pins the result by gitlink.
- `bootmagic.matrix` corrected from `[0,0]` to `[1,0]` (the top-left key's real
  matrix position; row 0 is unused).
- Board `keyboard.json` gained a `url` and the `readme.md` a hardware link.
- Documentation restructured under `docs/` (`DEVICE.md`, `HARDWARE.md`,
  `PROTOCOL.md`, `DEPENDENCIES.md`, `FINDINGS.md`); `AGENTS.md` added.

### Removed

- `local-patches.diff`, now redundant with the tracked sources.

[Unreleased]: https://github.com/pngdeity/keeb/commits/main
