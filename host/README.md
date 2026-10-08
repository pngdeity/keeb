# Host side — battery polybar module

`battery_polybar.py` reads the keyboard battery over raw HID (USB and the
2.4 GHz dongle) or, as a fallback, the Bluetooth BLE Battery Service. See
`../docs/PROTOCOL.md` for the raw HID command.

> **The number is not yet trustworthy.** Over USB the keyboard reports `100`
> because its wireless module never answers the level inquiry on that transport,
> so the value is the firmware's compile-time default (`../TODO.md` defect 1).
> Treat any output as a transport/plumbing check, not a charge reading, until
> that defect is fixed.

The dongle **shares the keyboard's VID:PID** (`342d:e4c6`). If a dongle is present
it exposes the same raw HID interface (`0xFF60`/`0x61`) and **bridges host →
keyboard**, so `--pull` should work over 2.4 GHz as well as USB. **Unverified:** no
dongle has been confirmed on the bus in this project (see `TODO.md` defect 3). The
keyboard also pushes the value unprompted, so `--listen` remains a valid (and
more robust) mode.

The `0xA4` command is answered by **our firmware** (the responder
`wls/wls_battery.c` in the `qmk_firmware` submodule; both halves now run the
current build). On **stock/vendor** firmware with no responder, the raw HID
interface answers with an unhandled `FF` sentinel instead, so `--pull` returns
nothing useful.

**Interface selection.** `find_raw_hid_interface()` enumerates every
`0xFF60`/`0x61` collection and returns the one with `interface_number == 2` by
default as an **assumed dongle** (unverified; the dongle shares the keyboard's
VID:PID); `--transport usb` selects interface 1, the keyboard's own collection.
With only one collection attached it uses that one. `split65.py check` lists the
collections found and warns when more than one is present.

## Requirements

- Python 3 and the `hid` package. On Arch this is `python-hid` (`pacman -S
  python-hid`); Do **not** install `pyhidapi` — it is a different, unmaintained
  project. The API must be the newer `hid.Device` one, not the legacy
  `hid.device()`/`open_path()` API.
- For the Bluetooth fallback: BlueZ `bluetoothctl` on `PATH` and the keyboard
  paired and connected.

## Usage

```sh
python3 battery_polybar.py            # auto: pull over USB, else listen (dongle)
python3 battery_polybar.py --pull     # request/reply (USB)
python3 battery_polybar.py --listen   # passively read push reports (2.4 GHz)
python3 battery_polybar.py --bluetooth [--mac AA:BB:CC:DD:EE:FF]
```

Output is a single token pair such as `BAT 82%` or `CHG 91%`, followed by a
newline. Exit codes: `0` on success, `1` when nothing could be read (no output —
polybar hides the module), `2` when the `hid` package is missing. Default (no
mode flag) tries pull then falls back to listen.

## Polybar module

```ini
[module/battery]
type = custom/script
exec = python3 /home/nathan/repos/pngdeity/incubating/keeb/host/battery_polybar.py
interval = 5
format-prefix = "⌨ "
format-foreground = ${colors.foreground}
```

For the 2.4 GHz dongle, `--pull` and `--listen` both work: the dongle relays the
request to the keyboard and the reply comes back. Use `--pull` for a
request/response value or `--listen` to passively accept the keyboard's push.
The keyboard pushes on change with a `WLS_BATTERY_PUSH_INTERVAL` (10000 ms)
keepalive, but `--listen` only waits for one report per invocation, so any
`interval` of a few seconds works. `interval = 5` is a reasonable polling
cadence for polybar (the firmware's push keepalive is `WLS_BATTERY_PUSH_INTERVAL`,
default 10000 ms).
