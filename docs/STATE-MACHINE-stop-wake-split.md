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
The liveness half — that an order given *is* released — is now determined too, and wired:
see §5's last row.

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

**And the sender was USB-gated by convention.** `WLS_SPLIT_CMD_WAKEUP` (`0xCC`) has exactly
**one** call site in the tree: `wls_lifecycle.c`, inside
`wls_lifecycle_suspend_wakeup_init_user()`, which **returned before it on USB** with a bare
`if (wireless_get_current_devs() == DEVS_USB) return;`:

> *"While cabled the rail must stay up on both halves; broadcasting it would extinguish
> the slave's backlight."*

That early return was a *convention*, exactly the shape the order executor removed one step
back, and it left the safety argument's premise (the release is sent whenever it is reachable)
with no home — D2. It is now the release handle (`wls_sleep_release_open()`,
`wls_sleep_release_permitted()`, and the words-form `wls_split_can_send_relay()`), taken by
both relay sites: `0xCC` in this hook and `0xBB` in
`wls_lifecycle_suspend_power_down_user()`. The two endpoints consume the same fact derived the
same way, so **the transport that may not order is exactly the transport that may not
release**.

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
once given is *eventually* released — is now determined and wired (§5).

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
separate change. The release path itself (`0xCC` on USB) is now asserted as well — the release
handle of §5's last row (D2).

---

## 5. What is determined, weakly determined, and undetermined

