# keeb

EPOMAKER Split65 wireless (tri-mode) keyboard firmware and host tooling.

Adds host-visible battery reporting via a vendor Raw HID command (`0xA4`), so a
polybar module can display the keyboard's battery level. The transport and wire
format are implemented and verified over USB and 2.4 GHz, but **the reported
percentage is not yet trustworthy** — the keyboard's wireless module does not
answer the level inquiry on USB, so the value stays at its compile-time default
(see `TODO.md` defect 1). Bluetooth is implemented on the host side but not yet
probed on hardware.

## Layout

| Path | Purpose |
|------|---------|
| `qmk_firmware/` | The QMK tree this board builds against, pruned to only what it needs. GPL-2.0-or-later. |
| `qmk_firmware/keyboards/epomaker/epomaker_split65/` | Vendor board source (no battery responder; see `TODO.md`). |
| `qmk_firmware/keyboards/epomaker/epomaker_split65/keymaps/default/` | Vendor keymap (the only one in the tree). |
| `qmk_firmware/keyboards/linker/wireless/` | The vendor wireless stack, included by the board's `post_rules.mk`. |
| `host/battery_polybar.py` | Polybar module; reads battery over Raw HID or BLE. |
| `host/README.md` | Host module usage and polybar configuration. |
| `split65.py` | Build / flash / diagnostics helper. |
| `host/epomaker-split65-via.json` | VIA keyboard definition. |
| `docs/DEVICE.md` | What the device is: layout, ports, modes, accessories, nomenclature. |
| `docs/assets/` | Device photographs referenced by `docs/DEVICE.md`. |
| `docs/PROTOCOL.md` | The `0xA4` battery Raw HID protocol. |
| `docs/HARDWARE.md` | Immutable hardware facts (USB IDs, interfaces, DFU entry, sleep/wake). |
| `docs/DEPENDENCIES.md` | Toolchain, flashing procedure, host dependencies. |
| `docs/FINDINGS.md` | Research notes and design decisions. |
| `TODO.md` | **The live record** — outstanding work, defects, and verification status. |
| `CHANGELOG.md` | Notable changes. |
| `CONTRIBUTING.md` | Lint/build/commit conventions and the traps in this tree. |
| `LICENSE` | Apache-2.0 for project files; scope note for GPL firmware. |

## Repositories

- **`pngdeity/keeb`** (this project) — the whole tree, docs, host tooling and the
  pruned firmware.
- **`pngdeity/cleave-keeb`** — the QMK fork the firmware was originally taken
  from (`split65-battery` branch). Upstream is `hangshengkeji/qmk_firmware`
  (`tri-mode`).

The `qmk_firmware/` directory is **plain files**, not a submodule: it was
flattened into this repository, so a normal `git clone` gets everything and no
submodule commands are needed. `lib/{chibios,chibios-contrib,printf,fnv,lib8tion}`
are kept whole; the vendor stack's own submodules under `qmk_firmware/lib/` were
resolved into the same tree.

## Status

**Both halves still run the earlier `nathan` battery build** (manufacturer
`LEO`); they have **not** been reflashed with the vendor build now in the tree,
which is why the tree and the hardware disagree. Read `TODO.md` for the
authoritative, live status — do not rely on this summary.

> The tree currently holds **vendor firmware** (no battery reporting); our
> battery work is parked in the older inner repo. See `TODO.md` Status.

- Both halves enumerate as `342d:e4c6`, manufacturer `LEO` (stock firmware was
  `MILE`).
- The battery `0xA4` responder is **not** in the current tree; `--pull` only
  works against a battery-feature build (the `nathan` firmware on the halves).
- The 2.4 GHz round-trip works; a real percentage has never been observed.
- Bluetooth is unprobed.

## Quick start

```bash
./split65.py check                # verify toolchain, udev rules, device

# from qmk_firmware/ (the tree currently builds the vendor keymap):
make epomaker/epomaker_split65:default
```

See `docs/DEPENDENCIES.md` for prerequisites and the DFU entry procedure for
each half. Both split halves run identical firmware; handedness is pin-based.

## Reading order

If you are new to this project, read in this order:

1. **`AGENTS.md`** — working rules and environment traps. Read first.
2. **`TODO.md`** — the live record: status, priority order, known defects.
3. **`docs/DEVICE.md`** — what the device is: layout, ports, modes, accessories,
   and the vocabulary for naming its parts.
4. **`docs/HARDWARE.md`** — immutable hardware facts (USB identities, raw HID
   interfaces, DFU entry, sleep/wake). Measured, not inferred.
5. **`docs/PROTOCOL.md`** — the `0xA4` battery wire format.
6. **`docs/DEPENDENCIES.md`** — toolchain, flashing, host dependencies.
7. **`docs/FINDINGS.md`** — why the design is the way it is.
8. **`CONTRIBUTING.md`** — conventions and the traps in this tree.

## Development

QMK conventions apply to the firmware tree: run `qmk lint` and build before
committing. See `CONTRIBUTING.md`.

## License

Apache-2.0 for this project's own files. The vendored `qmk_firmware/` and the
board firmware derived from it are GPL-2.0-or-later. See `LICENSE` for the
exact scope.
