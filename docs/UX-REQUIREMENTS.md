# UX requirements — what a person must be able to infer from the keyboard

Up to now this project has organized itself around **engineering** requirements:
a power-only cable must not force USB (mode 2), a real enumerating host wins
(mode 3). Those are correct, but they are not user outcomes — and per § 1.5 they
are **derived from** the user-facing requirements, not a layer beside them. This
document states the **user-facing** requirements: what the keyboard owes a person
at the desk, in what they can see and do, and what a reasonable person should be
able to infer from the board without reading any of our documentation. **Every
engineering requirement is downstream of this document.**

It is a **requirements** document, not a description. What the keyboard does
*today* is in `docs/USAGE.md`; what the LEDs mean *as a debugging instrument* is in
`docs/INDICATORS.md`. This file states what those must become, and how we will
know a requirement is met.

> **Why this document exists.** The 2026-10-14 dark-board event is the founding
> example. Every engineering check passed — transport was USB, `usb_line=1`, the
> board typed, `0xA4` answered — and the user's experience was **a dead
> keyboard**. The board was healthy and the *experience* was broken. That gap is
> what a UX requirement names, and it is why "it passes the tests" was never a
> sufficient bar.

---

## 0. The method — how these requirements were derived, and how they are verified

Per `docs/METHOD.md` § I.1, a standard is stated **with its measurement** before
it is applied. The standard here is the human-interface literature, and the
measurement is a **heuristic evaluation** (§ 6), with **user observation** when a
person is available.

### 0.1 The source

**Primary: the *Macintosh Human Interface Guidelines* (Apple, 1992).** Chosen
over the current (2026) web HIG for a specific reason: it was written when *the
computer was an object you sat at*, not a screen you carry. Its principles are
about how a physical object should behave, which is what a keyboard is. Modern
Apple, Nielsen, and connected-device UX (see § 0.4) are used where they add
something the 1992 text did not cover.

**A caveat that must be stated up front:** the 1992 examples are
**screen-centric** — menus, dialog boxes, windows, alert panels. The *principles*
transfer to a keyboard; the worked examples do not. Every keyboard-specific rule
below that is not a direct quotation is marked **[derived]** and names the
principle it derives from. Nothing here is presented as a citation that is a
derivation.

### 0.2 Apple's design process — the four steps we follow

Verbatim from the 1992 HIG, Chapter 3 ("Involving Users in the Design Process"):

1. **Define Your Audience** — and per the 80 Percent Solution (§ 0.3), *which*
   audience.
2. **Analyze Tasks** — "imagine a scenario in which a user uses your product.
   List each task… then break each task apart into its component steps…
   **Order the steps according to how people do them.**" The doc must then be
   readable back to a person as a usable procedure.
3. **Build Prototypes** — storyboards of the experience. For firmware, a
   storyboard is a **state/indication table** (§ 3) precise enough to be checked
   before it is built.
4. **Observe Users** — § 6.

**Apple's cost list for every added feature** (Chapter 3, "Design Decisions"),
which is the discipline for the whole document — each feature "increases the
number of possible user errors" and "can have an impact on an existing feature."
A UX requirement that adds an indicator is not free; it must earn its place.

### 0.3 Scope discipline — the 80 Percent Solution

Verbatim: *"your design meets the needs of at least 80 percent of your users. If
you try to design for the 20 percent… who are power users, your design will not
be usable by the majority."*

**Applied here as a two-pass method, in this order:**

1. **Write the complete vocabulary first** — every state we *can* distinguish,
   with an indication we *could* render (§ 3).
2. **Then trim to the 80%** in an explicit
   **§ 8 "What we deliberately do not indicate"** — so the trimming is a decision
   on the record, with a reason, not an omission.

The justification for the second pass is Apple's **Feature Cascade**: *"it's very
tempting to include additional features that users claim they want. It takes a lot
of restraint to stick to the original intent."*

### 0.4 The evaluation lens

**Nielsen's 10 heuristics** (Nielsen & Molich, 1990) are the **evaluation
method**, applied in § 6. The four that bind hardest here:

- **#1 Visibility of system status** — "the design should always keep users
  informed about what is going on, through appropriate feedback within a
  reasonable amount of time."
- **#5 Error prevention** — "good error messages are important, but the best
  designs carefully prevent problems from occurring in the first place."
- **#6 Recognition rather than recall** — "the user should not have to remember
  information from one part of the interface to another."
- **#9 Help users recognize, diagnose, and recover from errors** — "plain
  language (no error codes)."

Nielsen's **gulf of evaluation** is the framing for the whole document: *"Only by
knowing what the current system status is can you change it."*

**Connected-device UX** adds the rule that this board needs most: a connected
product has **compound state**, and pressing distinct situations into one generic
"not connected" forces the user to debug the system by trial and error. The
distinctions a user must not have to make by guesswork: **powered-off vs
out-of-range** ("same symptom… opposite fixes"); **available vs claimed**
("not broken, just taken").

### 0.5 Capability derivation — how we establish what may be surfaced

Before a requirement may say *"the keyboard indicates X"*, we must know **X is
possible on this hardware**. The method is a four-stage pipeline, and it exists
because both of the other approaches are wrong on their own:

| Stage | Input | Evidence class | Failure if skipped |
|---|---|---|---|
| **1. Intended** | the vendor's documentation | what the *designer promised* | design for capability never built |
| **2. Actual** | our measurements + the vendor source in the tree | what the hardware *is* | design around a fiction |
| **3. Possible** | the **intersection** of 1 and 2 | what can actually be delivered | impose vendor behaviour we cannot honour, or ignore capability already built |
| **4. UX** | the possible set + this document's requirements | what we *choose* to surface | surface capability the 80% does not need |

**Stage 3 is an intersection, not a union.** Neither source alone is sufficient:
the manual describes intent that may not exist, and our measurements describe
what we happen to have exercised, not what the hardware was built to do.

**The vendor is an OEM, and its documentation is a claim, not a fact.** Epomaker
manuals are aspirational at worst and approximate at best; a documented
capability is therefore a **hypothesis to test against stage 2**, never a
requirement in itself. Every claim the manual makes is treated as *unverified
until the hardware or the vendor source in the tree confirms it*, and the stage-3
table records which claims are confirmed and which remain unmeasured.

**The intent ranks are ordered by authority, and this matters for which source to
trust.** Three ranks exist, each more authoritative than the last:

1. **the vendor's manual** — the reseller's marketing and support text;
2. **the ODM's protocol in the tree** (`linker/wireless/module.h`, `md_frame.c`) —
   the interface the firmware actually speaks;
3. **upstream QMK's own documentation** (`qmk_firmware/docs/`) — the plate's
   contract.

**A reseller's literature is never more authoritative than the ODM's or
upstream's**, and where they disagree, the disagreement is itself a finding
(resolve it at the source, do not pick a side). Note also that rank 3 states
*upstream's* implementation status, not this board's capability — "not yet
implemented" upstream is **not** evidence a capability is absent here.

**Three acceptance states, not two, because some claims cannot be tested by us.**
A capability that stage 2 can test is either **confirmed** or **refuted**. But
where the instrument needed to test it is unavailable — the case for anything
behind the module's closed image, which has **no dump or update path**
(`docs/FINDINGS.md`) — the claim is **unfalsifiable-by-us**: recorded as such, and
**never promoted to a requirement on the strength of the claim alone**. This is a
stronger state than "unverified": an unverified claim is one we have not measured
yet; an unfalsifiable one is one we currently *cannot*. Neither becomes a
requirement; both stay on the record with their reason.

**Stage 4 is where the 80 Percent Solution applies (§ 0.3).** "Possible" is not
"required". The output of stages 1–3 is a *set of capabilities*; the UX is the
subset the primary audience needs, and § 8 records what was deliberately left out.

