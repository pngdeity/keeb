# Hardware reference — EPOMAKER Split65

Physical and electrical facts established by measuring the real hardware. These
are **not** derivable from the source tree, so they are recorded here to avoid
re-discovering them. What the device *is* and how to name its parts is in
`DEVICE.md`; source-derived behaviour is in `FINDINGS.md`; the wire format is
`PROTOCOL.md`; live status and open work are in `TODO.md`.

Terminology: `left half` / `right half` name physical position (operator's point
of view); `master half` / `slave half` name the firmware role. See
`DEVICE.md` "Nomenclature". This file uses the role word only where the
behaviour is a role behaviour (e.g. "only the master answers").

## USB identities

| Device | VID:PID | Mode | Manufacturer string | Product string |
|---|---|---|---|---|
| Left half (`LEO`) | `342d:e4c6` | application | `LEO` | `EPOMAKER Split65` |
| Right half (`LEO`) | `342d:e4c6` | application | `LEO` | `EPOMAKER Split65` |
| 2.4 GHz dongle | `342d:e4c6` | application | `MILE` | `2.4G Dongle` |
| Any half | `342d:dfa0` | WB32 DFU bootloader | `Westberry Tech.` | `WB Device in DFU Mode` |

- The keyboard and the dongle share the **same VID:PID** (`342d:e4c6`). They are
  distinguishable only by the manufacturer/product string and by which
  interfaces they expose.
- `bcdDevice` for this firmware is `0.3.0` (`keyboard.json` `usb.device_version`,
  reported `0.30`); stock firmware reported `0.0b` with manufacturer `MILE`.
- **Manufacturer string is the quickest "is our firmware on it" check:** `LEO` =
  ours, `MILE` = stock.
- The bootloader is at `342d:dfa0` in both halves.

## Battery indicator LED

One LED, on the **right half** bottom row. Its index is into
`keyboard.json`'s `rgb_matrix.layout` (68 LEDs).

| Constant | Index | Matrix | Position | Role |
|---|---|---|---|---|
| `HS_MATRIX_BLINK_INDEX_BAT` | 63 | `[11,3]` | 6th from the right | Charging/full colour, and periodic blink at level `<= 15` |

- Drawn by `bat_indicators()` on the **master half only**, even though the LED is
  physically on the right half.
- Behaviour (vendor `default`): while charging *and* full, red; while charging
  (not full), green; while discharging at `<= BATTERY_CAPACITY_LOW` (15), a red
  blink every `250 ms`; at `<= BATTERY_CAPACITY_STOP` (0) it also lowers the
  sleep timeout.
- The red/green charging colours are drawn only while a battery query is active
  (`im_bat_req_charging_flag`, set by `KC_BATQ`); they are not continuously
  shown.
- This is **not a percentage bar**: no key and no LED renders a numeric level.
- Our tree adds an always-on "soft" level indicator inside the same
  `bat_indicators()`: two adjacent right-half bottom-row LEDs at indices 64 and
  65 (`[11,4]`/`[11,5]`, `HS_MATRIX_BAT_SOFT_INDEX`/`HS_MATRIX_BAT_SOFT_INDEX2`)
  drawn at full channel intensity. Colours: green ≥50 %, amber ≥30 %, red below
  30 % (the vendor's separate `<= 15` blink is a different indicator), green while
  charging-to-full, blue while charging. It is part of the battery work committed
  in the submodule (see `TODO.md`).

## RGB matrix frame timing

The LED-facing diagnostics (the boot code blink) are a *side effect* of the RGB
matrix frame pass, not an independent output: whatever is painted is only
repainted when the frame pass runs. So the frame period is the hard ceiling on
the blink's temporal resolution — a pulse shorter than one frame can be dropped
entirely. This is the "the timing is not what the comment claims" trap, one
level below the instrument itself, so it is measured rather than assumed.

**What is verified from the source (2026-10-14):**

- **The frame gate is `RGB_MATRIX_LED_FLUSH_LIMIT` = 16 ms**, defined in
  `quantum/rgb_matrix/rgb_matrix.h` (`#ifndef` default 16) and applied in
  `rgb_task_sync()` (`rgb_matrix.c`): the next frame begins only when
  `sync_timer_elapsed32(g_rgb_timer) >= RGB_MATRIX_LED_FLUSH_LIMIT`. The value is
  **not** overridden by this board (absent from the build's `cflags.txt`).
- **The whole frame cycle runs inside the main loop**, not a timer:
  `keyboard_task()` (`quantum/keyboard.c:737`) calls `rgb_matrix_task()`, which
  walks `STARTING → RENDERING → FLUSHING → SYNCING`. The real frame period is
  therefore `max(16 ms, one main-loop period)` — it is loop-rate dependent and
  **cannot be derived from constants alone**.
- **The SPI transfer is not the limiter.** The panel is `WS2812_SPI`
  (`WS2812_SPI_DIVISOR 32`, driver `SPIDM2`) driving **68** LEDs
  (`RGB_MATRIX_LED_COUNT`). One frame transmits `4 (preamble) + 68 × 12 (data) +
  112 (reset) = 932` SPI bytes. Even at a pessimistically slow 1.5 MHz that is
  ~5 ms — below the 16 ms gate at any plausible SPI clock, so the WS2812 shift
  time does not dominate.
- **Consequence for the blink design:** at the nominal 16 ms frame the pulse
  width of 300 ms spans ~19 frames, so a pulse is only dropped if the main loop
  period exceeds roughly 150 ms. The measured period is published through the
  boot report (see below) so this stays a *verified* fact, not a standing
  assumption.

### RESOLVED 2026-10-14: the amber group rendered green because the byte order was wrong

**Cause found by reading the whole chain, not by theory about timing.** The board
never defined `WS2812_BYTE_ORDER`, so the driver took upstream's default
(`drivers/led/ws2812.h`: `#ifndef WS2812_BYTE_ORDER` → `WS2812_BYTE_ORDER_GRB`).
Under that order the driver's `ws2812_led_t` is laid out `{g, r, b}`, and
`set_led_color_rgb()` (`platforms/chibios/drivers/ws2812_spi.c`) serialises the
channels `g, r, b`. **The two swaps cancel:** `rgb_matrix_set_color_all(r,g,b)`
stores `{g,r,b}` in memory, then the serializer reads those fields back in `g,r,b`
slots — so the bytes on the wire are source `[G,R,B]`, i.e. pure pass-through.

Amber is `(255, 96, 0)`. On the wire that became `96, 255, 0` — which **an
RGB-ordered panel reads as (R=96, G=255, B=0)**: a fully saturated yellow-green
the eye calls green. The fault hit **every** colour, not just the boot code
(ambient white only looked right because R=G=B).

**This corrects the earlier text in this section**, which listed "WS2812
bit-timing at `WS2812_SPI_DIVISOR 32`" as a candidate. Timing governs pulse
*widths* (`WS2812_TIMING`/`T1H`/`T0H`/`TRST_US`) and **cannot permute byte
order**; the divisor only sets the SPI clock. The panel-order candidate was the
right one.

**Fix:** `#define WS2812_BYTE_ORDER WS2812_BYTE_ORDER_RGB` in the board
`config.h`. It is board-local (our panel's fact, not upstream's), and it is not
a change to the colour constants — the constants were always correct.

**Status: CONFIRMED ON HARDWARE 2026-10-14.** Built (`633d5886…`, 64,736 B; then
`aec73138…`, 64,600 B, which carries this fix plus the requirement-2 transport
reform) and flashed. **The boot code now renders amber.** The one look was the
falsifier, and it passed: the fault was the byte order, and the panel is
RGB-ordered. Every colour on the board was affected before this fix, not just the
boot code.

**It does not affect the reading.** Colour only groups the code
(category = amber, value = white); **the pulse count carries the message**, so
the boot code is legible regardless.

## Raw HID interfaces

- Usage page `0xFF60`, usage `0x61`, `RAW_EPSIZE` = **32 bytes** in both
  directions, on all transports.
- **A raw HID write through hidapi must be 33 bytes**: a leading Report ID `0x00`
  followed by the 32-byte report. The descriptor declares **no report IDs**, but
  hidapi still requires the leading byte. A bare 32-byte write is silently
  accepted and never answered.
- Each half exposes three interfaces; the raw collection is **interface 1** on a
  half. The dongle's raw collection is **interface 2** — now **verified on
  hardware (2026-10-09)**: with the dongle attached the composite is three
  interfaces and the `0xFF60`/`0x61` collection lands on interface 2
  (`/dev/hidraw5`). With both attached, selecting by usage page alone picks the
  wrong one.

## Split-link power

- **The two halves do not have the same ports.** The **left half has two**
  (a host USB-C port and the link port); the **right half has one**, which is the
  link port. A cable into the right half therefore connects right-to-left, not
  right-to-host.
- **The inter-half link carries power, one way: left to right.** The master
  (left) is the only half that can source power, because it is the only half with
  a path to a supply. The link feeds the right half.
- **A single cable powers the whole keyboard only through the left half's host
  port.** Plugging the left half into a host both powers the left half and, over
  the link, the right half. There is no configuration in which a lone right half
  is powered: its only port is the link port, and a link alone sources nothing.
  A lone right half showing no signs of life is therefore **expected**, not a
  fault — that half is masterless and unsupplied.
- Consequence: `charging_state` (A7) is a shared "power present" bit, not a
  per-half cable-detection bit — it reads true on the left half whenever the left
  half is powered or charging, whether or not that half's own cable is attached.
- **Superseded, recorded because it is wrong:** an earlier revision of this file
  claimed "a single USB-C cable into *either* half charges the whole keyboard",
  inferred from the master's `charging_state` reading true without a cable in the
  master's own port. That inference over-extended one observation and is
  physically impossible given the right half's single link-only port: a link
  cable cannot carry a supply into a half that has no supply of its own.

## Batteries

- **Only one half carries a battery.** Observed directly with the right half's
  backplate removed: the **right half has no battery**. The battery is therefore
  in the **left half** (the half that is currently master). This supersedes the
  earlier firmware-inferred guess that both halves had cells.
- **Quirk, not a defect: the firmware models per-half charge state that the
  right half cannot have.** Both halves run identical firmware, so the right
  half still reads a local `BAT_FULL_PIN` (A15) and keeps a `bat_full_flag`
  whose value is meaningless on a battery-less half. This is harmless: every
  consumer is either master-gated (`bat_indicators()` returns early when not
  master) or link-powered, and the `0xA4` report carries only the master's own
  module value, so no phantom value can reach a host. Do **not** add a
  right-half special case — the guard would be dead code over a value nothing
  reads.
- **Open:** whether the right half has any charging circuitry at all, or is
  purely bus/link powered. Record it when known.
- **The inter-half link carries power, left to right only** (`## Split-link power`
  below): a cable into the **left** half's host port reaches both PCBs. That is a
  power distribution fact, not evidence of two cells.
- **Reporting is the battery half's level.** The master (currently the left /
  battery-bearing half) answers `0xA4` with its own module's value. One battery,
  one reported number; there is no second cell whose level could differ.

## Charging and battery sensing

- There is **no ADC and no charge-controller telemetry**. The firmware cannot
  measure voltage, current, or charge; it reads two GPIO bits only.
- `HS_BAT_CABLE_PIN` = A7 = "USB insertion detection pin" (power present).
- `BAT_FULL_PIN` = A15, active-high (`BAT_FULL_STATE 1`) = the FULL line.
- The keyboard cannot measure its own charge; the level only ever arrives from
  the wireless module over the module UART (`MD_REV_CMD_BATVOL` `0x5C`).
- On USB the module does not answer the level inquiry, so `md_info.bat` keeps its
  compile-time init of `100` (see `TODO.md` defect 1).

## The wireless module (public information)

The radio side of this board is **not an Epomaker invention**. The module UART
protocol the vendor stack speaks is the **WCH CH582F** tri-mode keyboard protocol
(Nanjing Qinheng), and the host side of it is a widely shared body of firmware.
This is now documented publicly, so it is *objective* hardware knowledge, not
inference — it can be cited instead of re-derived.

- **The chip.** `CH582F` — a BLE 5.0 / 2.4 GHz SoC from WCH. In a tri-mode
  keyboard it owns Bluetooth and 2.4 GHz RF while the main MCU (our WB32FQ95)
  owns the matrix, RGB and USB HID. The vendor implements only the host side of
  the UART protocol; the module's own product image is WCH's, but the **stack it
  is built on is not opaque** — see "The BLE stack is a symbolized library, not a
  blob" below.
- **The protocol is shared across manufacturers.** The reference doc states it is
  used by "GMMK, Akko, MonsGeek, Neo, Shortcut Studio, and others" — i.e. this is
  a common Chinese-OEM module stack, not a per-board secret.
- **Our firmware is byte-identical to the documented protocol.** Verified against
  `keyboards/linker/wireless/module.h`: command bytes `0xA1` (KB) / `0xA2` (NKRO)
  / `0xA3` (consumer) / `0xA4` (system) / `0xA8` (mouse), `0xA6` device-control
  with sub-commands `0x11` (USB) / `0x30` (2.4G) / `0x31..0x35` (BT1–BT5) /
  `0x51` (pair) / `0x52` (unpair) / `0x53` (query battery), replies `0x5A`
  (indicator) / `0x5B` (device-control status) / `0x5C` (battery percent), the
  8-bit additive checksum, the `0x61 0x0D 0x0A` ACK, and the 3000 ms battery poll
  (`WLS_INQUIRY_BAT_TIME`) all match.
- **The state machine is documented.** `MD_STATE_NONE/PAIRING/CONNECTED/
  DISCONNECTED/REJECT`, driven by `0x5B` sub-codes `0x31` pairing / `0x32`
  connected / `0x33` disconnected / `0x36` rejected. HID reports are only
  transmitted in `MD_STATE_CONNECTED`; a report sent in any other state triggers a
  reconnection attempt. (This is what the `wls_bluetooth.c` link-up gate assumes.)
- **Battery semantics are documented.** The host polls (`0xA6 0x53`) and the
  module answers `0x5C <percent>`. Some firmwares also emit unsolicited `0x5B`
  threshold sub-codes (`0x21` very-low, `0x22` first-read, `0x23` normal) — a
  candidate explanation for a stale/placeholder reading that only needs handling,
  not decoding, on the `0x5C` path.
- **Sleep/wake opcodes are documented.** `0x55`/`0x56` (BT sleep-timeout
  enable/disable), `0x57`/`0x58` (2.4G), `0x60 0x00`/`0x01` (host
  suspend/resume) — matching the vendor `lowpower` design.
- **The MAC is fixed per chip** (from WCH's factory UUID; no UART command sets
  it). The host can only set the BLE name (`0xA9`), the dongle manufacturer /
  product strings (`0xAB`/`0xAC`) and the dongle VID/PID (`0xAD`).

Reference: `emolitor/WestberryTech-WB32`, `docs/wireless/ch582f-protocol.md`.

### Sibling-board pinout (cross-check, not our netlist)

An independent reverse-engineering of a **different** WB32FQ95 board
(`ozboar/zoom65v3-re`) published a concrete pin map. It is a useful cross-check
for our own pin facts, but it is **not** the Split65 netlist — treat it as a
sibling, and keep our own pin facts sourced from our board files.

- Wireless module UART: `A9` TX / `A10` RX (sibling).
- USB cable detection: `B9` (high when plugged).
- Battery-level signal: `B8` (low charging, high full).
- USB data enable: `A14`.
- On/off switch: `C1` (`BT-2.4G IO`, high = wireless).
- LED rails: `B7` (`LED-V`), `B12` (`LED-V1`).
- Ribbon/one-key column + encoder: `C10`/`C11` (UART3 RX/TX), `C14`/`C13`.

**Important divergence — do not copy the sibling's module-UART pins.** The
sibling runs the module over `A9`/`A10` (UART1). **Our Split65 runs the module
over `C10`/`C11` (UART3, `SD3`) and the *split link* over `A9`/`A10` (UART1,
`SD1`)** — see `config.h` (`UART_DRIVER SD3` / `UART_TX_PIN C10` vs
`SERIAL_USART_DRIVER SD1` / `SERIAL_USART_TX_PIN A9`). This is exactly the
collision the board-local comments warn about: reusing the sibling's pin map
would put the module on the same UART as the split link (symptom: master types,
slave does not). The sibling's value is the *shape* of the map (which classes of
pin a WB32 tri-mode board uses) and confirmation of the cable/battery/LED
pin roles, not the literal module-UART assignment.

