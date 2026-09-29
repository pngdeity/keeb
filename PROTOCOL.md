# EPOMAKER Split65 — Battery Reporting Protocol

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
  report ID; verified by reading its report descriptor). Host pull over 2.4 GHz
  **round-trips on real hardware**: writing `[0x00, 0xA4, ...]` to the dongle's
  raw interface reaches the keyboard and its reply comes back (observed: the
  current stock firmware answered `FF 00 00 ...`, i.e. its "unhandled command"
  sentinel, because it has no `0xA4` handler yet). Pull is therefore the expected
  path over 2.4 GHz; the push path is retained as a fallback (see Push mode).
- Bluetooth: in scope; delivery path under investigation (raw HID vs. BLE
  Battery Service `0x180F` / `0x2A19`).

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
| 1 | battery percentage, `0..100` |
| 2 | reserved — `0x00` (no voltage source on this hardware) |
| 3 | reserved — `0x00` |
| 4 | charging state: `0` discharging, `1` charging, `2` full |
| 5 | transport: `0x01` USB, `0x02` Bluetooth, `0x04` 2.4 GHz |
| 6 | model id (`KB_BATTERY_MODEL_ID`; `0` = unspecified) |
| 7..31 | `0x00` |

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

- enabled by `WLS_BATTERY_PUSH_ENABLE` (see `config.h`),
- emitted only on the split master half,
- emitted only while `md_getp_state()` reports `MD_STATE_CONNECTED`.

Hosts reading over a dongle can use either `--listen` (accept push reports) or
`--pull` (request/reply); both work now that the dongle's host→keyboard path is
confirmed.

## Verifying pull over 2.4 GHz (hardware — already confirmed working)

The keyboard-side tunnel exists: `md_raw.c` maps `md_receive_raw_cb()` →
`raw_hid_receive()`, and `module.c` forwards received raw packets
(`MD_RAW_SIZE = 32`) to that callback. The host side was confirmed on real
hardware: writing the request to the dongle's raw interface reached the keyboard
and its reply came back over the radio.

Probe: with the dongle attached and the keyboard switched to 2.4 GHz (`KC_2G4`),
run `python3 host/battery_polybar.py --pull`, or use the standalone
`/tmp/opencode/split65-dongle-probe.sh`. The host enumerates by usage page
`0xFF60`/usage `0x61` and selects the dongle's interface 2. Before flashing our
firmware the reply is `FF ...` (stock firmware has no `0xA4` handler); after
flashing it is the `0xA4` battery report. A read timeout means the pull path did
not complete on that attempt — the push path then covers it.
