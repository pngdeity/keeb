# EPOMAKER Split65 — Battery reporting (Option D) — Research Findings

## Target
Expose keyboard battery percentage to the host over **all three transports** (**2.4GHz
dongle**, **Bluetooth**, **USB-wired**), so a polybar module can display it. 2.4GHz is
primary; USB-wired is useful while charging; **Bluetooth is in scope** and must be read
over too. Keep transport logic modular so every transport shares one code path.

## Hardware / firmware base
- MCU: **WB32FQ95** (Artery WB32 series), bootloader **wb32-dfu**.
- Vendor firmware (Hangsheng "tri-mode" lineage) is open:
  - `github.com/hangshengkeji/qmk_firmware` branch **`tri-mode`** — contains
    `keyboards/epomaker/epomaker_split65/` (the real upstream for this board).
  - The wireless stack is `keyboards/linker/wireless/` (included via the board's
    `post_rules.mk`). There is **no** `keyboards/wireless/` in this tree — earlier
    notes that cited that path were wrong.
- Community mirrors: `zozonteq/epomaker_split65` (older, single-file, no `quantum/`),
  `Epomaker/Split65`. Upstream `hangshengkeji` is the authoritative base.

## KEY FINDING — battery data ALREADY EXISTS in firmware
The wireless stack tracks battery internally. All paths below are in
`qmk_firmware/keyboards/linker/wireless/`:

- `module.c`: `md_info_t` has field `uint8_t bat;`, updated from the dongle/BT
  module via `MD_REV_CMD_BATVOL (0x5C)` → `md_info.bat = md_rev_payload[1];`
  Accessor: `uint8_t *md_getp_bat(void);`
- The dongle reports the value; the keyboard does **not** read an ADC itself. The
  keyboard periodically asks the dongle: `md_inquire_bat()` →
  `md_send_devctrl(MD_SND_CMD_DEVCTRL_INQVOL /*0x53*/)`, driven every
  `WLS_INQUIRY_BAT_TIME` (3000 ms) from `wireless_task()` (`wireless.c`).
- `uint8_t *md_getp_state(void)` reports the link state, compared against
  `MD_STATE_CONNECTED`.
- `bool charging_state;` and `bool bat_full_flag;` are defined in
  `keyboard/epomaker/epomaker_split65.c` from the `HS_BAT_CABLE_PIN` and
  `BAT_FULL_PIN` GPIOs.
- `KC_BATQ` keycode (Fn+B) already exists: it triggers the *visual* battery
  indicator (`bat_indicators()`) rather than reporting to the host. So the
  battery-trigger path is proven; the work was to route the value to the host.

## KEY FINDING — raw HID is ALREADY bridged over the 2.4GHz dongle, both ways
`keyboards/linker/wireless/md_raw.c` (guarded by `RAW_ENABLE`):
- `replaced_hid_send()` → if `TRANSPORT_USB` uses USB endpoint, else `md_send_raw()`
  (tunneled over UART/dongle as `MD_SND_CMD_RAW 0xAF` / `MD_SND_CMD_RAW_IN 0x61`).
- `md_receive_raw_cb()` → calls `raw_hid_receive(data, length)`.
- `module.c:435` `md_send_raw()` and `module.c:115-116` `md_receive_raw_cb()` show the
  tunnel carries `MD_RAW_SIZE = 32`-byte reports in **both** directions.