**Module-side UART (CH582F QFN28 pinout, from the WCH datasheet).** On the
CH582F side, `UART1` is `PA8`/`PA9` (RXD1/TXD1) and `UART3` is `PA4`/`PA5`
(RXD3/TXD3); the WCH EVT firmware's default console is UART1 (`PA8`/`PA9`). So
the module exposes several UARTs, and a board may pick any of them — which is
why the sibling and the Split65 can both talk the same protocol over different
MCU pins.

### The BLE stack is a symbolized library, not a blob

Earlier records called the module BLE stack a "binary blob" and treated it as
unreadable. That was **too strong**. WCH's own SDK (`openwch/ch583`, `EVT v2.4`)
ships the stack as `EVT/EXAM/BLE/LIB/LIBCH58xBLE.a` — a genuine `ar` archive of
**67 separate object files**, one per subsystem, compiling the whole link layer
and host stack:

- Link layer: `ll.o`, `ll_advertise.o`, `ll_connect.o`, `ll_core.o`, `ll_scan.o`,
  `ll_slave.o`, `ll_master.o`, `ll_pdu.o`, `ll_hop.o`, `ll_whitelist.o`,
  `ll_resolvinglist.o`, `ll_periodic .o`, `ll_sync.o`.
- Controller/radio: `bb.o` (baseband), `lle.o` (link-layer engine), `rf_fh.o`
  (frequency hopping), `rfend.o`, `ip.o`, `aes.o`, `aes_soft.o`.
- Host stack: `hci*.o` (HCI + SLIP + UART transport), `l2cap*.o`, `att*.o`,
  `gatt*.o`, `gap*.o`, `gap_central/peripheral.o`, `gapbondmgr.o`, `sm*.o`
  (security manager), `linkdb.o`, `role.o`, `api_c.o`, `ctl_input/output.o`.
- Scheduler: `tmos*.o` (TMOS task/event kernel), `memory.o`, `message.o`.

**It is unstripped and disassemblable.** It exports **10,410 named global
functions** — `LL_Init`, `LL_AdvertiseEnalbe`, `HCI_LE_CreateConnCmd`,
`API_LE_SetAdvParamCmd`, `GAP_EstablishLinkReq`, `SM_StartPairing`, … — and
carries the original per-object source filenames (`gap.c`, `ll_advertise.c`,
`tmos.c`). Compiled by `xPack GNU RISC-V Embedded GCC 8.2.0` (`.comment`), with
no DWARF (`-g` off), so function *bodies* are readable but line numbers are not.

Disassembly works today with tools already installed: `llvm-objdump -d` decodes
it cleanly (RISC-V RV32IMAC + C extension). GNU `objdump` reports "architecture
UNKNOWN" only because binutils tags the file `riscv32` while WCH emits the
`riscv32imac_zicsr` arch tag — reading the ELF header shows `Machine: RISC-V`,
`Flags: 0x1, RVC, soft-float ABI`.

The remaining genuinely-proprietary piece is:
- the module's **shipped factory product image** (the `.hex` flashed onto the
  CH582F in the keyboard) — no vendor publishes its own customer firmware.

**Public firmware artifacts that DO exist (2026-10-09).** Two distinct classes
were found, and neither is a CH582F module image:

1. **The main-MCU (WB32) factory firmware is public.** `carlosedp/qmk_firmware`
   release `0.31.2` ("Factory Firmware files") ships
   `EPOMAKER_Split65_via_v10_factory.zip` → a single `EPOMAKER_Split65_via_v10.hex`
   (sha256 `ee9bb455…308a`), covering `0x08000000..0x080123C4` (74,692 bytes).
   Verified **WB32/ARM, not CH582F**: Intel-hex base records `0x0800`/`0x0801`,
   vector table SP `0x20000400`, reset `0x080001B9` (Cortex-M Thumb). It is the
   *main MCU* application — the same thing we flash, not the module.
   - It is **a closed/older build, not the public vendor source**: it embeds
     strings absent from both our tree and the vendor-overlay source —
     `0bts lib version: v2.8.2` and `module ver: %d` (grep of the source finds
     neither). So the factory WB32 firmware was built from an unpublished codebase
     and is not byte-comparable to `hangshengkeji/qmk_firmware`.
   - The other EPOMAKER "factory" zips in the same release (TH40, Split70,
     Galaxy100-lite) are **also single `0x08000000` WB32 images** — EPOMAKER's
     packaging never bundles a CH582F module image.
