# EPOMAKER Split65 — Battery reporting: findings and design

> **Scope.** This narrates the **battery-feature work**, which is committed in
> the `qmk_firmware` submodule. The layered helpers below (`wls/wls_battery.c`,
> `WLS_BATTERY_PUSH_*`, the strong `raw_hid_receive` override) are in the tree.
> See `TODO.md` Status.

Why the firmware is shaped the way it is, and which upstream facts a future
change depends on. What the device is is in `DEVICE.md`; measured hardware facts
live in `HARDWARE.md`; the wire format is `PROTOCOL.md`; live status and open
work are in `TODO.md`.

> **Reading order.** `Usage modes (derived)` → `Goal` → `Hardware / firmware
> base` are the frame. The `FINDING —` sections are self-contained; each states
> one conclusion and the evidence for it. `Design`, `Build facts` and
> `Dongle recon` are reference, not findings. Skip by heading.

## Contents

- Usage modes (derived) · Goal · Hardware / firmware base — the frame.
- **Findings**: the vendor fork is shallow (re-base is a replay) · the battery
  value already exists in firmware · raw HID is already bridged over the dongle ·
  the wireless stack is shared · the deep-sleep `PRE_LP()`/`POST_LP()` blobs ·
  Bluetooth is a dongle-free path · upstream already ships the battery and
  connection APIs · what stays bespoke · upstream is already defining the API we
  would invent · shared state has no owner · the vendor split stack is closer to
  upstream than it looks · the three power-off faults are one defect · upstream
  has no sleep invariant · the wake-armed predicate was a proxy · the WB32 EXTI
  aliases pads · the USB path has a second sleep route · the sleep decisions are
  a functional core · the wireless stack is a documented third-party protocol,
  not an Epomaker invention · the board is an ODM product (MATHEW candidate /
  Shenzhen Changyun named by certification) · the boot switch read is
  un-settled, and UNKNOWN is silently applied · the low-power presleep hook cut a
  live USB line, giving a periodic reset loop · **the recurring defect is one
  class with two shapes (feedback and ordering), and the remedy is a gate the
  component owns, not a guard each caller remembers** · **the boot instrument is
  a Dell-style `(amber, white)` code — the old field-per-step blink was
  unreadable for four reasons, including an ordering fault of that same class** ·
  **a reset loop is proved by the chip's own latch (`RCC->RSTSTAT`), not by an
  instrument that counts boots** · **the shell held policy — a show bound and a
  clock origin — which is why the boot-code miscount was untestable**.
- Design · Build facts · Dongle recon — reference.
- Open questions tied to these findings.

## Usage modes (derived)

**These are *engineering* modes — the transport behaviours the firmware must have,
in priority order — and they are *derived from* the user-facing requirements in
`docs/UX-REQUIREMENTS.md` § 1.5, not a layer beside them.** The user-facing
requirements (what a person must be able to infer from the keyboard, and the
method that derived them) are the parent; these modes are their engineering form.
An engineering mode has no independent authority — it can be wrong only by failing
to serve its user-facing parent, and each mode below names the X-n it serves. The
2026-10-14 dark board satisfied all three modes and still presented a dead
keyboard, which is why the user-facing set is the one that governs.

1. **Wireless while discharging** — serves **X-20**, **X-24**. Both halves
   operate on a wireless transport (2.4 GHz or Bluetooth) with no cable attached.
2. **Wireless while charging** — serves **X-20** (§ 1.2: this mode *is* the
   library-laptop circumstance). Both halves operate on a wireless transport
   while a cable supplies charge (to the battery-bearing left half; see
   `HARDWARE.md` "Batteries").
3. **USB while charging** — serves **X-4**, **X-20**. Both halves operate over
   USB-C with a cable attached.

**Why mode 2 exists.** A cable that only *powers* the keyboard — a wall
charger, a power bank, a USB hub's charging port — must not change the transport:
the board should keep typing over its wireless link while charge comes from the
cable. So "a cable is present" must not by itself mean "switch to USB".

**Wording corrected 2026-10-14.** This mode previously read "charge from an
external PSU while connecting to a *different, power-limited host* (e.g. a phone
or tablet)". That is not realisable and was wrong: there is ONE USB-C port, and
a phone is a real USB host that enumerates exactly as a PC does. On a single port
the board cannot distinguish "a phone supplying charge" from "a PC", so
"a real host on the cable" and "a power-only supply on the cable" cannot be told
apart by any means available to the firmware. Mode 2 therefore means what
is implementable and was always the intent: **a power-only cable must not force
USB; the switch stays authoritative; a real enumerating host still wins.** (A
phone attached as a host is precisely the "real host" case and correctly takes
USB — it is mode 3.) The rule is `hsm_input_rule` in
`wls/transport_logic.{c,h}`: the cable is a *power* fact and reaches no transport
decision at all.

**CONFIRMED ON HARDWARE 2026-10-14** (build `aec73138…`, 64,600 B). With the
switch on 2.4 GHz and the host cable attached, the board **stays on the radio**:
the raw-HID `0xA4` request gets no reply, which is the expected signature of a
non-USB committed transport (`--info`'s own message: "On a keyboard whose
committed transport is not USB, this is expected — keystrokes and the report path
go to the module, not the host"). The USB peripheral remains enumerated, so the
board charges. **The pre-reform build measurably did the opposite** — `switch=3
(2.4G)` with `host(raw)=2 (USB)`, the cable forcing USB and stranding the radio.
This is the reading that closes mode 2; § 7's falsifier did not fire.

Note the limit of this evidence: `host(raw)=4` **cannot be read directly** in this
state (the `0xA4` reply is unreachable while the transport is not USB — the
wireless driver has no `.send_raw_hid`), so the confirmation is "no reply + still
enumerated" rather than a positive field read. The discriminating test is that it
*types* on the radio.

**Accepted tradeoff.** The firmware's cable-insert auto-switch (in
`housekeeping_task_user()`) forced `DEVS_USB` when a cable appeared, which would
defeat mode 2. Removing it is sanctioned: the keyboard has a physical
mode switch, so mode selection can belong to the switch alone. `hs_modeio_detection()`
already forces `DEVS_USB` when the switch is in the USB position, and
`wls_process_long_press()` already makes `KC_BT*`/`KC_2G4` no-ops unless the
switch reports BT/wireless — so the switch becomes the single, coherent control.
The same reasoning was applied to the second cable consumer, the pure
`hsm_switch_apply_with_cable` (which forced USB on any cable read): it was
replaced by `hsm_input_rule`, so no cable read reaches the transport decision.

**Unverified.** Whether VBUS presence disturbs the module UART or the radio link
is unknown; nothing in the firmware gates wireless on `charging_state`. That is
evidence to gather (`TODO.md`), not established fact.

## Goal (reporting mechanism)

Expose the keyboard battery to the host over all three transports (2.4 GHz
dongle, Bluetooth, USB-C) via the `0xA4` raw HID command, so a polybar module
can display it. Transport logic is layered so every transport shares one code
path.

## Hardware / firmware base

