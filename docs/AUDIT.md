# Code audit — ownership, cadence, and maintainability

> **Scope and method.** A read-only, systematic audit prompted by the observation
> that the defects found on this board share a *shape* rather than being random
> faults. Four parallel passes covered disjoint areas: (1) the board file
> `epomaker_split65.c`, (2) our board layer `wls/` + host tools, (3) the vendor
> wireless stack `keyboards/linker/wireless/`, (4) the upstream seams we patched.
> Every finding was verified by reading source; citations are `file:line`.
>
> The lens is **not** "find bugs" but "find design faults that make bugs
> intractable": multiple writers for one state, one function doing two jobs at
> different cadences, state derived at the wrong time, and duplicated
> consistency readers. These are the mechanical causes of the defects already
> fixed (defect 4 = two owners; defect 5 = four writers; defect 6 = one function,
> two cadences).
>
> **Disposition vocabulary.** `FIX` = consolidate to a single owner / split
> cadences. `ACCEPT` = keep as-is with a Chesterton's-fence reason (upstream
> contract, or inert). `FC/S` = extract a pure functional core so the rule is
> testable and the imperative shell only performs effects.

## Summary of the recurring shapes

| Shape | Meaning | Examples found |
|---|---|---|
| N-writers | >1 subsystem mutates one state without reconciliation | `md_info.state`/`.indicator`, `lower_sleep`, `confinfo.devs`/`last_btdevs`, `lpwr_state`/`lpwr_timestamp` |
| Two-cadence | one function/variable serves a bookkeeping job *and* a transition/effect job | `hs_linker_rgb_timer`, `wls_rgb_indicator_*`, `housekeeping_task_user`, `manual_timeout` |
| Stale-time | state derived at the wrong moment (snapshot vs live; torn reads) | battery read at 4 sites; `keycode_shadow` captured by pointer |
| Duplicated reader | two decoders of one wire layout, kept in sync by hand | `0xA4` byte map in `wls.h` vs `battery_polybar.py`; charge decode |

## Tier 1 — our additions (`wls/`, board hooks, host tools)

