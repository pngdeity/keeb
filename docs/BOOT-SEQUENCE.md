# Boot sequence — reset to steady state, mapped definitively

> **Scope and method.** A complete, ordered map of what runs from MCU reset to
> the steady-state main loop, on this board, for the revision named below. Every
> claim was read out of the source **at that revision** — `file:line` is given so
> each can be re-checked rather than trusted. This document exists because
> debugging by symptom (`flash -> observe one line -> guess -> flash`) is
> reactive and expensive; the boot is small and linear, and mapping it is the
> a-priori alternative. It is descriptive, not aspirational: it records what the
> code *does*, including the parts that are ugly.

**Revision this map describes (verify before trusting it):**

| Tree | Revision | Notes |
| --- | --- | --- |
| `qmk_firmware/` submodule | `75a5ee699e` (signed) | **clean**; the "owner arc" is stashed, not in the tree |
| root repo | `ee3ad13` (signed) | topic docs only; nothing in it runs on the MCU |
| userspace keymap | `a832a0b` (signed) | build with `-km nathan`; `is_keyboard_master()` lives here |

The **keyspace the map is generated for** is the `nathan` build. Feature
switches are not guessed: they are read from the build's own
`cflags.txt`. Those that change this map:

`SPLIT_KEYBOARD`, `CONNECTION_ENABLE`, `RGB_MATRIX_ENABLE`, `ENCODER_ENABLE`,
`RAW_ENABLE`, `NKRO_ENABLE`, `MOUSEKEY_ENABLE`, `WIRELESS_ENABLE`,
`BATTERY_ENABLE`, `BLUETOOTH_ENABLE`, `WIRELESS_2P4GHZ_ENABLE`, `CRC_ENABLE`
are **on**; `NO_USB_STARTUP_CHECK` is **on**.

`VIA_ENABLE`, `BACKLIGHT_ENABLE`, `RGBLIGHT_ENABLE`, `AUDIO_ENABLE`,
`LED_MATRIX_ENABLE`, `OLED_ENABLE`, `VIRTSER_ENABLE`, `POINTING_DEVICE_ENABLE`,
`USB_WAIT_FOR_ENUMERATION`/`WAIT_FOR_USB`, `EE_HANDS`, `SPLIT_USB_DETECT` are
**off**. Regenerate with:

```sh
rg -n "D(SPLIT_KEYBOARD|CONNECTION_ENABLE|...)" \
   qmk_firmware/.build/obj_epomaker_epomaker_split65_nathan/cflags.txt
```

---

## 0. The shape of it

The whole boot is **one linear sequence of five calls**, then an infinite loop
(`quantum/main.c:37-82`):

```
main()
  ├─ platform_setup()        — ChibiOS only: halInit(); chSysInit()
  ├─ protocol_setup()        — USB device-state object
  ├─ keyboard_setup()        — EEPROM, matrix pins, keyboard_pre_init_*
  ├─ protocol_pre_init()     — start the USB peripheral
  ├─ keyboard_init()         — the bulk: timers, split, matrix, EEPROM reads, RGB
  │     └─ … keyboard_post_init_quantum()  ← last thing; calls our biggest hook
  ├─ protocol_post_init()    — install the host driver
  └─ while (true) { protocol_pre_task(); keyboard_task(); protocol_post_task();
                    raw_hid_task(); housekeeping_task(); }
```

Everything else in the firmware is a callee of one of those seven steps. There is
no hidden dispatcher: **`main()` is 45 lines** (`quantum/main.c:38-82`).

An important consequence, stated once here: **the USB peripheral is started in
`protocol_pre_init()`, before `keyboard_init()`.** So the host may begin
enumerating while our layer is still initialising, and *any* early crash in
`keyboard_init()` will be observed by the host as "enumeration started and
stopped".

---

## 1. Before `main()` — the ChibiOS vector path

Not visible in `quantum/main.c`; it runs first. Verified in
`tmk_core/protocol/chibios/chibios.c:118-135`:

