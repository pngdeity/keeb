# Host side — battery polybar module

`battery_polybar.py` reads the keyboard battery over raw HID (USB and the
2.4 GHz dongle) or, as a fallback, the Bluetooth BLE Battery Service. See
`../PROTOCOL.md` for the raw HID command.

The dongle exposes the same raw HID interface (`0xFF60`/`0x61`) as the keyboard
and **bridges host → keyboard**, so `--pull` works over 2.4 GHz as well as USB.
The keyboard also pushes the value unprompted, so `--listen` remains a valid (and
more robust) mode. On stock firmware a `--pull` returns an `FF ...` unhandled
sentinel; it becomes a `0xA4` report only after flashing this firmware.

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

Output is a single token pair such as `BAT 82%` or `CHG 91%`. The script exits
non-zero with no output when the keyboard is absent, so polybar hides it.

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
The keyboard reports the last known value between pushes, so a short `interval`
is fine.
