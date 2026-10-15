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

> **The transport underneath is the WCH CH582F module protocol, and it is
> public.** The `0xA4` command above is the *host-facing* wire (ours). The
> keyboard-to-module link that supplies the percentage is a documented
> third-party protocol — query battery via `0xA6 0x53`, reply `0x5C <percent>`,
> with `0x5B` carrying connection/battery-threshold events. See `HARDWARE.md`
> "The wireless module (public information)" for the full command set and the
> reference doc (`emolitor/WestberryTech-WB32`, `docs/wireless/ch582f-protocol.md`).
> This is why the module's per-transport battery behavior can be reasoned about
> from a specification rather than only from hardware.
>
> **Command-space collision worth noting before flashing.** `0xA4` is also the
> third-party module's `MD_SND_CMD_SEND_SYSTEM` code on the keyboard→module UART
> link (`keyboards/linker/wireless/module.h`). The two uses live on different
> buses today — ours is the *host-facing* raw-HID command, the module's is the
> internal UART frame — so they do not collide while raw HID is distinct from the
> module link. They **would** meet if a raw-HID report were ever tunneled over
> the module UART: the send path does exactly that on a non-USB transport, wrapping
> our 32-byte report in a `0xAF 0x61` frame (`module.c` `md_send_raw()`). That
> frame carries the report as opaque payload (its own `0xAF`/`0x61` header, not a
> bare `0xA4`), so no collision is present in the current code — but any future
> change that put a bare host command into the module byte stream would have to
> avoid the `0xA4` system-key code. Recorded so the 2.4 GHz/BT raw-HID test (which
> takes exactly that tunnel path) is not misread as a protocol fault if `0xA4`
> appears on the UART.

## Transport / interface

- Raw HID interface: usage page `0xFF60`, usage `0x61`, report size `RAW_EPSIZE`
  = **32 bytes**, in both directions, always.
- USB-wired: host **pulls** (sends the request; keyboard replies).
- 2.4 GHz dongle: the dongle **shares the keyboard's VID:PID** (`342d:e4c6`) and,
  when active, exposes a second raw HID collection with the same `0xFF60`/`0x61`
  usage page and **32-byte IN and OUT reports** (no report ID). **Verified on
  hardware (2026-10-09):** the dongle enumerates only once it is powered and the
  keyboard is on the 2.4 GHz link (before that it is USB-silent); when it does,
  the raw collection lands on **interface 2** (`/dev/hidraw5`) and a `0xA4` pull
  round-trips with **transport byte `0x04` (2.4 GHz)**. The mapping below is
  therefore **measured**, not assumed. Pull is the normal path; push is a
  fallback (see Push mode).
- **Host-side interface selection matters.** The keyboard's own raw collection is
  **interface 1** (measured). Because the dongle shares the VID:PID, it cannot be
  told apart from the keyboard by a simple match; `host/battery_polybar.py`
  enumerates every match and prefers `interface_number == 2` as the dongle (now
  **verified** on hardware, 2026-10-09), falling back to the only collection
  present; `--transport usb` selects interface 1. `split65.py check` reports which
  collections are present.
