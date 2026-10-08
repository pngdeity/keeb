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
  in the vendor's own history).
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
  tracked;
- a stray `.txt`.

Plus three submodule bumps (`lib/chibios`, `lib/chibios-contrib`, `lib/pico-sdk`).
Everything else is additive: vendor boards under `keyboards/…` and the shared
wireless stack.

**WB32 platform support is already upstream** at the base —
`platforms/chibios/boards/GENERIC_WB32_FQ95XX/` and
`platforms/chibios/bootloaders/wb32_dfu.c` exist — so the vendor needed no
platform fork, and neither do we.

**Our own authored payload is 9 commits**, confined to
`keyboards/epomaker/epomaker_split65/`, `keyboards/linker/wireless/`, and a
4-line `lib/python/qmk/math.py` fix. No core edits we authored.

**Consequence:** re-basing is "replay our ~10 commits onto `qmk/qmk_firmware`
master," not a fork re-import. It was proven tractable by the spike (branch
`split65-rebase-spike`): both keymaps build green on master (`7a1bbf37c5`,
2026-10-02, 1,695 commits ahead of base) after six mechanical upstream-breakage
fixes. The one genuine red flag is `libmodule.a`, the vendor's prebuilt binary —
a vendored `.a` is not upstreamable as-is and needs a keep-or-replace decision.
Details in `TODO.md` "## Re-base".

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

`keyboards/linker/wireless/` is a **de-facto shared library**: ~20 boards include
its `wireless.mk`. Split65 therefore does **not** carry a copy of the whole
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
The one shared file we did touch is `wireless.c`'s leading blank line, a lint
fix that benefits every board using the stack.

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
`et/wireless/`, and the ChibiOS demo `RT-WB32F3G71-RTC`), which is itself the
proof they are frozen output rather than generated code.

Deobfuscated with:

```sh
python3 -c "import struct,sys; sys.stdout.buffer.write(b''.join(w.to_bytes(4,'little') for w in [553863175,554459777,1208378049,4026624001,688390415,554227969,3204472833,1198571264,1073807360,1073808388]))" > /tmp/opencode/pre.bin
arm-none-eabi-objdump -D -b binary -m arm -M force-thumb /tmp/opencode/pre.bin
```

**`PRE_LP()` — runs before entering deep sleep** (`lpwr_wb32.c:285`). Literal pool:
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

**`POST_LP()` — runs after waking** (`lpwr_wb32.c:293`). Literal pool:
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

1. **Battery source abstraction** (`wls/wls.c`): `kb_battery_percent()` (clamps
   `*md_getp_bat()` to 0-100), `kb_battery_charge()` (0/1/2 from
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
  `tmk_core/protocol/chibios/usb_main.c:539`.
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
  `quantum/raw_hid.h:29` (the declaration; inert) and `quantum/via.c:461` (the
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

**Consequence.** Adopting the upstream battery API retires the
`kb_battery_snapshot_t`/`kb_battery_percent()` naming that
`docs/PROTOCOL.md` described — that doc now scopes to the wire format and the
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
`SPLIT_WATCHDOG_ENABLE` / `SPLIT_ACTIVITY_ENABLE` are upstream options we have
not switched on — unused features, not bespoke code.

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
3. **Layering decision (the real gate)** — whether the wireless stack becomes a
   `drivers/wireless/` + `quantum/wireless/` feature with a driver contract,
   mirroring `quantum/battery`/`drivers/battery`. Upstream has no precedent for a
   shared dir under `keyboards/` (our `keyboards/linker/wireless/`). Resolves the
   `host_driver_t` alignment above.
4. **`libmodule.a` resolution (hard blocker)** — vendored prebuilt binaries are
   rejected upstream. Either the module traffic moves behind a documented UART
   protocol with no prebuilt blob, or the merge is blocked. A design question, so
   answer it before building more on top — see `TODO.md`, Re-base.

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

- **Transport arbiter.** `hs_transport_arbitrate_cable()` is the single owner of
  the cable insert/remove policy (switch to USB on insert; restore
  `confinfo.last_wireless_devs` on remove). Both `housekeeping_task_user` and
  `lpwr_wakeup_hook` now call it instead of mutating `confinfo` and
  `wireless_devs_change()` themselves, so the two paths can no longer interleave.
- **Atomic battery snapshot.** `kb_battery_snapshot_t` + `kb_battery_snapshot()`
  sample `percent`/`charge`/`transport` **once**; the change check
  (`kb_battery_changed()`) and the report assembly (pull and push) are both built
  from that one sample, so they cannot observe a torn state.

The **general** fix — a real board-facing API replacing the externed globals — is
deliberately **not** done. It is upstream-sized (it would touch the shared stack
and ~20 boards) and belongs in the U1 RFC's scope, not a local cleanup. The two
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
  `#define SPLIT_TRANSACTION_IDS_USER USER_SYNC_MMS` (`config.h:79`), registers a
  slave handler with `transaction_register_rpc(USER_SYNC_MMS, ...)`
  (`epomaker_split65.c:215`), and drives it with `transaction_rpc_exec(...)` in
  five places (the mode-sync 0x55 / 0xCC / 0xAA paths). This is exactly QMK's
  documented "custom data sync between sides" mechanism. *(An earlier note in
  this project called the m2s/s2m link "hand-rolled" — that was wrong; it is
  upstream's RPC transport with vendor-chosen `cmd` bytes.)*
- **Handedness is upstream's hand-by-pin.** `keyboard.json` sets
  `split.handedness.pin B9`, generating `SPLIT_HAND_PIN B9` — the doc's
  "Handedness by Pin" method, with high = left.
- **`SPLIT_USB_DETECT` is forced on for this board.** `platforms/chibios/chibios_config.h:18-20`
  defines it whenever `USB_VBUS_PIN` is **not** defined, and this board does not
  define that pin. So core would delegate master by USB communication — which is
  why the board's `is_keyboard_master()` override (to `readPin(SPLIT_HAND_PIN)`)
  matters: it **supersedes** the core USB-role decision, pinning the role to
  handedness. The doc's own warning that `SPLIT_USB_DETECT` "will stop the
  ability to demo using battery packs" is precisely the reason a battery board
  prefers a pinned handedness — that is what this board does.
- **Supported transport.** ARM split with the `serial` / `serial_usart` driver is
  upstream-supported; the board uses `SERIAL_USART` (SD1 A9/A10).

**What upstream offers that the vendor does not yet use** (candidates for the U1
port, not defects today):

- **`SPLIT_WATCHDOG_ENABLE` / `SPLIT_MAX_CONNECTION_ERRORS`.** The vendor stack
  has its own low-power/disconnect handling; upstream's watchdog would reboot a
  wedged slave if no master communication arrives. Worth evaluating against the
  vendor logic rather than adding blindly.
- **`SPLIT_ACTIVITY_ENABLE`.** Syncs activity timestamps so a sleep timeout can
  fire consistently across halves — directly relevant to the deep-sleep work.
- **The other `SPLIT_*` sync options** (`SPLIT_MODS_ENABLE`, `SPLIT_LAYER_STATE_ENABLE`,
  …) are documented as cosmetic/OLED aids; the board has no display, so these are
  not needed.

**Conclusion for the upstream effort:** the split layer is *not* a place to
invent. The vendor already rides QMK's transaction RPC and handedness-by-pin.
The upstream-shaped contribution is the **wireless/battery** layer (radio,
low-power, module UART) — that is the genuinely novel part, and it should sit
*on top of* the standard split mechanisms rather than replacing them.
