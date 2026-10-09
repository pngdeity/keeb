# EPOMAKER Split65 — Battery reporting: findings and design

> **Scope.** This narrates the **battery-feature work**, which is committed in
> the `qmk_firmware` submodule. The layered helpers below (`wls/wls_battery.c`,
> `WLS_BATTERY_PUSH_*`, the strong `raw_hid_receive` override) are in the tree.
> See `TODO.md` Status.

Why the firmware is shaped the way it is, and which upstream facts a future
change depends on. What the device is is in `DEVICE.md`; measured hardware facts
live in `HARDWARE.md`; the wire format is `PROTOCOL.md`; live status and open
work are in `TODO.md`.

## Functional requirements

The user-facing requirements, in priority order. These are the end; the battery
reporting described below is a means to them.

1. **Wireless while discharging.** Both halves operate on a wireless transport
   (2.4 GHz or Bluetooth) with no cable attached.
2. **Wireless while charging.** Both halves operate on a wireless transport
   while a cable supplies charge (to the battery-bearing left half; see
   `HARDWARE.md` "Batteries").
3. **USB while charging.** Both halves operate over USB-C with a cable attached.

**Why requirement 2 exists.** The operator may charge the halves from an
external PSU while connecting them to a *different, power-limited host* (e.g. a
phone or tablet that cannot supply charging current) purely for input. In that
arrangement the keyboard must keep typing over its wireless link while the
charge comes from elsewhere — so "a cable is present" must not by itself mean
"switch to USB".

**Accepted tradeoff.** The firmware's cable-insert auto-switch (in
`housekeeping_task_user()`) forces `DEVS_USB` when a cable appears, which would
defeat requirement 2. Removing it is sanctioned: the left half has a physical
mode switch, so mode selection can belong to the switch alone. `hs_modeio_detection()`
already forces `DEVS_USB` when the switch is in the USB position, and
`wls_process_long_press()` already makes `KC_BT*`/`KC_2G4` no-ops unless the
switch reports BT/wireless — so the switch becomes the single, coherent control.

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

