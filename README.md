# keeb

EPOMAKER Split65 wireless (tri-mode) keyboard firmware and host tooling.

Adds host-visible battery reporting via a vendor Raw HID command (`0xA4`), so a
polybar module can display the keyboard's battery level. Verified over USB and
2.4 GHz; Bluetooth is implemented on the host side but not yet probed on
hardware.

## Layout

| Path | Purpose |
|------|---------|
| `qmk_firmware/` | Vendored QMK snapshot (`hangshengkeji/qmk_firmware`, branch `tri-mode`) containing the wireless stack. GPL-2.0-or-later. |
| `qmk_firmware/keyboards/epomaker/epomaker_split65/` | Board source, including `wls/wls_battery.c` (the battery responder). |
| `qmk_firmware/keyboards/epomaker/epomaker_split65/keymaps/default/` | Stock keymap. |
| `qmk_firmware/keyboards/epomaker/epomaker_split65/keymaps/nathan/` | Personal keymap. |
| `host/battery_polybar.py` | Polybar module; reads battery over Raw HID or BLE. |
| `host/README.md` | Host module usage and polybar configuration. |
| `split65.py` | Build / flash / diagnostics helper. |
| `EPOMAKER Split65.json` | VIA keyboard definition. |
| `PROTOCOL.md` | The `0xA4` battery Raw HID protocol. |
| `DEPENDENCIES.md` | Toolchain, flashing procedure, host dependencies. |
| `FINDINGS.md` | Research notes, design decisions, hardware verification status. |
| `TODO.md` | Outstanding work and current flashing status. |
| `CHANGELOG.md` | Notable changes. |
| `CONTRIBUTING.md` | Lint/build/commit conventions. |
| `LICENSE` | Apache-2.0 for project files; scope note for GPL firmware. |
| `chunk87.bin` | Unidentified flash artifact, kept for reference (not version-controlled). |

## Repositories

- **`pngdeity/keeb`** (this project) — docs, host tooling, and the `qmk_firmware`
  submodule.
- **`pngdeity/cleave-keeb`** — the QMK fork (`split65-battery` branch) that the
  `qmk_firmware` submodule points at. Upstream is `hangshengkeji/qmk_firmware`
  (`tri-mode`), kept as the submodule's `upstream` remote.

The `qmk_firmware/` directory is a **git submodule**, not a plain directory. After
a fresh clone, run `git submodule update --init --recursive`.

## Status

- Left half flashed and verified: `python3 host/battery_polybar.py --pull`
  returns `CHG 100%` over USB.
- Right half not yet flashed. The flashed firmware identifies as manufacturer
  `LEO`; the stock firmware was `MILE`.
- See `TODO.md` for what remains and `FINDINGS.md` for the verification log.

## Quick start

```bash
./split65.py check                # verify toolchain, udev rules, device
./split65.py build                # build the nathan keymap
./split65.py flash                # flash (keyboard must be in DFU)

python3 host/battery_polybar.py --pull        # USB
python3 host/battery_polybar.py --listen      # 2.4 GHz
```

See `DEPENDENCIES.md` for prerequisites and the DFU entry procedure for each
half. Both split halves run identical firmware; handedness is pin-based.

## Development

QMK conventions apply to the firmware tree: run `qmk lint` and build before
committing. See `CONTRIBUTING.md`.

## License

Apache-2.0 for this project's own files. The vendored `qmk_firmware/` and the
board firmware derived from it are GPL-2.0-or-later. See `LICENSE` for the
exact scope.