- MCU **WB32FQ95** (Artery WB32), bootloader **wb32-dfu**.
- Upstream is `github.com/hangshengkeji/qmk_firmware`, branch `tri-mode`, which
  contains `keyboards/epomaker/epomaker_split65/` and the wireless stack at
  `keyboards/linker/wireless/` (pulled in by the board's `post_rules.mk`). There
  is **no** `keyboards/wireless/` in the pinned tree (the legacy copy exists only
  in the vendor's own history, and is deleted in the spike — see "the vendor fork
  is shallow" below).
- The board source is a sibling port of the same EPOMAKER board found in
  `qmk/qmk_firmware`; that upstream tree is newer but lacks the wireless stack.
  Re-basing is now the organizing priority (Tier 0) — see "the vendor fork is
  shallow" below.

## FINDING — the vendor fork is shallow, so a re-base is a replay, not a re-import

The vendor tree carries full upstream lineage, not a squashed snapshot; its last
upstream sync (`92afc8198a`, 2024-10-29) is our true base, after which the vendor
forked to build the wireless stack. **The conflict surface is almost nil:** of the
677-file / 81,873-line divergence, only two non-board files differ (`.gitignore`
dropping `*.a`, plus a stray `.txt`) and three submodules bumped; everything else
is additive vendor boards plus the shared wireless stack. **WB32 platform support
is already upstream at the base**, so no platform fork was needed. Our own
authored payload is ~10 commits confined to `epomaker_split65/` and
`linker/wireless/` with no core edits — so re-basing is "replay our commits onto
master", not a fork re-import. It is done and builds green; the `libmodule.a`
"red flag" was a non-issue (it lived only in the obsolete `keyboards/wireless/`
copy and held nothing but objects compiled from source we already hold). Record
in `TODO.md` "## Re-base".

## FINDING — the battery value already exists in firmware

The wireless stack tracks it; the board only had to route it to the host. All
paths are in `qmk_firmware/keyboards/linker/wireless/`:

- `module.c`: `md_info_t.bat` is updated from the wireless module via
  `MD_REV_CMD_BATVOL (0x5C)` → `md_info.bat = md_rev_payload[1];`, read through
  `uint8_t *md_getp_bat(void)`.
- The keyboard has **no ADC** and never measures its own charge. It asks the
  module: `md_inquire_bat()` → `md_send_devctrl(MD_SND_CMD_DEVCTRL_INQVOL)`
  (`0x53`), driven every `WLS_INQUIRY_BAT_TIME` (3000 ms) from `wireless_task()`
  (`wireless.c`).
- `uint8_t *md_getp_state(void)` gives the link state, compared against
  `MD_STATE_CONNECTED`.
- `charging_state` and `bat_full_flag` are board-level GPIO reads
  (`HS_BAT_CABLE_PIN` / `BAT_FULL_PIN`), not module telemetry — see
  `HARDWARE.md`.
- `KC_BATQ` already existed to request the *visual* indicator. The work was to
  route the value to the host.

## FINDING — raw HID is already bridged over the 2.4 GHz dongle

`keyboards/linker/wireless/md_raw.c` (guarded by `RAW_ENABLE`):

- `md_receive_raw_cb()` calls `raw_hid_receive(data, length)` — the receive path.
- The send path has no board glue: upstream `raw_hid_send()` →
  `host_raw_hid_send()` selects the driver from the connection host, so `md_send_raw()`
  tunnels over the module UART whenever the host is not USB.
- The tunnel carries `MD_RAW_SIZE = 32`-byte reports in **both** directions, so
  host pull works over 2.4 GHz as well as USB. Push is retained as a fallback
  only.

This matters because it is why no custom transport code was needed: the vendor
stack already forwards raw HID both ways.

## FINDING — the wireless stack is shared; keep the divergence to one file

`keyboards/linker/wireless/` is the vendor's **shared wireless stack** (other
boards in the vendor's own tree include its `wireless.mk`; in the pinned tree only
Split65 does). Split65 therefore does **not** carry a copy of the whole
stack. Its `wireless/wireless.mk` sources the six shared files
(`wireless.c`, `transport.c`, `lowpower.c`, `md_raw.c`, `smsg.c`, `module.c`)
from `keyboards/linker/wireless` and keeps only `lpwr_wb32.c` board-local — the
one file the deep-sleep fix actually changes. `VPATH` lists the board dir first
so `lpwr_wb32.c` resolves locally and everything else falls through to the
shared dir.

Consequences: the divergence from vendor is a **one-file diff** (drift is
visible, and vendor fixes to the shared stack reach this board automatically),
and the board does not fork the transport logic. The pattern is the same one
`keyboards/cannonkeys/satisfaction75` uses (`VPATH += keyboards/cannonkeys/lib/...`).
The board does not fork the transport logic at all: in the landed tree, no
shared-stack file except `lpwr_wb32.c` differs from the vendor overlay (the
promised one-file divergence), so every board using the stack keeps its own copy
untouched.

## FINDING — the deep-sleep `PRE_LP()`/`POST_LP()` blobs are raw Thumb, and they deobfuscate

`lpwr_wb32.c` enters and leaves deep sleep through two `uint32_t[]` arrays of raw
machine code, cast to function pointers with the Thumb bit set:

```c
static const uint32_t pre_lp_code[]  = {553863175u, ...};
#define PRE_LP()  ((void (*)(void))((unsigned int)(pre_lp_code)  | 0x01))()
static const uint32_t post_lp_code[] = {553863177u, ...};
#define POST_LP() ((void (*)(void))((unsigned int)(post_lp_code) | 0x01))()
```

These are **not** obfuscated — they are the compiler's literal output for
hand-tuned register writes the author needed to pin exactly (no C prologue, no
register-allocation surprises, no reordering). The bytes are **identical in every
copy** in the tree and in both vendor factory images (`vendor/factory-firmware/`,
v7 Nov 2024 and v10 Dec 2025) exactly once, byte-identical — proof they are frozen
output, not something our tree introduced. Both blobs unlock the analog-control
(ANCTL) write lock, clamp/sync a trim field, omit any settling loop (a short one
in `POST_LP`), and return; all addresses are documented WB32 peripherals except
`0x1FFF0000 + 0x310`, an undocumented factory/trim mirror read by raw literal.

Deobfuscate with `arm-none-eabi-objdump -D -b binary -m arm -M force-thumb` on the
`w.to_bytes(4,'little')` stream of the array; the full dual listing lives in the
git history (`git log -p -- docs/FINDINGS.md`).

**Do not rewrite them in C as a "cleanup".** They are timing-critical and use only
`r0–r2`, so they are safe to call from any context including the low-power path;
since they are byte-identical across every board on the stack, rewriting them
would fork a shared file for zero gain. They are the one place the compiler must
not be trusted to schedule.

## Design

Layered so the transports share one code path. Wire format: `PROTOCOL.md`.

1. **Battery source abstraction** (`wls/wls.c`): `kb_battery_snapshot()` exposes
   `percent`/`charge`/`transport` in one struct. The *value* is upstream's —
   `percent` comes from `battery_get_percent()` (`quantum/battery`, fed by the
   `custom` driver `wls/wls_battery_driver.c`), not a board-local function.
   Board-local helpers remain for `charge` (0/1/2 from
   `charging_state` / `bat_full_flag`), `kb_battery_transport()` (from
   `wireless_get_current_devs()`), `kb_battery_changed()` (change detection for
   push), and `kb_battery_snapshot()` (samples transport/percent/charge **once**
   into a `kb_battery_snapshot_t`, so detection and report assembly see the same
   sample).
2. **Raw HID responder** (`wls/wls_battery.c`): a strong `raw_hid_receive()`
   override (`#ifndef VIA_ENABLE`) that replies to `0xA4` and stays silent for
   any other command — an unsolicited reply would collide with other raw HID
   clients. Master half only.
3. **Transport tagging**: `0x01` USB / `0x02` BT / `0x04` 2.4 GHz.
4. **Push fallback**: `kb_battery_push_task()` is called from the existing
   `wireless_post_task()`. It sends on **change** (level/charge/transport), with
   `WLS_BATTERY_PUSH_INTERVAL` (10 s) as a slow keepalive bound on staleness,
   when non-USB, connected, and master. Gated by `WLS_BATTERY_PUSH_ENABLE`.
5. **Host side** (`host/battery_polybar.py`): enumerates by usage page `0xFF60` /
   usage `0x61`; supports `--pull`, `--listen` and `--bluetooth` (BLE Battery
   Service `0x180F`/`0x2A19` fallback), prints `BAT <n>%` / `CHG <n>%`, and
   hides when absent.
6. **Bluetooth path**: probed, and **broken in a known way** — the module
   advertises and accepts a bond, but its HID GATT server rejects the CCC
   notification-enabling writes with ATT `0x0E`, so no input flows. Whether the
   BT link exposes the raw HID collection and whether `*md_getp_bat()` is
   populated over BT is therefore **still unmeasured** (it cannot be reached
   while the CCC write fails); the host falls back to BLE Battery Service
   `0x180F`/`0x2A19` either way. Tracked in `TODO.md`; capability derivation in
   `docs/UX-REQUIREMENTS.md` § 0.7.

## Build facts

- Build via the project wrappers from the repo root: `./bin/make
  epomaker/epomaker_split65:<keymap>`. Current sizes and artifact md5s are
  recorded in `TODO.md` Status — they change with every keymap edit, so treat
  them as a freshness check, not a constant.
- `raw_hid_receive` links as a strong `T`, overriding the weak default at
  `quantum/raw_hid.c:11`.
- **EEPROM is versioned.** `confinfo_t` (`epomaker_split65.c`) is a 32-bit union
  persisted via `eeconfig_kb`; adding/altering a field changes its layout.
  `CONFINFO_VERSION` must be bumped whenever it does, and
  `eeconfig_confinfo_init()` re-defaults (once) when the stored `version`
  differs, rather than guessing per-field. The struct is exactly 32 bits — a new
  field must fit or the union must be widened.
- **VIA is not enabled** (`VIA_ENABLE` unset), so the hook is the strong
  `raw_hid_receive()` override, not `via_command_kb()`. The VIA definition
  (`host/epomaker-split65-via.json`) is for external VIA tooling and keymap
  import; it is
  not a claim that the firmware speaks VIA.
- **The raw-HID tunnel needs no board-private send path.** The receive side is
  `md_receive_raw_cb()` (`md_raw.c`), which forwards a module-tunneled frame to
  `raw_hid_receive()` exactly as the USB path does. The send side has no board
  glue at all: `raw_hid_send()` (upstream) calls `host_raw_hid_send()`, which
  selects the driver from the connection host
  (`host_get_active_driver()->send_raw_hid`) — the USB endpoint, or the
  Bluetooth/2.4 GHz module sink. **The old design was different and is gone:** a
  line-pinned macro remap in `md_raw.h` rewrote `raw_hid_send` to
  `replaced_hid_send` at two fixed `__LINE__`s, so a submodule bump that shifted
  either line would silently break the tunnel. `md_raw.h`, `replaced_hid_send()`
  and the CI guard that asserted those line numbers have all been **deleted**;
  the transport selection is now upstream's, so a submodule bump cannot break it
  silently.

## Dongle recon

Device `342d:e4c6` "MILE 2.4G Dongle", three HID interfaces:

- iface 0: keyboard, mouse, consumer, system, LEDs, plus a vendor block.
- iface 1: 120-key bitmap, no report ID.
- iface 2: the raw HID tunnel — usage page `0xFF60`, usage `0x61`, 32-byte IN
  and OUT. Identical to QMK's own raw collection.

Full device description: `DEVICE.md` "Accessories".

`hid.enumerate()` confirms exactly one `0xff60/0x61` interface on the dongle.
A live probe writing `[0x00, 0xA4, ...]` to it reaches the keyboard over the
radio and the reply comes back.

The dongle firmware is **not** in the QMK tree. Dumping it would require
entering its DFU bootloader (physical BOOT pads, same as the keyboard); the
optional command is
`wb32-dfu-updater_cli -t -s 0x08000000 -U dongle.bin`. Not done, not required.

## FINDING — Bluetooth is a dongle-free path to the same radio, and upstream BT is not our shape

Two facts that matter for testing and for the eventual upstream port.

**The battery inquiry is transport-gated, and USB is the only blocked transport.**
`wireless_task()` (`keyboards/linker/wireless/wireless.c:252-258`) only calls
`md_inquire_bat()` when the transport is **not** USB:

```c
if (connection_get_host() == CONNECTION_HOST_USB) {
    usb_remote_wakeup();
} else if (lpwr_get_state() == LPWR_NORMAL) {
    if (sync_timer_elapsed32(inqtimer) >= WLS_INQUIRY_BAT_TIME) {
        if (md_inquire_bat()) inqtimer = sync_timer_read32();
    }
}
```

The reply handler (`MD_REV_CMD_BATVOL`, `module.c:232-233`) is transport-agnostic.
So **Bluetooth populates `md_info.bat` exactly as 2.4 GHz would** — which makes BT
a **dongle-free substitute** for the blocked 2.4 GHz tests: the real battery
percentage (and the ground truth defect 1's honesty fix needs), the real
transport field, and mode 2. The raw-HID tunnel is likewise
transport-agnostic (the send path rides upstream `host_raw_hid_send()`, so
`md_send_raw()` is used whenever the transport is not USB). Caveat: the module is the single radio for
both 2.4 GHz and BT, so a BT *failure* would be ambiguous (module vs host), but a
BT *success* proves the module radio alive and yields the real reading.

**Upstream's Bluetooth subsystem does not fit this board — but there is a seam to
conform to later.** `docs/features/wireless.md` scopes upstream BT to **AVR only**:
RN-42 (UART, `BLUETOOTH_DRIVER = rn42`) and Adafruit Bluefruit LE SPI Friend (SPI,
`bluefruit_le`); Bluefruit LE UART / HC-05 / HM-13 are "Not Supported Yet". This
board's BT is a **third-party UART module** (the same chip that does 2.4 GHz) with
**multi-profile BT (BT1–BT5)**, driven over the vendor `module.c`/`smsg.c` UART
protocol and selected by the physical mode switch — neither RN-42 nor Bluefruit,
on a ChibiOS/WB32 ARM MCU. Nothing upstream can be reused directly, and for the
immediate test upstream is irrelevant: our BT runs entirely through the vendor
stack, not `host_driver_t bluetooth_*`.

The upstream-shaped seam for the contribution is the **`custom` driver type**:
`builddefs/common_features.mk:905-927` lists
`VALID_BLUETOOTH_DRIVER_TYPES := bluefruit_le custom rn42`, and the driver
contract is `drivers/bluetooth/bluetooth.h` (`bluetooth_init/task/is_connected/
can_send_nkro/keyboard_leds/send_{keyboard,nkro,mouse,consumer,system,raw_hid}`);
core wires it through `host_driver_t bt_driver` (`tmk_core/protocol/host.c:53-62`,
under `BLUETOOTH_ENABLE`) with `bluetooth_init()`/`bluetooth_task()` called from
`quantum/keyboard.c:541,792`. **A `BLUETOOTH_DRIVER = custom` implementing that
header is now in place** — `wls/wls_bluetooth.c`, selected by
`BLUETOOTH_DRIVER = custom` in `post_rules.mk` and `"bluetooth": true` in
`keyboard.json` — mirroring what we did with `BATTERY_DRIVER = custom`. It is a
thin adapter over the vendor module stack: it gates every call on the current
device being a BT profile (`DEVS_BT1..DEVS_BT5`), because otherwise upstream's
`connection_auto_detect_host()` would resolve `CONNECTION_HOST_AUTO` to Bluetooth
on USB and 2.4 GHz too (the module UART reports `MD_STATE_CONNECTED` on every
transport). Of the upstream BT keycodes, only `QK_OUTPUT_BLUETOOTH` is
implemented; the profile/unpair/2.4 GHz keycodes are all still "(not yet
implemented)". The driver is inert until a BT profile is selected — the vendor
stack still owns the module lifecycle and the `host_driver_t` swap, and this
driver is the path upstream's `bt_driver` takes once `active_host` is
`CONNECTION_HOST_BLUETOOTH`.

## FINDING — upstream already ships the battery and connection APIs; adopt, don't maintain

The re-base makes two upstream features usable that the vendor tree could not
have had: `quantum/battery/` and `quantum/connection/`. Both are now enabled on
the spike and the vendor's parallel code is replaced rather than kept.

**Battery — upstream owns the sampling and the cache.** `quantum/battery/`
calls `battery_init()`/`battery_task()` from core (`quantum/keyboard.c`),
sampling every `BATTERY_SAMPLE_INTERVAL` (30 s) through a driver, caching the
result, and exposing `battery_get_percent()` plus weak
`battery_percent_changed_user/kb(uint8_t)` hooks. The driver contract is small
and is the intended hook for a non-ADC source: the `custom` driver needs only
`void battery_driver_init(void)` and `uint8_t battery_driver_sample_percent(void)`
(`drivers/battery/battery_driver.h`); `BATTERY_DRIVER = custom` in
`post_rules.mk` makes the build skip the bundled driver compile. Our
`wls/wls_battery_driver.c` is that driver — it returns `*md_getp_bat()`, the
module's UART-reported level, clamped to 100. The vendor's own
`kb_battery_percent()` is deleted; `kb_battery_snapshot()` now fills its
`percent` field from `battery_get_percent()`.

What stays board-local: the `0xA4` raw-HID **responder** (`wls/wls_battery.c`).
Upstream has no host-visible battery command, so this remains ours. The
distinction matters — upstream owns the *value*, the board owns the *wire*.

**Connection — upstream is a state store, not a transport driver.** This is the
non-obvious one. `quantum/connection/` records a `desired_host` in EEPROM
(`eeconfig_read_connection`) and fires `connection_host_changed_user/kb(host)`;
it never calls `host_set_driver()`, never touches USB, and its 2.4 GHz candidate
is `#if 0`-disabled in the candidate array. `connection_set_host()` is a no-op
when the value is unchanged. So it cannot by itself switch transports on this
board — the vendor's `wireless_devs_change()` / `set_transport()` remains the
transport authority.

The board therefore **bridges** the two: `connection_host_changed_kb(host)` maps
`CONNECTION_HOST_USB` → `DEVS_USB`, `2P4GHZ` → `DEVS_2G4`, `BLUETOOTH` →
`confinfo.last_btdevs` (fallback `DEVS_BT1`), and ignores `AUTO`/`NONE`; then
applies it through `wireless_devs_change()`. The vendor keycode path
(`KC_BT1`/`BT3`/`KC_2G4`) now routes through `connection_set_host()` instead of
calling `wireless_devs_change()` directly, so upstream owns the user-facing
selection and the EEPROM record, while the vendor keeps the `DEVS_*` enum and its
BT1–BT5 profile model. The deferred long-press re-pair path still calls
`wireless_devs_change(..., true)` directly, preserving pairing/reset.

**Enabling them.** `BATTERY` and `CONNECTION` are `GENERIC_FEATURES` entries
(`builddefs/generic_features.mk`), so they are turned on with
`keyboard.json` `features: {battery: true, connection: true}` — which also sets
`BATTERY_ENABLE`/`CONNECTION_ENABLE`. This is the correct standalone switch for
`CONNECTION`: `common_features.mk` only sets `CONNECTION_ENABLE` as a side effect
of `BLUETOOTH_ENABLE` and has no block of its own. Note `quantum/quantum.h`
auto-includes `battery.h` but **not** `connection.h`, so the board `.c` includes
it explicitly.

**Consequence.** Adopting the upstream battery API retired the
`kb_battery_snapshot_t`/`kb_battery_percent()` naming from the pre-rebase design
(`kb_battery_percent()` no longer exists; the clamp now lives in
`wls_battery_driver.c`). `docs/PROTOCOL.md` scopes to the wire format and the
responder, not the internal value source. This is the ownerless-shared-state
cleanup arriving for free: the value's owner is now upstream core, and only the
wire stays board-local.

## FINDING — what stays bespoke, and why it is not superseded

After the re-base, the question "are we maintaining code upstream has
superseded?" has a precise answer: **no, with one deliberate exception that is a
superset, not a duplicate.** The re-base already retired the two genuine cases
(battery, connection). What remains is the wireless/tri-mode layer, which
upstream does not implement at all.

**Already upstream (adopted or stock, not ours to maintain):** the battery value
(`quantum/battery`, via our `custom` driver — see above), the connection
selection (`quantum/connection`, with our `connection_host_changed_kb()` as a
deliberate adapter), the split transport and RPC (`quantum/split_common`,
`transaction_rpc_*`), and core keyboard/RGB/encoder/raw-HID/EEPROM/bootmagic/NKRO.
`SPLIT_WATCHDOG_ENABLE` / `SPLIT_ACTIVITY_ENABLE` are upstream options.
`SPLIT_WATCHDOG_ENABLE` was tried and reverted: its slave-side re-arm depends on
a one-way master ping, which reset-looped this board's slave (~3 s) — it is
deliberately left off, matching the vendor firmware (see the regression section in
`TODO.md`). `SPLIT_ACTIVITY_ENABLE` is enabled (via `keyboard.json`
`split.transport.sync.activity`).

**Genuinely bespoke, and upstream has no equivalent (this is the contribution,
not a leftover):**

- **The wireless stack** (`keyboards/linker/wireless/`): module UART protocol,
  the module state machine, the WB32 deep-sleep `PRE_LP()`/`POST_LP()` blobs.
  Upstream's wireless is **AVR-only** — RN-42 and Bluefruit LE SPI Friend only
  (`drivers/bluetooth/`, `docs/features/wireless.md`) — and it documents 2.4 GHz
  and most wireless keycodes as **"(not yet implemented)"**. Upstream has no
  module-UART protocol for our class of board.
- **The `0xA4` battery responder** (`wls/wls_battery.c`): upstream exposes a
  battery *value* but has no host-visible battery command. The wire stays ours.
- **`rgb_record`**: a small board-local RGB persistence shim with no upstream
  equivalent.

**The one uncomfortable spot (parallel mechanism, not duplication):** our
`host_driver_t wireless_driver` plus `set_transport()` sits beside upstream's
`bt_driver` in `tmk_core/protocol/host.c` — two implementations of the same
"swappable `host_driver_t`" idea, for different transports. Ours must exist
(upstream has no driver for our module), but the **shape** should align: present
the module as one more `host_driver_t` alongside `bt_driver`, rather than a
parallel swap path. This is the single consolidation candidate.

## FINDING — upstream is already defining the API we would invent, and we should follow it

The wireless work is **not duplicating anything merged**, but it is on a
**collision course with unmerged upstream PRs that propose the exact layering our
audit independently derived.** Follow their shape rather than inventing ours.

**Nothing on our axis has landed.** On `qmk/master` `7a1bbf37c5`: `drivers/wireless/`
does not exist; `WIRELESS_2P4GHZ` appears nowhere in `builddefs/`; and
`quantum/connection/connection.c` still has `CONNECTION_HOST_2P4GHZ` behind
`#if 0` in `host_candidates[]` (the keycode is wired in
`process_keycode/process_connection.c`, but the host is unreachable by cycling).
Only the connection *keycode* ever merged (PR 24251, in our base).

**The upstream proposals, and why they matter to us:**

- **PR 26203 — "enable/implement 2.4 GHz wireless dongle API" (damex).** Closed
  by the stale bot (2026-08-04), **not rejected**. It proposes precisely the
  layering this project derived: a `drivers/wireless/wireless_2p4ghz.{c,h}`
  dispatcher with weak hooks (`init`, `task`, `is_connected`, `can_send_nkro`,
  `keyboard_leds`, the `send_*` family, `unpair`); a `wireless_2p4ghz_driver`
  `host_driver_t` in `tmk_core/protocol/host.c` selected when
  `active_host == CONNECTION_HOST_2P4GHZ`; auto-detect via
  `wireless_2p4ghz_is_connected()`; a `QK_2P4GHZ_UNPAIR` keycode; enabled with
  `WIRELESS_2P4GHZ_ENABLE` + `WIRELESS_2P4GHZ_DRIVER = custom`. That is the
  `host_driver_t`-swap + dispatcher shape, arrived at independently here.
- **PR 26207 — "implement bt/2.4 GHz fr800x driver" (damex).** **OPEN.** A
  `drivers/fr800x.{c,h}` shared core for the Freqchip fr8003a UART module —
  state machine, opcode framing, three BT slots plus a dongle, battery query,
  charging relay — with thin `drivers/bluetooth/fr800x.c` and
  `drivers/wireless/fr800x.c` adapters. It is the **same category as our
  module stack, for a different chip**, and its body says it is "modeled on how
  the existing bluetooth driver api is implemented". If 26203+26207 land,
  `WIRELESS_2P4GHZ_DRIVER` becomes real and our stack should be **one more
  driver behind that API**, not a parallel `keyboards/linker/wireless/` layer.
- **PR 24365 — "Host driver (wireless) rework, phase 1" (tzarc).** Open draft,
  stalled ~1.5 years, but it is the maintainer-sanctioned `host_driver_t` swap
  direction ("swap around outputs dynamically"). Confirms the target; not
  dependable to land.

**Consequence for our plan.** The layering step below is no longer *our* design
choice — it is **"conform to the pending upstream shape."** Target
`WIRELESS_2P4GHZ_DRIVER = custom` and a `drivers/wireless/` dispatcher as PR
26203 defined them, so our driver drops in behind the upstream API instead of
racing it. `damex` is the author to engage before writing more, and the U1 RFC
should cite 26203 / 26207 / 24365 explicitly rather than proposing an API from
scratch. This supersedes the earlier framing of the layering decision as an open
design question.

**Alignment plan (for the eventual upstream merge).** QMK review is mechanical,
and most of it is already satisfied (`qmk lint` is clean on the spike). The
remaining work is sequenced cheapest-first and happens **on the spike branch**,
because formatting churn on 44 vendor-derived files would wreck cherry-pickability
against the vendor overlay:

1. **Formatting + licensing** — `qmk format-c` / `format-json -i` / `format-text`,
   plus GPL-2.0-or-later SPDX headers on every authored source (a common
   review-blocker).
2. **Naming / hook conventions** — move the vendor's `wls_*`/`kb_*`/`hs_*` prefixes
   toward upstream idioms, with `_kb`/`_user` hook suffixes and `xxx_init`/`xxx_task`
   pairs where core calls them. The adopted battery driver is the template.
3. **Layering — CONFORM to the pending upstream shape (no longer a design
   question).** Target `WIRELESS_2P4GHZ_DRIVER = custom` behind a
   `drivers/wireless/wireless_2p4ghz.*` dispatcher and a
   `host_driver_t wireless_2p4ghz_driver` in `tmk_core/protocol/host.c`, exactly
   as PR 26203 defines it (see "upstream is already defining the API" above).
   Our module stack becomes one driver behind that API rather than a parallel
   `keyboards/linker/wireless/` layer. This also resolves the `host_driver_t`
   alignment above. Upstream has no precedent for a shared dir under
   `keyboards/`, which is why the stack must move behind the driver contract.
4. **`libmodule.a` — RESOLVED (not a blocker).** The archive lived only in the
   obsolete `keyboards/wireless/` directory, which no board linked (no
   `-lmodule` in any build); the live stack is `keyboards/linker/wireless/` with
   `module.c`/`smsg.c` as source. The legacy directory is deleted in the spike
   (commit `f1ee1f3`), so no vendored binary remains. See `TODO.md`, Re-base.

## FINDING — shared state has no owner; two contained fixes

The board and the wireless stack communicate through **shared mutable globals**
(`lower_sleep`, `charging_state`, `bat_full_flag` externed in `wls.h`;
`wireless_get_current_devs()`; the `confinfo` EEPROM mirror) rather than a
board-facing API. Nothing enforces who may change what, so correctness depends on
each caller "knowing" not to fire a transition at the wrong moment. That property
produced two of the three hardware defects found here (the battery `100` on USB
and the unwakeable slave); the third (the wrong host interface pick) is a
separate class, and is fixed separately. (The same root property recurs in the
power-off faults — see "the three power-off faults are one defect".)

Two of those are addressable *within our files*, without touching the shared
vendor stack (so upstream divergence stays a one-file diff):

- **Transport arbiter is now a no-op.** `hs_transport_arbitrate_cable()` used to
  own the cable insert/remove policy (switch to USB on insert; restore
  `confinfo.last_wireless_devs` on remove). It was deliberately gutted to a
  `return false;` stub so a cable no longer forces USB, which is what engineering
  mode 2 needs: mode selection now belongs solely to the physical switch
  (`hs_modeio_detection()` in `wls/wls.c`). Both `housekeeping_task_user` and
  `lpwr_wakeup_hook` still call it, so the two paths stay in one place.
- **Atomic battery snapshot.** `kb_battery_snapshot_t` + `kb_battery_snapshot()`
  sample `percent`/`charge`/`transport` **once**; the change check
  (`kb_battery_changed()`) and the report assembly (pull and push) are both built
  from that one sample, so they cannot observe a torn state.

The **general** fix — a real board-facing API replacing the externed globals — is
deliberately **not** done. It is upstream-sized (it would touch the shared stack
and every board that uses it) and belongs in the U1 RFC's scope, not a local cleanup. The two
contained fixes capture most of the benefit at a fraction of the blast radius,
since verifying a board rearchitecture requires physical reflashing of both
halves with a hardware-only recovery path.

## Open questions tied to these findings

- **Is byte 1 ever real?** See `TODO.md` defect 1. Until the module answers the
  inquiry on USB, the value is indistinguishable from the init constant.
- **Which interface did the host pick?** Resolved — `TODO.md` defect 3 (closed).
- **Does Bluetooth expose the raw collection at all?** See `TODO.md`, Tier 2.

## FINDING — the vendor split stack is closer to upstream than it first looks

QMK's own split-keyboard documentation (`docs/features/split_keyboard.md` in the
pinned tree; same text as `docs.qmk.fm/features/split_keyboard`) was read against
the actual board source. It is **relevant and correct**, and it shows the vendor
already uses upstream mechanisms in the places that matter — so the U1 upstream
port should **extend** them, not reinvent them.