| State / Effect | Writers (file:line) | Persistence | Verdict | Disposition |
|---|---|---|---|---|
| `wls_bt_profile` vs `wls_devs`/`confinfo.devs` | `wls_bluetooth.c:43`; `wireless.c:208` | RAM (mirrors EEPROM) | **VIOLATION** — two RAM vars for one sub-selection, kept in lockstep only by convention; a `wireless_devs_change` on a BT index that bypasses `bluetooth_select_profile` desyncs them, and `bluetooth_get_profile()` (`wls_bluetooth.c:61`) then lies in the `0xA4` reply (`wls_battery.c:35`) | **DONE (fix 2)** — the profile is now *derived*, not stored: `wls_bt_profile` deleted; `bluetooth_get_profile()` = pure `hsm_profile_of_devs(wireless_get_current_devs())`; 8/8 `transport_logic` tests (new `bt_profile_is_a_pure_function_of_the_device_index`) |
| `lower_sleep` | **sole setter** `wls_order_sleep()` (`wls/wls.c`), called from the low-battery tick and the 0xAA RPC; cleared by `wls_order_sleep(false)` on a real wake | RAM | **DONE (fix 5)** — one authority: the flag moved into `wls.c` behind `wls_order_sleep(bool)`/`wls_sleep_ordered()`. The `extern bool` is gone; every reader is now a side-effect-free query, so no consumer mutates it (the wake-clear previously wrote a bare global). The low-battery decision is the pure `hsm_should_order_sleep(level, charging, stop_threshold)`. Tested: `sleep_order_is_a_pure_function_of_battery_and_charge` (13/13) |
| `confinfo.devs` / `confinfo.last_btdevs` | **sole writer** `wls_persist_devs` (`:1329`, keycode path) | EEPROM (persisted intent) | **DONE (fix 3)** — the bookkeeping mirror is gone: the board no longer overrides `wireless_devs_change_kb` (vendor weak no-op applies), so the persisted index is written *only* by user intent. The live authority is `wireless_get_current_devs()`; every live reader (six mode-scan seeds, two `hs_mode_scan` seeds, three "on wireless" checks) now reads it via the pure `hsm_mode_seed`/`hsm_seed_btdev`. `confinfo.devs`/`.last_btdevs` are read only at boot as the persisted seed. Tested: `mode_seed_is_the_live_device_index`, `bt_seed_prefers_live_index_and_clamps_fallback` (10/10). |
| `hs_linker_rgb_timer` | setter `wls.c:123`, ~13 callers | RAM | **VIOLATION** — one timer read as both `HS_LBACK_TIMEOUT` (`wls.c:153`) and `HS_SLEEP_TIMEOUT` (`wls.c:164`) in one fall-through pass | **DONE (fix 4)** — split into two independent deadlines in `hsm_link_timers_t`; the policy is the pure `hsm_link_watch()` (arm-on-entry/change, fire the state's own deadline, clear foreign ones) and `hsm_link_restart()` for activity; the shell performs only the returned action. The fall-through `switch` (missing `break`) is gone. 12/12 `transport_logic` tests |
| `wls_rgb_indicator_*` | arm `epomaker_split65.c:1336-1341`; tick `:1469-1476`; re-arm `:1456` | RAM | **VIOLATION** — arm path and tick path write the same fields; the tick callback re-enters the arm function | **FC/S FIX** |
| `keycode_shadow` | `:477` (every `process_record_wls` call) | RAM | **VIOLATION** — deferred long-press captures the *address* (`:502`); a later non-WLS key overwrites it before the 3 s timer fires → wrong profile re-pair | **DONE (fix 1)** — pure `hsm_long_press_devs(keycode)` decides the target; the shell passes the value by pointer-cast, so nothing shared is captured; `keycode_shadow` deleted (17 insertions, 36 deletions); 7/7 `transport_logic` tests |
| `confinfo.filp` persist | `:1085` writes the whole `confinfo.raw` | EEPROM | **RESOLVED by fix 3** — with the bookkeeping mirror removed, `confinfo.devs`/`.last_btdevs` hold only persisted user intent, so a `KC_FILP` whole-struct write can no longer commit a transport the user never chose. The behaviour is now correct by construction (no second writer to leak in). |
| LED rail `A5`/`A8` | `wls_led_rail_apply` `wls.c:21` (sole logical writer) | derived | **SINGLE-OWNER (clean)** — fixed as defect 5 | ACCEPT (done) |
| `bat_indicator_cnt` | init `:75` (`= true` on a ms timestamp) | RAM | latent — the 2 s re-enable gate can trip at boot | **DONE (fix 7)** — initializer corrected to `0` (a valid ms epoch, not a boolean) |
| `inqbat_flag`, `test_white_light_flag`, `start_hsv`, `temp`, `im_test_rate_flag`, `prev_cable_state`, `hs_transport_arbitrate_cable` | never set / never read | RAM | dead or missing-writer state | **DONE (fix 7)** — all deleted; the no-op `hs_transport_arbitrate_cable` and its two calls removed with its rationale kept in the file comment |
| Host: interface selection | `battery_polybar.py:75` hardcoded default vs `:250` CLI vs `:80` first-candidate fallback | host memory | **VIOLATION** — three selection rules, two made unreachable by argparse defaults | **DONE (fix 7)** — the dead `None` branch removed and the stale "UNVERIFIED" docstrings corrected (interface 2 = dongle is hardware-verified) |
| Host: charge decode | `battery_polybar.py:203` (1,2 → "CHG") vs `:217` (raw) | derived | **VIOLATION** — two decoders disagree; FULL renders as "CHG" | **DONE (fix 7)** — one `CHARGE_NAMES` table used by both `format_status` and `format_info` |
| Host: `0xA4` byte map | duplicated between `wls.h:55-77` and `battery_polybar.py:136-152` | n/a | **VIOLATION** — two hand-synced copies of the wire layout | **DONE (fix 7)** — one `REPLY_INDEX` dict drives `parse_reply`; the decode tables are co-located with it. (The firmware/`PROTOCOL.md` copy remains a separate source of truth by necessity — a host tool cannot read the C header — but each side is now single-sourced internally.) |

## Tier 2 — our modifications to upstream/vendor seams

| State / Effect | Verdict | Disposition |
|---|---|---|
| `active_host` (`host.c:109`) | **SINGLE-OWNER (clean)** — one writer, only on change | ACCEPT (done) |
| `host_candidates[]`, `w2p4_driver`/`bt_driver` structs | **SINGLE-OWNER (clean)** | ACCEPT (done) |
| `driver` fallthrough (`host.c:164`) | latent second chooser; upstream contract; not live (no report before first `host_task`) | ACCEPT (upstream) |
| `connection_set_host` unconditional EEPROM write (`connection.c:80-84`) | upstream idiom; board already uses `_noeeprom` where needed | ACCEPT (upstream) |
| `connection_host_changed_kb` reads routed state inside a change hook (`:1447`) | board mitigates the upstream "hook skipped on no-op" gap with an explicit `wls_usb_connect()` (`:219`) | ACCEPT (documented mitigation) |
| `wireless_2p4ghz_task()/init()` | **DONE (fix 11)** — `keyboard.c` now includes `wireless_2p4ghz.h` under `WIRELESS_2P4GHZ_ENABLE` and calls `wireless_2p4ghz_init()` (from `keyboard_init`, mirroring `bluetooth_init()`) and `wireless_2p4ghz_task()` (from `keyboard_task`, mirroring `bluetooth_task()`); both are now `T` in the linked ELF, so the 2.4 GHz contract has a real driven lifecycle | DONE |
| `md_info.state` / `.indicator` | **DONE (fix 6)** — the module now owns the transition: `wireless_devs_change` calls `md_devs_changed()` (module.c) instead of poking `*md_getp_state()`/`*md_getp_indicator()`; no external writer reaches the registers (reads via the accessors remain) | **DONE** |
| `smsg_instance.state` | **VIOLATION** — decoder sets `replied` (`module.c:158`), send task sets the rest (`module.c:257-276`); no lock | FIX |
| `lpwr_state` / `lpwr_timestamp` | **VIOLATION** — `md_receive_host_cb` (`lowpower.c:121-133`, UART cadence) writes both alongside `lpwr_task` | **FC/S FIX** |
| `manual_timeout` | **DONE (fix 10)** — `lpwr_is_allow_timeout()` is now a pure query (`lpwr_timeout_allowed_decide()` in `lowpower_logic`); the one-shot override is consumed by the caller (`lpwr_task`) only when the timeout path is actually taken, so a request made while the decision is false is no longer silently destroyed | DONE |
| `lpwr_wakeupcd` reset vs ISR | **DONE (fix 10)** — the STOP entry called an accumulate-only setter with `NONE` (`\|= 0`, a no-op), so the wake set was never cleared. New `lpwr_clear_sleep_wakeupcd()` performs a real clear under `chSysLock()`/`chSysUnlock()` against the ISR `\|=` (`lpwr_wb32.c` `palcallback`) | DONE |
| `raw_hid_send` line-pinned macro (`md_raw.h:8-10`) | **DONE (fix 8)** — deleted. `replaced_hid_send()` had become behaviorally identical to upstream `raw_hid_send()` (both route to `host_raw_hid_send()` → active-driver `send_raw_hid`); the alias, the shim, the direct board call, and the `-include md_raw.h` in both `.mk` files are all removed. The board calls plain `raw_hid_send()`; the receive path (`md_receive_raw_cb` → `raw_hid_receive`) is kept in `md_raw.c` | DONE |
| `md_receive_msg_task` | **DONE (fix 9)** — the framer is extracted as the pure, include-free core `keyboards/linker/wireless/md_frame.{c,h}` (state carries the decided grammar + expected length; zero-init = idle). The shell `module.c` feeds bytes through `md_frame_feed()` and only interprets completed frames; the two coupled statics (`data_count`/`data_remain`) are gone. It lives in the shared tree (not the board `wls/`) because `module.c` is shared across ~20 boards and must not include a board header. Tested byte-by-byte: 8/8 `md_frame` tests | DONE |

## Tier 3 — upstream/vendor code we depend on but did not author

Everything in Tier 2 above that is labelled **ACCEPT (upstream)** is documented
here rather than fixed: it is the upstream contract, we work around it in the
board layer, and rewriting it would fight the plate. Tier 2 items we *did* author
or materially extend (`md_info` writers, the framer, `raw_hid_send`) are ours to
fix.

## Acceptance criteria — what "clean" means on hardware

For this project a fix is **not** done when the symptom disappears; it is done
when the rule is *provable*. Every remaining fix must meet all three bars, and
each is checked against them before it is committed:

1. **Single authority.** Exactly one writer per piece of state, or the state is
   **derived** from a single source and never mirrored. A second writer is a
   defect even if it currently agrees (it will diverge).
2. **One job per function / one cadence per variable.** Bookkeeping (runs
   always) and effect (runs on a transition) never share a body. A timer has one
   meaning. A "change" handler does not act on a no-op.
3. **Testable rule.** The decision lives in a **pure function** (no I/O, no
   globals, no timers) covered by a test in `tests/`; the imperative shell only
   selects effects from its result. "It works" is not evidence — a test that
   states *why* it is right is.

This is the standard the three already-landed fixes met: `transport_logic`
(defect 4 — the switch→host rule as a tested pure core), the rail owner (defect
5 — effect derived from one source), and `wls_indicate_devs` (defect 6 — the
effect separated from the bookkeeping hook).

## The fix strategy — functional core / imperative shell

The recurring cure is to move each rule out of the tangled imperative code into a
**pure function** (no I/O, no globals, fully testable) and leave the shell with
only effect-selection. This is what has already worked three times (the pure
`transport_logic`, `lowpower_logic`, and the rail-owner derive), and it is what
retires the remaining shapes structurally:

1. **A change handler should decide, not act.** `wireless_devs_change_kb` and
   friends become shells that call a pure `decide_*` and apply its result.
2. **One timer, one meaning.** `hs_linker_rgb_timer`'s two roles split into two
   named deadlines owned by their respective rules.
3. **Wire layouts get one source.** The `0xA4` map (firmware + Python) and the
   framer state machine become pure functions with shared tests.

Each fix lands with a test in `tests/` (as `transport_logic` and `lowpower_logic`
already do), so the rule cannot regress and the shell stays trivial.

## Why the audit did not catch defects 7 and 8 — the shape of the blind spot

The audit above caught *state* faults: one value, more than one writer. It missed
two defects that were later found on hardware, and the miss was structural, not
careless:

- **Defect 7 — one rule, three private copies.** "Choose the transport from the
  switch" was implemented three times (boot, keycode, switch edge); the edge copy
  wrote only half the decision. No *state* had two writers; the *rule* had three
  authors. A per-site state inventory cannot see a rule written N times.
- **Defect 8 — an effect that retriggers itself.** The channel indicator re-armed
  its own flash while not connected, so it blinked forever. Nothing was
  mis-owned; an effect depended on the passage of time rather than a transition.

Both faults live in the **imperative shell**, not the pure core. The pure cores
are proven by `tests/`; the shells were only *compiled*. The audit's own framing
("the fix strategy is functional core / imperative shell") invited the too-strong
reading that a proven core means a proven feature. It does not: a correct decision
applied wrongly is still a bug, and nothing tested the application.

## The wiring review — extending the strategy to the shell

Literature. The pattern is "Functional Core, Imperative Shell" (Gary Bernhardt,
*Boundaries*, SCNA 2012; re-stated by Google's Testing Blog, "Simplify Your Code:
Functional Core, Imperative Shell", 2025). The corollary that closes defects 7
and 8 is the **Humble Object** (Michael Feathers, *The Humble Dialog Box*, 2002;
Gerard Meszaros, *xUnit Test Patterns*; Martin Fowler's bliki entry): the part
that cannot be unit-tested must be made so thin that it holds no decisions at all.
For embedded specifically, three further standing rules apply — NASA/JPL's *Power
of Ten* (Gerard Holzmann, 2006; Rules 4, 6, 7, 9: bounded functions, smallest
scope, checked parameters, no hidden pointer dereference), Samek's state-machine
discipline (*Practical UML Statecharts in C/C++*; one authority per state, no
event-action spaghetti), and CMU 18-642 (*Modal Systems and Statecharts*: never
mix mode-change logic with normal output sequencing).

The test the review applies to every shell. A function in the shell is allowed to
exist only if it passes all four:

1. **Humble.** It selects effects; it does not decide. Any `if`/`switch` in the
   shell that encodes a *rule* (not a dispatch on an already-decided value) must
   move into the pure core. Threshold: a shell function should be, in Feathers's
   words, "so simple we don't bother testing it".
2. **One authority.** Each mutable fact has exactly one writer, or is derived.
   The pure core owns rules; the shell owns I/O and register writes.
3. **Rule stated once.** If the same comparison/idiom appears at more than one
   call site, it is one rule with N copies (defect 7) — collapse it to one
   exported function and call it N times.
4. **Effect on transition, never on time.** Any effect that runs "every loop" or
   "while X" and re-derives its own trigger (defect 8) must instead be armed at
   the transition and terminate. A periodic re-derivation of a trigger is a defect
   unless the periodicity is itself the named rule.

Evidence gathered in this review (citations are `file:line`):

| Finding | Location | Shape | Disposition |
|---|---|---|---|
| The mode gate `hs_modeio_detection(true,&mode,…)` + `(mode==hs_bt\|\|hs_wireless\|\|hs_none)` is written **6 times** | `epomaker_split65.c:433,442,491,500,508,516` | Rule stated N times (defect 7's shape, still live) | FIX — one exported gate |
| The mode-seed idiom `hsm_mode_seed(...); hsm_seed_btdev(...)` repeated | `epomaker_split65.c:417,432-433,441-442,490-491,499-500,507-508,515-516,1729` | Duplicated prelude | FIX — one `wireless_mode_now()` shell helper |
| `process_record_kb` MOR_/KC_F1..F12 blocks: mode-change and HID emission interleaved | `epomaker_split65.c:643+` | CMU 18-642 anti-pattern | **DONE (Phase C.6)** — the mac/media remap decision is now the pure core `wls/keymap_logic.{c,h}` (`filp_decide` + three tables); the shell only performs the effect (`filp_apply`). `tests/keymap_logic` 5/5 |
| 13 file-scope mutable globals in the board file, several un-owned (`no_record_fg`, `pov`, `mac_status`, `hs_ct_time`) | `epomaker_split65.c:70-79,641` | Smallest-scope violation (Power of Ten Rule 6) | **DONE (Phase C.5)** — 3 dead globals + `pov` deleted; `post_init_timer`/`no_record_fg` made `static`; `buff[]` `static const`; the five `wls_rgb_indicator_*` bundled into one `static struct wls_indicator`; only the honest cross-file state (`confinfo`, `charging_state`, `bat_full_flag`) remains file-scope |
| `hs_link_last_status` static in the link watch | `wls/wls.c:137` | Shell-held state that the pure `hsm_link_watch` should carry | FIX — move into the pure timer struct |
| `scan_timer` static inside `hs_modeio_detection` | `wls/wls.c:48` | Hidden cadence in a rule function | FIX — pass `now` in, make the rate-limit pure |
| Warning level: board build is `-Wall -Wstrict-prototypes` only, **no `-Wextra`, no `-Werror`** (`ALLOW_WARNINGS` not set means warnings do not fail the build) | `builddefs/common_rules.mk:77-81` | Power of Ten Rules 5/10 not in force | FIX — raise warnings, add `-Werror` for our files |
| Test build: `-Wall -Wundef` via CXXFLAGS, **no sanitizers** | `builddefs/build_test.mk` → `common_rules.mk:96-98` | UBSan/ASan absent for the pure cores | FIX — build the pure-core tests with `-fsanitize=address,undefined` |

## The plan — eliminate the fault classes, not the instances

Ordered by risk × provability, same cadence as the fixes above (one commit each,
pure core + test + humble shell). Each item states the invariant it makes
unbreakable.

**Phase A — retire the "rule stated N times" shape (defect 7's class).**
1. **One switch gate.** **DONE.** Exported `hs_keycode_allowed(target_devs,
   last_bt)` (`wls/wls.c`) — the seed+detect+predicate idiom, stated once — built
   on the pure `hsm_keycode_allowed` (previously dead code) and a new
   `hsm_switch_pos_of_hs_mode` mapper (the detector's output vocabulary, distinct
   from the pin-read `hsm_switch_pos_of_mode`). All 6 gate copies and the 6
   in-glue seed copies in `epomaker_split65.c:432-505` are gone; verified by `rg`
   (no residual `hs_modeio_detection(true` or `mode == hs_bt` in the board glue).
   `last_bt` is passed in because the persisted sub-index lives in board state
   (`confinfo`, defined in the `.c`, not a header) — this keeps `wls.c` free of
   board-only globals. Tests `detector_output_mode_maps_to_the_canonical_position`
   and `keycode_gate_permits_only_the_matching_position`. The invariant: *the "may
   this keycode act" rule is stated once and tested.*
2. **One transport-apply.** **DONE.** One `apply_switch_transport(pos, last_bt)`
   shell (`wls/wls.c`) resolves the pure `hsm_switch_apply` and sets BOTH
   selectors (`_noeeprom` host + vendor device index) from that one decision. All
   three switch-driven paths now call it: the two boot seeds
   (`epomaker_split65.c:212` in `keyboard_post_init_kb`, `:403` in
   `wireless_post_task`) and the runtime switch edge (`hs_modeio_detection`). A
   new `hs_mode_switch_pos()` is the single pin read, shared by the boot seed and
   the applier; `hs_mode_switch_devs` is deleted. This removed the last private
   `devs -> host` copy (a ternary at the early boot site that the defect-7 fix had
   missed) and the last hand-paired `connection_set_host_noeeprom` +
   `wireless_devs_change`. The early site's direct `wls_usb_connect` stays at the
   caller (a distinct concern: forcing the data line past the `_noeeprom`
   early-return gap, not choosing the transport). The invariant: *one pin read,
   two selectors, always paired — stated once.*

**Phase B — retire the "effect on time" shape (defect 8's class).**
3. **Indicator.** Done (defect 8) — record the rule: *an indicator is armed at a
   transition and terminates.*
4. **Audit every periodic re-derivation — DONE.** Two sites, two different
   verdicts, both now honest:
   - *The 1 s `md_send_devctrl` poll (`housekeeping_task_user`)* is a **genuine
     bounded poll**: an external USB-C cable can be inserted or removed while the
     keyboard is idle, with no keycode or switch event to trigger on, so the
     module must be told periodically. The periodicity *is* the rule, so it is now
     the named `WLS_MODULE_POLL_MS` (`wls.h`) rather than a bare `1000`.
   - *The `enable_bat_indicators` re-arm* was the **defect-8 shape**: a `bool` kept
     in lockstep with a parallel `bat_indicator_cnt` timer and re-derived every
     frame, to express a bounded one-shot suppression after an EEPROM reset. It is
     now one **deadline**, `bat_suppress_until` (0 = not suppressed), read as
     `timer_read32() < bat_suppress_until`; `hs_reset_settings()` *sets a
     transition* (`now + WLS_BAT_SUPPRESS_MS`) instead of flipping a flag. The bool
     and the counter are gone; the suppression expires on its own.

**Phase C — make the shell humble and the toolchain enforce it.**
5. **Localize globals.** **DONE.** The board file's file-scope mutable state was
   reduced to the smallest honest scope (Power of Ten Rule 6):
   - **Deleted 3 dead globals** — `mac_status`, `hs_ct_time`, `rgb_test_open`
     (each had exactly one reference: its own declaration).
   - **Deleted `pov`** — a write-only store at init and an immediate-consume at
     the 2 s master sync; both sites now pass `*md_getp_bat()` directly.
   - **`post_init_timer` → `static`** (used only in the boot-init group).
   - **`no_record_fg` → `static`** (all references in `process_record_user`).
   - **`buff[]` → `static const`** (read-only init table; indices 0 and `mode`).
   - **Bundled the five `wls_rgb_indicator_{timer,interval,times,index,rgb}`
     globals into one named `static struct wls_indicator`** — written together by
     `rgb_matrix_wls_indicator_set()`, consumed together by
     `rgb_matrix_wls_indicator()`, so the flash state has a name and one owner.
   The two that remain genuinely file-scope are honest: `confinfo` (persisted
   config) and `charging_state`/`bat_full_flag` (already exported via `wls.h`,
   written in `wls.c`). Verified by `rg` (no residual `wls_rgb_indicator_`,
   `pov`, `mac_status`, `hs_ct_time`, `rgb_test_open`).
6. **Table-drive `process_record_kb` — DONE (Phase C.6).** The mac/media
   remap decision was extracted to the pure core `wls/keymap_logic.{c,h}`
   (`filp_decide(keycode, is_mac) → filp_action_t`), with three tables
   (`filp_mac_only`, `filp_dual`, `filp_mac_special`) and one shell dispatcher
   (`filp_apply`) that performs the effects. Mode/layer logic no longer
   interleaves with HID emission (CMU 18-642). The `mor_map` loop keeps the
   Ctrl-combo rule (a different rule). Tested: `tests/keymap_logic` 5/5.
   `MOR_5` is declared in `keyboard.json:74` but handled by neither the original
   nor the new code — a pre-existing latent no-op, recorded here, not invented.
7. **Raise the toolchain floor.** `-Wextra` and `-Werror` for our files
   (`epomaker_split65.c`, `wls/`, `keyboards/linker/wireless/`), and build the
   pure-core test targets with `-fsanitize=address,undefined`. The invariant: *a
   class of defect cannot compile or cannot pass CI.*

**Phase D — close the loop on hardware.**
8. **Flash and verify** defects 7 and 8 on hardware (switch flip BT→USB routes
   without a power cycle; the right half does not blink on a non-connected
   channel). Then re-run the manual matrix (USB / 2.4 GHz / BT) and record results.

**Definition of done.** Every shell function passes the four-part test above; the
`tests/` suite covers every rule (not just the pure arithmetic); the build is
warning-clean at `-Wextra -Werror` for our code and sanitizer-clean for the pure
cores; and the hardware matrix in Phase D passes without a power-cycle workaround.
