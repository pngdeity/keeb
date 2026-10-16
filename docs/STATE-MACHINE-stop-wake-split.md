# The stop/wake × split composite

**What this document is.** A *composite state machine*: the product of the low-power
machine (`lowpower.c`) and the split-link machine (`wls/wls_split.c`, `wls_lifecycle.c`)
that **no file in the tree owns**. It exists because the relations between those two
machines were *underdetermined* — entailed by the code jointly and stated by none of it —
and that is where the 2026-10-15 30 s dark-board fault lived
(`docs/DETERMINATION.md` §II.3 artefact 1, `TODO.md` §8).

**How it was derived.** Not by the codebase's shape. By **symptom-directed backward
slice** over data, control, **shared state** and **transition guards**, per
`docs/DETERMINATION.md` §I.9. The slicing criterion is the symptom, which is an
observable the hardware can state:

- **The dark panel** — `rgb_matrix_enable_noeeprom()` (`lowpower.c:301`) was not reached.
- **The silent slave** — the `USER_SYNC_MMS` wake (`WLS_SPLIT_CMD_WAKEUP`, `0xCC`) was
  never sent.

Every line citation below was read in the file. Nothing here is inferred.

---

## 0. The invariant this document gives a home

> **An effect must not be applied unless its undo is reachable from the state the
> application leaves the machine in.**

Two consequences, each of which was violated:

> **S1 (panel).** PRESLEEP must not be enterable unless the STOP transition is
> available. (PRESLEEP disables the matrix; only WAKEUP re-enables it; a refused STOP
> goes to NORMAL, not WAKEUP.)

> **S2 (slave).** A half that has been *ordered* asleep must be *released* by a command
> that is reachable on the transport it will wake on. (The slave arms its own stop on
> `0xAA`; the release `0xCC` is gated on not-USB; the user wakens on USB.)

S1 is now **executable** — the pure predicate `lpwr_presleep_is_allowed_decide`
(`lowpower_logic.c:34`) with a test composed from the real deciders
(`tests/lowpower_logic`). S2 is now **executable too** — the pure predicate
`wls_split_can_order_sleep` (`split_logic.c`) with a test composed the same way
(`tests/split_logic`), and the master's presleep send routed through it
(`wls_lifecycle.c`). The condition it enforces is stated once, in `split_logic.h`:
*a half may not be ordered asleep on a transport where its release is suppressed.*
The liveness half below remains **not** determined by any artefact.

---

## 1. Machine A — the low-power machine (per half, `lowpower.c`)

`lpwr_task()` (`:313-372`) is a four-state machine. The states are `lpwr_state_t`
(`lowpower.h:6-11`): `LPWR_NORMAL`, `LPWR_PRESLEEP`, `LPWR_STOP`, `LPWR_WAKEUP`.

| From | Guard | Effect | To |
|---|---|---|---|
| `NORMAL` | `lpwr_presleep_is_allowed_decide(lpwr_is_allow_timeout(), lpwr_stop_is_allowed())` | clears `manual_timeout` | `PRESLEEP` |
| `PRESLEEP` | `lpwr_is_allow_presleep()` ∧ `lpwr_stop_is_allowed()` | **`lpwr_presleep_cb()` → `rgb_matrix_disable_noeeprom()` (`:230`)**, `suspend_power_down()` | `STOP` |
| `PRESLEEP` | `lpwr_is_allow_presleep()` ∧ ¬`lpwr_stop_is_allowed()` | **`lpwr_wakeup_cb()`** — the abort, added by the fix | `NORMAL` |
| `STOP` | `lpwr_is_allow_stop()` ∧ `lpwr_stop_is_allowed()` | `lpwr_enter_stop()` — the MCU actually sleeps | stays `STOP` until an interrupt sets `WAKEUP` |
| `STOP` | `lpwr_is_allow_stop()` ∧ ¬`lpwr_stop_is_allowed()` | refusal: `lpwr_set_state(LPWR_NORMAL)` (`:267-268`), **no matrix re-enable** | `NORMAL` |
| `WAKEUP` | `lpwr_is_allow_wakeup()` | **`lpwr_wakeup_cb()` → `rgb_matrix_enable_noeeprom()` (`:301`)**, `suspend_wakeup_init()` | `NORMAL` |

**The three facts the tree states separately and nowhere together:**

1. The matrix is disabled in `lpwr_presleep_cb()` (`:230`) — a *different function*
   from the state case that calls it.
2. The matrix is re-enabled in `lpwr_wakeup_cb()` (`:301`) — a *third function*, and it
   runs only from the `WAKEUP` case (`:367-372`), never from `NORMAL`.
3. The `STOP` refusal (`:267-268`) goes to `NORMAL`. **Therefore a refused stop after
   PRESLEEP has run leaks a dark matrix permanently.** This is S1's violation.

**The arming.** `manual_timeout` is *permission*, not an order to sleep
(`lowpower.c:123-125`; consumed in `lpwr_timeout_allowed_decide`,
`lowpower_logic.c:20-32`, as `manual_pending`). It is set at three sites, all of them
board-side:

