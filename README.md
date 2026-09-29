# keeb

EPOMAKER Split65 wireless (tri-mode) keyboard firmware and host tooling.

Adds host-visible battery reporting over all three transports (2.4 GHz dongle,
Bluetooth, USB-C) via a vendor Raw HID command, so a polybar module can display
the keyboard's battery level.

## Layout

| Path | Purpose |
|------|---------|
| `qmk_firmware/` | Vendored QMK snapshot (`hangshengkeji/qmk_firmware`, branch `tri-mode`) containing the wireless stack. GPL-2.0-or-later. |
| `qmk_firmware/keyboards/epomaker/epomaker_split65/` | Board source, including `wls/wls_battery.c` (the battery responder). |
| `qmk_firmware/keyboards/epomaker/epomaker_split65/keymaps/default/` | Stock keymap. |
| `qmk_firmware/keyboards/epomaker/epomaker_split65/keymaps/nathan/` | Personal keymap. |
| `host/battery_polybar.py` | Polybar module; reads battery over Raw HID or BLE. |
| `split65.py` | Build / flash / diagnostics helper. |
| `EPOMAKER Split65.json` | VIA keyboard definition. |
| `PROTOCOL.md` | The `0xA4` battery Raw HID protocol. |
| `DEPENDENCIES.md` | Toolchain, flashing procedure, host dependencies. |
| `FINDINGS.md` | Research notes and design decisions. |
| `TODO.md` | Outstanding work. |
| `CHANGELOG.md` | Notable changes. |

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