- Bluetooth: in scope. **Probed, and broken in a known way:** the module advertises
  and will pair/bond, but its HID GATT server rejects the CCC notification-enabling
  writes with ATT `0x0E`, so no input flows (see `HARDWARE.md` "Why a host does not
  connect" and `UX-REQUIREMENTS.md` § 0.7). Whether the BT link would also expose
  the raw HID collection (`0xFF60`/`0x61`) and populate `*md_getp_bat()` is
  therefore still unmeasured — it cannot be reached while the CCC write fails. The
  host falls back to the BLE Battery Service `0x180F` / Battery Level `0x2A19`
  (via `bluetoothctl`).

### Dongle raw HID interface

The descriptor below is **the generic QMK raw HID descriptor, not a live dump** —
it was not captured with `HIDIOCGRDESC`, because the live dongle was probed by
usage page rather than by descriptor read. It is what the dongle exposes when it
presents the standard QMK raw collection (34 bytes, no report ID); the collection
itself **is** now confirmed present on a live dongle (interface 2,
`/dev/hidraw5`, usage page `0xFF60`/usage `0x61`, 2026-10-09):

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
| 7 | persisted host (`connection_get_host_raw()` raw value: `0` AUTO, `1` NONE, `2` USB, `3` BLUETOOTH, `4` 2P4GHZ) |
| 8 | active BT sub-profile (the BT driver's profile, `DEVS_BT1`..`DEVS_BT5` = `1`..`5`) |
| 9 | module firmware version (`0x5D` reply; `0` if the image never answers — see below) |
| 10 | module link state (`MD_STATE_*`: `0` NONE, `1` PAIRING, `2` CONNECTED, `3` DISCONNECTED, `4` REJECT) |
| 11..20 | diagnostic block (`wls_diag_t`, 10 bytes; `WLS_DIAG_ENC_SIZE`) — pin levels, switch/host decision, reset cause |
| 21..22 | boot diagnostic code, as the two LED counts (`{amber, white}`) |
| 23..31 | jump journal (`wls/wls_jump_journal`, 9 bytes) — discriminates a dispatched `QK_BOOT` from a corrupt or electrical reset |

The fields at 7–10 are a **diagnostic extension** (added with the transport
collapse and the module-fingerprint work). They exist because the Bluetooth
faults live in the CH582F module, whose image is closed and undumpable: byte 9
identifies which module revision is fitted (the only public fingerprint), and
byte 10 makes the module's own view of the link observable when the HID link
never establishes. Byte 7 is the *stored* host (not the AUTO-resolved one) so a
client can see what persistence holds. Hosts must ignore fields they do not
know; older firmware replies with `0x00` here.

**Scope of these fields — board-local, not upstream.** This whole `0xA4` command
is a board host convention (Keychron-derived), not a QMK standard, so none of
7–10 can be "upstreamed" today. Two of them carry a *generic concept* anyway and
are the natural readback if a wireless-module abstraction is ever modeled
upstream: **byte 9 (module firmware version)** and **byte 10 (module link
state)** are module-protocol-agnostic. **Bytes 7–8 are test-only diagnostics for
our own verification and are deliberately reclaimable** — do not build host
features on them. See `HARDWARE.md` "The Layer boundary" for the full split.

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
`--pull` (request/reply). **Both are now confirmed present over 2.4 GHz
(2026-10-09):** a `--pull` against the dongle's raw collection returned a real
reply with transport byte `0x04`.

## Verifying the pull path

The keyboard-side tunnel exists: `md_raw.c` maps `md_receive_raw_cb()` →
`raw_hid_receive()`, and `module.c` forwards received raw packets
(`MD_RAW_SIZE = 32`) to that callback, so a host request reaches `0xA4` handling
over every transport. The send direction needs no board glue — `raw_hid_send()`
(upstream) calls `host_raw_hid_send()`, which selects the driver from the
connection host, reaching the USB endpoint and the module sink the same way every
other report is.

To check the battery: put the keyboard in USB or 2.4 GHz mode and run
`python3 host/battery_polybar.py --pull` (or `--listen` for push reports). The
host enumerates by usage page `0xFF60` / usage `0x61`. **Verify the interface it
picked before trusting the transport byte** — with keyboard and dongle both
attached, a first-match selection returns the keyboard's USB interface, so the
tool prefers interface 2 (the dongle, verified 2026-10-09; `--transport usb`
forces the keyboard's own). A read timeout means the pull did not complete on
that attempt; the push path then covers it.

Use `python3 host/battery_polybar.py --info` to print the **full** readback —
battery, the persisted host and BT sub-profile (bytes 7–8), and the module
fingerprint (bytes 9–10). This is the way to identify the fitted CH582F image
(byte 9) and to see the module's link state (byte 10) when no HID link forms.

For the Bluetooth re-pair loop, `host/bt_reconnect.py` scans for `Split65-N`,
pairs fresh with an agent, and connects — working around the module's
non-resolvable address rotation, which makes a stored bond unusable. It cannot
fix the module's GATT faults; it makes the connection attempt reproducible.

What a successful pull proves and does not prove:

- It proves the transport plumbing works end to end (request out, reply back).
- It does **not** prove byte 1 is real. On USB, byte 1 is the module's init
  constant (`100`); only the radio path has ever been seen to carry a value that
  responds to actual use. See the byte-1 caveat above and `TODO.md` defect 1.
