# keeb

EPOMAKER Split65 wireless (tri-mode) keyboard firmware and host tooling.

The firmware must support three usage modes, in priority order: the whole
keyboard wireless while discharging; wireless while charging (an external PSU
charges it while a separate, power-limited host uses it for input); and wired
over USB while charging. See `docs/FINDINGS.md` "Functional
requirements" for the rationale and the accepted tradeoffs. Mode 2 currently
conflicts with a cable-insert auto-switch in the firmware; that is `TODO.md`
Tier 1 item 7.

To serve those modes, the firmware adds host-visible battery reporting via a
vendor Raw HID command (`0xA4`), so a polybar module can display the keyboard's
battery level. The transport and wire format are implemented and verified over
USB and 2.4 GHz, but **the reported percentage is not yet trustworthy** — the
keyboard's wireless module does not answer the level inquiry on USB, so the
value stays at its compile-time default (see `TODO.md` defect 1). Bluetooth is
implemented on the host side but not yet probed on hardware.

The `nathan` battery firmware is committed in the `qmk_firmware` submodule; the
halves still run an older build of it (see Status).

## Layout

| Path | Purpose |
|------|---------|
| `qmk_firmware/` | The QMK tree this board builds against, a **pinned submodule** (`pngdeity/cleave-keeb`, vendor revision `580665f7` + our commits). GPL-2.0-or-later. |
| `qmk_firmware/keyboards/epomaker/epomaker_split65/` | Board source, including our battery responder (`wls/wls_battery.c`). |
| `qmk_firmware/keyboards/epomaker/epomaker_split65/keymaps/default/` | Vendor `default` keymap (the only keymap in the tree). |
| `qmk_firmware/keyboards/linker/wireless/` | The vendor wireless stack, included by the board's `post_rules.mk`. |
| `bin/make`, `bin/qmk` | Project-local wrappers for `make`/`qmk` (see `AGENTS.md`). |
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

- **`pngdeity/keeb`** (this project) — the docs, host tooling, build wrappers and
  the submodule pin.
- **`pngdeity/cleave-keeb`** — the QMK fork the firmware builds from (branch
  `split65-overlay`, now rebased onto `qmk/qmk_firmware` master; the old vendor
  line is preserved as the local branch `split65-vendor-overlay`). It is the
  `qmk_firmware/` submodule's remote. Upstream is `hangshengkeji/qmk_firmware`
  (`tri-mode`). **The rebased branch is local-only until pushed** — the remote's
  `split65-overlay` still holds the old vendor line.

`qmk_firmware/` is a **pinned git submodule**, not plain files. A fresh clone
needs `git clone --recurse-submodules` (or `git submodule update --init
--recursive`); the submodule URL is HTTPS so it fetches without an SSH key.
Only the build-required libs are initialized inside it
(`lib/{chibios,chibios-contrib,printf,lufa}`).

## Status

**Both halves still run the earlier `nathan` battery build** (manufacturer
`LEO`); they have **not** been reflashed with the current tree's build. Read
`TODO.md` for the authoritative, live status — do not rely on this summary.

- The tree **holds the battery feature**: `wls/wls_battery.c` (raw HID `0xA4`),
  committed inside the `qmk_firmware` submodule, and the `nathan` keymap lives in
  the sibling userspace repo `../keeb-userspace/`.
- The `nathan` keymap and the board source (battery responder, board-local
  deep-sleep fix) are committed in the submodule/userspace; build them with
  `./bin/make epomaker/epomaker_split65:all` and read the hash on demand.
- Both halves enumerate as `342d:e4c6`, manufacturer `LEO` (stock firmware was
  `MILE`).
- The 2.4 GHz round-trip works; a real percentage has never been observed.
- Bluetooth is unprobed.

## Quick start

```bash
./split65.py check                             # verify toolchain, udev rules, device
./bin/make epomaker/epomaker_split65:default   # stock keymap
./bin/make epomaker/epomaker_split65:nathan    # personal keymap (userspace)
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

QMK conventions apply to the firmware tree: lint and build before committing, via
`./bin/qmk lint` and `./bin/make`. See `AGENTS.md` and `CONTRIBUTING.md`.

## License

Apache-2.0 for this project's own files. The vendored `qmk_firmware/` and the
board firmware derived from it are GPL-2.0-or-later. See `LICENSE` for the
exact scope.
