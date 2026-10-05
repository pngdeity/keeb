# EPOMAKER Split65 — Battery reporting: findings and design

> **Scope.** This narrates the **battery-feature work** (our parked `nathan`
> firmware). The current tree holds **vendor source**: the layered helpers below
> (`wls/wls_battery.c`, `WLS_BATTERY_PUSH_*`, the strong `raw_hid_receive`
> override) are **not** in it. The findings about how the vendor stack works
> still apply. See `TODO.md` Status.

Why the firmware is shaped the way it is, and which upstream facts a future
change depends on. What the device is is in `DEVICE.md`; measured hardware facts
live in `HARDWARE.md`; the wire format is `PROTOCOL.md`; live status and open
work are in `TODO.md`.

## Goal

Expose the keyboard battery to the host over all three transports (2.4 GHz
dongle, Bluetooth, USB-C) via the `0xA4` raw HID command, so a polybar module
can display it. Transport logic is layered so every transport shares one code
path.

## Hardware / firmware base

- MCU **WB32FQ95** (Artery WB32), bootloader **wb32-dfu**.
- Upstream is `github.com/hangshengkeji/qmk_firmware`, branch `tri-mode`, which
  contains `keyboards/epomaker/epomaker_split65/` and the wireless stack at
  `keyboards/linker/wireless/` (pulled in by the board's `post_rules.mk`). There
  is **no** `keyboards/wireless/` in this tree.
- The board source is a sibling port of the same EPOMAKER board found in
  `qmk/qmk_firmware`; that upstream tree is newer but lacks the wireless stack,
  so re-basing would invalidate all hardware verification (`TODO.md`, Tier 4).

## KEY FINDING — the battery value already exists in firmware

The wireless stack tracks it; the board only had to route it to the host. All
paths are in `qmk_firmware/keyboards/linker/wireless/`:

- `module.c`: `md_info_t.bat` is updated from the wireless module via
  `MD_REV_CMD_BATVOL (0x5C)` → `md_info.bat = md_rev_payload[1];`, read through
  `uint8_t *md_getp_bat(void)`.
- The keyboard has **no ADC** and never measures its own charge. It asks the
  module: `md_inquire_bat()` → `md_send_devctrl(MD_SND_CMD_DEVCTRL_INQVOL)`
  (`0x53`), driven every `WLS_INQUIRY_BAT_TIME` (3000 ms) from `wireless_task()`
  (`wireless.c`).
- `uint8_t *md_getp_state(void)` gives the link state, compared against
  `MD_STATE_CONNECTED`.
- `charging_state` and `bat_full_flag` are board-level GPIO reads
  (`HS_BAT_CABLE_PIN` / `BAT_FULL_PIN`), not module telemetry — see
  `HARDWARE.md`.
- `KC_BATQ` already existed to request the *visual* indicator. The work was to
  route the value to the host.

## KEY FINDING — raw HID is already bridged over the 2.4 GHz dongle

`keyboards/linker/wireless/md_raw.c` (guarded by `RAW_ENABLE`):

- `replaced_hid_send()` uses the USB endpoint on `TRANSPORT_USB`, otherwise
  `md_send_raw()` tunnels over the module UART.
- `md_receive_raw_cb()` calls `raw_hid_receive(data, length)`.
- The tunnel carries `MD_RAW_SIZE = 32`-byte reports in **both** directions, so
  host pull works over 2.4 GHz as well as USB. Push is retained as a fallback
  only.

This matters because it is why no custom transport code was needed: the vendor
stack already forwards raw HID both ways.

## Design

Layered so the transports share one code path. Wire format: `PROTOCOL.md`.

1. **Battery source abstraction** (`wls/wls.c`): `kb_battery_percent()` (clamps
   `*md_getp_bat()` to 0-100), `kb_charging_state()` (0/1/2 from
   `charging_state` / `bat_full_flag`), `kb_transport_byte()` (from
   `wireless_get_current_devs()`), and `kb_battery_report_fill()` (assembles the
   32-byte reply).
2. **Raw HID responder** (`wls/wls_battery.c`): a strong `raw_hid_receive()`
   override (`#ifndef VIA_ENABLE`) that replies to `0xA4` and stays silent for
   any other command — an unsolicited reply would collide with other raw HID
   clients. Master half only.
3. **Transport tagging**: `0x01` USB / `0x02` BT / `0x04` 2.4 GHz.
4. **Push fallback**: `kb_battery_push_task()` is called from the existing
   `wireless_post_task()` and emits the reply every
   `WLS_BATTERY_PUSH_INTERVAL` (2000 ms) when non-USB, connected, and master.
   Gated by `WLS_BATTERY_PUSH_ENABLE`.
5. **Host side** (`host/battery_polybar.py`): enumerates by usage page `0xFF60` /
   usage `0x61`; supports `--pull`, `--listen` and `--bluetooth` (BLE Battery
   Service `0x180F`/`0x2A19` fallback), prints `BAT <n>%` / `CHG <n>%`, and
   hides when absent.
6. **Bluetooth path**: still unprobed. Open question is whether the BT HID link
   exposes the raw collection and whether `*md_getp_bat()` is populated over BT;
   the host falls back to BLE either way. Tracked in `TODO.md`.

## Build facts

- Build from `qmk_firmware/`: `make epomaker/epomaker_split65:<keymap>`. Current
  sizes and artifact md5s are recorded in `TODO.md` Status — they change with
  every keymap edit, so treat them as a freshness check, not a constant.
- `raw_hid_receive` links as a strong `T`, overriding the weak default at
  `tmk_core/protocol/chibios/usb_main.c:539`.
- **VIA is not enabled** (`VIA_ENABLE` unset), so the hook is the strong
  `raw_hid_receive()` override, not `via_command_kb()`. The VIA definition
  (`host/epomaker-split65-via.json`) is for external VIA tooling and keymap
  import; it is
  not a claim that the firmware speaks VIA.
- `raw_hid_send`'s macro remap in `md_raw.h` is **line-specific**, so new code
  must call `replaced_hid_send()` directly.

## Dongle recon

Device `342d:e4c6` "MILE 2.4G Dongle", three HID interfaces:

- iface 0: keyboard, mouse, consumer, system, LEDs, plus a vendor block.
- iface 1: 120-key bitmap, no report ID.
- iface 2: the raw HID tunnel — usage page `0xFF60`, usage `0x61`, 32-byte IN
  and OUT. Identical to QMK's own raw collection.

Full device description: `DEVICE.md` "Accessories".

`hid.enumerate()` confirms exactly one `0xff60/0x61` interface on the dongle.
A live probe writing `[0x00, 0xA4, ...]` to it reaches the keyboard over the
radio and the reply comes back.

The dongle firmware is **not** in the QMK tree. Dumping it would require
entering its DFU bootloader (physical BOOT pads, same as the keyboard); the
optional command is
`wb32-dfu-updater_cli -t -s 0x08000000 -U dongle.bin`. Not done, not required.

## Open questions tied to these findings

- **Is byte 1 ever real?** See `TODO.md` defect 1. Until the module answers the
  inquiry on USB, the value is indistinguishable from the init constant.
- **Which interface did the host pick?** See `TODO.md` defect 3.
- **Does Bluetooth expose the raw collection at all?** See `TODO.md`, Tier 2.