**Verified against the tree (not assumed from the doc):**

- **Upstream's transaction API is already in use.** The board declares
  `#define SPLIT_TRANSACTION_IDS_USER USER_SYNC_MMS` (`config.h:90`), registers a
  slave handler with `transaction_register_rpc(USER_SYNC_MMS, ...)`
  (`epomaker_split65.c:216`), and drives it with `transaction_rpc_exec(...)` in
  five places (the mode-sync 0x55 / 0xCC / 0xAA paths). This is exactly QMK's
  documented "custom data sync between sides" mechanism. *(An earlier note in
  this project called the m2s/s2m link "hand-rolled" — that was wrong; it is
  upstream's RPC transport with vendor-chosen `cmd` bytes.)*
- **Handedness is upstream's hand-by-pin.** `keyboard.json` sets
  `split.handedness.pin B9`, generating `SPLIT_HAND_PIN B9` — the doc's
  "Handedness by Pin" method, with high = left.
- **`SPLIT_USB_DETECT` is forced on for this board.** `platforms/chibios/chibios_config.h:20-22`
  defines it whenever `USB_VBUS_PIN` is **not** defined, and this board does not
  define that pin. So core would delegate master by USB communication — which is
  why the board's `is_keyboard_master()` override (to `gpio_read_pin(SPLIT_HAND_PIN)`,
  in each **keymap**) matters: it **supersedes** the core USB-role decision, pinning
  the role to handedness. The doc's own warning that `SPLIT_USB_DETECT` "will stop
  the ability to demo using battery packs" is precisely the reason a battery board
  prefers a pinned handedness — that is what this board does.
- **Supported transport.** ARM split with the `serial` / `serial_usart` driver is
  upstream-supported; the board uses `SERIAL_USART` (SD1 A9/A10).
- **The module UART must stay on SD3.** The board sets `UART_DRIVER SD3` (module,
  `C10`/`C11`) alongside `SERIAL_USART_DRIVER SD1` (split link, `A9`/`A10`). The
  old vendor alias layer that mapped `SERIAL_DRIVER`/`SD1_*` onto `UART_*` was
  removed upstream; without an explicit `UART_DRIVER` the module UART silently
  defaults to `SD1` and collides with the split link. Symptom: the slave's matrix
  rows never reach the master (master types, slave does not). See `TODO.md`
  "Regressions introduced by our own change set" §3.

**What upstream offers that the vendor does not yet use** (candidates for the U1
port, not defects today):

- **`SPLIT_WATCHDOG_ENABLE` / `SPLIT_MAX_CONNECTION_ERRORS`.** Tried and
  **reverted**: upstream's watchdog reset-loops a slave on this board because the
  slave's `done` flag can only be re-armed by a one-way master ping. The vendor
  stack's own low-power/disconnect handling stays; the watchdog is left off. (The
  `SPLIT_MAX_CONNECTION_ERRORS` retry throttle is part of
  `transport_master_if_connected()` and remains live independently.)
- **`SPLIT_ACTIVITY_ENABLE`.** Syncs activity timestamps so a sleep timeout can
  fire consistently across halves — already enabled via `keyboard.json`.
- **The other `SPLIT_*` sync options** (`SPLIT_MODS_ENABLE`, `SPLIT_LAYER_STATE_ENABLE`,
  …) are documented as cosmetic/OLED aids; the board has no display, so these are
  not needed.

**Conclusion for the upstream effort:** the split layer is *not* a place to
invent. The vendor already rides QMK's transaction RPC and handedness-by-pin.
The upstream-shaped contribution is the **wireless/battery** layer (radio,
low-power, module UART) — that is the genuinely novel part, and it should sit
*on top of* the standard split mechanisms rather than replacing them.

## FINDING — the three power-off faults are one defect: sleep has no enforced invariant

Three faults, chased separately, are the same architectural defect wearing
different masks:

1. **Slave reset-loops** (`SPLIT_WATCHDOG_ENABLE`) — the slave entered a state
   nothing could rescue; fixed by removing the watchdog.
2. **Slave dark-out** (idle timeout) — the slave entered STOP with no armed
   wake; fixed by making the slave never self-time-out.
3. **Master dark-out** (BT mode, current) — the master enters STOP and cannot be
   woken; the same class again, one half over.

Each was fixed at the point it bit. That is whack-a-mole. The real defect is
structural: **a half can enter an unrecoverable low-power state, and nothing
owns the decision or guarantees a way back.** The event loop has conventions
three call sites are trusted to honour, and no invariant it enforces.

What is missing, concretely:

- **No single owner of "may we sleep?".** The decision is spread across
  `lowpower.c` (`lpwr_is_allow_timeout`), the board hook
  (`lpwr_is_allow_timeout_hook`), `wls/wls.c` (`hs_rgb_blink_hook` sets the
  manual timeout), and config flags. Nothing states the rule in one place.
- **No invariant that *entering* a sleep arms a *wake*.** `mcu_stop_mode()` is
  entered with no check that any wake source is live. `lpwr_stop_hook_pre()`
  kills the LED rail unconditionally. `lpwr_exti_init()` arms wake sources from
  **hand-agnostic** static arrays: `static ioline_t row_pins[MATRIX_ROWS] =
  MATRIX_ROW_PINS;` where `MATRIX_ROW_PINS` lists only the **6** left-half rows
  into a **12**-element array — indices 6..11 are zero-filled (pin 0), so the
  loop arms 6 bogus entries. A half can therefore stop with the wake it needs
  unarmed and nothing detects it.
- **No recovery guarantee.** After `mcu_stop_mode()` resumes there is no check
  that it woke for a known reason, and no backstop if it did not.

**The invariant the loop should enforce** (the vendor `lpwr_*` state machine
already has the shape — `LPWR_NORMAL/PRESLEEP/STOP/WAKEUP` and a
`lpwr_wakeupcd` field — but no rule over it):

> Sleep is a decision only the master may take. A half stops only when the
> master orders it (which arms the wake sources first). Before `mcu_stop_mode()`
> at least one wake source must be armed, or the stop is refused.

