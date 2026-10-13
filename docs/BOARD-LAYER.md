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
| `wls_split` | the `USER_SYNC_MMS` RPC: master→slave sync, the slave handler | the sync *payload* construction (pure, testable) |
| `wls_usb` | the USB data line: `wls_usb_connect`, power connect/disconnect | none (a two-state actuator) |
| `wls_indicator` | every LED: rail apply, channel flash, battery blink, caps/winlock, `hs_reset_settings` | the indicator *sequence* (pure: given events → what to paint) |
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
   `WLS_DIAG_ENC_SIZE` 6, `wls_diag_encode`/`wls_diag_decode`), tested in
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
5. `wls_indicator` — move every LED writer out; the sequence becomes a pure
   decision the shell executes.
6. `wls_lifecycle` — the hooks; each becomes a delegate.
7. `wls_keymap` — already split; only the hook wrappers move.

After every slice: build clean, all tests pass, `bin/test-sanitized` clean,
`format-c -n` clean, lint unchanged.

## Definition of done

- `epomaker_split65.c` is hooks-only (target: under ~200 lines).
- Every concern has a header that states its interface and states what it owns.
- Every rule that can be pure is pure and tested; the shell selects effects.
- `wls_diag` exposes the shell's state on the `0xA4` report, with a test for the
  codec and a host tool to read it.
- The open USB-detach bug is root-caused **with** the seam, not by blinking.
