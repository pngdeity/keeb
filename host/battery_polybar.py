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
--transport usb to read interface 1 instead. The interface-2 = dongle mapping is
VERIFIED (2026-10-09): the dongle shares VID:PID 342d:e4c6 with the keyboard, so
it cannot be disambiguated by a VID filter; it is selected by interface number.

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

# Raw HID collection interface numbers (see PROTOCOL.md). The keyboard's own
# collection is interface 1; the 2.4 GHz dongle's is interface 2. Both share
# VID:PID 342d:e4c6, so the interface number is the discriminator (verified on
# hardware 2026-10-09).
INTERFACE_KEYBOARD = 1
INTERFACE_DONGLE = 2

# The single source of truth for the 0xA4 reply field meanings (mirrors the
# firmware's wls.h; see PROTOCOL.md "Reply"). Keep the decode tables next to the
# byte indices so a change lands in one place.
REPLY_INDEX = {
    "percent": 1,
    "charging": 4,
    "transport": 5,
    "model": 6,
    "host": 7,
    "btsub": 8,
    "md_version": 9,
    "md_state": 10,
}

TRANSPORT_NAMES = {0x01: "USB", 0x02: "BT", 0x04: "2.4G"}
CHARGE_NAMES = {0: "discharging", 1: "charging", 2: "full"}
HOST_NAMES = {0: "AUTO", 1: "NONE", 2: "USB", 3: "BLUETOOTH", 4: "2P4GHZ"}
MD_STATE_NAMES = {0: "NONE", 1: "PAIRING", 2: "CONNECTED", 3: "DISCONNECTED", 4: "REJECT"}
# The shell-state diagnostic block, mirroring the firmware's `wls_diag_t` and
# the pure `wls_diag_encode()` layout (wls/diag_logic.c). Nine bytes starting at
# KB_BATTERY_IDX_DIAG: this is the observability seam -- the firmware's own view
# of the switch/devs/host, readable on whichever channel is up. The last three
# are the RAW switch/cable pin levels behind `switch`, so the decode can be
# audited against the part (the pins are measured to lie across boots).
DIAG_INDEX = {
    "switch": 11,
    "devs": 12,
    "host": 13,
    "bootcnt": 14,
    "usb_line": 15,
    "link": 16,
    "pin_c14": 17,
    "pin_c15": 18,
    "pin_b9": 19,
    "reset_cause": 20,
}
SWITCH_NAMES = {0: "UNKNOWN", 1: "USB", 2: "BT", 3: "2.4G"}
# RSTCAUSE: the MCU's latched reset cause (RCC->RSTSTAT), consumed once at boot.
# The firmware reports the raw bits; these names decode the six named causes at
# the same bit positions the CMSIS header defines.
RESET_CAUSE_NAMES = {
    0: "low-power",
    1: "window-watchdog",
    2: "independent-watchdog",
    3: "software",
    4: "power-on",
    5: "external-pin",
}
# KB_BATTERY_IDX_BOOT_CODE: the boot diagnostic code (wls/boot_code_logic), the
# two counts the LED plays -- {amber, white} (Dell E-series convention). Amber =
# the boot stage (coarse category), white = the code within it. Retained across
# the boot, so a boot that tore its own USB line down is still readable on the
# next successful reply.
BOOT_CODE_INDEX = 21
# The jump journal (wls/wls_jump_journal), starting at index 23 (after the
# 2-byte boot code at 21..22). Twelve bytes: a presence flag, then the boot-code
# stage/code and the reset-cause bits and uptime that were live when
# `bootloader_jump()` ran. The record lives in `.ram0` and survives the reset the
# jump performs, so it is readable on the boot AFTER a DFU jump.
JUMP_INDEX = 23
# The stage names, from the firmware's wls_boot_code_logic.h. Amber is the
# count of the stage (0 = healthy); white is the specific fault within it.
BOOT_STAGE_NAMES = {
    0: "OK",
    1: "PREINIT",
    2: "BOOT_PASS",
    3: "TRANSPORT",
    4: "ROLE",
    5: "INCOMPLETE",
    6: "BOOTCOUNT",
    7: "RSTCAUSE",
}

