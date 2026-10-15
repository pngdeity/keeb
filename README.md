# keeb

EPOMAKER Split65 wireless (tri-mode) keyboard firmware and host tooling.

The governing requirements are **user-facing** and live in
`docs/UX-REQUIREMENTS.md`: what a person must be able to infer from the keyboard.
The firmware's **engineering** usage modes — the whole keyboard wireless while
discharging; wireless while charging (a power brick charges it while a
power-limited host uses it for input); and wired over USB while charging — are
**derived from** those requirements, not a layer beside them (`docs/FINDINGS.md`
"Usage modes (derived)"; the mapping is `docs/UX-REQUIREMENTS.md` § 1.5). **Mode 2
is fixed in source**: the cable is a power fact and reaches no transport decision —
the switch is authoritative (`wls/transport_logic.c`, `hsm_input_rule`). The
remaining work is a hardware confirmation, not a code change (`TODO.md` Tier 1
item 8).

To serve those modes, the firmware adds host-visible battery reporting via a
vendor Raw HID command (`0xA4`), so a polybar module can display the keyboard's
battery level. The transport and wire format are implemented; over USB the
percentage is **not yet trustworthy** — the keyboard's wireless module does not
answer the level inquiry on USB, so the value stays at its compile-time default
(see `TODO.md` defect 1). **2.4 GHz works end to end**: the dongle does
enumerate — it stays USB-silent until the keyboard is actively on the 2.4 GHz
link, then appears as `342d:e4c6` with its raw-HID collection on interface 2,
and a `0xA4` pull round-trips with transport byte `0x04` (measured 2026-10-09;
`docs/HARDWARE.md` "The 2.4 GHz dongle"). **Bluetooth is implemented and probed,
but broken in a known way**: the module's HID server rejects the
notification-enabling writes with ATT `0x0E`, so a link may connect without
carrying input (`docs/UX-REQUIREMENTS.md` § 0.7). A real battery percentage has
never been observed over a wireless transport.

The `nathan` keymap lives in the sibling userspace repo `../keeb-userspace/`;
the firmware sources live in the `qmk_firmware/` submodule. **Both halves run an
earlier build, not the current tree's** — see Status.

## Layout

| Path | Purpose |
|------|---------|
| `qmk_firmware/` | The QMK tree this board builds against, a **pinned submodule** (`pngdeity/cleave-keeb`, rebased onto `qmk/qmk_firmware` master + our commits). GPL-2.0-or-later. |
| `qmk_firmware/keyboards/epomaker/epomaker_split65/` | Board source, including our battery responder (`wls/wls_battery.c`). |
| `qmk_firmware/keyboards/epomaker/epomaker_split65/keymaps/default/` | Vendor `default` keymap (the only keymap in the tree). |
| `qmk_firmware/keyboards/linker/wireless/` | The shared vendor wireless stack, included by the board's `post_rules.mk` via `wireless/wireless.mk`. |
| `qmk_firmware/keyboards/epomaker/epomaker_split65/wireless/` | The board's local override of the one vendor file it changes (`lpwr_wb32.c`, the deep-sleep fix), plus the make fragment that pulls in the shared stack. |
| `bin/make`, `bin/qmk` | Project-local wrappers for `make`/`qmk` (see `AGENTS.md`). |
| `host/battery_polybar.py` | Polybar module; reads battery over Raw HID or BLE. |
| `host/README.md` | Host module usage and polybar configuration. |
| `split65.py` | Build / flash / diagnostics helper. |
| `host/epomaker-split65-via.json` | VIA keyboard definition. |
| `docs/DEVICE.md` | What the device is: layout, ports, modes, accessories, nomenclature. |
| `docs/assets/` | Device photographs referenced by `docs/DEVICE.md`. |
| `docs/PROTOCOL.md` | The `0xA4` battery Raw HID protocol. |
| `docs/0xA4-golden-vector.md` | The pinned golden-vector table the host self-check and the firmware agree on. |
| `docs/HARDWARE.md` | Immutable hardware facts (USB IDs, interfaces, DFU entry, sleep/wake). |
| `docs/INDICATORS.md` | **The LED instrument contract** — what each pattern means when debugging a board you cannot otherwise see. The *instrument* view; `docs/UX-REQUIREMENTS.md` is the user-facing one. |
| `docs/BOOT-SEQUENCE.md` | What runs from reset to steady state, in order. |
| `docs/USAGE.md` | The end-user guide, from the desk: layers, backlight, battery, wireless, sleep, recovery. |
| `docs/DEPENDENCIES.md` | Toolchain, flashing procedure, host dependencies. |
| `docs/RUNBOOK-flash-and-measure.md` | The pre-flight checklist, measurement procedure, and session log for a hardware session. |
| `docs/FINDINGS.md` | Research notes and design decisions. |
| `docs/BOARD-LAYER.md` | The board layer's contract and its definition of done. |
| `docs/ADR-transport-authority.md` | Decision record: one authority for transport, and the alternatives rejected. |
| `docs/PLAN-fcis-audit.md` | The plan that named the audit's values (V1–V10) and their measurements. |
| `docs/AUDIT.md` | Per-state audit against the plan's values. |
| `docs/AUDIT-fcis.md` | Per-value, per-module audit record (the measurement used, not an impression). |
| `docs/METHOD.md` | **How we work** — the authoritative process in two halves: the **engineering loop** (exhaust analysis before any flash → standard → audit → slice → class → fitness function → hardware) and the **debugging loop** (observe → instrument → layer → class), generalized from practice, each rule citing its incident. Read before changing code or investigating a fault. |
| `docs/UX-REQUIREMENTS.md` | **What a person must be able to infer from the keyboard** — the user-facing requirements, derived from the human-interface literature with the derivation method recorded. The standard that `docs/USAGE.md` describes behaviour against. |
| `TODO.md` | **The live record** — outstanding work, defects, and verification status. |
| `CHANGELOG.md` | Notable changes. |
| `CONTRIBUTING.md` | Lint/build/commit conventions and the traps in this tree. |
| `LICENSE` | Apache-2.0 for project files; scope note for GPL firmware. |