```
__early_init()          (overrides ChibiOS's board hook)
  ├─ early_hardware_init_pre()    (weak; default is a no-op unless
  │                                EARLY_INIT_PERFORM_BOOTLOADER_JUMP)
  ├─ __chibios_override___early_init()   — clocks, GPIO, flash
  └─ early_hardware_init_post()   (weak; default no-op)
boardInit()
  ├─ __chibios_override_boardInit()      — board pins, DFU handling
  └─ board_init()                 (weak; default no-op)
… then main()
```

**Our code does not run here.** Neither `early_hardware_init_pre/post` nor
`board_init` is overridden by this board (checked: no definition under
`keyboards/epomaker/epomaker_split65/`). So a fault before `main()` cannot be
ours.

**DFU is entered here**, in `__chibios_override_boardInit()` and/or the
bootloader's own reset path — *not* by our firmware. This is why the bootloader
(`342d:dfa0`) survives when the application faults.

---

## 2. `platform_setup()` — ChibiOS bring-up

`platforms/chibios/platform.c:19-22`:

```c
void platform_setup(void) { halInit(); chSysInit(); }
```

Two calls; no board code. After this, interrupts and the RTOS are live.

---

## 3. `protocol_setup()` — USB device-state object

`tmk_core/protocol/chibios/chibios.c:137-142`:

```c
void protocol_setup(void) { usb_device_state_init(); }
```

`usb_device_state_init()` (`tmk_core/protocol/usb_device_state.c`) sets
`configure_state = USB_DEVICE_STATE_INIT` and calls
`notify_usb_device_state_change()`, which dispatches to
`notify_usb_device_state_change_kb()` — **a hook this board overrides** (in the
owner arc; at the mapped revision it is the upstream default, see §8).
So this is the *first* point where any USB-lifecycle notification can reach board
code — and it fires before the USB peripheral exists.

---

## 4. `keyboard_setup()` — EEPROM, matrix pins, pre-init hooks

`quantum/keyboard.c:365-372`, in order:

1. `print_set_sendchar(sendchar);` — routes `print()` to USB console.
2. `eeprom_driver_init();` — wear-levelled emulated EEPROM
   (`EEPROM_DRIVER` is defined).
3. `matrix_setup();` — **weak**, empty by default
   (`quantum/keyboard.c:289`). This board does **not** override it.
4. `keyboard_pre_init_quantum();` (`quantum/keyboard.c:315-318`), which calls:
   - `keyboard_pre_init_modules()` — weak, no-op.
   - `keyboard_pre_init_kb()` — **weak; this board does not override it**, so
     the default runs: `keyboard_pre_init_user()` (`quantum/keyboard.c:301-303`)
     — **weak in quantum, and neither the `default` nor the `nathan` keymap
     defines it.** So this is a no-op on this board.

**Nothing board-specific runs in `keyboard_setup()`.** At this point the USB
peripheral is still stopped.

> **Trap for future work.** `matrix_setup()` and `keyboard_pre_init_kb()` are the
> only board hooks that run *before* USB starts. If a fault must be visible to
> the host as a failed enumeration, it is **not** here — anything here happens
> before the host sees us at all. This is where the *earliest* instrumentation
> would go if we ever need to prove "we reached `main()`".

---

## 5. `protocol_pre_init()` — **the USB peripheral starts here**

`tmk_core/protocol/chibios/chibios.c:144-168`, in order:

1. `usb_event_queue_init();` — the event queue the main loop drains later.
2. `init_usb_driver(&USB_DRIVER);` — **starts the USB peripheral.** The host can
   now begin enumeration. On a WB32 this arms the LLD and the interrupt.
3. `#ifdef MIDI_ENABLE` — off here.
4. `#ifdef USB_WAIT_FOR_ENUMERATION` — **not defined** for this build, so the
   `while (USB_DRIVER.state != USB_ACTIVE) wait_ms(50);` **does not run**.
   The firmware does **not** wait for the host. (This is the single most
   important line for our fault: enumeration and our init now proceed
   *concurrently*.)
5. `wait_ms(50);` — **unconditional**, with a comment that it prevents later
   `print()` uses from hard-faulting on a not-yet-ready console endpoint. This is
   50 ms of dead time on every boot, before `keyboard_init()`.
6. `print("USB configured.\n");` — goes to the USB console (only useful under a
   console build).