Stated once, this subsumes all three masks. It is expressed in code as the
**sleep-policy contract**: `lpwr_stop_is_allowed()` (declared in `lowpower.h`)
reports whether the present stop is one the board may take, and the shared
`lpwr_stop_cb()` refuses the stop when it is false, falling back to
`LPWR_NORMAL`. The unsafe state is therefore unrepresentable at the single point
of commitment, regardless of which path led there. The board implements the
contract (this board: master && `lower_sleep`); the enforcement lives in the
shared state machine, so any board on the stack inherits it. This is the shape to
offer upstream — the subject of the U1 RFC. (The predicate was first named
`lpwr_wakeup_is_armed()`, which overclaimed: see the following finding, which
corrects both the name and the board's rationale.)

## FINDING — upstream has no sleep invariant, and our wireless stack *is* an upstream PR

Checked upstream before fixing the invariant, to keep the bespoke code minimal.
Result: **there is nothing to adopt — upstream has no low-power/sleep subsystem at
all, and the stack we carry is itself an open upstream PR.** The invariant above
is therefore novel work, not a reimplementation.

**No core sleep machinery exists.** A search across `quantum/`, `tmk_core/`,
`platforms/` and `docs/` for `lpwr`, `deep_sleep`, `low_power`, `allow_timeout`
and `wakeupcd` returns nothing. Upstream's own `platforms/chibios/suspend.c` is 55
lines beginning `/* TODO */` — the trivial AVR-shaped
`suspend_power_down()`/`suspend_wakeup_init()`, with no STOP mode, no wake arming
and no invariant. The split layer's only power-adjacent device is
`SPLIT_WATCHDOG_ENABLE` (`split_util.c`, `SPLIT_WATCHDOG_TIMEOUT` 3000,
`SPLIT_MAX_CONNECTION_ERRORS`) — the link-liveness watchdog already tried and
reverted here (it reset-loops our slave).

**Our wireless stack is PR #24209, still open and stalled.** "Update Tide65
keyboard to add wireless functionality" (sdk66, open 2024-07-29) upstreams
`keyboards/linker/wireless/` wholesale — `lowpower.c`/`.h`, `lpwr_wb32.c`,
`module.c`/`.h`, `smsg.c`/`.h`, `transport.c`/`.h`, `wireless.c`/`.h`,
`md_raw.c`/`.h` — which is exactly the shared stack this board carries. Activity
is cosmetic only; the latest comment (2025-12-21) says it builds on QMK 0.25.17
only after dropping a stray `quantum/rgblight/rgblight.c` change and a `.vscode/`
file, **relocating `linker/wireless/` into `epomaker/tide65/wireless/`** ("fix
improper location"), and correcting the `WIRELESS_DIR`/`post_rules.mk` includes.
No reviewer has flashed it, so the unbounded-sleep defect fixed here was never
seen. Our stack is *ahead* of its own upstream submission.

**Upstream has deliberately gated wireless boards on a core framework.** PR
# 24808 (Tide75) was closed unmerged, with tzarc: *"until true wireless support is
added to QMK core code, boards like this are on hold."* The label
`needs-core-wireless` (12 open PRs: AULA F75 Ultra, NuPhy Air60 V2 / Air75 v2, RK
R87Pro, Skylong GK87, redragon k715_pro, …) marks exactly this gate. The
manufacturer PR #23552 sits `invalid`/`crippled-firmware` since 2024-04.

**The core framework in flight — and it has no power handling.** PR #26207
"feat: implement bt/2.4ghz fr800x driver" (damex, open 2026-05-12) is the effort
that would satisfy that gate: `drivers/fr800x.{c,h}` (shared chip core: state
machine, framing, queue, init sequence `HANDSHAKE + SLEEP_BLUETOOTH_ENABLE +
SLEEP_DONGLE_ENABLE`, 3 BT slots + dongle, battery query, charge relay),
`drivers/bluetooth/bluetooth.{c,h}` and `drivers/wireless/wireless_2p4ghz.{c,h}`
adapters, `quantum/connection/`, and `process_connection.c`. It adds reconnection
(2 s retry while DISCONNECTED) but **contains no low-power/sleep code** — its only
"sleep" is the chip's RF sleep opcodes. So the invariant is unaddressed by the
core work too.

**Consequence for the effort.** The wake-source contract is the correct fix and
is *novel* relative to upstream. Because the enforcement now lives in the shared
`lowpower.c` (the contract is declared in `lowpower.h`, implemented per board),
it is genuinely new work to offer alongside #24209 / the wireless-core discussion
with `damex` — it could ride as the fix that stack needs. Recorded here so a
future agent does not re-search for an upstream sleep API that does not exist.

## FINDING — the wake-armed predicate was a proxy; the real fault is an unhandled wake code

Reading the **compiled** copy of `lpwr_wb32.c` (the board keeps its own, the
shared one is not built) corrects the rationale above, and locates the master
dark-out precisely.

**What the predicate claimed vs what is true.** The committed
`lpwr_wakeup_is_armed()` returns `is_keyboard_master() && lower_sleep`, with a
comment saying the board "has no unconditional wake source". The compiled code
contradicts that. On the idle path (`lower_sleep == false`), `lpwr_exti_init()`
arms, for a master: its **own** rows (`MATRIX_ROW_PINS`, FALLING_EDGE,
unconditional), drives its own columns (`open-drain` low, unconditional — the
shared copy gates this on `lower_sleep`, the board copy does not), the
mode-switch pins (`HS_BT_DEF_PIN`/`HS_2G4_DEF_PIN`, master-only but not gated on
`lower_sleep`), the cable pin, the split-link RX and USB `A12`. So the master is
wake-armed on **both** paths; `lower_sleep` does not decide whether the master
has a wake source. The refusal is therefore a **policy** choice (do not take the
unordered idle sleep), not a hardware necessity — and the `lower_sleep`-gated
EXTIs are only the *cross-half* column drive and the module-sleep command.

**What `lower_sleep` actually changes** (the whole of it):
1. `lpwr_stop_hook_pre()` — ordered sends `md_send_devctrl(MD_SND_CMD_DEVCTRL_USB)`
   and waits 200 ms (module sleep command).
2. `lpwr_exti_init_hook()` — ordered drives **both halves'** columns high, so a
   keypress on *either* half pulls a row low (the cross-half wake).
3. `lpwr_stop_hook_post()` — the board's whole body is wrapped in
   `if (lower_sleep)`, so on the idle path it is a **no-op**.

**The actual fault — an unhandled wake code.** `lpwr_stop_cb()` interprets the
wake afterwards:

```c
switch (lpwr_get_sleep_wakeupcd()) {
    case LPWR_WAKEUP_UART: lpwr_set_state(LPWR_STOP);   /* straight back to sleep */
    default:               lpwr_set_state(LPWR_WAKEUP);
}
```

Because the board copy deliberately does not arm `UART_RX_PIN` (the module's own
traffic would defeat the 30-minute sleep), but `palcallback()` still maps the
UART pad to `LPWR_WAKEUP_UART`, a spurious/aliased edge that resolves to
`LPWR_WAKEUP_UART` sends the state machine back to `LPWR_STOP` **without ever
running `lpwr_wakeup_cb()`** — no rail re-raise, no `matrix_init_pins`, no
`last_matrix_activity_trigger`. With `lower_sleep == false` the board's
`lpwr_stop_hook_post()` does nothing to compensate. The half re-enters STOP and
never recovers: dark, no typing — exactly the observed symptom.

**Consequence for the fix.** The one-line refusal (never take the unordered idle
sleep) is correct as a *mitigation*, and the contract shape (a board-reported
predicate enforced at the single point of commitment) is right. But the predicate
must be named for what it truly reports — this board's *sleep policy* — and the
comment must stop claiming "no wake source". The deeper structural fix is that a
wake code must never be *discarded*: every exit from STOP should pass through the
wake path once. That is the upstream-shaped statement of the invariant, and it
belongs with the contract, not hidden in a board comment.

## FINDING — the WB32 EXTI aliases pads, and a wake code must be validated as a set

The "unhandled wake code" defect has a hardware root that makes it a *guaranteed*
fault on this board, not a rare race.

**The WB32 EXTI is pad-numbered and port-discarding.** `PAL_PAD(line) = line & 0x0F`
(`hal_pal_lld.h`) — the port is dropped. `pal_lld_get_line_event(line)` indexes
`_pal_events[PAL_PAD(line)]`, and there are only 16 channels. `wb32_isr.c` serves
channels 5–9 from one handler and 10–15 from another; `_pal_lld_enablepadevent`
asserts a pad is not already in use. **One EXTI channel per *pad number*, across
all ports.**

Concretely on this board: **pad 11 is shared by matrix column `B11`
(`MATRIX_COL_PINS`) and the module UART RX `C11` (`UART_RX_PIN`, `UART_DRIVER
SD3`)**. `palcallback()` matches on `PAL_PAD(UART_RX_PIN) == 11` with no port
comparison, so a **matrix column-11 line event is classified `LPWR_WAKEUP_UART`**.
(Similarly `A12`/`B12` share pad 12, aliasing USB wake with a matrix column.) The
board deliberately does not arm UART wake — but the classifier does not know that.

**Why a set, not a scalar.** The old `switch (lpwr_get_sleep_wakeupcd())` reads the
*last* code written. A phantom UART edge and a genuine row edge in the same wake
window would leave one of them unserved; the fix must test the accumulated set
against a board-supplied mask:

> `if (lpwr_get_sleep_wakeupcd() & lpwr_wakeup_armed_mask())` → wake, else re-enter
> STOP — where the board's mask is `MATRIX | CABLE | SWITCH | USB`, never UART.

That is why the wake codes became bit flags, the storage widened to `uint32_t`
(the mask is 32-bit; an 8-bit store would truncate a future flag), and
`lpwr_set_sleep_wakeupcd()` became an OR-accumulate. Verified by lldb disassembly:
board `lpwr_wakeup_armed_mask` is `movs r0, #0x4d` (`MATRIX|CABLE|USB|SWITCH`),
the setter is a 32-bit `ldr/orrs/str`, and `lpwr_stop_cb` is a single `tst` with
`ite`/`moveq`/`movne` — no jump table over a multi-bit value.

## FINDING — the USB path has a second, host-initiated sleep route

The static USB-path audit proved the `lpwr_*` wireless sleep machine is
**structurally unreachable** on USB: one route to `mcu_stop_mode()` (behind
`lpwr_stop_cb`), a double-gated timeout (`lpwr_is_allow_timeout_hook()`'s
`DEVS_USB` refusal **and** the generic `DEVS_USB && USB_DRIVER.state == USB_ACTIVE`
check, both consulted before `manual_timeout`), USB stopped only on a deliberate
transport change, and a raw-HID `0xA4` responder with no `lpwr_*` references.

But USB is **not** sleep-free. A separate mechanism, `usb_remote_wakeup()`
(`keyboards/linker/wireless/transport.c:98-135`), runs on every `wireless_task()`
while on USB and — when the *host* suspends the bus — calls `suspend_power_down()`
after `USB_POWER_DOWN_DELAY` (3000 ms), once per suspension (`#else` branch;
`USB_REMOTE_USE_QMK` is undefined). On chibios `suspend_power_down()` is
`suspend_power_down_quantum()` + `wait_ms(17)` — it powers down backlight/LEDs/OLED
and sets the RGB suspend state, but **does not enter MCU STOP** (no
`mcu_stop_mode()`). Its mirror `usb_remote_host()` calls `suspend_wakeup_init()`.

**Context, corrected.** An earlier draft of this note claimed the wake handler runs
in **ISR context**. That is wrong. The USB ISR `usb_event_cb()`
(`tmk_core/protocol/chibios/usb_main.c`) only *enqueues* `USB_EVENT_WAKEUP`; the
dequeue and dispatch to `usb_event_wakeup_handler()` (`→ suspend_wakeup_init()`)
happen in `usb_event_queue_task()`, called from `protocol_pre_task()`
(`chibios.c:175`) — **main-loop context**. For this board `NO_USB_STARTUP_CHECK`
is defined (both `wireless.mk` files), so the *upstream* `protocol_pre_task()`
suspended loop that would call `update_matrix_state_after_wakeup()` is compiled
out; USB-suspend handling is entirely the vendor `usb_remote_wakeup()`/
`usb_remote_host()` path.

**Consequence.** Neither USB-suspend side can reach the WB32 STOP mode, so USB is
**not** exposed to the unrecoverable-STOP class of fault that bit Bluetooth. It is
still not sleep-free (LEDs/backlight power down while the host suspends the bus).
The tempting `update_matrix_state_after_wakeup()`-in-`suspend_wakeup_init()` fix
was written and then **reverted** — correctly, though for a different reason than
first stated: that callback is not an ISR, but it is not the architectural home
for matrix work either (upstream places the call in main-loop task context guarded
by `USB_SUSPEND_WAKEUP_DELAY > 0`, and on this board that site is compiled out).
A real leftover oddity, now fixed: `usb_remote_host()` called
`suspend_wakeup_init()` **unconditionally on every action while the bus is
suspended** — not gated on a wake transition — so the full state-clear +
backlight-init + rail re-raise + slave RPC `0xCC` would re-run per action. It was
removed: the genuine wake transition is already handled exactly once by the QMK
USB core (`USB_EVENT_WAKEUP` → `usb_event_wakeup_handler()` → `suspend_wakeup_init()`,
main loop), so `usb_remote_host()` now only requests the remote wakeup
(`usbWakeupHost()`). Idempotent before, correct now.

**Behavioural soak (USB).** With the flashed build on USB, a 90 s soak sampled the
raw-HID `0xA4` battery query on interface 1 every 2 s: **44/44 replies, zero
failures**, and the kernel log showed **no change** in the `342D:E4C6`
enumeration-event count (114 before and after) and **no `-71`/`-62`/disconnect/
reset** after the 19:17:49 clean enumeration. The USB contract (stays enumerated,
raw HID responsive, no EPROTO storm) held throughout. Runner:
`/tmp/opencode/usb_soak.py`.

**Reflash verification (2026-10-09).** Both halves reflashed with the current
build (battery responder + BT driver + board-local deep-sleep fix), then the
keyboard reconnected on USB in USB mode. Enumerated cleanly as `342d:e4c6`
(`LEO` / `EPOMAKER Split65`, `bcdDevice 0.30`) with **one** raw-HID collection at
interface 1 (`0xFF60`/`0x61`, `/dev/hidraw4`). A single live `0xA4` piggyback
query returned `A4 64 00 00 01 01 01 …`: level byte1 `0x64` = **100%**, charge
byte4 `0x01` (charging), transport byte5 `0x01` (USB), model byte6 `0x01`
(Split65) — indexes per `wls.h` (cmd 0, level 1, charge 4, transport 5, model
6). No EPROTO/`-71` in the kernel
log; all HID collections (keyboard, raw, mouse/system/consumer) attached. This
confirms the responder and manufacturer string on the freshly flashed hardware;
the 100% is still the USB-mode constant, so it does not yet distinguish a real
reading (defect 1).

**The BT-profile keycode persists the transport, and the mode switch cannot undo
it (2026-10-09).** After using `KC_BT1` (Fn on the **right** spacebar, then `Q`)
to try Bluetooth, the keyboard stopped typing on USB on **both** halves — while
USB stayed enumerated (`342d:e4c6`) and the `0xA4` responder still answered. The
cause is persistence, not a crash: `KC_BT1` → `connection_set_host(BLUETOOTH)`
writes EEPROM, and `connection_host_changed_kb()` maps it through
`wireless_devs_change()`, which persists `confinfo.devs = DEVS_BT1`. On the next
boot the housekeeping path restores that persisted index
(`wireless_devs_change(!confinfo.devs, confinfo.devs, false)`), so reports are
routed to the dead BT link while the USB composite remains up. The mode switch is
**not** an override at a steady position: the boot-time `hs_mode_scan(false, …)`
acts only when `hs_modeio_detection()` sees the switch *change* after boot. There
is no USB-select keycode. **Recovery that works:** `EE_CLR` (hold 3 s) →
`hs_reset_settings()` → `eeconfig_init()` (EEPROM wipe) →
`keyboard_post_init_kb()` re-defaults `confinfo` and restores USB. **Bootmagic is
not a recovery route** — `bootmagic_should_reset()` does `eeconfig_disable()` and
`bootloader_jump()`, i.e. it enters DFU rather than resuming. Full defect writeup
in `TODO.md` defect 4. Not a regression from our change set (the vendor stack has
the same persistence); it is a usability/authority defect in the mode model.

## FINDING — the sleep decisions are a functional core, and the shell that touches the MCU is not

The low-power state machine mixes two kinds of code: decisions that depend only
on their arguments, and code that touches the MCU (registers, ChibiOS, the
`PRE_LP()`/`POST_LP()` blobs). Both faults chased in this project — the
un-ordered stop and the phantom wake code — lived entirely in the first kind.
That part is now a dependency-free core so it can be tested without hardware:

- `keyboards/linker/wireless/lowpower_logic.{h,c}` (no ChibiOS, no registers, no
  globals) holds `lpwr_stop_is_allowed_decide(is_master, lower_sleep)` and
  `lpwr_wakeup_is_real(wake_set, armed_mask)`.
- `lowpower.c` and the board `wls.c` are now thin adapters: they fetch the facts
  (`is_keyboard_master()`, `lower_sleep`, the accumulated wake set, the board's
  armed mask) and delegate. `lpwr_stop_cb()` no longer contains the decision; it
  calls `lpwr_wakeup_is_real()` and maps the result to the next state.

**Why this shape and not a parallel mock of the chassis.** The upstream test
convention (battery, encoder, debounce) is to compile the *real* module against
mocked primitives — but no upstream test mocks ChibiOS (`chSysLock`,
`mcu_stop_mode`, `__WFI`), and we should not invent that infrastructure. The
existing fence is therefore respected by extracting only the pure decisions,
not by building a ChibiOS mock to test `lowpower.c` itself.

**Test placement.** Modern upstream tests live in `tests/<name>/` (auto-discovered
by `find -name test.mk`, built via `include $(n)/test.mk`; the test's own `.cpp`
files are globbed automatically and must **not** be re-listed in `SRC`). The
per-feature `quantum/*/tests/testlist.mk` path expects its entries relative to
`tests/` and is not for a keyboard-dir module. `tests/lowpower_logic/` follows the
modern layout and pins the two hardware facts as data: the wake codes are bit
flags, and the armed mask excludes UART (the phantom). Eight tests, all passing.

**Honest limitation.** The core cannot enforce the storage width of
`lpwr_wakeupcd_t` at the shell boundary; the core takes `uint32_t` throughout, so
it is immune, but the boundary stays a shell fact (a `_Static_assert` is the
mitigation). This pattern fixes *testability*, not *hardware truth* — the aliasing
is reproduced only because the test is fed the board's real pad/armed facts.

## FINDING — the wireless stack is a documented third-party protocol, not an Epomaker invention

A search for the board's schematics (English, Japanese, Chinese) found **no
Split65 netlist** — but it found something more useful: **our wireless subsystem
is a standard WCH module stack with a public specification, and our firmware
traces to public source.** This converts several "assumption, not measurement"
items into spec-backed facts.

**The module is a WCH CH582F, and the UART protocol is documented publicly.**
`emolitor/WestberryTech-WB32` (a ~year of independent WB32 RE) carries
`docs/wireless/ch582f-protocol.md`: a complete reference for the CH582F, "a BLE
5.0 / 2.4 GHz wireless SoC from Nanjing Qinheng Microelectronics." It states the
protocol is **not vendor-specific** — used by "GMMK, Akko, MonsGeek, Neo,
Shortcut Studio, and others", with the module firmware a **WCH binary blob** (the
protocol doc's words; see the correction below — the stack is actually a
symbolized library) and
only the host side implemented per board. Our `keyboards/linker/wireless/module.h`
matches it **byte for byte** (`0xA1/0xA2/0xA3/0xA4/0xA8`, `0xA6`+`0x11/0x30/
0x31..0x35/0x51/0x52/0x53`, `0x5A/0x5B/0x5C`, the additive checksum, the
`0x61 0x0D 0x0A` ACK, `WLS_INQUIRY_BAT_TIME == 3000`).

**What this settles without hardware:**
- **The per-transport state question.** The doc defines `MD_STATE_*` and states
  HID reports are only transmitted in `MD_STATE_CONNECTED`, else a reconnection
  attempt fires. This is module-firmware behavior, documented by the ecosystem —
  it backs the BT-profile link-up gate in `wls/wls_bluetooth.c` (see "Bluetooth is
  a dongle-free path"), which previously rested on inference.
- **Battery semantics.** Poll `0xA6 0x53` → `0x5C <percent>`, plus optional
  unsolicited `0x5B` threshold sub-codes (`0x21` very-low / `0x22` first-read /
  `0x23` normal). Relevant to defect 1: a stale placeholder could partially be a
  threshold-notification artifact, though the `0x5C` value remains authoritative.
  Our stack **deliberately ignores** the `0x5B` threshold sub-codes:
  `module.c` `md_receive_msg_task()` handles only the `0x5B` pairing/connected/
  disconnected/reject states and drops everything else, and `module.h` annotates
  `0x21/0x22/0x23` "(unused)". That is a defensible choice — the `0x5C` percent is
  the authoritative value and the thresholds are advisory — but it means a
  low-battery or first-read notification the module sends is invisible to us. The
  RE route (below) can confirm from `gap.o`/`ll_connect.o` which internal event
  drives each sub-code before deciding whether to honour them.
- **Dongle descriptor programming.** The doc explains the *host MCU* sets the
  dongle's manufacturer/product strings and VID/PID (`0xAB`/`0xAC`/`0xAD`) during
  pairing — a concrete failure mode for our dongle's enumeration, and a reason its
  USB identity is not fixed.
- **The receiver has no debug interface** ("dev only via a CH582EVT eval board"),
  so the dongle cannot be introspected from the keyboard side — mechanistically
  consistent with our dongle's failure to enumerate, though not a diagnosis.

**The lineage is public and shallow.** Each of these carries the same
`keyboards/*/wireless/` file set (`lowpower`, `lpwr_wb32`, `md_raw`, `module`,
`smsg`, `transport`, `wireless`):

```
isuua → emolitor/qmk_firmware#wireless-2.0 (Shortcut Bridge75, WB32FQ95+CH582F)
      → WestberryTech/qmk_westberry#tri-mode (vendor fork)
      → hangshengkeji/qmk_firmware#tri-mode → Epomaker/Split65
```

`emolitor`'s `module.h` is essentially identical to ours, and that port ships a
**`battery_custom.c`** — an independent precedent for our `BATTERY_DRIVER =
custom` shape — plus a `retarget_suspend.c` we do not carry.

**Consequence.** (a) The stack is not an Epomaker black box; it is a documented,
shared OEM stack, so the U1 RFC can cite the protocol reference rather than
reverse-engineering it. (b) A `test/` harness that stubs `module.c`/`smsg.c` can be
written against a **specification**, not a guess — the highest-value artifact that
needs no hardware. (c) The board-specific netlist and the radio/dongle facts
remain flash-gated; the search did not find them and they are not inferable from
the protocol doc.

**Why the schematic is unfindable (a white-label board).** A deliberate sweep of
every plausible leak channel found nothing: the OEM's GitHub (33 repos, all
firmware), its firmware/software/VIA/manual download pages, `hub.epomaker.com`,
the ODM's `hangshengkeji` tree, the `WestberryTech` vendor fork, Chinese
open-hardware `oshwhub.com` (**0** "split65" projects), `gitee.com`, and forums
(the only "Split65" elsewhere is an unrelated 2.4 G-only kit). The board is a
**white-label ODMed product**: the WCH CH582 module reference design plus a vendor
QMK tree, wired by the ODM and never published. The "accidental public web server"
hypothesis is not supported by any reachable channel; treat the netlist as
unavailable and derive board facts from the firmware, not from a schematic.

**Related schematics DO exist — the question is which kind of "schematic".** A
follow-up sweep for *any* same-family schematic (not necessarily the Split65)
turned up three usable artifacts, none of them our netlist:

- **A same-family board pin map — `ozboar/zoom65v3-re`.** A Meletrix Zoom65 v3
  (WB32FQ95, `HFD22001A` rebadge) reverse-engineered to a full **pin map**:
  matrix rows/cols, the 14-pin ribbon, and the module-UART / cable-detect /
  battery / LED / power-enable pins. It is the closest published analogue to a
  Split65 netlist and the reason the "sibling pinout" section in `HARDWARE.md`
  exists. **Critical caveat:** its module UART is `A9`/`A10`, whereas ours is
  `C10`/`C11` (UART3) with the *split link* on `A9`/`A10` — so the sibling's
  literal pin assignment must not be copied; copying it re-creates the module/split
  UART collision our board-local comments already warn about.
- **The module's own chip datasheet — WCH CH582F (QFN28).** Public; gives the
  module-side UARTs (`UART1` = `PA8`/`PA9`, `UART3` = `PA4`/`PA5`, default console
  `UART1`). This explains *why* two boards can speak the same protocol over
  different MCU pins: the module exposes several UARTs and the board picks one.
- **Third-party CH582F *keyboard* schematics — `oshwhub.com`.** Open-hardware
  projects with published schematics for a wired→BT converter module ("HH90"),
  CH582M tri-mode pads / a 61-key board, and a CH582F **2.4 GHz receiver**. These
  are different boards but document the **same module architecture** (keyboard MCU
  + CH582F + TP4056 charge / boost LDO / battery + PCB antenna), which is directly
  reusable as a *reference topology* even though the matrix and pins differ.
  `oshwhub.com` blocks direct fetch (HTTP 418); descriptions/attachments are
  reachable via search.

**What stays unavailable:** the WCH vendor `CH583EVT.ZIP` / `SCHPCB.ZIP` (official
eval-board schematic/PCB) require "contact sales", and the module's shipped
factory product image is not published. **But the BLE stack is not the opaque blob
it was once recorded as:** `openwch/ch583` `EVT/EXAM/BLE/LIB/LIBCH58xBLE.a` is a
genuine `ar` archive of 67 named object files (`ll_*.o`, `gap*.o`, `hci*.o`,
`sm*.o`, `tmos*.o`, …), unstripped, exporting 10,410 named functions and
disassemblable with `llvm-objdump`; the app/profile layer is full C source. The
`CH58xBLE_ROM*.hex` BASELIB is **also public** and is **not mask ROM** — the
CH582/583 has no BLE stack in silicon; "ROM" is the stack compiled separately and
flashed to a fixed Flash region, reached through a jump table
(`BLE_LIB_JT(n)` at `LIB_FLASH_BASE_ADDRESSS+0x34`, `_ROM`/`_ROMx` differing only
in load address). It is a first-class WCH download (and `WCHBleLib_MultiOS.ZIP`),
mirrored in the same repo. Both the archive and the linked 180 KB image are
disassemblable. This turns "the module is a black box" into "the module's
*behavior* is readable", which is discussed under "Why this matters" in
`docs/HARDWARE.md`. Net: the **Split65 netlist is still flash-gated**, but the
*architecture it is an instance of* is now public from three independent
directions.

## FINDING — the board is an ODM product; the ODM candidate is MATHEW TECHNOLOGY LIMITED, the manufacturer named by certification is Shenzhen Changyun Technology Co., Ltd., and the radio filings are public

The provenance chain resolves one level above Epomaker. `Epomaker/Split65` is a
direct copy of `hangshengkeji/qmk_firmware#tri-mode`, which is the `WestberryTech`
vendor fork, which is `emolitor`'s Shortcut Bridge75 port. The **ODM itself** is
reachable and has published its raw firmware source archives:

- **`mathewkb.com` = "MATHEW TECHNOLOGY LIMITED"** (`wp-json` site name), a Shenzhen
  keyboard OEM/ODM. Its `/firmware/` page and `wp-content/uploads/` tree carry
  **dozens of unencrypted `.7z` firmware source archives** (not just `.bin`
  blobs): `MK*`, `MT*`, `NK*`, `HW*`, `YG*`, Honor, Aula, Langtu, and the **ZUOYA
  GMK** series. WordPress `wp/v2/media?mime_type=application/x-7z-compressed`
  enumerates the recent set; the older set is linked from the `/firmware/`
  portfolio (`us_portfolio` post type, no REST base).
- **`ZUOYA-GMK70.7z`** (`uploads/2024/11/`) is the same source *shape* as our
  board: `config.h`, `keyboard.json`, `post_rules.mk`, `rgb_record/`, `wls/`,
  `keymaps/`, `mcuconf.h`, `halconf.h`, `*.c` — a QMK `keyboards/<oem>/<board>/`
  tree with the vendor wireless stack, archived with source timestamps
  (`2024-12-19`).
- **ZUOYA is the ODM's own brand.** GMK70's `keyboard.json` gives
  `manufacturer: "LEO"` and `"pid": "0xE491"`, and **VID `0x342D` — the same VID as
  our Split65** (`342d:e4c6`, manufacturer `LEO`). The GMK70 VIA JSON
  (`customKeycodes` = `BT DEV1..BT DEV5 / 2.4G / USB`, matrix 10×9, `layouts` = 5)
  is the same vendor JSON generator as our Split65 VIA JSON (`0x342d:0xe4c6`,
  matrix 12×9, identical custom-keycode set). `mathewkb.com` even names its
  `qmk-via-json` and `oem-odm` pages.
- **The GMK70 board source is upstream's Split65 source with board-local edits.**
  `wls/wls.c` (OEM) differs from `upstream/tri-mode`'s
  `keyboards/epomaker/epomaker_split65/wls/wls.c` by exactly the split-half /
  master-gating lines we ourselves later added (`col_pins_right`,
  `is_keyboard_master()` gates) — i.e. the OEM archive is an *earlier snapshot of
  the very file* we carry. `rgb_record/rgb_record.c` differs by 3 commented
  lines; `rgb_record.mk` is byte-identical; `wls.h` differs only in whether
  `HS_BT_DEF_PIN`/`HS_2G4_DEF_PIN` are commented out.

**What the ODM library does *not* contain (negative result).** A full sweep of
`mathewkb.com`'s published set — 73 download archives spanning `MK*` (61/66/67/68/
75/80/84/86/87/96/100), `MT*` (66/87/97), `NK*` (68T/75T/98T), `HW*` (61/68/87/108),
`YG*` (108/98), Honor (84/100), Aula, Langtu, CIDOO, and **ZUOYA GMK (61/70/81/87/
104)** — turns up **no 65% split board and no Split65**. The GMK family is a
*67-key/70-key/75-key/…* series, all apparently single-piece or standard splits,
never a 65% split. So the Split65 is **not** published by the OEM under any name;
it is a board the ODM built for Epomaker and left unpublished. The Split65 remains
the only source of its own pin truth; GMK70 is a same-platform sibling, not a
hardware-equivalent donor.

