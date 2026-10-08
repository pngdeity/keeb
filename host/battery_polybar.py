#!/usr/bin/env python3
# Copyright 2026
# SPDX-License-Identifier: Apache-2.0
"""Read EPOMAKER Split65 battery level and print a polybar-friendly string.

Firmware side: see PROTOCOL.md at the repository root. Command 0xA4
(KC_GET_BATTERY_LEVEL) returns the battery percentage in reply byte 1.

Usage:
    battery_polybar.py            # auto: pull over USB, listen over dongle
    battery_polybar.py --pull     # send the request, read the reply (USB)
    battery_polybar.py --listen   # passively read push reports (2.4 GHz)

When both the keyboard's USB collection (interface 1) and the 2.4 GHz dongle's
(interface 2) are attached, interface 2 is preferred by default; pass
--transport usb to read interface 1 instead. NOTE: the interface-2 = dongle
mapping is UNVERIFIED -- the dongle shares VID:PID 342d:e4c6 with the keyboard,
and only interface 1 has ever been observed live (see PROTOCOL.md/TODO.md).

Exits non-zero with no output when the keyboard is absent, so polybar hides
the module.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

try:
    import hid
except ImportError:  # pragma: no cover
    print("battery_polybar: missing 'hid' package (pip install hid)", file=sys.stderr)
    sys.exit(2)

USAGE_PAGE = 0xFF60
USAGE = 0x61
REPORT_LENGTH = 32
CMD_GET_BATTERY = 0xA4

TRANSPORT_NAMES = {0x01: "USB", 0x02: "BT", 0x04: "2.4G"}

# Raw HID collection interface numbers (see PROTOCOL.md). The keyboard's own
# collection has been observed on interface 1. A second collection on interface
# 2 is *assumed* to be the 2.4 GHz dongle, but that is UNVERIFIED: the dongle
# shares VID:PID 342d:e4c6 with the keyboard, so it cannot be disambiguated by a
# VID filter, and only interface 1 has been seen live. See TODO.md defect 3.
INTERFACE_KEYBOARD = 1
INTERFACE_DONGLE = 2


def enumerate_raw_hid_interfaces():
    """Return every raw HID interface matching the QMK raw HID usage."""
    return [
        info
        for info in hid.enumerate()
        if info.get("usage_page") == USAGE_PAGE and info.get("usage") == USAGE
    ]


def find_raw_hid_interface(prefer=None):
    """Pick the raw HID interface to use.

    Several can match at once (the keyboard's collection on interface 1 and,
    if present, a second collection on interface 2 assumed -- UNVERIFIED -- to
    be the 2.4 GHz dongle). Default to interface 2 so a read over 2.4 GHz is not
    silently satisfied by the keyboard's USB collection; prefer="usb" selects
    interface 1 instead. See TODO.md defect 3 for the open verification.
    """
    candidates = enumerate_raw_hid_interfaces()
    if not candidates:
        return None

    wanted = INTERFACE_DONGLE if prefer in (None, "dongle", "2.4g") else INTERFACE_KEYBOARD
    for info in candidates:
        if info.get("interface_number") == wanted:
            return info
    # Only one collection present: take it regardless of preference.
    return candidates[0]


def read_battery_pull(prefer=None):
    """Send the 0xA4 request and return the parsed reply, or None."""
    info = find_raw_hid_interface(prefer)
    if info is None:
        return None

    try:
        device = hid.Device(path=info["path"])
    except Exception:
        # Device vanished between enumerate() and open().
        return None
    try:
        # The first byte is the HID Report ID.
        request = bytes([0x00, CMD_GET_BATTERY] + [0x00] * (REPORT_LENGTH - 1))
        device.write(request)
        reply = device.read(REPORT_LENGTH, timeout=1000)
    finally:
        device.close()

    if not reply:
        return None
    return parse_reply(reply)


def read_battery_listen(timeout_ms=6000, prefer=None):
    """Passively read push reports. Returns the first valid parsed reply."""
    info = find_raw_hid_interface(prefer)
    if info is None:
        return None

    try:
        device = hid.Device(path=info["path"])
    except Exception:
        # Device vanished between enumerate() and open().
        return None
    try:
        while True:
            report = device.read(REPORT_LENGTH, timeout=timeout_ms)
            if not report:
                return None
            parsed = parse_reply(report)
            if parsed is not None:
                return parsed
    finally:
        device.close()


def parse_reply(report: bytes):
    # Accept only our own command echo. This rejects the 0xFF "unhandled"
    # sentinel some firmware lineages emit, as well as stray HID reports.
    if len(report) < 2 or report[0] != CMD_GET_BATTERY:
        return None
    # Bytes 2-3 are reserved (this board reports no voltage); skip them.
    result = {"percent": report[1], "charging": 0, "transport": 0, "model": 0}
    if len(report) >= 5:
        result["charging"] = report[4]
    if len(report) >= 6:
        result["transport"] = report[5]
    if len(report) >= 7:
        result["model"] = report[6]
    return result


def read_battery_bluetooth(mac=None):
    """Fallback: read the BLE Battery Service via bluetoothctl.

    With no MAC, searches paired devices for one whose name looks like this
    keyboard, then reads its 'Battery Percentage' line.
    """
    def bt_info(target):
        try:
            out = subprocess.run(
                ["bluetoothctl", "info", target],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return None
        match = re.search(r"Battery Percentage:\s*0x[0-9a-fA-F]+\s*\((\d+)\)", out)
        return int(match.group(1)) if match else None

    if mac:
        percent = bt_info(mac)
        return {"percent": percent, "charging": 0, "transport": 0x02} if percent is not None else None

    try:
        devices = subprocess.run(
            ["bluetoothctl", "devices"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None

    for line in devices.splitlines():
        if "Split65" not in line:
            continue
        mac_addr = line.split()[1] if len(line.split()) > 1 else None
        if not mac_addr:
            continue
        percent = bt_info(mac_addr)
        if percent is not None:
            return {"percent": percent, "charging": 0, "transport": 0x02}
    return None


def format_status(result):
    percent = result["percent"]
    if result.get("charging") in (1, 2):
        return f"CHG {percent}%"
    return f"BAT {percent}%"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--pull", action="store_true", help="send the request and read the reply")
    mode.add_argument("--listen", action="store_true", help="passively read push reports")
    mode.add_argument("--bluetooth", action="store_true", help="read the BLE battery service")
    parser.add_argument("--mac", help="Bluetooth MAC address for --bluetooth")
    parser.add_argument(
        "--transport",
        choices=("dongle", "usb"),
        default="dongle",
        help="raw HID interface to read: 'dongle' (interface 2, default) or 'usb' (interface 1)",
    )
    args = parser.parse_args()

    prefer = args.transport
    result = None
    if args.pull:
        result = read_battery_pull(prefer)
    elif args.listen:
        result = read_battery_listen(prefer=prefer)
    elif args.bluetooth:
        result = read_battery_bluetooth(args.mac)
    else:
        result = read_battery_pull(prefer)
        if result is None:
            result = read_battery_listen(prefer=prefer)

    if result is None or result.get("percent") is None:
        return 1

    print(format_status(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