2. **The CH582F *stack archive* is public, the *application* is closed — but
   open CH582 keyboard projects now expose the failing layer as source.**
   - Independent CH582-family QMK ports confirm the module app cannot be rebuilt
     wholesale: `O-H-M2/qmk_port_ch582` (and its `rgoulter` write-up) state plainly
     that *"Enabling BLE requires the wireless lib, but … the required files aren't
     provided in the repo. Hence, BLE isn't available with the publicly provided
     code"* — wireless is marked 暂不开放 ("not yet opened") on the `via` branch.
   - **However**, sibling *open* tri-mode keyboard projects publish the whole CH582
     application, including the exact layer that fails for us. `ChnMasterOG/tp78_v2`
     (active, releases to v2.1.17, 2026-09) ships, in-tree:
     - `Profile/hidkbmservice.c` (940 lines) + `Profile/hiddev.c` (1214) +
       `Profile/battservice.c` (599) — the **HID-over-GATT server, device
       information service, and battery service, in full C source**, including the
       CCC-descriptor table (`hidAttrTbl[…CCCD_IDX]`, `hidRptMap[].cccdHandle`).
     - `LIB/LIBCH58xBLE.a` + `CH58xBLE_ROM{,x}.hex` — the same WCH stack class we
       already hold (here sha1 `3e7a0b7e…`; **not** the same build as our
       `/tmp/opencode/ch583` copy, sha1 `f9b488a9…`), plus `APP/` application source.
     - A `firmware/DefaultFS.BIN` DataFlash image and full `obj/` build output.
   - So the **HID GATT/profile layer** — the part returning ATT `0x0E` on our unit —
     is **readable as ordinary source** in a sibling CH582 project, not merely
     disassemblable. It is the *generic WCH/WCH-derived profile* (a different vendor
     than `0bts`), so it is a reference implementation, not a drop-in replacement.
   - `c3h4o` (oshwhub 丐PAD) and `bluetooth-keyboard-squad` (oshwhub) likewise
     publish complete keyboard+receiver **`.hex` images** for their own CH582
     boards — proof that a full CH582 keyboard image is distributable; ours simply
     is not published by EPOMAKER.
   - The module's *own* application image (the `0bts` build) remains unavailable:
     no EPOMAKER, WCH, or leaked copy. Its version string `0bts lib version: v2.8.2`
     is the only public fingerprint, and it appears **only inside the WB32 factory
     firmware** (the WB32 side links the "0bts" host protocol library), not in any
     CH582 image.

So: the module's own firmware image is **not** publicly available (no EPOMAKER, WCH, or
leaked image), the SDK's stack archive is readable but is not the app, and the one
public EPOMAKER firmware artifact is the WB32 side we already control. Reflashing
a *fixed* module image is therefore not a route we can take; the module is only
reachable over UART/ISP (WCH tooling) if a vendor image were ever obtained.

**Can we dump or update the module's firmware? (2026-10-09, researched).** Three
facts settle it, and all three are adverse:

1. **The keyboard's own UART cannot do it.** The CH582F UART command set
   (`module.h`) has **no** firmware-update, bootloader-entry, or flash command —
   it is HID reports and device control only. The WB32 side has no protocol path
   to the module's flash.
2. **ISP entry is the only route, and it is not a keyboard-accessible one.**
   The CH582/CH583 ISP bootloader is reached over **USB or UART** with WCH tooling
   (`wchisp`, `WCHISPTool`). Critically, per WCH's own documentation: *"ISP
   bootloader entry cannot be controlled via external pin state at reset; instead
   the user application code must instruct the device to enter the bootloader via
   setting `FLASH_STATR.MODE` and performing a software reset."* On this keyboard
   the module is a soldered sub-board with no exposed BOOT button and no USB; the
   only external UART is the host link, and the module's app does not offer ISP
   entry. Reaching ISP would mean probing the module's own pins (its `PB22`
   download pin / its boot USB) directly.
3. **Even if ISP were reached, a readable dump is very likely blocked and a
   reflash unhelpful.** The CH582 read-protect bit `CFG_ROM_READ` (`USER_CFG[7]`)
   gates code dump; the WeAct CH582F reference and the FOSSASIA badge both ship
   with it **0 ("disable the programmer to read out, and keep the program
   secret")** — the default a vendor module is expected to keep. A dump is only
   possible if it is 1. And even with a dump, the CH582 code flash is
   **hardware-scrambled** (reads are not plaintext) and multiple vendors
   (`bluetooth-keyboard-squad`) additionally **encrypt their images against the
   chip UID with the key stored in DataFlash** — so an image from another unit is
   not directly reusable. WCH also publishes no fixed module image, and the
   defective layer is in the closed app, not the public stack archive, so nothing
   to reflash *to* exists.

Net: **no, we cannot dump or update this module's firmware** without physical
access to the module's own ISP pins, and even then only if `CFG_ROM_READ` happens
to be enabled on our unit — a dump would still be scrambled/possibly UID-encrypted,
and there is no fixed image to write. This is why the BT fault is recorded as a
bounded Layer-0 unknown rather than a fixable defect.

The `CH58xBLE_ROM.hex` / `CH58xBLE_ROMx.hex` files are **not** a chip mask ROM.
Despite the name, the CH582/583 has **no BLE stack in silicon ROM**; "ROM" here
means "the protocol stack compiled separately, flashed to a fixed Flash region and
called through a jump table":

- `CH58xBLE_ROM.h` defines `FUNCITON_BASE_ADDRESSS = LIB_FLASH_BASE_ADDRESSS+0x34`
  and `#define BLE_LIB_JT(n) (*(uint32_t*)(FUNCITON_BASE_ADDRESSS+n*4))` — the API
  is a **flash-resident jump table** at a fixed address, with a `VER_LIB` version
  word at the head (`BLE_LIB_JT(0)`, base+0x08 UUIDs, base+0x34 function table).
- The `_ROMx` variant differs **only in load address** (`0x10000` vs `0x40000`);
  three files exist (`_ROM` / `_ROMx` / `_ROM_MESH`) differing solely in
  `LIB_FLASH_BASE_ADDRESSS`. A mask ROM could not be relocatable.
- The CH583 datasheet's CodeFlash map (`0x00000000-0x0006FFFF` app, `0x00078000`
  BootLoader, `0x0007E000` InfoFlash) has **no ROM region**; the "ROM" image
  occupies user CodeFlash. The `CFG_ROM_READ` InfoFlash bit is a *FlashROM*
  read-protect flag, not a mask-ROM concept.
- WCH's own forum answer: 这个 hex 文件是协议栈单独编译生成的文件 — the protocol
  stack compiled as a standalone file, so the app stays ~10 KB and several
  firmwares share one stack.

So it is **not a hidden artifact**: WCH publishes it as a first-class download
(`wch.cn` EVT package, `EVT/EXAM/BLE/LIB/`; there is also a separate
`WCHBleLib_MultiOS.ZIP` distribution) and it is mirrored in `openwch/ch583` on
GitHub — the same place `LIBCH58xBLE.a` came from. Local dumps already taken:

```
CH58xBLE_ROM.hex  -> CH58xBLE_ROM.bin   180115 bytes  md5 c34e6ddb790199bfeb975a9f09a8b078  base 0x10000
CH58xBLE_ROMx.hex -> CH58xBLE_ROMx.bin  180115 bytes  md5 df9367c2f532497004fed7bc18bc45ef  base 0x40000
# objcopy -I ihex -O binary CH58xBLE_ROM.hex CH58xBLE_ROM.bin
```

`CH58xBLE_ROM.bin` is the **linked form** of the same stack the `.a` archive
builds — a flat 180 KB RISC-V image. It disassembles with
`llvm-objdump -b binary -m riscv` (symbols resolved by matching jump-table offsets
against `CH58xBLE_ROM.h`). This is the artifact the vendor most plausibly actually
flashed, so it is the best single target for fingerprinting the SDK revision the
module corresponds to.

Neither the ROM image nor the archive is needed to read *how the stack behaves*,
because the SDK's app layer is **full C source**: every profile and example
(`HID_Keyboard`, `HID_Consumer`, `BLE_UART`, `BLE_USB`, OTA, `Central`/`Peripheral`,
…) is present as `.c` files.

**Why this matters — reverse engineering is a real avenue here, not a dead end.**
The vendor stack is what our board actually talks to, and we own only the *host*
side of the UART protocol. Three things the disassemblable library can settle
that the protocol doc and our hardware cannot:

