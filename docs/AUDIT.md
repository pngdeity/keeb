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
| `wireless_2p4ghz_task()/init()` | **VIOLATION (new incompleteness)** — mirrors the BT contract but `keyboard.c` never calls it (unlike `bluetooth_init`/`bluetooth_task`) | FIX (add call sites or drop the contract) |
| `md_info.state` / `.indicator` | **DONE (fix 6)** — the module now owns the transition: `wireless_devs_change` calls `md_devs_changed()` (module.c) instead of poking `*md_getp_state()`/`*md_getp_indicator()`; no external writer reaches the registers (reads via the accessors remain) | **DONE** |
| `smsg_instance.state` | **VIOLATION** — decoder sets `replied` (`module.c:158`), send task sets the rest (`module.c:257-276`); no lock | FIX |
| `lpwr_state` / `lpwr_timestamp` | **VIOLATION** — `md_receive_host_cb` (`lowpower.c:121-133`, UART cadence) writes both alongside `lpwr_task` | **FC/S FIX** |
| `manual_timeout` | **VIOLATION** — `lpwr_is_allow_timeout()` is a query that *clears* it (`lowpower.c:145,150,155`) | **FC/S FIX** |
| `lpwr_wakeupcd` reset vs ISR | **VIOLATION** — non-atomic `= NONE` (`lowpower.c:272`) races the ISR `\|=` | FIX (critical section) |
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
