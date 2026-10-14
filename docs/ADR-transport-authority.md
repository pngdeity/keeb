# ADR: one owner for the transport decision

Status: **accepted (2026-10)**. This supersedes the transport-selection design
in `docs/BOARD-LAYER.md` where the two disagree; the concern split there still
binds. It records *why* the transport is being restructured and what the target
is, not the per-defect work (that is `docs/AUDIT.md`) or the measured hardware
facts (that is `docs/HARDWARE.md`).

## Context

The board chooses among three transports: USB, Bluetooth, 2.4 GHz. Until this
ADR the choice was made by **the physical 3-position switch alone**, read from
two pins (`C14`/`C15`), with the switch treated as absolute authority for its
own domain.

Two things broke that model.

1. **The switch can lie.** A hardware run produced a boot whose blink reported
   the *host* as 2.4 GHz (`MAGENTA`, step 1 — a colour that appears in exactly
   one place in the schedule) while the switch was physically on USB, and the
   board enumerated, lit up, and typed nothing. The pin read and the physical
   position disagreed; the firmware believed the pin.
2. **Power is not a host.** A dumb USB PSU raises the cable-detect pin (`B9`)
   and supplies VBUS exactly as a host does. So "a cable is attached" cannot
   distinguish "a host is talking to me" from "something is charging me".

The response was a **two-stage rule**: hints first (switch, cable, persisted
host), then the USB peripheral's own enumeration result (`USB_ACTIVE`) promoted
to outrank every hint, because only a real host reaches `USB_ACTIVE`.

That rule is correct and is kept. **Its implementation introduced a cycle.**

## The problem: the decision consumed a signal its own action cleared

```
   switch pins ─┐
   B9 cable ────┼──▶ decide() ──▶ connection_set_host_noeeprom()
   USB_ACTIVE ──┘                      │
        ▲                              ▼
        │                    connection_host_changed_kb()
        │                              ▼
        └────── USB line ────▶ wls_usb_connect() ──▶ restart_usb_driver()
                                                    (clears USB_ACTIVE)
```

`USB_ACTIVE` was an **input** to the decision, and driving the line was a
**consequence** of the decision. But `wls_usb_connect(true)` calls
`restart_usb_driver()`, which drops the driver out of `USB_ACTIVE`. The decision
therefore perturbed its own input. On a board whose switch read disagrees with
the resolved transport — the exact case the rule exists for — this closed into a
livelock: the board enumerated, self-detached, and re-enumerated about once a
second, forever. Measured: 11 enumerations / 10 disconnects in five minutes,
every device binding all three HID interfaces and then dropping the line.

Two instances were patched before the cycle itself was named:

- **the switch-edge predicate** (`hs_modeio_detection` asked "does the resolved
  transport differ from the pins?", which is *permanently* true under the new
  rule) — fixed by `hsm_switch_moved`, a true position edge;
- **the USB-activity edge** in `wls_lifecycle_housekeeping`, which re-armed
  itself on the `true → false` transition its own effect produced — fixed by
  making it promotion-only.

A third trigger (`hs_modeio_detection`'s position edge) was waiting behind them.

**Patching instances of a cycle is the wrong response. The cycle is the bug.**
This is the defect class the project had already named for the switch read — a
value sampled, translated into an action, where the action perturbs the value —
rebuilt at the system level.

Three deeper problems, in severity order:

1. **`connection_host_changed_kb` has the wrong contract.** Upstream fires it on
   "host changed"; the board discards the argument (`(void)host;`) and
   re-derives intent from the *live* resolved host. The physical line therefore
   follows an **observation**, not an **intent**, and every oscillation of that
   observation becomes a physical teardown.
2. **Five writers mutate `desired_host` unsynchronised** — the boot path,
   `hs_modeio_detection`'s edge, the appliers, the keycode path (which also
   persists to EEPROM), and `wls_split`. Nothing owns the transport.