## Repositories

- **`pngdeity/keeb`** (this project) — the docs, host tooling, build wrappers and
  the submodule pin.
- **`pngdeity/cleave-keeb`** — the QMK fork the firmware builds from (branch
  `split65-overlay`, rebased onto `qmk/qmk_firmware` master). The old vendor line
  is preserved as `split65-vendor-overlay` (remote and local). It is the
  `qmk_firmware/` submodule's remote. Upstream is `hangshengkeji/qmk_firmware`
  (`tri-mode`).

`qmk_firmware/` is a **pinned git submodule**, not plain files. A fresh clone
needs `git clone --recurse-submodules` (or `git submodule update --init
--recursive`); the submodule URL is HTTPS so it fetches without an SSH key.
Eight submodules are initialized inside it — `lib/{chibios,chibios-contrib,
googletest,lufa,printf,pico-sdk,lvgl,vusb}` — covering both the build and the
`./bin/qmk test-c` suite (`googletest`).

## Status

**Both halves still run the earlier `nathan` battery build** (manufacturer
`LEO`); they have **not** been reflashed with the current tree's build. Read
`TODO.md` for the authoritative, live status — do not rely on this summary.

- The tree **holds the battery feature**: `wls/wls_battery.c` (raw HID `0xA4`),
  committed inside the `qmk_firmware` submodule, and the `nathan` keymap lives in
  the sibling userspace repo `../keeb-userspace/`.
- The `nathan` keymap and the board source (battery responder, board-local
  deep-sleep fix) are committed in the submodule/userspace; build them with
  `./bin/make epomaker/epomaker_split65:default` or `:nathan` and read the hash
  on demand.
- Both halves enumerate as `342d:e4c6`, manufacturer `LEO` (stock firmware was
  `MILE`).
- **2.4 GHz is a working second transport** — the dongle enumerates on the 2.4 GHz
  link, its raw-HID collection is on interface 2, and a `0xA4` pull round-trips
  (measured 2026-10-09). A real battery percentage has not been observed over it.
- Bluetooth is implemented and probed, but the module's HID server rejects the
  notification-enabling writes (ATT `0x0E`), so a connected link may not deliver
  input (`docs/UX-REQUIREMENTS.md` § 0.7).

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
7. **`docs/METHOD.md`** — **how we work**: the authoritative engineering and
   debugging loops. Read before changing code or investigating a fault.
8. **`docs/FINDINGS.md`** — why the design is the way it is.
9. **`docs/UX-REQUIREMENTS.md`** — what a person must be able to infer from the
   keyboard; the user-facing requirements and the method that derived them.
10. **`docs/INDICATORS.md`** — what each LED pattern means when debugging a board
    you cannot otherwise see (the *instrument* contract).
11. **`docs/USAGE.md`** — the end-user guide: layers, backlight, battery, wireless,
    sleep, and recovery, from the desk.
12. **`CONTRIBUTING.md`** — conventions and the traps in this tree.

## Development

QMK conventions apply to the firmware tree: lint and build before committing, via
`./bin/qmk lint` and `./bin/make`. See `AGENTS.md` and `CONTRIBUTING.md`.

## License

Apache-2.0 for this project's own files. The vendored `qmk_firmware/` and the
board firmware derived from it are GPL-2.0-or-later. See `LICENSE` for the
exact scope.