**Confidence: circumstantial, and it has a gap that has *not* been closed.** The
chain `emolitor → WestberryTech → hangshengkeji → Epomaker/Split65` is an
**explicit GitHub fork chain** (provenance by `git` parentage). Every link from
`emolitor` onward is *declared vendor source*, not a rebadge of an unknown board.
Getting from there to "MATHEW built *this* board" rests on **three inferences,
none of which is a direct OEM→Split65 link**:

1. `mathewkb.com` is titled "MATHEW TECHNOLOGY LIMITED" and self-labels its pages
   `oem-odm` — this identifies the *website's* operator, not a contract with
   Epomaker. Nothing on the site names Epomaker, the Split65, or a 65% split.
2. The **ZUOYA GMK70 archive is a near-identical *earlier snapshot* of the same
   vendor file we carry** (`wls/wls.c` differs by exactly the split-half lines we
   later added; `rgb_record.mk` byte-identical; same VID `0x342D`, same `LEO`
   persona, same VIA-JSON generator, same Magic-keycode set). This proves *the
   same hand wrote both trees* — a shared ancestor — and given that `mathewkb.com`
   distributes it, MATHEW is the strongest candidate for that hand. It does **not**
   prove MATHEW contracted for the Split65 specifically.
3. The **VID `0x342D` + manufacturer `"LEO"`** is a *platform* identity shared
   across the whole family (`MK*`, `MT*`, …), not a per-board OEM stamp.

The gap: **no archive, page, or string ties `mathewkb.com` to Epomaker or to the
Split65.** MATHEW might be the ODM; it might equally be a distributor/reseller that
merely *rebrands* a stack it also received from the same further-upstream source
that fed `emolitor`. The negative result above (no 65% split in the library)
is consistent with either story. The **certification filings name a different
entity — `Shenzhen Changyun Technology Co., Ltd.` — as the manufacturer/applicant**
(see "Corroboration" below), which is a *second* candidate and shows the MATHEW
inference is not the whole story.

**What would close it (all flash- or contact-gated):** the dongle's USB
descriptors, the module firmware's ODM string, the PCB silkscreen, a
`strings`/`binwalk` sweep of the vendor `.bin`, or a direct reply from
`mathewkb.com`. Until then the correct statement is: **the board is a Shenzhen
ODM product; `Shenzhen Changyun Technology Co., Ltd.` is named as manufacturer by
the radio certifications, and MATHEW is a strongly-indicated candidate via a
shared-ancestor source snapshot — but the exact OEM→Split65 contract is not
proven.**

**Corroboration from the certification filings (new evidence).** Two filing
bodies name the manufacturer directly:

- **FCC ID `2A5D2-RT100-010`** (grantee `2A5D2` = **SHENZHEN CHANGYUN TECH CO.,
  LTD**), granted `2024-12-13`, test report `SSP24100235-1E`. The Split65 is
  certified **by family declaration** under the RT100 main model: the *Model
  Difference Statement* lists `... Hack 59, Alice 66, **Split 65**` as "the same
  circuit and electronic construction." `fccid.io/2A5D2-RT100-010` publishes a
  **teardown annex** (`Internal-Photos-7897160.pdf`) showing the **wireless
  daughter module with a PCB antenna over the main matrix PCB** — i.e. the module
  architecture we inferred — plus the battery cell. The schematic is withheld
  (`Long-Term Confidentiality: Yes`).
- **EU CE annex** (retail packaging / `manuals.plus`) names `Manufacturer:
  **Shenzhen Changyun Technology Co., Ltd.**, Seventh Floor, Kai Daer Building,
  No.168 Tongsha Road, Xili Street, Nanshan District, Shenzhen` — **the same
  entity and address cluster as the FCC grantee**. So Epomaker's supplier is
  **Changyun**, a Shenzhen factory that also acts as the certification applicant.

This **changes the OEM picture**: it corroborates that a Shenzhen ODM manufactures
the board and files the radio certifications, and it names that ODM candidate
(`Changyun`) independently of the `mathewkb.com`/MATHEW inference. It does **not**
merge the two — Changyun and MATHEW may be the same group, related, or separate
tiers — but it is a second, government-facing identity for "who built this radio."

**Consequence.** (a) There is a *provably equivalent, source-available* sibling
board: ZUOYA GMK70 shares our VID, ODM, vendor-stack source, VIA-JSON generator,
and Magic-keycode set, and its source is free to read. (b) The "epomaker" name is
a rebadge of the ODM's own ZUOYA/GMK platform; the Split65 (65%) is one
keyswitch-count variant in a family (`GMK61/70/81/87/104`, `MK*`, `MT*`). (c) The
OEM half of "upstreaming" is not a black box: the OEM publishes exactly this QMK
vendor-tree shape, which is what the pinned `split65-overlay` branch mirrors. (d)
The netlist is still unpublished — the archives hold *firmware source*, not
schematics or PCB files.

## FINDING — the transport WAS a tiny machine whose transition matrix named the defect-4 bug

**Resolved 2026-10-09.** Kept as the audit record. The `transport`/`driver`/`T`/`H`
columns below no longer exist: 14d deleted `set_transport()`, `host_set_driver()`,
`get_transport()` and the `transport_t` enum, leaving `host_get_active_driver()` as
the sole chooser. `wls_devs` and `confinfo.devs` remain (the vendor device index the
CH582F protocol speaks), but neither is a transport authority. See the "three
partial state machines" finding below for the resolution mapping.

Defect 4 ("a BT keycode hijacks the transport and the switch cannot undo it") was
not a mystery once the state is written down. This section is the **transition
matrix** for the transport subsystem as it stood *before* 14d: every state × event
cell evaluated on purpose, so a missed cell is visible rather than latent. It is
deliberately a matrix, not a diagram — a matrix forces each cell to be filled,
which is how the illegal corner was found.

### The state

The runtime transport state is the product of three small variables. There is no
hidden state; every write site is listed.

| Variable | Domain | Written by | Persisted? |
| --- | --- | --- | --- |
| `transport` (`transport.c`) | `USB \| WLS` | `set_transport()`, only | no |
| `driver` (`host.c`) | `&chibios_driver \| &wireless_driver \| NULL` | `host_set_driver()` (called from `set_transport`) | no |
| `active_host` (`host.c`) | `USB \| BLUETOOTH \| 2P4GHZ \| NONE` | `host_task()`, from `connection_get_host()` | no |
| `wls_devs` (`wireless.c`) | `DEVS_USB \| BT1..5 \| 2G4` | `wireless_devs_change()` only | no |
| `confinfo.devs` (`epomaker_split65.c`) | same enum | `wireless_devs_change_kb()` only | **yes (EEPROM)** |
| `config.desired_host` (`connection.c`) | `AUTO \| USB \| BLUETOOTH \| 2P4GHZ \| NONE` | `connection_set_host*()` | **yes (EEPROM)** |
| `md_info.state` (`module.c`) | `NONE \| PAIRING \| CONNECTED \| DISCONNECTED \| REJECT` | module UART RX (`md_receive_msg_task`) + `wireless_devs_change` force | no |

Two facts make the machine subtle:

1. **Two independent selectors pick the sender.** `host_get_active_driver()`
   returns `&bt_driver` iff `active_host == BLUETOOTH`, else the `driver` pointer.
   So the **same** `wls_devs == DEVS_BT1` physical link can be driven either by
   the board's `wls_bluetooth.c` (`bt_driver`) **or** by the vendor
   `wireless_driver` (`driver`), depending on `desired_host`, not on `wls_devs`.
   There is no invariant tying the two.
2. **The physical switch is an input to a *comparison*, not a selector.** At boot
   the board restores `confinfo.devs`, and the switch only matters when it has
   *changed* since the last scan (`sw_mode`). The switch LEVEL is never read to
   *set* the mode at boot.

### The transition matrix

Rows are states; columns are events; each cell is `[next wls_devs / side-effects]`.
`devs` = the device index; `T` = `set_transport`; `H` = `host_set_driver`;
`sleep` = module sleep command.