| Site | When |
|---|---|
| `wls.c:305` | `HSM_LINK_ACT_RECONNECT` |
| `wls.c:308` | `HSM_LINK_ACT_SLEEP` |
| `wls_indicator.c:181` | low-battery order (`wls_order_sleep(true)` immediately before) |
| `wls_split.c:60` | **the slave**, on receiving `0xAA` |

Only the last two also set `ordered_sleep` — and `ordered_sleep` is what the stop policy
requires (below). So the **armed-but-unordered** rows (`wls.c:305,308`) are the ones that
reach PRESLEEP and are then refused: the exact board state of the 30 s dark board.

---

## 2. The guard (the edge that refuses, and the shared state behind it)

`lpwr_stop_is_allowed()` is a weak symbol. Board code overrides it at `wls.c:389-421`:

```
lpwr_stop_is_allowed() = lpwr_stop_is_allowed_decide(is_keyboard_master(), wls_sleep_ordered())
                       = is_keyboard_master() && ordered_sleep        (lowpower_logic.c:6-11)
```

`ordered_sleep` (`wls.c:47`) is **file-static in the board layer**, written by
`wls_order_sleep()` (`wls.c:49`) and read by the guard. Its only `true` writers are the
low-battery path (`wls_indicator.c:180`) and the slave's `0xAA` handler
(`wls_split.c:59`); its only `false` writer is the post-stop release
(`wls.c:439-441`, gated on the *local* half reaching `LPWR_WAKEUP`).

**This is why a call-graph slice misses the fault.** `ordered_sleep` is file-static board
state that outlives the statements that touch it, and the *shared* lowpower machine reads
it only through a weak override. A slice over the call graph sees `lowpower.c` calling
`lpwr_stop_is_allowed()`; it does **not** see that the value derives from state set in a
different file by a different machine. `docs/DETERMINATION.md` §I.9 step 3 flags exactly
this as the hand-added relation.

---

## 3. Machine B — the split machine (across the two halves)

The wire is upstream's `USER_SYNC_MMS` RPC; the *rules* are `wls/split_logic.{h,c}`
(pure) and its shell `wls/wls_split.c`. By command:

| Cmd | Meaning (`split_logic.h:19-27`) | Decided action (`split_logic.c:18-38`) | Slave's effect (`wls_split.c:48-76`) |
|---|---|---|---|
| `0x55` | sync multimode | `SYNC_DEVICE_INDEX` | `wls_module_devs_change(...)` |
| `0xAA` | order the slave to stop | `ORDER_SLEEP` | **`wls_order_sleep(flag)` + `lpwr_set_timeout_manual(true)`** — the slave arms its **own** stop |
| `0xBB` | master is suspending | `NONE` | nothing (deliberate — the slave must not force its own rail off) |
| `0xCC` | master woke: re-assert the rail | `REAPPLY_RAIL` | `wls_led_rail_apply()` **and nothing else** — no `wls_order_sleep(false)`, no `lpwr_set_timeout_manual(false)`, no `suspend_wakeup_init()` |
| `0xDD` | reset settings | `RESET_SETTINGS` | `wls_reset_settings(...)` |

**The asymmetry that is S2.** The slave's ordered sleep is *set* by `0xAA` and *cleared*
only by the slave's own `lpwr_stop_hook_post()` (`wls.c:433-442`) — which requires the
slave to reach `LPWR_WAKEUP`, i.e. to actually wake from a real stop. `0xCC` does not
clear it. So if `0xCC` is not received, the slave has no path out of its order.

**And the sender is USB-gated.** `WLS_SPLIT_CMD_WAKEUP` (`0xCC`) has exactly **one** call
site in the tree: `wls_lifecycle.c:179`, inside
`wls_lifecycle_suspend_wakeup_init_user()`, which **returns before it on USB**
(`:175-177`):

> *"While cabled the rail must stay up on both halves; broadcasting it would extinguish
> the slave's backlight."*

So on USB the master sends the slave **no wake at all** — and USB is the transport the
user returns to. The master is alive (its USB enumerates, its matrix scans, it types);
the slave is ordered asleep with its release never sent. **Left half types, right half
does not.**

**The cross-half contract, stated together for the first time:** *the master must never
order the slave to sleep on a path that can return to a transport where the wake is
suppressed.* Neither half's source states this; each half's local protocol is
self-consistent.

**How the contract is now enforced (2026-10-15).** The rule is a pure predicate,
`wls_split_can_order_sleep(sends_wake_on_this_transport)` (`split_logic.{h,c}`), and the
master's presleep send routes through it (`wls_lifecycle.c`): on USB the `0xAA` order is
skipped entirely, so the slave is never ordered on a transport that cannot release it. The
suppression fact is derived the same way the sole `0xCC` call site derives it
(`wireless_get_current_devs() != DEVS_USB`), so the two cannot disagree. Tested in
`tests/split_logic` (11 tests), composed the S1 way. The *liveness* half — that an order
once given is *eventually* released — remains undetermined (§5).

