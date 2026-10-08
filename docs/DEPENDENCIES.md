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

## Flashing

- `wb32-dfu-updater_cli` (present at `/usr/local/bin/wb32-dfu-updater_cli`).
  Flash with `wb32-dfu-updater_cli -t -s 0x08000000 -D <bin>` then
  `wb32-dfu-updater_cli -R` to reset. **Wired USB is required**; 2.4 GHz /
  Bluetooth cannot flash.
- **Prerequisite:** the wb32-dfu udev rule must be installed or the updater
  cannot claim the device as a normal user. `qmk doctor` reports this as
  "Missing or outdated udev rules for 'wb32-dfu' boards". The rule (from
  `qmk_firmware/util/udev/50-qmk.rules`) is:

  ```
  SUBSYSTEMS=="usb", ATTRS{idVendor}=="342d", ATTRS{idProduct}=="dfa0", TAG+="uaccess"
  ```

- **Both halves run identical firmware** — handedness is pin-based
  (`split.handedness.pin`, read by `is_keyboard_master()`), not EEPROM-based, so
  there are no `-split-left`/`-split-right` variants. Each half is flashed
  separately, and they enter DFU by **different** means:
  - **Left (master):** remove the spacebar, **short the two metal-plated holes**
    the spacebar switch's feet sit in, and plug in USB-C **while still shorting**.
    Esc-hold (bootmagic) works on stock firmware but is **broken on our build**;
    there is also no reset switch on this half (an earlier claim to the contrary
    was unverified and wrong).
  - **Right (slave):** Esc-hold does **not** work. Remove the `R_Shift` keycap,
    flip the hidden toggle switch to the bottom, then short the two holes under
    the spacebar switch with tweezers while plugging in the right half's USB-C
    cable. Toggle the switch back afterwards.

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
| Right-half DFU | R_Shift toggle + spacebar-pin short + plug USB | Bootloader (see Flashing) |
| Software DFU | `QK_BOOT` — base layer at left half, matrix `[1,0]` (the left `Esc` position) | Bootloader |
| Factory reset | `EE_CLR` — hold-only `_RST` layer at right half, matrix `[11,7]` (the bottom-right corner key) | Clears EEPROM settings |

> `QK_BOOT` sits on the **base** layer at the left half's `Esc` position, where it
> is trivially hit — an accidental tap drops the left half into the bootloader
> (accepted; it is the intended software DFU route). `EE_CLR` was moved off the
> Fn-layer `Bksp` position to the far corner of a hold-only layer: `_RST` is
> armed only by `LT(_RST, KC_NO)` on the **Fn-layer top-right corner** key, so a
> wipe needs a held Fn chord plus a press on the opposite half's bottom-right
> corner. It is no longer reachable by a single stray hold.

### Wireless modes

| Key (Fn layer) | Matrix | Action |
|---|---|---|
| `KC_BT1` / `KC_BT2` / `KC_BT3` | `[2,1]` / `[2,2]` / `[2,3]` (left half) | Bluetooth device 1 / 2 / 3 |
| `KC_2G4` | `[2,4]` (left half) | 2.4 GHz dongle |
| `KC_BATQ` | `[5,5]` and `[11,1]` (both spacebars) | Request the battery indicator |

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

- `lib/python/qmk/math.py`: replace the removed `ast.Num` with `ast.Constant`
  (Python 3.12+).
- `keyboards/epomaker/epomaker_split65/post_rules.mk`: include paths
  `keyboards/leo/...` → `keyboards/epomaker/...`.
- `keyboards/linker/wireless/wireless.c`: drop the leading blank line before the
  license header (QMK's lint reads line 1 literally). Shared file, benefits every
  board that uses the stack.

If you reset the tree to pristine upstream and find the build broken, this is the
first thing to check.