**Correction (2026-09-29, hardware recon + live probe):** the earlier claim that the
dongle does **not** forward host → keyboard raw HID is **wrong for this hardware**.
Reading the dongle's report descriptors shows interface 2 is a vendor raw HID
collection with usage page `0xFF60`, usage `0x61`, and **32-byte IN and OUT
reports** — the same interface QMK exposes on the keyboard. A live probe confirmed
the round-trip: writing `[0x00, 0xA4, ...]` to the dongle's raw interface reached
the keyboard over the radio and its reply came back (`FF 00 00 ...`, the stock
firmware's "unhandled command" sentinel, since it has no `0xA4` handler yet).
Host → keyboard pull over 2.4 GHz is therefore **proven viable**; the push path is
retained as a fallback only.
(Caveat observed on stock 2.4G firmware: some VIA/Vial commands return `unhandled`
(`0xFF`) because the stock build was compiled without the needed handlers.)

## Implementation plan — VERIFIED AND IMPLEMENTED
Layered so transports share one code path. Reference: `PROTOCOL.md`.

> Corrections applied after verifying against source and upstream docs
> (2026-09-29): the wireless stack is `keyboards/linker/wireless/`; `VIA_ENABLE`
> is **off** so the hook is a strong `raw_hid_receive()` override (**not**
> `via_command_kb()`); the 2.4 GHz dongle **does** bridge host → keyboard raw HID
> — verified live — so pull over 2.4 GHz works and push is only a fallback; and
> `raw_hid_send`'s macro remap is line-specific, so new code calls
> `replaced_hid_send()` directly.

1. **Battery source abstraction** (done): in `wls/wls.c` —
   `kb_battery_percent()` (clamps `*md_getp_bat()` to 0–100),
   `kb_charging_state()` (0/1/2 from `charging_state` / `bat_full_flag`),
   `kb_transport_byte()` (from `wireless_get_current_devs()`), and
   `kb_battery_report_fill()` (assembles the 32-byte reply).
2. **Raw-HID responder** (done): `wls/wls_battery.c` defines a strong
   `raw_hid_receive()` (`#ifndef VIA_ENABLE`), replies to `0xA4` with
   `{0xA4, percent, volt_lo, volt_hi, charging, transport, model}` (32 bytes),
   and stays silent for any other command (the raw HID contract is one report in,
   at most one report out; an unsolicited reply would collide with other raw HID
   clients). Master half only.
3. **Transport tagging** (done): `transport` = 0x01 USB / 0x02 BT / 0x04 2.4G.
4. **2.4 GHz push (fallback)**: `kb_battery_push_task()` is called from the
   existing `wireless_post_task()` in `epomaker_split65.c`; emits the reply every
   `WLS_BATTERY_PUSH_INTERVAL` (2000 ms) when non-USB, connected, and master.
   Gated by `WLS_BATTERY_PUSH_ENABLE`. Retained as a fallback because pull over
   2.4 GHz is proven to work; hosts may prefer pull, with push guaranteeing a
   value when a pull attempt is missed.
5. **Bluetooth path (in scope, probe pending)**: on-device probe still required
   to settle (a) whether the BT HID link exposes the vendor raw-HID collection
   (usage 0xFF60/0x61) and (b) whether `*md_getp_bat()` is populated over BT.
   Fallback: BLE **Battery Service 0x180F / Battery Level 0x2A19**, read by the
   host script via `bluetoothctl`.
6. **Host side** (done): `host/battery_polybar.py` (Python `hid`) enumerates by
   usage page 0xFF60 / usage 0x61, supports `--pull` (USB), `--listen` (2.4 GHz
   push), and `--bluetooth` (BLE fallback); prints `BAT <n>%` / `CHG <n>%` and
   hides when absent. See `host/README.md`.

## Build / flash facts (verified)
- Build: `make epomaker/epomaker_split65:default` from `qmk_firmware/`.
  Current sizes (after all changes):
  - `default` — **63160** bytes (`f6b8`)
  - `nathan` — **64932** bytes (`fda4`)
  The stock (pre-change) bin was 62644 bytes.
- Symbols: `raw_hid_receive` links as a strong `T` (the weak default at
  `tmk_core/protocol/chibios/usb_main.c:539` is overridden).
- The dongle (VID 342D / PID E4C6) firmware is **not** in the QMK tree, but the
  device exposes a `0xFF60/0x61` raw HID interface with a 32-byte OUT report
  (interface 2, no report ID). See the dongle recon section below.
- Two keyboard halves (split) must be flashed separately, and they enter DFU by
  **different** means (see Flashing).

## Dongle recon (2026-09-29, read-only + live probe)
Device `342d:e4c6` "MILE 2.4G Dongle", three HID interfaces:
- iface 0 (hidraw3): 210-byte descriptor, report IDs 1-5 — keyboard, mouse,
  consumer, system, LEDs, plus a vendor `0x0001/0x0000` block.
- iface 1 (hidraw4): 43-byte descriptor, no report ID — 120-key bitmap.
- iface 2 (hidraw5): 34-byte descriptor, no report ID — **raw HID tunnel**:
  usage page `0xFF60`, usage `0x61`, 32-byte Input and 32-byte Output. Identical
  to QMK's own raw collection.
- `hid.enumerate()` confirms exactly one `0xff60/0x61` interface on the dongle.
- **Live probe result:** writing `[0x00, 0xA4, <30 zero bytes>]` to hidraw5
  returned `ff 00 00 ...` — the stock keyboard firmware received the request over
  the radio and replied with its unhandled sentinel. The host → dongle → keyboard
  → dongle → host round-trip works over 2.4 GHz.
- Descriptors read with `HIDIOCGRDESC` (Python's `fcntl.ioctl` rejects the
  4096-byte `hidraw_report_descriptor` struct; a small C helper is required).
- DFU dump **not yet possible**: `wb32-dfu-updater_cli -l` → "Not found device!";
  the dongle is in application mode (`e4c6`) and no `342d:dfa0` DFU device is
  present. Entering DFU needs the physical BOOT pads shorted, same as the
  keyboard. Optional follow-up: `wb32-dfu-updater_cli -t -s 0x08000000 -U
  dongle.bin` to preserve the factory image for inspection.

## Recon / probe scripts
Two throwaway scripts under `/tmp/opencode/` (outside the repo) were used for
the pre-flash reconnaissance. They are not part of the project and may not
survive a reboot; their findings are recorded above and in `PROTOCOL.md`, so
they do not need to be re-run to understand the design.

- `/tmp/opencode/split65-recon.sh` — elevated diagnostics (dmesg, udev state, DFU
  scan, descriptor dump, block devices). `--flash-udev-rule` optionally installs
  the wb32-dfu udev rule. Writes reports to `/tmp/opencode/recon/`.
- `/tmp/opencode/split65-dongle-probe.sh` — enumerates HID interfaces, dumps the
  raw interface descriptor, sends the `0xA4` request and listens for a reply.
  This is the tool that proved the 2.4 GHz pull round-trip.

## Flashing
- Tool present: `/usr/local/bin/wb32-dfu-updater_cli` (supports `--list`, `--download`,
  `--upload`, `--toolbox-mode`, `--wait`). Compatible with `wb32` DFU bootloader.
- Command (matches QMK `lib/python/qmk/flashers.py` and the `:flash` make target):
  `wb32-dfu-updater_cli -t -s 0x08000000 -D <bin>`, then `wb32-dfu-updater_cli -R`
  to reset into application mode. The `.bin` is a raw `objcopy -O binary` starting
  at `0x08000000`, so the start address is correct.
- **Both halves run identical firmware.** Handedness is pin-based
  (`keyboard.json` `split.handedness.pin = B9`, read by `is_keyboard_master()` in
  `keymaps/default/keymap.c`), not EEPROM-based, so there are no
  `-split-left`/`-split-right` variants to flash.
- Enter bootloader — the two halves differ:
  - **Left (master):** hold **Esc** while plugging in USB (this also erases
    settings), or tap the `QK_BOOT` key (mapped at matrix `[0,0]`), or the
    physical reset switch on the PCB underside.
  - **Right (slave):** Esc-hold does **not** work. Per Epomaker's own guidance:
    remove the `R_Shift` keycap, flip the hidden toggle switch to the bottom,
    then short the two holes under the spacebar switch with tweezers while
    plugging in the right half's USB-C cable. Toggle the switch back to the top
    afterwards. (Confirmed by two independent community reports; one recovered a
    bricked master with the same spacebar-pad short.)
- **Wired USB required** to flash (WB32 DFU is a USB bootloader). 2.4G/BT cannot flash.
- **Prerequisite:** wb32-dfu udev rules must be installed or the updater cannot
  claim the device as a normal user. `qmk doctor` flags this. The rule is the
  wb32 line from `qmk_firmware/util/udev/50-qmk.rules`:
  `SUBSYSTEMS=="usb", ATTRS{idVendor}=="342d", ATTRS{idProduct}=="dfa0", TAG+="uaccess"`.

## Hardware verification status (2026-09-29)
- **Left half: UPGRADED AND VERIFIED.** Flashed over wired USB and tested:
  `python3 host/battery_polybar.py --pull` returns `CHG 100%`. The raw report
  was `a4 64 00 00 01 01 01 ...` — byte 0 `0xA4`, byte 1 `100`, bytes 2-3 `00 00`
  (reserved), byte 4 `1` (charging), byte 5 `01` (USB), byte 6 `01` (model id).
  Every field matches `PROTOCOL.md`.
- The flashed firmware identifies as manufacturer **`LEO`** (`bcdDevice 0.30`);
  the stock firmware was **`MILE`** (`bcdDevice 0.0b`). This is the quickest way
  to tell whether a half has our firmware: `lsusb` / the device string.
- Esc-hold DFU re-entry still works after flashing (no lockout). The WB32
  bootloader lives at `0x1FFFE000`, outside the 128 KB application region we
  write at `0x08000000`, so a normal flash cannot damage it.
- **Right half: NOT yet flashed.** Its DFU entry requires the R_Shift toggle +
  spacebar-pin short (see Flashing). `TODO.md` tracks making this key-based.
- 2.4 GHz: the host→dongle→keyboard→dongle→host round-trip was proven with the
  stock firmware (reply `FF ...`); it will return a real `0xA4` report once both
  halves carry our firmware.
- Bluetooth: not yet probed on hardware.

## External software needed
See DEPENDENCIES.md.

## Repository consolidation (2026-09-29)

A second, earlier project (`incubating/keeb/`) held the same keyboard's files.
It has been merged into this one and removed; this project's directory was then
renamed to `keeb`.

Key finding — the two vendored QMK trees differ in age and provenance:

- This project's `qmk_firmware/` is a **1-commit squashed snapshot** of
  `hangshengkeji/qmk_firmware` branch `tri-mode` (HEAD `580665f7`, dated
  2026-01-20). It is the only tree containing the wireless/tri-mode stack
  (`keyboards/linker/wireless/`) that the radio and this battery work depend on.
- The old `keeb` project's `qmk_firmware/` was **real upstream**
  `qmk/qmk_firmware` branch `master` (HEAD `486f01f513`, dated 2026-06-04,
  29,551 commits) — ~4.5 months newer, **without** the wireless stack.
- The keyboard source itself existed in both as **sibling ports of the same
  EPOMAKER board**, not one being newer-and-better. The old `keeb` tree's
  `leo/epomaker_split65/` carried the EPOMAKER copyright, newer WS2812 usage,
  `HS_MATRIX_BAT_SOFT_INDEX`, and a USB cable-detect auto-switch fix; this
  tree carried the sleep RPC handlers (`0xAA`/`0xBB`/`0xCC`), the battery work,
  `SERIAL_USART_*_PAL_MODE`, and `is_keyboard_master()` guards that the other
  tree had dropped.

Decision: **keep this tree** (the flashed-and-verified battery work) and port
the genuinely-unique additions from the old project:

- `keymaps/nathan/` (custom keymap: key overrides, `LT` spaces, encoder RGB
  brightness) — builds clean.
- `confinfo.last_wireless_devs` + EEPROM-migration validation.
- USB cable-detect transport auto-switch (`housekeeping_task_user`,
  `lpwr_wakeup_hook`).
- Battery soft-indicator at `HS_MATRIX_BAT_SOFT_INDEX`, **retaining** this
  tree's `is_keyboard_master()` guard.
- `EPOMAKER Split65.json` (VIA), `split65.py` (build/flash helper, paths
  adapted to this project and flash flags corrected to
  `-t -s 0x08000000 -D <bin>` + `-R`).

Deliberately **not** ported: the `eeconfig_read_keymap(&keymap_config)`
pointer-form modernization (this tree's QMK core has the older scalar API), and
the removed `is_keyboard_master()` guards.

Re-basing onto the newer upstream QMK is possible but would invalidate the
hardware verification of the battery work; it should be a deliberate, separately
tested change (see `TODO.md`).

`local-patches.diff` was deleted: every hunk it contained is already applied in
`qmk_firmware/`, and its documented contents now live in `DEPENDENCIES.md`.
`chunk87.bin` at the project root was kept; it is a keyboard flash artifact of
unclear origin and is excluded from version control by the root `.gitignore`
(`*.bin`). (The identically-named file inside `qmk_firmware/` is unrelated: a
ChibiOS demo resource at
`lib/chibios-contrib/demos/STM32/RT-STM32F429-DISCOVERY-DMA2D/res/chunk87.bin`.)