A requirement that cites this method is **[derived]**, exactly as elsewhere in
this document. Five worked examples are written up, all in the same form:
§ 0.6 (2.4 GHz), § 0.7 (Bluetooth), **§ 0.8 (the split half)**, **§ 0.9 (the
link, as a state set)** and **§ 0.10 (the host, as a readable state)**.

### 0.6 Worked example — 2.4 GHz, stages 1–3 (stage 4 deferred)

The dongle is the transport the owner's four circumstances never asked for
(§ 1.1), so its capability set was derived explicitly rather than assumed. Stage 4
(the UX choice) is **deferred**; this records what stages 1–3 established.

**Stage 1 — intended** (Epomaker manual & product page): switch to the 2.4G
position; hold **`Fn+R`** 3–5 s to pair (indicator blinks fast); *"when the
indicator light stops flashing, the connection is done"* (steady = connected);
**one** slot (contrast BT's three); `Fn+B` battery check in wireless mode;
**1000 Hz** and **5 ms** on 2.4 GHz vs **125 Hz** / **15 ms** on BT; deep sleep
30 min, backlight off 5 min.

**Stage 2 — actual** (our measurements + vendor source):

| Claim | Status | Evidence |
|---|---|---|
| One slot, first-class index | **confirmed** | `DEVS_2G4 = 6`; `hsm_devs_is_bt()` excludes it (`transport_logic.c:12-13,34`) |
| Switch selects it | **confirmed** | `hsm_boot_devs` `HSM_SWITCH_2G4` → `HSM_DEVS_2G4` (`transport_logic.c:54-55`) |
| Hold-to-pair / tap-to-reconnect | **confirmed** | `hsm_long_press_devs(HSM_KC_2G4)` → `HSM_DEVS_2G4` (`transport_logic.c:210-211`); tap → `bluetooth_select_profile` (`wls_keymap.c:148-154`) |
| The module pairs it | **confirmed** | `md_devs_change` `case DEVS_2G4` → `DEVCTRL_2G4` (0x30), + name/`vpid`/`CLEAN`/`PAIR` on reset (`module.c:460-472`; `module.h:55`) |
| Flash→steady indicator | **confirmed** | `wls_indicator.c:310-316` — 200 ms blink on reset, 500 ms otherwise |
| Battery over the radio | **built, never observed** | `md_inquire_bat()` fires on any non-USB host (`wireless.c:252-258`); `MD_REV_CMD_BATVOL` → `md_info.bat` (`module.c:520,223`) |
| Dongle enumerates | **confirmed** | `342d:e4c6`, `2.4G Dongle`/`MILE`, raw-HID **interface 2**, `0xA4` round-trips (`HARDWARE.md:129-140`) |
| **5 ms / 1000 Hz** | **UNVERIFIED** — vendor spec only, never measured here (measurable: 2.4 GHz *does* carry input, unlike BT — see § 0.7) | none in tree |

**Stage 3 — possible.** Everything the manual documents, the hardware can do, and
almost all of it is **already built**: 2.4 GHz is the **degenerate case of the BT
state machine** — one slot, the same hold/tap grammar, the same flash→steady
indicator, plus a battery inquiry that already fires on it. **No new mechanism is
required.** Two measurements are owed and are recorded as **unverified**, not
assumed — and unlike BT's (§ 0.7 item 4), these are **merely unmeasured, not
unfalsifiable**, because the 2.4 GHz path does carry input: **(a)** that the link
is actually 5 ms / 1000 Hz, and **(b)** that the battery readback completes over
2.4 GHz.

**Stage 4** is the UX choice and is **not made here** (deferred by the owner).

### 0.7 Worked example — Bluetooth, stages 1–3

**"Intended" is not one source but a rank-ordered stack**, and Bluetooth is where
that becomes visible. Each rank is more authoritative than the one above it:

| Rank | Source | What it is | Weight |
|---|---|---|---|
| 1 | **Epomaker's manual** | the reseller's marketing and support text | **hypothesis only** — aspirational at worst (§ 0.5) |
| 2 | **the ODM's protocol in the tree** (`linker/wireless/module.h`, `md_frame.c`) | the module vendor's own opcodes and states — the interface the firmware actually speaks | strong |
| 3 | **upstream QMK's `docs/features/wireless.md`, `battery.md`** | the *plate's* contract | authoritative for the **contract**, not for this board |

**Stage 1 — intended.** Rank 1: three slots `Split65-1/2/3`, hold `Fn+Q/W/E` 3–5 s
to pair (indicator blinks fast, stops when connected), tap to toggle, **125 Hz /
15 ms**, `Fn+B` battery check, 30 min deep sleep *"will interrupt Bluetooth
connectivity"*, and **"NKRO in all modes"**. Rank 2: **five** slots
(`DEVS_BT1..BT5`, `DEVCTRL_BT1..BT5` 0x31–0x35); five states — `PAIRING`,
`CONNECTED`, `DISCONNECTED`, **`REJECT`** — plus a reserved **`UNPAIRED`** (0x37);
per-transport sleep (`SLEEP_BT_EN/DIS` 0x55/0x56); a second pairing path
**`FORCED_PAIRING_BT` (0x62, factory-only)**; the module reports its own
**battery** (0x5C) and **firmware version** (0x5D). Rank 3: the profile keys
(`QK_BLUETOOTH_PROFILE1..5`), `QK_BLUETOOTH_UNPAIR`, and the 2.4 GHz output
keycodes are all **"not yet implemented"** upstream — so their presence here is
*ours*, not a conformance obligation — and upstream states that *"the currently
supported Bluetooth chipsets do not support NKRO"*.

**The rank-1 source is the poorest and is contradicted twice:** three slots where
the protocol has five, and "NKRO in all modes" where upstream says the chipset
class cannot do it. Two intent sources disagreeing is a signal to go to the
source, not to pick one.

**Stage 2 — actual** (measured):

| Claim | Status | Evidence |
|---|---|---|
| Five slots in the protocol | **confirmed** | `DEVS_BT1..BT5` (`module.h:8-14`), `DEVCTRL_BT1..BT5` |
| Five states including `REJECT` | **confirmed** | `module.c:207-218` |
| `REJECT` **modelled and carried** | **yes — end to end** | `module.c:216-218` → `wls.c:283` → `HSM_LINK_REJECT` (`transport_logic.h:307`) |
| `REJECT` **acted on or rendered** | **NO — treated as inert** | `hsm_link_watch` groups it with `NONE`/`PAIRING` → `HSM_LINK_ACT_NONE` (`transport_logic.c:275`); no renderer consumes it (`wls_indicator.c` paints BT1..BT5 identically regardless) |
| `UNPAIRED` (0x37) | **reserved and unused** | the ODM marks it reserved; handled nowhere |
| `FORCED_PAIRING_BT` used | **NO** — factory-only, correctly unused | no board caller |
| Battery readback over BT | **built, never observed** | `md_inquire_bat()` on any non-USB host (`wireless.c:256`); `battery_driver_sample_percent()` reads `*md_getp_bat()` (`wls_battery_driver.c:15-17`) |
| **Keystrokes over BT** | **BROKEN — the known fault** | the GATT layer rejects CCC writes with ATT `0x0E`; no input flows |
| Manual's "3 slots" | **contradicted by source** | the protocol has five |
| Manual's "NKRO in all modes" | **UNVERIFIED, and contradicted by rank 3** | upstream: unsupported on this chipset class |
| Sleep opcodes actually sent | **confirmed** | `wls_lifecycle.c:266-267` |

**Stage 3 — possible.** The capability is present and mostly **unexposed**:

1. **A distinguishable failure state exists end-to-end and dies at the renderer.**
   The module *reports* `MD_STATE_REJECT` (`module.c:216-218`), the board maps it to
   a real core state `HSM_LINK_REJECT` (`wls.c:283`, `transport_logic.h:307`) — and
   then nothing acts on it: `hsm_link_watch` folds it into `HSM_LINK_ACT_NONE`
   alongside `NONE` and `PAIRING` (`transport_logic.c:275`), and no renderer paints
   it distinctly. So **X-2** (no look-alike with opposite action) and **X-1** (a
   terminal, distinguishable outcome) are implementable **with data already
   arriving, through a state already modelled**: the missing piece is indication
   policy, not plumbing. *Same shape as § 0.6, one layer further along.*
2. **Un-pair has a reserved opcode** (`UNPAIRED`, 0x37) and a plate keycode
   (`QK_BLUETOOTH_UNPAIR`, unimplemented upstream). Today reclaim is whole-slot
   wipe (`DEVCTRL_CLEAN`); per-host un-pair is the finer instrument for **X-21**.
3. **The manual's NKRO claim is contradicted by rank 3** — upstream states this
   chipset class cannot do NKRO over BT. Recorded as **unverified**, not adopted:
   the aspirational claim § 0.5 predicted.
4. **Rate and module behaviour are unfalsifiable-by-us, which is stronger than
   unverified.** BT's advertised **125 Hz / 15 ms** cannot be checked because
   input does not flow over BT at all — *the advertised rate cannot be verified
   because the transport does not deliver keystrokes*. And the cause is behind the
   module's closed image: the GATT layer rejects the notification-enabling writes
   (`0x0E`), and the module has **no dump or update path**. So every claim that
   depends on module behaviour is **unfalsifiable-by-us** (§ 0.5): we have no
   instrument that can test it. Nothing here is promoted on a claim alone.

**Deep source available, deliberately not exercised:** `DEPENDENCIES.md` records
that the module's BLE stack is a *symbolized* `ar` archive
(`openwch/ch583` `LIBCH58xBLE.a`, 67 named objects, disassemblable). That is the
strongest stage-2 instrument that exists for this module — but reading it is a
hardware-reversing session, not a documentation review.

**Stage 4** (the UX choice) is **not made here.**

### 0.8 Worked example — the split half (stages 1–3, stage 4 stated)

The split is the board's most distinctive property and the only surface where
**one keyboard is two objects with independent state**. § 4 already carries the
requirements (X-13…X-15); what follows is the derivation behind them, which was
previously asserted. It is run here because a *dark half* is the exact case
`docs/METHOD.md` Part II exists for, and because the derivation shows the
half-state is **already measured end-to-end** and dies at the same place § 0.7's
does: the renderer.

**Stage 1 — intended** (rank-ordered per § 0.5). Rank 1 (the reseller's material):
a split 65% board, "both halves work independently", each half bears its own USB-C
and its own mode switch. Rank 2 (**the ODM's own configuration, which is the real
intent source here** — `keyboard.json`): `split.handedness.pin = "B9"`,
`split.matrix_pins.right` distinct from the left, per-half `matrix_pins`, a
right-half encoder, and — the decisive line — `split.transport.sync` with
`activity`, `indicators`, `layer_state` and `matrix_state` all **true**, i.e. the
design intends the halves to stay **synchronised**, not to lead separate lives on
separate transports. Rank 3 (upstream): `is_keyboard_master_impl()` is
`usb_bus_detected()` — *the half with the host cable is the master* — with
`SPLIT_HAND_PIN`/`B9` feeding handedness.

**Stage 2 — actual** (measured):

| Claim | Status | Evidence |
|---|---|---|
| Handedness is a **pin**, not an EEPROM flag | **confirmed** | `keyboard.json` `split.handedness.pin = "B9"`; no `EE_HANDS`/`MASTER_RIGHT`/`SPLIT_HAND_PIN` macro anywhere in the board (`config.h` has neither) |
| Master = **the half with the cable** | **confirmed** | the board overrides `is_keyboard_master()` (default keymap) to read `B9` **settled** (`wait_us(100)`); upstream's weak impl is `usb_bus_detected()` |
| The role is therefore **runtime, not fixed** | **confirmed** | mastery follows the cable: plug the host into the right half and it becomes master. Corollary: the right half is not *inherently* the slave — the board is symmetric, and the asymmetry arrives at runtime |
| The halves **exchange their device index** | **confirmed** | `master_sync_mms_slave(wireless_get_current_devs(), …, *md_getp_bat())` every 2 s (`epomaker_split65.c:168-173`) → `WLS_SPLIT_CMD_SYNC_MULTIMODE` (0x55) → the slave calls `wls_module_devs_change(last, now, false)` |
| The sync carries **the same index twice** | **measured, and the point** | the live call passes `(now, now)` — `epomaker_split65.c:172` — so the slave is told the master's index, but never told that *it is a sync* (no last/now distinction reaches the wire) |
| The slave **adopts the master's device index** | **confirmed** | `wls_split_decide_slave()` → `WLS_SPLIT_ACT_SYNC_DEVICE_INDEX` → `wls_module_devs_change` on the slave (`wls_split.c:49-50`) |
| The **wire is clamped** (a corrupt byte cannot become state) | **confirmed** | `WLS_SPLIT_DEVS_MIN/MAX` 0..6, out-of-range rejected (`split_logic.h`, `wls_split_decide_slave`) |
| The master-gated work is real and named | **confirmed** | master only: the transport decision, `hs_rgb_blink_hook`, the low-battery sleep order, the battery renderer, the split sync itself, the module's own sleep send (`wls.c:298,330,338`; `wls_lifecycle.c:205,217`; `wls_indicator.c:138`) |
| A dark half is **rendered** (not a mystery) | ~~confirmed~~ **NO** | nothing distinguishes "intentionally dim/off" from "lost link/power"; the slave's rail is dropped by its *own* suspend path and only re-raised by `0xCC` when the master wakes — **a dark slave with a lit master is reachable, and renders as a plain dark half** |
| **Which half is the slave** is observable | **NO** | `B9` is *cable detect* — the board never publishes "I am this half", so neither half can *say* its role to the user; it can only *be* it |

**Stage 3 — possible.**

1. **The half-state is synchronised by design and by wire, and the one thing
   that is not synchronised is the one the user sees.** `split.transport.sync`
   intends the halves to agree; `WLS_SPLIT_CMD_SYNC_MULTIMODE` enforces it every
   2 s. And yet **nothing renders any of it**: `wls_indicator.c` has no notion of
   the half state, so X-13 ("tell from either half that both are alive and
   linked") and X-14 ("a dark half must be attributable") are implementable
   **from data that already crosses the link** — the missing piece, exactly as in
   § 0.7, is indication policy.
2. **The role is a runtime fact derivable from the cable read.** `B9` settles to
   "this half has the host", which is precisely what makes it master. So
   "which half am I" is not a new capability — it is a re-read of an existing pin
   — and X-15 ("no indicator may require the user to hold a belief about which
   half is master") becomes satisfiable *without* the user needing the answer:
   the board can know it for itself.
3. **`KC_BATQ`'s `im_bat_req_charging_flag` is a second, narrower example in the
   same family** — it is a request flag, not a rendered state, so a query key
   exists whose *answer* has no dedicated display (`wls_keymap.c:337-343`).

**Stage 4 — the UX choice, stated.** Because the halves are synchronised by
configuration, the 80% does not need **per-half transport** legibility — a split
keyboard is *one* keyboard, and X-29 forbids the halves settling on different
hosts. What the 80% needs is only **(a)** "both halves are alive and linked"
(X-13), **(b)** "this half is dark on purpose, not lost" (X-14), and **(c)** it
works from either half (X-15). Per-half *state* is deliberately **not** surfaced;
the existence of a synchronisation channel is what makes that safe.

### 0.9 Worked example — the link, as a state set (stages 1–3)

§ 0.7 derived BT and § 0.6 derived 2.4 GHz. Neither derived the thing they have in
common: **the set of link states the board can be in, and which of them the user
can distinguish.** This is the derivation behind X-1, X-2 and X-30, and it is the
one that found X-30 in the first place.

**Stage 1 — intended.** Rank 1 (Epomaker): the indicator blinks fast while
pairing and "stops when connected". Rank 2 (**the ODM protocol** — the
authoritative one): **five** states on `MD_REV_CMD_DEVCTRL` (0x5B),
`NONE`/`PAIRING`/`CONNECTED`/`DISCONNECTED`/**`REJECT`** (0x31/0x32/0x33/0x36 —
`module.h:18-22`, `module.c:207-218`), plus a reserved `UNPAIRED` (0x37). Rank 3
(upstream): `connection_host_t` models *which host* is selected, not the link's
health — upstream has no vocabulary for "the link rejected us".

**Stage 2 — actual** (measured):

| Claim | Status | Evidence |
|---|---|---|
| The module reports **five** link conditions | **confirmed** | `MD_STATE_NONE/PAIRING/CONNECTED/DISCONNECTED/REJECT` decoded from 0x5B sub-codes |
| The board **maps all five** to core states | **confirmed** | `hs_link_state()` → `HSM_LINK_NONE/PAIRING/CONNECTED/DISCONNECTED/REJECT` (`wls.c:274-286`) |
| The core **acts** on all five | ~~confirmed~~ **NO** | `hsm_link_watch` groups `NONE`/`PAIRING`/**`REJECT`** into one actionless arm → `HSM_LINK_ACT_NONE` (`transport_logic.c:275`) |
| The renderer **shows** all five | ~~confirmed~~ **NO** | no renderer consumes the link state at all; `wls_indicator.c` paints a per-transport flash and nothing per-link-state |
| The host channel reports it | **confirmed** | the `wls_diag` byte `link_state` carries the raw `MD_STATE_*` (0..4) |
| A state the firmware **carries** is therefore **flattened** | **confirmed — this is X-30** | `REJECT` and `DISCONNECTED` render identically while requiring **opposite** user actions (fix the host's pairing vs wait/re-pair) |

**Stage 3 — possible.** The capability is **five-for-five present and three-fifths
rendered**. `NONE` and `PAIRING` legitimately share an "in progress" render; the
flattening that matters is **`REJECT` collapsing into `DISCONNECTED`-look-alike**,
which is exactly what X-2 forbids. So the requirement is not "add a state" (the
state exists, is transported, and is already in the `0xA4` block) — it is **"stop
flattening"**: a render must exist for every state the board carries, or the
state must be *deleted* from the vocabulary. The general rule this yields is X-30
itself: **a carried state is never silently flattened.**

**Stage 4** (the UX choice — *which* render for `REJECT`) is **not made here**;
it is the A7 work item, and X-9/X-11/X-12 (no colour-only, no reused pattern,
two cues) constrain it.

### 0.10 Worked example — the host, as a readable state (stages 1–3, stage 4 stated)

X-20 and X-21 exist because § 1.1's four circumstances made "which host am I on?"
a **primary** question. This derives what the board can actually say about it.

**Stage 1 — intended.** Rank 1 (Epomaker): three BT slots, `Fn+Q/W/E`, and a
`Fn+B` battery check. Rank 2 (**the ODM protocol**): **five** slots
(`DEVS_BT1..BT5`, `DEVCTRL_BT1..BT5` 0x31–0x35), `DEVCTRL_PAIR` as the only connect
verb, `DEVCTRL_CLEAN` to wipe a slot, and a reserved `UNPAIRED` (0x37). Rank 3
(upstream): `QK_BLUETOOTH_PROFILE1..5` and `QK_BLUETOOTH_UNPAIR` exist **in
`keycodes.h`** but upstream marks them **"not yet implemented"** — so their
presence here is ours.

**Stage 2 — actual** (measured):

| Claim | Status | Evidence |
|---|---|---|
| The protocol has **five** slots | **confirmed** | `DEVS_BT1..BT5`, `DEVCTRL_BT1..BT5` |
| The board exposes **three** as keycodes | **confirmed** | `KC_BT1/2/3` at `[2,1]..[2,3]`; `KC_2G4` at `[2,4]` (`keymap.c`, `keyboard.json` keycodes) |
| The **core handles all five** | **confirmed** | `hsm_devs_is_bt()` accepts BT1..5; `wls_indicator.c` renders `DEVS_BT4`/`DEVS_BT5` — **but on LED indices 41/42 with the same `RGB_BLUE`**, so the profile is not distinguishable by colour |
| The **active host** is readable by a host | **confirmed** | the `0xA4` reply carries transport and BT profile (`hsm_profile_of_devs`) |
| The **active host** is readable on the **board** | ~~confirmed~~ **surfaced only as a momentary flash** | `wls_indicate_devs()` fires once on a genuine transition and then goes dark — a *transition* indicator, not a *state* indicator, so "which host am I on?" is unanswerable at rest |
| A guest's slot is **reclaimable** | **confirmed, coarsely** | `DEVCTRL_CLEAN` wipes a slot; there is **no per-host un-pair** (the reserved `UNPAIRED` 0x37 is unused) |

**Stage 3 — possible.** The capability is **five slots present, three surfaced, and
the state not readable at rest.** So X-20 ("the active host is a readable
**state**") is implementable with no new mechanism — the index is in hand, the
render path exists, and the missing piece is that the render is owed to a
*transition* rather than held as a *state*. X-21's measured promise follows
directly: since the only connect verb pairs into a slot, the honest requirement is
**"occupies a slot that can be taken back"**, not "leaves nothing behind".

**Stage 4 — stated.** The 80% needs *which host*, not the slot number as a datum;
a two-cue render (X-12) satisfies it, and the guest case (X-23) requires it be
readable **without knowing our conventions**. Deliberately **not** surfaced: the
raw index, and per-half host state (X-29 forbids the halves differing).

---

## 1. Audience

**Primary audience (the 80%): one person, with both hands, using the keyboard
across several of their own hosts, daily, and occasionally handing it to someone
else.** The audience is derived from **four circumstances the owner actually
described** (§ 1.1), not from a label. The circumstances settle two questions the
first draft conflated, and the conclusion is: **one owner, many hosts** — those
are separate axes and only the second was ever in doubt.

### 1.1 The four circumstances (the evidence)

Given by the keyboard's owner, verbatim in substance, as places and situations
where this keyboard is actually intended to be used:

| # | Where | Host | Cable present | Transport wanted | Why |
|---|---|---|---|---|---|
| 1 | Home office | **Desktop** | yes | **USB** | ordinary desk use |
| 2 | Library | **Laptop** (on its own battery) | *may* be present | **wireless** | *"charge the keyboard through an external power brick while using it wirelessly with the laptop, so as to not drain the laptop's power"* |
| 3 | Presenting | **Phone** | no | **wireless** | the laptop could not reach the projector; the phone becomes the presentation machine and the keyboard becomes the presenter's interface — *"I'm used to pressing space to advance slides in case I'm nervous at the lectern"* |
| 4 | A friend's house | **the friend's laptop** | not wanted | **wireless** | the friend needs *"a lot of writing homework… lots of keystroke-heavy work"*, once; *"I want to get my friend working as soon as possible, so I don't want to have to deal with cables"* |

**Four circumstances, four different hosts, one owner.** That is the whole
resolution.

### 1.2 What each circumstance proves

- **Circumstance 2 *is* engineering mode 2, measured from the user side.**
  "Charge through a brick while using it wirelessly" is exactly "a power-only cable
  must not force USB". The engineering mode and a real user's stated need are the
  same requirement — **the user statement is the parent, the engineering statement
  the derivation** (§ 1.5) — and this is the first place the document has a *user*
  behind a rule rather than a derivation.
- **Circumstances 3 and 4 are the same requirement in two dresses**: connect, with
  no cable and no fuss, **now**.
- **Circumstance 4 is the harder bar of the two**, because the person typing is
  **not the owner and has never seen the keyboard**. That is the only circumstance
  where *the reader is not the user*, and § 1.4 turns it into a requirement.
- **Circumstance 3 is not a different host, it is a different *task*.** Space-to-
  advance is "present", not "type". It is also the only circumstance where
  **failure is severe and unattended** (a dropped link stops the slides in front of
  an audience) and the only one where the user is **away from the keyboard at the
  lectern** — so its state must be readable *at setup*, and then must not change.
  § 1.4 states this as a stability requirement.
- **One host is USB and three are wireless.** The switch's three positions map onto
  this cleanly: USB (1), BT (2, 3, 4). **2.4 GHz is never asked for** — worth
  noting, since it is the one transport with a dedicated dongle and no circumstance.

### 1.3 One owner, many hosts — and why the first draft's phrase was wrong

The first draft said *"one owner, one desk"*. **That phrase is not a term from any
source; it was my coinage, and it was wrong** — in a document whose whole method is
"cite the standard or mark the derivation", it read as a citation. It merged two
claims and got the axes confused:

- **Habit and bilateral use (defensible, from Gemmell):** a split board's
  adaptation cost is **weeks**, and its purpose is that "your two hands sit on two
  different computers". That cost is only rational for a **habitual** user. This
  implies *one person*, and *repeat contexts* — but **repeat contexts plural, not
  one desk**.
- **"One owner" (my addition, and refuted by the evidence):** circumstance 4 is
  shared use *by design of the situation*, and the module supports **five** bonds.
  Being the *owner's* keyboard does not mean it talks to one machine, and does not
  mean nobody else ever types on it.

**So the audience is one owner, multi-host, occasionally shared** — three facts, no
contradiction, and the first draft collapsed them into one.

### 1.4 Consequences **[derived]**

- **A.** Indication must be readable **at a glance from a normal typing posture** —
  no leaning, no re-seating, no host tool.
- **B.** Anything that changes spontaneously (a mode, a link) must be visible
  **while it is in effect**, not only when it changed (§ 5).
- **C.** The user must not have to **remember** a mapping between indication and
  meaning (Nielsen #6). If a colour carries a meaning, position or count must carry
  it too (§ 3.4).
- **D.** Because the board is multi-host, **the active host is a state the user must
  be able to read.** X-4's "indicate the active mode" therefore extends from *which
  transport* to **which host**, and the first draft's trim of "BT profile number" in
  § 8 was the wrong call (now corrected there).
- **E.** **A first-time user must be able to read the board** (circumstance 4). The
  board may not require knowing the owner's conventions, or which half is master
  (X-15), to answer "which machine will this type into, and is it connected?" This
  is the constraint that makes the guest case work without the owner present.
- **F.** **A presentation session must survive unattended** (circumstance 3): once
  the link is up it must stay up, and no indicator may require interaction to
  remain legible.

**Secondary audience (the 20%):** the owner when debugging (the `0xA4` host
readback, `docs/INDICATORS.md`) and anyone reading this repo. Served by the
instrument contract; must not shape the primary experience.

### 1.5 The three usage modes, subsumed

The three modes this project was originally organized around — (1) wireless while
discharging, (2) wireless while charging, (3) USB while charging — are **not a
requirement layer beside this one.** They are the *engineering* form of the user
requirements above, and they are **derived from them, not the reverse**. They were
the project's early goalposts, written before the board was usable over USB, and
they are subsumed here so there is one requirements set and one direction of
derivation:

```
user experience  →  requirement (X-n)  →  interface  →  implementation
```

An engineering requirement has **no independent authority**: it can be wrong only
by failing to serve its user-facing parent. The mapping, stated so the modes stay
recoverable from the requirements rather than asserted alongside them:

| Usage mode | User-facing parent | Why it is the same requirement |
|---|---|---|
| 1. Wireless while discharging | **X-20**, **X-24**, **X-25** | "serves the host the person chose, and stays there" — no cable involved. |
| 2. Wireless while charging | **X-20** (§ 1.2: circumstance 2 *is* this mode) | the person charges from a brick and keeps typing on the laptop; a power-only cable must not force USB. |
| 3. USB while charging | **X-4**, **X-20** | the switch's USB position is the person's stated intent, and USB is one of the hosts X-20 makes readable. |

Two consequences follow, and both are re-derivations rather than new policy:

- **`README.md` and `docs/FINDINGS.md` frame these as the top-level requirements.**
  They are the implementation's shape, not the project's end. They stay documented
  (the transport work needs them in engineering terms), but they are referenced
  *from here*, not the other way round.
- **`TODO.md`'s Tier 1 states them as goals.** Under this derivation a Tier-1 item
  is an *implementation* step serving an X-n; when it is re-stated it must cite its
  parent, and it can only be "done" when the parent's observation shows.

---

## 2. Task analysis — the experiences, step by step

Ordered the way a person actually does them (Apple: "Order the steps according to
how people do them").

### 2.1 "Connect the keyboard to a computer" (the founding task)

| # | The person does | What they must be able to tell | Where it is indicated |
|---|---|---|---|
| 1 | Picks a transport at the **switch** | that the switch's position **is** the intent, and the board accepted it | § 3, the transport state |
| 2 | Turns the keyboard on / plugs it in | that it is **alive** (not dark-because-dead) | § 4, "alive" |
| 3 | Waits for the link (BT/2.4 GHz only) | **which** of: pairing, connected, failed, still trying | § 3, the link state |
| 4 | Tries to type | whether the link is **carrying input** or only powered | § 3, the link state |

**Requirement X-1.** For every step above, the board must present a state the
person can act on. **An indefinite "connecting…" with no end is worse than an
honest failure** (connected-device UX) — every link attempt must have a
**timeout** and a **terminal, distinguishable outcome** (Nielsen #1, #9).

**Requirement X-2.** No step may require the person to **guess between two
situations that look the same but need opposite actions** — the powered-off /
out-of-range problem. In particular, "the board is dark" must not be the sole
signal for more than one distinct condition (§ 4).

**Requirement X-30.** Where the hardware **already reports** a distinct condition,
the board must surface it rather than reduce it to the nearest coarse state. The
measured case: the module reports five link states — `PAIRING`, `CONNECTED`,
`DISCONNECTED`, and **`REJECT`** — and the board carries all five into the core
(`module.c:216-218` → `wls.c:283` → `HSM_LINK_REJECT`), **but then treats
rejection as inert**: `hsm_link_watch` folds it into `HSM_LINK_ACT_NONE` with
`NONE` and `PAIRING` (`transport_logic.c:275`), and no renderer paints it apart
from an ordinary non-connection. **"Rejected" and "not connected" need opposite
user actions** (fix the host's pairing vs wait/re-pair), so this is X-2's exact
failure, with both the data and a modelled state already in hand. The rule is
general: **a state the firmware carries is never silently flattened** (§ 0.5,
§ 0.7).

### 2.2 "Change the mode" (the switch)

**Requirement X-3.** The mode switch is changed **many times in a work session**,
so by Apple's own rule ("Implementing Preferences": choices changed often must be
accessible *modelessly*, and their state visible) **its current position must be
visible at all times** — which the physical switch satisfies, provided the
*consequence* of the position is also visible (§ 5).

**Requirement X-4.** Because the switch is a **mode** in Raskin's exact sense
("any state in which the same user action produces a different result"), and
because mode errors occur *"where an interface makes the current mode hardest to
notice: a change that happened silently… or one masked by something else stealing
the user's attention"* — the keyboard must indicate the active mode **while the
switch is in that position**, redundantly with the switch's own position § 3.4.

### 2.3 "Is my keyboard charged / charging?"

**Requirement X-5.** Charge state must be readable **without a host** (the
keyboard is wireless; a host tool cannot be the only channel). It must
distinguish **charging / full / discharging / low** — and it must not claim
**full** when it does not know (§ 7, honesty).

### 2.4 "Something is wrong — recover it"

**Requirement X-6.** Every failure the user can reach must have a **recovery the
user can perform at the desk**, and the board must make it *findable* (Nielsen #9:
plain language, no codes). Where a recovery destroys saved state, the board
must make that consequence **visible in advance** (Apple's **Forgiveness**: "create
safety nets"; and the sharp diagnostic, *"frequent alert boxes are a good
indication that something is wrong with the program design"* — a board that
constantly needs recovery is a design defect, not a user error).

### 2.5 "The board looks dead"

**Requirement X-7 (the 2026-10-14 lesson).** A board whose backlight is
**intentionally dimmed to zero** must never be indistinguishable from a board that
is **off, asleep, or faulted**. This is the founding requirement of this document;
see § 4.

### 2.6 "Hand the keyboard to someone else" (circumstance 4)

Ordered as the guest experiences it, which is *not* the owner's order — the guest
starts at the middle:

| # | The guest does | What they must be able to tell, unaided |
|---|---|---|
| 1 | Is handed the keyboard | nothing yet — the owner may have set it up |
| 2 | Types | **whether their keystrokes are going anywhere**, and if not, where the board *is* pointed |
| 3 | Looks at the board | which machine it will type into — **without knowing our conventions or which half is master** |

**Requirement X-20.** Because the board serves four hosts (§ 1.1) across one USB
and three wireless ones, **the active host is a readable state**: which transport is
committed, and — on BT — **which** host. The first draft trimmed this as a
power-user distinction; the four circumstances reverse that. This is X-4 extended
from *which transport* to *which host*. *(Derivation: § 0.10 — five slots exist,
three are surfaced, and the render is owed to a **transition**, not held as a
state, which is the whole gap.)*

**Requirement X-21.** A transient, one-off host must be **usable and leave no
permanent claim**: the guest connects without the owner explaining anything, and
the profile slot the guest used is **reclaimable** afterwards. *Measured from
source:* the protocol exposes no non-bonded connection — `DEVCTRL_PAIR` is the only
connect verb and always pairs into one of five slots (`module.c:475-514`), while
`DEVCTRL_CLEAN` wipes a slot. So the correct promise is not "leaves nothing behind"
but **"occupies a slot that can be taken back."**

**Requirement X-23.** The board must be legible to a **first-time reader**. This is
the only circumstance where the reader is not the user, and it is the constraint
that makes X-15 (no indicator may require knowing the master half) load-bearing
rather than tidy.

### 2.7 "Present from the keyboard" (circumstance 3)

The task is **not** "connect to a phone"; it is "keep advancing slides, from the
lectern, with an audience watching."

**Requirement X-22.** Once a link is up for a talk, it must **stay up unattended**,
and the board's state must be readable **at setup** and then legible **without
interaction**. Failure here is asymmetric and severe — a dropped link stops the
slides in front of an audience — so this is a *stability* requirement on the length
of a session, not just on its start. It is also the one task where the user's hands
are not on the keyboard for most of its duration, so **nothing may require a
keypress to remain readable**, and the sleep policy (§ 5) must not be able to
darken the board mid-talk.

### 2.8 "Keep typing on the other machine" (alternating hosts — the KVM case)

**Not in the four circumstances; derived from the hardware.** `KC_BT1/2/3` are
*keycodes*, and a short tap selects a profile: `connection_set_host()` →
`bluetooth_select_profile(devs, false)` (`wls_keymap.c:148-154`). **Measured: it
works while the board is live, with no reboot and no switch movement.** So the
board can alternate machines mid-session — the user types on the desktop, taps a
key, and types on the phone.

**The measured cost, which is the requirement.** `bluetooth_select_profile()`
changes the device index through `wireless_devs_change()`, which **resets the
module link state** (`wls_bluetooth.c:46-58`). So selecting a host **tears down the
link being left**. That is acceptable for a deliberate switch, but it means the
switch is *destructive to the other link* and the user must not be able to trip it
by accident, nor be left unsure which host is now live.

**Requirement X-24.** When more than one host is paired, **switching hosts is
deliberate, immediate, and its result is unambiguous** — the user must be able to
tell which host is active *before* typing into it, and the switch must not be
confusable with an ordinary keypress. *(Gating note, measured:* `hs_keycode_allowed()`
refuses a wireless keycode unless the switch is on BT (`transport_logic.c:174-193`),
so this path is only live in BT mode.)

### 2.9 "It must just work again tomorrow" (the daily round)

**Not in the four circumstances; derived from them.** Every circumstance involves
connecting, and three are repeat visits (home office, library, presenting from the
same phone). The unstated requirement is that the *repeat* is a **no-op**: the board
defaults to last-known-good without the user re-selecting anything.

**Measured:** a *dropped* link reconnects automatically —
`HSM_LINK_DISCONNECTED` re-arms `HSM_LINK_ACT_RECONNECT` on a repeating 30 s
`HS_LBACK_TIMEOUT` (`transport_logic.c:249-261`, `wls.h:26`), poking the module via
`MD_SND_CMD_DEVCTRL_USB`. A fresh boot relies on the switch + persisted index
(`wls_transport_decide(WLS_TRANSPORT_INPUT_HINT)`) plus the module auto-connecting
its last bond.

**Requirement X-25.** After a power cycle or an idle gap, the board must return to
the **same host it used last** without the user acting, and if it cannot, it must
say so rather than fail silently into a dead-looking state (X-2, X-7).

### 2.10 "Charge it and leave it" (idle-cabled)

**Not in the four circumstances, but ordinary.** The board cabled and **not in use**
is its own state: the only question is "is it charging / is it full?". This is where
X-7 (dark-but-alive) and the charge indication carry the whole message, because
nothing else is happening.

**Requirement X-26.** A cabled, idle board must still answer "am I charging, and
how full?" — without the user typing, and without a host tool.

### 2.11 "Read the board from a machine that is not typing" (the monitoring host)

**Derived from a channel that already exists.** `host/battery_polybar.py` speaks the
`0xA4` raw-HID protocol (`--info`, `--pull`, `--listen`). So a host can *monitor* the
keyboard without being its typing target — on the desktop, polybar shows battery.
The asymmetry this exposes: **monitoring requires the committed transport to be
USB** (the reply is unreachable otherwise — the wireless driver has no
`.send_raw_hid`), so when the board is on the radio, the monitoring host sees
nothing.

**Requirement X-27.** The state a monitoring host can read must be **honest when it
is stale**: a host tool that cannot reach the board must say *"no reply"* rather
than showing the last value as current (which `--info` already does — the
requirement makes that a *contract*, not a convenience).

### 2.12 "Use one half" (accessibility, and the split hazard)

**From the literature (Apple 1992 Ch. 2 *Universal Access*: "build in support for
universal access from the beginning"), and from the hardware.** A split board can be
**positioned** for a body a one-piece board cannot fit — this is the keyboard's
strongest accessibility property, and the document currently has no accessibility
requirement. Its corollary is *one-handed operation*: half the board set aside.

**The hazard that must be forbidden explicitly.** The two halves are independent
endpoints, so `left = BT1, right = BT2` is **reachable** — each hand on a different
machine. This is almost certainly never wanted and must not be reachable by accident.

**Requirement X-28.** Accessibility is an explicit audience: the board must remain
fully usable when the halves are **widely separated**, and must not require both
halves to be in the same place or the same posture.

**Requirement X-29.** The two halves must **not** be able to settle on **different
hosts** without it being obviously wrong — a split keyboard is one keyboard, and
"each hand on a different machine" must be either impossible or unmistakable.

---

## 3. The state vocabulary

One named state, one rendering per channel. This section is written **complete**
(per § 0.3); § 8 then trims it.

### 3.1 The states

The board's observable condition is the product of a few independent facts. Each
is already a real, distinct state in the firmware — this section gives each a
**name a person could use**.

| Name | What it is | Firmware source |
|---|---|---|
| **transport** | which pipe the keys go down: USB, BT, 2.4 GHz | `hsm_switch_pos_t`, the persisted index |
| **link** | whether that pipe is up: none, pairing, connected, disconnected, rejected | `md state`, `MD_STATE_*` |
| **alive** | the MCU is running (not asleep, not dark-from-zero) | rail + brightness, § 4 |
| **charge** | charging / full / discharging / low | `charging_state`, `bat_full_flag`, level |
| **mode** | the switch's position (the user's stated intent) | switch pins |
| **split** | per-half: is *this* half working — the two halves can differ (§ 4) | per-half |

### 3.2 The channels

Three channels exist, in order of who can see them:

1. **The RGB matrix** — the only channel visible across a dark room and the only
   one that survives an early-boot fault (`docs/INDICATORS.md`).
2. **The host channel** (`0xA4` raw HID) — precise, but requires a host and a
   tool, so it is **never** sufficient alone (§ 2.3).
3. **The physical switch position** — always visible, but a mode without a
   displayed consequence (§ 2.2).

**Requirement X-8.** Every state in § 3.1 that the 80% needs (§ 8) must be
rendered on the **RGB matrix**, because that is the only channel that survives
the situations where the answer matters most.

### 3.3 The rendering rules

**[derived] from Apple, Ch. 2, "Universal Access", verbatim:**

> **"Don't create software that uses only color coding to convey important
> information. Color coding should always be redundant to other types of cues,
> such as text, position, or highlighting."**

**Requirement X-9.** No user-facing state may be conveyed by **colour alone**.
Every colour meaning must be redundant with **position** or **pattern** or
**count**.

This is already the *instrument's* rule — `docs/INDICATORS.md`: "the pulse count
carries the message, colour only groups it" — but there it is a debugging
convenience. Here it becomes a **user-facing requirement**, cited to the 1992
source.

**Requirement X-10 (dim, don't remove).** From Apple's **Perceived Stability**:
*"Even when particular actions are unavailable, they are not eliminated from a
display but are merely dimmed."* A state that is **off/unavailable must be shown
as dim or dark in a patterned way — never simply absent**, because absence is
indistinguishable from a fault (§ 4).

**Requirement X-11 (don't invent new elements).** From Apple's "Extending the
Interface": (1) *"Build on the Existing Interface"*; (2) *"Don't Assign New
Behaviors to Existing Objects"* — *"When you need a new behavior, design a new
element for it. If elements behave differently in different situations, the
interface becomes unpredictable"*; (3) *"Create a New Interface Element
Cautiously."* So a new LED pattern must not reuse an existing pattern with a
second meaning, and a new pattern must be justified against the existing ones.

**Requirement X-12 (redundant cues).** At least **two** independent cues per
important state — e.g. colour **and** position, or pattern **and** count — so a
colour-blind user, or a user glancing from the side, still gets the message.

### 3.4 The split-specific channel

The two halves are **separate physical objects to the user** ("your two hands sit
on two different computers"), and they can be in **different states** — the right
half is battery-less and link-powered, so "my right half is dark" is a different
user state from "my keyboard is off" (see § 4). **[derived]**

---

## 4. Split-specific requirements (the first-class half state)

**This is the distinctive requirement of a split keyboard, and the one the
dark-board event exposed.**

**Derivation: § 0.8.** The half-state is measured end-to-end (the ODM's
`split.transport.sync` intent, the `B9`-derived runtime mastery, and the 2 s
`SYNC_MULTIMODE` wire) and dies at the renderer — which is why these are
requirements and not yet behaviour.

**Requirement X-13.** The user must be able to tell, **from either half**, that
**both** halves are alive and linked — because the right half has **no battery
and no supply of its own** (`docs/HARDWARE.md`, "Split-link power" and
"Batteries"): it is powered solely by the left over the link. Therefore:

- the right half going dark is **a consequence of the left half**, not an
  independent fault; and
- the user must not be left to infer that from first principles.

**Requirement X-14.** A dark half must be attributable: the board must distinguish
**this half is intentionally off/dim** from **this half has lost its link/power**.
Today both render identically (dark) — the defect this section exists to name.

**Requirement X-15 (handedness legibility).** Because the switch lives on the
**right** half while the master is normally the **left** (§ `docs/USAGE.md` § 4),
no indicator may require the user to hold a belief about which half is master.

---

## 5. Platform principles applied

The 1992 eleven, each with what it means **for a keyboard** and how it becomes a
requirement. **[derived]** marks the keyboard-specific translation.

| Principle | For a keyboard **[derived]** | Requirement |
|---|---|---|
| **Metaphors** | an indicator should look like what it means (a charge bar, a link) | X-16 |
| **Direct Manipulation** | the user wants "clues that tell them that a particular command is being carried out, or… why not" | X-1, X-6 |
| **See-and-Point** | recognition over recall: no mapping to memorise | X-3/C |
| **Consistency** | same look ⇒ same behaviour; Apple's own question "consistency with people's expectations" | X-11 |
| **WYSIWYG** | what is shown is what will happen (the switch shows the intended transport) | X-4 |
| **User Control** | the user, not the firmware, chooses the mode | X-3 |
| **Feedback and Dialog** — "Keep users informed… as immediate as possible"; "describe any delays, why they occur, and how long they'll take"; "Provide direct, simple feedback that people can understand" | an in-progress link must show **progress and a time expectation** | X-1, X-17 |
| **Forgiveness** — "actions… are generally reversible… create safety nets" | destructive recovery must be hard to hit, easy to understand | X-6 |
| **Perceived Stability** — "it is the *perception* of stability" | **dim, don't remove** | X-10 |
| **Aesthetic Integrity** | the board's steady look must not lie about its state | X-18 |
| **Modelessness** — "avoid modes; prefer modeless operation" | the switch is a mode; make its state continuously visible (Raskin's quasimode insight) | X-4, § 2.2 |

**The exemplary failure, verbatim from the 1992 Feedback principle:**
*"The computer unexpectedly crashed. ID = 13."* — **a code where a situation was
needed.** Applied **[derived]**: the board must not answer a user's "what is
wrong?" with a number, a bare colour, or silence. (The boot code in
`docs/INDICATORS.md` is a *deliberate* exception: it is the instrument for a
debugging audience, not a user message — see § 8.)

**Requirement X-17 (time expectations).** Connected-device UX: *"an expected wait
is patience; an unexpected one is a failure."* Any state with a duration (pairing,
reconnect, sleep) must advertise **that it is waiting and roughly how long**.

**Requirement X-18 (consistency with the host).** Connected-device UX: *"Trust
dies the moment they contradict each other."* The board's own indication and the
host's report (polybar, the `0xA4` readback) must **agree** about the state, from
one shared vocabulary. This is the FC/IS insight from the UX side — *"a screen can
only display the states the firmware exposes"* — so the state machine is the
contract § 3.1.

---

## 6. Verification

**Requirement X-19.** These requirements are verified two ways, in this order:

1. **Heuristic evaluation (now, per § 0.4)** — walk each requirement against the
   Nielsen heuristics and the 1992 principles, and record the verdict and its
   measurement per `docs/METHOD.md` § I.2 ("a verdict is only written after the
   measurement named in the plan has been run").
2. **User observation (when a person is available)** — Apple's ten-step protocol,
   recorded below so it is not re-derived.

### The ten-step user-observation protocol (Apple 1992, § 3)

1. **Introduce**, purpose in general terms — do not say what you are observing.
   Script: *"we're testing the product, not you"*; *"if you have trouble, it's the
   product's fault, not yours."*
2. **Tell the participant they may quit at any time.** *"Never leave this step
   out."*
3. **Explain the equipment.**
4. **Explain how to think aloud** — and demonstrate it.
5. **Explain that you will not provide help** — *"if you… immediately provide an
   answer, you will lose the most valuable information you can gain…— where users
   have trouble and how they figure out what to do."* Decide the intervention
   rule in advance (e.g. three minutes of struggle); intervene before a
   participant gives up entirely.
6. **Describe in general terms what they will do** — written instructions; do not
   demonstrate what you are testing.
7. **Ask for questions, then begin.**
8. **During:** stay alert; prompt neutrally on hesitation (*"what are you thinking
   about?"*); be patient — *"the participant is doing you a favor."*
9. **Conclude:** explain what you were testing; answer questions; ask for
   suggestions.
10. **Use the results:** attribute difficulties to **faulty product design, not the
    participant**; take notes between sessions.

---

## 7. Horizon requirements (stated, deliberately not built)

These are requirements the project accepts but that are not yet implemented.
They are recorded so the vocabulary does not need redesign when they land.

**H-1. Honest battery reporting.** The reported level must never claim a value it
has not measured. Today `md_info.bat` is initialised to `100` and only updated by
a module reply, so on USB the board reports `100%` it has never verified
(`TODO.md` defect 1). **The UX requirement is that "unknown" is a renderable
state** and is shown as unknown, not as full. Related to X-5.

**H-2. Bluetooth must be a transport that carries input.** BT is implemented and
probed, and it is **broken in a known way**: the module's own GATT server rejects
the notification-enabling writes (ATT `0x0E`), so BT connects without carrying
input (§ 0.7). Requirement X-1's "distinguish carrying input from merely powered"
is written **for this case**: the board must be able to say "connected, but input
is not flowing" rather than answering with a green "connected" that lies. Until
the module fault is resolved — and it may be **unfalsifiable-by-us**, having no
dump or update path (§ 0.5) — this honest state is the requirement that stands.

---

## 8. What we deliberately do not indicate (the 80% trim)

Per § 0.3, the vocabulary in § 3 was written complete, and this section is the
**decision on the record** about what the 80% does not get — with the reason.

| Not indicated (to the primary user) | Why | Where it still lives |
|---|---|---|
| The **boot code** (`docs/INDICATORS.md` § 1) | it is the *instrument* for the unobservable region, a debugging channel; Apple's feedback principle also warns against answering a user with a code | `docs/INDICATORS.md`, the `0xA4` readback |
| **BT profile number** (which of BT1..5) | **REVERSED — the first draft trimmed this and was wrong.** The board is multi-host by the owner's own four circumstances (§ 1.1): desktop, laptop, phone, and a guest's laptop. "Which host am I on?" is therefore a **primary** question, not a power-user one. See X-20 | the Fn-layer keys, `docs/USAGE.md` |
| **Which half is master** | an implementation fact the user should never need (X-15) | nothing — deliberately |
| **The raw persisted index / EEPROM contents** | invisible machinery; recovery is provided instead (X-6) | `EE_CLR`, `docs/USAGE.md` § 6 |
| **Confirming every keystroke** to the host | noise; the *link* state already carries "input is flowing" | — |
| **Distinguishing "out of range" from "powered off"** | *partly* trimmed — but see X-30: the module already *reports* rejection, so the "rejected" half is no longer a 20% distinction | § 7 H-2; § 0.7 stage 3 |

**The one thing this section must never trim:** X-7 (§ 4) — a dark-but-alive
board must remain distinguishable from a dead one. It is the founding
requirement, and it is the reason `docs/METHOD.md` exists in its present form.

---

## 9. The requirements, collected

| # | Requirement | From |
|---|---|---|
| X-1 | every step of "connect" presents an actionable state; every link attempt has a timeout and a terminal outcome | Nielsen #1, #9; connected-device UX |
| X-2 | no step requires guessing between two look-alike situations with opposite actions | connected-device UX |
| X-3 | the switch's position is the user's stated intent, always visible | Apple "Implementing Preferences" |
| X-4 | the active mode is indicated **while** the switch is in that position | Raskin; Apple "Modelessness" |
| X-5 | charge state is readable without a host, and distinguishes the four charge conditions | Apple "Feedback"; § 2.3 |
| X-6 | every reachable failure has a desk-performable recovery, made findable; destructive recovery is clearly marked | Nielsen #9; Apple "Forgiveness" |
| X-7 | a dark-but-alive board is never indistinguishable from a dead one | 2026-10-14 dark-board event |
| X-8 | every state the 80% needs is rendered on the RGB matrix | `docs/INDICATORS.md`; § 3.2 |
| X-9 | no state by colour alone; colour is redundant with position/pattern/count | Apple Ch. 2 (verbatim) |
| X-10 | off/unavailable states are shown dim/dark-in-pattern, never absent | Apple "Perceived Stability" |
| X-11 | no new LED element without justification; no existing pattern reused with a new meaning | Apple "Extending the Interface" |
| X-12 | at least two independent cues per important state | Apple "redundant cues" |
| X-13 | from either half, both halves are shown alive and linked | split research; `docs/HARDWARE.md` |
| X-14 | a dark half is attributable: intentional-off vs lost-link | `docs/HARDWARE.md` "Split-link power" (power is one-way, left→right); § 4 |
| X-15 | no indicator requires knowing which half is master | `docs/USAGE.md` § 4 |
| X-16 | indicators are shaped like what they mean | Apple "Metaphors" |
| X-17 | any state with a duration advertises the wait and an expectation | Apple "Feedback"; connected-device UX |
| X-18 | the board's indication and the host's report agree, from one vocabulary | connected-device UX; FC/IS |
| X-19 | verification is heuristic evaluation now, user observation when possible | Apple § 3; Nielsen |
| X-20 | **the active host is a readable state**: which of the four circumstances the board is serving now (which transport, and which wireless host), from either half | § 1.1 (four hosts), § 1.4 D |
| X-21 | **a transient host is usable and leaves no permanent claim**: a one-off guest (§ 1.1 #4) must connect without the owner explaining anything, and its profile slot must be reclaimable | § 1.1 #4; `DEVCTRL_CLEAN` per slot |
| X-22 | **a presentation session survives unattended**: once a link is up for a talk, it stays up, and its state needs no interaction to stay legible | § 1.1 #3, § 1.4 F |
| X-23 | **the board is legible to a first-time user**, not only its owner: no reading requires the owner's conventions or knowing the master half | § 1.1 #4, § 1.4 E |
| X-24 | **switching hosts is deliberate and unambiguous**: with >1 host paired, the active host is readable *before* typing into it, and the act is unconfusable with a keypress | § 2.8; `bluetooth_select_profile` resets the link |
| X-25 | **returns to the last host without user action** after a power cycle or idle gap; if it cannot, it says so | § 2.9; `HSM_LINK_ACT_RECONNECT` |
| X-26 | a **cabled, idle** board still answers "charging? how full?" with no typing and no host tool | § 2.10 |
| X-27 | a monitoring host that cannot reach the board shows **"no reply"**, not a stale value as current | § 2.11; `--info` behaviour as contract |
| X-28 | **accessibility is an explicit audience**: fully usable with the halves widely separated | Apple Ch. 2; § 2.12 |
| X-29 | the two halves must **not settle on different hosts** without it being obviously wrong | § 2.12 (the split hazard) |
| X-30 | **a state the firmware carries is never silently flattened**: where the module reports a distinct condition (e.g. `REJECT`) and the board models it, it must be surfaced, not folded into "not connected" | § 0.7 stage 3; `wls.c:283`, `transport_logic.c:275` |
| H-1 | unknown charge is renderable and shown as unknown | honesty; `TODO.md` defect 1 |
| H-2 | "connected but input not flowing" is a *distinguishable* state | honesty; BT ATT `0x0E` |