---

## 4. The composed machine (the product, which the fault lived in)

```
                 ┌─────────────────────── MASTER (left) ───────────────────────┐
                 │                                                             │
  switch USB→BT  │  hs_rgb_blink_hook()  wls.c:287                             │
  ──────────────►│    hsm_link_watch(...) → HSM_LINK_ACT_RECONNECT             │
                 │        md_send_devctrl(...); lpwr_set_timeout_manual(true)  │  ← arms, does NOT order
                 │                                                             │
  idle 30 s      │  lpwr_task() NORMAL:  timeout_allowed ∧ ¬stop_allowed       │
  ──────────────►│    → REFUSED at the new gate  (was: entered PRESLEEP)       │
                 │                                                             │
                 │  ── with the fix, nothing irreversible has happened ──      │
                 └─────────────────────────────────────────────────────────────┘
                 ┌─────────────────────── SLAVE  (right) ──────────────────────┐
                 │  user_sync_mms_slave_handler  0xAA (from presleep path)     │
                 │    wls_order_sleep(true); lpwr_set_timeout_manual(true)     │
                 │    → slave now ordered + armed; may enter its own STOP      │
                 │                                                             │
  switch BT→USB  │  master: wireless_get_current_devs()==DEVS_USB              │
  ──────────────►│    wls_lifecycle_suspend_wakeup_init_user() RETURNS         │
                 │    ✗ 0xCC NEVER SENT                                        │
                 │  slave: still ordered, release unreachable  →  SILENT      │
                 └─────────────────────────────────────────────────────────────┘
```

The master's column is now safe (S1 determined executably). The slave's column **was**
the open fault (S2) and is now determined executably too — the master no longer orders a
sleep it cannot release (`wls_split_can_order_sleep`, §3). **The two columns remain
independent**, which is why §8's fix did not restore the right half: it took a second,
separate change, and the release path itself (`0xCC` on USB) is not yet asserted.

---

## 5. What is determined, weakly determined, and undetermined

| Property | Home | Rung (`II.2`) |
|---|---|---|
| S1: PRESLEEP needs the STOP transition | `lpwr_presleep_is_allowed_decide` + test | **executable** |
| The arm sites and their ordering (`ordered_sleep` vs `manual_timeout`) | this document, §1 table | prose |
| S2: an ordered half must have a reachable release | `wls_split_can_order_sleep` + test | **executable** |
| The composite's liveness (a half, once ordered, *eventually* released) | nothing | **undetermined** |

The last row is the honest one: the tree has no statement, no test, and no guard for the
*liveness* half of S2. `docs/DETERMINATION.md` §I.4 (safety vs liveness) names the
distinction; S2's *safety* half (never order an unreleasable sleep) is now executable, but
its *liveness* half (a sleep once ordered is eventually released) still has no home above
prose.

---

## 6. What this document implies for the fix of S2

Per `docs/DETERMINATION.md` §II.2, in ascending strength:

1. **Prose (done here).** The contract in §3 is now written down.
2. **Executable (done, 2026-10-15).** `wls_split_can_order_sleep(sends_wake_on_this_transport)`
   (`split_logic.{h,c}`), pure, with the composition tested the way S1's is
   (`tests/split_logic`, 11 tests): *"order sent on a transport whose wake is suppressed ⇒
   refuse."* The master's presleep send (`wls_lifecycle.c`) now routes through it, so on USB
   the order is skipped rather than stranding the slave. The suppression fact is derived as
   `wireless_get_current_devs() != DEVS_USB` — the same predicate the sole `0xCC` call site
   uses.
3. **Unrepresentable.** Make the master's order and its release a single transaction
   whose handle cannot exist without naming a transport on which the release is
   reachable. Expensive; the honest target, not the next step.

**Not to be done in this document:** writing the fix. `docs/DETERMINATION.md` §II.4 (a
candidate, not yet adopted) says *name the property's home before writing the fix* — this
document named it, and the fix (rung 2) was then written as a separate, aimed change with
its own test vectors.

---

## 7. Provenance

- Symptom and session: `TODO.md` §8, `docs/OBSERVATIONS.md` (2026-10-15).
- The rule violated, its class: `docs/FINDINGS.md` "the recurring defect is one class".
- The derivation method: `docs/DETERMINATION.md` §I.9 (traversal by symptom-directed
  slice), §II.3 artefact 1 (this composite named as the primary missing artefact).
- The S1 fix and its test: submodule `d596e9a79c`; `lowpower_logic.{h,c}`,
  `tests/lowpower_logic/lowpower_logic_tests.cpp` (13 tests).
- The S2 fix and its test (rung 2, 2026-10-15): `split_logic.{h,c}`
  (`wls_split_can_order_sleep`), `wls_lifecycle.c` (the presleep send routed through it),
  `tests/split_logic/split_logic_tests.cpp` (11 tests).
