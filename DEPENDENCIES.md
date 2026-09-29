# Dependencies

## Build (firmware)

- QMK build toolchain as shipped in `qmk_firmware/` (ChibiOS/ChibiOS-Contrib
  git submodules — run `make git-submodule` in `qmk_firmware/` if `lib/` is
  empty).
- `arm-none-eabi-gcc` (Arch: `arm-none-eabi-gcc`), `make`, `python3`.
- Build and flash commands (from `qmk_firmware/`):

  ```sh
  make epomaker/epomaker_split65:default   # stock keymap
  make epomaker/epomaker_split65:nathan    # nathan keymap (custom bindings)
  ```

- Or use the project helper: `./split65.py build` / `./split65.py flash` /
  `./split65.py check` / `./split65.py setup` (see `--help`). It builds and
  flashes the `nathan` keymap (built artifact:
  `qmk_firmware/epomaker_epomaker_split65_nathan.bin`).
- **`split65.py flash` and the raw `wb32-dfu-updater_cli` are for a human to
  run.** `flash` calls `doas` and prompts with `input()`, so it must not be
  launched by an agent or any non-interactive context: an unanswered `doas`
  prompt locks the account after three failed attempts.

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
  - **Left (master):** hold **Esc** while plugging in USB (this also erases
    settings), or tap the `QK_BOOT` key (matrix `[0,0]`), or the physical reset
    switch on the PCB underside.
  - **Right (slave):** Esc-hold does **not** work. Remove the `R_Shift` keycap,
    flip the hidden toggle switch to the bottom, then short the two holes under
    the spacebar switch with tweezers while plugging in the right half's USB-C
    cable. Toggle the switch back afterwards.

## Keyboard reference

### Recovery / DFU entry

| Method | How | Effect |
|---|---|---|
| Hardware DFU | Hold reset button (PCB underside) + plug USB | Always works |
| Bootmagic DFU | Hold Escape + plug USB (left half only) | Bootloader, clears EEPROM |
| Right-half DFU | R_Shift toggle + spacebar-pin short + plug USB | Bootloader (see Flashing) |
| Software DFU | `QK_BOOT` key (Fn layer `[0,0]`) | Bootloader |
| Factory reset | Hold `Fn+Backspace` ~3 s (`EE_CLR` on Fn layer) | Clears EEPROM settings |

### Wireless modes

| Key | Action |
|---|---|
| `Fn+Q` / `Fn+W` / `Fn+E` | Bluetooth device 1 / 2 / 3 (`KC_BT1`/`KC_BT2`/`KC_BT3`) |
| `Fn+R` (hold 3-5 s) | 2.4 GHz dongle / re-pair (`KC_2G4`) |
| `Fn+B` | Battery indicator (`KC_BATQ`); keys 1-0 light to show percent |

Auto-switch: inserting the USB cable switches to wired and remembers the
previous wireless transport; removing it restores that transport.

### Notable keymap features (nathan keymap)

| Combo | Effect |
|---|---|
| Shift+Esc | `~` (key override) |
| GUI+Esc | `` ` `` (key override) |
| Shift+Backspace | Delete (key override) |
| Right Space (hold) | Fn layer (`LT(_FL, KC_SPC)`) |
| Encoder, Fn/MacFn layers | RGB brightness instead of volume |

The `nathan` keymap enables `KEY_OVERRIDE_ENABLE` and `CAPS_WORD_ENABLE`.

## VIA

- Definition: `EPOMAKER Split65.json` (project root). Load in VIA with
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

The `qmk_firmware/` checkout carries compatibility changes on top of the
vendored upstream snapshot. They live in the tree (and are tracked when it is
committed), and must be re-applied if the tree is reset or re-cloned:

- `lib/python/qmk/math.py`: replace the removed `ast.Num` with `ast.Constant`
  (Python 3.12+).
- `keyboards/epomaker/epomaker_split65/post_rules.mk`: include paths
  `keyboards/leo/...` → `keyboards/epomaker/...`.
- `keyboards/epomaker/epomaker_split65/keyboard.json`: reformatting plus
  `features.raw: true`.