| Property | Home | Rung (`II.2`) |
|---|---|---|
| S1: PRESLEEP needs the STOP transition | `lpwr_presleep_is_allowed_decide` + test | **executable** |
| S1: the state is writable only by the machine | `bin/guard-invariants` (3 checks) | **unrepresentable** |
| The arm sites and their ordering (`ordered_sleep` vs `manual_timeout`) | this document, §1 table | prose |
| S2: an ordered half must have a reachable release | `wls_sleep_order_open` + `tests/split_logic` | **unrepresentable** |
| S2: the order is constructible only when a release is reachable | `wls_sleep_order_t` (handle) | **unrepresentable** |
| The composite's liveness (a half, once ordered, *eventually* released) | `wls_sleep_order_outlived_release` + the `wls.c` record + `tests/split_logic` | **executable, and wired** |
| S2: the release is sent only where it is carried (the sender's gate) | `wls_sleep_release_open` + `wls_split_can_send_relay` + `tests/split_logic` + `bin/guard-invariants` | **unrepresentable at the seam** |

The liveness row was the honest gap: the tree had no statement, no test, and no guard for the
*liveness* half of S2. `docs/DETERMINATION.md` §I.4 (safety vs liveness) names the
distinction; S2's *safety* half (never order an unreleasable sleep) is now unrepresentable, and
its *liveness* half (a sleep once ordered is eventually released) is now **executable** —
`wls_sleep_order_outlived_release(sent_at, now, release_transport_still_carries, released)` in
`split_logic.{h,c}`, which states the fault in the only form the master can observe, since it
cannot see the slave. Six vectors in `tests/split_logic` and a `bin/guard-invariants`
check. **The wiring is now made as well (2026-10-15)**: the rule had no caller — nothing recorded
that an order had been sent, so no check could run. The record is `wls_sleep_order_record_t`
(`split_logic.h`), held in `wls.c` with one writer each way
(`wls_note_sleep_order_sent()` on the `0xAA` send, `wls_note_sleep_order_released()` on the
`0xCC` send), and `hs_sleep_order_liveness_check()` — master, wireless only, on the module-poll
tick — consults the predicate and **reports** the residue to the diagnostic rather than acting,
because the recovery the master owns (reaching a transport that carries `0xCC`) is the switch, a
person's decision. A guard keeps the record at exactly one writer each way.

**The last row is D2, and it is a different fact.** The liveness row is "the release happens in
time"; the release *sender*'s rule is "the release path is correct at all". The `0xCC`/`0xBB`
pair relay the slave's LED rail, so both are gated by the transport; that gate was a bare
`if (== DEVS_USB) return;` at each site — a convention, not a precondition, which left the
safety argument's premise (*the release is sent whenever it is reachable*) unstated and
unowned. It now has a home: `wls_sleep_release_open(sends_release_on_this_transport)` returns a
handle permitted exactly when the release is carried, taken by both relay sites; the words-form
`wls_split_can_send_relay()` sits beside `wls_split_can_order_sleep()` so both endpoints read
alike. Because both opens consume the same fact derived the same way, the pair **cannot
disagree** — pinned by `the_order_and_the_release_cannot_disagree` in `tests/split_logic`
(26 tests) and kept by two negative-tested guards. **D1 and D2 are both closed.**

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
3. **Unrepresentable (both S1 and S2 done 2026-10-15).** See §6a for S1 and §6b for S2.
   For S1, the unsafe *entry* is no longer writable, checked by a guard. For S2, the
   single-transaction form exists: the order cannot be **constructed** unless a release is
   reachable, so "an order without a reachable release" is not a state the shell can write.
   S2's *liveness* half is now done too — see §5's last row (predicate, record, guard).

### 6a. Rung 3 for S1 — the unsafe order is now unwritable (2026-10-15)

The gate added in rung 2 (`lpwr_presleep_is_allowed_decide`) **refused** an unsafe entry to
`LPWR_PRESLEEP`, but it did not make the entry *unwritable*: the state was exposed as a
public free-writer, `lpwr_set_state(state)`, so any of six other files could have named
`LPWR_PRESLEEP` directly and bypassed the gate — re-creating the very defect rung 2 fixed,
without any test going red. Rung 3 removes the possibility:

- `lpwr_set_state()` is gone. The only writer is a **file-static** `lpwr_transition()`
  inside `lowpower.c` (`lowpower.c:68`), so the machine owns its own transitions and no
  external translation unit can name a state.
- The public surface keeps `lpwr_get_state()` (read) and gains
  `lpwr_request_wakeup()` (`lowpower.c:73`) — the one transition an outside caller may
  legitimately force, and one that **can only restore, never strand** (it enters
  `LPWR_WAKEUP`, whose callback re-enables the matrix). The generic resume path in
  `md_receive_host_cb` now routes through it rather than writing state directly.
- Three checks were added to `bin/guard-invariants`: no public state setter in the header,
  `lpwr_transition` is file-static, and no file outside `lowpower.c` writes the state. Each
  was **negative-tested** — the invariant was deliberately broken and the guard failed, then
  the tree was restored and it passed.

The property this determines: *the low-power state is writable only by the state machine.*
It is the rung-3 form of S1's rule. It does not replace rung 2 — a reordering *inside*
`lowpower.c` is still caught by the rung-2 test — it closes the bypass.

### 6b. Rung 3 for S2 — the order cannot be constructed without a reachable release (2026-10-15)

Rung 2 (`wls_split_can_order_sleep`) **refused** an unsendable order, but it was a
convention, not a precondition: the send was still a plain call
(`wls_split_send(WLS_SPLIT_CMD_SLEEP, ...)`) that any caller could make after forgetting to
ask, or after asking and disregarding the answer. Nothing in the type of the operation said
"this may only happen when the release is reachable."

Rung 3 makes the right a **precondition of constructing the order**:

- `wls_sleep_order_t` (`split_logic.h`) is a small executor. The only way to obtain one is
  `wls_sleep_order_open(sends_wake_on_this_transport, sleep_flag)`, which returns a handle
  whose `permitted` is exactly the contract — and there is no path that produces a permitted
  handle for an unreachable wake.
- The shell (`wls_lifecycle_lpwr_allow_presleep()`) no longer decides anything: it derives
  the transport fact as before, opens the handle, and sends **only** if the handle permits.
  The flag it sends is carried by the handle, so the body the slave reads cannot be
  reconstructed independently of the decision.
- 5 vectors pin it at the construction site (`tests/split_logic`, 16 tests): the handle is
  unpermitted for *every* flag when the wake is suppressed; permitted when it is reachable;
  it carries the flag unchanged; it agrees with `wls_split_can_order_sleep()` for both
  transports (the stricter form must not be more permissive than the rule it formalises); and
  a null handle is never permitted.

The property this determines: *an order without a reachable release is not representable.*
That is S2's *safety* half, at the rung-3 strength S1 now has. **What it does not determine:**
*liveness* — that an order, once given, is *eventually* released. The handle proves a release
was reachable at the moment of ordering; it does not prove the release is taken. That is §5's
last row, now determined and wired there (predicate + record + guard).

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
- The S1 rung-3 change and its guard (2026-10-15): `lowpower.c` (`lpwr_transition` static,
  `lpwr_request_wakeup`), `lowpower.h` (the public setter removed),
  `bin/guard-invariants` (three checks, negative-tested).
- The S2 rung-3 change and its vectors (2026-10-15): `split_logic.h` (`wls_sleep_order_t`,
  `wls_sleep_order_open`, `wls_sleep_order_permitted`), `split_logic.c` (the handle opened
  from the contract), `wls_lifecycle.c` (the presleep send built from the handle),
  `tests/split_logic/split_logic_tests.cpp` (16 tests).
