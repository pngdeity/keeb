# Indicators — the LED contract

> **Scope.** Every LED this firmware drives: what each one means, and how to
> read the board from a cold glance — including the **boot code**, the one
> channel that survives a failure which leaves the board dark and silent. This
> is the *contract* (what the lights mean and how a human reads them); the
> measured facts behind the timing are in `docs/HARDWARE.md` ("RGB matrix frame
> timing", "Battery indicator LED"), the ownership map is in
> `docs/BOARD-LAYER.md` (the `wls_indicator` row), and the discovery narrative —
> why the previous instrument was unreadable — is the `boot instrument` FINDING
> in `docs/FINDINGS.md`.
>
> **This is the instrument contract, for a debugging audience.** What the LEDs
> owe *the person typing* — the user-facing meanings, which are a different and
> shorter set, and the requirement that a colour never be the sole carrier of a
> state — is `docs/UX-REQUIREMENTS.md`. A user-facing indicator and an instrument
> may share a pattern; they must not share a *meaning* by accident (see that
> file's X-11).

Read this when you need to **interpret** the board, not when you change it. A
change to what the lights mean must update this file in the same commit.

## 0. Why the LEDs are the instrument of record

The region this project works in — the boot sequence and the vendor wireless
stack reached through it — **cannot be observed by the usual channels**:

- it runs **before there is a console** (no `print` output is guaranteed to
  reach anyone),
- it runs **before USB is up** (so the host cannot be asked),
- it **can fail in ways that leave the board dark and silent** — a fault in
  early init pulls up the USB data line and then goes mute, which a host sees as
  a device that never enumerates (see `docs/BOOT-SEQUENCE.md` §12.1),

so the only channel that survives such a failure is the **LED rail**, which is
powered before the switch is read.

**The standing rule that follows:** when working in a region that cannot be
observed, the instrument comes first, and it must itself be trustworthy. An
instrument that races other output, whose timing is not what its comment claims,
or that plays once from an arbitrary phase is not an instrument — it is a second
source of ambiguity. See `docs/METHOD.md` (§II.1) for the process this belongs
to, `TODO.md` "Pre-flight discipline" and the four defects in §5 below for what
"trustworthy" means concretely.

## 1. The boot code — how to read it

The board plays a **two-part code** at boot, in the convention of Dell's
Latitude E-series diagnostic LED (Dell KB `000131044`): a code is *A* flashes
of **amber** followed by *W* flashes of **white** — "the first number represents
the number of amber-colored flashes, the second number the number of
white-colored flashes."

The played frame is:

```
[amber x A] --gap-- [white x W] --pause-- (repeat, until dismissed)
```

**How to count.** Watch a whole frame, then confirm on the next one (it loops).
The three time scales are deliberately different and named, so the boundaries
are unambiguous — a **pulse** is lit then dark for the same time
(`WLS_BOOT_CODE_PULSE_MS`), the **intra-code gap** between the amber and white
groups is longer (`WLS_BOOT_CODE_GROUP_GAP_MS`), and the **inter-frame pause**
after the white group is longer still (`WLS_BOOT_CODE_FRAME_GAP_MS`). Cite the
constants in `wls/wls/boot_code_logic.h` for their values; do not copy numbers
into prose, where they drift.

The code **repeats** until a keypress dismisses it or a timeout expires, so a
missed start is recoverable — you can look up late and still catch the next
frame. **Every code plays for exactly one frame and no more**: the show window is
*derived* from the frame length (`wls_boot_code_show_ms()` returns
`wls_boot_code_frame_ms()`), so a group is never cut short and two frames are
never merged into one reading. This matters on both sides — a window shorter than
a frame truncates the group, and a window longer than a frame runs the *next*
frame's amber group into this one, and since both groups are amber the reader
counts them together. Both are historical hazards of a hand-chosen window; with
the window derived from the frame neither can occur, and a host simulation of the
core confirms the full count renders at every origin offset (see
`docs/HARDWARE.md`, "the `(5, 5)` reading").

**A worked example.** "Two white blinks, a pause, two white blinks, then the
backlight comes on" reads as **`(0 amber, 2 white)`** — no amber, so the board
is healthy (stage `OK`), and two white reports code 2. The pause is the
inter-frame gap, the repetition is the loop, and the backlight coming on
afterwards is the code having finished and normal RGB taking over.

**The healthy case speaks too.** `A == 0` is not "no message" — it is the `OK`
stage, which still reports the chosen transport and role, so a **working board
is also readable**. A fault is recognised by the presence of an amber group.

## 2. The vocabulary — what a code means

**Amber = the boot stage** (the coarse category: *where* in the boot the board
got to, or stopped). **White = the code within that stage** (the specific fault).
The stage partition is fixed; **the white-code assignments inside each stage are
deliberately revisitable** — the vocabulary is expected to change as the boot
path is re-engineered, and adding a stage or a code must not require touching the
sequencer. The stages (`WLS_BOOT_STAGE_*` in `wls/wls/boot_code_logic.h`):

| Amber | Stage | Meaning |
| --- | --- | --- |
| 0 | `OK` | ran, and chose a transport it can type on (the healthy case) |
| 1 | `PREINIT` | faulted before our boot pass (boot steps 1–32) |
| 2 | `BOOT_PASS` | our boot pass (step 33) could not decide |
| 3 | `TRANSPORT` | ran, but routed keystrokes to a transport with no listener |
| 4 | `ROLE` | this half is not the master |
| 5 | `INCOMPLETE` | reached the loop but the transport is not committed |
| 6 | `BOOTCOUNT` | **a reset already happened this power session**: the white group is the MCU boot count |
| 7 | `RSTCAUSE` | **the chip's own reason for the last reset**, from the latched `RCC->RSTSTAT` |

**Stage 6 (`BOOTCOUNT`) is the fallback proof that a reset loop is happening** —
used when stage 7 has no named cause to speak. The MCU boot counter
(`wls_boot_count`) is RAM, incremented once per boot; it is 1
after a cold power-up and climbs only if the chip reset within the same session.
When it has climbed, that is the news and the transport reading of a boot that is
about to be reset again is noise — so the code becomes six amber, then *n* white
for **boot number *n***. **Replug and watch the white group: if it changes between
replugs the MCU is resetting; if it holds, the app is stable.** A runaway loop
clamps at `WLS_BOOT_CODE_MAX_GROUP` (9), and seeing it pinned is itself the
reading. No channel that needs the running app can carry this — the reset destroys
it — which is why the count rides the LED. **Stage 7 is preferred whenever a cause
bit is latched** (which is the normal case; see below), so stage 6 is the
fallback — but it still proves the loop when no cause bit survived.

**Stage 7 (`RSTCAUSE`) names *why* the chip last reset**, which is more useful than
the count alone. The MCU latches its reset cause in `RCC->RSTSTAT` and holds it
until `RCC->CLRRSTSTAT` is written, so the firmware reads and clears it once at
boot (before `wls_lifecycle_boot()`, so the LED code sees the value). The white
group is the cause: **1** low-power, **2** window-watchdog, **3**
independent-watchdog, **4** software, **5** power-on, **6** external-pin — the
bit order of the register, in the low bits. A white of **9** (`WLS_BOOT_CODE_MAX_GROUP`)
means the latch held nothing we name (which is itself news). The same consumed
value is in the host `0xA4` diag block as `reset_cause` (raw bits), so the eye and
the host cannot disagree.

**Stage 7 is reported unconditionally when any cause bit is latched** — it is
*not* gated on the boot counter, and that is deliberate. The counter is RAM, so
every reset wipes it; gating the cause on `count > 1` would disable the reading on
exactly the boots that matter (a chip that resets before it can boot twice never
sees the counter climb). The register needs no such help: it distinguishes a
genuine cold boot honestly (**5** power-on) from a loop's true cause, so the
reading is self-describing. This also means **every boot now speaks stage 7** —
`(7 amber, 5 white)` on an ordinary power-up, and the fault's own cause when there
is one. Stage 6 is the fallback for the rare case where no cause bit survived.

A code is `(stage, code)`; the counts are the amber and white **pulse counts**.
Both groups are clamped to `1..WLS_BOOT_CODE_MAX_GROUP`, so a spoken code never
has a zero-length group (zero would be indistinguishable from a missing
delimiter) — stage `OK` with code 0 therefore plays **one** white pulse, not
none. **The table of specific white codes per stage lives with the mapping, not
here**: the mapping is `wls_boot_facts()` in `wls/wls.c`, and the current
assignments are recorded in `TODO.md` and the `boot instrument` FINDING in
`docs/FINDINGS.md`. Read them there; this document defines the *form*, not a
frozen set of values.

## 3. The other indicators

The boot code is the highest-priority owner of the matrix (see §4), but it is
one of several indicators. While it is **not** playing, these are active.
Behaviour is vendored-then-extended; the source of truth for each is the pure
core named.

- **Channel / transport flash** (`wls_indicator_channel_flash`,
  `wls_indicate_devs`): a flash when the transport or BT sub-index genuinely
  changes. `reset` selects the re-pair (fast) cadence over the select (slow) one.
  Armed from the mode-switch edge; colours and cadence are the indicator logic's.
- **Battery indicator** (right half bottom row, one channel LED; master-gated):
  charging/full colour and a periodic blink at low level, plus the always-on
  "soft" level LEDs at two indices beside it. The colour is a **pure function of
  `(charging, full, level)`** — `wls_bat_colour_of()` in
  `wls/indicator_logic.h` — so the shell holds no policy. The exact colour table
  and the LED indices are in `docs/HARDWARE.md` "Battery indicator LED" and
  `keyboard.json`'s `rgb_matrix.layout`.
- **Caps lock / Win-lock**: the Caps LED is lit when caps is on; the Win-lock LED
  is lit when the host is *not* macOS and `no_gui` is set. Both are painted
  directly in the board's paint pass.
- **Set-driven flashes** (`wls_indicator_set_flash`): the reset / ack / NKRO
  family, and the settings-reset acknowledgement. An indicator whose index is
  `0xFF` means "all LEDs" — this is the mechanism that, in the previous
  instrument, repainted the whole matrix and erased the boot frame (defect 1,
  §5).

## 4. The arbitration — one owner of the matrix

While the boot code plays, **nothing else may paint**. The rule is enforced by a
single predicate, `wls_indicator_boot_code_owns_matrix()`, checked in the board's
`rgb_matrix_indicators_advanced_kb` pass (`epomaker_split65.c`): the boot code is
painted, and if it owns the matrix the pass **returns early**, suppressing the
channel flash, the battery indicator and the set-driven flashes.

This is the same "one owner per state" rule the project applies to the USB line
and the LED rail — and it is **structural, not an ordering convention**: the
previous instrument painted *additively* and was overwritten by a later pass in
the same frame, so what the eye saw depended on unrelated state. Making the
arbitration a check the owning indicator performs, rather than a paint order a
caller must remember, is what makes the overwrite impossible rather than merely
unlikely.

## 5. What a trustworthy instrument requires — the four defects

These are the constraints any future LED instrument must satisfy. They are not
history: they are the test a replacement has to pass. (This is `docs/METHOD.md`
§II.1 stated concretely for this instrument.) The previous boot
instrument (`wls/boot_report_logic` + `wls/boot_blink_logic`, both deleted) failed
all four.

1. **Exclusive** — the instrument must be the only thing painting while it
   plays. The old one painted additively and was overwritten by a later pass.
2. **Uniform timing** — every pulse the same width; the *count* carries the
   value. The old one's step period applied per half-period, so a step with `n`
   pulses lasted `n` periods and counting required the spec open.
3. **A delimiter and repetition** — a distinguishable frame boundary (the long
   pause) and a loop, so a missed start is recoverable. The old one played once,
   from an arbitrary phase, with no leading marker.
4. **Started where the frame is live** — an instrument armed before the paint
   loop exists has already advanced its phase before it can be seen, and a boot
   that dies earlier shows nothing. The old one was started at boot step 33 but
   painted only once the RGB pass ran. (This is an instance of the project's
   recurring defect class — an effect whose ordering the effect itself violates;
   see `docs/FINDINGS.md` "the recurring defect is one class".)

## 6. The same code on the host channel

The code the LED plays is carried on the `0xA4` reply too, at
`KB_BATTERY_IDX_BOOT_CODE` (the `(amber, white)` pair, `WLS_BOOT_CODE_ENC_SIZE`
bytes), so **the eye and the host cannot drift** — `host/battery_polybar.py`
decodes it and prints `BOOT CODE: A amber, W white -> stage=… code=…`. The header
`wls/wls.h` names the index; the encoder is `wls_boot_code_encode()`.

Note the host channel is only readable while the USB path is up. When the
committed transport is not USB, the `0xA4` responder does not answer at all
(keystrokes and the report path go to the wireless module), and
`host/battery_polybar.py` reports that as its failure reason. **The LED code is
therefore the more robust of the two readers: it works even when the host
channel is dead.** Read the code first, then the host channel.
