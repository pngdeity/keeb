# EPOMAKER Split65 — Battery Reporting Protocol

> **Scope.** This documents the protocol implemented by the **battery-feature
> build** (committed in the `qmk_firmware` submodule as `wls/wls_battery.c`; the
> halves currently run an older build of it). On a stock/vendor build with no
> responder, the raw HID interface answers with an unhandled `FF` sentinel
> instead. See `TODO.md` Status.

Raw HID command used by the host to read the keyboard battery over all
transports. The command id `0xA4` (`KC_GET_BATTERY_LEVEL`) follows the
community/Keychron convention (Keychron `qmk_firmware` PR #504), where
**response byte 1 is the battery percentage**. The additional fields below are
a backwards-compatible extension; hosts must ignore bytes they do not know.

## Transport / interface

- Raw HID interface: usage page `0xFF60`, usage `0x61`, report size `RAW_EPSIZE`
  = **32 bytes**, in both directions, always.
- USB-wired: host **pulls** (sends the request; keyboard replies).
- 2.4 GHz dongle: the dongle exposes a second raw HID collection with the same
  `0xFF60`/`0x61` usage page and **32-byte IN and OUT reports** (interface 2, no
  report ID; verified by reading its report descriptor, below). Host pull over
  2.4 GHz **round-trips on real hardware**. Pull is the normal path; push is a
  fallback (see Push mode).
- **Host-side interface selection matters.** The keyboard's own raw collection is
  interface 1 and the dongle's is interface 2, and both are present whenever the
  keyboard is plugged in *and* the dongle is attached. `host/battery_polybar.py`
  enumerates every match and **prefers interface 2 (the dongle)** by default,
  falling back to the only collection present; `--transport usb` reads the
  keyboard's own collection instead. `split65.py check` reports which collections
  are present. (This was `TODO.md` defect 3; the code is fixed, a confirmation run
  with the dongle attached is still outstanding.)
- Bluetooth: in scope. Not yet probed on hardware — unknown whether the BT HID
  link exposes the raw HID collection (`0xFF60`/`0x61`) and whether
  `*md_getp_bat()` is populated over BT. The host falls back to the BLE Battery
  Service `0x180F` / Battery Level `0x2A19` (via `bluetoothctl`).

### Dongle raw HID interface (verified)

Report descriptor of the 2.4 GHz dongle (`342d:e4c6`) interface 2, obtained with
`HIDIOCGRDESC` (34 bytes, no report ID):

```
06 60 ff        Usage Page 0xFF60      <- QMK RAW_USAGE_PAGE
09 61           Usage 0x61             <- QMK RAW_USAGE_ID
a1 01           Collection (Application)
  09 62  15 00 26 ff 00  95 20 75 08  81 02   -> 32-byte Input  (keyboard -> host)
  09 63  15 00 26 ff 00  95 20 75 08  91 02   -> 32-byte Output (host -> keyboard)
c0
```

Matches `tmk_core/protocol/usb_descriptor_common.h` (`RAW_USAGE_PAGE 0xFF60`,
`RAW_USAGE_ID 0x61`) and `RAW_EPSIZE 32` exactly. Because the collection declares
no report ID, `data[0]` is the first data byte and the host's `0x00` report-ID
prefix is the correct convention for an unnumbered collection.

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
| 1 | battery percentage, `0..100` — **see the caveat below** |
| 2 | reserved — `0x00` (no voltage source on this hardware) |
| 3 | reserved — `0x00` |
| 4 | charging state: `0` discharging, `1` charging, `2` full |
| 5 | transport: `0x01` USB, `0x02` Bluetooth, `0x04` 2.4 GHz |
| 6 | model id (`KB_BATTERY_MODEL_ID`; `0` = unspecified) |
| 7..31 | `0x00` |

> **Byte 1 is not yet a measurement.** The keyboard has no ADC; the value only
> ever arrives from the wireless module, and on USB the module does not answer,
> so `md_info.bat` keeps its compile-time init of `100`. A host cannot
> distinguish "really 100%" from "never reported" today. Defect 1 in `TODO.md`
> tracks the fix; until then, treat byte 1 as unverified.

If the command is not recognised, the keyboard sends **no reply** (the raw HID
contract is one report in, at most one report out; an unsolicited response would
collide with other raw HID clients). The host must tolerate a read timeout.

Bytes 2-3 follow the Keychron `0xA4` layout (cell voltage, little-endian mV) but
this board's wireless module reports only a percentage, so they are always `0`.
Hosts must treat byte 1 as the authoritative value and ignore bytes 2-3.

## Push mode (2.4 GHz)

When running over a non-USB transport while connected, the keyboard emits the
same reply report unprompted every `WLS_BATTERY_PUSH_INTERVAL` (default
`2000 ms`). This path needs no host request, so it is robust against a missed
pull. Push is:

- enabled by `WLS_BATTERY_PUSH_ENABLE` (a `config.h` knob in the battery-feature
  build),
- emitted only on the split master half,
- emitted only while `md_getp_state()` reports `MD_STATE_CONNECTED`.

Hosts reading over a dongle can use either `--listen` (accept push reports) or
`--pull` (request/reply); both work now that the dongle's host→keyboard path is
confirmed.

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