The vendor tree is **not** a squashed snapshot. It carries full upstream lineage
(28,110 commits); its last real upstream sync merge is `45caa1174b` (2024-10-30),
whose `qmk:master` parent is upstream commit **`92afc8198a`** (2024-10-29, "Add
Singa Kohaku (#24309)"). That is our true base. The vendor then forked to build
the wireless/tri-mode stack and stopped reconciling against upstream — the normal
vendor-fork trajectory.

**The conflict surface is almost nil because the vendor never patched core.**
Of the entire 677-file / 81,873-line divergence from `92afc8198a`, only two
non-board files differ:

- `.gitignore` — removes `*.a` (one line) so the prebuilt `libmodule.a` can be
  tracked (that archive lived only in the obsolete `keyboards/wireless/` copy —
  see below);
- a stray `.txt`.

Plus three submodule bumps (`lib/chibios`, `lib/chibios-contrib`, `lib/pico-sdk`).
Everything else is additive: vendor boards under `keyboards/…` and the shared
wireless stack.

**WB32 platform support is already upstream** at the base —
`platforms/chibios/boards/GENERIC_WB32_FQ95XX/` and
`platforms/chibios/bootloaders/wb32_dfu.c` exist — so the vendor needed no
platform fork, and neither do we.

**Our own authored payload is 9 commits**, confined to
`keyboards/epomaker/epomaker_split65/` and `keyboards/linker/wireless/`. No core
edits we authored. (The vendor overlay line also carried a `lib/python/qmk/math.py`
Python-3.12 fix, but that is the *vendor's* history, not part of the rebase
payload — and upstream deleted `math.py` before our base.)

**Consequence:** re-basing is "replay our ~10 commits onto `qmk/qmk_firmware`
master," not a fork re-import. It was proven tractable by the spike, which has
now landed (branch `split65-overlay`, renamed from `split65-rebase-spike`; the
root gitlink points at it): both keymaps build green on master (`7a1bbf37c5`,
2026-10-02, 1,695 commits ahead of base) after six mechanical upstream-breakage
fixes. The `libmodule.a` "red flag" turned out to be a **non-issue**: the
prebuilt archive lived only in the obsolete `keyboards/wireless/` copy, which no
board linked and nothing referenced, and it held nothing but `module.o`,
`smsg.o` and `assert.o` compiled from source we already hold. That directory is
deleted in the spike (commit `f1ee1f3`); both keymaps rebuild byte-identical, so
no vendored binary remains in the build path. Details in `TODO.md` "## Re-base".

## KEY FINDING — the battery value already exists in firmware

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

## KEY FINDING — raw HID is already bridged over the 2.4 GHz dongle

`keyboards/linker/wireless/md_raw.c` (guarded by `RAW_ENABLE`):

- `replaced_hid_send()` uses the USB endpoint on `TRANSPORT_USB`, otherwise
  `md_send_raw()` tunnels over the module UART.
- `md_receive_raw_cb()` calls `raw_hid_receive(data, length)`.
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

These are **not** obfuscated or encrypted — they are the compiler's literal output
for hand-tuned register writes the author needed to pin exactly (no C prologue,
no register-allocation surprises, no reordering). The bytes are **identical in all
copies** of the file in the tree (`linker/wireless/`, `epomaker/.../wireless/`,
`keyboards/epomaker/epomaker_split65/wireless/`, and the ChibiOS demo
`RT-WB32F3G71-RTC`), which is itself the
proof they are frozen output rather than generated code.

Deobfuscated with:

```sh
python3 -c "import struct,sys; sys.stdout.buffer.write(b''.join(w.to_bytes(4,'little') for w in [553863175,554459777,1208378049,4026624001,688390415,554227969,3204472833,1198571264,1073807360,1073808388]))" > /tmp/opencode/pre.bin
arm-none-eabi-objdump -D -b binary -m arm -M force-thumb /tmp/opencode/pre.bin
```

**`PRE_LP()` — runs before entering deep sleep** (`lpwr_wb32.c:178`). Literal pool:
`0x40010000` (PWR), `0x40010404` (ANCTL + `0x04`).

```asm
ldr  r0, =0x40010000    ; PWR
movs r1, #3
str  r1, [r0, #0x28]    ; PWR->ANAKEY1 = 3   -- unlock ANCTL writes (key 1)
movs r1, #12
str  r1, [r0, #0x2C]    ; PWR->ANAKEY2 = 12  -- unlock ANCTL writes (key 2)
ldr  r0, =0x40010404    ; ANCTL + 0x04
ldr  r1, [r0]
and  r1, r1, #0x0F
cmp  r1, #8
bls  done
movs r1, #8             ; clamp ANCTL[+4] low nibble to <= 8
str  r1, [r0]
done: bx lr
```

**`POST_LP()` — runs after waking** (`lpwr_wb32.c:186`). Literal pool:
`0x40010000`, `0x1FFF0000`, `0x40010404`.

```asm
ldr  r0, =0x40010000
movs r1, #3
str  r1, [r0, #0x28]    ; re-unlock ANCTL
movs r1, #12
str  r1, [r0, #0x2C]
ldr  r0, =0x1FFF0000    ; undocumented factory/trim mirror region
ldrb r0, [r0, #0x310]
and  r0, r0, #0x0F
ldr  r1, =0x40010404
ldr  r2, [r1]
cmp  r2, r0
beq  skip
str  r0, [r1]           ; sync ANCTL[+4] low nibble from SYS[+0x310]
skip:
movs r0, #0
loop: adds r0, #1       ; short analog-settling delay before resuming
cmp  r0, #0x23          ; 0x23 = 35 iterations
blt  loop
bx   lr
```

At the board's 96 MHz sysclk (`mcuconf.h`: `WB32_PLLDIV_VALUE 2`,
`WB32_PLLMUL_VALUE 16`) the loop is only ~100–200 ns — a settling margin, not a
noticeable delay.

So the sequence is: **re-open the analog-control (ANCTL) write lock, clamp/sync a
trim field, let the analog domain settle briefly, then return.** Every address is
a documented WB32 peripheral (`PWR_BASE = 0x40010000`, `ANCTL_BASE = 0x40010400`,
`SYS_BASE = 0x40016400`) with one exception: `0x1FFF0000 + 0x310`, which is not
`SYS_BASE` and sits in an undocumented address region (a factory/trim mirror the
vendor reads by raw literal). Its source register has no name in the CMSIS header.

Why the blobs stay as machine code (a deliberate choice, not an artifact):

- **Timing/masking guarantee.** `str`/`ldr` of constants with no compiler-inserted
  code between them is the whole point; C cannot promise the exact stream.
- **Register-free.** The code uses only `r0–r2`, so it is safe to call from any
  context, including the low-power path where the stack may be minimal.
- **Vendor-tuned and shared.** Since the bytes are identical across every board
  that uses the stack, rewriting them in C would fork that shared file per board
  for zero functional gain.
- **Corroborated by the factory images.** The two vendor release binaries
  (`vendor/factory-firmware/`, v7 Nov 2024 and v10 Dec 2025) each contain the
  `PRE_LP`/`POST_LP` byte sequences **exactly once, byte-identical** to ours — as
  does our own built `.bin`. So this is the vendor's own construction on the same
  hardware, not something our tree introduced.

Do **not** rewrite them in C as a "cleanup". They work, they are timing-critical,
and they are the one place where the compiler must not be trusted to schedule.
The right treatment is the one given here: document the disassembly so the file
stops being a black box, and leave the bytes alone.

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
6. **Bluetooth path**: still unprobed. Open question is whether the BT HID link
   exposes the raw collection and whether `*md_getp_bat()` is populated over BT;
   the host falls back to BLE either way. Tracked in `TODO.md`.

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
- `raw_hid_send`'s macro remap in `md_raw.h` is **line-specific**: it renames
  `raw_hid_send` to `replaced_hid_send` only where `__LINE__` matches a fixed
  number, by defining `_temp_rhs_<n>`. It currently keys on exactly two lines:
  `quantum/raw_hid.h:29` (the declaration; inert) and `quantum/via.c:489` (the
  live call QMK core makes). Consequence: a QMK/submodule bump that shifts
  either line **silently** breaks the tunnel — raw HID replies would go to the
  wrong transport with no compile error. New code must never rely on the macro;
  call `replaced_hid_send()` directly (as `wls_battery.c` does). CI's
  "Guard the raw-HID tunneling line coupling" step asserts both lines still
  hold the expected text and fails loudly otherwise; if it fires, update
  `keyboards/linker/wireless/md_raw.h` and that guard together.

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
`wireless_task()` (`keyboards/linker/wireless/wireless.c:225-243`) only calls
`md_inquire_bat()` when the transport is **not** USB:

```c
if (get_transport() == TRANSPORT_USB) {
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
transport field, and requirement 2. The raw-HID tunnel is likewise
transport-agnostic (`md_raw.c:23-27`: `replaced_hid_send()` uses `md_send_raw()`
whenever the transport is not USB). Caveat: the module is the single radio for
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
`quantum/keyboard.c:541,792`. A future `BLUETOOTH_DRIVER = custom` implementing
that header is the upstream-idiomatic home for our module — mirroring what we
already did with `BATTERY_DRIVER = custom`. Of the upstream BT keycodes, only
`QK_OUTPUT_BLUETOOTH` is implemented; the profile/unpair/2.4 GHz keycodes are all
still "(not yet implemented)". **This is a later refactor, not a test
prerequisite.**

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
produced three separate hardware defects (battery `100` on USB, the unwakeable
slave, the wrong interface pick) — one root cause wearing three hats.

Two of those are addressable *within our files*, without touching the shared
vendor stack (so upstream divergence stays a one-file diff):

- **Transport arbiter is now a no-op.** `hs_transport_arbitrate_cable()` used to
  own the cable insert/remove policy (switch to USB on insert; restore
  `confinfo.last_wireless_devs` on remove). It was deliberately gutted to a
  `return false;` stub so a cable no longer forces USB, which is what functional
  requirement 2 needs: mode selection now belongs solely to the physical switch
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
- **Which interface did the host pick?** See `TODO.md` defect 3.
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
