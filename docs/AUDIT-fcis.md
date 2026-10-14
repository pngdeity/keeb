# The FC/IS audit — verdicts, per module

**This is the Stage 2 working record.** The governing plan is
`docs/PLAN-fcis-audit.md`; the values V1–V10 and their measurements are defined
there and are not repeated here. This file records, for each audited module, the
verdict against those values, the measurement actually used, and for each
violation either the fix applied or a recorded decision to leave it with the
reason.

Method: depth-first, cores before shells, in dependency order. A verdict is only
written after the measurement named in the plan has been run — not after a read.

## The audit set (confirmed against `git status`, 2026-10-14)

Root repo dirty: `AGENTS.md`, `TODO.md`, `docs/BOARD-LAYER.md`, `docs/FINDINGS.md`,
`docs/HARDWARE.md`, `docs/RUNBOOK-flash-and-measure.md`, `host/battery_polybar.py`,
the `qmk_firmware` gitlink, plus untracked `docs/ADR-transport-authority.md`,
`docs/BOOT-SEQUENCE.md`, `docs/INDICATORS.md`, `docs/PLAN-fcis-audit.md`.

Submodule dirty: `epomaker_split65.c`, `keymaps/default/keymap.c`, the deleted
`wls/boot_blink_logic.{c,h}`, `wls/boot_report_logic.{c,h}` and their two test
directories, `wls/diag_logic.{c,h}`, `wls/transport_logic.{c,h}`, `wls/wls.c`,
`wls/wls.h`, `wls/wls.mk`, `wls/wls_2p4ghz.c`, `wls/wls_battery.c`,
`wls/wls_bluetooth.c`, `wls/wls_eeprom.{c,h}`, `wls/wls_indicator.{c,h}`,
`wls/wls_keymap.c`, `wls/wls_lifecycle.c`, `wls/wls_split.c`, `wls/wls_usb.{c,h}`,
`platforms/chibios/boards/GENERIC_WB32_FQ95XX/board/board.c`, plus untracked
`wls/boot_code_logic.{c,h}`, `wls/wls_module.{c,h}`, `wls/wls_transport.{c,h}`,
`tests/boot_code_logic/`.

Userspace: `keymaps/nathan/keymap.c`.

**Not in the audit set:** the untouched vendor stack and upstream QMK. Only the
boundary where our code meets them is audited, and it must be named explicitly.

---

## The pure cores

These are the modules where V1–V3 are the whole point, and they must be proven by
execution rather than asserted.

### `wls/transport_logic.{c,h}`

**Measurement run.** `gcc -std=c11 -Wall -Wextra -c transport_logic.c` with no
include path at all: **compiles clean, zero warnings.** `nm -u` on the resulting
object: **no undefined symbols.** The only `#include` is its own header. The
externally-visible symbols are all `hsm_*` functions taking plain values.

| Value | Verdict | Evidence |
| --- | --- | --- |
| V1 dependency direction | **HOLDS** | Compiles and links standalone for the host; `nm -u` empty; single include (own header). |
| V2 explicit inputs/outputs | **HOLDS after F2** | `hsm_link_restart` now returns `hsm_link_timers_t` (was `void` + out-pointer). `hsm_link_watch` keeps its `hsm_link_timers_t *timers` parameter by recorded decision — it is the pure step function of an explicit state struct and already returns the decision. |
| V3 decision/effect separation | **HOLDS** | No effect performed; every function returns a decision value or a plain derived value. |
| V4 shell holds no policy | n/a (this is the core) | — |
| V5 deep modules | **HOLDS after F1** | The redundant forward declaration of `hsm_switch_pos_of_mode` at `transport_logic.c:24-27` was deleted; the `.c` includes its own header at line 4. Verified: the symbol now occurs exactly twice in the `.c` — the definition at `:181` and a comment at `:200`. |
| V6 seam per non-determinism | **HOLDS** | No clock, pin, EEPROM or USB call anywhere; `now` is a parameter; the host build is the enabling point and it works (see measurement). |
| V7 parse, don't validate | **HOLDS (with a note)** | `hsm_switch_pos_of_mode`/`hsm_switch_pos_of_hs_mode` are the two parsers from raw mode bytes to `hsm_switch_pos_t`; the two vocabularies are kept distinct by name. The BT range check `>= BT1 && <= BT5` appears five times, but each is a *derivation from a value already typed as a device index*, not a re-validation of raw input — acceptable, though it is a candidate for one `hsm_devs_is_bt()` helper. |
| V8 illegal states unrepresentable | **HOLDS** | `hsm_switch_pos_t` and `hsm_link_state_t` are enumerations; `hsm_switch_apply_t` is a tagged-kind struct so an unreadable read cannot carry a `devs`/`host` pair; every `switch` has an explicit `default`. |
| V9 error kernel | **HOLDS** | No dynamic allocation, no unbounded loops; `hsm_deadline_reached` is wrap-safe by signed difference. |
| V10 fitness function | **HOLDS** | `tests/transport_logic` (34 tests) executes this core on the host; V1 is enforced by the compile-alone measurement above. |

**Findings / work items.**

1. **V2 — `hsm_link_restart`.** **FIXED (F2).** It now returns
   `hsm_link_timers_t`, so the single caller in `wls/wls.c` reads
   `hs_link_timers = hsm_link_restart(hs_link_state(), timer_read32(), HS_LBACK_TIMEOUT, HS_SLEEP_TIMEOUT);`
   and cannot forget to persist the deadlines. `hsm_link_watch` is **left as-is**
   by recorded decision — it is the pure step function of an explicit state
   struct, and returning a struct-of-timers plus an action would need a nested
   struct for no gain.
2. **V5 — the duplicate declaration at `transport_logic.c:24-27`.** **FIXED (F1)** —
   deleted. It was dead: the file includes its own header.
3. **V7 — the repeated BT range check.** Five occurrences of the same predicate.
   **Decision: leave for now**, recorded: consolidating it is a readability
   change with no behavioural effect, and the audit's job is to fix violations of
   the values, not to churn. It is listed as a candidate in `TODO.md`.
4. **V10 — `hsm_link_restart` had no test.** **FIXED** — the F2 change exposed
   that no test exercised it at all (grepping `tests/transport_logic/` gave zero
   hits). A test was added: `TEST_F(TransportLogic, link_restart_returns_active_deadline_only)`,
   asserting DISCONNECTED→only `reconnect_at`, CONNECTED→only `sleep_at`, and
   `HSM_LINK_NONE`/`HSM_LINK_PAIRING`→both zero. The suite is now **35/35**.

### `wls/boot_code_logic.{c,h}`

**Measurement run.** Same measurement: compiles clean standalone, `nm -u` empty,
single include. Every function takes values and returns a value or a plain struct.

| Value | Verdict | Evidence |
| --- | --- | --- |
| V1 | **HOLDS** | Compiles/links standalone; `nm -u` empty. |
| V2 | **VIOLATED (1 site)** | `wls_boot_code_encode` returns `void` and writes an `out` buffer. This one is *necessary*: the output is a byte array of fixed size and returning a 2-byte struct then memcpy'ing would be worse. **Decision: leave, recorded.** |
| V3 | **HOLDS** | The core returns a *description* of what to paint (`wls_boot_code_out_t` with a phase and a colour); it paints nothing. |
| V4 | n/a | — |
| V5 | **HOLDS** | The interface is small and the timing/sequencer complexity is hidden behind `wls_boot_code_at`/`wls_boot_code_show_ms`. No duplicate declarations. |
| V6 | **HOLDS** | `now_ms` and `origin_ms` are parameters; no clock call. Measured by the host build. |
| V7 | **HOLDS** | The codec parses boot facts into counts once; the sequencer takes counts. No repeated validity checks (values are clamped once, at `wls_boot_code_counts`). |
| V8 | **HOLDS (with a note)** | `wls_boot_code_phase_t` is a 2-state enum; the "nothing lit" case is the explicit named `PHASE_DARK`, not a fall-through. Stages are the enum. **Note:** `wls_boot_code_t.stage`/`code` are `uint8_t`, not the enum type — deliberate, so a value read from a report cannot be an out-of-range enum; the clamp in `wls_boot_code_counts` is the boundary. |
| V9 | **HOLDS** | No allocation, bounded loops (`for bit < 6`), no absent-subsystem dependence. |
| V10 | **HOLDS** | `tests/boot_code_logic` (22 tests), including `the_show_window_is_exactly_one_frame`. |

**Findings / work items.** None requiring a fix. The one `void`+out-buffer
function is recorded as an accepted exception with its reason.

### `wls/diag_logic.{c,h}`

**Measurement run.** Compiles clean standalone, `nm -u` empty, single include.

| Value | Verdict | Evidence |
| --- | --- | --- |
| V1 | **HOLDS** | Standalone compile; `nm -u` empty. |
| V2 | **VIOLATED (structural)** | `wls_diag_encode` returns a count (not `void`) — good. `wls_diag_decode` writes through `out` — necessary for a bytes→struct parse. **Decision: leave, recorded.** |
| V3 | **HOLDS** | Pure encode/decode; performs no effect. |
| V4–V6 | n/a / **HOLDS** | No ambient state; the descriptor `wls_diag_t` is passed in. |
| V7 | **HOLDS** | `wls_diag_decode` is the one parse of the `0xA4` DIAG block into a typed struct; it returns a distinct type (`bool` + filled `wls_diag_t`) from its `const uint8_t *` input, and checks `NULL`. |
| V8 | **HOLDS** | Fixed-size fields; `WLS_DIAG_ENC_SIZE` is the single source of the block length, used by both encode and the tests. |
| V9 | **HOLDS** | No allocation, bounded, explicit `NULL` guard. |
| V10 | **HOLDS** | `tests/wls_diag` (4 tests). |

**Findings / work items.** None. The encode/decode pair is the model the rest of
the boundary code should follow.

### `wls/indicator_logic.{c,h}`