| State (`wls_devs`, `desired_host`) | boot / post-init | switch→USB | switch→BT | switch→2.4G | `KC_BT1` (Fn+RSPC+2) | `KC_2G4` | module `CONNECTED` | module `DISCONNECTED`/\`REJECT` | `EE_CLR` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **(USB, USB)** | stays USB; T(USB); H(chibios) | — (already) | devs→BT1; T(WLS) if conn; H(wireless) | devs→2G4; T(WLS) if conn | persist `desired_host=BT`; devs→BT1 | devs→2G4 | n/a | n/a | reset → (USB, AUTO) |
| **(BTn, BLUETOOTH)** | **restores BTn** (defect); `active_host=BLUETOOTH`→H(bt_driver) **and** T(WLS)→H(wireless) | devs→USB; T(USB); H(chibios); clears md state | devs→BT(n) | devs→2G4 | devs→BT1 | devs→2G4 | md=CONNECTED; T(WLS); H(wireless) | forces md=DISCONNECTED | reset → (USB, AUTO) |
| **(2G4, 2P4GHZ)** | restores 2G4 | devs→USB; T(USB) | devs→BT1; T(WLS) if conn | — (already) | persist BT; devs→BT1 | devs→2G4 | md=CONNECTED; T(WLS) | forces md=DISCONNECTED | reset → (USB, AUTO) |

