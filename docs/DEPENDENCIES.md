# Dependencies

## Build (firmware)

- QMK build toolchain as shipped in `qmk_firmware/`, which is a **pinned
  submodule** (branch `split65-overlay`, rebased onto `qmk/qmk_firmware` master).
  Its build-required submodules
  (`lib/{chibios,chibios-contrib,printf,lufa}`) are initialized; the rest arrive
  with the pinned revision.
- `arm-none-eabi-gcc` (Arch: `arm-none-eabi-gcc`), `make`, `python3`.
- **Use the project-local wrappers `bin/make` and `bin/qmk`, not a bare `make`
  or a system `qmk`.** The packaged `qmk` (1.2.0) lacks `compile`, `flash` and the
  `userspace-*` commands; the modern CLI ships **inside the submodule** at
  `lib/python/qmk/`. `bin/qmk` runs `.venv/bin/python` against that copy. See
  "The qmk CLI and make wrapper" below.
- Build commands (run from the project root; `bin/make` `cd`s into
  `qmk_firmware/` itself):

  ```sh
  ./bin/make epomaker/epomaker_split65:default   # stock (vendor) keymap
  ./bin/make epomaker/epomaker_split65:nathan     # personal keymap (userspace)
  ```

- The `nathan` keymap lives **outside** the tree, in the sibling userspace repo
  `../keeb-userspace/` (the submodule holds the vendor `default` keymap and our
  board source; the personal keymap is userspace). **`QMK_USERSPACE` is
  required**: this tree's Makefile reads `user.overlay_dir` from the qmk config
  but does **not** forward it into the inner `build_keyboard.mk` submake, and
  `qmk list-keymaps` / `qmk compile` do not consult userspace either. Without it,
  `make ...:nathan` resolves only `default` and fails with `No rule to make
  target 'nathan'`. `bin/make` supplies it.
- Or use the project helper: `./split65.py build` / `./split65.py flash` /
  `./split65.py check` / `./split65.py setup` (see `--help`). `split65.py`
  targets the `nathan` keymap (`KEYMAP` at the top) and builds via `bin/make`, so
  `QMK_USERSPACE` is supplied exactly as above.
- **`split65.py flash` and the raw `wb32-dfu-updater_cli` are for a human to
  run.** `flash` calls `doas` and prompts with `input()`, so it must not be
  launched by an agent or any non-interactive context: an unanswered `doas`
  prompt locks the account after three failed attempts.

## The qmk CLI and make wrapper

Use the project-local wrappers — no system install is needed.

```sh
./bin/qmk hello
./bin/qmk compile -kb epomaker/epomaker_split65 -km default
./bin/make epomaker/epomaker_split65:nathan
```

- **`bin/qmk`** sets `ORIG_CWD`, prepends the submodule's `lib/python` to
  `PYTHONPATH`, and `cd`s into `qmk_firmware/` before running `.venv/bin/python` —
  the tree's CLI resolves `requirements.txt` and `keyboards/` relative to CWD.
  It also forces `sys.argv[0] = "qmk"` **before** importing milc: milc derives its
  program name (and therefore its config file `~/.config/qmk/qmk.ini`) from
  `argv[0]`, so a plain `python -c` would look for `-c.ini` and never read
  `user.overlay_dir`.
