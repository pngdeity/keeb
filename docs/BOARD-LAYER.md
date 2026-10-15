# Board layer — target architecture

Status: **design (2026-10)**. The rewrite is in progress; this is the target the
slices move toward. It is the counterpart to `docs/AUDIT.md` (which records the
per-defect work) and it supersedes nothing — the audit's four-part shell test
still binds every function.

## Why this document exists

`epomaker_split65.c` is 1,434 lines, ~44 top-level functions, and no internal
boundary. It mixes six unrelated concerns (EEPROM, split sync, USB power,
indication, keymap, lifecycle). Every defect this project has found — 7, 8,
both C.6 bugs, 9 — lived in that file or its siblings in `wls/`, and the shell
is the one layer we can only *compile*, never *test*.

The pure cores are done and proven. This rewrite finishes the job: give the
shell the same treatment the cores already have — a concern per module, a
stated interface, and (where the concern owns state) a pure core behind it.

## Principles (unchanged, stated for the target)

1. **Functional core, imperative shell.** A decision lives in a pure function
   with a test; the shell only selects effects and applies the result. The
   shell holds no policy.
2. **One authority per state.** One writer, or the state is derived. No two
   variables kept in lockstep by convention.
3. **Rule stated once.** Any idiom at more than one site is a defect — collapse
   it to one exported function.
4. **Effect on a transition, never on time.** An effect that re-derives its own
   trigger each loop is the defect-8 shape unless the periodicity *is* the rule
   (then it is named).
5. **Dependency direction is one-way.** `board → {wls concerns} → {pure cores,
   upstream}`. A concern never reaches back into the board glue, and never into
   another concern's state.

## The concerns (six, from the measured file)