> **This is where the "enumeration started and stopped" signature originates.**
> Once step 2 runs, the host sees a device. If a later step faults, the host
> logs `new full-speed USB device number N` and never `New USB device found`.

---

## 6. `keyboard_init()` — the bulk, in exact order

`quantum/keyboard.c:466-559`. Only the *compiled-in* steps are listed (feature
set per the header). Order is **significant** and is exactly as written:

| # | Call | Source | Runs here? | What it does on this board |
| --- | --- | --- | --- | --- |
| 1 | `timer_init()` | quantum | yes | system timers |
| 2 | `sync_timer_init()` | quantum | yes | deferred/sync timers |
| 3 | `via_init()` | quantum | **no** | `VIA_ENABLE` off |
| 4 | `split_pre_init()` | `split_common/split_util.c:200-216` | **yes** | **decides our role** — see §7 |
| 5 | `encoder_init()` | quantum | yes | `ENCODER_ENABLE` on |
| 6 | `matrix_init()` | `quantum/matrix.c:269+` | yes | configures matrix pins **for the half** — see §7 |
| 7 | `quantum_init()` | `quantum/keyboard.c:438-457` | yes | EEPROM signature check, `eeconfig_init()` if blank, reads debug/keymap/default-layer |
| 8 | `connection_init()` | `quantum/connection/connection.c:52-57` | **yes** | reads `config.desired_host` from EEPROM; if `INVALID`, writes defaults |
| 9 | `host_init()` | `tmk_core/protocol/host.c:132-134` | yes | **literally does nothing** (`// currently do nothing`) |
| 10 | `led_init_ports()` | quantum | yes | indicator LED pins |
| 11 | `backlight_init_ports()` | quantum | **no** | `BACKLIGHT_ENABLE` off |
| 12 | `audio_init()` | quantum | **no** | off |
| 13 | `led_matrix_init()` | quantum | **no** | off |
| 14 | `rgb_matrix_init()` | quantum | **yes** | `RGB_MATRIX_ENABLE` on |
| 15 | `unicode_input_mode_init()` | quantum | **no** | off |
| 16 | `crc_init()` | quantum | **yes** | `CRC_ENABLE` on |
| 17 | `oled_init()` | quantum | **no** | off |
| 18 | `st7565_init()` | quantum | **no** | off |
| 19 | `ps2_mouse_init()` | quantum | **no** | off |
| 20 | `backlight_init()` | quantum | **no** | off |
| 21 | `rgblight_init()` | quantum | **no** | `RGBLIGHT_ENABLE` off |
| 22 | `steno_init()` | quantum | **no** | off |
| 23 | `dip_switch_init()` | quantum | **no** | off |
| 24 | `joystick_init()` | quantum | **no** | off |
| 25 | `sleep_led_init()` | quantum | **no** | off |
| 26 | `virtser_init()` | quantum | **no** | off |
| 27 | `split_post_init()` | `split_util.c:221-228` | **yes** | slave half starts its transport |
| 28 | `pointing_device_init()` | quantum | **no** | off |
| 29 | `battery_init()` | quantum | **yes** | `BATTERY_ENABLE` on |
| 30 | `bluetooth_init()` | quantum | **yes** | `BLUETOOTH_ENABLE` on |
| 31 | `wireless_2p4ghz_init()` | quantum | **yes** | `WIRELESS_2P4GHZ_ENABLE` on |
| 32 | `haptic_init()` | quantum | **no** | off |
| 33 | `keyboard_post_init_quantum()` | `quantum/keyboard.c:348-351` | **yes** | calls `keyboard_post_init_modules()` then `keyboard_post_init_kb()` |

**`keyboard_post_init_quantum()` is the last call** (`quantum/keyboard.c:559`,
with the comment *"Always keep this last"*). It dispatches to
`keyboard_post_init_kb()` — **the board hook where all our boot work happens**
(§8).

> **Critical ordering fact.** `connection_init()` (step 8) reads the persisted
> host **before** our code runs (step 33). And `split_pre_init()` (step 4)
> decides master/slave **before** the EEPROM is even known to our layer. Both
> matter for the transport.

---

## 7. Split role: `split_pre_init()` decides who we are