1. **Close the `0x5B`/`0x5C` semantics gap from the source of truth.** Our
   `wls_bluetooth.c` link-up gate assumes `0x5B 0x32` (connected) ⇔ *module*
   `GAP` link established. The module emits that byte from its own GAP/LL event
   handling; disassembling `gap.o`/`ll_connect.o` (and matching against the
   open `HID_Keyboard` example's `GAP_LINK_ESTABLISHED_EVENT` handling) shows
   exactly which internal event produces each sub-code, turning an inference into
   a traced fact. The same applies to the `0x21`/`0x22`/`0x23` battery-threshold
   sub-codes that could explain our stale/placeholder reading (defect 1).
2. **Explain behavior with no hardware access.** The 2.4 GHz dongle does not
   enumerate here and no second machine is available; the module's MAC is fixed
   per chip and the pairing/sleep decisions (`0x51` pair, `0x54` sleep, `0x55`/
   `0x56`/`0x57`/`0x58` timeouts) are made *inside* this library. Reading the
   pairing state machine and the TMOS sleep path is the only way to reason about
   them without a second device or a probe on the module UART.
3. **Validate our assumptions against the vendor image's provenance.** If a
   factory image for a sibling board ever surfaces, matching its code against
   `LIBCH58xBLE.a` object-by-object identifies the exact SDK version the ODM
   built from — bounding how much of the protocol doc actually applies to our
   module's revision.

**SDK-revision fingerprints to capture from hardware.** Our own stack already
branches on the module's reported firmware version: `module.c` `md_devs_change()`
gates Unicode descriptor handling on `md_get_version() < 48` ("Add Unicode
character support starting from v48"), reading the version from the `0x5D`
(`MD_REV_CMD_MD_FW_VERSION`) reply. So the first hardware read of `0x5D` is
directly interpretable, and the fingerprints below turn that byte into an SDK
identity:

| Fingerprint | Value | Where |
| --- | --- | --- |
| compiler | `xPack GNU RISC-V Embedded GCC 8.2.0` | `LIBCH58xBLE.a` `.comment` |
| ROM image (load base `0x10000`) | 180115 B, md5 `c34e6ddb790199bfeb975a9f09a8b078` | `CH58xBLE_ROM.bin` |
| ROMx image (load base `0x40000`) | 180115 B, md5 `df9367c2f532497004fed7bc18bc45ef` | `CH58xBLE_ROMx.bin` |
| version word | `VER_LIB = BLE_LIB_JT(0)` at `LIB_FLASH_BASE_ADDRESSS+0x34` | `CH58xBLE_ROM.h` |
| SDK revision host-gate already in-tree | `v48` (Unicode names) | `keyboards/linker/wireless/module.c` |

The `0x5D` byte read over hardware maps to a known SDK build via these, which is
what bounds the protocol doc's applicability (item 3).

Tooling is already sufficient: `llvm-objdump` for disassembly, `nm`/`readelf` for
symbols, and the open `ArcaneNibble/project-nanjing` (WCH BLE RE), `ch58x-hal`
(Rust HAL), and `fossasia/badgemagic-firmware` (CH582 pinout RE) projects as
prior art. Nothing here needs the SWD pads this board hides.

Reference artifact: `openwch/ch583` `EVT/EXAM/BLE/LIB/LIBCH58xBLE.a`.

### The ODM and its public sibling boards

The board's likely origin is **MATHEW TECHNOLOGY LIMITED** (`mathewkb.com`,
Shenzhen), an ODM that publishes raw QMK firmware source archives (`.7z`) for its
product family. Its own brand **ZUOYA** ships the same vendor stack: the **GMK70**
is a sibling of our Split65 — same **VID `0x342D`**, same `manufacturer: "LEO"`,
same vendor VIA-JSON generator (`BT DEV1..5 / 2.4G / USB`), and a board source
that is `upstream/tri-mode`'s `epomaker_split65` source with board-local edits.
The GMK family (`61/70/81/87/104`) and the `MK*`/`MT*`/`NK*`/`HW*` lines are the
same platform at different key counts.

**Caveat — this is circumstantial, not a proven OEM→Split65 link.** `mathewkb.com`
self-identifies as MATHEW and tags its pages `oem-odm`, but no archive, page, or
string ties it to Epomaker or to the Split65 by name; the shared-ancestor source
snapshot proves *one hand wrote both trees*, and MATHEW is the strongest candidate
for that hand — a distributor/reseller reading the same upstream is not excluded.
The negative result (no 65% split in the library) fits either story. Closing it
needs the dongle descriptors, module ODM string, PCB silkscreen, or a vendor
reply. See `docs/FINDINGS.md` for the full reasoning. Schematics and PCB files are
still unpublished; the archives are firmware source only.

### Certification filings — the one public hardware artifact

The board is a **radio device, so it is certified**. Two filing bodies publish
documents that carry real hardware evidence, and both name the **manufacturer**
(the OEM/ODM factory), which the retail branding does not.

- **FCC (US) — FCC ID `2A5D2-RT100-010`.** Grantee `2A5D2` = **SHENZHEN CHANGYUN
  TECH CO., LTD** (the manufacturer; contact `Peter Wang, Certification Engineer`).
  Grant **2024-12-13**, test firm Shenzhen CCUT Quality Technology, report
  `SSP24100235-1E`, sample `Hardware Version V0.2 / Software Version V108`. The
  cert covers the **RT100 as the "main model" with the Split65 added by a *Model
  Difference Statement***: `... Hack 59, Alice 66, **Split 65**` — "the circuit and
  the electronic construction are the same, declared by the manufacturer." So the
  Split65 is certified **by family declaration**, not photographed in its own right.
  Documents live at `fccid.io/2A5D2-RT100-010` (and mirrors `fcc.id`,
  `fccid.ai`, `fcc.report`). The **Internal Photos** annex
  (`/Internal-Photos/Internal-Photos-7897160.pdf`, 5 pages) is a teardown of the
  RT100 sample: it shows the **wireless daughter module with an on-board PCB
  antenna** (silkscreen `PCB ANT`) over the main matrix PCB, plus the battery
  pouch cell (`5565114 5000mAh 3.7V 18.5Wh` — the RT100's 5000 mAh, not the
  retail 3000 mAh). The **Antenna Report** confirms the 2.4 GHz PCB antenna.
  Note the confidentiality flag: `Long-Term Confidentiality: Yes`, so the block
  diagram / schematic, if it exists, is withheld.
- **CE / EU — the manufacturer is named explicitly.** The retail conformity
  annex (Epomaker EU packaging / `manuals.plus`) gives: `Made in China;
  Manufacturer: **Shenzhen Changyun Technology Co., Ltd.**; Address: Seventh Floor,
  Kai Daer Building, No.168 Tongsha Road, Xili Street, Nanshan District, Shenzhen,
  Guangdong, CN; Email: support@epomaker.com`. **`Shenzhen Changyun Technology
  Co., Ltd.` is the same entity as the FCC grantee `SHENZHEN CHANGYUN TECH CO.,
  LTD`** — the same address cluster (`Kai Daer Building 2, No.168 Tongsha Road`).
  The EU responsible party is a CE representative (`CE SPECIALISTS GMBH` /
  `APEX CE SPECIALISTS LIMITED`).
- **Japan — TELEC (技適).** The retail box prints the 技適 mark and Epomaker's JP
  site claims TELEC/無線 certification; Japanese reviews note the mark is on the
  **box, not the keyboard**, and question whether certification was actually held
  at launch. TELEC certification bodies (e.g. Telecom Engineering Center) do
  publish grant numbers, but no Split65 TELEC grant number was found.
- **Korea (KC) / UKCA / other** were not separately located.

**What certification gives us that no firmware source can:** the *manufacturer
identity* (`Shenzhen Changyun Technology Co., Ltd.`), and a **teardown-level photo
of the module architecture** (wireless daughterboard + PCB antenna + main matrix
PCB). What it does **not** give: the netlist/schematic (FCC holds schematics as
`Long-Term Confidential`), or the Split65's *own* board photos.

### What is deliberately *not* public

- **No Split65 schematic exists on the open internet** (searched in English,
  Japanese, and Chinese). The `Epomaker` GitHub account has 33 public repos and
  **every one is QMK firmware**, not hardware; there is no schematic, PCB, or
  netlist repo. The board-specific netlist remains unavailable — but the board
  is not entirely absent from the public record: the FCC grant `2A5D2-RT100-010`
  and the EU CE annex both exist (see "Certification filings" above), a
  same-family board's **pin map** is published (`ozboar/zoom65v3-re`), and
  third-party CH582F tri-mode keyboard **schematics** are public (see the list
  below). None of them is *this* board's netlist.
- The WB32 **reference-board** schematic (a dev board, not this keyboard) and the
  **WCH module** vendor docs are public; the Split65 board wiring is not.
- **Schematics for *related* boards do exist publicly** — just not for the
  Split65. What is findable, and what each is good for:
  - **`ozboar/zoom65v3-re`** — a WB32FQ95 keyboard (Meletrix Zoom65 v3,
    `HFD22001A` = rebadged WB32FQ95). Publishes a full reverse-engineered
    **pin map** (matrix rows/cols, ribbon pinout, module-UART / cable / battery /
    LED / power-enable pins) — *not* a KiCad netlist, but a concrete wiring map
    for a same-family board. This is the closest published analogue to a Split65
    netlist and the reason the "sibling pinout" section above exists.
  - **`emolitor/WestberryTech-WB32`** — the WB32 **reference-board** schematic
    (`vendor-docs/schematics/Schematic_wb32f10x_48pin_Mini_v1.1.pdf`, a bare
    48-pin dev board: USB, power, SWD, headers) plus the full datasheet/reference
    manual and the **CH582F module protocol reference**. Good for chip-level
    facts, not board wiring.
  - **Chinese open-hardware (`oshwhub.com`)** — third-party CH582F *tri-mode
    keyboard* projects with published schematics: a wired→BT converter module
    ("HH90"), several CH582M 3-mode pads / 61-key boards, and a CH582F **2.4 GHz
    receiver** design. These are *different* boards (different matrix, different
    MCU-side pins) but they document the **same WCH CH582F module architecture** —
    i.e. how a keyboard-side MCU + CH582F + battery/charge/boost LDO + antenna
    is actually wired. `oshwhub.com` blocks direct fetch (HTTP 418) but the
    project descriptions and attachments are reachable via search.
  - **Neither the Split65 nor any 65% *split* appears in any of these.** The
    family trees are single-board (or 2.4 G-only) and the split variant is never
    published. See `docs/FINDINGS.md` for the lineage.
  - **WCH's own `CH583EVT.ZIP` / `SCHPCB.ZIP`** (the module vendor's official
    evaluation-board schematic/PCB) are **not freely downloadable** — the
    download pages say "contact sales". The BLE *stack*, however, is not the
    blocker it was once recorded as — see below.

#### Where the schematic was looked for, and why each channel came up empty

A deliberate "possibility-eliminating" sweep, so a later agent does not repeat
it. The OEM is **Shenzhen-based** (`© EPOMAKER · Shenzhen, China`) and publishes
**only firmware, VIA JSON, drivers and manuals** — no hardware.