3. **`USB_ACTIVE` is used as both an input and a consequence.** In one sentence,
   that *is* the cycle.

## Decision

**The transport gets one owner, and the data flow becomes one-way.**

1. **A single owner** (`wls_transport`) holds the committed transport. It is the
   only writer of the transport decision.
2. **It decides from inputs only** — switch position, the settled `B9` cable
   read, the persisted host. **`USB_ACTIVE` is not an input.**
3. **Host lifecycle arrives as events, not as polling.** The owner is told about
   host presence through the USB event queue (`USB_EVENT_CONFIGURED` /
   `USB_EVENT_UNCONFIGURED`, already handled in
   `tmk_core/protocol/chibios/usb_main.c`), never by reading a signal the owner
   itself can change.
4. **The line is driven on decision change only.** The actuator is a pure
   consequence of a decision transition and is never re-entered by an
   observation of its own effect.
5. **`connection_host_changed_kb` stops being a teardown trigger.** It either
   disappears or becomes a notification that cannot command the line.
6. **The decision is a pure function over an input alphabet,** events included,
   so a cycle of this shape becomes a **failing test** rather than a live
   livelock.

### The invariant

> **`wls_usb_connect` may only be called as the consequence of a decision
> change, and nothing in the line's own state may cause a decision change.**

This is the same shape as the project's other authority rules ("one authority
per state", "effect on a transition, never on time") applied to the one place
they were not.

## Consequences

**Gains**

- The livelock class becomes unrepresentable: a trigger that cannot depend on a
  signal its own effect modifies cannot re-arm itself.
- The switch keeps working as the user's primary affordance, but as a *hint*:
  a lying pin can no longer route keystrokes to a transport that is not there,
  because a confirmed host outranks it.
- The PSU case resolves correctly: no enumeration means no USB commitment, so a
  charger leaves the board wireless instead of silent.
- The decision becomes testable end-to-end without hardware, because the input
  alphabet — including events — is data.

**Costs and risks**

- The board can no longer be put on BT or 2.4 GHz by the switch **while the host
  cable is attached**; it will commit to USB. The upstream keychord
  (`connection_next_host()`) still reaches the other transports. This is the
  intended trade-off, not an accident.
- Moving host lifecycle onto the USB event queue means the firmware now depends
  on those events being delivered; the promotion-only polling is removed, so if
  an event is missed the transport will not self-correct until the next decision
  input changes. This must be verified on hardware.
- **Unresolved hardware fact, deliberately out of scope:** why the switch pins
  read `(1,0)` — 2.4 GHz — while the switch is physically on USB is still
  unmeasured (no multimeter available). This ADR makes the firmware *tolerate*
  that fault; it does not explain it. `docs/HARDWARE.md` keeps the open question.

## Alternatives considered

**Option A — enforce the invariant in place.** Remove `USB_ACTIVE` from the
decision inputs and drive the line only on `desired_host` transitions. Smaller
and it fixes the cycle, but it leaves five writers on one state and keeps
`connection_host_changed_kb` as a teardown path. Rejected as primary; it is the
fallback if the owner proves too large a change for the value.

**Keep the switch as absolute authority and debounce it.** Rejected: debouncing
addresses a *transient* misread, not a *stuck-wrong* pin, which is what was
observed. And it cannot answer the PSU/host question at all, because the
distinguishing information is not on the pins.

**Drop the switch from the firmware entirely.** Rejected: it is the only
hardware affordance for BT versus 2.4 GHz, and removing it makes the keyboard
wired-only, which deletes the project's headline capability.

## Status of the earlier work

The two-stage rule (`hsm_transport_decide`) and the hints
(`hsm_switch_apply_with_cable`, `wls_usb_cable_present`) are **kept** — they are
the correct decision. What changes is *who runs them and when*: one owner, on
decision change, with host lifecycle as events. The two hotfixes
(`hsm_switch_moved`, the promotion-only edge) are correct in themselves and are
subsumed by the owner rather than reverted.
