#!/usr/bin/env python3
# Copyright 2026
# SPDX-License-Identifier: Apache-2.0
"""Re-pair and connect the Split65 over Bluetooth.

This is a WORKAROUND for the CH582F module's faults, not a fix for them. The
module advertises as "Split65-N" (N = BT profile) under a NEW random address
each advertising session, so a stored bond never matches and BlueZ reports
"No matching connection for device". This script does the whole sequence from
scratch whenever a link is wanted: scan, pick the live address by name, pair
with an agent (the module uses SMP numeric-comparison confirm, so an agent MUST
be registered or pairing returns AuthenticationFailed), then connect.

It cannot fix the module's GATT faults (its HID server rejects the
notification-enabling writes with ATT 0x0E), so a connected link may not
deliver input. It reliably reproduces the connection attempt and prints the
module's state. See docs/HARDWARE.md for the full diagnosis.

This is board-local tooling for a vendor-specific module fault; it is not, and
should not become, an upstream QMK concern.

Usage:
    bt_reconnect.py                 # pair+connect the first Split65-N found
    bt_reconnect.py --name Split65-2
    bt_reconnect.py --adapter hci0 --scan-secs 20

Non-interactive: no bluetoothctl prompt is ever left waiting.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import threading
import time

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
# "Device C8:02:09:B0:56:5E Split65-2" -> capture address + name
DEVICE_RE = re.compile(r"(\w{2}:\w{2}:\w{2}:\w{2}:\w{2}:\w{2})\s+(Split65-[1-9])\b")
# journal lines that name a module-side fault
JOURNAL_RE = re.compile(
    r"ccc|hog-lib|PPCP|split65|No matching connection|Terminated", re.IGNORECASE
)


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def run_bluetoothctl(script: str, timeout: int) -> str:
    """Run an interactive bluetoothctl session fed via stdin, ANSI-stripped.

    bluetoothctl has no fully non-interactive interface, so commands are piped
    in. A bounding timeout guarantees no prompt is ever left waiting.
    """
    try:
        result = subprocess.run(
            ["bluetoothctl"],
            input=script,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        # A timeout still yields partial output; report what was seen.
        out = (exc.stdout or b"").decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = (exc.stderr or b"").decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return strip_ansi(out + err)
    return strip_ansi(result.stdout + result.stderr)


def scan_and_wait(adapter: str, secs: int) -> list[tuple[str, str]]:
    """Power on, scan for `secs`, then list devices -- one bluetoothctl session.

    Implemented with a small helper process so the scan window can elapse before
    `devices` is requested, mirroring the bash version's `sleep` between.
    """
    proc = subprocess.Popen(
        ["bluetoothctl"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert proc.stdin and proc.stdout
    script = f"select {adapter}\npower on\nscan on\n"

    def feed() -> None:
        assert proc.stdin
        proc.stdin.write(script)
        proc.stdin.flush()
        # Let the scan run; discovery is asynchronous.
        time.sleep(secs)
        proc.stdin.write("devices\n")
        proc.stdin.flush()
        time.sleep(2)
        proc.stdin.write("quit\n")
        proc.stdin.flush()
        proc.stdin.close()

    thread = threading.Thread(target=feed, daemon=True)
    thread.start()
    try:
        out, _ = proc.communicate(timeout=secs + 15)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, _ = proc.communicate()
    thread.join(timeout=2)

    seen: list[tuple[str, str]] = []
    for addr, name in DEVICE_RE.findall(strip_ansi(out or "")):
        if (addr, name) not in seen:
            seen.append((addr, name))
    return seen


def connect(addr: str) -> str:
    """Register an agent, then remove/pair/trust/connect/info `addr`."""
    script = (
        "agent KeyboardDisplay\n"
        "default-agent\n"
        f"remove {addr}\n"
        f"pair {addr}\n"
        f"trust {addr}\n"
        f"connect {addr}\n"
        f"info {addr}\n"
        "quit\n"
    )
    return run_bluetoothctl(script, timeout=60)


def recent_journal() -> str:
    try:
        result = subprocess.run(
            ["journalctl", "-u", "bluetooth", "-n", "40", "--no-pager"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    lines = [ln for ln in result.stdout.splitlines() if JOURNAL_RE.search(ln)]
    return "\n".join(lines[-10:])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", default="", help="prefer this advertised name")
    parser.add_argument("--adapter", default="hci0", help="HCI adapter (default hci0)")
    parser.add_argument(
        "--scan-secs", type=int, default=20, help="scan window in seconds"
    )
    args = parser.parse_args()

    print(f"--> scanning {args.scan_secs}s for Split65-*")
    found = scan_and_wait(args.adapter, args.scan_secs)
    if not found:
        print("no Split65-* advertising found.", file=sys.stderr)
        print(
            "  - is the switch on BT and the pairing window open "
            "(indicator blinking fast)?",
            file=sys.stderr,
        )
        print(
            "  - the module stops advertising ~30 min after idle; long-press "
            "Fn+2/3/4 (KC_BT1/2/3) to re-arm.",
            file=sys.stderr,
        )
        print(
            "  - if the adapter never leaves 'Discovering: no' while scanning, "
            "the host controller is wedged (seen on Intel AX200): reset it "
            "(`doas rmmod btusb btintel; doas modprobe btusb`) or reboot. This "
            "is a host fault, not the keyboard.",
            file=sys.stderr,
        )
        return 2

    addr, name = found[0]
    if args.name:
        for a, n in found:
            if n == args.name:
                addr, name = a, n
                break
    print(f"--> target: {name} at {addr}")

    resp = connect(addr)
    print(resp)

    journal = recent_journal()
    if journal:
        print("--> journal (module profile errors, if any):")
        print(journal)

    if "Connected: yes" in resp:
        print("--> connected.")
        return 0
    print(
        "--> not connected (module-side GATT/address fault; see docs/HARDWARE.md).",
        file=sys.stderr,
    )
    return 3


if __name__ == "__main__":
    sys.exit(main())