**Boot column is the bug.** Every wireless row *restores itself* at boot from
`confinfo.devs`, regardless of the switch. USB is not special-cased. So if the
last session ended on BT1, the board boots on BT1 even with the switch on USB —
and because USB was still enumerated, the failure is silent ("enumerated but no
keys"), exactly as observed.

### The illegal combinations (invariants)

These are states the machine can reach that *should* be unreachable. An invariant
checker (`assert_invariants()`, run in tests and optional debug) would flag each:

- **I1 — "USB present but not selected."** `usb_connected_state() && wls_devs != DEVS_USB`.
  The switch says a physical cable is authoritative to the user; the state says
  otherwise. This is the defect-4 landing state.
- **I2 — "two senders for one link."** On any BT index, both `bt_driver`
  (`active_host==BLUETOOTH`) and `wireless_driver` (the `driver` pointer, set by
  `set_transport(WLS)`) are live and target the same UART. Nothing asserts they
  agree. Only one is consulted per report (`host_get_active_driver()`), but a
  `host_set_driver()` from either path silently re-points the other.
- **I3 — "edge-without-level."** `sw_mode` can only be true if the switch moved
  *after* boot; therefore the boot-time scan cannot correct a state that was
  already wrong at power-on. Any state that requires the switch to *have moved* to
  be fixed is fragile.
- **I4 — "persisted authority with no non-flash escape."** If the persisted state
  is wrong and no keycode selects the target, the only reset is `EE_CLR` (EEPROM
  wipe). That is a recovery, not a control.

### Bug classes this instance belongs to

In the taxonomy used for this audit, defect 4 is **authority inversion** (software
persistence overrides a physical switch) *compounded with* **edge-vs-level boot
desync** (the override is only corrected on a switch edge, which never occurs at
boot). Both are structural, not incidental: any state that (a) persists, (b) is
restored at boot, and (c) is *also* expressed by a physical control, has this
shape. The general rule the machine violates: **a physical control is absolute
authority for its own domain; persistence may only model sub-domains the control
cannot express** (here: which of `BT1..5`, once the switch merely says "BT").

### What the matrix buys

- The fix target is named: make the boot column read the switch LEVEL, not
  `confinfo.devs`. **DONE** — see `TODO.md` defect 4 and the pre-flight rule; the
  fix sets both selectors (vendor index + `config.desired_host`) from the level.
- The test target is named: a table-driven vector asserts **I1 is never entered**
  for every boot state and switch position, with no hardware. **DONE** —
  `tests/transport_logic/` holds exactly that matrix as a pure core
  (`wls/transport_logic.{c,h}`, 6 tests, `make test:transport_logic`).
- The residual unknown is bounded: I2 (two senders) was a separate, real ambiguity
  that the transition matrix exposed but did not resolve. **DONE (14d)** — deleting
  the vendor `set_transport()`/`host_set_driver()` swap leaves
  `host_get_active_driver()` as the single chooser, so I2 is no longer reachable.
  The fix still writes both selectors (vendor index + `config.desired_host`) from
  the level, which the boot-order rule depends on.

## FINDING — the transport WAS three partial state machines, and we collapsed them (the vendor one as scaffolding to delete)

**Resolved 2026-10-09.** This finding is kept as the record of the audit and the
reasoning; the code has since moved past the state it describes. The three partial
state machines are gone: the vendor transport selector (`set_transport()` /
`host_set_driver()` / the `transport_t` enum / `get_transport()`) is deleted, and
upstream `host_get_active_driver()` is the single sink chooser. See "The
resolution" at the end of this finding for the mapping of each hole to its commit.

A design audit prompted by "is any of this actually well designed, or are we
guessing?" The honest answer was **poorly *factored*, not poorly understood**.
There was no single transport state machine; there were **three partial ones**
sharing **four variables**, written by different subsystems and never
reconciled:

| Variable | Owner | Persisted | Consumed by |
| --- | --- | --- | --- |
| `config.desired_host` | upstream `connection.c` | EEPROM | `host_task()` → picks `bt_driver` vs `driver` |
| `confinfo.devs` | vendor `wireless.c` (our bridge writes it) | EEPROM | `wireless_devs_change()` → vendor UART frame |
| `driver` pointer | vendor `transport.c` `host_set_driver()` | RAM | `host_get_active_driver()` fallback |
| `active_host` | upstream `host.c` = `connection_get_host()` | RAM | the branch that returns `&bt_driver` |

Every symptom we chased lives at a *seam* between these, not in one of them:

- **`KC_BT1` locks out USB** (defect 4) — the ODM bridge writes **both** persisted
  selectors; upstream AUTO is never consulted; the vendor switch-edge check never
  fires. Authority inversion + edge-vs-level desync.
- **Fn+2 blinks but nothing advertises** — the bridge told the module "go BT1"
  (layer 2); whether BLE advertises is layer 0 (module firmware), which *neither*
  subsystem models. **RESOLVED 2026-10-09:** the module *does* advertise correctly
  (see `HARDWARE.md`); the original "nothing advertises" was a search-miss on the
  wrong name and a random address.
- **2.4 GHz unreadable over USB** — upstream `connection.c` **cannot represent
  2.4 GHz at all**; the vendor piggybacks `DEVS_2G4` outside the model.
- **`bluetooth_send_raw_hid` vs `md_send_raw`** — two mechanisms for the same
  bytes (upstream BT-driver contract vs vendor tunnel).

### Provenance (why the three exist)

- **Upstream `quantum/connection/` is new and unfinished.** Authored by Joel
  Challis, PRs #25176 (2025-04-21) and #25199 (2025-05-05) — ~6 months old.
  Critically, **it already names tri-mode**: `CONNECTION_HOST_2P4GHZ` is a real
  enum member (`connection.h:21`). The `#if 0` in `host_candidates[]`
  (`connection.c:33`) and the missing case in `host_get_active_driver()`
  (`host.c:121`) are **gaps upstream left open, not a rejection**. Upstream has
  **no tri-mode/vendor-module BT driver** — only `bluefruit_le` and `rn42`.
- **The vendor stack predates the connection subsystem** and has its own model
  (`wls_devs`, its own `transport`, its own `host_driver_t wireless_driver`,
  `set_transport()` calling `host_set_driver()` directly). It does not know
  `connection.c` exists. ODM-authored, lightly maintained.
- **Our ODM bridge** (`epomaker_split65.c` `connection_host_changed_kb()` +
  `WLS_KEYCODE_EXEC`) is the translation shim, and the weakest link.

### Doctrine — priority of the three code sources

Recorded here because it governs every future change:

**The goal is a firmware that works on this one keyboard.** Prior work — upstream
*or* vendor — is an optional input, judged only by whether it serves that goal.
Where existing code is worse than what we would write, **discard it and write our
own**; quality and clean architecture are ours to define, and are what makes the
result correct here and (secondarily) plausible to upstream.

1. **Upstream QMK is the plate.** Extend its model; do not invent a parallel one.
   Its unfinished tri-mode support (holes below) is the *intended* home for our
   work, and patching it is the most upstreamable path.
2. **Our own well-architected code is the board layer.** The switch-authority
   rule, the pure decision cores (`transport_logic`, `lowpower_logic`), the
   upstream-shaped BT/battery drivers.
3. **The vendor stack is scaffolding to delete where it fights the plate.**
   Keep only what upstream cannot provide (the CH582F UART protocol in
   `module.c`/`smsg.c`, which drives the module). Do **not** add glue around it.
   The vendor "remember last transport" persistence is abandoned wherever a
   physical switch exists — the switch is the authority for its domain, and
   persistence is only for what the switch cannot express (which of BT1–5).
   **The vendor stack is not owed preservation.** Keeping a vendor file is a
   choice made only when it beats a rewrite we would otherwise do; "it already
   exists" is not a reason. `module.c`/`smsg.c` stay because the CH582F UART wire
   is a fixed hardware fact, not because the code is good.

### The five holes after committing to upstream-first

1. **2.4 GHz is unrepresented upstream.** Add a `2p4ghz` driver contract mirroring
   `bluetooth.h` (weak `is_connected`/`send_*`), un-`#if 0` the candidate, add the
   `host_get_active_driver()` case. Same shape as the BT driver work; upstreamable.
2. **`connection.h` cannot express "which BT1–5".** `desired_host` is 3 transports;
   the sub-index has no upstream home — our `confinfo.devs` exists only for it.
   Give the BT driver its own `select_profile(n)` and delete `confinfo.devs`.
3. **Persistence semantics conflict.** `connection_set_host()` persists
   *unconditionally* (`connection.c:76`) — wrong when a physical switch is
   authoritative. Board doctrine: switch-driven changes use
   `connection_set_host_noeeprom()`; only user keycodes persist.
4. **Two sink choosers.** Delete vendor `set_transport()`/`host_set_driver()`;
   leave `host_get_active_driver()` as the single chooser, so
   `bluetooth_send_raw_hid` (upstream contract) is the only raw path.
5. **The module is unmodeled in either system.** Treat the CH582F as a **modeled
   peer**: inputs = UART frames; outputs = {BLE advert, BLE HID, UART reply,
   `md_info.state`}. ~~Whether it advertises is layer-0 and remains a **bounded
   hardware unknown**~~ **RESOLVED 2026-10-09: it advertises a correct BLE HID
   keyboard profile** (`HARDWARE.md`); the earlier uncertainty was a search-miss,
   not a fault.

The defect-4 fix wrote *at* the seam (switch level → both selectors); holes 1–4
were then closed so the seam disappears.

### The resolution (2026-10-09)

Every hole above is now implemented. The mapping, for anyone tracing a symbol that
no longer exists:

| Hole | Resolution |
| --- | --- |
| 1. 2.4 GHz unrepresented | `drivers/wireless/wireless_2p4ghz.{c,h}` (weak contract mirroring `bluetooth.h`), `w2p4_driver` + `CONNECTION_HOST_2P4GHZ` cases in `host.c`, `#if 0`→`#ifdef WIRELESS_2P4GHZ_ENABLE` in `connection.c` `host_candidates[]`, `WIRELESS_2P4GHZ_ENABLE` feature in `builddefs/common_features.mk`. Board adapter: `wls/wls_2p4ghz.c`. |
| 2. Cannot express "which BT1–5" | `bluetooth_select_profile(profile, reset)` / `bluetooth_get_profile()` in `wls/wls_bluetooth.c` — the sub-index is now driver-owned and applied through `wireless_devs_change(current, profile, reset)` (which sets `wls_devs`, drives the LED, and pushes to the module via `md_devs_change`). `confinfo.devs` is no longer a transport *authority* (it survives only as the vendor device index the module protocol itself uses). |
| 3. Persistence semantics | Switch-driven changes call `connection_set_host_noeeprom()` (boot switch read in `keyboard_post_init_kb()` and the 100 ms `wireless_post_task()` pass); only the user keycode path persists, via `connection_set_host()` + `wls_persist_devs()`. |
| 4. Two sink choosers | `set_transport()`/`host_set_driver()`/`get_transport()`/the `transport_t` enum deleted from `keyboards/linker/wireless/transport.c`; `host_get_active_driver()` is the sole chooser. USB connect/disconnect is now the board hook `wls_usb_connect()` called from `connection_host_changed_kb()`; the raw path branches on `usb_connected_state()`. Resolves invariant I2. |
| 5. Module unmodeled | `wls_bluetooth.c` / `wls_2p4ghz.c` are the modeled peers: inputs = the vendor device index, outputs = the `md_send_*` UART sinks and `md_info.state`. **The module advertises a correct BLE HID keyboard profile** (resolved 2026-10-09; `HARDWARE.md`) — the earlier "never advertises" was a search-miss. |

**Still live from this finding:** the boot-order rule. `connection_init()`
(`quantum/keyboard.c:478`) reads EEPROM *before* `keyboard_post_init_kb()`, so the
switch level is seeded into `config.desired_host` in `keyboard_post_init_kb()`
(`_noeeprom`) to guarantee no report precedes the switch read now that the vendor
`driver` pointer no longer masks the ordering.

**Subsequently removed (2026-10-14):** the `md_raw.h` line-pinned
`raw_hid_send`→`replaced_hid_send` remap, which at the time of this review was
"deliberately optional" and left in place, has since been **deleted** — along
with `md_raw.h`, `replaced_hid_send()` itself, and the CI guard that asserted its
line numbers. The send path now rides upstream `raw_hid_send()` →
`host_raw_hid_send()`, the single driver chooser, so nothing board-private
remains and a submodule line-shift can no longer break the tunnel silently.

### Post-collapse design review — claims verified and remediated (2026-10-09)

A review of the 14a–14e change set raised four claims; all four were checked
against the source and three were found valid (one classed HIGH, one narrow
HIGH, one MEDIUM) plus one doc-only fix:

1. **`connection_host_changed_kb()` keyed off the raw host argument — VALID,
   FIXED.** `handle_host_changed()` forwards `config.desired_host`
   (`connection.c:62-64`), which can be `CONNECTION_HOST_AUTO` (the board never
   overrides `CONNECTION_HOST_DEFAULT`, so `AUTO` is the blank-EEPROM default,
   and `host_candidates[0] == AUTO` is reachable via `QK_OUTPUT_NEXT`). Testing
   the raw value tore the USB line down whenever the host was `AUTO`, even when
   `AUTO` resolved to USB. Now tests the resolved host
   (`connection_get_host() == CONNECTION_HOST_USB`), matching
   `host_get_active_driver()`.
2. **Boot seed depended on the hook firing — VALID (narrow), FIXED.**
   `connection_set_host_noeeprom()` early-returns **without** calling
   `handle_host_changed()` when the host is unchanged (`connection.c:70-78`), so
   when EEPROM already equalled `boot_host` the USB line kept its reset default
   (connected) on a non-USB host. The boot seed now drives `wls_usb_connect()`
   directly from `boot_host`, removing the dependence on the early-return path.
   Note the pre-change vendor code deferred the same line change to
   `wireless_post_task()` at +100 ms, so the new code was already **earlier**,
   not a regression.
3. **`replaced_hid_send()` keyed off the USB bus state — VALID, FIXED.** It
   branched on `usb_connected_state()`, which diverges from every other report
   path (all key off `connection_get_host()`) and from its own stated intent.
   Now routes through `host_raw_hid_send()` — the single driver chooser — which
   on USB reaches `chibios_driver.send_raw_hid` (`send_report(USB_ENDPOINT_IN_RAW)`)
   and on Bluetooth/2.4 GHz reaches the module sink via the driver's
   `send_raw_hid`. Behaviourally equivalent on both callers (`kb_battery_push_task`
   already gates on link-up; `raw_hid_receive` only arrives on USB). This also
   removes the `usb_util.h` dependency from `md_raw.c`.
4. **Stale comment in `wls_bluetooth.c` describing the deleted `set_transport()`
   as current — VALID, FIXED** (past tense); same wording corrected in the
   header comment.

**Verified sound (no change):** the four claims did **not** include any fault in
the driver adapters (`wls_bluetooth.c`/`wls_2p4ghz.c`) — the link-up gating,
`select_profile` clamping, NKRO-collapse parity, and per-device poke are all
correct; `usb_connected_state()` is genuinely implemented for ChibiOS
(`tmk_core/protocol/chibios/usb_util.c` → `usbGetDriverStateI == USB_ACTIVE`),
not the always-true weak stub; and the deletion of the vendor swap is complete
(`nm` shows no `set_transport`/`get_transport`/`wireless_driver`).

**Re-verified after remediation:** `:default` 61,488 B (+8), `:nathan` 63,532 B,
`qmk format-c -n` clean, `qmk lint` unchanged (4 pre-existing duplicates),
`host_raw_hid_send` linked, tests `transport_logic` 6/6, `lowpower_logic` 8/8,
`wireless_nkro_parity` 8/8.

## FINDING — the half-backlight fault was four writers for one rail; the fix is one owner

Defect 5 (a half's backlight off while it still types) was not a race to be
papered over with a reasserting write — the Chesterton's-fence question ("why is
the rail written *here*?") exposed that **the writes themselves were the
defect.** `A5`/`A8` (`LED_POWER_EN_PIN`/`LED_POWER_EN2_PIN`) are the backlight
rail ENABLE — the rail is a pure function of the RGB value (`val != 0`). Yet it
had **four** writers that disagreed:

- `keyboard_post_init_kb()` / `lpwr_wakeup_hook()` set it from a **one-shot
  snapshot** of `rgb_matrix_get_val()` at boot/wake;
- `QK_RGB_MATRIX_VALUE_UP`/`_DOWN` drove the pins **directly** (duplicating what
  QMK's `process_rgb_matrix` does to the value), unguarded by master/slave;
- the cross-half `0xBB`/`0xCC` relay forced the slave's rail **off/on**, and both
  senders are gated `if (wireless_get_current_devs() == DEVS_USB) return;` — so
  **on USB neither fires**, leaving a `0xBB` (received off-cable) with no `0xCC`
  to undo it.

With no reassertion anywhere, a single retained-LOW write latched a half dark
permanently (the rail is LED enable, not matrix power, so typing continued over
the split link). Four writers, one pin pair, no arbiter: the fifth-writer
"reassert every tick" patch would have made the rail *work by tick order*, which
is the same anti-pattern with a longer fuse.

**The rearchitecture: one owner, derived, idempotent.** `wls_led_rail_apply()`
(`wls/wls.c`) sets `A5`/`A8` from `rgb_matrix_get_val() != 0`; every former
writer is now a **caller** (post-init, wake, the value keycodes, the `0xCC`
relay, and one reassertion in `housekeeping_task_user` on both halves). The
`0xBB` handler no longer forces the rail off. The rail now **self-derives**, so
no stray write can latch it; the only direct writes left are pin setup and the
explicit suspend power-down (a one-way action, not a latch).

This is the same shape as the transport collapse (item 14): several partial
writers of one piece of state, reconciled into a single authoritative owner —
board-local here because a vendor rail-relay is not a generic model gap, but the
principle (derive, don't scatter) is the general one.

## FINDING — the half-blink was a transient effect welded to a bookkeeping hook

Same disease as the rail, different organ. `wireless_devs_change_kb(old, new,
reset)` did two jobs that have opposite call frequencies:

- **Bookkeeping** — mirror the vendor device index into `confinfo`. Wanted on
  *every* call.
- **A transient indicator flash** — `switch (new_devs)` → `rgb_matrix_wls_indicator_set(index, color, 500, 1)`.
  Wanted only on a *real* transition.

Because the flash lived inside a function the bookkeeping needs unconditionally,
it fired on every call with **no change guard** — including the master's **2 s**
`master_sync_mms_slave` (which exists to carry the battery value, `old == new`),
the `MD_STATE_DISCONNECTED` retry in `hs_rgb_blink_hook`, and the indicator's own
`rgb_matrix_wls_indicator_cb`. Net effect: the **slave half flashed its indicator
every 2 s forever**, on the half the user had not touched.

**Why a guard would have been the wrong fix.** Adding `if (old == new) return;`
to the flash would have treated the symptom: the *function* would still conflate
two responsibilities with different cadences, and the next re-assert caller would
inherit the same latent blink. The honest read is that the change hook should
never have had a visible effect at all.

**The rearchitecture: separate the effect, give it one owner.** `wireless_devs_change_kb`
is now **bookkeeping only**; a new **`wls_indicate_devs(new_devs, reset)`** owns the
flash and is called **only** from genuine transitions (the mode-switch edge via
`sw_mode`, the Fn+2/3/4 keycode tap, the re-pair long-presses). The 2 s sync is now
a true no-op for LEDs. This is the rail fix's shape exactly — pull the effect out of
the bookkeeping, give the effect a single owner, so a re-assert cannot carry it.
Board-local (a vendor sync/indicator design), not a generic model gap.

**Correction (defect 8, 2026-10-13): the "self-re-arm while unconnected" was the
same bug, not a policy.** This fix initially kept one self-retrigger:
`rgb_matrix_wls_indicator_cb()` re-armed the flash whenever the module was not
CONNECTED, described here as "a repeat policy, not a change". On hardware it
turned out to be an **unbounded loop** — any half on a not-connected channel
blinked forever on both halves (the indicator is not master-gated). A
*time-driven* repeat is not a channel change, so it does not belong to this
effect at all; the callback is now a **terminal predicate** that never re-arms.
The lesson generalises: "a repeat policy" is only legitimate if it is **bounded
and explicitly owned**; an effect that re-arms itself from its own completion
callback is a loop, and the vocabulary that hid it ("repeat", "re-assert") was
the tell. See TODO defect 8.

**The general principle (now applied three times).** A re-assert must be a no-op
for anything user-visible: *derive state and effects from a single owner, and let
idempotent re-asserts be silent.* Transport (item 14), the LED rail (defect 5),
the channel indicator (defect 6), and now the indicator's own completion callback
(defect 8) were all the same bug — several partial writers of one piece of state,
or one effect arming itself twice.

## FINDING — one rule, three private copies: the switch wrote half the transport (defect 7)

**The defect.** Flipping the mode switch from BT to USB at runtime did nothing:
neither half typed until a power cycle. The switch edge (`hs_modeio_detection`,
`wls/wls.c`) changed only the **vendor device index**; it never touched
upstream's **connection host**, so the USB data line was never brought up and HID
kept routing to the radio-off BT driver. Boot and the keycode path set **both**
selectors; the switch set one.

**Why the audit missed it.** The ownership/cadence audit (`docs/AUDIT.md`) was a
**per-site** method: it read each function and asked "does this state have one
writer?" That finds *state* with two writers, but it cannot see a **rule** that
is written three times across three functions with no shared name. The rule here
— "the switch level determines the transport" — existed as three independent
implementations (boot, keycode, switch edge), and one had silently drifted. The
audit's own framing ("clean = provable") invited the too-strong reading that the
code was already verified; it was verified *site by site*, which is a weaker
property than *rule by rule*.

**The fix, and the design choice.** A senior answer is not the smallest diff that
makes the three copies agree again — it is to **remove the copies**. The shared
rule was extracted as one pure function, `hsm_switch_apply(pos, last_bt) →
{devs, host}`, and every site now *applies* its result instead of recomputing it;
`hsm_host_of_devs(devs)` is the single `devs → host` mapping (it had three inline
copies). Crucially the **keycode path was not folded in**: its rule is genuinely
different (user intent; the transport is chosen by the keycode, not the switch),
so only the mapper is shared. Over-unifying would have been the opposite error.

**The transferable lesson.** Two selectors that must agree are one state. If a
rule to keep them in agreement is expressed more than once, it *will* drift. Give
the rule a single home (a pure function returning the whole decision — not half
of it, which is how the switch could set the index and forget the host), and make
callers apply it. This is the same shape as defect 4 (the boot path once set only
one selector) — the fix for defect 4 corrected *that site*; the fix for defect 7
removed the possibility of a *third* site diverging.

**Verification caveat (honest).** The pure cores are proven by tests; the
**shells are only compiled, not behaviourally verified**. Both defects 7 and 8
lived in shells (a call site, a callback) that no test exercised. The tests pin
the *decisions*; they cannot yet prove the *wiring*. Both fixes are build-clean
and unit-green; hardware confirmation is pending a flash.

## FINDING — the boot switch read is un-settled, and UNKNOWN is silently applied

**The symptom.** On the USB switch position, a cold plug enumerates completely
(full descriptors, three HID interfaces) and then disconnects **within the same
second**, deterministically, across three power events. It does not re-enumerate.
The MCU is fine (one `new full-speed USB device` per power event, not a reset
loop); the USB stack runs long enough to enumerate. So this is *firmware
tearing its own USB line down*, not a dead or resetting chip.

**The trace.** Walking `main()` → `keyboard_init()` → `keyboard_post_init_kb()`
→ `wls_lifecycle_boot()`, in the order QMK actually calls them (verified against
`quantum/main.c`, `quantum/keyboard.c`, `host.c`, `connection.c`):

1. `connection_init()` reads the EEPROM `desired_host` and, if it is invalid,
   stores `CONNECTION_HOST_AUTO`. It does **not** call `handle_host_changed()`.
2. `keyboard_post_init_kb()` loads `confinfo`. A fresh/blank block is
   re-defaulted, and the default sets `last_btdevs = BT1` — **so the persisted
   fallback holds a Bluetooth index.**
3. `wls_lifecycle_boot()` enables the switch pins as pull-up inputs
   (`gpio_set_pin_input_high`, i.e. `palSetLineMode(…, PAL_MODE_INPUT_PULLUP)`)
   and **immediately** reads them via `hs_mode_switch_pos()` — with **no
   `waitInputPinDelay()`** on this path (the settle macro exists, but only the
   sleep path uses the pattern).

A `PAL_MODE_INPUT_PULLUP` change takes effect asynchronously; a pin read in the
same breath can see the old (floating) level. `hs_mode_switch_pos()` then falls
through all three patterns to `HSM_SWITCH_UNKNOWN`. **And `UNKNOWN` is not
rejected — it is *mapped*:**

- `hsm_boot_devs(UNKNOWN, last_bt)` returns `last_bt` when it is a BT index, else
  USB. With the fresh default that is **BT1**.
- `hsm_host_of_devs(BT1)` returns **BLUETOOTH**.
- The transport applier in the code *at the time* (`apply_switch_transport()`,
  since replaced by `hsm_input_rule()` / `wls_transport_decide()`) then called
  `connection_set_host_noeeprom(BLUETOOTH)`.
  The stored value was `AUTO`, so this is a *change*: it writes and calls
  `handle_host_changed()` → `connection_host_changed_kb()` →
  `wls_usb_connect(resolved == USB)` → **`wls_usb_connect(false)` → the USB data
  line is torn down inside post-init.**

4. The first `wireless_task()` (first `housekeeping_task`, after the first
   `keyboard_task`) has a function-local-static one-time guard that calls
   `wls_usb_connect(connection_get_host() == USB)` a **second** time — the same
   decision enforced by a second mechanism.
5. At `post_init_timer + 100 ms`, `wireless_post_task()` called the same applier
   (`apply_switch_transport(hs_mode_switch_pos(), …)`) **again**. By then the
   pull-ups *have* settled, so this read is reliable and re-applies the correct
   transport. **This is why a later replug or a switch flip recovers** — and why
   the failure window is exactly the first ~100 ms of boot.

**The real defect is not the missing delay.** The delay is one instance. The
class is: *a level-derived value is sampled once, with no settling and no
confirmation, and its indeterminate state is translated into a valid-looking
answer* — `UNKNOWN → last_bt → BLUETOOTH`. A missing delay is a timing bug; a
**total mapping of "indeterminate" onto "a definite transport"** is a
*representational* bug, and it would resurface in any future read this board
adds. The pull-up enables a decision; the decision is worthless until the level
is knowable; and the code has no way to *say* "not knowable yet".

**Why the instruments did not catch it.** `wls_diag` exports over the raw-HID
reply — which needs the USB line — so on this failing path, the line is dead
before the host can ask. The observability seam is unreachable exactly when it is
needed. This is itself a design finding: a diagnostic that rides the failing
channel is not a diagnostic for that channel's failures.

**The transferable lessons.**

1. *An input read must have a settled-ness, not just a value.* If a pure core
   cannot represent "indeterminate", the shell must invent something — and it
   will invent a plausible wrong answer. Express indeterminacy in the type.
2. *Enabling and reading an input are two events, not one.* Enabling a pull-up
   (or any pin mode) is asynchronous; the read belongs after the settle, not
   adjacent to the mode change.
3. *A fallback that is indistinguishable from a real answer is worse than no
   fallback.* `UNKNOWN → last_bt` looks defensive; it converts "I don't know"
   into "Bluetooth", which is the one answer that silently kills USB.
4. *Two enforcers of one rule are one too many.* The boot seed and the task-pass
   guard both actuate the USB line from the same resolved host — the defect-7
   shape again (one rule, two homes, able to disagree). One owner.
5. *A diagnostic must survive the failure it diagnoses.* The seam needs an
   exporter that does not depend on the channel under test.

**The fix this derivation implies** (developed as `wls-*` slices and tested):
represent settled-ness in the pure core (`hsm_switch_apply` returns a `settled`
flag; an unsettled read applies **nothing**), read after a settle, collapse the
two line-actuators to one owner, and give the diagnostic a second exporter that
does not ride the USB line. The first of these makes the defect *unrepresentable*
rather than merely absent — which is the bar this project set for itself.

**The remedies as landed** (all four, with their regression guards):

- *Settled-ness in the core.* `hsm_switch_apply()` returns a tagged
  `hsm_switch_apply_t { kind; devs; host; }` (`HSM_SWITCH_SETTLED` /
  `HSM_SWITCH_UNREADABLE`), matching the house `wls_blink_out_t` /
  `filp_action_t` shape; in the unreadable case the payload is **poisoned to
  0xFF**, not zeroed — `DEVS_USB` is 0, so a zeroed payload would be
  indistinguishable from a real USB decision. The input rule (`hsm_input_rule()`)
  applies nothing unless settled. Guarded by `tests/transport_logic` (20/20), which
  asserts the unreadable case carries no transport for *every* `last_bt`.
- *Read after a settle.* The boot seed now calls `waitInputPinDelay()` between
  enabling the C14/C15 pull-ups and the first read (the idiom the sleep path
  already used); `palSetLineMode` is asynchronous, so the gap is real.
- *One owner for the USB line.* The shared stack's one-time
  `static bool usb_initialized` guard in `wireless_task()` was a second enforcer
  of the same rule (and existed only because `connection_set_host_noeeprom`
  early-returns when the stored host already matches, so the board handler does
  not fire for the already-USB case). Deleted; the board's boot seed now covers
  that case unconditionally on a settled read. The line has exactly one owner:
  the board's `connection_host_changed_kb()` plus the boot seed.
- *A second exporter that does not ride the USB line.* The boot decision
  (switch position, applied host, settled-ness) is retained in `wls.c` beside the
  boot counter and exposed on the `0xA4` reply at the boot-code index (21), now
  as the `(amber, white)` pair the LED also plays — see the instrument finding
  below. Because it is
  retained rather than sampled live, the *next* successful reply is a post-mortem
  of a boot whose own USB line died — the case the live 10-byte diag block cannot
  cover. Written by `wls_lifecycle_boot()` at the moment of decision; decoded by
  `host/battery_polybar.py` (a `BOOT:` line; note its host field is the
  `HSM_HOST_*` vocabulary, not the raw `CONNECTION_HOST_*`). Tested 7/7.

- *A host-less exporter: the same record, blinked.* The USB reply above still
  needs the USB line, so it cannot be read on the very boot that tears the line
  down. `wls/boot_blink_logic` is the missing **in-sequence** blink (the existing
  indicator arrays hold flashes concurrently, not in sequence): given a schedule
  of per-step pulse counts and the current time, it says which step to show and
  whether the pulse is lit. The schedule itself is the pure
  `wls_boot_report_blink_step()` (same `boot_report_logic` core): step 0 = switch
  position, step 1 = applied host, step 2 = settled-ness (one white pulse when
  settled, three red when not — the failure marker). `wls_indicator_boot_report_start()`
  arms it from the retained decision at boot; the RGB frame hook paints it. It is
  the one indicator that works with the line down. Tested 7/7.

  > **SUPERSEDED (2026-10-14).** This field-per-step blink was replaced: reading
  > it in the field proved ambiguous (four defects — not exclusive, per-step
  > durations differed, no delimiter, an ordering fault). `wls/boot_blink_logic`
  > and `wls/boot_report_logic` are **deleted**; the retained-decision half now
  > lives in `wls/wls.h` and the host renderer in `wls/boot_code_logic`. See
  > "the boot instrument is a Dell-style `(amber, white)` code" below.

So both halves of Measure D are in place: the retained record (readable on the
next successful reply) and the blink (readable with no host at all). The
self-detach now has an instrument that survives the failure it diagnoses.

## FINDING — the low-power presleep hook cut a live USB line, giving a periodic reset loop

**Symptom.** On the USB switch position the keyboard re-enumerated repeatedly —
27 times in 60 minutes, the device number climbing every cycle, each cycle
re-emitting the full descriptor set and re-binding all three interfaces on the
host. Intervals were bimodal: many re-enumerations within **1 s**, interleaved
with stable windows of 10 s, 26 s, ~2 min and ~4 min, and finally a settle that
lasted. It correlated with host activity, not a free-running timer.

**What it was not.** Not a hard fault: every fault handler on this build resolves
to the same weak `_unhandled_exception`, which is `b.n` to itself — an infinite
self-branch that would *hang* the MCU, not reset it. Not a watchdog: no
IWDG/WWDG is linked and `SPLIT_WATCHDOG_ENABLE` is deliberately undefined. Not
the boot seed: with the switch read UNKNOWN, the boot applier of the day
(`apply_switch_transport()`, now `hsm_input_rule()`) applied nothing, so the boot path was inert.

**What it was.** `wls_lifecycle_lpwr_allow_presleep()` ended with

```c
if ((wireless_get_current_devs() == DEVS_USB) && (!charging_state)) {
    if (USB_DRIVER.state != USB_STOP) { usb_power_disconnect(); usbDisconnectBus(&USBD1); usbStop(&USBD1); }
}
```

— byte-identical to the pre-refactor vendor/board code, so a **pre-existing
latent bug**, not one our rewrite introduced. It became reachable through two
compounding conditions:

1. The switch read comes back **UNKNOWN**, so nothing is applied and
   `wireless_get_current_devs()` keeps its prior value — which in the USB
   position *is* `DEVS_USB`. The guard therefore reads a **stale** transport the
   boot refused to apply.
2. `!charging_state` is not a "we are on battery" test. `HS_BAT_CABLE_PIN` (A7)
   is a **shared "power present" bit**, not a charger detect (docs/HARDWARE.md,
   "Split-link power"), so on a host's own port it can read either way for
   reasons unrelated to whether the host is *using* the data line.

Together those make the guard hold for the whole session, so **every time the
low-power machine reached pre-sleep it cut the USB line**, the host logged a
disconnect, the device re-enumerated, and the same state came back.

**The fix.** Gate the teardown on the thing the hook actually means — the line is
not in use — instead of on `!charging_state`:

```c
if ((wireless_get_current_devs() == DEVS_USB) && (USB_DRIVER.state != USB_ACTIVE)) { ... }
```

A line in `USB_ACTIVE` is enumerated and in use; tearing it down is never a
low-power action. This makes the hook agree with its sibling
`lpwr_is_allow_timeout()` in `lowpower.c`, which already states "on USB" as
`(devs == DEVS_USB) && (USB_DRIVER.state == USB_ACTIVE)` — the two had been
contradicting each other.

**The transferable lesson.** A guard built from a *stale* value plus a
*repurposed* signal is worse than no guard: `DEVS_USB` was never applied (so it
was not a fact), and `charging_state` was never about the charger (so `!` it was
not the claim it appeared to be). The class is the same one this project keeps
meeting — an indeterminate or repurposed input translated into a confident,
valid-looking decision. The cure is the same: make the predicate mean what it
says, and never act on a value the boot declined to apply.

## FINDING — the recurring defect is one class, and it has two shapes

Four defects found on hardware in one session (2026-10-13) shared a structure
that is worth naming, because naming it is what turns four patches into one
remedy. **The class:**

> An effect is derived from state whose value the effect itself can change — or
> whose validity depends on an initialization or lifecycle stage that the
> effect's trigger can precede.

The class has two shapes with *different* root remedies:

- **Feedback** — the trigger reads a value the effect perturbs. The result is a
  livelock or an oscillation, and the symptom looks like a hardware fault
  (self-detach, re-enumeration). The remedy is to break the loop: a trigger must
  not depend on a signal its own effect modifies.
- **Ordering** — the effect is reachable at a lifecycle stage where its
  dependencies are not yet valid. The result is a fault or a silent no-op. The
  remedy is a gate the *component that owns the effect* enforces, so no caller
  can reach it too early.

**The four instances.** (1) `hs_modeio_detection`'s predicate asked "does the
resolved transport differ from the pins?" — permanently true once the transport
legitimately differed, so it re-fired every 50 ms and re-drove the USB line
(feedback). (2) The polled USB-activity edge in housekeeping re-armed itself on
the `USB_ACTIVE` loss its own `restart_usb_driver` caused (feedback). (3) The
USB lifecycle hook, reachable from `protocol_setup()` before `wireless_init()`,
let the owner call `wireless_devs_change()` → `smsg_push()` on an uninitialized
ring and HardFault the MCU before the main loop — a deterministic dead board
(ordering). (4) The boot and +100 ms sites drove `wls_usb_connect(false)` from an
*unconfirmed* hint decision, cutting the line a host needed to confirm — the
promotion that outranks a lying switch could never fire (ordering, and also
feedback: the decision destroyed its own trigger).

**Why the instance fixes were not enough.** The first two fixes were guards on
`wls_usb_connect`'s call sites. That made *that one actuator* safe and said
nothing about `wireless_devs_change` — the actuator that actually hard-faulted —
nor about the suspend hooks, which had the same shape and were reachable from the
same early stage. **Gating one actuator's call sites is not gating the class.**

**The class remedy, now in the tree.** (1) `wls_module` owns "the module is up"
and refuses a device-index change before it, so *every* caller — present and
future — is safe. (2) The transport owner drives the USB line itself, in one
place, and the decision carries its input's *class*: an unconfirmed hint may only
**promote** (turn the line on, idempotent); **demotion** belongs to confirmed
events. (3) The rail owner's comment names its one deliberate exception, so the
"one writer" claim is true.

**The transferable lessons.**
- **The two directions of a destructive actuator are not symmetric.** A confirmed
  owner may command loss; an unconfirmed derivation may only command presence.
  Commanding loss destroys the very input that would confirm.
- **Gate the component, not the caller.** A guard at each call site is a promise
  someone must remember; a gate inside the owner is a fact the compiler and the
  tests enforce.
- **Nothing may act before its dependencies exist.** A hook reachable from
  `protocol_setup()` runs before `keyboard_init()`, before EEPROM, and before the
  wireless module. A hook that *records an input* there is fine; one that
  *performs an effect* is a fault waiting for a boot.
- **A pure predicate can only be tested if it is a pure predicate.** Every rule
  above is a one-line boolean with a test; the shells cannot be unit-tested, so
  the invariant has to live where a test can reach it.

## FINDING — the boot instrument is a Dell-style `(amber, white)` code, and the old one was unreadable

> **The reader's contract now lives in `docs/INDICATORS.md`** — how to count the
> code, the stage vocabulary, the other indicators, and the four constraints a
> trustworthy instrument must satisfy. This section keeps the *discovery
> narrative*: why the previous instrument was unreadable and what replaced it.

**Why a new instrument.** The region this project is now working in — the boot
sequence and the vendor wireless stack reached through it — is *not amenable to
bug-hunting*: it runs before there is a console, before USB is up, and (as of the
2026-10-13 faults, §13 items 0/0b of `docs/BOOT-SEQUENCE.md`) it can fail in ways
that leave the board dark and silent. The only channel that survives such a
failure is the LED rail, which is powered before the switch read. So the
instrument is the LED, and the LED instrument had to become trustworthy before
anything else could be.

**The four defects that made the old instrument unreadable.** (1) It was **not
exclusive**: the boot schedule painted at `rgb_matrix_indicators_advanced_kb`,
but `wls_indicator_set_flash()` ran *after* it and, for an indicator with
`index == 0xFF`, called `rgb_matrix_set_color_all(...)` — repainting the whole
matrix and erasing the frame. The battery and channel indicators painted in the
same pass. This is why the early field readings ("white magenta" and "white,
magenta, then solid white") were ambiguous: the eye was seeing a mixture whose
content depended on unrelated state. (2) **Per-step durations differed** — the
step period was applied *per half-period*, so a step with `n` pulses lasted
`n × 400 ms` and counting required the spec open. (3) **No delimiter and no
repetition** — the schedule played once, from an arbitrary phase, with no leading
marker; a missed start was unrecoverable. (4) **An ordering fault of the
project's own recurring class**: the schedule was *started* in
`wls_lifecycle_boot()` (step 33 of `keyboard_init()`) but only *painted* once the
RGB frame pass ran in `main()`'s loop, so its phase had already advanced before
the first paint, and a boot that died earlier showed nothing at all.

**The convention adopted.** Dell's Latitude E-series diagnostic LED, KB
`000131044`: a **two-part code `(amber, white)`** — "the first number represents
the number of amber-colored flashes, the second number the number of white-colored
flashes"; the LED stops `1.5 s` between the two groups and `3 s` between
repetitions, and the code repeats. So **colour partitions the code into two
groups; the count carries the value**; the intra-code gap delimits the groups and
the inter-code pause delimits the frame. Repetition makes a missed start
recoverable. This replaced the previous field-per-step schedule entirely.

**What the code speaks.** Amber = the boot **stage** (coarse category); white =
the code within it. `WLS_BOOT_STAGE_{OK=0, PREINIT=1, BOOT_PASS=2, TRANSPORT=3,
ROLE=4, INCOMPLETE=5}` — OK speaks no amber and reports the chosen transport and
role, so a working board is *also* readable; a fault speaks its stage first. The
white-code assignments within each stage are deliberately revisitable (the
vocabulary is expected to change); only the stage partition is fixed. The code is
carried on the host channel too, at `KB_BATTERY_IDX_BOOT_CODE`, so the eye and
the host cannot drift: `host/battery_polybar.py` prints
`BOOT CODE: A amber, W white -> stage=… code=…`.

**The design that makes it trustworthy.**
- **`wls/boot_code_logic.{c,h}` is pure**: `wls_boot_code_counts()` maps a
  `(stage, code)` to `(amber_count, white_count)` (clamped to `1..9` — a group is
  never zero-length within a spoken code, since zero is indistinguishable from a
  missing delimiter); `wls_boot_code_frame_ms()` gives the frame length;
  `wls_boot_code_at(counts, elapsed_ms)` returns the phase and colour at an
  *elapsed* time, taken modulo the frame, so a **late first paint is still
  correct** — the property the old instrument lacked. `wls_boot_code_encode()`
  writes the same pair for the host. 13 tests, including the exact pulse counts,
  the pulse width, the three ordered time scales (pulse period < group gap <
  frame gap), the dark frame gap, and the loop property.
- **The matrix has one arbitration owner.** While the boot code plays,
  `wls_indicator_boot_code_owns_matrix()` is true and the paint pass returns
  early, suppressing the channel flash, the battery indicator and
  `wls_indicator_set_flash()`. The old additive overwrite is now structurally
  impossible rather than merely reordered — the same "one owner per state" rule
  as the USB line and the rail.
- **It is started from the paint pass**, where the frame is live, so the
  ordering defect (4) is gone by construction.
- **A keypress dismisses it**, and it self-clears after a timeout, so it loops
  long enough to be read from a cold glance at a dark board.

**Timing is measured, not assumed.** The frame rate sets the floor on pulse
width, and it is not derivable from constants: the frame cycle runs inside the
main loop behind a `RGB_MATRIX_LED_FLUSH_LIMIT` (16 ms, not overridden here)
gate, so the true period is `max(16 ms, one loop period)` — loop-rate dependent.
The SPI shift is *not* the limiter (≈5 ms worst case for 68 LEDs). See
`docs/HARDWARE.md` "RGB matrix frame timing". A 300 ms pulse therefore spans ~19
frames and is comfortably reachable.

## FINDING — a reset loop is proved by the chip's own latch, not by an instrument that counts boots

The board was observed to cycle: the app enumerates, binds all three HID
interfaces, then disappears, and the cycle repeats with **`342d:dfa0` — the DFU
bootloader — appearing *between* app enumerations with no flash in progress**.
The bootloader cannot run without executing the reset vector, so a `dfa0`
appearance is proof that the **MCU is resetting**, not merely that the USB data
line dropped. "Self-detach" (a line fault) and "reset loop" (a CPU or power
fault) have different remedies, so the distinction is load-bearing; an earlier
note in `TODO.md` defect 8 calling this "not a reset loop" was wrong and is
corrected there.

**The first instinct was an instrument that infers the cause**: a boot counter
spoken on the LED, so that one reset shows as one more count — a channel that
survives a reset because the LED rail is powered before the switch is read. That
works, but it only proves *that* a reset happened and it needs a replug ritual to
read.

**The better fact was already in the silicon.** The WB32FQ95xx latches the cause
in `RCC->RSTSTAT`, six named bits (low-power, window watchdog, independent
watchdog, software, power-on, external pin), cleared only by an explicit write.
So the MCU can *name* why it reset, and the value survives the fault that
produces it. See `docs/HARDWARE.md` "Reset cause" for the register and bits, and
`docs/INDICATORS.md` §2 for how the boot code speaks it.

**Two lessons, both transferable.**

1. **Consult the silicon before building an instrument that infers.** A counter
   is a proxy for a fact the chip already records; the proxy needed a ritual, the
   latch needs one read.
2. **A latch is consumed once and carried to every reader.** Read-and-clear is a
   *consume* operation, so it must happen exactly once, at one defined point, and
   the consumed value must be retained for every reporter. Reading it at the LED
   and again at the host would let the two disagree — the same "one authority per
   state" rule that governs the transport and the LED rail.

This is the same class the rest of this document names: the *channel* by which a
diagnosis travels must be independent of the fault under diagnosis. A reset
destroys any channel that needs the running application; the LED rail and the
reset-cause latch both survive it, and the latch answers a strictly larger
question than the count.

## FINDING — the shell held policy, and that is why the miscount was untestable

The boot code played `(5 amber, 5 white)` where the core emits `(7 amber, 5
white)`. The core was correct — verified by executing it, twice. The fault was a
bound in the *shell*: `WLS_BOOT_CODE_SHOW_MS 10000` was shorter than a `(7,5)`
frame (**11700 ms**), so the window closed mid-group and the leading amber pulses
were never shown. The other direction is a defect too: a window longer than a
frame lets the next frame's amber group in, and because both groups are amber the
reader counts them together (harness-measured: twelve amber, not seven).

**Why it reached hardware: the decision's inputs lived in the shell.** The
`wls_indicator.c` shell held a clock origin (`static uint32_t boot_code_started`)
and a show bound (the `SHOW_MS` constant). Neither is an effect; both are *inputs*
to the pure decision "what is lit now". So the core never saw them, no pure test
could reach the policy, and the only way to find the bug was to flash it. This is
`docs/BOARD-LAYER.md` principle 1 — "the shell holds no policy" — stated as a
failure mode rather than a rule.

**A related smell: the header promised a property nothing tested.** The
`wls_boot_code_at()` doc comment claimed a late first paint "is still correct".
It was not: a late start shifts the frame and silently consumes leading pulses.
A comment that asserts a guarantee no test enforces is the same defect as the
policy in the shell — a claim where a proof belongs.

**The fix moved the inputs into the core.** `wls_boot_code_show_ms(counts)` now
*derives* the window (exactly one frame, so it cannot disagree with the frame),
and `wls_boot_code_at(counts, origin_ms, now_ms)` takes the origin as a value, so
"how late may the first paint be" is answered by a test. The shell's remaining
state is a latch ("armed"), not a decision.

**Three lessons, all transferable.**

1. **Policy inputs belong in the core, not the shell.** A bound or a clock origin
   that the shell supplies is policy; keep it where it can be tested. If a defect
   is only reachable by flashing, look first for the decision's inputs sitting in
   the caller.
2. **A bound must be derived from the thing it bounds.** A hand-chosen constant
   can disagree with the object it limits, and *both* directions are wrong.
3. **When a reading contradicts the code, execute the core.** The code was right;
   the explanation for the wrong reading was a shell defect, not a hardware quirk.
   Reaching for a hardware hypothesis before running the pure function would have
   sent us to the wrong layer.