| Channel | Result |
| --- | --- |
| `github.com/Epomaker` (33 repos) | all QMK firmware; no HW repo |
| OEM downloads (`/blogs/firmware`, `/blogs/software`, `/blogs/via-json`, `/blogs/manuals`) | firmware/HEX/ZIP, drivers, PDFs only |
| `hub.epomaker.com` | web configurator, no docs |
| ODM `hangshengkeji/qmk_firmware#tri-mode` | the firmware tree only (`linker/wireless/`) |
| `WestberryTech/qmk_westberry#tri-mode` | vendor firmware fork only |
| Chinese open-hardware `oshwhub.com` search "split65" | **0 projects** |
| `gitee.com` search "split65" | **no relevant repos** |
| Forums / group buys (`zfrontier.com`) | a *different* 2.4 G-only "Split65" kit by Block boy studio — not this board |
| Community RE (`ozboar/zoom65v3-re`, `zolw.) | **hit (partial)** — sibling WB32FQ95 board **pin map** (matrix/ribbon/MCU pins), not a netlist |
| WB32 reference board (`emolitor/WestberryTech-WB32`) | dev-board schematic + datasheet/RM + CH582F module protocol; chip-level, not board wiring |
| Chinese open-hardware `oshwhub.com` (CH582F tri-mode KBs) | **hit** — third-party CH582F keyboard / 2.4 GHz-receiver **schematics** (different boards, same module architecture); direct fetch blocked (HTTP 418) |
| WCH vendor `CH583EVT.ZIP` / `SCHPCB.ZIP` | not freely downloadable ("contact sales"); the BLE stack, however, is a symbolized library, and its `CH58xBLE_ROM*.hex` "ROM" image is a normal public download (not mask ROM) |
| Chinese vendor portals (eefocus, sekorm) | the **WCH CH582 reference *solution*** (a different chip-on-board design, not our module board) |
| **FCC (`fccid.io` / `fcc.id` / `fcc.report`)** | **hit** — grant `2A5D2-RT100-010` (Split65 as a series model under RT100); internal teardown photos + antenna report; **no schematic** (confidential) |
| **EU CE conformity annex (retail packaging / `manuals.plus`)** | **hit** — names the manufacturer `Shenzhen Changyun Technology Co., Ltd.` and the CE rep; no schematic |
| **Japan TELEC 技適 (Telecom Engineering Center)** | box mark + Epomaker JP claim; **no grant number found** |
| Korea KC, UKCA | not separately located |

The pattern: this is a **white-label ODMed board** assembled from a WCH module
reference design plus a vendor QMK tree. The schematic never leaves the ODM's
internal tooling, and the OEM distributes firmware only — so the "accidentally
left on a public web server" hypothesis did not bear out for the **schematic**,
though **certification filings did** put the manufacturer's name and a family
teardown into the public record.

## Halves and handedness

- Both halves run **identical firmware**; there is no left/right build variant.
  Handedness is a physical pin (`split.handedness.pin` = B9). **B9 is USB cable
  detection** — "high when plugged" (see the sibling-board pin map above, which
  is the only place this pin's physical meaning is recorded). QMK **core** derives
  the master from the USB role (`usb_bus_detected()`), but each **keymap**
  overrides `is_keyboard_master()` to `gpio_read_pin(SPLIT_HAND_PIN)` — so on this firmware the
  pin determines the role too, and the two questions coincide: **the half with the
  host cable is the master**, which is the only half that can be, since only the
  left half has a host port at all. Removing that override would restore the core
  USB-role semantics.
- The **left half is currently the master** and the **right half the slave**,
  joined by the link cable. Role is pin-determined, not positional; see
  `DEVICE.md` "Nomenclature".
- Only the master answers the battery raw HID command; a pull addressed to the
  slave never gets a reply.

## DFU entry

- **LEFT half — use the spacebar-hole short, not Esc-hold.** Esc-hold bootmagic
  works on stock firmware but is **broken on any non-OEM build** (a reported
  failure, not one we introduced — see `TODO.md`, defect 2 area, and
  `FINDINGS.md`). The left half has **no reset switch** — that earlier claim was
  unverified and wrong. The real route is the spacebar-hole short: remove the
  spacebar, **short the two metal-plated holes** the spacebar switch's feet sit
  in, and plug in USB-C **while still shorting**. Every key has such holes; only
  the spacebar's are metal-plated, which is how you tell them apart.
- **RIGHT half — needs the toggle, but no case opening.** The case never needs
  to be opened to flash either half. Esc-hold does **not** work on the right
  half, and there is no keymap route into its own bootloader (the `nathan`
  Fn-layer `QK_BOOT` is on the Fn layer; the WB32 bootloader samples the boot pin
  only at reset, so a warm keypress may not enumerate). The right half has a
  hidden **toggle switch** — found by removing the `R_Shift` **keycap** (not the
  case), it is exposed underneath. **Toggle it DOWN (toward the bottom) to arm
  DFU**, then remove the spacebar, short the two metal-plated holes the spacebar
  switch's feet sit in, and plug in USB-C **while still shorting**. **Toggle it
  back UP afterwards.** (Direction from the ODM's own maintainer reply in
  `Epomaker/Split65` issue #2, 2025-04-29: "Switch it to the bottom … make sure
  the switch is toggled back to the top".)
- **Cold-plug rule (both halves):** the reset and the enumeration window must
  coincide. Short first, plug second, hold the short until enumeration completes;
  bridging an already-powered board does nothing. If the device does not appear as
  `342d:dfa0`, unplug and replug it.
- A marginal cable or port shows up as an EPROTO (`-71`) storm in the kernel log
  (`device descriptor read/64, error -71`), not as a clean failure. Retry on a
  different port/cable.

## Sleep and wake

- **Not yet verified on hardware.** The current tree arms the right (slave) half's
  own rows (`MATRIX_ROW_PINS_RIGHT` in the board-local `wireless/lpwr_wb32.c`) and
  accepts `LPWR_WAKEUP_MATRIX` in the board's `lpwr_wakeup_armed_mask()`
  (`wls/wls.c`), which `lpwr_stop_cb()` (`keyboards/linker/wireless/lowpower.c`)
  checks before committing to a stop. Whether a keypress on the right half
  actually wakes it still needs a flash and a keypress-wake test (`TODO.md`,
  defect 2). Until then, waking the right half relies on toggling its 2.4 GHz/BT
  mode switch or replugging its USB cable.
  - **Precondition to run the test (as of 2026-10-09):** the board will not sleep
    while charging/USB — the sole permitted stop is the low-battery ordered path
    (`lower_sleep` set only at `bat_level <= BATTERY_CAPACITY_STOP`, i.e. 0%, not
    charging). So the wake test needs a run on battery with the low-battery stop
    reached, not a simple idle timeout. Currently deferred.
- The master wakes the slave over the inter-half UART, which *is* an accepted
  cause.
- Sleep is a decision only the master may take, and only through the ordered path
  (`lower_sleep` set, which arms the wake sources); a plain idle timeout is
  refused. See `FINDINGS.md` "the three power-off faults are one defect".
- The deep-sleep entry/exit path (`PRE_LP()`/`POST_LP()` in `lpwr_wb32.c`) is a
  pair of raw-Thumb `uint32_t[]` blobs, fully deobfuscated in `FINDINGS.md` "the
  deep-sleep `PRE_LP()`/`POST_LP()` blobs are raw Thumb".

## Keycaps vs matrix

- Keycap legends do **not** reliably match the matrix positions, so physical key
  identification on this unit must be positional: "right half, matrix `[11,4]`".
  Never identify a key by its legend. See `DEVICE.md` "Nomenclature".

## The known/unknown boundary (no schematic)

There is no Split65 netlist (`FINDINGS.md`). The substitute is not a guess at the
schematic but a **precise box around what we do not know**: for each unknown, what
it is bracketed by, so the residual risk is small and named. This section is that
box. It is a *map of ignorance*, not a claim of completeness.

Read it as three tiers:

1. **Known (measured or source-attested).** Safe to build on.
2. **Bounded unknown (a named gap with a known ceiling).** Tractable today; the
   bound says how wrong we can be.
3. **Open unknown (no bound yet).** The genuine blockers.

### 1. Known

| Fact | Basis |
| --- | --- |
| MCU `WB32FQ95`, Cortex-M3; app flash region **128 K** at `0x08000000` | part marking + the build's link script `WB32FQ95xB.ld` (`flash0 … len = 128k`); the *part's* total flash is not established, only the region firmware uses |
| USB IDs — app `342d:e4c6` (enumerated live, master/left half), bootloader `342d:dfa0` | live enumeration; `HARDWARE.md` "Identity" (bootloader expected on both halves) |
| Matrix `MATRIX_ROWS 12`, `MATRIX_COLS 9`; both halves use the **same 6 row pins** (`A0..A4`, `C13`) with **different column pins** per half (left `C0..C3`,`A6`,`B10`,`B11`; right `B12..B14`,`C6..C9`,`C4`,`C5`), so rows 0–5 = left and 6–11 = right | `keyboard.json` `matrix_pins` + `split.matrix_pins.right` |
| Module UART on `C10`/`C11` (`UART_DRIVER SD3`); split link on `A9`/`A10` (`SD1`) | `config.h`, and the collision it prevents is a documented past symptom |
| Module chip is `CH582F`; the UART protocol is public | `FINDINGS.md` "the module is a WCH CH582F" + `emolitor/WestberryTech-WB32` |
| Mode switch pins `C14` (BT) / `C15` (2.4G); switch reads correctly | live `0xA4` transport byte tracked the switch USB↔BT |
| Cable-detect `A7`, full-charge `A15`, handedness `B9`, encoder `B7`/`B6`, WS2812 `B15` | `config.h` + `DEVICE.md` |
| LED count 68, per-half column maps | `keyboard.json`, `config.h` |
| The module's **BLE stack and its linked "ROM" image are public and disassemblable** | `HARDWARE.md` "The BLE stack is a symbolized library" |

### 2. Bounded unknown

Each row is a gap whose *ceiling* is known, so a design decision can be made
without the schematic.

- **Trace-level wiring of the charge/boost/level-shift stage.** Unknown netlist,
  but **bounded** by the public same-family topology (`oshwhub` CH582F boards:
  keyboard MCU + CH582F + TP4056-class charge + boost LDO + PCB antenna — see
  `FINDINGS.md`). The firmware only *observes* two pins of this stage (`A7`,
  `A15`); it never drives it, so the wiring cannot change firmware behavior beyond
  those two inputs.
- **Whether the module UART is direct or passes through a level shifter.** Unknown
  netlist, but bounded by behavior: the WB32 drives and reads this link with **no
  firmware-visible translator** and the protocol works continuously (USB `0xA4`
  answers; the vendor stack ran on stock), so any shifter present is transparent
  to firmware. A wrong assumption here would surface as a UART fault, which is
  absent. (The line voltage itself is **not** measured — do not record one.)
- **The module's shipped factory image / BLE pairing policy.** Unknown, but
  bounded: the *stack* it is built from is public (`LIBCH58xBLE.a`) and the
  protocol is spec'd; the pairing-related frames (`0x51`/`0x52`) are part of the
  byte-for-byte match with the public protocol doc (`FINDINGS.md`), so the
  behavior is spec'd even though the exact shipping image is not.
- **Whether the CH582F forwards raw HID over BLE.** Unknown, **bounded** by two
  mutually exclusive outcomes: either the BLE HID descriptor exposes the
  `0xFF60`/`0x61` collection (then our `bluetooth_send_raw_hid` → `md_send_raw`
  path carries `0xA4` over BT), or it does not (then BT battery output must be the
  **BLE Battery Service `0x180F`/`0x2A19`**). Both are testable; neither needs the
  netlist.
- **Right-half keypress wake.** Unknown, bounded: the tree arms the right rows and
  the board accepts `LPWR_WAKEUP_MATRIX`; only the *observation* is missing, and
  its test precondition is known (a battery run to the low-battery stop). See
  "Sleep and wake".

### 3. Open unknown (unbounded or hardware/world-blocked)

- **No Split65 schematic or netlist exists publicly** (English/Japanese/Chinese;
  `FINDINGS.md`). Bounded only by "measured by hand" — the Tier-1 continuity /
  voltage / dynamic probe in `TODO.md` for a physical session.
- ~~**The 2.4 GHz dongle does not enumerate on this host**~~ — **RESOLVED
  2026-10-09: it does, and 2.4 GHz works.** The earlier "zero USB events" was a
  **trigger artifact**: the dongle stays USB-silent until it is powered and the
  keyboard is actively on the 2.4 GHz link. With the keyboard in 2.4 GHz mode it
  enumerates as `342d:e4c6` (`bcdDevice 20.04`, product "2.4G Dongle", mfr
  "MILE"), exposes the QMK raw-HID collection at **interface 2**
  (`/dev/hidraw5`, usage page `0xFF60`/usage `0x61`), and a `0xA4` pull
  round-trips — reply `a4 64 00 00 00 04 01 00 …` = level 100, discharging,
  **transport `0x04` (2.4 GHz)**, model 1. So 2.4 GHz is a **working second
  transport**, and unlike BLE it does not depend on the module's broken GATT
  server. Cosmetic bug recorded: the dongle re-enumerates on its own a few
  seconds after first attaching, and on the second enumeration its USB string
  descriptors come out **byte-swapped** (`2.4G Dongle`/`MILE` as garbled
  UTF-16LE) — a firmware quirk, not a functional fault.
- ~~**Whether the module advertises over BLE at all.**~~ **RESOLVED 2026-10-09:
  it advertises, and correctly.** Earlier scans found nothing because they hunted
  the wrong identity — the primitive `PRODUCT " BTn"` default, not the board's
  `MD_BTn_NAME` override (`config.h`), and a name search cannot match a random
  address. A `bluetoothctl` LE scan for the real names found the module reliably,
  per profile: `Split65-2` at `C8:02:09:B0:56:5E` and `Split65-3` at
  `C8:03:09:B0:56:5E` (**random** addresses, third octet = profile index).
  `bluetoothctl info` on the live entry: **Appearance `0x03c1` (HID keyboard)**,
  **Icon `input-keyboard`**, **UUID `0x1812` (HID service)**, AdvertisingFlags
  `0x06` (LE General Discoverable, BR/EDR not supported) — a fully-formed,
  connectable BLE HID keyboard advertisement. The Layer-0 premise that the module
  never advertises is **disproven**; the remaining question is why a host does not
  *bond/connect*, which is no longer a module-silence fault.
- **Why a host does not connect — RESOLVED 2026-10-09: the module pairs and bonds,
  but its HID GATT server rejects the notification-enabling writes.** On the BT2
  profile (`Split65-2`) against a BlueZ 5.87 host:
  - With a pairing agent registered (`bluetoothctl agent KeyboardDisplay` + a
    confirm-capable agent), the module **pairs and bonds**: `Pairing successful`,
    `Paired: yes`, `Bonded: yes`. The first attempt failed with
    `org.bluez.Error.AuthenticationFailed` purely because **no agent was
    registered** — `bluetoothd: src/device.c:new_auth() No agent available for
    request type 2`, `device_confirm_passkey: Operation not permitted`. The module
    requests **SMP numeric-comparison confirm (request type 2)**, not Just Works,
    so a host with no agent cannot answer and the bond never forms. **This is a
    host-side requirement, not a module fault.**
  - The module's GATT tree is real and complete: `0x1812` **HID**, `0x180f`
    **Battery**, `0x180a` Device Info, and a vendor service `02f00000-…-fe00`;
    the full characteristic/descriptor tree (handles up to `0x005a`) enumerates.
  - After bonding, the host attaches **HID-over-GATT** and enables notifications,
    then fails at the **CCC descriptors**:
    `profiles/input/hog-lib.c:ccc_read_cb() Error reading CCC value: Request
    attribute has encountered an unlikely error` and
    `hog-lib.c:report_ccc_written_cb() Write report characteristic descriptor
    failed: … unlikely error` (ATT `0x0E`, `ATT_ERROR_UNLIKELY_ERROR`), plus
    `battery.c:batt_io_ccc_written_cb() Battery Level: notifications not enabled`.
    So the module's **GATT server rejects the descriptor writes that would turn on
    input reports** — the peripheral side errors out, not the host.
  - `bluetoothd: profiles/gap/gas.c:read_ppcp_cb() GAS PPCP: Invalid Connection
    Parameters values` — the module's advertised **Peripheral Preferred Connection
    Parameters** are malformed, which the host also rejects.
  - Net: **advertise → bond works; the HID enable path fails inside the module.**
    Binding to a host is blocked by the module's own GATT/connection-parameter
    behaviour, which is **Layer 0** — not addressable from our firmware.
  - **A/B against stock vendor firmware — DONE 2026-10-09: the vendor build fails
    identically, so this is not our firmware.** The stock `split65-vendor-overlay`
    (`d68e3152`) build, flashed to both halves, was put through the same gesture
    and scan:
    - It advertises the same identities (`Split65-1`/`Split65-2`, `Appearance
      `0x03c1``, `UUID `0x1812``, flags `0x06`) and **pairs + bonds** the same way
      (`Pairing successful` / `Paired: yes` / `Bonded: yes`).
    - It then produces the **same ATT-level failure, byte-for-byte**: at 17:04
      (vendor) the journal shows `GAS PPCP: Invalid Connection Parameters values`
      and `hog-lib.c:ccc_read_cb() Error reading CCC value: … unlikely error`
      (×7), and the module itself dropped the link —
      `LE.Disconnected … Connection terminated by remote user`. This is the exact
      signature our firmware produced at 16:35–16:36.
    - Its address rotates the same way: `Split65-1` appeared as `C8:06` then
      `C8:08` in one session.
    - **Conclusion:** both blockers (the HID-CCC rejection and the non-resolvable
      address rotation) are **the module's own firmware (Layer 0)**, reproduced
      independent of our code. Our firmware is exonerated; no change we make to
      the WB32 side can address them. The remaining levers are the wired UART
      (`C10`/`C11`) probe and a possible module-firmware update over that UART.
  - **The address rotates per advertising session, which is a second, independent
    obstacle.** The module re-advertises under a **new random address each time**
    (observed `C8:02`, `C8:03`, `C8:06`, `C8:07` for the same `Split65-2`
    identity). A bonded host can silently reconnect across such rotation **only if
    the address is a resolvable private address (RPA)** that the host can match to
    the stored bond via the IRK. Here it does not: after the pair, a fresh
    advertising session appeared as a brand-new device, the host could not match
    the bond, and it fell back to a fresh pairing that the peripheral rejected —
    `bluetoothd: No matching connection for device`, and
    `hog-lib.c:info_read_cb() HID Information read failed: Attribute requires
    authentication before read/write` (the HID service needs an **encrypted** link,
    which the unmatched session does not have). Reconnect therefore fails after a
    successful initial bond, and only the LED shows pairing mode (no passkey
    display), so **pairing must be re-done from the keyboard each session**. The
    address policy (RPA vs non-resolvable random) is set **inside the module** and
    is Layer 0.
  - **External corroboration (2026-10-09).** Two independent lines confirm this is
    a known firmware-fault class, not a host misconfiguration and not our code:
    - **The vendor's own issue tracker.** `Epomaker/Split65` issue **#3, "Stuck
      after wireless connection"** (gwangyi, 2025-08-04): a build from the
      *vendor's own* `hangshengkeji/qmk_firmware` "stuck about 20s later from
      wireless connection … *both BT and 2.4 GHz*", with the left half dark — the
      same power-state family as our defect 4. The reporter's own fix was the
      community workaround below. Issue **#7** asks for official `.bin`s; the
      vendor only distributes them via Discord, so there is no public module
      firmware to diff against.
    - **The community workaround.** `zozonteq/epomaker_split65` (a fork of the
      vendor repo) is described as "**Wireless issue workaround (lowpower-mode
      disabled)** + More Bluetooth Connections (up to 5)". Its `wls/wls.c` proves
      the mechanism: every `lpwr_set_timeout_manual(true)` call is **commented
      out**, i.e. the board is simply never allowed to sleep. Their BT works once
      the power-management path is removed — consistent with our finding that the
      faults live below our firmware, and with our own defect-4 conclusion (a half
      entering an unrecoverable STOP). We fixed the STOP fault properly; they
      disabled sleep outright.
    - **The ATT `0x0E` signature is a documented host/peripheral interaction, not a
      BlueZ-only bug.** BlueZ issue #448 and zmkfirmware/zmk issue #3309 show the
      *same* `hog-lib.c:ccc_read_cb() … unlikely error` stream arising when a
      peripheral's GATT server returns `BT_ATT_ERR_UNLIKELY` (0x0E) for reads it
      cannot yet serve — and the ZMK case localises the cause to the peripheral's
      own profile/address matching (its `zmk_ble_profile_index()` fails on an
      address it cannot match, exactly the rotation problem recorded above). So the
      failure is the module declining the ATT operations, not Linux refusing them.
    - Our BT-select is **protocol-identical to the vendor's**: `bluetooth_select_profile`
      → `wireless_devs_change` → `md_devs_change()` emits the same `DEVCTRL_BTn`
      frame, and on re-pair the same `DEVCTRL_CLEAN` + `devinfo` + `DEVCTRL_PAIR`
      sequence, so the module receives exactly the commands the stock firmware
      sends. Nothing in our change set altered the module wire.
  - **Source-level comparison against a working reference (2026-10-09).** The
    failing layer *is* public as ordinary C source in a different CH582M tri-mode
    keyboard: `ChnMasterOG/tp78_v2`, `mounriver_project/KEYBOARD_CH582M/Profile/`
    (`hidkbmservice.c`, `hiddev.c`, `battservice.c`). It is the generic
    WCH-derived HID-over-GATT profile — a different vendor than our module's
    `0bts`, so it is a reference, not a drop-in — but it shows precisely what a
    correct implementation does, and where ours diverges:
    - **CCC writes.** The reference's `HidDev_WriteAttrCB()` handles
      `GATT_CLIENT_CHAR_CFG_UUID` by calling `GATTServApp_ProcessCCCWriteReq(...)`
      and **always returns `SUCCESS`**; the whole profile never emits an ATT error
      from a CCC write (the only `0x0E` bytes in the file are HID report-map
      descriptor data, not error codes). Our module answers the same write with
      `ATT_ERROR_UNLIKELY_ERROR` (0x0E) — i.e. its GATT server is failing an
      operation the reference stack serves generically. The CCC attributes are
      `GATT_PERMIT_READ | GATT_PERMIT_ENCRYPT_WRITE` with a zero initial value;
      the host's `ccc_read_cb()` on our module also failed, which means the module
      could not even serve a plain readable attribute — a stack-level GATT fault,
      not a profile-callback choice we could influence.
    - **Reconnect after bond.** The reference makes reconnect work by two
      deliberate mechanisms we see no sign of in our module's behaviour:
      (a) `GAPBondMgr_SetParameter(GAPBOND_AUTO_SYNC_WL, TRUE)` — it syncs the
      bonded host's address into the **controller whitelist** so the bond survives
      across the peer's own address changes; and (b) `HidDev_Report()` chooses the
      advertising duty by bond state — **high-duty-cycle** when bonded (fast
      reconnect for the known host), initial/general when not. Our module instead
      re-advertises under a **non-resolvable random address** each session, so the
      host cannot match its stored bond at all (`No matching connection for
      device`). That is the opposite of the reference's whitelist/RPA-bond design
      and is fixed entirely inside the module image.
    - Net: the two faults are **exactly the two behaviours the reference
      implementation handles explicitly and our module does not.** This upgrades
      the conclusion from "module misbehaves" to "module's GATT/ bonding layer is a
      known-aberrant/older WCH-profile variant" — still Layer 0, still unreachable
      from the WB32 firmware, but no longer unexplained.

### The Layer boundary: what we can and cannot fix (2026-10-09)

The Bluetooth faults sit at a boundary worth stating plainly, because it decides
where any future work belongs.

- **Layer 0 — the CH582F module image.** The GATT server that rejects CCC writes
  (ATT `0x0E`) and the address/bond policy that rotates non-resolvably. **Closed,
  undumpable, un-updatable** from the keyboard (see "Can we dump or update the
  module's firmware?"). Nothing we flash onto the WB32 can reach it: the UART
  command set has no flash/bootloader/memory command, and ISP entry cannot be
  triggered from outside the module's own app. This layer is not ours to fix.

- **Layer 1 — our WB32 firmware.** It can (a) speak the module protocol
  correctly (done; the vendor A/B showed the faults are not host-sequence-caused),
  (b) **fingerprint** the module — `0xA4` bytes 9–10 expose the module's `0x5D`
  firmware version and its own `0x5B` link state, the only public handle on a
  closed image, and (c) surface module state for diagnosis. It **cannot** make
  the module's GATT server serve an attribute it refuses to serve, nor make it
  use a resolvable address.

- **Layer 2 — host tooling.** The reconnect loop is a host-side workaround for
  the module's rotation (`host/bt_reconnect.py`). It makes the attempt
  reproducible; it does not repair the link.

**Which of these is upstreamable, and which is board-local — deliberately:**

- **Upstreamable (already done, generic):** the wireless-module *abstraction* —
  `drivers/wireless/wireless_2p4ghz.{c,h}`, the `CONNECTION_HOST_2P4GHZ` cases in
  `host.c`, the `WIRELESS_2P4GHZ_ENABLE` feature. These fill a hole upstream left
  open (`#if 0` in `host_candidates[]`) and name a transport any board may have.
  If a generic wireless-module protocol readback is ever modeled upstream, `0xA4`
  bytes 9–10 (module firmware version / link state) are the fields that would
  carry over — they are module-protocol-agnostic concepts.
- **Board-local, never upstream:** the `0xA4` command itself (a
  Keychron-derived host convention, not a QMK standard), bytes 7–8 (the
  persisted host and BT sub-profile — *test-only* diagnostics for our
  verification, deliberately reclaimable), and the entire reconnect workaround
  (`host/bt_reconnect.py`), which encodes *this* module's specific bug. Upstream
  cannot carry "reconnect to a broken CH582F", and must not: patching around a
  vendor fault (faking notifications, spoofing an address) would be fiction in
  the plate. The honest split is *generic model gaps upstream; vendor-specific
  faults board-local and documented.*

- **What `0xA4` byte 1 means off-USB.** Every value seen on USB is the module's
  init constant; only the radio path is known to be live. Cannot be bounded until
  2.4 GHz or BT works.

### How to keep the boundary honest

When a new fact lands, put it in tier 1, move its bound out of tier 2/3, and
**delete the bound** rather than leaving it as folklore. When a design decision
depends on a tier-2 item, cite the bound next to the decision so a future reader
knows the ceiling it was made under. `FINDINGS.md` holds the *reasoning*; this
table holds the *state*.

## Reset cause (the chip latches it)

The WB32FQ95xx records why it last reset in **`RCC->RSTSTAT`** (offset `0x100`),
a six-bit latch cleared by writing **`RCC->CLRRSTSTAT`** (offset `0x0C8`, bit
`CLR`). Verified in the CMSIS device header
(`lib/chibios-contrib/os/common/ext/CMSIS/WB32/WB32FQ95xx/wb32fq95xx.h`).

| Bit | Define | Cause |
| --- | --- | --- |
| 0 | `RCC_RSTSTAT_LPWRRSTF` | low-power mode |
| 1 | `RCC_RSTSTAT_WWDGRSTF` | window watchdog |
| 2 | `RCC_RSTSTAT_IWDGRSTF` | independent watchdog |
| 3 | `RCC_RSTSTAT_SFTRSTF` | software |
| 4 | `RCC_RSTSTAT_PORRSTF` | power-on |
| 5 | `RCC_RSTSTAT_PINRSTF` | external reset pin |

**Why it matters.** A reset loop cannot be observed by any channel that needs the
running application — the fault destroys the channel that would report it. This
latch is a fact the *chip* holds across the reset, so the next boot can read and
report it with no host and no prior instrumentation. The firmware consumes it
exactly once (`wls_note_reset_cause()`, read-and-clear at
`keyboard_post_init_kb`) and retains the value (`wls_reset_cause()`) so the two
readers — the LED code and the `0xA4` diag block — cannot disagree. See
`docs/INDICATORS.md` §2 for how the value is spoken.

**Caveat — now MEASURED (2026-10-14).** The register set is confirmed from the
vendor CMSIS header, and `RCC->` is already used elsewhere in the tree
(`keyboards/linker/wireless/lpwr_wb32.c`). On 2026-10-14 the instrument was read
on hardware: a deliberate cold boot spoke `(7 amber, 5 white)` — stage
`RSTCAUSE`, white 5 = bit 4 = `PORRSTF` (power-on). **So the latch is real, this
board's silicon reports it, and bit 4 is confirmed.**

**The latch held TWO bits, which corrects an earlier claim here and in
`boot_code_logic.h`.** The USB readback (`--info`) reports
`RESET: cause_bits=0x30 (power-on, external-pin)` — bits 4 **and** 5 set. So the
"a single reset normally sets exactly one, the lowest set bit wins" statement is
**not universally true on this board**: a power-on event also latches the pin
bit, and the reported white 5 is the lowest set bit of a two-bit word. The code's
lowest-bit rule is therefore *correct as a tie-break*, but the reading is not
proof that only one cause occurred. The *other* four bits have not been observed;
in particular the loop's own cause has still not been seen. Do not treat "the
register works" as evidence about which bit the fault sets — that is what the
next reading must establish.

**Second measurement of the same event, and a withdrawn defect hypothesis
(2026-10-14).** After flashing the Stage-4 build (sha256 `2ec21c44…`) the board
was power-cycled and read again: the operator saw **five amber (rendered green),
pause, five white, pause, backlight**. That is stage `RSTCAUSE` / white 5 =
`PORRSTF` again — the same event as the `(7, 5)` reading above — but the **amber
group showed five pulses where the code says seven**.

**First written as a live instrument defect; then withdrawn as a phantom of the
old artifact; now REINSTATED (2026-10-14, second flash).** The withdrawal
reasoned from a host simulation of the *pure core* — and the pure core is indeed
correct (see below). But this reading was reproduced on the **new flash**
(`a45a9762…`, built from the committed tree with the show-window fix), so the
loss is real, survives the fix, and is **not** an artifact of the old build.

The simulation modelled `wls_boot_code_at` and its helpers verbatim, swept the
origin offset across the full pulse period, and counted visible pulses at every
offset: `(amber 7, white 5)` renders as **seven amber and five white at every
offset**, with `show == frame == 11 700 ms`. Three properties of the core make a
*rule-level* truncation impossible:

- `wls_boot_code_show_ms()` returns exactly `wls_boot_code_frame_ms()`, so the
  window cannot end mid-group;
- the window is measured *from the stamped origin*
  (`timer_elapsed32(boot_code_started) >= show_ms`), so the pass that stamps the
  origin is itself inside the window;
- `wls_boot_code_at(t = 0)` is already lit, so a late origin can begin a little
  into the first pulse but can never skip a whole one.

**What the simulation did not model — and the honest state of the cause.** It
assumed a clean 1 ms tick and an unbroken frame cadence. A "frame starvation
during boot" theory was then written: the origin is armed on the first *live*
paint, and the amber group is the first 4200 ms of the 11 700 ms window, when the
RGB frame limiter (`RGB_MATRIX_LED_FLUSH_LIMIT`, 16 ms), matrix scan, USB
enumeration and the RSTCAUSE gathering all compete for the frame. **That theory
was never measured, and a settle-delay fix built on it was reverted unflashed.**
It is recorded here as a hypothesis, not a finding.

**What IS measured (2026-10-14, the working flash, `--info` over USB):** the
firmware reports `BOOT CODE: 7 amber, 5 white -> stage=RSTCAUSE code=5`. **The
code is correct in the firmware.** The eye reads 5 amber, so the discrepancy is a
**rendering defect only** — the count's *value* is trustworthy over USB (the
`0xA4` reply carries the same code the LED plays, `wls_boot_code_encode()`), and
must be read there. The LED undercount is cosmetic and its cause is unmeasured.