# The golden vector shared with the firmware (see docs/0xA4-golden-vector.md).
# The firmware test suite asserts these exact bytes; this asserts they decode to
# the fields below. It fails if either side's indices, name tables, or layout move.
GOLDEN_VECTOR = bytes(
    [
        0xA4,  # 0  CMD = KB_BATTERY_CMD_GET (the reply echoes the command),
        0x51,  # 1  level 81%
        0x00,  # 2  reserved
        0x00,  # 3  reserved
        0x01,  # 4  charge = charging
        0x02,  # 5  transport = bluetooth
        0x07,  # 6  model
        0x04,  # 7  host = BLUETOOTH
        0x03,  # 8  btsub = 3 (BT4)
        0x12,  # 9  md_version = 18
        0x02,  # 10 md_state = CONNECTED
        0x02,  # 11 diag switch = BT
        0x04,  # 12 diag devs = DEVS_BT4
        0x04,  # 13 diag host = bluetooth
        0x03,  # 14 diag bootcnt = 3
        0x01,  # 15 diag usb_line = 1
        0x02,  # 16 diag link = connected
        0x01,  # 17 diag pin_c14 = 1
        0x00,  # 18 diag pin_c15 = 0
        0x01,  # 19 diag pin_b9 = 1
        0x10,  # 20 diag reset_cause = bit 4 (PORRSTF)
        0x07,  # 21 boot code amber = 7
        0x05,  # 22 boot code white = 5
        0x01,  # 23 jump journal: presence = 1 (our bootloader_jump ran)
        0x01,  # 24 jump journal: version = 1
        0x09,  # 25 jump journal: generation = 9
        0x00,  # 26 jump journal: stage = 0 (healthy at the jump)
        0x00,  # 27 jump journal: code = 0
        0x10,  # 28 jump journal: reset_cause low byte (bit 4 PORRSTF)
        0x00,  # 29 jump journal: reset_cause >>8
        0x00,  # 30 jump journal: reset_cause >>16
        0x00,  # 31 jump journal: reset_cause >>24
        0xD2,  # 32 jump journal: uptime_ms low byte (0x00B4D2 = 46354 ms)
        0xB4,  # 33 jump journal: uptime_ms >>8
        0x00,  # 34 jump journal: uptime_ms >>16
    ]
)

GOLDEN_EXPECTED = {
    "percent": 0x51,
    "charging": 0x01,
    "transport": 0x02,
    "model": 0x07,
    "host": 0x04,
    "btsub": 0x03,
    "md_version": 0x12,
    "md_state": 0x02,
    "diag_switch": 0x02,
    "diag_devs": 0x04,
    "diag_host": 0x04,
    "diag_bootcnt": 0x03,
    "diag_usb_line": 0x01,
    "diag_link": 0x02,
    "diag_pin_c14": 0x01,
    "diag_pin_c15": 0x00,
    "diag_pin_b9": 0x01,
    "diag_reset_cause": 0x10,
    "boot_amber": 0x07,
    "boot_white": 0x05,
    "jump_present": 0x01,
    "jump_version": 0x01,
    "jump_generation": 0x09,
    "jump_stage": 0x00,
    "jump_code": 0x00,
    "jump_reset_cause": 0x10,
    "jump_uptime_ms": 0x00B4D2,
}


def check_golden_vector():
    """The host half of the cross-language 0xA4 fixture (docs/0xA4-golden-vector.md).

    The firmware test suite asserts these exact bytes; this asserts they decode to
    the fields above. Returns a list of human-readable mismatches (empty = OK).
    """
    decoded = parse_reply(GOLDEN_VECTOR)
    problems = []
    if decoded is None:
        return ["golden vector did not parse (command echo mismatch)"]
    for name, want in GOLDEN_EXPECTED.items():
        got = decoded.get(name)
        if got != want:
            problems.append(f"{name}: decoded {got!r}, expected {want!r}")
    return problems


def enumerate_raw_hid_interfaces():
    """Return every raw HID interface matching the QMK raw HID usage."""
    return [
        info
        for info in hid.enumerate()
        if info.get("usage_page") == USAGE_PAGE and info.get("usage") == USAGE
    ]


