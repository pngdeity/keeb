# EPOMAKER Split65 — Battery Reporting Protocol

> **Scope.** This documents the wire format of the battery responder and the
> host read path — the `0xA4` raw HID command and its reply. The *value* source
> is upstream QMK's battery API: the board supplies a `custom` battery driver
> (`wls/wls_battery_driver.c`) whose `battery_driver_sample_percent()` returns
> the wireless module's UART level, and the responder answers
> `battery_get_percent()` (`quantum/battery/`). The `kb_battery_*` helpers named
> below survive only as the responder's own framing/push logic; the percentage
> is no longer computed by them.
>
> The responder is committed in the `qmk_firmware` submodule as
> `wls/wls_battery.c` (branch `split65-overlay`). See `TODO.md` Status for
> build/hardware state, and `docs/FINDINGS.md` for the design rationale.

Raw HID command used by the host to read the keyboard battery over all
transports. The command id `0xA4` (`KC_GET_BATTERY_LEVEL`) follows the
community/Keychron convention (Keychron `qmk_firmware` PR #504), where
**response byte 1 is the battery percentage**. The additional fields below are
a backwards-compatible extension; hosts must ignore bytes they do not know.

## Transport / interface

- Raw HID interface: usage page `0xFF60`, usage `0x61`, report size `RAW_EPSIZE`
  = **32 bytes**, in both directions, always.
- USB-wired: host **pulls** (sends the request; keyboard replies).
- 2.4 GHz dongle: the dongle **shares the keyboard's VID:PID** (`342d:e4c6`) and,
  when seen, exposes a second raw HID collection with the same `0xFF60`/`0x61`
  usage page and **32-byte IN and OUT reports** (no report ID). **Unverified:** a
  dongle has never been confirmed on the bus in this project — its enumeration is
  documented upstream but was not observed live, so the interface mapping below is
  *assumed*, not measured (see `TODO.md` defect 3). Host pull over 2.4 GHz is
  claimed by the vendor to round-trip; it is untested here. Pull is the normal
  path; push is a fallback (see Push mode).
- **Host-side interface selection matters.** The keyboard's own raw collection is
  **interface 1** (measured). Because the dongle shares the VID:PID, it cannot be
  told apart from the keyboard by a simple match; `host/battery_polybar.py`
  enumerates every match and prefers `interface_number == 2` by default as an
  *assumed* dongle, falling back to the only collection present; `--transport usb`
  selects interface 1. `split65.py check` reports which collections are present.
  (This is `TODO.md` defect 3; the code is defensive, but the interface-2 = dongle
  mapping remains unconfirmed and cannot be tested until a working dongle is
  available.)
- Bluetooth: in scope. Not yet probed on hardware — unknown whether the BT HID
  link exposes the raw HID collection (`0xFF60`/`0x61`) and whether
  `*md_getp_bat()` is populated over BT. The host falls back to the BLE Battery
  Service `0x180F` / Battery Level `0x2A19` (via `bluetoothctl`).

### Dongle raw HID interface (assumed, unverified)

The descriptor below is **the generic QMK raw HID descriptor, not a live dump** —
no dongle has been confirmed on the bus, so nothing here was captured with
`HIDIOCGRDESC`. It is what the dongle would expose if it presents the standard QMK
raw collection (34 bytes, no report ID):

```
06 60 ff        Usage Page 0xFF60      <- QMK RAW_USAGE_PAGE
09 61           Usage 0x61             <- QMK RAW_USAGE_ID
a1 01           Collection (Application)
  09 62  15 00 26 ff 00  95 20 75 08  81 02   -> 32-byte Input  (keyboard -> host)
  09 63  15 00 26 ff 00  95 20 75 08  91 02   -> 32-byte Output (host -> keyboard)
c0
```

Matches `tmk_core/protocol/usb_descriptor_common.h` (`RAW_USAGE_PAGE 0xFF60`,
`RAW_USAGE_ID 0x61`) and `RAW_EPSIZE 32` (`tmk_core/protocol/usb_descriptor.h`).
Because the collection declares no report ID, `data[0]` is the first data byte
and the host's `0x00` report-ID prefix is the correct convention for an
unnumbered collection.

## Request (host → keyboard)

32-byte report. Only byte 0 is meaningful; remaining bytes zero.

| byte | value | meaning |
|------|-------|---------|
| 0 | `0xA4` | `KC_GET_BATTERY_LEVEL` |
| 1..31 | `0x00` | unused |

The host prepends a Report ID byte (`0x00`) when writing, per the QMK raw HID
convention, giving a 33-byte write.

## Reply (keyboard → host)

32-byte report.

| byte | meaning |
|------|---------|
| 0 | `0xA4` (echo) |
| 1 | battery percentage, `0..100` — **not yet a measurement: unverified; see below** |
| 2 | reserved — `0x00` (no voltage source on this hardware) |
| 3 | reserved — `0x00` |
| 4 | charging state: `0` discharging, `1` charging, `2` full |
| 5 | transport: `0x01` USB, `0x02` Bluetooth, `0x04` 2.4 GHz |
| 6 | model id (`KB_BATTERY_MODEL_ID`; board sets `1` = Split65, `0` = unspecified) |
| 7..31 | `0x00` |

> **Byte 1 is not yet a measurement.** The keyboard has no ADC; the value only
> ever arrives from the wireless module, and on USB the module does not answer,
> so `md_info.bat` keeps its compile-time init of `100`. A host cannot
> distinguish "really 100%" from "never reported" today. Defect 1 in `TODO.md`
> tracks the fix; until then, treat byte 1 as unverified. (When fixed, an
> unreported value will be reported distinctly rather than as `100`.)

If the command is not recognised, the keyboard sends **no reply** (the raw HID
contract is one report in, at most one report out; an unsolicited response would
collide with other raw HID clients). The host must tolerate a read timeout. Some
firmware lineages instead answer with an unhandled `FF` sentinel, but this has not
been observed on this hardware and is not part of the contract here.

If the command is not recognised, the keyboard sends **no reply** (the raw HID
contract is one report in, at most one report out; an unsolicited response would
collide with other raw HID clients). The host must tolerate a read timeout.

Bytes 2-3 follow the Keychron `0xA4` layout (cell voltage, little-endian mV) but
this board's wireless module reports only a percentage, so they are always `0`.
Hosts must treat byte 1 as the authoritative value and ignore bytes 2-3.

## Push mode (2.4 GHz)

When running over a non-USB transport while connected, the keyboard emits the
same reply report unprompted when a value changes (level, charge, or transport),
with `WLS_BATTERY_PUSH_INTERVAL` (default `10000 ms`) as a slow keepalive bound
on how stale an unchanged host view may become. This path needs no host request,
so it is robust against a missed pull. Push is:

- enabled by `WLS_BATTERY_PUSH_ENABLE` (a `config.h` knob in the battery-feature
  build),
- emitted only on the split master half,
- emitted only while `md_getp_state()` reports `MD_STATE_CONNECTED`.

Hosts reading over a dongle can use either `--listen` (accept push reports) or
`--pull` (request/reply); the vendor reports the dongle's host→keyboard path as
working, but it is **unconfirmed here** (no dongle has enumerated in this
project).

## Verifying the pull path

The keyboard-side tunnel exists: `md_raw.c` maps `md_receive_raw_cb()` →
`raw_hid_receive()`, and `module.c` forwards received raw packets
(`MD_RAW_SIZE = 32`) to that callback, so a host request reaches `0xA4` handling
over every transport.

To check the battery: put the keyboard in USB or 2.4 GHz mode and run
`python3 host/battery_polybar.py --pull` (or `--listen` for push reports). The
host enumerates by usage page `0xFF60` / usage `0x61`. **Verify the interface it
picked before trusting the transport byte** — with keyboard and dongle both
attached, a first-match selection returns the keyboard's USB interface
(`TODO.md` defect 3). A read timeout means the pull did not complete on that
attempt; the push path then covers it.

What a successful pull proves and does not prove:

- It proves the transport plumbing works end to end (request out, reply back).
- It does **not** prove byte 1 is real. On USB, byte 1 is the module's init
  constant (`100`); only the radio path has ever been seen to carry a value that
  responds to actual use. See the byte-1 caveat above and `TODO.md` defect 1.