**Bearing (corrected again).** Read the code over USB (`host/battery_polybar.py
--info --transport usb`). The LED is a fallback for when no host is available: its
white group (5) is stable and reads `RSTCAUSE`, but **its amber count must not be
trusted to the pulse until the render path is instrumented**. Treat a `(5, 5)`
reading as `RSTCAUSE`; **stage 5 (`INCOMPLETE`) has no code path at all**.

**The sentinel hazard found while walking this code is fixed, but it was not the
cause.** The shell used `boot_code_started == 0` to mean "armed, not yet
started", aliasing a *real* time value onto the sentinel: `timer_read32()`
genuinely returns 0 during the first millisecond after `timer_init()`
(`platforms/chibios/timer.c`), so an origin stamped at exactly 0 would re-enter
the "not started" branch forever and hold the matrix black for the whole window.
It is now a separate latch (`boot_code_armed`, `wls_indicator.c`), so the
sentinel and the time value cannot be confused. **That fixes a distinct hazard;
it does not address the sampling loss above.**

## The cabled-but-wireless fault (measured 2026-10-14, the Stage-4 flash)

The same Stage-4 flash re-exposed a fault this project has met before — **the
C14/C15 pin lie** (`TODO.md` "THE STATE OF PLAY", and the boot-switch-settling
derivation in `FINDINGS.md`). It is a bug in our own layer, not a wild pointer
and not electrical.