| Module | Owns | Pure core behind it |
|---|---|---|
| `wls_eeprom` | `confinfo` storage: read/default/update, the version gate, `usart_init` | none (storage; the *encoding* is a struct) |
| `wls_transport` | the transport decision: the one owner of the committed host/devs pair, the input rule (the switch is authoritative; the cable is a power fact), and the USB line drive | `transport_logic` (`hsm_input_rule`, `hsm_switch_apply`, `hsm_transport_changed`, `hsm_host_present_on_notify`, `hsm_transport_may_act`, `hsm_transport_may_drive_line`) |
| `wls_module` | the wireless module's lifecycle: owns "the module is up" and refuses a device-index change before it — the board's view of the vendor `devs` index | `transport_logic` (`hsm_module_may_act`) |
| `wls_split` | the `USER_SYNC_MMS` RPC: master→slave sync, the slave handler | the sync *payload* construction (pure, testable) |
| `wls_usb` | the USB data line: `wls_usb_connect`, power connect/disconnect, the settled cable read | none (a two-state actuator) |
| `wls_indicator` | every LED: rail apply, channel flash, battery blink, caps/winlock, `hs_reset_settings_user`, and the boot code (the matrix's arbitration owner while it plays) | `boot_code_logic` (`wls_boot_code_counts`, `wls_boot_code_at`, `wls_boot_code_frame_ms`), `indicator_logic` |
| `wls_keymap` | wireless keycodes, long-press, filp | `transport_logic` (`hsm_*`), `keymap_logic` (`filp_*`) — **already done** |
| `wls_lifecycle` | the QMK hooks themselves: `keyboard_post_init_kb`, `suspend_*`, `housekeeping_task_user`, `wireless_post_task`, `lpwr_*_hook` | the boot/housekeeping *sequence* (pure: given state → what to do) |

`epomaker_split65.c` keeps **only** the QMK-mandated entry points. Each becomes
a one-to-five-line delegate to the concern that owns the work. That is the
"imperative shell boundary": QMK calls the board; the board calls the concerns.

## The invariant that makes it provable

The reason the last three sessions could not root-cause the USB bug is that the
shell has **no observability seam**: no host console, USB raw-HID is the broken
channel, and the radio push is gated on connection state. The bisect found no
behavioral delta precisely because we could not *see* the firmware's own view.

So this rewrite has a fourth deliverable, equal in weight to the code split:

**`wls_diag` — a pure snapshot of the shell's observable state.**

- A pure, unit-tested encoder/decoder: `{switch_pos, devs, host, boot_count,
  usb_line, link_state}` ↔ a fixed byte layout.
- The shell captures the snapshot at defined moments and exposes it on every
  channel that happens to be up (the `0xA4` report over USB; a bounded buffer
  readable over the radio push).
- No blinking, no counting, no flash-per-iteration. One instrument, reusable for
  every future shell bug.

This is not a debug hack. It is the shell's equivalent of the pure cores' tests:
the thing that turns "only compiled" into "observable". It is why the rewrite
is worth doing now rather than later.

## Slices (each its own signed commit, behavior-preserving except where stated)

Ordered by dependency and by risk (leaf concerns first):

1. **`wls_diag` first, not last.** Build the observability seam while the code
   is still in one file and the concerns are visible; it is also the tool that
   verifies every later slice on hardware. (Pure encoder + test + exposure.)
   **DONE.** `wls/diag_logic.{c,h}` is the pure codec (`wls_diag_t`,
   `WLS_DIAG_ENC_SIZE` 10, `wls_diag_encode`/`wls_diag_decode`), tested in
   `tests/wls_diag` (4/4). The shell half is `wls_diag_gather()` (`wls.c`),
   which reads switch/devs/host/boot-count/usb-line/link-state once each; the
   snapshot rides the `0xA4` reply at `KB_BATTERY_IDX_DIAG` (11), and is decoded
   by `host/battery_polybar.py` (`DIAG:` line). A boot counter
   (`wls_note_boot()` from `keyboard_post_init_kb`) distinguishes a reset loop
   from a mere USB-line drop.
2. `wls_eeprom` — move storage out; the version gate becomes explicit. **DONE.**
   `wls/wls_eeprom.{c,h}` owns `confinfo_t`/`confinfo`, `CONFINFO_VERSION`, the
   four `eeconfig_confinfo_*` accessors, and `usart_init`. The board file keeps
   `extern confinfo` (it reads/writes fields at ~50 sites) and the RGB default
   (`rgblight_mode(buff[0])`), which the block reset used to apply; the RGB
   constant stays in the board file because the mode keycode also uses it.
   Behavior-preserving: the binary size is unchanged (63,112 B).
3. `wls_usb` — move the USB-line actuator out; **this is where the open
   self-detach bug gets a real instrument** (the diag seam from slice 1 records
   `usb_line` and `switch_pos` at boot). **DONE.** `wls/wls_usb.{c,h}` owns
   `usb_power_connect`/`usb_power_disconnect` and `wls_usb_connect`; a leaf
   concern whose caller is `connection_host_changed_kb()`. Behavior-preserving:
   build 63,120 B.
4. `wls_split` — move the sync RPC out; the payload becomes a pure function.
   **DONE.** `wls/split_logic.{c,h}` owns the protocol *rule*
   (`wls_split_decide_slave(cmd, body) -> action`, tested 6/6: 0x55 sync,
   0xAA sleep, 0xBB deliberate slave no-op, 0xCC rail, 0xDD reset, unknown ->
   NONE). The board's slave handler now *applies* the decided action; all five
   master-side senders route through one `wls_split_send(cmd, body)` primitive
   (the wire call stated once). Build 63,136 B.
5. `wls_indicator` — move every LED writer out; the sequence becomes a pure
   decision the shell executes. **DONE (rule extracted).**
   `wls/indicator_logic.{c,h}` owns the two pure decisions: the blink tick
   (`wls_blink_t`, `wls_blink_tick`/`wls_blink_arm` — the one rule the three
   near-identical loops each re-derived: interval elapsed, colour on the odd
   half-period, DONE when the counter empties) and the battery colour table
   (`wls_bat_colour_of(charging, full, level)`). Tested 5/5. The board's three
   loops now embed a `wls_blink_t` and execute the tick; the colour block is a
   `switch` over the pure result. Board file 1,376 -> 1,294 lines; build
   63,236 B. `hs_reset_settings` is left for slice 6 (it resets EEPROM/keymap
   and re-runs `keyboard_post_init_kb`, so it is not purely an indicator).
6. `wls_lifecycle` — the hooks; each becomes a delegate. **6a DONE (self-contained hooks).** `wls/wls_lifecycle.{c,h}` now owns the boot pass (`wls_lifecycle_boot`, incl. the switch seed that drives the USB line from the applied host), the suspend family, the three low-power decision points (`lpwr_is_allow_timeout`/`_presleep`/`lpwr_wakeup`), `wireless_post_task`, and housekeeping (charge-pin reads, the rail apply, the module poll); it also now *defines* `charging_state`/`bat_full_flag`. `wls/wls_split.{c,h}` owns the split wire half (the payload structs and the one `wls_split_send()`). Each QMK hook in the board file is a thin delegate. Board file 1,294 -> 1,094 lines; build 63,300 B; tests 63/63. **6b DONE (reset plan).** `wls/reset_logic.{c,h}` owns the reset *policy* as a pure ordered plan (`wls_reset_cause_t` LOCAL/REMOTE, `wls_reset_step_t` notify-peer/wipe-config/flash/rerun-boot, `wls_reset_plan_of(cause)`, tested 4/4). `hs_reset_settings_user(cause)` is now a plan executor: it performs the named steps in order. The one thing the cause changes is whether the peer is notified — a REMOTE reset must not be echoed back, which is the rule the test pins; that also removes the would-be `wls_split -> wls_lifecycle` call-back, since the slave handler now passes `WLS_RESET_CAUSE_REMOTE` into the board's own executor instead of the lifecycle module calling back. **6c DONE (keycode + indicator shell).** `wls/wls_keymap.{c,h}` owns the whole former `process_record_kb` switch (the WLS keycode chain with its `WLS_KEYCODE_EXEC` macro and deferred long-press, the MOR Ctrl-combo table, the filp effect half, `im_rgblight_increase` and the shared `wls_rgblight_modes[]` table, `wls_persist_devs`, and every RGB/rgblight/layer/HS keycode case), plus the shared `enum layers` and `keymap_is_mac_system()` in the header so the board and the keymap concern state the mac/Windows rule once. `wls/wls_indicator.{c,h}` owns the whole LED shell (the three indicator arrays as a module-local `wls_rgb_indicator_t`, the channel flash, the set-driven flashes, the battery blink and colour paint, `wls_indicate_devs`, the nkr colour hook, and the suppression deadline). `master_sync_mms_slave` moved to `wls_split`. `process_record_kb` is now `process_record_user()` + `wls_keymap_process_record()`; `rgb_matrix_indicators_advanced_kb` is a delegate to the indicator passes. Board file 1,094 -> **272 lines**; build **63,412 B**; tests **67/67**.
7. `wls_split`'s slave half — the last non-hook implementation in the board.
   **DONE.** `user_sync_mms_slave_handler` moved into `wls/wls_split.c` (it is
   that concern's slave end; the master half — the payload structs and
   `wls_split_send` — was already there). The handler body is unchanged (it
   applies the action the pure `wls_split_decide_slave()` returns); the board
   keeps only the `transaction_register_rpc()` registration. Board file
   272 -> 230 lines; build 63,412 B; tests 67/67.

### Faithfulness remediation (post-audit, FC/IS review)

An external-principle audit (Bernhardt's *Functional Core, Imperative Shell* and
*Boundaries*, functional-architecture.org, seanh.cc) scored the board layer
A- (90%) and named four places where policy still lived in imperative code. The
three that were worth addressing are now done:

- **`wls/rgb_key_logic.{c,h}`** — the four `QK_RGB_MATRIX_*` keycodes' threshold
  policy (the magic numbers 215/120/95/30 and the mode 29->31 step) is a pure
  `wls_rgb_key_decide(keycode, state) -> wls_rgb_key_action_t`, tested 7/7 at the
  exact boundaries. `wls_keymap.c` now supplies the live values and applies the
  returned instruction; the thresholds are named constants with a contract.
- **`wls/sleep_order_logic.{c,h}`** — the low-battery sleep-order *timing*
  (arm on first critical sight, fire once the 60 s window elapses, clear on
  recovery) was inline state in `wls_indicator_battery()`; it is now the pure
  `wls_sleep_order_tick(state, critical, now)` (same shape as `wls_blink_tick`),
  tested 6/6. The *whether* remains the pure `hsm_should_order_sleep()`.
- **`wls_eeprom_wipe_config()`** — the reset executor's `WIPE_CONFIG` step body
  (the eeconfig/rgblight/keymap/NKRO sequence) moved from `wls_lifecycle` into
  `wls_eeprom`, which already owns the board's storage; the WIPE step is now a
  one-line delegate and the lifecycle module no longer reaches into how the
  board's config is laid out.

The fourth named item (branch density in `wls_bluetooth`/`wls_2p4ghz`/`wls.c`)
was deliberately **not** addressed: those branches are the CH582F UART protocol
and devs-switching, which are genuinely effectful; forcing purity there would
require modelling the closed module (fiction), which the project forbids.

Build **63,532 B**; tests **80/80** (the two new cores add 13).

### The self-detach root cause and its remedies (measures A-D)

The USB self-detach (a USB-position cold plug enumerated, then tore its own
line down in under a second, deterministically) was root-caused by a full boot
trace rather than by hardware probing. The cause is a *representational* defect,
and the fix is in the types. The derivation, with the QMK call order, is
`docs/FINDINGS.md` "the boot switch read is un-settled, and UNKNOWN is silently
applied".

- **Measure A — indeterminacy is a value.** `hsm_switch_apply_t` is now the
  tagged variant `{ hsm_switch_read_t kind; uint8_t devs; uint8_t host; }`
  (`HSM_SWITCH_SETTLED` / `HSM_SWITCH_UNREADABLE`), matching `wls_blink_out_t`
  and `filp_action_t`. An unreadable position carries a **poisoned 0xFF**
  payload, not a zeroed one — `DEVS_USB` is 0, so a zeroed payload is
  indistinguishable from a valid USB. The input rule (`hsm_input_rule()`)
  applies nothing when the read is unreadable. Tested in `tests/transport_logic`.
- **Measure B — read after settle.** `wls_lifecycle_boot()` calls
  `waitInputPinDelay()` between enabling the switch pull-ups and the first read
  (the sleep path already used the idiom; `palSetLineMode` is asynchronous).
  This is a mitigation; Measure A is the fix.
- **Measure C — one owner for the USB line.** The shared stack's one-time
  `static bool usb_initialized` guard in `wireless_task()` was a *second*
  enforcer of the same decision (reading the resolved host on a different
  schedule from the boot seed's applied host). It covered only the case where
  `connection_set_host_noeeprom()` early-returns because the stored host already
  matches — which the board's boot seed now covers unconditionally on a settled
  read. Deleted, with its now-unused declarations in the shared stack.
- **Measure D — an instrument that survives the fault.** `wls_diag` rides the
  `0xA4` raw-HID reply, which needs the very line the fault tears down. Two
  additions: (half 1) `wls/boot_report_logic.{c,h}` retains the boot decision
  (`switch_pos`, applied `host`, `settled`) in `wls.c` and exposes it at
  `KB_BATTERY_IDX_BOOT_REPORT` → now `KB_BATTERY_IDX_BOOT_CODE` (21), so the *next* successful reply is a
  post-mortem; (half 2) `wls/boot_blink_logic.{c,h}` blinks the same record over
  the LEDs with no host at all — the schedule comes from the pure
  `wls_boot_report_blink_step()` (step 0 switch position, step 1 applied host,
  step 2 settled-ness: one white pulse settled, three red unsettled). The
  sequencer is a pure time-driven walk; the indicator arrays hold flashes
  *concurrently*, so an in-sequence blink needed its own core. Both halves are
  tested (7/7 each).

  > **SUPERSEDED (2026-10-14).** The blink half was replaced by the Dell-style
  > `(amber, white)` boot code (`wls/boot_code_logic`), and the retained-record
  > half moved into `wls/wls.h`; `boot_report_logic` and `boot_blink_logic` are
  > deleted. The index is now `KB_BATTERY_IDX_BOOT_CODE` (21). See
  > `docs/FINDINGS.md` "the boot instrument is a Dell-style `(amber, white)` code".

The through-line: an input read that is sampled once, un-settled, and whose
indeterminate state is silently mapped to a plausible value is a defect *class*.
Expressing indeterminacy in the type is what stops the next one.

Build **64,228 B**; tests **96/96** (the four new cores add 16).

After every slice: build clean, all tests pass, `bin/test-sanitized` clean,
`format-c -n` clean, lint unchanged.

## Definition of done

- `epomaker_split65.c` is hooks-only (target: under ~200 lines).
- Every concern has a header that states its interface and states what it owns.
- Every rule that can be pure is pure and tested; the shell selects effects.
- `wls_diag` exposes the shell's state on the `0xA4` report, with a test for the
  codec and a host tool to read it.
- The open USB-detach bug is root-caused **with** the seam, not by blinking.
  **DONE** — the boot trace found it (an un-settled switch read silently mapped
  to the persisted BT index), the fixed types make it unrepresentable
  (measures A–D), and the seam now has a second exporter that does not ride the
  line under test. Hardware confirmation is the remaining step.
- Every state the **user** must be able to infer is a state the machine
  *exposes* — the user-facing contract (`docs/UX-REQUIREMENTS.md`) is a contract
  on this layer's state machine, not on its rendering. A state the firmware
  collapses (e.g. "connected" for a link that carries no input) cannot be
  indicated honestly by any renderer; the fix belongs here, not in the LEDs.