def find_raw_hid_interface(prefer=None):
    """Pick the raw HID interface to use.

    Several collections can match at once: the keyboard's on interface 1 and,
    when attached, the 2.4 GHz dongle's on interface 2 (verified 2026-10-09).
    Default to interface 2 so a read over 2.4 GHz is not silently satisfied by
    the keyboard's USB collection; prefer="usb" selects interface 1 instead.
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
    # Decode every field present, by its index (REPLY_INDEX is the one source).
    result = {}
    for name, index in REPLY_INDEX.items():
        if len(report) > index:
            result[name] = report[index]
    for name, index in DIAG_INDEX.items():
        if len(report) > index:
            result[f"diag_{name}"] = report[index]
    # The boot diagnostic code (wls/boot_code_logic): the two counts the LED
    # plays, at index 17 -- {amber, white} (Dell E-series convention). Amber is
    # the boot stage (coarse), white the code within it. The eye and the host
    # read the same pair.
    if len(report) > BOOT_CODE_INDEX + 1:
        result["boot_amber"] = report[BOOT_CODE_INDEX]
        result["boot_white"] = report[BOOT_CODE_INDEX + 1]
    # The jump journal (wls/wls_jump_journal): the record our `bootloader_jump()`
    # writes into `.ram0` before it jumps, which survives the reset. Its presence
    # byte is 1 only if OUR jump path ran; a `dfa0` window with presence 0 means
    # the DFU magic word was written by something else.
    if len(report) > JUMP_INDEX + 11:
        j = report[JUMP_INDEX : JUMP_INDEX + 12]
        result["jump_present"] = j[0]
        result["jump_version"] = j[1]
        result["jump_generation"] = j[2]
        result["jump_stage"] = j[3]
        result["jump_code"] = j[4]
        result["jump_reset_cause"] = j[5] | (j[6] << 8) | (j[7] << 16) | (j[8] << 24)
        result["jump_uptime_ms"] = j[9] | (j[10] << 8) | (j[11] << 16)
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


def format_info(result):
    """Full readback: battery, selectors, and the module fingerprint."""
    transport = result.get("transport", 0)
    charging = result.get("charging", 0)
    lines = [
        f"battery:   {result['percent']}%  charge={charging} ({CHARGE_NAMES.get(charging, '?')})  "
        f"transport={TRANSPORT_NAMES.get(transport, hex(transport))}",
        f"model:     {result.get('model', 0)}",
    ]
    if "host" in result:
        host = result["host"]
        lines.append(f"host(raw): {host} ({HOST_NAMES.get(host, '?')})")
    if "btsub" in result:
        lines.append(f"bt profile:{result['btsub']}")
    if "md_version" in result:
        lines.append(f"md fw ver: {result['md_version']}  (0 = module did not answer 0x5D)")
    if "md_state" in result:
        state = result["md_state"]
        lines.append(f"md state:  {state} ({MD_STATE_NAMES.get(state, '?')})")
    # The shell-state diagnostic block (observability seam): the firmware's own
    # view of the switch position and transport, plus a boot counter that tells a
    # reset loop from a mere USB-line drop.
    if "diag_switch" in result:
        sw = result["diag_switch"]
        lines.append(
            f"DIAG:      switch={sw} ({SWITCH_NAMES.get(sw, '?')})  "
            f"devs={result.get('diag_devs', '?')}  "
            f"host={result.get('diag_host', '?')}  "
            f"usb_line={result.get('diag_usb_line', '?')}  "
            f"bootcnt={result.get('diag_bootcnt', '?')}  "
            f"link={result.get('diag_link', '?')}"
        )
        # The raw levels behind `switch`: the switch pins are measured to LIE
        # (bridged, not an SPDT), so reporting them turns "the pins lie" into a
        # specific measurement, and `pin_b9` decides whether the cable detect is
        # usable as a hint at all.
        lines.append(
            f"PINS:      C14={result.get('diag_pin_c14', '?')}  "
            f"C15={result.get('diag_pin_c15', '?')}  "
            f"B9={result.get('diag_pin_b9', '?')}  (B9: 1 = cable detected)"
        )
        # The MCU's own latched reset cause (RCC->RSTSTAT), consumed once at boot:
        # the chip names why it last reset, which turns a reset loop from "the
        # boot count climbs" into "and the cause is X".
        cause_bits = result.get("diag_reset_cause", 0) or 0
        cause_names = [name for bit, name in RESET_CAUSE_NAMES.items() if cause_bits & (1 << bit)]
        lines.append(
            f"RESET:     cause_bits=0x{cause_bits:02X}  "
            f"({', '.join(cause_names) if cause_names else 'none latched'})"
        )
    # The boot diagnostic code: the (amber, white) pair the LED plays. Amber is
    # the boot stage, white the fault within it -- the same numbers the eye
    # counts, so the two readers cannot disagree.
    if "boot_amber" in result:
        a = result["boot_amber"]
        w = result["boot_white"]
        lines.append(f"BOOT CODE: {a} amber, {w} white  ->  stage={BOOT_STAGE_NAMES.get(a, '?')} code={w}")
    # The jump journal: whether OUR bootloader_jump() ran before the last reset,
    # and where the board was when it did. presence=1 means a QK_BOOT (or our
    # wrapper) drove the jump; presence=0 with a DFU window means the magic word
    # was written by something else -- the discriminator this record exists for.
    if "jump_present" in result:
        if result["jump_present"]:
            lines.append(
                f"JUMP:      our QK_BOOT ran  gen={result['jump_generation']}  "
                f"stage={result['jump_stage']} ({BOOT_STAGE_NAMES.get(result['jump_stage'], '?')})  "
                f"code={result['jump_code']}  "
                f"reset=0x{result['jump_reset_cause']:08X}  "
                f"uptime={result['jump_uptime_ms']} ms"
            )
        else:
            lines.append("JUMP:      no journal (our bootloader_jump has not run since power-on)")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--pull", action="store_true", help="send the request and read the reply")
    mode.add_argument("--listen", action="store_true", help="passively read push reports")
    mode.add_argument("--bluetooth", action="store_true", help="read the BLE battery service")
    mode.add_argument("--info", action="store_true", help="print the full readback (battery, selectors, module fingerprint)")
    mode.add_argument("--self-check", action="store_true", help="run the golden-vector self-check and exit (no hardware)")
    parser.add_argument("--mac", help="Bluetooth MAC address for --bluetooth")
    parser.add_argument(
        "--transport",
        choices=("dongle", "usb"),
        default="dongle",
        help="raw HID interface to read: 'dongle' (interface 2, default) or 'usb' (interface 1)",
    )
    args = parser.parse_args()

    if args.self_check:
        problems = check_golden_vector()
        if problems:
            print("golden-vector self-check FAILED:", file=sys.stderr)
            for line in problems:
                print(f"  {line}", file=sys.stderr)
            return 1
        print("golden-vector self-check OK")
        return 0

    prefer = args.transport
    result = None
    if args.pull:
        result = read_battery_pull(prefer)
    elif args.listen:
        result = read_battery_listen(prefer=prefer)
    elif args.bluetooth:
        result = read_battery_bluetooth(args.mac)
    elif args.info:
        result = read_battery_pull(prefer) or read_battery_listen(prefer=prefer)
    elif args.self_check:
        result = None
    else:
        result = read_battery_pull(prefer)
        if result is None:
            result = read_battery_listen(prefer=prefer)

    if result is None or result.get("percent") is None:
        # Say WHY, then fail. A silent non-zero exit is its own defect: it is
        # indistinguishable from "the tool is broken" when the real news is
        # "the board answered nothing". This is the path a keyboard on a
        # non-USB transport takes -- the raw-HID responder is only live while
        # the host is the committed transport, so no reply IS the diagnosis.
        if result is None:
            print(
                "no reply on the raw HID interface: the device did not answer 0xA4 "
                "(write accepted, nothing read). On a keyboard whose committed "
                "transport is not USB, this is expected -- keystrokes and the "
                "report path go to the module, not the host.",
                file=sys.stderr,
            )
        else:
            print(
                f"reply parsed but carries no battery level: {result}",
                file=sys.stderr,
            )
        return 1

    if args.info:
        print(format_info(result))
    else:
        print(format_status(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