**What was observed.** The keyboard enumerated on USB as `342d:e4c6`, `mfr=LEO`
(our firmware — the dongle's string is `MILE`), presenting the full QMK raw-HID
collection `usage_page 0xFF60 / usage 0x61` on interface 1. **Yet it did not type
on USB and did not answer `0xA4`** (a raw 32-byte probe on `/dev/hidraw1`
returned nothing). No dongle was attached. **The mode switch was on USB, and had
been all session.**

**Why the silence is expected *given* the transport, and what that proves.**
`host_raw_hid_send()` (`tmk_core/protocol/host.c:388`) dispatches to
`host_get_active_driver()->send_raw_hid`, and the wireless driver
(`keyboards/linker/wireless/wireless.c:24`) has **no `.send_raw_hid` member at
all**, so the call returns early and nothing is sent. A silent `0xA4` with the
device enumerated therefore means **the committed transport was wireless while
the switch said USB** — the two observations are one fact.

**The read that is wrong.** `hs_mode_switch_pos()` (`wls/wls.c:233`) decides from
`HS_GET_MODE_PIN(HS_*_PIN_STATE)`, which reads **C14 and C15** and matches them
against the 2-bit pattern per position (`wls/wls.h:17-24`):
`HS_USB_PIN_STATE "1, 1"`, `HS_BT_PIN_STATE "0, 1"`, `HS_2G4_PIN_STATE "1, 0"`,
`'x'` a wildcard. A USB-position switch therefore requires **C14 == 1 && C15 == 1**.
The documented failure is that the boot seed reads these pins **immediately after
enabling their pull-ups, before `palSetLineMode` settles**, so the read yields
UNKNOWN or the wrong pair — here, 2.4 GHz — and the board commits wireless with
the cable attached and the switch on USB.

**The consequence chain is the project's named defect class.** With a wireless
hint committed, `drive_line_for(WLS_TRANSPORT_INPUT_HINT)` (`wls_transport.c:65`)
calls `hsm_transport_may_drive_line(want_usb)`, which for an **unconfirmed** input
returns `decision_is_usb` — so with `want_usb == false` the line is neither
driven down (correct) nor driven up. Stage 1 of `hsm_transport_decide`
(`usb_active -> USB`) can only fire once `host_confirmed` is true, and
`host_confirmed` is set only by `wls_transport_host_event()` from
`notify_usb_device_state_change_kb()` — which needs the enumeration the unhurried
line never reached. **The trigger depends on the state it should confirm.**

**Open, not fixed.** `TODO.md` records that fixes A–D were built for exactly this
(the settling wait, the promote-only rule, the UNKNOWN handling). This flash shows
the fault recurring, so **the settling fix is not sufficient at this boot** — a
live reading is needed to say which pin settled wrong. That is the next software
question, and it must be settled and proven before it earns a flash.

## The USB restart erratum, and why our tree does not have the guard

**Measured fact (2026-10-14, from the linked ELF, not from a forum).**

Upstream QMK carries a board-level guard for WB32 USB:

```c
// platforms/chibios/boards/GENERIC_WB32_FQ95XX/board/board.c
void restart_usb_driver(USBDriver *usbp) {
  // Do nothing. Restarting the USB driver on these boards breaks it.
}
```

It was added by **`b5a52b4cff` — "Prevent USB peripheral fault when restarting USB
on WB32 MCUs (#18058)"** (Joy Lee, 4 years ago). **It was then removed by
`bd2e59af60` — "Fixed WB32 MCU remote wakeup issue (#20863)"** (same author, 3
years ago), which deleted the guard while adding one blank line. **Both commits
are in our submodule's history, and the deletion is the state our tree is in:**
our `GENERIC_WB32_FQ95XX/board/board.c` has a stub `boardInit()` and **no
`restart_usb_driver` override at all.**

**What that means concretely.** With the override absent, the weak default in
`tmk_core/protocol/chibios/usb_main.c` is linked instead, so the board **does**
run the full restart sequence. Verified in the shipped ELF
(`epomaker_epomaker_split65_nathan.elf`):

```
0800a590 W restart_usb_driver          <- weak symbol, i.e. NOT overridden
  bl  wb32_usb_disconnect              <- usbDisconnectBus
  bl  usbStop
  bl  usb_endpoint_in_stop  (x4)
  bl  usb_endpoint_out_stop
  movw r0, #5000 ; bl chThdSleep       <- wait_ms(50)
  ... usb_endpoint_*_init/_start, usbStart, usbConnectBus
```

The `W` in `nm` output is the proof: the symbol is weak and un-overridden, so the
erratum the upstream comment describes ("restarting the USB driver on these
boards breaks it") is **live on this board**.

**Why this matters to us specifically.** Our transport owner calls
`wls_usb_connect(true)` → `restart_usb_driver()` as the promotion path when a
host is confirmed. That is exactly the operation upstream flagged as breaking the
WB32 peripheral. This is a real, named, upstream-documented hazard that sits
**on our hot path**, and it is the first candidate that explains intermittent USB
misbehaviour that survives reflashing and is absent on some boots.

**Status: measured as *present* (the guard is absent, the weak default is
linked); NOT yet measured as the *cause* of the observed DFU entries or the
non-typing.** Treat it as a leading hypothesis, not a conclusion — the same
discipline the `RSTSTAT` work needed (a register that works is not evidence about
which bit a fault sets).

**ACTION TAKEN 2026-10-14: the guard is RESTORED.** The override now exists in
`platforms/chibios/boards/GENERIC_WB32_FQ95XX/board/board.c` (an empty
`restart_usb_driver`), restoring upstream's own deleted text. Verified on the
rebuilt ELF: `arm-none-eabi-nm` now reports **`T restart_usb_driver`** where it
previously reported **`W`** (the override wins), the body disassembles to
`movs r0,#0; bx lr` (a bare return), and **`usbDisconnectBus` no longer appears
anywhere in the image**.

**RESULT 2026-10-14: the erratum is NOT the cause.** The comparison was run. The
flash changed nothing about the fault: the port still cycles, the `dfa0` DFU
windows still appear between app enumerations with no flash in progress, and the
board still does not type. The 25-minute window after the flash showed 8
enumerations / 8 disconnects / 0 `-71`, including a 12-minute stable hold
(10:46:47–10:58:50) followed by the same jump.

So the guard is **kept** (upstream's own reasoning stands on its own, and it cost
nothing), but it is **not** the explanation for the cycling — look elsewhere.
The live candidate is the DFU magic word itself: a `dfa0` window means
`bootloader_jump()` ran, which means `0xDEADBEEF` was written to `MAGIC_ADDR`.
The only board-reachable writer is `QK_BOOT` (`wls/wls_keymap.c`), and the word
lives at the last word of the heap, so the possibilities are a spurious `QK_BOOT`
dispatch, heap/stack corruption of that word, or an electrical cause. Unseparated
as of this writing.

## Flash targeting

- Flashing requires **wired USB**. 2.4 GHz and Bluetooth cannot flash.
- `wb32-dfu-updater_cli -t -s 0x08000000 -D <bin>` then `wb32-dfu-updater_cli -R`.
- Required udev rules, toolchain and the full procedure are in `DEPENDENCIES.md`.
