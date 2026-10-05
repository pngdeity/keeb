#!/usr/bin/env python3
# Copyright 2026
# SPDX-License-Identifier: Apache-2.0
"""
EPOMAKER Split65 -- Setup and Firmware Management

Usage:
  split65.py setup     Check system and print missing setup steps
  split65.py build     Build firmware
  split65.py flash     Flash firmware to keyboard
  split65.py check     Full system diagnostics
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────
# Paths are resolved relative to this project's root (the directory that holds
# this script), so the tooling works wherever the project is checked out.
PROJECT_DIR = Path(__file__).resolve().parent
QMK_DIR = PROJECT_DIR / "qmk_firmware"
KEYMAP = "nathan"
FIRMWARE_BIN = QMK_DIR / f"epomaker_epomaker_split65_{KEYMAP}.bin"
VIA_JSON = PROJECT_DIR / "host" / "epomaker-split65-via.json"
VIA_APPIMAGE = PROJECT_DIR / "via-3.0.0-linux.AppImage"
UDEV_RULE = Path("/etc/udev/rules.d/50-epomaker-split65.rules")
FLASH_RULE = Path("/etc/udev/rules.d/50-qmk-wb32.rules")

PACMAN_PKGS = [
    "qmk",
    "arm-none-eabi-gcc",
    "arm-none-eabi-binutils",
    "arm-none-eabi-newlib",
    "dfu-util",
    "dfu-programmer",
]
AUR_PKGS = ["wb32-dfu-updater_cli-git"]

KEYBOARD_VID = "342d"
KEYBOARD_PID = "e4c6"
KEYBOARD_DFU_PID = "dfa0"

# ── Helpers ──────────────────────────────────────────────────────────


def step(msg: str) -> None:
    print(f"\n---> {msg}")


def ok(msg: str) -> None:
    print(f"  OK  {msg}")


def warn(msg: str) -> None:
    print(f"  WARN  {msg}")


def err(msg: str) -> None:
    print(f"  ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def has_cmd(name: str) -> bool:
    return shutil.which(name) is not None


def has_pkg(name: str) -> bool:
    result = subprocess.run(["pacman", "-Q", name], capture_output=True, text=True)
    return result.returncode == 0


def doas(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(["doas", *args], **kwargs)


def check_doas(strict: bool = True) -> bool:
    """Verify doas is installed and authenticated.
    In strict mode, shows password prompt and exits on failure (for flash).
    In non-strict mode, checks non-interactively and warns (for setup/check)."""
    if not has_cmd("doas"):
        if strict:
            err("doas not found -- required for privileged operations")
        warn("doas not found -- install doas and configure /etc/doas.conf")
        return False

    if strict:
        result = subprocess.run(["doas", "true"])
        if result.returncode != 0:
            err("doas authentication failed -- check /etc/doas.conf")
        ok("doas available and authenticated")
        return True
    else:
        result = subprocess.run(["doas", "-n", "true"], capture_output=True, text=True)
        if result.returncode != 0:
            warn("doas available but not authenticated")
            return False
        ok("doas available and authenticated")
        return True


# ── Setup ────────────────────────────────────────────────────────────


def setup() -> None:
    """Check system state and print instructions for missing items."""
    print("==============================")
    print("  EPOMAKER Split65 Setup")
    print("==============================")

    # --- doas ---
    step("Privilege check")
    check_doas(strict=False)

    # --- pacman packages ---
    step("System packages")
    missing_pacman = []
    for pkg in PACMAN_PKGS:
        if has_pkg(pkg):
            ok(pkg)
        else:
            warn(f"NOT INSTALLED: {pkg}")
            missing_pacman.append(pkg)

    # --- AUR packages ---
    for pkg in AUR_PKGS:
        bin_name = pkg.replace("-git", "")
        if has_cmd(bin_name):
            ok(f"{bin_name} (AUR)")
        else:
            warn(f"NOT INSTALLED: {bin_name} (AUR: {pkg})")

    if missing_pacman:
        print(f"\n  Install missing packages:")
        print(f"    sudo pacman -S {' '.join(missing_pacman)}")
    if not has_cmd("wb32-dfu-updater_cli"):
        print(f"  Install AUR packages:")
        print(f"    yay -S {' '.join(AUR_PKGS)}")

    # --- files ---
    step("Required files")

    for label, path in [
        ("QMK source", QMK_DIR),
        ("VIA JSON", VIA_JSON),
        ("VIA AppImage", VIA_APPIMAGE),
    ]:
        if path.exists():
            ok(f"{label}: {path}")
        else:
            warn(f"MISSING: {label} ({path})")

    if not QMK_DIR.exists():
        print("\n  QMK source is expected at:")
        print(f"    {QMK_DIR}")
        print("  This project ships with it; restore it if it was removed.")

    # --- udev ---
    step("Udev rules")
    for rule, desc in ((UDEV_RULE, "hidraw access for VIA/QMK (342d:e4c6)"),
                       (FLASH_RULE, "DFU bootloader access (342d:dfa0)")):
        if rule.exists():
            ok(f"{rule} -- {desc}")
        else:
            warn(f"Missing: {rule} -- {desc}")

    if not UDEV_RULE.exists():
        print("\n  Create the hidraw rule (as root):")
        print(f"    echo 'KERNEL==\"hidraw*\", SUBSYSTEM==\"hidraw\", "
              f"ATTRS{{idVendor}}==\"342d\", ATTRS{{idProduct}}==\"e4c6\", "
              f"MODE=\"0660\", TAG+=\"uaccess\"' | doas tee {UDEV_RULE}")
    if not FLASH_RULE.exists():
        print("\n  Create the DFU rule (as root):")
        print(f"    printf '%s\\n' 'SUBSYSTEMS==\"usb\", ATTRS{{idVendor}}==\"342d\", "
              f"ATTRS{{idProduct}}==\"dfa0\", TAG+=\"uaccess\"' | doas tee {FLASH_RULE}")
    if not UDEV_RULE.exists() or not FLASH_RULE.exists():
        print("\n  Then reload udev:")
        print("    doas udevadm control --reload && doas udevadm trigger")

    # --- firmware ---
    step("Firmware binary")
    if FIRMWARE_BIN.exists():
        size = FIRMWARE_BIN.stat().st_size
        ok(f"Firmware: {FIRMWARE_BIN} ({size / 1024:.1f} KB)")
    else:
        warn(f"Firmware not built: {FIRMWARE_BIN}")
        print("  Build with: ./split65.py build")

    # --- summary ---
    print("\n==============================")
    print("  Setup Check Complete")
    print("==============================")
    print("  Build:   ./split65.py build")
    print("  Flash:   ./split65.py flash")
    print("  Check:   ./split65.py check")
    print("  VIA:     ./via-3.0.0-linux.AppImage")
    print("")


# ── Build ────────────────────────────────────────────────────────────


def build() -> None:
    """Build firmware using QMK make."""
    step("Building firmware")

    if not QMK_DIR.exists():
        err(f"QMK source not found: {QMK_DIR}")

    if not FIRMWARE_BIN.exists():
        print(f"  First build -- this may take a few minutes...")
    else:
        print(f"  Rebuilding...")

    result = subprocess.run(
        ["make", f"epomaker/epomaker_split65:{KEYMAP}"],
        cwd=str(QMK_DIR),
    )

    if result.returncode != 0:
        err("Build failed")

    if FIRMWARE_BIN.exists():
        size = FIRMWARE_BIN.stat().st_size
        ok(f"Build successful ({size / 1024:.1f} KB)")
    else:
        err(f"Build completed but binary not found: {FIRMWARE_BIN}")


# ── Flash ────────────────────────────────────────────────────────────


def flash() -> None:
    """Flash firmware to keyboard in DFU mode."""
    check_doas(strict=True)
    step("Flashing firmware")

    if not has_cmd("wb32-dfu-updater_cli"):
        err(
            "wb32-dfu-updater_cli not found -- install: yay -S wb32-dfu-updater_cli-git"
        )

    if not FIRMWARE_BIN.exists():
        err(f"Firmware not found: {FIRMWARE_BIN}\n  Build first: ./split65.py build")

    # Check if keyboard is connected and in DFU mode
    lsusb = subprocess.run(["lsusb"], capture_output=True, text=True)
    vid_pid = f"{KEYBOARD_VID}:{KEYBOARD_PID}".lower()
    vid_dfu = f"{KEYBOARD_VID}:{KEYBOARD_DFU_PID}".lower()

    if vid_dfu in lsusb.stdout.lower():
        ok(f"DFU bootloader detected ({KEYBOARD_VID}:{KEYBOARD_DFU_PID})")
    elif vid_pid in lsusb.stdout.lower():
        warn(f"Keyboard in normal USB mode ({KEYBOARD_VID}:{KEYBOARD_PID}) -- not DFU")
        print()
        print("  Enter DFU bootloader mode first:")
        print("    Left half:  hold Esc while plugging in USB")
        print("    Right half: toggle the hidden R_Shift switch, short the spacebar")
        print("                switch pin holes, then plug in USB")
        print()
        resp = input("  Continue anyway? [y/N] ").strip().lower()
        if resp != "y":
            print("  Aborted.")
            return
    else:
        err(
            f"No EPOMAKER device found (looked for {KEYBOARD_VID}:{KEYBOARD_DFU_PID} "
            "and {KEYBOARD_VID}:{KEYBOARD_PID})"
        )

    # Flash
    result = doas(
        "wb32-dfu-updater_cli",
        "-t",
        "-s",
        "0x08000000",
        "-D",
        str(FIRMWARE_BIN),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        err("Flash failed")

    ok("Firmware flashed successfully")

    # Reset out of the bootloader into the application firmware.
    doas("wb32-dfu-updater_cli", "-R", capture_output=True, text=True)

    print("  Waiting for keyboard to reboot...")
    time.sleep(5)

    # Verify keyboard is back online
    lsusb2 = subprocess.run(["lsusb"], capture_output=True, text=True)
    if KEYBOARD_VID in lsusb2.stdout:
        ok("Keyboard is back online")
    else:
        warn("Keyboard not detected after flash -- may need manual reconnect")


# ── Check ─────────────────────────────────────────────────────────────


def check() -> None:
    """Full system diagnostics."""
    print("==============================")
    print("  EPOMAKER Split65 -- Check")
    print("==============================")

    issues = 0

    # --- doas ---
    step("Privilege check")
    if not check_doas(strict=False):
        issues += 1

    # --- packages ---
    step("System packages")
    for pkg in PACMAN_PKGS:
        if has_pkg(pkg):
            ok(pkg)
        else:
            warn(f"NOT INSTALLED: {pkg}")
            issues += 1

    for pkg in AUR_PKGS:
        bin_name = pkg.replace("-git", "")
        if has_cmd(bin_name):
            ok(f"{bin_name} (AUR)")
        else:
            warn(f"NOT INSTALLED: {bin_name}")
            issues += 1

    # --- files ---
    step("Required files")
    for label, path in [
        ("QMK source", QMK_DIR),
        ("VIA JSON", VIA_JSON),
        ("VIA AppImage", VIA_APPIMAGE),
    ]:
        if path.exists():
            ok(f"{label}")
        else:
            warn(f"MISSING: {label} ({path})")
            issues += 1

    # --- firmware ---
    if FIRMWARE_BIN.exists():
        size = FIRMWARE_BIN.stat().st_size
        ok(f"Firmware binary ({size / 1024:.1f} KB)")
    else:
        warn("Firmware not built -- run: ./split65.py build")
        issues += 1

    # --- udev ---
    step("Udev rules")
    for rule, desc in ((UDEV_RULE, "hidraw (342d:e4c6)"),
                       (FLASH_RULE, "DFU (342d:dfa0)")):
        if rule.exists():
            ok(f"{rule} -- {desc}")
        else:
            warn(f"Missing: {rule} -- {desc}")
            issues += 1

    # --- keyboard detection ---
    step("Keyboard detection")
    lsusb = subprocess.run(["lsusb"], capture_output=True, text=True)
    if KEYBOARD_VID in lsusb.stdout:
        ok(f"EPOMAKER device found (VID 0x{KEYBOARD_VID})")
    else:
        warn("EPOMAKER keyboard not detected on USB -- may be on battery")
        issues += 1

    # --- summary ---
    print("\n==============================")
    if issues == 0:
        print("  All checks passed")
    else:
        print(f"  {issues} issue(s) found -- run './split65.py setup' for details")
    print("==============================\n")


# ── Main ──────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EPOMAKER Split65 -- Setup and Firmware Management"
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("setup", help="Check system and print setup instructions")
    sub.add_parser("build", help="Build firmware")
    sub.add_parser("flash", help="Flash firmware to keyboard")
    sub.add_parser("check", help="Full system diagnostics")

    args = parser.parse_args()

    commands = {
        "setup": setup,
        "build": build,
        "flash": flash,
        "check": check,
    }

    if args.command in commands:
        commands[args.command]()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