`quantum/split_common/split_util.c:200-216`:

```c
void split_pre_init(void) {
    split_config.master = is_keyboard_master_impl();
    split_config.left   = is_keyboard_left_impl();
    if (is_keyboard_master()) { transport_master_init(); }
}
```

Two different functions, and the distinction is load-bearing:

- **`is_keyboard_left_impl()`** (`split_util.c:139-148`) — for this board
  `SPLIT_HAND_PIN` is defined (`B9`), so it does:
  `gpio_set_pin_input(B9); wait_us(100); return gpio_read_pin(B9);`
  (settled read; the `wait_us(100)` is the core's own idiom).
- **`is_keyboard_master_impl()`** (`split_util.c:181-189`) — returns
  `usb_bus_detected()`, and if that is false calls `usb_disconnect()`.
  `usb_bus_detected()` (`split_util.c:66-80`) has two forms, selected by
  `SPLIT_USB_TIMEOUT`: with it defined, a **timed poll of
  `usb_connected_state()`**; without it, `usb_vbus_state()`.

  **For this board `SPLIT_USB_DETECT` is force-defined and the polling form is
  what compiles.** `USB_VBUS_PIN` is undefined (verified absent from
  `.build/obj_epomaker_epomaker_split65_nathan/cflags.txt`, and from the board
  and `keyboards/linker/wireless/` config chains), so
  `platforms/chibios/chibios_config.h:19-21` (`#ifndef USB_VBUS_PIN` →
  `#define SPLIT_USB_DETECT`) turns it on. `usb_bus_detected()` therefore does:

  ```c
  for (uint16_t i = 0; i < (SPLIT_USB_TIMEOUT / SPLIT_USB_TIMEOUT_POLL); i++) {
      if (usb_connected_state()) return true;
      wait_ms(SPLIT_USB_TIMEOUT_POLL);
  }
  return false;
  ```

  with `SPLIT_USB_TIMEOUT 2000` and `SPLIT_USB_TIMEOUT_POLL 10`
  (`split_util.c:36-41`, no board override): **up to ~2 s of *blocking*
  `wait_ms`, inside `split_pre_init()` — i.e. inside `keyboard_init()`, step 4.**
  This runs *after* `protocol_pre_init()` has already started the USB
  peripheral (`quantum/main.c:43-44`), so the poll can legitimately see USB come
  up; but if `usb_connected_state()` is not true within the window it returns
  false and `is_keyboard_master_impl()` calls **`usb_disconnect()`** — the
  device detaches itself. On a board with no `USB_VBUS_PIN`, `usb_vbus_state()`
  is a constant `true` (`tmk_core/protocol/usb_util.c:28-36`), so the
  non-polling branch would *never* disconnect; the polling branch is the only
  one that can, and it is the one that compiles here.

  **Correction (2026-10-13):** an earlier revision of this section claimed the
  keymaps' `is_keyboard_master()` overrides decide boot mastery. They do not:
  `split_pre_init()` calls **`is_keyboard_master_impl()`** directly (line 201),
  never the public `is_keyboard_master()` accessor (`split_util.c:195-197`).
  **Both keymaps' `is_keyboard_master()` overrides are therefore dead code for
  boot mastery.** `keymaps/default/keymap.c:59-62` reads `B9` unsettled; the
  userspace `nathan/keymap.c:104-114` variant adds `wait_us(100)`. Neither is
  consulted here, and the `wait_us(100)` "mastery fix" made earlier in the
  project targets a function the boot does not call.

**Consequence:** mastery is decided by the **`SPLIT_USB_DETECT` poll of
`usb_connected_state()`**, not by `B9` and not by the keymaps, **before** any of
our transport code runs. `matrix_init()` (step 6) then configures the
column/row pins for the half `is_keyboard_left()` reported — and *that* one does
read `B9` (settled).

---

## 8. `keyboard_post_init_kb()` — where our boot actually happens

`keyboards/epomaker/epomaker_split65/epomaker_split65.c:34-53`, in order:

1. `debug_enable = true;` — only under `CONSOLE_ENABLE`.
2. `wls_note_boot();` — the diagnostic boot counter (one per MCU boot).
3. `eeconfig_confinfo_init();` — initialise the board's `confinfo` EEPROM block.
4. `rgblight_mode(...)` — **compiled out** (`RGBLIGHT_ENABLE` off).
5. **`wls_lifecycle_boot();`** — the big one; see below.
6. `keyboard_post_init_user();` — **the keymap's hook**:
   `keymaps/default/keymap.c:71-74`
   (and `nathan/keymap.c:123+`) set the RGB mode/HSV. **This is the second place
   the keymap runs**, and on `nathan` it uses `*_noeeprom` variants.
7. `rgbrec_init(confinfo.record_channel);` — the RGB-record subsystem.
8. `transaction_register_rpc(USER_SYNC_MMS, …);` — split RPC registration.

### 8.1 `wls_lifecycle_boot()` — in order (`wls/wls_lifecycle.c:39-125`)

| Order | Statement | Purpose / note |
| --- | --- | --- |
| 1 | `gpio_set_pin_output(LED_POWER_EN_PIN)` (A5) | rail pin → output |
| 2 | `gpio_set_pin_output(LED_POWER_EN2_PIN)` (A8) | rail pin → output |
| 3 | `wls_led_rail_apply()` | drives A5+A8 from `rgb_matrix_get_val() != 0` |
| 4 | `gpio_set_pin_input_high(HS_BT_DEF_PIN)` (C14) | **enables the pull-up** on the switch pin |
| 5 | `gpio_set_pin_input_high(HS_2G4_DEF_PIN)` (C15) | **enables the pull-up** on the other switch pin |
| 6 | `gpio_write_pin_low(USB_POWER_EN_PIN)` (B1) then `gpio_set_pin_output(B1)` | **"USB power on"** — low=on is an *inherited, never-measured* assumption (see notes) |
| 7 | `gpio_set_pin_input(HS_BAT_CABLE_PIN)` (A7) | shared power-present bit |
| 8 | `gpio_set_pin_input_high(BAT_FULL_PIN)` (A15) | battery-full input |
| 9 | `wireless_init();` | module UART/driver bring-up (`WIRELESS_ENABLE`) |
| 10 | `wireless_devs_change(...)` | **only if the switch pins are NOT both defined** — they *are*, so **this does not run** |
| 11 | `waitInputPinDelay();` | settle the C14/C15 pull-ups before reading (comment: a fresh `palSetLineMode` is async). Macro → `wait_cpuclock(GPIO_INPUT_PIN_DELAY)` (`platforms/chibios/_wait.h:66`) |
| 12 | `hs_mode_switch_pos();` | **first switch read** |
| 13 | `apply_switch_transport(pos, last_btdev_from_confinfo());` | the shared applier: sets host + devs from one read |
| 14 | `wls_note_boot_decision(...)` | retain the decision for the `0xA4` diagnostic |
| 15 | *(no boot-code call here)* | **deliberately absent**: the boot code is started from the RGB frame pass, not from step 33 — a schedule armed here would advance its phase before the first paint, and a boot that died before the loop started would have "shown" nothing. See §13. |
| 16 | `if (applied.kind == HSM_SWITCH_SETTLED) wls_usb_connect(applied.host == HSM_HOST_USB);` | **the USB data line is driven here** — only on a settled read |
| 17 | `post_init_timer = timer_read32();` | seeds the +100 ms re-seed |

> **Two writes to `B1` and `A5/A8` happen here, before the main loop.** The
> step-6 write to `B1` (**low**) is the "USB power enabled" claim. It is
> **undocumented in `docs/HARDWARE.md`** and appears nowhere in git history as a
> measured fact — it is inherited from the vendor port. If the boot ever fails
> *at this point*, this is the first suspect, because it is the only board-local
> write that could plausibly affect the board's own power/bus presence.

---

## 9. `protocol_post_init()` — install the host driver

`tmk_core/protocol/chibios/chibios.c:170-172`:

```c
void protocol_post_init(void) { host_set_driver(&chibios_driver); }
```

One call. Note this is a *different* driver from the wireless one: with
`CONNECTION_ENABLE`, `host_task()` (§10) can swap the active driver per host.
`host_init()` did nothing (§6 #9); this is where a driver is actually installed.

---

## 10. The steady-state loop

`quantum/main.c:48-81`, every iteration, in order:

| Order | Call | Source | What it does here |
| --- | --- | --- | --- |
| 1 | `protocol_pre_task()` | `chibios.c:174-203` | drains the USB event queue; the suspend path is **compiled out** by `NO_USB_STARTUP_CHECK` |
| 2 | `keyboard_task()` | `quantum/keyboard.c` | matrix scan, layer/key processing, **`host_task()`** (driver swap + our `connection_host_changed_kb`) |
| 3 | `protocol_post_task()` | `chibios.c:205-210` | `usb_idle_task()` (no VirTSer) |
| 4 | `raw_hid_task()` | quantum | `RAW_ENABLE` on — **this is the `0xA4` path** |
| 5 | `housekeeping_task()` | `quantum/keyboard.c:428-432` | `_modules()` → **`_kb()`** → `_user()` |

**Our per-loop work is in two places:**
- `housekeeping_task_user()` (`epomaker_split65.c:147-162`) → `wls_lifecycle_housekeeping()`.
  This is the loop where the +100 ms re-seed, the LED rail, and the USB edge
  block live (the exact contents differ between the mapped revision and the
  owner arc — see §11).
- `protocol_pre_task()`'s event drain → `notify_usb_device_state_change_kb()`
  (only in the owner arc; at the mapped revision this hook is upstream's default).

**`host_task()`** (`tmk_core/protocol/host.c:136-146`) compares
`connection_get_host()` to the active host and swaps drivers on change. With
`CONNECTION_ENABLE`, a host change is what fires
`connection_host_changed_kb()` — the hook the board uses for its USB-line side
effects.

---

## 11. What the **owner arc** changes in this boot (now applied to the tree)

The arc replaces the single-applier boot with one **transport owner** plus a
**module gate**. Boot-path regions that change:

1. **`wls_lifecycle_boot()` steps 12-16** become: `wls_transport_decide(WLS_TRANSPORT_INPUT_HINT)`
   — the owner computes the hint decision, commits it, and drives the USB line
   itself if the decision changed (see `wls/wls_transport.c`). The direct
   `apply_switch_transport(...)` call is gone.
2. **`keyboard_post_init_kb` / `epomaker_split65.c`** gains
   `notify_usb_device_state_change_kb()` (the event hook) and empties
   `connection_host_changed_kb()`.
3. **`wls_lifecycle_housekeeping()`** — the polled USB edge is replaced by the
   event feed.
4. **A readiness gate**: `wls_lifecycle_boot()` calls `wls_transport_ready()` and
   `wls_module_ready()` immediately after `wireless_init()`, because the event
   hook is reachable from `protocol_setup()` (§3) — long before the module
   exists.

**The ordering hazard this closes (2026-10-13, resolved):** the hook fires from
`protocol_setup()` → `usb_device_state_init()` with `INIT`. Before the readiness
gate, the owner acted on it: `decide()` → `commit()` → `wireless_devs_change()` →
`md_devs_change()` → `smsg_push()` → `memcpy(NULL, ...)`, because the module's
ring is zeroed statics until `wireless_init()` runs at step 33. That is a
HardFault inside `protocol_setup()`, i.e. the MCU resets before `keyboard_init()`
and the board pulls up D+ and goes mute — the deterministic "dead half" of that
day. Head of the arc now: **no effect may run before its dependencies exist**, so
the owner refuses to act until ready, and the module refuses a device-index
change until ready. See §13 item 0.

**Second hazard this closes (same day):** the boot and +100 ms sites originally
drove the line from an *unconfirmed* hint decision — with the switch reading
2.4 GHz (the C14/C15 pin lie), that was `wls_usb_connect(false)` at boot, cutting
the line that would have let a host confirm. Unconfirmed inputs may now **only
promote**; demotion belongs to confirmed events (the switch edge and the USB
lifecycle hook). §13 item 0.

Note **size is not a discriminator** between builds — compare sha256.

---

## 12. Diagnostics this map enables

Each observable now maps to a boot region, so a single flash can localise a
fault instead of prompting a guess:

| Observable | Region reached | Region NOT reached |
| --- | --- | --- |
| `342d:dfa0` DFU appears | bootloader (§1) | — |
| Host logs `new full-speed USB device number N` only | `protocol_pre_init()` step 2 (§5) | end of `keyboard_init()` (§6), all of §8 |
| Host logs `New USB device found` then `disconnect` | full boot; fault is **after** init | — |
| Full enumeration + all interfaces | entire boot succeeded | — |
| Board dark but enumerates | boot ok; only RGB value is 0 (§8.1 step 3) — *not* a fault | — |

**The unmapped gap:** there is currently **no instrumentation between §5 and
§8**. If the fault is in `keyboard_init()` steps 1-33, or in
`keyboard_post_init_kb()` steps 1-4 (before `wls_lifecycle_boot()`), nothing in
the firmware reports it and no host-visible signal exists until enumeration
succeeds or fails. Proving "we reached `main()` / reached step N" needs a
breadcrumb written early (e.g. an LED or a pin) — that is a *change*, not part of
this map.

### 12.1 The 2026-10-13 field reading, against this table

A flash of the owner build left the left half dark and non-enumerating. Read
against the table, and with the artifact's own timestamps:

- The observed signature is **`new full-speed USB device number N` and nothing
  else** — no `New USB device found`, no interface binds, no `USB disconnect`,
  zero `-71`, zero over-current. By the table that reaches `protocol_pre_init()`
  step 2 (§5) and **not** the end of `keyboard_init()`. So the fault is a device
  that pulled up D+ and then went mute somewhere in **`keyboard_init()`**.
- **The failure is deterministic, not intermittent.** Seven enumeration attempts
  across two replug sessions (devices 18, 20, 21, 24, 27, 29, 30) produced
  **zero** `New USB device found`. The one full enumeration seen that day
  (device 16, `342d:e4c6`, all interfaces bound) is **not** this build:
  `/tmp/opencode/split65-nathan-owner2.bin` was written `20:50:45` and device 16
  enumerated `20:51:51` — an artifact cannot run before it is flashed, so device
  16 was the *previous* firmware.
  **Correction (2026-10-13):** an earlier reading of this same evidence called
  the fault intermittent and exonerated the owner arc. It was wrong, and the
  falsifier — the artifact's mtime versus the event time — was one `ls` away.
  The failure is deterministic and the owner arc is the prime suspect.
- **The owner arc's only change inside `keyboard_init()` is step 33**
  (`keyboard_post_init_kb()` → `wls_lifecycle_boot()`); steps 1-32 are upstream
  and untouched. That is where to look, and the HEAD control build
  (`/tmp/opencode/split65-nathan-HEAD.bin`) is the discriminator: if it also
  fails, the fault pre-dates the arc (see §13 candidates 1 and 4); if it
  enumerates, the arc is confirmed.

---

## 13. Open questions this map raises (candidates, not conclusions)

> **Resolved 2026-10-13 (the candidate is now #0 below).** The owner-arc build
> that left the board dark was traced to a fault *before* `keyboard_init()` —
> in `protocol_setup()` (step 3) — which this section had not listed, because the
> map treats §3 as fixed upstream. It is a board hook firing that early, so it
> belongs here. See #0.

0. **RESOLVED — `protocol_setup()` fires the USB hook before the wireless module
   exists, and the board's hook performs an effect.** This was the 2026-10-13
   dead-board fault, and it is deterministic (seven attempts, zero enumerations).
   `protocol_setup()` (step 3) calls `usb_device_state_init()`, which fires
   `notify_usb_device_state_change()` → the board's
   `notify_usb_device_state_change_kb()` hook. In the owner arc that hook fed the
   transport owner, whose commit path calls `wireless_devs_change()` →
   `md_devs_change()` (unconditional) → `md_send_devctrl()` → `smsg_push()`.
   The `smsg` ring buffer is initialized only by `md_init()` via
   `wireless_init()`, which runs at `wls_lifecycle_boot()` (step 33) — far later.
   `smsg_push()` on the uninitialized ring dereferences its NULL buffer and
   **HardFaults the MCU before the main loop**, so the board pulls up D+ and goes
   mute: exactly the observed single `new full-speed USB device number N`.
   (Reproduced on the host: the same pointer arithmetic segfaults. See the
   board's `notify_usb_device_state_change_kb`.)
   **Fix:** the transport owner performs no effect until the board declares it
   ready (`wls_transport_ready()`, called right after `wireless_init()`), gated
   by the pure, tested `hsm_transport_may_act(ready)`. Gating the component that
   owns the effect makes every caller safe, present and future.
   **Corollary for this map:** *any* board hook reachable from `protocol_setup()`
   and earlier runs before `keyboard_init()`, before EEPROM (`confinfo`) is read,
   and before the wireless module is initialized. A hook that performs an effect
   there is wrong; one that only records an input is fine.

0b. **RESOLVED — the boot sites drove the USB line from an *unconfirmed* hint
   decision, which cut the line a host needed to confirm the transport.**
   With the switch reading 2.4 GHz (the C14/C15 pin lie; `docs/HARDWARE.md`),
   `wls_lifecycle_boot()` and the +100 ms post-task called the owner, got a
   2.4 GHz commitment, and issued `wls_usb_connect(false)` — tearing down the
   data line before any host could enumerate, so no `CONFIGURED` event could
   ever arrive to let a confirmed host outrank the lying switch. The device
   then alternately enumerated and detached (the host's retry storm, with
   `-71` bursts), and typed nothing because HID was routed to the CH582F module
   over the UART rather than to the host. **A decision whose own effect
   destroys its own trigger** — the fourth instance of the session's dominant
   error class.
   **Fix:** the decision carries its *input class*
   (`WLS_TRANSPORT_INPUT_HINT` / `_CONFIRMED`), and the owner drives the line
   itself in one place, direction-correct by construction — an unconfirmed hint
   may only **promote** (turn the line on, which is idempotent); **demotion**
   belongs to confirmed events (the switch edge and the USB lifecycle hook).
   Pure rule: `hsm_transport_may_drive_line(decision_is_usb)`.
   **Corollary for this map:** the two directions of a destructive actuator are
   not symmetric. Only the confirmed owner of a state may command its loss.

1. **The `SPLIT_USB_DETECT` poll can self-disconnect** — §7: with `USB_VBUS_PIN`
   undefined, `is_keyboard_master_impl()` runs a **~2 s blocking poll** of
   `usb_connected_state()` inside `keyboard_init()` step 4, and calls
   **`usb_disconnect()`** if it times out. That is a live candidate for
   "attached, then mute": it detaches the device during init. It also predicts a
   distinguishing detail — a boot that succeeds via this path should show the
   device appearing only *after* roughly two seconds, not immediately. Whether
   the poll sees USB up depends on how far `protocol_pre_init()` (§5) has got;
   the 50 ms unconditional wait there is the only head start.
   *Status: not the 2026-10-13 fault — HEAD has this poll and enumerates, and
   HEAD's boots appeared within the same second, not after ~2 s. Still an open
   latent risk.*
2. **`USB_POWER_EN_PIN` (B1) polarity is unverified** — §8.1 step 6 drives it low
   and calls that "on". No measurement exists: `docs/HARDWARE.md` records `A7`,
   `A15` and `B9` but not `B1`, and `git log -S 'USB_POWER_EN'` finds nothing, so
   "low = on" is an *inherited* assumption from the vendor port, not a measured
   fact. It is the only board-local write before the main loop that could affect
   the board's own bus presence, so if it is inverted, "on" powers the board
   down. *Status: not the 2026-10-13 fault — HEAD drives `B1` identically and
   enumerates.*
3. **`connection_init()` reads EEPROM before our layer runs** (§6 #8), and
   `split_pre_init()` decides mastery before it (§7). Any transport assumption
   made in `wls_lifecycle_boot()` is therefore made *after* upstream has already
   acted on persisted state.
4. **Enumeration is concurrent with `keyboard_init()`** (§5: `USB_WAIT_FOR_ENUMERATION`
   is not defined, so the firmware never waits for the host). So "started
   enumerating, then stopped" is exactly the signature of a crash anywhere in §6
   or §8 — it does not localise further on its own.