**Measurement run.** Compiles clean standalone, `nm -u` empty, single include
(the file's own header). Verified again after F3 added `wls_bat_rgb_t`.

| Value | Verdict | Evidence |
| --- | --- | --- |
| V1 | **HOLDS** | Standalone compile; `nm -u` empty. |
| V2 | **HOLDS (with a note)** | `wls_blink_tick` and `wls_sleep_order_tick` take the state struct by pointer and advance it in place, returning the decision. **Recorded decision: accepted** — this is the pure *step function* of an explicit state struct: given `(state, now)` it returns what to do and advances the clock state. The alternative (return a struct containing both the new state and the decision) is equally pure; the in-place form was chosen for legibility. `wls_bat_rgb_of` takes the enum and returns the RGB, no state at all — the strict form. |
| V3 | **HOLDS** | Returns decisions (`wls_blink_out_t`, `wls_sleep_order_out_t`, `wls_bat_rgb_t`); performs no effect. |
| V4 | n/a | Not a shell. |
| V5 | **HOLDS** | Small surface, all types named in the domain (`wls_blink_t`, `wls_sleep_order_t`, `wls_bat_rgb_t`). |
| V6 | **HOLDS** | `now_ms` is a parameter; no clock read. |
| V7 | **HOLDS** | Consumes the already-parsed enum from `wls_bat_colour_of`; introduces no second interpretation. |
| V8 | **HOLDS** | `wls_blink_tick` is total over `(idle | armed, now)`; the idle case is an explicit named outcome (`WLS_BLINK_IDLE`, returns PAINT/off) rather than a fall-through. `wls_bat_rgb_of`'s `switch` has an explicit `default` returning black. |
| V9 | **HOLDS** | No allocation, no loop, no dependency on a subsystem that can be absent. |
| V10 | **HOLDS** | Covered by `tests/...` (blink arm/tick cases) and, after F3, by the colour-map assertions. |

**Findings / work items.** None. The in-place step pattern is recorded as the
accepted form rather than a violation (see V2).

### `wls/sleep_order_logic.{c,h}`

**Measurement run.** Compiles clean standalone, `nm -u` empty, single include.

| Value | Verdict | Evidence |
| --- | --- | --- |
| V1 | **HOLDS** | Standalone compile; `nm -u` empty. |
| V2 | **HOLDS (with a note)** | Same in-place step pattern as `indicator_logic` — `wls_sleep_order_tick(wls_sleep_order_t *s, bool critical, uint32_t now_ms)` returns `wls_sleep_order_out_t` and advances the armed timestamp. **Recorded decision: accepted**, for the same reason. |
| V3 | **HOLDS** | Returns HOLD/NOW; schedules nothing itself. |
| V4 | n/a | Not a shell. |
| V5 | **HOLDS** | Two outcomes and one timestamp; the interface is much smaller than the timing it hides. |
| V6 | **HOLDS** | `now_ms` is a parameter; `critical` is a parameter. No ambient read. |
| V7 | **HOLDS** | `critical` arrives as a `bool` already decided by the caller; no raw re-interpretation. |
| V8 | **HOLDS** | Total over `(critical, armed/not)`: clears when not critical, arms on the first critical tick, fires after the window and resets. `WLS_SLEEP_ORDER_IDLE` (`armed_ms == 0`) is the explicit "not armed" state. |
| V9 | **HOLDS** | No allocation, no loop. |
| V10 | **HOLDS** | The arm-window and fire-after-window cases are exercised in the suite, including the low-battery sleep-order test. |

**Findings / work items.** None. Note the deliberate boundary: the predicate
*"whether to sleep at all"* is **not** here — it is the pure
`hsm_should_order_sleep()` in `transport_logic`. This file owns only the *order*
(the delay between the decision and the action), which keeps the two concerns
from leaking into each other.

### `wls/wls_indicator.{c,h}` — the instrument shell

This is the shell for the boot code, the channel flash, the battery indicator and
the charge-state LED. It is where V3/V4 are most at risk, because "paint the LED"
is an effect and there is a lot of it.

**Measurement run.** Read in full; the pure decisions it uses
(`wls_blink_tick`, `wls_blink_arm`, `wls_sleep_order_tick`,
`wls_bat_colour_of`, `wls_boot_code_at`, `wls_boot_code_counts`,
`wls_boot_code_show_ms`, `hsm_should_order_sleep`) all come from cores that
compile standalone; the shell itself adds only `rgb_matrix_set_color*` and
`timer_read32()` calls.

| Value | Verdict | Evidence |
| --- | --- | --- |
| V1 | **HOLDS (as a shell)** | It is the shell; it is *expected* to reach the driver and the clock. The check is that its core does not reach back — verified above. |
| V2 | n/a | Shells take no inputs and return nothing by design; their inputs are the world. |
| V3 | **HOLDS** | Every policy it applies comes from a core: the show window is `wls_boot_code_show_ms`, the blink timing is `wls_blink_tick`, the sleep timing is `wls_sleep_order_tick`, the colour is `wls_bat_colour_of`. The shell paints and does nothing else. |
| V4 shell holds no policy | **HOLDS after F3** | The five-way `switch` mapping `WLS_BAT_*` to RGB is gone from the shell: `wls_bat_rgb_of()` in `indicator_logic` now owns the map and the shell passes `rgb.r/g/b` through unchanged. The indicator-*selection* branch remains (see finding 2). |
| V5 | **HOLDS** | The public surface is small; the two static arrays and the blink structs hide the bookkeeping. |
| V6 | n/a | The clock is the shell's to read. |
| V7 | **HOLDS** | It consumes already-parsed values (`wls_bat_colour_of` returns the enum; no raw byte is re-interpreted here). |
| V8 | **HOLDS (with a note)** | `wls_indicate_devs` is a `switch` over the device index with an explicit `default: break` — a total mapping, good. The battery `switch` over `WLS_BAT_*` also has a `default`. |
| V9 | **HOLDS** | No allocation; bounded loops. |
| V10 | **PARTIAL** | The boot-code shell has no *unit* test (the core does, 22/22). A shell test would need the RGB driver mocked, which per V6 means the seam is in the wrong place — so the correct fitness function for the shell is not a unit test but the **ownership invariant**: `wls_indicator_boot_code_owns_matrix()` must be the gate every other painter respects. That invariant is currently enforced by *convention* in `epomaker_split65.c`'s paint pass, not by a check. |

**Findings / work items.**

1. **V4 — the battery colour mapping is policy in the shell.** The five-way
   `switch (wls_bat_colour_of(...))` → `r/g/b` at `:148-169` decides *what colour
   to paint* from a domain enum. The core already says *which* colour
   (`WLS_BAT_GREEN` etc.); the shell re-derives RGB. **Fix:** the colour→RGB map
   belongs in a core (or as constants beside the enum), so the shell only passes
   the RGB through. (See the fix list.)
2. **V4 — the indicator-arming branch** at `:171-192` chooses between four
   mutually exclusive indicator actions and a `wls_order_sleep` call. Some of
   this is unavoidable (it must call the effect), but the *choice* of which is
   policy. **Decision: partially leave, recorded** — the branch is a total
   mapping over `(charging, full, level-band)`, and extracting it to a core that
   returns an action enum is the right fix but a larger change than this pass.
   Recorded as a Stage-3 candidate so the choice is not silently forgotten.
3. **V10 — the boot-code ownership invariant has no check.** **Fix:** none
   required in code (it is a contract between modules); recorded so the next
   person knows the enforcement is by convention and where.

---

## Fix list (Stage 2, cores complete)

| # | Module | Value | Fix | Status |
| --- | --- | --- | --- | --- |
| F1 | `transport_logic.c` | V5 | Delete the redundant forward declaration of `hsm_switch_pos_of_mode` at `:24-27`. | **DONE** — verified: the symbol occurs exactly twice in the `.c` (definition `:181`, comment `:200`). |
| F2 | `transport_logic.{c,h}` | V2 | `hsm_link_restart` returns `hsm_link_timers_t` instead of writing through the pointer. | **DONE** — the single caller in `wls/wls.c` updated; `hsm_link_watch` keeps its out-parameter by recorded decision. |
| F3 | `wls_indicator.c` | V4 | Move the `WLS_BAT_*` → RGB mapping out of the shell. | **DONE** — `wls_bat_rgb_of()` now owns the map; the shell passes `rgb.r/g/b` through unchanged. |
| F4 | `tests/transport_logic` | V10 | `hsm_link_restart` had no test at all (found by F2). | **DONE** — `TEST_F(TransportLogic, link_restart_returns_active_deadline_only)` added; suite now 35/35. |
| F8 | `wls/wls.c` → `boot_code_logic` | V3/V4/V10 | Extract the boot-stage precedence from the shell into a pure `wls_boot_facts(in, reset_cause, boot_count)`. | **DONE** — core precedence + `wls_boot_inputs_t` + `WLS_BOOT_HOST_*`; shell reduced to `wls_boot_code_now()`; 8 new tests (suite 30/30); build clean 63.3 KB. |
| F6 | `transport_logic.{c,h}` / `wls_eeprom.c` | V4/V7 | The "is a BT index" range test was spelled out at five core sites plus the shell, each with its own fallback literal; the EEPROM recovery rule and the confinfo migration gate lived in the store shell. | **DONE** — one predicate (`hsm_devs_is_bt`) + `hsm_btdev_or(devs, fallback)` with the fallback kept a per-site parameter; `hsm_confinfo_needs_default`; all six sites routed through it, fallbacks unchanged; shell reduced to reading fields. Suite 43/43. |
| F5 | tree-wide | V10 | No mechanical guard on the transport invariants (a single `wls_usb_connect` call site; the suspend hook must not drive the line). | **DONE** — `bin/guard-invariants`, wired into CI; proven to fail on an injected second call site and to pass when restored. |
| F7 | `transport_logic.c` / `module.h` | V10 | The core's `HSM_DEVS_*` copies can drift silently from the vendor `DEVS_*` enum. | **DONE** — the F7 guard in `bin/guard-invariants` parses the vendor enum and compares every `HSM_DEVS_*`; proven to fail on a corrupted value. |
| F9 | `tests/wls_diag` + `tests/boot_code_logic` + `host/battery_polybar.py` | V10 | The `0xA4` layout is a contract by convention across C and Python; nothing failed when they diverged (the host's `BOOT_STAGE_NAMES` was already two stages short). | **DONE** — one golden vector asserted by both sides: `golden_vector_diag_block_matches_the_host_fixture`, `golden_vector_boot_code_pair_matches_the_host_fixture`, and `battery_polybar.py --self-check`; both negative tests proven (`wls_diag` 5/5, `boot_code_logic` 31/31). |
| F10 | `wls_indicator.c` → `indicator_logic` | V3/V4/V10 | The shell's charging-LED branch chose among four effects (paint red / green / blink red / nothing) inline — the last real decision in a shell. | **DONE** — pure `wls_bat_action_of(charging, full, level, request, low)` returns an action enum; the shell applies it and holds no branch; `battery_action_follows_the_replaced_branch` pins all four outcomes and the branch asymmetry. |

All ten fixes were verified together: the five cores still compile standalone
with zero warnings and zero undefined non-libc symbols; `transport_logic` 43/43,
`boot_code_logic` 31/31, `indicator_logic` 7/7, `sleep_order_logic` 6/6,
`wls_diag` 5/5; the full cross-build is clean at 63.3 KB;
`./bin/guard-invariants` passes all three structural guards and each was proven
to fail on a deliberate violation; and the `0xA4` golden vector (F9) fails on
both sides when a field or an index moves.

Deferred with a recorded reason (see `TODO.md`):
- **None remaining** — the battery-indicator *selection* branch, the last item,
  was extracted as **F10** (below).

---

## F9 — the `0xA4` golden vector (V10, the cross-language instance)

**The `0xA4` report is written in C (`wls/wls_battery.c`, via
`wls_boot_code_encode` and `wls_diag_encode`) and read in Python
(`host/battery_polybar.py:parse_reply`), and nothing failed when the two
disagreed.** This is the strongest instance of the F7 shape in the project
because the encoder and decoder are in different languages and cannot share a
header. The drift had already happened: the host's `BOOT_STAGE_NAMES` carried six
stages against the firmware's eight (`BOOTCOUNT` and `RSTCAUSE` were missing), so
the host would print `stage=?` for exactly the readings the instrument exists to
produce.

**The fix is a checked-in fixture asserted by BOTH sides**, not a link-time
check:
- **Firmware:** `tests/wls_diag/wls_diag_tests.cpp` gained
  `golden_vector_diag_block_matches_the_host_fixture`, which decodes the vector's
  diag bytes (11..20) and then re-encodes them, so a moved index fails. The
  boot-code pair (bytes 21..22) is asserted in
  `tests/boot_code_logic/boot_code_logic_tests.cpp` as
  `golden_vector_boot_code_pair_matches_the_host_fixture` (reset cause bit 4 ->
  stage `RSTCAUSE`, white 5 -> encoded `{0x07, 0x05}`). The pair lives in that
  suite because `tests/wls_diag/test.mk` compiles only `diag_logic.c`.
- **Host:** `host/battery_polybar.py` gained the vector as a literal
  (`GOLDEN_VECTOR`, 23 bytes), the expected decode (`GOLDEN_EXPECTED`), and
  `check_golden_vector()`, exposed as `--self-check` (no hardware needed). The
  host's `BOOT_STAGE_NAMES` was completed to all eight stages as part of the fix.
- **The vector:** byte 0 is `0xA4` (the reply echoes the command; a zero byte
  makes `parse_reply` return `None`), then a battery snapshot, a diag block of
  non-trivial values, and the boot pair `{0x07, 0x05}`.

**Verification (both negative tests run):** mutating a host field -> `self-check
FAILED: charging: decoded 9, expected 1`, `rc=1`; mutating a firmware index
(`out[0] = d->devs`) -> `wls_diag` drops to `FAILED 4 tests` (the golden-vector
test among them); both restored -> `self-check OK` and `5/5` + `31/31` green.
`clang-format` clean on both test files; `python3 -c "ast.parse(...)"` OK.

---

## F7 — the duplicated device-index vocabulary (V10, a real finding)

**Found while preparing F6, and it is larger than the "five repeated range
checks" this doc previously recorded.**

The device-index fact (`DEVS_USB = 0`, `DEVS_BT1..BT5 = 1..5`, `DEVS_2G4 = 6`) is
written down **three times**:

| Site | Form |
| --- | --- |
| `keyboards/linker/wireless/module.h:7-15` | the real enum — `enum { DEVS_USB = 0, DEVS_BT1, … DEVS_BT4, DEVS_BT5, DEVS_2G4 }` |
| `wls/transport_logic.c:8-13` | private copies — `#define HSM_DEVS_USB 0`, `HSM_DEVS_BT1 1`, `HSM_DEVS_BT2 2`, `HSM_DEVS_BT3 3`, `HSM_DEVS_BT5 5`, `HSM_DEVS_2G4 6` |
| `tests/transport_logic/transport_logic_tests.cpp:36-37` | a third copy — `DEVS_USB = 0, DEVS_BT1 = 1` |

**The duplication in the core is deliberate and documented.** `transport_logic.h:41`
and `:102` both say the values "match `module.h`", and the reason is V1/V6: the
core keeps its own copies so the file stays **include-free**, which is exactly what
makes it host-testable. **So this is not a violation to fix by inclusion** — that
would trade a real property (the seam) for a cosmetic one.

**The real risk is silent drift.** Two definitions must agree, and nothing fails
if they diverge: change `module.h` and the core keeps compiling, keeps passing its
tests, and is quietly wrong. That is the V10 test — a decision with no fitness
function degrades silently.

**Two things to fix, and they are different:**

- **The fitness function (the important one).** Pin the duplication with a check
  that fails on divergence: a static assert in a file that sees *both* the real
  enum and the core's copy (a board TU, not the core), or a host test that
  includes `module.h` and asserts `HSM_DEVS_* == DEVS_*`. A static assert is
  preferable: it costs no runtime and cannot be skipped. `TODO.md` item.
- **The `HSM_DEVS_BT4` gap — investigated, and it is benign but *by luck*.** The
  core's define list jumps `BT3 → BT5`; `HSM_DEVS_BT4` does not exist. Checked
  whether any core path needs it: **no, and the reason is worth writing down.**
  Every core use of a BT index is either a *range check* (`>= BT1 && <= BT5`, which
  needs only the two endpoints) or one of the four keycode→index mappings in
  `hsm_long_press_devs` (`HSM_KC_BT1..BT3` and `HSM_KC_2G4`; there is no BT4/BT5
  keycode). So the core can pass BT4 *through* (it is inside every range) but never
  *needs to name* it. **That is consistent, not an off-by-one.**
  Note the contrast: our shell *does* name `DEVS_BT4` explicitly
  (`wls_indicator.c:280`, mapping it to LED `41`), and the vendor stack does too
  (`module.c:499`, `MD_SND_CMD_DEVCTRL_BT4`). So BT4 is reachable on hardware —
  `hsm_seed_btdev` can return it when the persisted `last_bt` is 4 — and the shell
  handles it. The core simply never has to spell it, because it is only ever the
  middle of a range. **Recorded, no fix needed; the static-assert check above is
  what would catch it if that ever changed.**

**Also checked while here:** `wls_indicate_devs` (`wls_indicator.c:257`) has
cases for `DEVS_BT1..BT5` and `DEVS_2G4`, and its callers
(`wls.c:263`, `wls_keymap.c:121/126/157`) pass a `devs` the core produced, so the
shell's switch and the core's vocabulary stay aligned in practice.

**Not yet decided:** where such a check lives. It cannot live inside
`transport_logic.{c,h}` — that file must stay include-free — so it belongs in the
board test suite or a board TU. Stage-3 candidate.

---

## Shells

The shells are where V3 (decision/effect separation) and V4 (no policy in the
shell) are at risk, because a shell's *job* is to touch the world. The check for
each is therefore: **does every branching decision it makes come from a core
function, and is every effect it performs named in one place?**

The include graph is the first measurement — it shows the dependency direction
(V1) structurally:

| Shell | includes cores | reaches drivers/HAL |
| --- | --- | --- |
| `wls_transport.c` | `transport_logic.h` (via `wls_transport.h`) | `wls.h`, `wls_usb.h`, `wls_eeprom.h`, `wls_module.h`, `connection.h`, `usb_util.h` |
| `wls_module.c` | `transport_logic.h` | `wireless.h`, `quantum.h` |
| `wls_usb.c` | — (no core; it *is* the raw actuator) | `usb_util.h`, `usb_main.h` |
| `wls_eeprom.c` | — (no core; it *is* the raw store) | `wls.h` (`eeconfig_*`) |
| `wls_indicator.c` | `indicator_logic.h`, `sleep_order_logic.h`, `transport_logic.h`, `boot_code_logic.h` | `quantum.h` (`rgb_matrix_*`, `timer_read32`) |

No core appears in the *right* column of another core's row: dependencies point
one way (shell → core), which is V1 confirmed at the module level rather than
only per-TU.

### `wls/wls_transport.{c,h}` — the transport owner (shell)

**Measurement run.** Read in full; the four predicates it applies
(`hsm_transport_may_act`, `hsm_transport_decide`, `hsm_transport_changed`,
`hsm_transport_may_drive_line`) are all defined and tested in
`transport_logic`; `nm`/include check above.

| Value | Verdict | Evidence |
| --- | --- | --- |
| V1 | **HOLDS** | Depends on cores and on the actuators it owns; no core depends on it. |
| V2 | n/a | Shell. Its inputs are the world (`hs_mode_switch_pos()`, `wls_usb_cable_present()`, the EEPROM), gathered at the edge as V3 requires. |
| V3 | **HOLDS — this is the exemplar** | The decision is entirely `hsm_transport_decide(hints(), host_confirmed)`; the shell adds only the *gathering* (`hints()` reads switch/cable/EEPROM) and the *applying* (`commit`, `drive_line_for`). The two effects it owns — `connection_set_host_noeeprom` + `wls_module_devs_change`, and `wls_usb_connect` — are each named in exactly one function. |
| V4 shell holds no policy | **HOLDS** | The only branch the shell makes is `if (input == HINT && !hsm_transport_may_drive_line(...)) return;` — and even that *condition* is a core predicate; the shell just executes the returned bool. The direction rule (may an unconfirmed decision demote?) is **not** in the shell. Cyclomatic complexity: `commit` 2, `drive_line_for` 2, `wls_transport_decide` 3, `wls_transport_host_event` 1. |
| V5 | **HOLDS** | Three pieces of private state (`committed`, `host_confirmed`, `ready`) and a five-function surface; the livelock the module exists to prevent is invisible from outside. The header documents the *ordering* precondition (`wls_transport_ready`) as part of the interface, which is the Ousterhout point. |
| V6 | n/a | Shell. Its non-determinism *is* the world; the core's seam is the `hints()` value it passes in. |
| V7 | **HOLDS** | `hints()` is the single place the three raw inputs are read; the core receives the already-parsed `hsm_switch_apply_t`, not the pins. |
| V8 | **HOLDS** | `committed` starts at `WLS_TRANSPORT_UNKNOWN` (0xFF, "no decision yet", which matches no `HSM_HOST_*`) — an explicit un-decided state, not a guess. `committed` is written in exactly one place (`commit`). |
| V9 | **HOLDS** | No allocation; the `ready` gate is the crash-only design — before the module exists the owner *refuses* rather than dereferencing the null ring (the 2026-10-13 fault). |
| V10 | **PARTIAL** | The *policy* is fully tested (in `transport_logic`, 35/35). The *shell* has no test, and per V6 a shell test would need the switch/cable/USB driver mocked — so the correct fitness function is not a unit test but the invariant. Two invariants are enforced structurally rather than by a check: (a) `wls_usb_connect` may only be called from `drive_line_for`; (b) nothing in the line's own state may feed the decision (`host_confirmed` is set only by events). Both are stated in the header; neither is mechanically enforced. **Recorded — a `grep`-based fitness function (e.g. "`wls_usb_connect` has exactly one call site in the tree") is the natural guard and is cheap.** |

**Findings / work items.**

1. **V10 — no mechanical guard on the single-call-site invariant.** The whole
   ADR rests on "`wls_usb_connect` is only called as the consequence of a
   decision change". That is true today (verified: `wls_usb_connect`'s only
   caller is `drive_line_for` in this file) but nothing fails if a future edit
   adds a second call site. **Recommended fitness function (F5): a test that
   asserts the call site count**, or a `make`-time `grep`. Recorded here; not
   added in this pass because it needs a decision about where such checks live
   (`tests/` vs a script) — a Stage-3 candidate.

### `wls/wls_module.{c,h}` — the module gate (shell)

**Measurement run.** Read in full; `hsm_module_may_act` verified present and
tested in `transport_logic`.

| Value | Verdict | Evidence |
| --- | --- | --- |
| V1 | **HOLDS** | Depends on the core; nothing depends inward on it. |
| V2 | n/a | Shell. |
| V3 | **HOLDS** | One effect (`wireless_devs_change`), named in one function (`wls_module_devs_change`). |
| V4 shell holds no policy | **HOLDS** | The single branch is `if (!hsm_module_may_act(ready)) return;` — the condition is a core predicate. Complexity 2. |
| V5 | **HOLDS** | Three functions, two private facts (`devs`, `ready`); hides the vendor-index bookkeeping and the null-ring hazard entirely. |
| V6 | n/a | Shell. |
| V7 | n/a | It passes an index through; no parsing. |
| V8 | **HOLDS** | `ready` is set once (`wls_module_ready`); `devs` written once (`wls_module_devs_change`). |
| V9 | **HOLDS (the crash-only gate)** | This module *is* the error-kernel discipline: it makes "too early" a no-op instead of a fault, at the actuator that would fault. |
| V10 | **HOLDS** | `hsm_module_may_act` is tested; the delay-before-ready behaviour is asserted. |

**Findings / work items.** None.

### `wls/wls_usb.{c,h}` — the raw USB actuator (shell) + one core-side fact

**Measurement run.** Read in full. Note `wls_usb_cable_present()` lives here
rather than in the shell that consumes it (see finding).

| Value | Verdict | Evidence |
| --- | --- | --- |
| V1 | **HOLDS** | Reaches the HAL/`USBD1`; no core dependency, correctly — there is no policy to extract. |
| V2 | n/a | Shell. |
| V3 | **HOLDS** | The three effects (power enable, line connect/disconnect, `restart_usb_driver`) are the whole file; each named once. |
| V4 shell holds no policy | **HOLDS (with a note)** | Two branches: the `enable` path's `if (!usb_connected_state())` (idempotence, not policy) and the disable path's `if (usb_connected_state()) return;` + `if (USB_DRIVER.state != USB_STOP)`. The second is the *monotonic actuator* guard — see finding 1; it is a real condition, but it is the actuator protecting itself from a wrong command, which is where V9 says such a guard belongs. |
| V5 | **HOLDS** | Small; hides the power-pin polarity (`low` = connect) which a caller would get wrong. |
| V6 | n/a | Shell. |
| V7 | **VIOLATED (by placement)** | `wls_usb_cable_present()` *parses* a raw pin into a `bool` fact — that is V7 work, and it is placed in the USB actuator rather than beside the other pin parse (`hs_mode_switch_pos`). It is defensible (it is a *USB* fact, as the comment says) but it means two files parse pins. **Recorded, not moved** — the placement is a deliberate, documented choice; moving it would not change behaviour and the comment already names the reason. |
| V8 | **HOLDS** | `enable` is a `bool`, so both paths are total. |
| V9 | **HOLDS** | The disable path's "a confirmed host is never torn down" guard is exactly the error-kernel principle at the actuator: it refuses a command that the confirmation proves wrong, regardless of caller. |
| V10 | **PARTIAL** | No test (it needs the USB driver mocked — a shell test, same V6 argument). The guard's *predicate* is `usb_connected_state()`, which is upstream state, so it cannot be moved to a core. Recorded. |

**Findings / work items.**

1. **V4/V9 — the two guards in `wls_usb_connect` are policy-shaped but correctly placed.** The disable-path guard ("a confirmed host is never torn down") reads like a domain rule in an actuator. It is *not* a violation: the transport owner already decided, and this guard is the actuator refusing a command that the world contradicts — the belt-and-braces the 2026-10-13 livelock earned. It is recorded so the next reader knows it is deliberate, and so that the *real* direction rule (promotion-only for hints) is not confused with it. The real rule is in `hsm_transport_may_drive_line` (core, tested).
2. **V7 — `wls_usb_cable_present` parses a pin outside the pin-parse module.** Recorded as a deliberate placement with its reason in the code.

### `wls/wls_eeprom.{c,h}` — the store (shell) + two core-side facts

**Measurement run.** Read in full; the version gate and the `last_btdev` fallback
are the two pieces of logic in it.

| Value | Verdict | Evidence |
| --- | --- | --- |
| V1 | **HOLDS** | Reaches `eeconfig_*`; no core dependency, correctly. |
| V2 | n/a | Shell. |
| V3 | **HOLDS** | The store effects are named once each. `confinfo` is the process-wide record, which is the boundary object. |
| V4 shell holds no policy | **VIOLATED (one site, small)** | `last_btdev_from_confinfo()` contains a real domain rule: *"if the persisted `devs` is a BT index use it, else fall back to the last BT device"* — a range test (`DEVS_BT1..BT5`) with a policy fallback. It reads as a parse but is actually the *recovery rule for a lying/missing persisted value*, i.e. a decision. Also `eeconfig_confinfo_init`'s version gate (`!raw \|\| version != CONFINFO_VERSION`) is a migration decision living in the shell. |
| V5 | **HOLDS** | Small surface; hides the `confinfo` struct packing. |
| V6 | n/a | Shell. |
| V7 | **PARTIAL** | `last_btdev_from_confinfo` is a *validating* read (it checks a range and substitutes), not a *parsing* one. Per V7 the parse should produce a type that cannot be wrong; here the raw field stays raw and every consumer re-checks. This is the same finding as the deferred "five repeated BT range checks". |
| V8 | **HOLDS** | `confinfo` is initialized in one place; the version gate is explicit. |
| V9 | **HOLDS** | No allocation; the default-fill path is idempotent. |
| V10 | **PARTIAL** | The version gate and the `last_btdev` fallback are not directly tested (the EEPROM is a shell dependency). Recorded. |

**Findings / work items.**

1. **V4/V7 — `last_btdev_from_confinfo` is a decision in the store shell. FIXED
   (F6).** This was the *same* class the audit already flagged (V7, "five repeated
   BT range checks"), and it is the one shell finding worth a real fix, because it
   is the policy that decides which BT device the board boots onto when the
   persisted value is missing or corrupt — a decision, not a read. The fix
   consolidated the predicate rather than the rule: `hsm_devs_is_bt()` (the range
   test, written once) and `hsm_btdev_or(devs, fallback)` (the substitution). The
   *fallback stays a parameter*, because the call sites genuinely differ — BT1
   where a BT device is required, USB where the switch said nothing, `0` where "no
   BT profile" is meant — so the shared helper does not erase each site's choice;
   it makes that choice visible. `last_btdev_from_confinfo()` is now
   `hsm_btdev_or(confinfo.devs, confinfo.last_btdevs)`, and the shell reads two
   fields and calls the core. All four former core sites (`hsm_boot_devs` twice,
   `hsm_switch_apply_with_cable`, `hsm_profile_of_devs`, `hsm_seed_btdev`,
   `hsm_keycode_allowed`) were routed through it with their fallbacks unchanged,
   so **behaviour is identical** — confirmed by the suite plus new tests pinning
   each fallback.

2. **V4 — the version gate (F6, predicate only).** `eeconfig_confinfo_init`'s
   `!raw || version != CONFINFO_VERSION` is itself pure; it is now
   `hsm_confinfo_needs_default(raw, version, current_version)`. The *action* it
   triggers (`eeconfig_confinfo_default()` → an EEPROM write) correctly stays in
   the shell that owns the store — so the fix is the decision, not the effect.
   **Recorded decision:** the write cannot move to a core by V3, and should not.

**F6 verification:** `transport_logic` suite **43/43** (was 35; +8 new cases —
the predicate bounds, the caller-supplied fallback, the four former sites
re-asserted, the EEPROM recovery rule, and the three confinfo-gate cases); the
core still compiles standalone with `gcc -std=c11 -Wall -Wextra` and **zero
undefined symbols**; full cross-build clean at 63.3 KB
(`aad6031cfdf03e9f3d3428c83a134cbb6ed9b309a986d9c9f908722254614d70`). A second
occurrence of the range test found during verification
(`hsm_keycode_allowed`'s `target_is_bt`) was consolidated in the same pass, so
**exactly one range test now exists** in the core (`hsm_devs_is_bt`'s body).

### `wls/wls_indicator.{c,h}` — verdict held above

The full verdict table for the instrument shell is above (see "the instrument
shell"); its outstanding items are the indicator-selection branch (recorded,
Stage-3 candidate) and the ownership invariant enforced by convention (recorded).

---

## Board glue

These are files we touched that are *neither* a core nor a clean shell: board
state, the boot path, the keymap dispatch, and the vendor-stack boundary. The
check is the same (V3/V4), but the expectation differs — some of this is
legitimately the composition root, where a decision *does* have to be taken
because that is the only place both halves of it are visible.

The include graph, measured the same way:

| File | includes cores | reaches |
| --- | --- | --- |
| `wls/wls.c` | `transport_logic.h` (via `wls.h`), `boot_code_logic.h` | `wls_transport.h`, `wls_usb.h`, `wls_module.h`, `wls_battery.h`, `quantum.h`, `wireless.h`, `md.h`, `lpwr.h` |
| `wls/wls.h` | — (declarations only) | — |
| `wls/wls_lifecycle.c` | — | `wls.h`, `wls_module.h`, `wls_usb.h`, `quantum.h` |
| `wls/wls_keymap.c` | `transport_logic.h` | `wls.h`, `wls_indicator.h`, `quantum.h` |
| `wls/wls_battery.c` | — | `wls.h`, `quantum.h` |
| `wls/wls_bluetooth.c` | — | `wireless.h`, `module.h`, `wls.h` |
| `wls/wls_2p4ghz.c` | — | `wireless.h`, `module.h`, `wls.h` |
| `wls/wls_split.c` | — | `quantum.h`, `wls_module.h` |
| `epomaker_split65.c` | — | `wls.h`, `quantum.h` |

### `wls/wls.c` — the composition root (532 lines)

**Measurement run.** Read in full; every function's decision source traced to a
core predicate or recorded as an exception below. 23 functions.

| Value | Verdict | Evidence |
| --- | --- | --- |
| V1 | **HOLDS** | Includes cores; no core includes it. |
| V2 | n/a | This is the composition root — the one place where ambient state is *supposed* to be read. |
| V3 | **HOLDS with one exception (see V4)** | Each effect has one owner and this file delegates rather than acts: `hs_link_activity` → `hsm_link_restart`, `hs_rgb_blink_hook` → `hsm_link_watch` + a switch on the returned action, `hs_mode_switch_pos` → a pure map to the switch enum, `hs_keycode_allowed` → `hsm_keycode_allowed`, `hs_modeio_detection`'s edge → `hsm_switch_moved`. The switch edge (`wls_transport_decide(CONFIRMED)` + `wls_indicate_devs` + `hs_link_activity`) is *orchestration* of three owners, which is what a composition root is for. |
| V4 shell holds no policy | **HOLDS, with two recorded exceptions** | No branch here decides a domain outcome; each tests a core predicate and dispatches. The two exceptions are named below (E1, E2). |
| V5 | **HOLDS** | Serves the board (`wls.h` is the board's internal API) and hides a lot: the whole low-power/EXTI arrangement, the battery snapshot packing, the boot-code assembly. |
| V6 | n/a | The composition root *is* where the impure world is gathered. |
| V7 | **PARTIAL** | `hs_mode_switch_pos` maps raw pins to the switch enum using `HS_GET_MODE_PIN` at three sites — a parse, but the *one* it should be if the pin truth is genuinely a three-way read with a precedence order (USB > BT > 2G4). `hs_link_state` maps `MD_STATE_*` → `hsm_link_*`, a clean total switch with an explicit default. |
| V8 | **HOLDS** | The switch-position map and the link-state map are both total switches with a named default (`HSM_SWITCH_UNKNOWN`, `HSM_LINK_NONE`). |
| V9 | **HOLDS** | No allocation; `hs_modeio_detection`'s `scan_timer`/`last_mode` are `static` but reset by the caller's fast path. |
| V10 | **PARTIAL** | The `0xA4` index block is a contract by convention (nothing fails if encode and decode diverge). Recorded; same shape as F7. |

**E1 — `hs_modeio_detection`'s mode map (V4, recorded, no fix).** The
`switch (now_mode)` mapping `3→hs_usb`, `1→hs_bt`, `2→hs_2g4` is a small
translation of the pin-encoder's numbering into the detector's vocabulary. It is
*not* real policy (there is no "which is better" question in it — the encoding is
arbitrary and comes from the vendor's `HS_GET_MODE_PIN` convention), and it sits
beside the pin read that produces `now_mode`, so moving it would separate a parse
from its bytes for no gain. **Recorded as a correctly-placed translation, not a
violation** — the same reasoning as `wls_usb_cable_present()` in the shells
section.

**E2 — `wls_boot_facts()` is policy in the shell (V4/V10; the one worth a
decision). FIXED (F8).** This function decided *which boot stage to report* — the
precedence of RSTCAUSE over BOOTCOUNT over ROLE over BOOT_PASS over
OK/TRANSPORT, and the per-stage code values. That is a **decision**, and by V3 it
belonged in a core (`boot_code_logic` already owns the codec; the *precedence* was
what lived here). It was a recorded exception rather than an open violation
because it was pure in substance — it read only the retained `wls_boot_report`
and `wls_reset_cause()`, both values, never an effect — and because its inputs
were exactly what a core would take, making the fix mechanical. That fix (F8) is
now applied: the precedence is the pure `wls_boot_facts(in, reset_cause,
boot_count)` in `boot_code_logic` (host-tested, 8 new cases) and the shell holds
only the adapter `wls_boot_code_now()`.

**F8 — DONE (2026-10-14).** The precedence table is now the pure
`wls_boot_code_t wls_boot_facts(wls_boot_inputs_t in, uint32_t reset_cause,
uint32_t boot_count)` in `wls/boot_code_logic`, and the shell keeps only the
adapter that reads the three live values: `wls_boot_code_now()` in `wls/wls.c`.
`wls_boot_inputs_t { master, settled, host }` and `WLS_BOOT_HOST_{USB,BLUETOOTH,
2P4GHZ}` (3/4/5, matching `HSM_HOST_*`) live in the core — copied rather than
included for the same reason as `HSM_DEVS_*`: an include-free core is
host-testable. Eight new tests in `tests/boot_code_logic` pin every branch and the
precedence ordering (latched cause outranks a boot count; a boot count outranks
the role/pass/transport cases; the healthy path names the transport). The suite is
now **30/30** and the cross-build is clean at 63.3 KB. The shell name was changed
to `wls_boot_code_now` precisely so the domain name (`wls_boot_facts`) belongs to
the core and the two cannot be confused at a call site — the collision this fix
would otherwise have introduced.

### `wls/wls.h` — the board's internal API (199 lines)

**Measurement run.** Read in full; contains only `#include`s, `#define`s, enum
declarations, struct declarations, and function prototypes. **No function bodies**
— so V1–V9 are n/a by construction (it is an interface, not an implementation).
**V5 HOLDS** and is the file's whole purpose: it is the deep interface Ousterhout
describes — the board's internals (the boot report struct, the battery snapshot,
the diag struct, the eight index constants) are declared here once and nowhere
else. **V7 HOLDS**: the `KB_BATTERY_IDX_*` block is the single place the `0xA4`
byte layout is written; `WLS_DIAG_ENC_SIZE` is defined once. **The one caveat
(V10)** is the finding already recorded in the `wls_indicator` section: the index
block is a *contract by convention* — nothing fails if an encode and a decode
disagree, and BOOT_CODE **was** silently moved 20→21 once. Recorded; no fix
proposed here (it is the same "fitness function for a contract two files must
agree on" shape as F7).

### `wls/wls_lifecycle.c` — the boot path (369 lines)

**Measurement run.** Read in full; the 17-row `wls_lifecycle_boot` sequence was
already verified claim-by-claim into `docs/BOOT-SEQUENCE.md` §12/§13.

| Value | Verdict | Evidence |
| --- | --- | --- |
| V1 | **HOLDS** | Includes `wls.h`/`wls_module.h`/`wls_usb.h`; no core includes it. |
| V2 | n/a | Boot path — the very definition of a place that gathers the world. |
| V3 | **HOLDS** | Each effect is named once and routed through an owner: the module-up gate is `wls_module_*` (not raw `wireless_devs_change`), the line is driven through `wls_transport`/`wls_usb`, the readiness gate is `wls_module_ready()`. This is the file where the pre-`keyboard_init()` HardFault was fixed, and the fix *was* V3: the fault's cause was an effect performed before its owner existed. |
| V4 shell holds no policy | **HOLDS** | The **ordering** is the whole content of this file, and ordering is not policy — it is *sequencing of effects*, which is exactly what an imperative shell is for. The decisions inside each step are core calls. |
| V5 | **HOLDS** | Hides a long, order-sensitive sequence behind a single `wls_lifecycle_boot()` entry plus a few named steps; `docs/BOOT-SEQUENCE.md` documents the ordering precondition as part of the interface (Ousterhout). |
| V6 | n/a | Boot path. |
| V7 | **HOLDS** | The switch is read through the settled reader, then parsed by the core; no raw pin reaches a decision here. |
| V8 | **HOLDS** | The readiness gates make "too early" an explicit no-op (via `wls_module`) rather than a fall-through. |
| V9 | **HOLDS — this is the error kernel's neighbour** | The boot path is the region that must not fail: it has no allocation, no unbounded loop, and every subsystem it touches is guarded by "is it up yet?" rather than assumed present. This is the file the whole class-of-defect work was about. |
| V10 | **PARTIAL** | The 17-row sequence is documented (`BOOT-SEQUENCE.md`) but not mechanically tested — there is no host test that would fail if a step were reordered. Recorded; this is a genuine gap but the sequence is not host-runnable (it is all effects), so the fitness function would be a *reviewed checklist*, which is what `BOOT-SEQUENCE.md` already is. Accepted. |

### `wls/wls_keymap.c` — the keymap dispatch (480 lines)

**Measurement run.** Read in full; every `QK_BOOT`-adjacent path inspected
because this file is the only board-reachable writer of the DFU magic word
(Stage-3 question 1).

| Value | Verdict | Evidence |
| --- | --- | --- |
| V1 | **HOLDS** | Includes `transport_logic.h`; no core includes it. |
| V3 | **HOLDS** | Every wireless keycode's effect has one owner: `wls_indicate_devs` for the indicator, `wls_keymap_*` long-press for the device switch, `bootloader_jump` for `QK_BOOT`. The keycode→device mapping is the core's `hsm_long_press_devs`, not a table here. |
| V4 shell holds no policy | **HOLDS** | The file dispatches on keycodes and calls owners; the wireless gate is the core's `hsm_keycode_allowed` (wrapped by `hs_keycode_allowed`, whose own verdict is above). |
| V5 | **HOLDS** | Hides the long-press `defer_exec` bookkeeping (`wls_process_long_press_token`, the `WLS_KEYCODE_EXEC` macro) behind a small record-processing surface. |
| V7 | **HOLDS** | `wls_keymap.c:116/153/217` re-check the `DEVS_BT1..DEVS_BT5` range **using the vendor enum** — the same fact F7 records as duplicated, but here it is the *legitimate* copy (this file is allowed to include `module.h`; the core is not). |
| V8 | **HOLDS** | The `process_record_wls` switch has a `default` and handles the unhandled-keycode case explicitly. |
| V9 | **HOLDS** | No allocation; the deferred token is invalidated on use. |
| V10 | **PARTIAL** | The long-press pairing window (`WLS_KEYCODE_PAIR_TIME 3000`) and the `QK_BOOT` guard are not tested. Recorded. |

**`QK_BOOT` — the Stage-3 question, answered as far as a read can answer it.**
The case is:

```c
case QK_BOOT: {
    if (record->event.pressed) {
        dprintf("into boot!!!\r\n");
        eeconfig_disable();
        bootloader_jump();
    }
} break;
```

It is **guarded by `record->event.pressed`** and reached only through
`process_record_wls`'s keycode switch — i.e. only from a `keyrecord_t` whose
`keycode` equals `QK_BOOT`. So the Stage-3 question reduces to: **can a
`keyrecord_t` with `keycode == QK_BOOT` be synthesised without a physical key?**
Three candidate paths, none of which this file can rule out on its own — recorded
into Stage 3 rather than guessed at:

1. **A corrupted matrix read.** The matrix scan produces row/col, which maps to a
   keycode via the keymap. A `QK_BOOT` keycode would require landing on the exact
   keymap cell that holds it. Plausible only if a scan can produce an out-of-range
   row/col that indexes into the `QK_BOOT` cell.
2. **A split-transaction payload.** The right half sends matrix events over the
   split link; a corrupted payload could in principle present a `QK_BOOT` keycode
   to the master. **This is the most promising lead** and is squarely a Stage-3
   item (it is a code question, answerable without hardware).
3. **An RPC / synthesised keycode.** Any `tap_code`/`register_code`-style path
   that names `QK_BOOT`.

None of these can be settled by reading `wls_keymap.c` alone. **Recorded as the
first Stage-3 question with its three candidate paths named** — exactly the shape
the plan asks for.

**However, path 2 was checked while writing this and it is much weaker than it
looked — recorded so Stage 3 does not spend effort re-deriving it.**

- **The split link carries MATRIX ROWS, not keycodes.** The wire format is
  `split_shmem->smatrix.matrix` (`transactions.c:183`), a per-row bitfield; the
  master's `slave_matrix_handlers_master` memcpys it into `slave_matrix[]` and it
  is then scanned by the normal matrix→keycode path. So a corrupted payload cannot
  present a keycode directly — it can only set matrix bits, and a *bit* can only
  reach `QK_BOOT` if it lands on the exact matrix cell whose keymap entry is
  `QK_BOOT`.
- **The region is CRC-guarded and last-known-good retained.**
  `read_if_checksum_mismatch` tests `curr_checksum == crc8(equiv_shmem, length)`
  (`transactions.c:149`) and, on mismatch, **replicates `last_matrix`** rather than
  accepting the bad frame (`transactions.c:179-189`). A corrupt split frame
  therefore cannot inject a stray bit at all; it is *replaced by the previous good
  matrix*, which is precisely the "defensive `if` swallows the fault" pattern the
  plan warns destroys a measurement — this one is correct (keeping HID working)
  but it means the split link is a poor candidate for the DFU entry.
- **So path 2 is largely eliminated without hardware.** What remains of it: a
  *stuck* matrix bit on the slave, or a genuine `QK_BOOT` cell in the keymap that
  the switch-can-fall-through — both are keymap/board questions, not split-protocol
  ones. **Stage 3 should spend its effort on paths 1 and 3, and confirm that the
  keymap has no `QK_BOOT` cell reachable by a single stuck row/col.**

### The remaining glue files

Verdicts below are recorded from a read of each; the group shares one
characteristic (they are vendor-stack adapters, so their V1 "includes cores" row
is empty by design).

- **`wls/wls_battery.c` (96 lines)** — V1/V5/V8/V9 HOLD. It is the battery
  snapshot's raw reader; the *decision* of what the snapshot means is in
  `indicator_logic`/`boot_code_logic`. **V4 HOLDS.** V10 PARTIAL (no test; it is
  a raw ADC read, correct to leave untested).
- **`wls/wls_bluetooth.c` (267 lines)** — **V7 HOLDS**; `:34` holds the
  `DEVS_BT1..DEVS_BT5` range check that F7 records (the legitimate vendor-enum
  copy). V4 HOLDS. This file is an adapter over `wireless.h`; its decisions are
  thin name/pair operations. V10 PARTIAL (untested; adapter).
- **`wls/wls_2p4ghz.c` (209 lines)** — same shape as `wls_bluetooth.c`; the
  `CONNECTION_HOST_2P4GHZ` adapter. V4/V5/V7 HOLD. V10 PARTIAL (untested;
  adapter).
- **`wls/wls_split.c` (77 lines)** — V1/V5/V9 HOLD; it is the split-link adapter
  and the hand-off for the module's UART. **V3 HOLDS.** V10 PARTIAL.
- **`epomaker_split65.c` (289 lines)** — the board entry point and the RGB
  indicator paint pass. **V3 HOLDS**; the paint pass is the one place that asks
  the boot-code owner for the frame and writes it, and the ownership invariant is
  checked by convention (recorded in the `wls_indicator` section as a V10 gap).
  V4 HOLDS. V10 PARTIAL — same ownership-invariant finding.
- **`wls/wls.mk` (22 lines)** — build glue; not code. It names the cores and the
  shells explicitly, which is what makes the dependency direction visible to the
  build as well. Recorded, nothing to audit.
- **`platforms/chibios/boards/GENERIC_WB32_FQ95XX/board/board.c`** — the restored
  `restart_usb_driver` guard. **This is the textbook case from the plan's honest
  limits**: an errata workaround belongs in the shell, attributed to a specific
  erratum and deletable when the die revision changes. It is one function, its
  comment names the erratum and both commits, it has no logic to leak into a core,
  and it is invisible to every core. **Audited verdict: V3 HOLDS and it is
  correctly placed.** No further work.
- **`host/battery_polybar.py`** — the host half of the `0xA4` boundary. It *is*
  the other side of the parse: it decodes the byte layout declared in `wls.h`. Its
  verdict is the same contract-by-convention finding (V10) as the index block —
  the encoder is in firmware and the decoder is in Python, and **nothing fails if
  they disagree**. That is the strongest instance of the F7 shape in the project,
  because the two halves are in different languages. Recorded; a candidate
  fitness function is a checked-in golden vector (a `0xA4` byte string plus its
  expected decode) that both sides assert against.

## Stage-3 question 1, measured: can `QK_BOOT` be dispatched without a physical key?

The `dfa0` DFU window means `bootloader_jump()` ran, which means the magic word
was written, and the only board-reachable writer is `QK_BOOT` in
`wls/wls_keymap.c` (`process_record_wls` → `case QK_BOOT`, guarded by
`record->event.pressed`). So the question reduces to: **can a `keyrecord_t` whose
`keycode == QK_BOOT` (`QK_BOOTLOADER`, `0x7C00`) arise without a person pressing
the key?** Three paths were named; two are now measured.

**Path 2 — a corrupted split-link payload — ELIMINATED (measured).** The split
wire carries *matrix rows*, not keycodes (`split_shmem->smatrix.matrix`,
`quantum/split_common/transactions.c:183`; `slave_matrix_handlers_master`
`:178-190` memcpys into `slave_matrix[]`, which the normal matrix→keycode scan
then reads). And the region is CRC-guarded with last-known-good retention:
`read_if_checksum_mismatch` (`:144-149`) tests `curr_checksum == crc8(...)` and on
mismatch replicates `last_matrix` (`:179-189`) rather than accepting the frame. A
corrupt split frame therefore cannot inject a stray bit at all.

**Path 1 — a corrupted or stuck matrix read — now has an exact target, and the
answer is "possible but narrow".** The personal `nathan` keymap places `QK_BOOT`
at a single matrix cell:

- **matrix `[10, 6]`** — determined by counting the `LAYOUT` argument position of
  the `QK_BOOT` token in the keymap (token index 55 of 69) against
  `keyboard.json`'s `LAYOUT` entry list, not by reading. The cell is
  **right-half** (`MATRIX_ROWS 12`; rows 0–5 are the master/left pins
  `A0..C13`, rows 6–11 the slave/right via `split.matrix_pins.right`), local row 4.
- Reachable on layers **`_FL` and `_MFL`** only (the Fn layers), at the position
  immediately left of `RM_VALD`. It is **not** on `_BL`/`_MBL`.
- No other keymap cell anywhere in the tree carries `QK_BOOT`: the board's
  `default` keymap has none (only `EE_CLR`), and the userspace `nathan` keymap has
  exactly these two Fn-layer cells.

So a single stuck matrix bit at slave row 10 / column 6, *while an Fn layer is
active*, would dispatch `QK_BOOT`. Reaching `_FL`/`_MFL` needs the left-hand
`LT(_FL, KC_SPC)` (or `TO(_MBL)`), so the false bit must coincide with a real Fn
hold — a two-condition coincidence, not a single stray read. **That makes path 1 a
poor candidate for a spontaneous jump and an implausible one for a recurring
one.**

**This corrects our own documentation.** `keymap.md` (userspace) claims `QK_BOOT`
"is on the **base** layer at the left half's `Esc` position" and, in a second
table, "on the right half, third row down at the `/` position (`[10,4]`)". Both
are wrong on the measured keymap: the layer is Fn, not base, and the cell is
`[10,6]`, not `[10,4]` nor the left `Esc`. **The prose was never re-derived from
the keymap; treat it as unverified.** The `keymap.c` itself is the truth, and the
`keymap.md` discrepancy is recorded as a finding in its own right (a document that
describes a keymap it does not match is the same class of defect as F7 — two
statements of one fact with nothing that fails when they diverge).

**Path 3 — a synthesised keycode (an RPC, a macro, `tap_code`) — EXAMINED, and
ELIMINATED (measured).** Two routes were checked:

- **The dynamic keymap (VIA/Vial).** `keyboard.json` sets
  `dynamic_keymap.layer_count: 4`, which is the shape of a VIA-ready board, and a
  VIA keycode map *can* hold `QK_BOOT`. But the feature is **inert here**:
  `dynamic_keymap.o` and `via.o` are **not built**, `DYNAMIC_KEYMAP_ENABLE` is
  **not defined** in the compilation flags, and the linked symbol is
  `08003b74 W keycode_at_keymap_location` — the **weak static-keymap**
  implementation in `quantum/keymap_introspection.c:46`, which reads the compiled
  `keymaps[][]` PROGMEM table (`keycode_at_keymap_location_raw`). The
  `dynamic_keymap.c` override (its own strong definition at `:85`) is never
  linked. **So keycodes come only from the compiled table, and the only
  `QK_BOOT` cells in that table are the two Fn-layer ones measured above.**
- **Keycode synthesis in our own code.** Every `register_code*` /
  `unregister_code*` call in the board's source takes a **compile-time constant or
  a value from a pure core**: `KC_LCMD`/`KC_RCMD` (`wls_keymap.c:447/460`, gated on
  `keymap_is_mac_system()`), `KC_LCTL` + `mor_map[i].base` (`:314-317`),
  and `act->key`/`act->mod`/`act->base` from `filp_decide()` (`:62-73`). None is
  `QK_BOOT` (`0x7C00`), and `register_code` is the basic-keycode path in any case.
  There is no `tap_code`, no macro expansion, and no re-entrant
  `process_record_*` call carrying a computed keycode.

**Conclusion for Stage 3 question 1: all three paths are weak or eliminated.** The
split link cannot inject a keycode (path 2, CRC-guarded row transport); a false
matrix bit needs the exact slave cell `[10,6]` *coincident with an Fn hold*
(path 1); and no synthesising route exists (path 3). **A `dfa0` window is
therefore unlikely to be a spurious `QK_BOOT` at all** — which shifts the weight
onto the two remaining explanations: **memory corruption of the DFU magic word**
(it sits at the last word of the heap, `0x20006ffc`) or **electrical**. That is
exactly when a flash carrying the magic-word capture earns its keep — and not
before.

**Correction to our own documentation (a finding in its own right).** Two of the
three paths were not the only surprise. The userspace `keymap.md` states `QK_BOOT`
"is on the **base** layer at the left half's `Esc` position", and, in a second
table, "on the right half, third row down at the `/` position (`[10,4]`)". **Both
are wrong against the measured keymap**: the layer is Fn (not base) and the cell
is `[10,6]` (not `[10,4]`, and not the left `Esc`). The prose was never re-derived
from `keymap.c` after the keymap changed. **This is the same class of defect as
F7 — two statements of one fact, with nothing that fails when they diverge** — and
it should be corrected in the userspace repo (`keymap.md:121` and `:180`) rather
than left as a second, wrong description of a safety-relevant key.

**Consequence for Stage 4.** Paths 1–3 are now weak or eliminated; if path 3 is
also exhausted with no synthesising route, then a `dfa0` window is unlikely to be
a spurious `QK_BOOT` at all, and the remaining explanations are **memory
corruption of the magic word** (it sits at the last word of the heap, `0x20006ffc`)
or **electrical**. That is exactly when a flash with the magic-word capture earns
its keep — and not before.

---

## Stage 3 question 2, measured: can anything write the DFU magic word?

**Question.** A `dfa0` window means `bootloader_jump()` ran, i.e. the DFU magic
word (`0xDEADBEEF`) was at `MAGIC_ADDR` (`0x20006ffc`) when
`enter_bootloader_mode_if_requested` checked it. A stale word is ruled out (it is
checked *and cleared* every boot). With question 1 answered — no spurious
`QK_BOOT` route — the word must have been *written*, and the two candidate writers
are a stray memory write or an electrical glitch. This section searches for the
memory writer and measures the RAM layout to bound it.

**The layout (measured on `arm-none-eabi-objdump -h` / `nm -n` of the built ELF).**

```
0x20000000  __main_stack_base__      (.mstack, 0x400)
0x20000400  __process_stack_base__   (.pstack, 0x800)
0x20000c00  __process_stack_end__
0x20001418  .bss .. 0x20004fbc       (0x3ba4 = 15268 B)
0x20004f4c  the last object we own: USBD1 (0x54 B), ends 0x20004fbc
0x20004fbc  __bss_end__ == .heap start; .heap is 0x2044 = 8260 B, ends 0x200068e0
0x200068e0  .. 0x20007000            (0x720 B unused gap)
0x20006ffc  MAGIC_ADDR == __ram0_end__ - 4
0x20007000  __ram0_end__
```

**Finding 1 — the stacks cannot reach the magic word.** Both stacks sit at the
*bottom* of RAM (`0x20000000`–`0x20000c00`), roughly `0x6400` bytes below
`MAGIC_ADDR`. Neither can descend or ascend into the heap window, whatever its
overflow. This **eliminates the stack-overflow hypothesis** — the one that looked
most plausible when the magic word was first noticed to be near RAM top.

**Finding 2 — nothing in the firmware allocates, so the heap never grows toward
the magic word.** `rg` for real call sites of `malloc|calloc|realloc|free` across
`keyboards/epomaker/`, `tmk_core/` and `quantum/` finds only three `free()` calls,
all in `quantum/painter/`, and **the painter/LVGL modules are not compiled for this
target** (no `painter`/`qp_*` objects under `obj_epomaker_epomaker_split65_nathan/`;
no `painter`/`lvgl`/`RGB_MATRIX_CUSTOM` in `keyboard.json` or either `rules.mk`).
`chHeapAlloc`/`chHeapFree`/`chHeapStatus` have **zero users** outside `lib/chibios`.
The managed heap is never used, so it cannot overflow.

**Finding 3 — even a heap overrun would miss.** The linker's `.heap` section stops
at `0x200068e0`; `MAGIC_ADDR` lies `0x720` bytes above it, in the gap before
`__ram0_end__`. A writer would have to cross that gap deliberately.

**Finding 4 — every array write in our board code is bounded.** The writes with a
non-constant index across `wls/*.c` are: the two `keys[idx]`/`keys[i]` loops in
`bluetooth_send_nkro`/`2p4ghz_send_nkro` (each guarded — an explicit
`if (idx == KEYBOARD_REPORT_KEYS && usageid < MD_SND_CMD_NKRO_LEN * 8)` before the
only write to `wls_report_nkro`), the `NKRO_REPORT_BITS` reads (both guarded by
`if (n >= NKRO_REPORT_BITS) break;`), `wls_report_kb`/`wls_report_nkro`/
`wls_report_mouse`/`buf`/`temp_report_keyboard` (all fixed-size locals, written
with `sizeof` or a constant index), and `col_pins_left/right` (a fixed initialiser
from `MATRIX_COL_PINS`). The battery encoder writes `buf[KB_BATTERY_IDX_*]`, all
compile-time constants.

**Finding 5 — the vendor message ring is bounded.** `smsg_push` (the site of an
earlier, now-fixed boot-order HardFault) is called from `module.c` with either
`sizeof(sdata)` or `infolen + 3`/`len + 3`. Every `len`/`infolen` is guarded by a
compile-time `if (len > MD_SND_CMD_*_LEN) return;` before the push, and every
buffer is `MD_SND_CMD_*_LEN + 2` or `+ 3` — so the maximum pushed size is
`46 + 3 = 49`, below `SMSG_PAYLOAD_LEN` (50). The ring (`smsg_buffer`,
`0x20001ef4`, 2000 B, ending `0x200026c4`) then has its own head/tail exhaustion
checks; its `buffer` cursor only ever advances and is reset to `smsg_buffer` on the
`FREE_SPACE < SMSG_PAYLOAD_LEN` condition. `wls_split.c` casts the transaction
`in_data` to a fixed-layout struct and reads fixed fields, bounded by the RPC's own
size argument.

**Conclusion.** **No writer in the firmware, ours or the vendor's, is measured to
be able to reach `MAGIC_ADDR`.** The layout findings (1–3) eliminate the whole
class by construction; the write audit (4–5) finds no unbounded store. This is a
*negative* result and must be stated as one: it does **not** prove the word was
never software-written (a wild pointer whose value is itself corrupt would not be
found by reading source), but it removes every *designed* path and leaves the
electrical explanation, which requires the improbable exact 32-bit value
`0xDEADBEEF` at an exact address. **The honest standing conclusion for Stage 4 is
therefore: a `dfa0` window is not explained by any code path we can name, so the
magic-word capture flash is the measurement that would discriminate — and it is
now the only software-visible test left on this lead.**

**Finding 6 — the vendor RX path, audited last, is also bounded.** The two vendor
`memcpy`s whose length is not `sizeof(...)` are both exact-size gated:
`module.c:198` copies `md_rev_payload[3..]` into `md_raw_payload` (32 B) only
inside `if (len == sizeof(md_raw_payload))`, and `module.c:449` (`md_send_raw`)
copies into `sdata[MD_RAW_SIZE + 4]` only inside `if (length != MD_RAW_SIZE)
return;`. The RX assembly is bounded by `frame_len < sizeof(md_rev_payload)` with
an explicit `raw_overflow` drop-and-resync; a completed frame's `length` is zeroed
if it overflowed. `md_rev_payload` is a static 0-length-templated buffer sized by
`MD_SEND_PKT_PAYLOAD_MAX`. **No runtime-length store in the vendor wireless stack
is unbounded.**

---

## Stage 3 question 3, measured: the `zozonteq` "disable lowpower" commit

**The lead.** A sibling fork, `zozonteq/epomaker_split65`, carries commit
`bd027b8` — *"disable lowpower mode to fix wireless (USB Dongle, Bluetooth)
issue"* (2026-01-01, parent `07a4ce7f…`). It was noted in `TODO.md` as unexamined.
It is a divergent descendant of the same vendor base (its tree has `wls/wls.c` and
`linker/wireless/lowpower.c`), so it is direct evidence about the vendor stack
both trees inherit.

**What it changes (two hunks).**

```diff
--- a/linker/wireless/lowpower.c
-    if (manual_timeout || (timeout && (last_input_activity_elapsed() >= timeout))) {
+    if ((timeout != 0) && (manual_timeout || (last_input_activity_elapsed() >= timeout))) {

--- a/wls/wls.c
-                    lpwr_set_timeout_manual(true);   // reconnect arm
+                    // lpwr_set_timeout_manual(true);
-                    lpwr_set_timeout_manual(true);   // sleep arm
+                    // lpwr_set_timeout_manual(true);
```

**Their diagnosis, in their words:** the wireless link could not settle, and they
attributed it to the low-power path. Their fix does two things: it stops the
reconnect/sleep hook from *requesting* a manual timeout at all (both arms
commented out), and it adds a global guard — `(timeout != 0) &&` — so that a
manual override cannot fire when the board has configured no idle timeout.

**How our tree already answers both, and where it deliberately differs.**

- **The `(timeout != 0)` guard: we already have its *effect*, by a different
  route.** `lpwr_is_allow_timeout()` is no longer a four-arm imperative; it is the
  pure `lpwr_timeout_allowed_decide(hook_allows, usb_active, manual_pending,
  idle_elapsed)` in `linker/wireless/lowpower_logic.c`. There is no separate
  `timeout != 0` test because the *board hook* (`lpwr_is_allow_timeout_hook` →
  `wls_lifecycle_lpwr_allow_timeout`, `wls_lifecycle.c:198`) already refuses the
  timeout path whenever this half is not master or is on USB — and the
  sleep-policy contract `lpwr_stop_is_allowed()` (shared `lowpower.c`) refuses an
  unordered stop at the point of commitment. So "a manual override must not fire
  when no timeout is configured" is subsumed by "the board hook forbids the
  timeout path outright in the states where it matters." **Their `(timeout != 0)`
  is a *symptom-level* guard against a path we have closed at the policy level.**
- **The commented-out `lpwr_set_timeout_manual(true)`: this is the important
  divergence, and we keep it on purpose.** In their tree, `hs_rgb_blink_hook`
  *requests* a manual timeout in two arms (reconnect, sleep). In ours the same
  hook is `hs_rgb_blink_hook` → the pure `hsm_link_watch` returns
  `HSM_LINK_ACT_{RECONNECT,SLEEP,NONE}`, and the shell calls
  `lpwr_set_timeout_manual(true)` on the first two (`wls/wls.c:322/325`). What
  `zozonteq` saw as the bug — the link never settling because the manual override
  kept arming — **is exactly the shape of the defect our `manual_timeout`
  *consumption* fix addresses:** `lpwr_is_allow_timeout()` is now a pure *query*
  that decides without consuming the override; the caller consumes it
  (`lpwr_set_timeout_manual(false)`) only when it actually takes the timeout path
  (`lowpower.c:318-324`). Under the vendor/`zozonteq` ordering, an override
  requested while the decision was *false* (on USB, or hook-forbidden) was
  silently destroyed — the "unconfirmed-hint destructive line drive" class this
  project has fixed before. **`zozonteq`'s "fix" removes the *request* entirely,
  which also removes the reconnect-wake and the sleep-arm behaviour the board
  needs; ours keeps the request and fixes the *consumption*.** Disabling the
  request would be a behavioural regression here (the low-battery sleep order and
  the link-reconnect handshake both depend on it), so their change is **not
  adopted**.

**Conclusion.** `bd027b8` is a *sibling's* symptom-level suppression of the low-
power path, not a fix this tree is missing. Its two elements map onto defects we
have already closed at the policy level (the `(timeout != 0)` guard ⇔ our board
hook + `lpwr_stop_is_allowed`) or deliberately handle the other way (consuming the
manual override rather than never requesting it). **The lead is closed: no change
to adopt.** It is worth recording because a reader who finds that commit (it is
the only public signal that the vendor's wireless/low-power path was unstable)
should know we saw it and why we diverge.

---

**This was the last recorded Stage-2 deferral and, with it, the last real branch
in a shell.** `wls_indicator_battery()` (in `wls_indicator.c`) held a four-arm
chain that chose *which effect to perform* on the charging LED:

```c
if (charging && full)        { ...; if (request) paint RED;   }
else if (charging)           { ...; if (request) paint GREEN; }
else if (level <= LOW)       { blink RED; ... sleep order ... }
else                         { ...; }
```

That is a decision among four outcomes — exactly the "shell holds no policy"
violation (V4) that the surrounding core work exists to remove. The *colour*
table (`wls_bat_colour_of`) and the *RGB map* (`wls_bat_rgb_of`) were already in
the core (F3), but the *selection of the effect* was not.

**The fix.** A pure
`wls_bat_action_t wls_bat_action_of(bool charging, bool full, uint8_t level, bool request, uint8_t low)`
in `indicator_logic` returns one of `WLS_BAT_ACT_{NONE, PAINT_RED, PAINT_GREEN,
BLINK_RED}`. The core mirrors the branch's order **and its asymmetry**: only the
two charging cases gate on `request`; the low-level warning blink ignores it —
the same asymmetry the board had, now stated once and testable. The shell's
`switch` on the returned action performs the effect (plus the two
`rgb_matrix_set_color` calls for the soft indicator and the sleep-order tick,
which are effects and remain).

**Verification.** `indicator_logic` 7/7 (was 5/5): the new
`battery_action_follows_the_replaced_branch` pins all four outcomes, the
`request` gate on each charging arm, the ignored `request` on the blink path, and
the branch order (charging wins over level, even at 0%). `wls_bat_rgb_of`, which
F3 shipped **without a test** (a V10 gap in our own earlier fix), is now pinned by
`battery_rgb_map_is_pinned`. The core still compiles standalone with zero warnings
and no undefined symbols; `arm-none-eabi-nm` shows `T wls_bat_action_of` and
`T wls_bat_rgb_of` in the ELF; the full cross-build is clean at 63.3 KB
(sha256 `17a8777e9b545688d461076327e92ba2c9a56dac87f41e6c6dbababef39ea1c7`).

---

## Stage 2 closed (2026-10-14)

**Every module in the audit set now carries a written verdict against V1–V10, with
the measurement that produced it, and every violation has either a fix or a
recorded decision with a reason.** The exit criteria stated in
`docs/PLAN-fcis-audit.md` are met.

**What was audited and how it stands.**

- **The pure cores** — `transport_logic`, `boot_code_logic`, `diag_logic`,
  `indicator_logic`, `sleep_order_logic`. All five are include-free and hold V1
  and V6 *by execution*: each compiles standalone with `gcc -std=c11 -Wall
  -Wextra -c <core>.c` at zero warnings, and `nm -u` on the object shows no
  undefined non-libc symbol. That is the fitness function for the cores, and it
  is what makes them host-testable.
- **The shells** — `wls_transport` (the exemplar: the decision is entirely
  `hsm_transport_decide`, the shell only gathers and applies), `wls_module` (the
  crash-only gate), `wls_usb` (pure actuator), `wls_eeprom` (pure store),
  `wls_indicator` (the instrument). Each holds V3/V4 with any exceptions recorded
  in place.
- **The board glue** — `wls.c` (the composition root, whose recorded exception E2
  became F8), `wls.h` (interface only), `wls_lifecycle` (the error kernel's
  neighbour), `wls_keymap`, `wls_battery`, `wls_bluetooth`, `wls_2p4ghz`,
  `wls_split`, `epomaker_split65.c`, `wls.mk`.
- **The boundary** — `platforms/chibios/boards/GENERIC_WB32_FQ95XX/board/board.c`
  (the restored errata guard: V3 holds and it is correctly placed — upstream's own
  text put back, invisible to every core) and `host/battery_polybar.py` (the other
  side of the `0xA4` parse, now pinned by the golden vector).
- **Not audited, by design** — the untouched vendor stack and upstream QMK. Only
  the line where our code meets them was audited, and that line is now explicit.

**Ten fixes, all verified together:** F1, F2, F3, F4 (the cores), F5 and F7 (the
structural guards), F6 (the BT-index predicate), F8 (the boot-stage precedence),
F9 (the `0xA4` golden vector), F10 (the charging-LED branch). The closing
verification: five cores compile standalone clean; `transport_logic` 43/43,
`boot_code_logic` 31/31, `indicator_logic` 7/7, `sleep_order_logic` 6/6, `wls_diag`
5/5; `./bin/guard-invariants` passes all three structural guards and each was
proven to fail on a deliberate violation; `python3 host/battery_polybar.py
--self-check` passes and was proven to fail on a mutated byte; the full
cross-build is clean at 63.3 KB
(sha256 `17a8777e9b545688d461076327e92ba2c9a56dac87f41e6c6dbababef39ea1c7`).

**One V10 finding is deliberately left open**, recorded so it is not mistaken for
an oversight: `wls.h`'s `KB_BATTERY_IDX_*` index block is a contract by
convention — the `0xA4` layout is now pinned by the golden vector on both sides,
but the *index constants themselves* are asserted only there, not by a
compile-time check at their point of definition. That is the same shape as F7 and
is the natural next structural guard if the layout ever moves again.

**Nothing in this audit changed behaviour.** Every fix preserved the observable
behaviour and proved it: the cores' pre-existing suites stayed green, and the
F2/F3/F6/F8/F10 refactors kept every fallback and branch outcome identical. No
flash was performed and no flash was warranted — the whole stage was measurable in
software, which was the point.

Stage 3 (software analysis) begins from here; its question 1 is already answered
above.

---

## Stage 3 closed (2026-10-14)

**Software analysis has run dry.** Three questions were asked in order, each
answered by measurement, and the last two returned *negative* results — which is
the honest form of "there is nothing more to find here."

1. **Can `QK_BOOT` be dispatched without a physical key?** No. The split link
   cannot inject a keycode (row transport, CRC-guarded with last-known-good
   retention); the dynamic keymap is inert (`keycode_at_keymap_location` is the
   weak static-table implementation, no `dynamic_keymap.o`/`via.o`); no
   `tap_code`/macro/re-entrant `process_record` carries it; and a false matrix bit
   would need the exact slave cell `[10,6]` **coincident with an Fn hold**.
2. **Can anything write the DFU magic word?** Not by any path we can name. The
   stacks sit at the bottom of RAM, ~`0x6400` bytes from `MAGIC_ADDR`; nothing in
   the firmware allocates (painter/LVGL is not built, the ChibiOS heap has no
   users); the managed `.heap` stops `0x720` bytes short of the magic word; every
   array write in our board code and every runtime-length store in the vendor
   wireless stack is bounded. No designed write path reaches `0x20006ffc`.
3. **Does the `zozonteq` "disable lowpower" commit hold a fix we lack?** No. Its
   two elements are a symptom-level guard we have closed at the policy level and a
   request-withdrawal that would regress this board's reconnect/sleep behaviour.
   Nothing to adopt.

**The conclusion, stated plainly.** A `dfa0` window means `bootloader_jump()` ran,
and neither a spurious `QK_BOOT` nor any memory-write path we can find explains
it. The remaining explanations are (a) a wild pointer whose own value is corrupt —
which source reading cannot rule out — or (b) an electrical write of the exact
32-bit `0xDEADBEEF` at the exact address. **Neither is decidable in software.** The
discriminating measurement is a flash that *captures* the magic word and the reset
cause at the moment of the jump: that is what Stage 4 exists for, and it is now
the only software-visible test left on this lead.

**What Stage 4 must therefore be, to earn its flash:** a build that records the
magic-word value and `RSTSTAT` on entry to the bootloader path (or the earliest
surviving point), with the LED instrument reporting it, and a **written falsifier**
— what reading would show a code path did it, and what reading would show it did
not. A flash that merely re-runs the current firmware would test nothing the
software analysis has not already settled. **No flash until that build and that
falsifier exist** (the operator's rule: recent flashes tested mechanisms software
analysis could have settled).

**Stage 3 exit criteria (from `docs/PLAN-fcis-audit.md`) are met:** three
questions, each with a recorded measurement and a conclusion; the surviving
explanations are named and are not software-decidable; and the next software step
(a discriminating build) is specified rather than assumed.

---

## Stage 4 — the discriminating build and its falsifier (2026-10-14)

**The measurement that discriminates.** Stage 3 concluded that a `dfa0` window
means `bootloader_jump()` ran, but that no software path we can find writes the
magic word: the surviving explanations are a corrupt-value wild pointer and an
exact-value electrical write, neither decidable by reading source. The magic word
itself cannot be read after the fact — `enter_bootloader_mode_if_requested()`
**clears** it (`*check = 0`) before any of our code runs. So the discriminator must
be evidence *we* leave behind, in RAM that survives a `NVIC_SystemReset`.

**The mechanism (measured, not assumed).** An object placed in
`__attribute__((section(".ram0")))` lands between `__ram0_noinit__` and
`__ram0_free__` in the linker's `NOLOAD` region. `crt0_v7m.S` zeroes `.bss`, and
`__init_ram_areas()` (`lib/chibios/os/common/startup/ARMCMx/compilers/GCC/crt1.c`)
zeroes each area only up to `no_init_area` — so **`.ram0` is never touched by
startup and survives a system reset** (`.bss` and `.data` do not). Confirmed on the
built ELF: `wls_journal` is a 16-byte `.ram0` object at `0x20004fbc`, with
`__ram0_noinit__ = 0x20004fbc` and `__ram0_free__ = 0x20004fcc`.

**What was built (`wls/`).**
- `jump_journal_logic.{c,h}` — the **sixth pure core**: a straight byte mapping
  `wls_jump_journal_encode_parts(magic, version, generation, stage, code,
  reset_cause, uptime_ms, out)`, 12 bytes at report indices 23..34. Compiles
  standalone clean; `nm -u` is empty.
- `wls_jump_journal.{c,h}` — the shell: a `.ram0`-sectioned
  `wls_jump_journal_t` holding a presence magic (`WLS_JUMP_JOURNAL_MAGIC`,
  `"JMPR"`), version, generation, the `wls_boot_code_t` at the moment of the jump,
  the `RSTSTAT` bits, and `timer_read32()`. `wls_jump_journal_stamp()` publishes
  the magic **last**, so a torn write cannot leave the presence flag set over a
  half-written record.
- `wls_boot_jump.c` — a **strong `bootloader_jump()`** replacing the weak upstream
  one (`wb32_dfu.c:30`). Its body stamps the journal, writes the magic word to
  `&__ram0_end__ - 4`, then calls the real strong
  `enter_bootloader_mode_if_requested()` (which performs the actual jump into
  `WB32_BOOTLOADER_ADDRESS`). **No upstream file is edited** — the weak symbol is
  designed for this, and its only caller (`wls_keymap.c:348`, the `QK_BOOT` arm)
  is unchanged. Duplicating the two-line magic write is deliberate: the
  address/value macros are file-local to `wb32_dfu.c`, and re-deriving them from
  the same `__ram0_end__` is not a second copy of a fact, while copying upstream's
  `NVIC_SystemReset()` would have been (it would skip the jump the strong
  function already performs).

**The falsifier (what the next flash must read, and what it would mean).** The
journal makes the two explanations separable on the next boot:

- **Journal present (byte 23 == 0x01) with a stage/code and an uptime** — our
  `bootloader_jump()` ran, i.e. a `QK_BOOT` was dispatched (or the wrapper was
  reached). Stage 3 says this should be impossible without a physical key, so this
  reading **falsifies that conclusion** and points at a keycode/matrix path (a
  false bit coincident with an Fn hold, or a synthesis route the audit missed).
- **No journal (byte 23 == 0x00) yet a `dfa0` window is observed** — the magic
  word was written by something that is *not* our `QK_BOOT` path, confirming the
  remaining explanation (a corrupt-value wild pointer or an exact-value electrical
  write) and **exonerating the keymap path**.
- **Journal present but the board does not enter DFU** — the jump was requested
  and the bootloader path did not complete, which would move the fault from "who
  wrote the word" to the bootloader-entry mechanics.

**Precondition to reading it:** the journal is carried in the `0xA4` reply (bytes
23..34, decoded by `host/battery_polybar.py --info` as `JUMP: ...`). That reply
needs a live USB line, which is exactly what a bad boot tears down — so the
reading is only trustworthy on a boot that survived long enough to answer. A boot
that jumps to DFU before answering leaves no `0xA4` reading and no journal visible
over USB; the discriminator for that case is the *next* normal boot's journal
generation (the record persists in `.ram0` until power-on clears it).

**Verification (all green, both negatives proven).** `wls_jump_journal` 3/3;
`transport_logic` 43/43, `boot_code_logic` 31/31, `indicator_logic` 7/7,
`sleep_order_logic` 6/6, `wls_diag` 5/5; six cores compile standalone clean
(`-fno-stack-protector` to drop the compiler's own `__stack_chk_fail` thunk, which
is not a core dependency); `./bin/guard-invariants` all three OK;
`python3 host/battery_polybar.py --self-check` OK. Both negatives: swapping
`out[2]` (generation) and `out[3]` (stage) in the core -> `wls_jump_journal` drops
to 2 failures; mutating the host's expected `jump_generation` -> `self-check
FAILED: jump_generation: decoded 9, expected 10`. Restored, both green. The
cross-build is clean at **63.5 KB, sha256
`2ec21c449dcb775e69663210c9768986b6db61ad4b0272ff5ef91d91fe705ce6`** — **not
flashed**. The board still runs `usbguard.bin`
(`7659464ddc2153364f6476471d294661b650e49367b0c19d500cd6974902f81e`).

---

## Stage 5 — the first hardware reading of the Stage-4 build, and the fault it exposed (2026-10-14)

**The Stage-4 build was flashed** (sha256 `2ec21c44…`), and the first reading is in.
It was **not** a DFU event: the board booted normally, the boot LED read
`RSTCAUSE` / white 5 (`PORRSTF`, a clean power-on), and the jump-journal
discriminator was never exercised — there was no `dfa0` window to explain. So
Stage 4's question is *still open*; what the flash did instead was expose a
**different, pre-existing fault** loudly enough to measure.

**The reading.** With the cable attached and the mode switch on USB (the
operator confirms it had been on USB all session), the keyboard enumerated as
`342d:e4c6`, `mfr=LEO` — our firmware, presenting the full QMK raw-HID
collection `0xFF60`/`0x61` on interface 1 — and then **did not type on USB and
did not answer `0xA4`**. No dongle was present.

**Why the silence is one fact, not two.** `host_raw_hid_send()`
(`tmk_core/protocol/host.c:388`) dispatches to
`host_get_active_driver()->send_raw_hid`, and the wireless driver
(`keyboards/linker/wireless/wireless.c:24`) has **no `.send_raw_hid` member**, so
the call returns early and nothing is sent. An enumerated device that is silent on
`0xA4` therefore proves **the committed transport was wireless while the switch
said USB** — the HID went to the module, and the reply had no USB driver to ride.

**The fault is the C14/C15 pin read, and it is the documented recurring one.** The
build's switch seed (`wls_lifecycle_boot()`, `wls_lifecycle.c:96`) reads
`hs_mode_switch_pos()` — which decides C14/C15 against the 2-bit patterns in
`wls/wls.h:19-21` (`USB "1,1"`, `BT "0,1"`, `2.4G "1,0"`) — **after** enabling
the pull-ups and calling `waitInputPinDelay()`. The wait is there, so this is not
the missing-settle symptom of 2026-10-13. What the reading shows is the fault the
settle cannot fix: **a settled read that returns a *valid but wrong* pair**. The
committed transport was 2.4 GHz, which is only reachable from a readable
`(1, 0)` — not from `UNKNOWN`. **Fixes A–D make an *unreadable* switch safe (the
unreadable variant carries no transport); they do nothing about a readable switch
that reads wrong.** That is the gap this reading measures.

**The rescue path did not fire, and its own read is suspect.**
`hsm_switch_apply_with_cable(pos, last_bt, cable_here)` (transport_logic.c:111)
puts the cable **above** the switch: `cable_here` true forces USB regardless of
the switch — the documented "the half with the host cable is the master" rule
(`docs/HARDWARE.md` "Halves and handedness"). It did not force USB, so
`cable_here` read false with the cable attached. `cable_here` is
`wls_usb_cable_present()` (`wls_usb.c:33`), which is
`gpio_set_pin_input(SPLIT_HAND_PIN); wait_us(100); return gpio_read_pin(SPLIT_HAND_PIN);`
— **a bare input read with no pull-up, and a 100 µs wait that is not a settle**
(`waitInputPinDelay()` is `CPU_CLOCK/1000000/4` ≈ 0.25 µs; 100 µs is upstream's
idiom copied from `is_keyboard_left_impl()`, not a measured settle for this pin).
Two things are wrong with it and both are worth a reading:

1. **The pin is reconfigured on every call**, discarding whatever pull
   QMK's split init established for the handedness pin
   (`keyboard.json` `split.handedness.pin` = `B9`), so the read is of a floating
   line. A floating line can read low with the cable present.
2. **It is the same pin (`B9`) that `is_keyboard_master()` reads** for a
   different question, and `docs/HARDWARE.md` records the two coinciding only
   *because* the half with the cable is the master — an assumption, not a
   measurement of "is a cable here". **`HS_BAT_CABLE_PIN` (`A7`) is the board's
   documented USB-insertion-detect pin** (`config.h:9`); the cable question has
   its own pin and this code does not use it.

**Open, and this is the next software question.** Why did the switch read 2.4 GHz
with the switch on USB? Either the switch truly presents `(1,0)` to C14/C15 at
that instant (a hardware/contact fact, which no firmware change fixes), or the
read is corrupted (a firmware defect). And separately: why did `cable_here` read
false with the cable attached — is it the discarded pull, the wrong pin, or
neither? **Both need a reading, and the `0xA4` diag block that would carry
`pin_c14`/`pin_c15`/`pin_b9` is silent precisely because the transport is wrong.**
The instrument rule applies: make the channel trustworthy (or take the reading
through the LED) before re-engineering. **No flash is warranted until a
discriminating build and a falsifier exist** — the same rule that produced
Stage 4.

**Nothing here is a regression from Stage 4.** The journal, the encoder, the
guards and the tests are unaffected; the fault is in the transport seed, which
Stage 4 did not touch.

### What the next build must do (the discriminating measurement for Stage 5)

The `0xA4` diag block already carries `pin_c14`, `pin_c15` and `pin_b9`
(`wls.c:148-156`), but it is **silent in exactly the failure that needs it** —
the reply rides the USB driver, which the wrong transport does not install. Two
consequences:

1. **The LED instrument is the only channel that survives**, as it was for the
   unobservable boot region. The next build must **play the raw C14/C15 pair (and
   the `cable_here` result) on the boot LED code** — an amber count of the packed
   `(c14, c15, cable)` triple, or a short fixed code — so the reading that is
   currently impossible becomes a look. That is the instrument rule applied to
   the transport seed: make the channel trustworthy before re-engineering.
2. **The `wls.c:146-147` comment is wrong and must be corrected**: it said `B9`
   "uses the settled reader", but `wls_usb_cable_present()` waits `wait_us(100)`
   and drops the pull-up — it is not the settled read its name and comment imply.
   **Corrected during the walk** (`wls.c`, the `wls_diag_gather` pin block): the
   comment now states the read is a bare input after `wait_us(100)`, the same
   idiom upstream uses, and is not a measured settle.

**The falsifier for Stage 5** (write it before flashing): if the LED reports
`C14 == 1 && C15 == 0` at boot with the switch on USB, the switch genuinely
presents 2.4 GHz to the pins and the defect is hardware/contact — no firmware
change can fix it, and the mitigation is to stop trusting the switch alone
(e.g. always attempt the USB line, or read `A7` instead). If the LED reports the
USB pair (`1, 1`) while the committed transport is 2.4 GHz, the read was
corrupted in firmware and the seed path is at fault. If `cable_here` is the
liar, the LED must show it separately. **Each reading names a different repair;
none of them is a flash away until the build reports all three.**

**No flash until that build and that falsifier exist** — the rule that produced
Stage 4.

---

## Stage 5 — the exhaustive walk: what it found and fixed (2026-10-14)

The walk the user commissioned (reset to steady state, debugger specificity,
fix-as-found) has completed its first pass over the pure cores and the board
shells. Every fix below was verified by the fitness functions, not by reading
alone.

**Defects fixed (each with the measurement that proves it):**

| # | Defect | Where | Why it was a defect |
| --- | --- | --- | --- |
| D1 | 12-byte journal encoded at offset 23 into a 32-byte report | `wls_battery.c` + `jump_journal_logic.*` | 3-byte stack overrun on every `0xA4` reply; host side had the mirrored error, so both agreed on an impossible layout |
| KF-1 | `HSM_HOST_*` off by one vs upstream `connection_host_t` | `transport_logic.h` | `connection_set_host_noeprom((connection_host_t)decision.host)` wrote the *wrong host* on every commit; `HSM_HOST_USB(3)` == `CONNECTION_HOST_BLUETOOTH` |
| KF-2 | Golden vector labelled `0x04` in the wrong vocabulary | `battery_polybar.py`, `wls_diag_tests.cpp`, `0xA4-golden-vector.md` | Two vocabularies for one byte; the fixtures encoded the pre-fix numbering |
| KF-3 | Header prose contradicted code on multi-bit reset cause and amber clamping | `boot_code_logic.h` | A doc that lies is worse than no doc; code and tests already agreed |
| KF-4 | `rgb_key_logic` declared the RGB mode-step rule but never emitted it | `rgb_key_logic.*`, `wls_keymap.c` | An omitted case disguised as dead vocabulary; the live rule was a shell literal |
| C1 | Two unguarded NKRO popcount loops read `bits[30]` | `wls_2p4ghz.c` | One-past-end read when the key set is empty; both siblings already carried the guard |
| — | Fabricated "98 kΩ bridge" figure | `diag_logic.h`, `docs/HARDWARE.md` | An invented hardware constant; purged |

**The largest structural finding — the switch decode existed twice.** The walk
reached `wls.c` and found the *same three pin macros* decoded in two functions
with two vocabularies: `hs_mode_switch_pos()` returned `HSM_SWITCH_*` directly,
while `hs_modeio_detection()` decoded them again into a `now_mode` 1/2/3
vocabulary only to map it straight back through `hsm_switch_pos_of_mode`. The
round-trip existed to feed `hsm_switch_pos_of_hs_mode`, a mapper for the
detector's `enum modeio_mode` output — a vocabulary no production code ever
read. Alongside it: `hs_modeio_detection`'s `mode` out-parameter was dead
(`hs_mode_scan` took it by value, so the write never escaped), and `lsat_btdev`
was threaded through three signatures and never read.

The repair reduced the whole cluster to one decode:

- `hs_modeio_detection(bool)` — the numeric mode is built once and delegated to
  `hsm_switch_pos_of_mode`, so `hs_mode_switch_pos()` is now the *only* pin
  decode in the firmware.
- Deleted: `hsm_switch_pos_of_hs_mode`, `enum modeio_mode`, `hsm_mode_seed`,
  `hsm_seed_btdev` (the last two were production-dead; `hsm_btdev_or` already
  carries the live clamp rule).
- `hs_mode_scan(bool)` and `hs_keycode_allowed(uint8_t target_devs)` lost their
  dead parameters; the six keymap call sites stopped passing
  `confinfo.last_btdevs` to a function that could not use it.
- The `transport_logic` suite went 43 → 40 tests (three removed with their
  subjects), the pure core still compiles `-Wall -Wextra` with an empty `nm -u`.

**Fitness functions, all green after the pass:** `transport_logic` 40/40,
`boot_code_logic` 31/31, `indicator_logic` 7/7, `sleep_order_logic` 6/6,
`rgb_key_logic` 8/8, `wls_diag` 5/5, `wls_jump_journal` 3/3; `./bin/guard-invariants`
all three OK; `python3 host/battery_polybar.py --self-check` OK; all six
include-free cores compile clean with empty `nm -u`.

**Later in the walk — the split log, the indicator, and a withdrawn hypothesis.**

| # | Defect | Where | Why it was a defect |
| --- | --- | --- | --- |
| E1 | `wls_split_send`'s "did the RPC complete" logged as "Slave Sleep OK" | `wls_split.c`, `wls_lifecycle.c` | Five sites, four naming a command that was not a sleep; the log is the only signal and it lied about which one was sent |
| — | `rgb_matrix_hs_set_remain_time(index, remain_time)` ignored `remain_time` | `wls_indicator.{c,h}`, `wls_keymap.c` | The name and signature promised an effect the body never performed; every caller passed 0 and meant "cancel". Renamed `rgb_matrix_hs_cancel_index(index)` with the dead parameter removed |
| — | `boot_code_started == 0` used as an "not yet started" sentinel | `wls_indicator.c` | `timer_read32()` genuinely returns 0 in the first millisecond, so a real origin of 0 would re-enter the arm branch forever and hold the matrix black. Now a separate `boot_code_armed` latch |
| G1 | `eeconfig_confinfo_default()` left `devs`, `filp` (and read `last_btdevs` as a bare `1`) unset | `wls_eeprom.c` | The bitfields share one `uint32_t` with `raw`, and the whole point of the version gate is that the block being discarded may be a *foreign* layout — so an unset field is not zero, it is whatever the foreign block held. Every field is now named |
| E4 | the split body's device index reached board state unclamped | `split_logic.c`, `split_logic.h` | The body is untrusted wire input. `0xFF` reached `wls_module_devs_change()` and `hsm_host_of_devs()`, which maps anything outside `DEVS_USB`..`DEVS_2G4` to a transport — so a corrupt byte read as BLUETOOTH. Now clamped in the pure core (`clamp_devs`), so the shell cannot be handed an out-of-range index at all; two vectors pin it (corrupt clamps to USB; the full 0..6 round-trips) |

**A hypothesis withdrawn — the "two-pulse loss" is not in the current source.**
The `(5 amber, 5 white)` reading taken after the Stage-4 flash had been written up
as a live painting defect (`docs/HARDWARE.md`). Walking `wls_indicator.c`, a host
simulation of the pure core (`wls_boot_code_at` re-implemented verbatim, scanned
at 1 ms over the window, origin offset swept across the whole pulse period)
counted **seven amber and five white at every offset** with `show == frame`. The
window is measured from the stamped origin, so the stamping pass is inside it;
`wls_boot_code_at(0)` is already lit, so a late origin cannot skip a whole pulse.
**The reading therefore describes the flashed Stage-4 artifact, which predates
the current tree — the same relationship as D1 and the `ENC_SIZE` mismatch — and
the claim was corrected in `docs/HARDWARE.md` rather than left for a future
session to chase.** The one real hazard the walk did find there (the timer
sentinel, above) was fixed.

**The board build has since been run and passes.** `./bin/make
epomaker/epomaker_split65:nathan` → `text 0 / data 64736 / bss 0`, no warnings,
with the artifact copied to the tree and the userspace folder. **That compiles the
`_Static_assert`s** (and every edit since), so the "still unproven" note below is
now resolved for the asserts specifically; the driver-layer series is now walked
(G1 and E4, above) with only the vendor-owned items outstanding. Note the artifact
is **64 736 bytes** where the flashed Stage-4 build was 63.5 KB — the sha256 has
changed, and any future pre-flight must verify the on-disk `.bin`, not the old
hash.

**Fitness functions, all green after the driver-layer walk:** the nine board
suites (`transport_logic` 40, `boot_code_logic` 31, `rgb_key_logic` 8,
`split_logic` 8, `indicator_logic` 7, `sleep_order_logic` 6, `wls_diag` 5,
`reset_logic` 4, `wls_jump_journal` 3); `./bin/guard-invariants` all three OK;
`python3 host/battery_polybar.py --self-check` OK. **`split_logic` is a seventh
include-free core** (compiles clean with an empty `nm -u`, so its clamp rule is
host-testable).

**What remains unproven.** The vendor-owned items only — `module.c`'s
`md_check_sum(..., 0)` length-0 underflow on an over-long raw frame, and
`smsg_push`'s unchecked bool — both in `keyboards/linker/wireless/`, which the
board does not own. Everything on this side of the edge has been walked and
either fixed or dismissed with evidence.