- **`bin/make`** wraps the real `make`: it puts `bin/` first on `PATH` (so the
  Makefile's `QMK_BIN := qmk` finds the project CLI) and passes `QMK_USERSPACE`
  both as an environment variable and as a make command-line variable. It
  resolves the real `make` path *before* touching `PATH`, so it does not recurse
  into itself. The userspace repo is a **sibling** of this repo
  (`../keeb-userspace/`), not a child.
- The project venv is `.venv/` (Python 3.12, gitignored). Create it once with:

  ```sh
  uv venv
  uv pip install --python .venv/bin/python -r qmk_firmware/requirements.txt
  ```

- **`bin/compiledb`** generates `qmk_firmware/compile_commands.json` (and a copy
  at the userspace root) and then does a real build, so the *generated* headers
  (`info_config.h`) exist on disk for clangd/Serena. Run `./bin/compiledb nathan`
  (or `default`) after a clean checkout or a build-config change. QMK's own
  `generate-compilation-database` does a `make clean` first, which removes those
  headers and defeats clangd — hence the wrapper. Both the DB and clangd's cache
  are gitignored.

## Flashing

- `wb32-dfu-updater_cli` (present at `/usr/local/bin/wb32-dfu-updater_cli`).
  Flash with `wb32-dfu-updater_cli -t -s 0x08000000 -D <bin>` then
  `wb32-dfu-updater_cli -R` to reset. **Wired USB is required**; 2.4 GHz /
  Bluetooth cannot flash.
- **Prerequisite:** the wb32-dfu udev rule must be installed or the updater
  cannot claim the device as a normal user. `qmk doctor` reports this as
  "Missing or outdated udev rules for 'wb32-dfu' boards". On this host two rules
  under `/etc/udev/rules.d/` cover both needs, and neither is vendored in this
  tree:
  - `50-qmk-wb32.rules` grants the DFU bootloader (`342d:dfa0`) as `uaccess`
    (QMK's set, installed by `util/install_udev.sh`, ships as `50-qmk.rules`).
  - `50-epomaker-split65.rules` grants hidraw access for the running keyboard
    (`342d:e4c6`, `MODE=0660` + `uaccess`), which VIA/QMK keymap editing needs.

- **Both halves run identical firmware** — handedness is pin-based
  (`split.handedness.pin`, read by `is_keyboard_master()`), not EEPROM-based, so
  there are no `-split-left`/`-split-right` variants. Each half is flashed
  separately, and they enter DFU by **different** means:
  - **Left (master):** remove the spacebar, **short the two metal-plated holes**
    the spacebar switch's feet sit in, and plug in USB-C **while still shorting**.
    Esc-hold (bootmagic) works on stock firmware but is **broken on our build**;
    there is also no reset switch on this half (an earlier claim to the contrary
    was unverified and wrong).
  - **Right (slave):** Esc-hold does **not** work. Remove the `R_Shift` **keycap**
    (not the case) to expose the hidden toggle switch underneath; **toggle it DOWN**
    to arm DFU, then remove the spacebar and short the two metal-plated
    holes with tweezers while plugging in the right half's USB-C cable.
    **Toggle it back UP** and restore the keycaps afterwards.

## Keyboard reference

### Recovery / DFU entry

Key positions are given in the canonical form from `DEVICE.md` — **`<half>,
matrix [row,col]`** — with the `LAYOUT()` argument index for cross-reference to
the keymap. Several entries act on the layer that is active, so the **layer-0
legend** and the **Fn-layer legend** are listed separately; they differ.

| Method | How | Effect |
|---|---|---|
| Hardware DFU | Short the two metal-plated spacebar holes + plug USB | Always works (both halves) |
| Bootmagic DFU | Hold Escape + plug USB (left half only) | Broken on non-OEM firmware |
| Right-half DFU | Remove the `R_Shift` keycap, toggle the exposed switch **down**, then spacebar-pin short + plug USB (toggle back **up** after) | Bootloader (see Flashing) |
| Software DFU | `QK_BOOT` — `Fn` (`held` spacebar) + the top-right corner key, matrix `[10,4]` | Bootloader |
| Factory reset | `EE_CLR` — hold-only `_RST` layer at right half, matrix `[11,8]` (the bottom-right corner key) | Clears EEPROM settings |

> `QK_BOOT` sits on the **Fn** layer at the Fn-layer top-right corner key
> (matrix `[10,4]`), reached by holding the right spacebar (Fn; the left space
> is plain). It is deliberately NOT
> on the base layer: the base-layer `Esc` position (`[1,0]`) is a plain `KC_ESC`,
> so a stray tap cannot drop a half into the bootloader.
>
> `EE_CLR` was moved off the Fn-layer `Bksp` position to the far corner of a
> hold-only layer: `_RST` is armed only by `LT(_RST, KC_NO)` on the **Fn-layer
> top-right corner key**, so a wipe needs a held Fn chord plus a press on the
> opposite half's bottom-right corner. It is no longer reachable by a single
> stray hold.

### Wireless modes

| Key (Fn layer) | Matrix | Action |
|---|---|---|
| `KC_BT1` / `KC_BT2` / `KC_BT3` | `[2,1]` / `[2,2]` / `[2,3]` (left half) | Bluetooth device 1 / 2 / 3 |
| `KC_2G4` | `[2,4]` (left half) | 2.4 GHz dongle |
| `KC_BATQ` | `[5,5]` (left spacebar position) | Request the battery indicator |

Notes:

- These keycodes are **no-ops unless the physical three-position switch already
  reports a wireless position** (`hs_modeio_detection()` in `wls/wls.c`; see
  `HARDWARE.md`). The switch wins over the keys.
- `KC_BATQ` does nothing on USB (`confinfo.devs == DEVS_USB`) and, when it does
  fire, only lights a single LED: `HS_MATRIX_BLINK_INDEX_BAT` blinks red when the
  level is `<= BATTERY_CAPACITY_LOW` (15). It does **not** render a percentage
  bar; no key does.
- Auto-switch: inserting the USB cable switches to wired and remembers the
  previous wireless transport; removing it restores that transport.

### Notable keymap features

The tree contains the vendor `default` keymap. The personal `nathan` keymap
(key overrides, right-spacebar Fn hold, `CAPS_WORD`) lives in the sibling
userspace repo `../keeb-userspace/` and is **not** in the tree — see `TODO.md`
Status.

| Combo | Effect |
|---|---|
| Fn held | Layer `_FL` (there is no held-key Fn on the vendor base layer) |

The encoder is **not mapped** in the effective build: the keymap contains an
`encoder_map[]`, but `ENCODER_MAP_ENABLE` is never set (not in `rules.mk`, not in
`keyboard.json`), so `encoder_map` is dead code and does not appear in the linked
ELF. The encoder therefore runs QMK's default handling unless the feature is
enabled (see `TODO.md`).

## VIA

- Definition: `host/epomaker-split65-via.json`. Load in VIA with
  **File → Import Keymap**.
- VIA releases: `https://github.com/WestBerryVIA/via-releases/releases`.

## Host (polybar module)

- Python 3 with the `hid` package. On Arch it is `python-hid` (already
  installed here; `pacman -S python-hid`). Do **not** install `pyhidapi` — it is
  a different, unmaintained project. The package must provide the `hid.Device`
  API (`.read(size, timeout=ms)`, `.write(data)`,
  `.get_report_descriptor()`) and `hid.enumerate()`.
- For the Bluetooth fallback: BlueZ `bluetoothctl` on `PATH`, keyboard paired.

## Diagnostics (optional)

Pre-flash reconnaissance scripts live under `/tmp/opencode/` (outside the repo)
and write reports to `/tmp/opencode/recon/`. They are throwaway helpers, not part
of the project; the facts they established are recorded in `FINDINGS.md` and
`PROTOCOL.md`.

- `/tmp/opencode/split65-dongle-probe.sh` — enumerates HID interfaces, dumps the
  raw (`0xFF60`/`0x61`) interface descriptor, sends the `0xA4` request and prints
  the reply. Confirms the 2.4 GHz round-trip and needs no elevated privileges.
  Requires the Python `hid` package.
- `/tmp/opencode/split65-recon.sh` — USB/DFU/udev diagnostics; wraps the
  privileged parts in `doas` (run it yourself; an agent must never invoke
  `doas`, as unanswered prompts lock the account). `--flash-udev-rule` installs
  the wb32-dfu udev rule above. Needs `gcc` for the descriptor dump, plus
  `wb32-dfu-updater_cli` / `lsusb` / `dfu-util` where available.

`./split65.py check` is the supported, in-repo alternative for day-to-day
diagnostics (toolchain, udev rules, device presence).

## Local patches to the QMK tree

The `qmk_firmware/` submodule carries our commits on top of the rebased base
(`qmk/qmk_firmware` master). They are pushed to the submodule's remote
(`pngdeity/cleave-keeb`, branch `split65-overlay`), so `git submodule update
--init --recursive` restores them. The old vendor line is preserved on
`split65-vendor-overlay` (remote and local). The list is kept here so the intent
is discoverable and so they can be re-applied if the tree is ever reset to
pristine upstream:

- `lib/python/qmk/math_ops.py`: replace the removed `ast.Num` with `ast.Constant`
  (Python 3.12+). (The file was renamed from `math.py`.)
- `keyboards/epomaker/epomaker_split65/post_rules.mk`: include paths
  `keyboards/leo/...` → `keyboards/epomaker/...`.
- `keyboards/linker/wireless/wireless.c`: drop the leading blank line before the
  license header (QMK's lint reads line 1 literally). Shared file, benefits every
  board that uses the stack.

If you reset the tree to pristine upstream and find the build broken, this is the
first thing to check.

## Provenance and external references

Where our wireless stack comes from, and the public sources that describe it.
Read-only references; nothing here is vendored.

**Lineage (each carries the same `keyboards/*/wireless/` file set — `lowpower`,
`lpwr_wb32`, `md_raw`, `module`, `smsg`, `transport`, `wireless`):**

```
isuua → emolitor/qmk_firmware#wireless-2.0 (Shortcut Studio Bridge75, WB32FQ95+CH582F)
      → WestberryTech/qmk_westberry#tri-mode (vendor fork)
      → hangshengkeji/qmk_firmware#tri-mode  → Epomaker/Split65  (our origin)
```

**Public references:**

- `emolitor/WestberryTech-WB32` — WB32FQ95/F10x reverse-engineering: the vendor
  reference-board schematic, datasheet + reference manual, per-chip YAML (memory
  map, AF pin table, DMA handshake, IRQ), an OpenOCD flash driver, and
  `docs/wireless/ch582f-protocol.md` — the **CH582F module UART protocol** our
  stack implements.
- `emolitor/qmk_firmware` (branch `wireless-2.0`) — the Bridge75 port; essentially
  the same module stack as ours, plus a `battery_custom.c` precedent for our
  `BATTERY_DRIVER = custom`.
- `ozboar/zoom65v3-re` — a **sibling** WB32FQ95 board's pinout/map. Use as a shape
  cross-check only; it is **not** the Split65 netlist, and its module-UART pins
  differ from ours (see `HARDWARE.md`).
- Chinese open-hardware (`oshwhub.com`) — third-party **CH582F tri-mode keyboard**
  schematics (a wired→BT converter "HH90", CH582M 3-mode pads/61-key, a CH582F
  2.4 GHz receiver). Different boards, same module architecture; usable as a
  reference topology. Direct fetch is blocked (HTTP 418).
- `zerosensei/doc_3modekbd` (rendered at `doc-3modekbd.readthedocs.io`) — WCH's
  tri-mode keyboard development doc (hardware/software/low-power chapters).

**Not public:** there is **no Split65 schematic or netlist** anywhere (English,
Japanese, or Chinese). The `Epomaker` GitHub account's 33 repos are all QMK
firmware — no hardware. Related boards' schematics/maps *are* public (above), but
none is this board. The WCH vendor `CH583EVT.ZIP`/`SCHPCB.ZIP` eval-board design
requires "contact sales". The module's BLE stack, once recorded as a "binary
blob", is in fact a **symbolized `ar` archive** (`openwch/ch583`
`EVT/EXAM/BLE/LIB/LIBCH58xBLE.a`: 67 named objects, 10,410 exported functions,
disassemblable with `llvm-objdump`; the profile/app layer is full C source) — so
the module's behavior is readable even though its shipped factory image is not.
The `CH58xBLE_ROM*.hex` BASELIB is likewise public and likewise readable; despite
the name it is **not mask ROM** (the CH582/583 has no BLE stack in silicon — it is
the stack compiled separately, flashed to a fixed Flash region behind a jump
table, with `_ROM`/`_ROMx` differing only in load address), and WCH distributes it
normally. A
channel-by-channel sweep (OEM downloads, `hub.epomaker.com`, ODM `hangshengkeji`,
`oshwhub.com`, `gitee.com`, forums) is recorded in `HARDWARE.md` "The wireless
module (public information)": the board is a white-label ODMed product and the
netlist is not published. See `FINDINGS.md` for the conclusion.
