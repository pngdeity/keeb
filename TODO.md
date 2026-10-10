# TODO

The live record: work, defects, and status. Sections below are marked **LIVE**
(open work or facts that still bind) or **ARCHIVAL** (closed, kept for rationale
— do not treat an archival section as an open task).

- **LIVE** — Status, Priority order, Outstanding verification, Defects found on
  hardware, Right-half DFU, Usability review, Debugging capability, Other.
- **ARCHIVAL** — Regressions introduced by our own change set, Code audit,
  Reverse-engineering the board, Re-base.

## Status

- **The tree holds our battery firmware, committed inside the `qmk_firmware`
  submodule.** `qmk_firmware/` is a **pinned submodule** of `pngdeity/cleave-keeb`
  branch `split65-overlay`, which now sits on **`qmk/qmk_firmware` master**
  (`7a1bbf37c5`, 2026-10-02) — not the vendor's Oct-2024 core. The board source
  therefore **contains the battery responder** (`wls/wls_battery.c`), the
  corrected `bootmagic.matrix [1,0]`, and the deep-sleep fix
  (`wireless/lpwr_wb32.c`; see the plan's 3.1). The battery *value* is upstream's
  (`quantum/battery`, via `wls/wls_battery_driver.c`) and host selection is
  upstream's (`quantum/connection`, bridged by `connection_host_changed_kb()`).
  The rest of the wireless stack is sourced from the shared
  `keyboards/linker/wireless/` via
  `VPATH`, so the board's divergence from vendor is a one-file diff.
- The personal `nathan` keymap is **not** in the tree: it lives in the sibling
  userspace repo `../keeb-userspace/`. Build with `./bin/make ...:nathan`
  (`bin/make` supplies `QMK_USERSPACE`).
- **Artifacts are not tracked here.** Build them and read the hash on demand;
  do not copy a size/md5 into this file (it goes stale on every firmware edit
  and only creates churn):
  `./bin/make epomaker/epomaker_split65:all && md5sum qmk_firmware/.build/epomaker_epomaker_split65_*.bin`.
  CI builds the same source with the container's `arm-none-eabi-gcc`, which can
  differ from the host's, so bytes are not comparable across toolchains — CI
  asserts "it builds", not a fixed md5.
- Both halves enumerate as `342d:e4c6`, manufacturer `LEO` (stock is `MILE`).
- **Both halves run an earlier `nathan` build, not the current tree's.** The
  flashed build predates the sleep-invariant and wake-code changes; regression 4
  below is source-complete but not flashed. Re-verify after any further firmware
  change and reflash.
- Both halves enter DFU by the spacebar metal-plated-hole short while plugging
  in USB-C (no case opening needed on either half; the right half first needs the
  hidden toggle flipped **down**, exposed by removing the `R_Shift` keycap, and
  back **up** afterwards); see
  `docs/HARDWARE.md`.
  Key-based DFU is still future work (a section below).
- **The prune was discarded and the canonical tree restored.** `qmk_firmware/` is
  a submodule again (the earlier flatten/prune/`layouts`+`lib/lufa` casualties are
  resolved by P0). Both repos are pushed and CI is green. Device context and
  vocabulary: `docs/DEVICE.md`.
- **The ownerless-shared-state defect class is partly closed** (submodule commit
  `d68e3152c3`, superseded by the re-base). Two contained fixes, board-local, no shared-stack file touched:
  `kb_battery_snapshot_t` + `kb_battery_snapshot()` make the battery read atomic,
  so change detection and report assembly see one sample (the value itself now
  comes from upstream `quantum/battery`). The cable-transport arbiter
  `hs_transport_arbitrate_cable()` was later gutted to a no-op for functional
  requirement 2 (see the Regressions section). Both keymaps build clean; CI
  green. The larger board-API layering (replace the
  `lower_sleep`/`charging_state`/`bat_full_flag` externs) is deliberately
  deferred — it is upstream-sized and waits on the U1 RFC.
- **The wireless stack is a documented third-party protocol, not an Epomaker
  black box.** The module is a WCH **CH582F**, and its UART protocol is public
  (`emolitor/WestberryTech-WB32`, `docs/wireless/ch582f-protocol.md`); our
  `module.h` matches it byte for byte. No Split65 schematic exists publicly, but
  the protocol, the module state machine, the battery/sleep opcodes, and our
  firmware's lineage are all published. The module's BLE stack itself is **not an
  opaque blob** — WCH ships it as `LIBCH58xBLE.a`, a symbolized archive of 67
  named objects (10,410 exported functions, disassemblable with `llvm-objdump`),
  with the profile layer as full C source — so the module's *behavior* is
  readable too. This turns several
  "assumption-not-measurement" items into spec-backed facts and makes a
  specification-driven test harness tractable without hardware. See
  `docs/HARDWARE.md` "The wireless module (public information)" and
  `docs/FINDINGS.md` "the wireless stack is a documented third-party protocol".

## Priority of code sources (read this before changing the wireless/connection stack)

**The goal is a firmware that works on this one keyboard.** Nothing else is
owed to any upstream or vendor: prior work (upstream *or* vendor) is an *input we
may use or ignore*, judged only by whether it serves that goal. Where existing
code is worse than what we would write, **discard it and write our own** — high
quality and clean architecture are ours to define, and are what makes the result
both correct here and, secondarily, plausible to upstream.

Three bodies of code exist here, and they do **not** have equal weight:

1. **Upstream QMK (`quantum/connection`, `host.c`, `quantum/battery`, the
   `drivers/*` weak contracts) — the plate.** Extend it; do not build a parallel
   system beside it. Its unfinished tri-mode support is the *intended* home for
   our work, so patching it is also the most upstreamable path. See
   `docs/FINDINGS.md` "the transport is three partial state machines…".
2. **Our own board layer — the clean extension.** The switch-authority rule, the
   pure decision cores (`wls/transport_logic`, `lpwr_*_logic`), and the
   upstream-shaped drivers (`wls/wls_bluetooth.c`, `wls/wls_battery_driver.c`).
   Be opinionated; this is the layer we own and want to keep clean.
3. **The vendor stack (`keyboards/linker/wireless/*`) — scaffolding to delete
   where it fights the plate.** Keep **only** what upstream cannot provide: the
   CH582F UART protocol (`module.c`/`smsg.c`). Do **not** add new glue around it,
   and abandon its "remember last transport" persistence wherever a physical
   switch is authoritative (the switch owns its domain; persistence is only for
   what the switch cannot express, i.e. *which* BT1–5). Deprioritize vendor code
   in every judgment call — it is ODM-authored and was never a design we chose.
   Corollary: the vendor stack is **not owed preservation**. Retaining a vendor
   file is a choice we make only when it beats a rewrite we would otherwise do;
   "it already exists" is not a reason. `module.c`/`smsg.c` are kept because the
   CH582F UART wire is a fixed hardware fact, not because the code is good.

## Priority order

Ordered by what unblocks what. Rationale and detail for each item follow in the
sections below.

**Tier 0 — blockers / one-way doors (do first, cheap, affect everything after):**

1. **Re-base onto current upstream QMK (`qmk/qmk_firmware` master).** Promoted
   from Tier 4 on the strength of the completed spike: the port is proven
   tractable — both keymaps build green on master. **The spike has landed:** the
   branch was renamed `split65-overlay` (the old vendor line is preserved as
   `split65-vendor-overlay`), and the root gitlink now points at it. This is now the organizing priority, because it decides the
   base every later item lands on: once the hardware work in Tier 1 is done on
   the vendor tree, doing it again after a re-base would waste the measurement
   and the flash. Do it **before** flashing, not after. See
   `docs/FINDINGS.md` "the vendor fork is shallow" and `## Re-base` below.
   - **Spike done:** ported the board + shared wireless stack onto master; six
     mechanical upstream breakages fixed (internal eeconfig header, GPIO API,
     `keyboard_protocol` global, `SD1_*`→`UART_*`, RGB keycodes, keymap-config
     struct); `default` and `nathan` both build; `qmk lint` clean.
     (`libmodule.a` and the legacy `keyboards/wireless/` copy are resolved:
     the directory was deleted in the spike — see `## Re-base`.)
2. ~~**Fix defect 3** (`find_raw_hid_interface()` picks the wrong interface) and
   **contain it in `split65.py check`.**~~ **DONE, hardware-confirmed
   (2026-10-09)** — `find_raw_hid_interface()` now prefers the dongle
   (interface 2) and accepts `--transport usb`; `split65.py check` reports the
   collections present. The confirmation run happened: with the dongle attached
   the raw collection landed on interface 2 and a `0xA4` pull returned
   **transport byte `0x04` (2.4 GHz)**, so the interface-2 = dongle mapping is
   verified, not assumed.
3. ~~**Decide and apply the critical ergonomics changes**~~ **DONE** (on the
   landed re-base; must be flashed with the Tier 1 batch):
  - **`QK_BOOT` / `EE_CLR` placement.** `QK_BOOT` sits on the **Fn** layer at
    matrix `[10,4]` (the Fn-layer top-right corner key), **not** on the base
    layer; `EE_CLR` moved off Backspace to the hold-only `_RST` layer's
    right-half **bottom-right corner** (`[11,7]`). The `_RST` layer is armed only
    by holding Fn + the top-right corner key, so the reset needs a held chord
    plus a press on the opposite half's far corner — no single stray keypress
    reaches it. `nathan` `keymap.md` corrected to match
    (it had described an older layout).
  - **Battery indicator made prominent.** The soft indicator now spans **two**
    adjacent right-half bottom-row LEDs (`HS_MATRIX_BAT_SOFT_INDEX` 64 and new
    `HS_MATRIX_BAT_SOFT_INDEX2` 65) at full channel intensity, instead of one
    dim LED — legible at a glance. Colours: green ≥50, amber ≥30, red ≤low,
    green while charging-full, blue while charging.
  - **Animation list trimmed** from 44 to 10 (`keyboard.json`
    `rgb_matrix.animations`), keeping `solid_color` (the boot default),
    `breathing`, `cycle_left_right`, `cycle_up_down`,
    `rainbow_moving_chevron`, `raindrops`, `solid_reactive`,
    `solid_reactive_wide`, `typing_heatmap`, `digital_rain`.
  - **Cable auto-switch disabled (Tier 1 item 8, done in the same pass).**
    `hs_transport_arbitrate_cable()` is now a no-op: "a cable is present" no
    longer means "switch to USB". Mode selection belongs solely to the physical
    mode switch (`hs_modeio_detection()` already owns it). This implements
    requirement 2 in source; hardware behaviour is still unverified.

**Tier 1 — the deliverable (the project exists for this):**

4. **Reflash both halves** with the current build. Cheap, and it gives a clean
   baseline for the measurement below. Do it *after* all the cheap pre-flash
   decisions are in, so the flash is done once.
5. **2.4 GHz: capture a real percentage** (the decisive test; needs the user at
   the keyboard). Depends on 1 and 4.
6. **2.4 GHz: confirm `chg` moves `1 -> 2` while charging.** Same session as 5.
7. **Decide and implement the honesty fix for the fake 100** (defect 1).
   Depends on 5 — you need to know what a real reading looks like before choosing
   how to represent "unknown".
8. **Wireless while charging (requirement 2).** ~~Disable the cable-insert
   auto-switch in `housekeeping_task_user()`~~ **SOURCE DONE** — the
   cable-insert auto-switch (`hs_transport_arbitrate_cable()`) is now a no-op
   (Tier 0 item 3 pass); mode selection belongs to the physical switch. **Still
   to verify on hardware:** a cable with the switch on 2.4 GHz must leave the
   keyboard wireless and the level still updating. The hardware behaviour (VBUS
   vs module UART/radio) is unverified. Needs the user at the keyboard.

**Tier 2 — feature completeness (in scope, not yet probed):**

9. **Probe Bluetooth at all**, then update `docs/PROTOCOL.md` and `README.md`.
   Independent of Tier 1 except that it wants a fixed host tool (2).

**Tier 3 — quality / ergonomics (valuable, not blocking):**

10. **Firmware unit tests** for the board-local **pure helpers** (`kb_battery_*`).
    Scope stops at those functions: the split transport is upstream's transaction
    API, so tests must not re-cover it (see `docs/FINDINGS.md`, "the vendor split
    stack is closer to upstream than it first looks"). Best done after 5/7 so the
    tests encode settled semantics, not the current fake-100 behaviour.
10b. **Spec-driven `test/` harness for the module stack (no hardware needed).**
    The CH582F protocol is now public (`docs/HARDWARE.md`), so a test can stub
    `module.c`/`smsg.c` I/O and drive the real `transport.c`/`wireless.c` against
    a *specified* byte stream rather than a guess. Highest-value no-hardware
    artifact: it retires the "assumption, not measurement" risk on the module
    state machine, the battery poll, and the host/transport selection. Does **not**
    cover radio/battery/dongle truth — those stay flash-gated.
    **First piece landed:** `tests/wireless_nkro_parity/` (8 tests, run
    `make test:wireless_nkro_parity`) byte-compares the board Bluetooth driver's
    NKRO collapse (`wls_bluetooth.c`) against the vendor implementation
    (`linker/wireless/wireless.c` `wireless_send_nkro()`) — the differential
    check that guards the one authored sender against drift. Non-vacuity confirmed
    by deliberate divergence. Remaining: the module state machine/battery poll.
11. **Key-based right-half DFU (low priority).** Both halves run identical
    firmware and the right half is link/bus-powered (no cell), so its own
    recovery path is less pressing than it first appeared. The spacebar-hole
    short (no case opening; `docs/HARDWARE.md`) stays the recovery path.
11b. **Pull the FCC / CE filings into the hardware record (no hardware needed).**
    The board is a certified radio: FCC ID `2A5D2-RT100-010` and the EU CE annex
    (see `docs/HARDWARE.md` "Certification filings"). These name the manufacturer
    (`Shenzhen Changyun Technology Co., Ltd.`) and carry a family teardown photo
    set. Worth: (a) request the **confidentiality-released** documents once the
    long-term-confidentiality window lapses (files become public on their
    availability date), (b) check whether any sibling grant is the Split65 itself
    rather than a series-model declaration, (c) reconcile `Changyun` with the
    `MATHEW`/`mathewkb.com` ODM candidate. No flash required.
12. **The rest of the UX / usability review** (whole section below) — layer
    ergonomics, held-modifier comfort, mode-switch discoverability, legends.
    Largest, most subjective; depends on 7 and 10 for what is even possible.
12b. **Mine the public same-family schematics (no hardware needed).** A sibling
     board's reverse-engineered **pin map** (`ozboar/zoom65v3-re`) and third-party
     **CH582F tri-mode keyboard schematics** (`oshwhub.com`) are public (see
     `docs/HARDWARE.md`). Worth: (a) reconcile the sibling's module-UART/cable/
     battery/LED pin roles against our `config.h` (note our module UART is
     `C10`/`C11`, *not* the sibling's `A9`/`A10`); (b) use the oshwhub CH582F
     board + 2.4 GHz-receiver designs as a **reference topology** for the
     charge/boost/level-shift stage, which is the least-documented part of our
     board. Does not yield the Split65 netlist.
12c. **Reverse-engineer the module BLE stack from `LIBCH58xBLE.a` (no hardware
     needed).** The WCH SDK's BLE stack is a **symbolized archive** of 67 named
     objects (unstripped, 10,410 exported functions, `llvm-objdump`-readable; the
     profile layer is full C source) — see `docs/HARDWARE.md` "The BLE stack is a
     symbolized library, not a blob". The linked BASELIB (`CH58xBLE_ROM*.hex`) is
     public too and disassembles (`llvm-objdump -b binary -m riscv`); it is the
     artifact the vendor most plausibly flashed, so it is the best single target
     for fingerprinting the module's SDK revision (fingerprint table in
     `docs/HARDWARE.md`, "SDK-revision fingerprints to capture from hardware").
     Worth: (a) trace which internal GAP/LL event emits each `0x5B` status
     sub-code (`0x31`/`0x32`/`0x33`/`0x36`) to confirm the `wls_bluetooth.c`
     link-up gate against the source of truth; (b) trace the `0x21`/`0x22`/`0x23`
     battery-threshold sub-codes for the stale-reading defect (defect 1) — our
     stack deliberately drops them (see `docs/FINDINGS.md`, "Battery semantics"),
     so this decides whether that choice costs us a low-battery signal; (c) read
     the pairing (`0x51`/`0x52`) and TMOS sleep
     (`0x54`/`0x55`/`0x56`/`0x57`/`0x58`) state machines — the parts that are
     invisible here because the 2.4 GHz dongle does not enumerate and no second
     machine is available. Prior art: `ArcaneNibble/project-nanjing`,
     `ch58x-hal`, `fossasia/badgemagic-firmware`. Bounds the protocol doc's
     applicability to our module revision.
     **Correction (2026-10-09):** the premise "the 2.4 GHz dongle does not
     enumerate" is **false** — with the keyboard in 2.4 GHz mode the dongle
     enumerates (`342d:e4c6`, raw-HID at interface 2) and `0xA4` round-trips (see
     the dongle subsection in `docs/HARDWARE.md`). So this route to the module's
     pairing/sleep state machines is now reachable on this host after all.
13. ~~**Research: can upstream's split watchdog replace the vendor's hand-rolled
    disconnect handling?**~~ **DONE — decided AGAINST.** The watchdog was enabled
    during the re-base, then proved to reset-loop the slave (~3 s) on hardware:
    its slave-side `done` flag is refreshed only by the master's one-way ping,
    which the master stops emitting once its own flag is clear, so the slave can
    never re-arm. It is now deliberately **not** defined in the board `config.h`
    (regression 2 below), matching the vendor firmware, which never enabled it.
    Upstream's `transport_master_if_connected()` throttling remains live via
    `quantum/matrix_common.c:96` and is unaffected. `SPLIT_ACTIVITY_ENABLE`
    remains an open candidate (keeps the link warm; interacts with sleep tuning).
14. ~~**Collapse the three partial transport state machines into the upstream
    `connection` model (architecture; no hardware needed).**~~ **DONE
    (2026-10-09).** The design audit
    (`docs/FINDINGS.md` "the transport is three partial state machines, and the
    vendor one is scaffolding to delete") found four selectors across two
    subsystems. **Doctrine: upstream is the plate, our board layer extends it, the
    vendor stack is scaffolding to delete where it fights the plate.** Work the
    five holes in order:
    14a. **2.4 GHz driver contract (upstreamable).** Add a `2p4ghz` driver mirroring
         `drivers/bluetooth/bluetooth.h` (weak `is_connected`/`send_*`), un-`#if 0`
         the candidate in `connection.c:33`, add the case in
         `host_get_active_driver()` (`host.c:121`). Same shape as the BT driver.
         **DONE (2026-10-09).** Added `drivers/wireless/wireless_2p4ghz.{c,h}`
         (weak `wireless_2p4ghz_init/task/is_connected/can_send_nkro/
         keyboard_leds/send_{keyboard,nkro,mouse,consumer,system,raw_hid}`,
         exactly mirroring `bluetooth.{c,h}`); added the `w2p4_driver`
         `host_driver_t` + `CONNECTION_HOST_2P4GHZ` cases in `host.c`
         `host_get_active_driver()` and `host_can_send_nkro()`; replaced the
         `#if 0` guard in `connection.c` `host_candidates[]` with
         `#ifdef WIRELESS_2P4GHZ_ENABLE`, added the auto-detect branch + include;
         wired a `WIRELESS_2P4GHZ_ENABLE ?= no` feature into
         `builddefs/common_features.mk` (mirrors the BT block; pulls in
         `CONNECTION_ENABLE`). **Verified:** both targets build clean (default
         61,396 B; `WIRELESS_2P4GHZ_ENABLE=yes` 61,528 B), `w2p4_driver` +
         weak `wireless_2p4ghz_*` link under `nm`, `qmk format-c -n` clean,
         `qmk lint` unchanged (4 pre-existing warnings). The board does **not**
         yet set `WIRELESS_2P4GHZ_ENABLE`, so behavior is unchanged — this is
         the upstream-shaped home 14d will route the vendor stack through.
    14b. **BT profile sub-index owned by the BT driver.** Give the driver a
         `select_profile(n)` and delete `confinfo.devs` (the only reason it exists
         is that `connection.h` cannot express BT1–5).
         **DONE (2026-10-09).** `wls_bluetooth.c` now owns `wls_bt_profile`
         (`bluetooth_select_profile()` / `bluetooth_get_profile()`; selection
         goes to the module via `md_devs_change(profile, true)`); `wls.h`
         declares them; `WLS_KEYCODE_EXEC` and the long-press re-pair call
         `bluetooth_select_profile()`. `confinfo.devs` remains only as a RAM
         mirror and the BT1–5 restore hint — it is no longer the profile
         authority. Build clean.
    14c. **Switch-authority persistence rule.** Switch-driven changes use
         `connection_set_host_noeeprom()`; only user keycodes persist. (Defect 4's
         fix already writes the level into both selectors; this makes the switch
         the sole authority and removes the stale-persistence trap.)
         **DONE (2026-10-09).** Boot switch read uses `_noeeprom`;
         `wireless_devs_change_kb()` no longer writes EEPROM; new
         `wls_persist_devs()` is called only from the keycode path. Build clean.
    14d. **One sink chooser.** Delete vendor `transport.c` `set_transport()` /
         `host_set_driver()` and the `md_send_raw` glue; leave
         `host_get_active_driver()` as the single chooser so
         `bluetooth_send_raw_hid` is the only raw path. Resolves invariant I2.
         **DONE (2026-10-09).** Deleted `set_transport()`/`get_transport()`/
         `wls_transport_enable()`/`usb_transport_enable()` and the
         `host_set_driver()` swap from `transport.c`; the file now holds only
         `usb_remote_wakeup()` + `usb_remote_host()`/`process_action_kb()` (the
         latter now keyed on `connection_get_host()`). New board
         `wls_usb_connect(bool)` owns the physical USB connect/disconnect, driven
         by `connection_host_changed_kb()`. `wireless_devs_change()` no longer
         swaps the driver; `wireless_task()` and `wls_battery.c` use
         `connection_get_host()`. `md_raw.c` `replaced_hid_send()` branches on
         `usb_connected_state()`. `transport.h` trimmed to the USB helpers.
         **Boot-order trap resolved:** `keyboard_post_init_kb()` now seeds the
         connection host from the switch LEVEL (with the 100 ms
         `wireless_post_task()` pass retained); post-init runs after
         `connection_init()` but before the first `host_task()`, so no report can
         precede the switch read. **Verified:** `:default` 61,480 B (−896 B),
         `:nathan` 63,524 B, both clean; dead vendor symbols absent from the ELF;
         `format-c` clean; `lint` unchanged (4 pre-existing warnings);
         `tests/transport_logic` 6/6, `tests/lowpower_logic` 8/8,
         `tests/wireless_nkro_parity` 8/8 PASS. **Unflashed.**
    14e. **Model the module as a peer, not an oracle.** Inputs = UART frames;
         outputs = {BLE advert, BLE HID, UART reply, `md_info.state`}. Its BLE
         behaviour stays a bounded hardware unknown (`HARDWARE.md`).
         **DONE (2026-10-09).** New `wls/wls_2p4ghz.c` implements the whole
         `wireless_2p4ghz_*` contract over `md_send_*`, gated on
         `DEVS_2G4 && *md_getp_state()==MD_STATE_CONNECTED`; `WIRELESS_2P4GHZ_ENABLE=yes`
         set in `post_rules.mk`; `wls.mk` includes the file. Build clean.
    Keep from the vendor **only** the CH582F UART protocol (`module.c`/`smsg.c`)
    and the upstream-shaped drivers; add no new glue around the vendor stack.

**Dependency notes (why the order is not free):**

- 1 decides the base everything else lands on; doing it first means Tier 1's
  flash and measurement are done once, on the final tree.
- 5/6/9 (the wireless verification) cannot start until the flash, which follows
  the remaining Tier 1 items.
- 10b is newly *unblocked without hardware* by the public CH582F protocol; it is
  independent of the flash chain and can proceed in parallel with Tier 1 waiting
  on the user. Doing it first also de-risks 5–7 by fixing the module semantics in
  a test before the hardware session.

## Outstanding verification (the deliverable is not yet proven)

The host can read a report, but **no real battery percentage has ever been
observed**. Until the items below are done, treat every displayed value as
unverified.

- [x] ~~**Fix defect 3** (`find_raw_hid_interface()` picks the wrong interface) and
      cover it in `split65.py check`~~ **DONE** (committed). A confirmation run
      with the dongle attached is still outstanding.
- [x] ~~**Flash both halves with the current build** (battery responder + the
      board-local deep-sleep fix) and confirm the manufacturer string is `LEO`
      and the `0xA4` responder answers.~~ **DONE (2026-10-09).** Both halves
      flashed. Over USB the keyboard enumerates as `342d:e4c6`, manufacturer
      `LEO`, product `EPOMAKER Split65` (`bcdDevice 0.30`); one raw HID
      collection at interface 1 (`0xFF60`/`0x61`, `/dev/hidraw4`). The `0xA4`
      piggyback command replied `A4 64 00 00 01 01 01 …` → level byte1 `0x64` =
      **100%**, charge byte4 `0x01` (charging), transport byte5 `0x01` (USB),
      model byte6 `0x01` (Split65). (Field indexes per `wls.h`: cmd 0, level 1,
      charge 4, transport 5, model 6 — an earlier note decoded these off-by-one.)
      No EPROTO in
      the kernel log. Both halves enter DFU by the spacebar
      **metal-plated-hole short** while plugging in USB-C (no case opening needed
      on either half; the right half first needs the hidden toggle flipped
      **down**, exposed by removing the `R_Shift` keycap, and back **up**
      afterwards); see `docs/HARDWARE.md`.
- [ ] **Right-half keypress wake:** with the deep-sleep fix flashed, confirm a key
      on the right half wakes it (defect 2). **DEFERRED (2026-10-09) — cannot be
      run in the current setup; the board will not sleep on USB.**
      The only path that permits a stop is the low-battery *ordered* sleep:
      `lpwr_stop_is_allowed()` (`wls/wls.c`) returns `lpwr_stop_is_allowed_decide(is_keyboard_master(), lower_sleep)`,
      i.e. `is_master && lower_sleep` (`lowpower_logic.c`), and `lower_sleep` is
      set **only** when `bat_level <= BATTERY_CAPACITY_STOP` (0%) while **not
      charging** (`epomaker_split65.c` ~1544). A plain idle timeout does **not**
      sleep — it is deliberately refused (an unordered stop is the dark/unresponsive
      regression documented at `wls/wls.c` ~205-211). On USB the board is charging
      at 100% (`0xA4` → pct 100, charge 0, transport USB), so no stop is ever
      taken and there is no wake to observe. **To run it:** unplug USB, run on
      battery until the low-battery stop fires (<= 0% on the board's own scale;
      `BATTERY_CAPACITY_STOP = 0`), then press a right-half key and watch for the
      raw-HID responder to come back. Practically this needs either a drained
      pack or a temporary threshold bump in a scratch build. Record the result in
      `docs/FINDINGS.md`; if it still fails, the cause is not the pin arrays.
- [ ] **2.4 GHz: capture a real percentage.** Every `100` seen so far is the
      module's compile-time init constant (defect 1). The radio path is the only
      transport known to populate `md_info.bat`, so this is where the first real
      number must come from. Record the observed value and raw bytes in
      `docs/FINDINGS.md`.
- [ ] **2.4 GHz: confirm the value changes while charging.** Re-run the probe with
      a cable in and watch `chg` go `1` -> `2` (full).
- [ ] **2.4 GHz dongle is not enumerating on the host — unresolved, blocked on
      hardware.** After the reflash the dongle produces **zero USB events**: no
      `342d` device in `lsusb`/sysfs, no hidraw node, and no kernel log line at
      all on a clean boot — not even a `-71` enumeration error. Tested on **both
      USB-A ports** of the T480 (different root hubs); the keyboard itself
      enumerates fine on those ports, so the host USB subsystem is not at fault.
      The keyboard's own mode state is correct (`0xA4` byte5 = `0x04`, 2.4 GHz).
      A keyboard firmware change cannot stop a separately-plugged dongle from
      enumerating (see below), so this is believed host/dongle-side, **not a
      regression from our change set** — but it was reported working beforehand,
      so it is not closed. **Cannot test the dongle on another computer** (no
      second machine available, per the operator). Next probes when a dongle is
      in hand: does the original dongle enumerate on any host; does a second
      dongle exist. Until then, the 2.4 GHz transport items above cannot be run.
      This also blocks the `docs/PROTOCOL.md` dongle-interface confirmation
      (`host/battery_polybar.py` prefers interface 2, but the live keyboard
      composite's interface 2 is its own mouse/system/consumer block — the two
      devices share VID:PID `342d:e4c6` and were likely conflated; see the
      accuracy defect note below). Bounded in `docs/HARDWARE.md` "The
      known/unknown boundary (no schematic)" as an open (unbounded) unknown —
      blocked on a second host.
- [ ] **USB: decide and implement the honesty fix for the fake 100** (defect 1).
      The report must not claim `100%` when the value was never refreshed.
- [ ] **Bluetooth: probe the transport at all.** Unknown whether the BT link
      exposes the raw HID collection (`0xFF60`/`0x61`) and whether `*md_getp_bat()`
      is populated over BT. If raw HID is absent, the BLE Battery Service
      (`0x180F`/`0x2A19`) fallback in `host/battery_polybar.py` is the path.
      Pairing is interactive, so the user must run `bluetoothctl`. **Update
      `docs/PROTOCOL.md`** and `README.md` once known. The upstream-shaped
      `BLUETOOTH_DRIVER = custom` home now exists (`wls/wls_bluetooth.c`), so the
      probe exercises both the vendor stack and that adapter.
      **First attempt (2026-10-09) — INCONCLUSIVE, gesture error found.** Two
      things were established: (1) the **mode switch is read correctly** — with USB
      attached, flipping the switch to BT changed the `0xA4` transport byte from
      `0x01` (USB) to `0x02` (BT) immediately, and the reply then carried
      `transport=0x02`; (2) `bluetoothctl` scans (several 12–16 s runs plus one
      55 s continuous capture) saw a dozen bystander devices but **nothing
      identifiable as the keyboard** — no `Split65-*`/`EPOMAKER` name and no hit
      stronger than ≈ −93 dBm (a keyboard inches away would be ≈ −40…−60), and the
      two unexplained random-MAC devices (`FCF1` service beacon; Apple `0x004c`
      beacon) are not it. **However, the pairing gesture was performed wrongly at
      least once:** `nathan`'s Fn is on the **RIGHT** spacebar only (left space is
      plain `KC_SPC`; `keymap.c:45`), so holding the **left** space + `Q` types a
      literal `q` and never fires `KC_BT1`. The one attempt that **did** blink the
      Q key (right space) still produced no advertisement, but the sample is
      small and the switch/USB state differed between attempts. **Next step:
      re-run the scan while the operator holds the RIGHT spacebar + `Q`**, USB
      unplugged, switch on BT, and confirm the Q key blinks before scanning.
      **Also correct `docs/USAGE.md`**, which wrongly said "hold either
      spacebar" (fixed 2026-10-09). Whether the CH582F forwards raw HID over BLE
      at all, and the BLE-vs-raw-HID battery alternatives, are bounded in
      `docs/HARDWARE.md` "The known/unknown boundary (no schematic)".
      **Second attempt (2026-10-09) — CONFIRMED: the module does not advertise,
      even with the correct gesture.** With USB unplugged, switch on BT, and the
      *right* spacebar (the real Fn) held + `Q` until the **Q key visibly blinked**
      (so `KC_BT1` fired and `wireless_devs_change()` ran), repeated
      `bluetoothctl` scans — including one **40 s continuous capture** — again saw
      bystander devices only: no `Split65-*`/`EPOMAKER` name, no HID keyboard
      class/icon on any new MAC, and **no hit stronger than ≈ −94 dBm** in every
      run (a keyboard inches from the adapter would be ≈ −40…−60). The blinking Q
      key proves the firmware side executed the pairing path; nothing came out over
      BLE. This **rules out the gesture-error explanation** and points at the
      **module side** (the CH582F is not transmitting BLE) or the **module UART**
      not reaching it. **Next discriminators (operator-assisted):** (a) try
      Fn + `W` / Fn + `E` (channels BT2/BT3) in case only BT1 is affected;
      (b) if a wired probe is possible, confirm the module UART is alive on our
      build by watching for any reply to `0xA6 0x53`/device-control frames while
      on BT (a scope/logic probe on `C10`/`C11`, or a UART sniffer); (c) flash the
      **stock/vendor** firmware and repeat the exact gesture — if stock also fails
      to advertise, the module or its antenna feed is the fault, not our build;
      (d) confirm the module is even populated/powered (FCC teardown photos show it
      on the matrix, but a board-level check is unverified). **Do not** keep
      re-running the host scan alone — it has been run enough to exclude the host
      and the gesture.
      **Third observation (2026-10-09) — channel asymmetry + half asymmetry.**
      (1) **Fn + `W` / Fn + `E` did NOT blink** (only Fn + `Q` did), so
      `KC_BT2`/`KC_BT3` did not visibly fire while `KC_BT1` did. The blink is a
      **per-channel left-half LED**: `HS_RGB_BLINK_INDEX_BT1..3` = 17/18/19
      (`config.h`), and LED index 17/18/19 = matrix `[2,1]`/`[2,2]`/`[2,3]` =
      **`Q`/`W`/`E`** on the base layer (so "Q blinked" is `KC_BT1` firing
      correctly). All three keycases run identical code
      (`hs_rgb_blink_set_timer`), so the asymmetry is the anomaly.
      (2) **The left half's backlight went out while the right half's stayed on**
      during the off-cable BT session. The blink is rendered with
      `rgb_matrix_set_color(index, ...)` where the index is a **left-half** LED
      (matrix rows 0-5 are left, 6-11 right - `rgb_matrix_wls_indicator()`,
      `epomaker_split65.c:1388`), so the pairing indicator is a left-half-only
      light. A dark left half but lit right half (slave) is consistent with the
      **master having entered a low-power/LED-power-down state**
      (`LED_POWER_EN_PIN` is dropped in `lpwr_stop_hook_pre()`) or lost its rail,
      while the slave (link/bus-powered) is unaffected. This is the same
      master-vs-slave asymmetry family as the deferred right-half-wake item; it is
      **not** explained by the switch or the scan. Next probe when convenient:
      with USB reattached, read `0xA4` - if it still answers the master is alive
      and only its LED rail dropped; if not, the master stopped.
      **FOURTH ATTEMPT (2026-10-09) — RESOLVED: the module DOES advertise. The
      earlier "does not advertise" verdict was a search-miss (wrong identity).**
      Root cause of the miss: the host scans searched `Split65-*`/`EPOMAKER` but
      the board overrides the module's advertised name to `MD_BT1..3_NAME`
      (`config.h` → `"Split65-1"`/`"Split65-2"`/`"Split65-3"`), *not* `module.c`'s
      `PRODUCT " BTn"` default — and a name search **cannot** match the module's
      **random** BLE address. A `bluetoothctl` LE scan for the real names found it
      reliably, **per profile**: `Split65-2` at `C8:02:09:B0:56:5E` and
      `Split65-3` at `C8:03:09:B0:56:5E` (random addresses; third octet tracks the
      profile index). Live `bluetoothctl info` on `Split65-2`: **Appearance
      `0x03c1` (HID keyboard)**, **Icon `input-keyboard`**, **UUID `0x1812` (HID
      service)**, AdvertisingFlags `0x06` (LE General Discoverable, BR/EDR not
      supported) — a **fully-formed, connectable BLE HID keyboard**. So `KC_BT1/2/3`
      work, the module transmits, and the gesture is correct. **This closes the
      BT-probe item:** the Layer-0 "module never advertises" premise is disproven.
      The gesture-error theory and the module-silence theory are both dead. The
      open question is now why a host does not **bond/connect** (pairing/just-works,
      bond persistence, or the split-master's own key routing while on BT) — a
      narrower problem than module silence. The Fn+W/Fn+E "did not blink" asymmetry
      above is now explained: at that time `bluetooth_select_profile()` had the
      **14b regression** (it told the module the new profile but never updated
      `wls_devs`, so the LED loop kept re-rendering BT1); fixed and
      hardware-confirmed (Fn+W→W blinks, Fn+E→E blinks). `btmon -w` is unavailable
      to the user (needs root to bind the HCI channel); `bluetoothctl` is the
      working observer.

### Unmeasured device facts (fill into `docs/DEVICE.md`)

`docs/DEVICE.md` was written from `keyboard.json` and the product photographs.
These facts are **not yet proven** and must be measured before the doc claims
them:

- [ ] **Which left-half port (`P1`/`P2`) is intended for the host vs the
      inter-half link.** The two are positionally distinct but functionally
      interchangeable (both carry power and data); firmware has one cable-detect
      pin (`A7`) and cannot tell them apart. Not a hardware property, so only
      the physical positions are recorded in `DEVICE.md`.
- [ ] **Right-half power path (informational).** The right half has **no battery**
      (observed with the backplate off). The firmware still models per-half
      charge state on that half; this is a harmless quirk, not a defect (see
      `docs/HARDWARE.md` "Batteries"). Only remaining question: whether the right
      half has any charging circuitry at all or is purely bus/link powered.
      **Caveat: this stays harmless only while the master is the battery-bearing
      half** — if the halves were ever swapped, the master would be the
      cell-less half and the reported level and cutoff would both read a phantom.
- [ ] **Confirm the current master/slave assignment** with the cable in the right
      half's `P3` — record which half reports as master.
- [ ] **Stock (`MILE`) factory configuration**: default layer, lighting, and
      keymap as shipped. Unverified; `DEVICE.md` "Stock vs ours" marks these
      unknown.
- [ ] **Physical form of the mode switch** — confirm the three glyph-to-position
      mapping against the actual unit.
- [ ] **Layout count check**: re-derive key count (69) and row widths
      (15/15/14/14/11) from `keyboard.json` and confirm `DEVICE.md` matches.

## Defects found on hardware (pre-existing vendor issues, not regressions)

### 1. USB report always says 100%

`md_info.bat` is initialised to `100` at compile time
(`qmk_firmware/keyboards/linker/wireless/module.c:72-77`) and is written in
exactly one place, `case MD_REV_CMD_BATVOL: md_info.bat = md_rev_payload[1];`
(`module.c:220-222`). The keyboard has no ADC: it can only learn the level by
asking the wireless module (`md_inquire_bat()` ->
`MD_SND_CMD_DEVCTRL_INQVOL` 0x53). That call silently gives up whenever the
module send queue is non-empty — `smsg.c:115-122 smsg_is_busy()`. On USB,
`housekeeping_task_user()` (`epomaker_split65.c:1257-1260`) pushes two devctrl
frames every second, so the queue is frequently busy and `INQVOL` is dropped.
Result: the report shows the never-updated init `100`, and the vendor's own soft
indicator also shows a full-looking colour while on USB regardless of true level.

Fix options (not yet chosen): report "unknown" instead of a fake 100 when the
value has never been refreshed (the pre-rebase `kb_battery_percent()` that the
old plan named for the sentinel no longer exists; the value is now upstream
`battery_get_percent()`), and/or retry `md_inquire_bat()` more aggressively.

### 2. The right (slave) half cannot be woken by its own keys

**Addressed in the board-local deep-sleep fix** (plan 3.1;
`keyboards/epomaker/epomaker_split65/wireless/lpwr_wb32.c`). The original defects,
for the record:

- `lpwr_exti_init()` sized its `row_pins[MATRIX_ROWS]` / `col_pins[MATRIX_COLS]`
  arrays from the **full** split matrix while initializing from the per-half
  `MATRIX_*_PINS`, so the tail slots were `0` (`PAL_LINE(0)`, which is **not**
  `NO_PIN`) and EXTIs were armed on garbage lines.
- Only the left/`MATRIX_*_PINS` geometry was ever used, so the **slave never
  armed its own matrix** and a right-half keypress could not wake it.
- The board's `lpwr_stop_hook_post()` (`wls.c`) only accepted
  `LPWR_WAKEUP_USB`/`LPWR_WAKEUP_CABLE`, so a `MATRIX` cause fell to `default:`
  and returned straight to `LPWR_STOP`.

**Fix:** `wireless/lpwr_wb32.c` (carlosedp's port; the only board-local file —
the rest of the stack is shared) sizes the arrays to `MATRIX_ROWS / 2`, selects
`row_pins_r`/`col_pins_r` from `MATRIX_*_PINS_RIGHT` via `is_keyboard_master()`,
uses `PAL_EVENT_MODE_FALLING_EDGE` (consistent with `ROW2COL`), stops arming the
UART-RX line (the wireless module's own traffic was waking the device and
defeating the 30-minute deep sleep), and `lpwr_stop_hook_post()` now accepts
`SWITCH` and `MATRIX` causes as well.

**Not yet verified on hardware** — this needs a flash and a keypress-wake test
(Tier 1). Until then, waking the right half still relies on toggling its 2.4 GHz/BT
mode switch or replugging its USB cable.

### 3. Host tooling picks the wrong raw HID interface

`host/battery_polybar.py:find_raw_hid_interface()` used to return the first
`hid.enumerate()` entry matching usage page `0xFF60` / usage `0x61`. When both the
keyboard's own USB interface (interface 1) and the 2.4 GHz dongle (interface 2)
are attached, it grabbed the keyboard's USB interface, so the module reported USB
while the user was on 2.4 GHz.

**Fixed, and now hardware-confirmed (2026-10-09).**
`find_raw_hid_interface(prefer=...)` enumerates all matching collections and
prefers interface 2 by default, falling back to the only collection present, with
`--transport usb` selecting the keyboard's own. The hardware run that was
"remaining" has now happened, and it **confirms the interface-2 = dongle mapping**:
with the dongle attached the composite is three interfaces and the raw collection
lands on **interface 2** (`/dev/hidraw5`, usage page `0xFF60` / usage `0x61`).
A `0xA4` pull against `/dev/hidraw5` returns a real reply with **byte 5 = `0x04`
(2.4 GHz)** — see `docs/PROTOCOL.md` "2.4 GHz dongle" and `docs/HARDWARE.md`.

**Documentation accuracy defect — RESOLVED (2026-10-09).** The earlier caution
("the interface-2 claim was never actually observed for a dongle; correct it only
once a dongle is confirmed present") is now satisfied: a dongle *was* confirmed
present and the interface-2 mapping held. The `PROTOCOL.md` claims have been
corrected to *verified* rather than *assumed*.

**Related, previously believed impossible.** The long-standing note that "the
2.4 GHz dongle does not enumerate on this host — zero USB events" was a
**trigger artifact, not a hardware fault**: the dongle only enumerates once it is
powered and the keyboard is actively on the 2.4 GHz link. With the keyboard in
2.4 GHz mode it enumerates (`342d:e4c6`), exposes the raw-HID collection, and
round-trips `0xA4`. See `docs/HARDWARE.md` "The 2.4 GHz dongle" and the defects
section below.

### 4. A BT-profile keycode silently hijacks the transport, and the mode switch cannot undo it

**Found on hardware 2026-10-09.** After using `KC_BT1` (Fn + right space, then
`Q`) to try Bluetooth, the keyboard stopped typing on USB — on **both** halves —
while USB stayed enumerated and the `0xA4` battery responder still answered.

Root cause (verified in `epomaker_split65.c`):

- `KC_BT1/2/3` and `KC_2G4` call `connection_set_host(...)`, which **persists**
  `desired_host` to EEPROM (`quantum/connection/connection.c`), and
  `connection_host_changed_kb()` (line 1393) maps it onto a vendor device index
  and calls `wireless_devs_change()` — which **persists `confinfo.devs`**.
- At the next boot, `keyboard_post_init_kb`'s housekeeping runs
  `wireless_devs_change(!confinfo.devs, confinfo.devs, false)` (line 362),
  restoring the **persisted** device index. So the board came up on `DEVS_BT1`
  and routed HID reports to the (dead) Bluetooth link while the USB composite
  remained up — hence "enumerated but no keys".
- The **mode switch does not override this on a steady position**: the boot-time
  `hs_mode_scan(false, ...)` only calls `wireless_devs_change()` when
  `hs_modeio_detection()` sees the switch **change** after boot (`sw_mode`).
  Flipping the switch before/at power-up does not force USB.
- There is **no USB-select keycode** on the Fn layer; the switch is the only
  intended USB route.

**Recovery (what actually worked).** `EE_CLR` (hold 3 s) →
`hs_reset_settings()` (`epomaker_split65.c:1708`) → `eeconfig_init()` wipes
EEPROM → `keyboard_post_init_kb()` re-runs `eeconfig_confinfo_init()`, which sees
`confinfo.raw == 0` and calls `eeconfig_confinfo_default()`, restoring
`confinfo.devs = DEVS_USB`. The board then came up on USB and the state
persisted. **Bootmagic is NOT a recovery route here:** `bootmagic_should_reset()`
does `eeconfig_disable()` **and `bootloader_jump()`** — it enters DFU, it does not
resume typing.

**Fix — IMPLEMENTED (2026-10-09), pending flash.** The boot-time restore no
longer trusts the persisted index: `wireless_post_task()` derives the device
index from the **switch level** via `hs_mode_switch_devs()` (`wls/wls.c`) and
sets **both** selectors from it — the vendor index (`wireless_devs_change`) *and*
upstream's `config.desired_host` (`connection_set_host`). Setting only one would
split-brain the two senders (`bt_driver` vs `wireless_driver`); see
`FINDINGS.md` "two senders". Persistence now supplies only the BT1..5
sub-selection the switch cannot express. The decision is a pure, tested core:
`wls/transport_logic.{c,h}` + `tests/transport_logic/` (6 tests, `make
test:transport_logic`) pin the invariant "every switch position × persisted
sub-selection boots onto the switch's own domain". The existing Fn keycode gate
(`hs_modeio_detection`, only acts in the matching switch position) already
prevented keycodes from *starting* the cross-mode contradiction, so no keycode
change was needed. Builds clean (default + nathan); **needs a flash to confirm on
hardware** — that the stale-BT lockout no longer survives a reboot with the
switch on USB.

The mechanism here is the worked example of the **authority-inversion /
edge-vs-level** bug classes, and the state it corrupts is mapped under
`docs/HARDWARE.md` "The known/unknown boundary (no schematic)" (the transport
state is *known* — this defect is a *logic* fault, not a hardware unknown).

## Regressions introduced by our own change set (not vendor defects)

> **ARCHIVAL.** All four regressions are fixed; kept for root-cause rationale.

### 1. Slave backlight flickers then goes dark (split link while cabled) — FIXED

**Symptom.** With both halves joined by the inter-half link cable, the slave's
backlight flickered and then extinguished, on every USB-C cable tried. Absent on
stock firmware.

**Cause.** `suspend_power_down_user()` sends RPC `0xBB` and
`suspend_wakeup_init_user()` sends `0xCC`; the slave's handler maps them to
`gpio_write_pin_low/high(A5)` / `(A8)` — i.e. the master's own suspend/wake
**broadcasts LED-rail power to the slave** (`LED_POWER_EN_PIN`/
`LED_POWER_EN2_PIN`). The pair is asymmetric: `0xBB` fires on every suspend, but
`0xCC` only on a matching QMK wake. When the master entered low power via the
vendor `lpwr_*` path (not QMK suspend/wake), the slave last received `0xBB` with
no `0xCC` to follow, so its rail stayed off.

**Why our change set exposed it.** The flash-ready commit made
`hs_transport_arbitrate_cable()` a no-op. Previously it forced the master's
transport to match the cable every housekeeping tick, which kept the master out
of the wireless low-power path while cabled, so `0xBB` never fired. Removing it
(pre-req for requirement 2) let the master sleep while cabled. Stock firmware had
the arbitrator; ours stopped calling it.

**Fix.** Gate both sends on `wireless_get_current_devs() != DEVS_USB`
(`epomaker_split65.c` `suspend_wakeup_init_user()` / `suspend_power_down_user()`):
the LED-rail relay only makes sense on battery; while cabled the rail stays up on
both halves. Two-line guard, no new coupling.

### 2. Slave reset-looped and went dark (split watchdog) — FIXED (by disabling)

**Symptom.** With the halves cabled, the slave's backlight flickered and then
went entirely dark after ~5–10 s and did not come back on its own keypresses.

**Cause.** `SPLIT_WATCHDOG_ENABLE` was enabled during the re-base (thinking it
would replace the vendor's own disconnect handling — it did not, and it was not
the fix for §1 either). Upstream's `split_watchdog_task()` calls `mcu_reset()` on
a non-master after `SPLIT_WATCHDOG_TIMEOUT` (3 s). But the slave's `done` flag is
refreshed **only** by `split_shmem->watchdog_pinged`, which the master writes only
while the master's own `done` is false. The slave's `is_transport_connected()`
can never re-arm `done` (`connection_errors` is incremented only inside the
master-only `transport_master_if_connected()`), so once the master stopped
pinging the slave reset every ~3 s, forever — rebooting just enough to blink the
rail before the next reset. The vendor firmware never enabled this watchdog.

**Fix.** `SPLIT_WATCHDOG_ENABLE` is **deliberately not defined** in the board
`config.h`, with a comment recording why (so a rebase reader does not re-add it).
Confirmed on hardware: backlight stable, no reset. Upstream's
`transport_master_if_connected()` throttle (`quantum/matrix_common.c:96`) is
unaffected and still live.

### 3. Slave typed nothing (module UART collided with the split link) — FIXED

**Symptom.** Master keystrokes registered; slave keystrokes produced no
characters at all. Present on our build, absent on stock.

**Cause.** The vendor's old `platforms/chibios/drivers/uart.h` carried a
deprecation alias layer mapping `SERIAL_DRIVER`→`UART_DRIVER` and `SD1_*`→
`UART_*`. Upstream **removed that file**, and the re-base re-added `UART_TX_PIN`/
`UART_RX_PIN`/pal-modes but **omitted `UART_DRIVER`**. `uart_serial.c` then
defaults `UART_DRIVER` to `SD1` — the same peripheral as the split link
(`SERIAL_USART_DRIVER SD1`). Two drivers on UART1 meant the slave's matrix rows
never reached the master.

**Fix.** `#define UART_DRIVER SD3` in the board `config.h` (the vendor's value),
with a comment. Confirmed on hardware: the slave types.

### 4. Master half entered an unrecoverable STOP on a non-USB transport — FIX (pending hardware)

**Symptom.** On Bluetooth, after ~60 s idle the **master** (left) half's
backlight went dark and it produced no characters; no keypress revived it. New
because the master was previously exempt (USB-only testing).

**Cause.** `lpwr_is_allow_timeout_hook()` exempted a half only when
`wireless_get_current_devs() == DEVS_USB`. Off USB the master became
timeout-eligible and entered STOP on the plain idle timer
(`hs_rgb_blink_hook()`, `HS_SLEEP_TIMEOUT` = 60 s). That path runs with
`lower_sleep == false`, so the board's `lpwr_stop_hook_post()` (gated on
`lower_sleep`) is a no-op, and a wake code of `LPWR_WAKEUP_UART` — which the
board deliberately does not arm, yet `palcallback()` still maps the pad to —
returns the machine to `LPWR_STOP` **without running `lpwr_wakeup_cb()`**. The
half re-enters STOP with no rail re-raise and no matrix re-init: dark and
unresponsive. Same class as regressions 1–3: a half entering an unrecoverable
low-power state. (The earlier note that this path "arms none of the driver-side
wake sources" was wrong — the master arms its own rows, the mode-switch pins and
the cable pin on both paths; see the correcting finding in `docs/FINDINGS.md`.)

**Fix (upstream-shaped, shared).** Two layers, both in the shared state machine
so the invariant is enforced once rather than at each entry point:

1. **The stop is refused unless sanctioned.** A sleep-policy contract
   `lpwr_stop_is_allowed()` (declared `lowpower.h`, weak default true in
   `lowpower.c`) is implemented by the board (`wls/wls.c`: master &&
   `lower_sleep`) and **checked in `lpwr_stop_cb()`**: false means the stop is
   refused and the machine falls back to `LPWR_NORMAL`. The board's
   `lpwr_is_allow_timeout_hook()` is simplified back to its own concern (master,
   not USB).
2. **A wake code is a set, and only an armed one counts.** The wake codes are now
   bit flags (`LPWR_WAKEUP_MATRIX = 1<<0`, …, `SWITCH = 1<<6`), accumulated by
   `lpwr_set_sleep_wakeupcd()` and compared **as a set** against a board-supplied
   `lpwr_wakeup_armed_mask()` (default weak = all). Because the WB32 EXTI is
   pad-numbered and port-discarding, the module UART RX `C11` aliases matrix
   column `B11` on pad 11, so a column line event is misclassified as
   `LPWR_WAKEUP_UART`. The board's mask is
   `MATRIX | CABLE | SWITCH | USB` (never UART), so a phantom UART-only wake no
   longer satisfies the test and the half is not sent back to STOP. `lpwr_stop_cb`
   now reads `if (wakeupcd & armed_mask) → LPWR_WAKEUP else → LPWR_STOP`; the
   old `switch` on a single code would misread a multi-bit set.

Width note: the wake set storage and getter were widened to `uint32_t` because the
armed mask is 32-bit; the first build stored the set as a byte and would have
truncated a future flag (caught by lldb disassembly, not by the compiler).

See `docs/FINDINGS.md`, "the three power-off faults are one defect", "the
wake-armed predicate was a proxy; the real fault is an unhandled wake code", and
"the WB32 EXTI aliases pads, and a wake code must be validated as a set". Not yet
flashed.

### 5. Right (slave) half backlight off while typing on USB — FIXED (rearchitected)

**Symptom (2026-10-09).** With the board cabled over USB-C, the **right
(slave) half's backlight is off**, yet the board still types normally — input
runs over the split link, which is unaffected. The same observation class
appeared on the off-cable BT session, on the *other* half (the left/master went
dark). Durable on both transports; the right half's keys still register.

**Root cause (confirmed by reading source).** `A5`/`A8`
(`LED_POWER_EN_PIN`/`LED_POWER_EN2_PIN`) are the backlight-rail **ENABLE**, and
the rail was written ad hoc from sites that disagreed:

1. `keyboard_post_init_kb()` / `lpwr_wakeup_hook()` — set the rail from a
   **snapshot** of `rgb_matrix_get_val()`, once, at boot/wake.
2. `QK_RGB_MATRIX_VALUE_UP` / `_DOWN` — drove `A5`/`A8` directly, unguarded by
   `is_keyboard_master()`, duplicating what QMK's own `process_rgb_matrix`
   already does to the RGB *value*.
3. The cross-half `0xBB`/`0xCC` relay — `0xBB` forced the slave's rail **LOW**,
   `0xCC` raised it. Both senders are gated `if (wireless_get_current_devs() ==
   DEVS_USB) return;`, so **on USB neither fires** — a `0xBB` received while
   off-cable had no `0xCC` to undo it.

No path re-raised the rail after a LOW write, so a stray `0xBB` (its matching
`0xCC` USB-gated off) or a local value-down press left a half **permanently dark
while still typing**. The rail is LED enable, not matrix power — hence the
"dark but functional" symptom. This **confirms the rail-latch hypothesis and
refutes the link-relay one** (input works over the split link).

**Fix (rearchitected, not patched).** Rather than add a fifth writer, the rail
became a **pure function of the RGB value with a single owner**:
`wls_led_rail_apply()` (`wls/wls.c`, declared `wls.h`) sets `A5`/`A8` from
`rgb_matrix_get_val() != 0`. Every former writer is now a **caller**:
`keyboard_post_init_kb`, `suspend_wakeup_init_kb`, `lpwr_wakeup_hook`, the
VALUE_UP/DOWN handlers, the `0xCC` relay, and a per-tick reassertion in
`housekeeping_task_user` (runs on both halves). The `0xBB` handler no longer
forces the rail off — the slave's own suspend path drops it when it actually
sleeps. Net: the rail self-derives and cannot be latched LOW. A Chesterton's-fence
analysis (why was the rail written where it was?) showed the scattered writers
*were* the defect, so collapsing them is the fix, not the risk. The only
remaining direct writes are pin setup and the explicit suspend power-down (a
one-way action, not a latch).

Board-local by nature (a vendor rail-relay quirk, not a generic model gap).
Build clean (63,552 B); `format-c` clean; tests pass (transport_logic 6,
lowpower_logic 8, wireless_nkro_parity 8). **Not yet flashed.**

**Next probe (hardware).** Flash, then with the right half dark: read `0xA4`
(master alive) and press **Fn+`↑`** (brightness up, `RM_VALU`) — the **slave**
rail must come back and stay back. (Not `Fn+F5`/`F6`: on the `nathan` keymap the
`_FL` F5/F6 keys are plain `KC_F5`/`KC_F6`; the RGB-value keys are `RM_VALU` on
Fn+`↑` and, since the brightness fix, `RM_VALD` on its left neighbour plus the
Fn-layer encoder.)

### 6. Right (slave) half's backlight flashes on a fixed interval — FIXED (rearchitected)

**Symptom (2026-10-09).** The right half's backlight flashes on a **consistent
~2 s interval**; re-seating the inter-half cable does not change it.

**Root cause (confirmed by reading source).** `wireless_devs_change_kb(old, new,
reset)` served **two unrelated purposes**: (1) bookkeeping — mirror the vendor
device index into `confinfo`; (2) a transient **pairing-indicator flash** (`switch
(new_devs)` → `rgb_matrix_wls_indicator_set(index, color, 500, 1)`). (1) must run
on every call; (2) should run only on a real transition — but they were welded
together, so the function blinked on every call with no change guard. Three
callers re-assert with `old == new`: the master's **2 s** `master_sync_mms_slave`
(carries the battery `pov`), the `MD_STATE_DISCONNECTED` retry in
`hs_rgb_blink_hook`, and `rgb_matrix_wls_indicator_cb`. So every 2 s the slave was
told "you're on channel N" and re-flashed the indicator — a blink with no meaning,
on the half the user did not touch.

**Why it should not exist as-is (UX).** The indicator is *feedback for a deliberate
action* (Fn+Q/W/E or a switch move confirms the channel). A periodic flash is not
feedback: on a split it flashes the half you did not press, and a signal that
fires on non-events trains the user to ignore it. It had escaped its purpose.

**Fix (rearchitected, A: one-shot on real transitions, both halves).**
`wireless_devs_change_kb` is now **bookkeeping only** (no LED writes; params
unused). A new **`wls_indicate_devs(new_devs, reset)`** owns the transient flash and
is called **only** from genuine transitions: the mode-switch edge
(`wls.c` `sw_mode`), the Fn+Q/W/E keycode tap (`WLS_KEYCODE_EXEC`), the three
re-pair long-presses, and the indicator's own self-re-arm while still unconnected
(`rgb_matrix_wls_indicator_cb` — a repeat policy, not a change). The 2 s sync
becomes a true no-op for LEDs. `wls_rgb_indicator_reset` now travels with
`wls_indicate_devs`. This is the **same separation as defect 5** (effect out of
bookkeeping, one owner, no-ops silent) — board-local.

Build clean (63,804 B); `format-c` clean; tests pass (transport_logic 6,
lowpower_logic 8, wireless_nkro_parity 8). **Not yet flashed.**

### Process note — anticipatable issues were not anticipated

Both §1 and §2 were foreseeable from upstream's own code and mechanics, and §2 and
§3 are both **rebase omissions** (dropped alias macros; an upstream feature enabled
without checking its slave-side contract). None was caught because the re-base port
audit checked only **breaking changes**, never "what upstream **features** does this
board now become eligible for, and what are their contracts?". Standing rule: after
any base or feature change, enumerate newly-eligible upstream mechanisms *and* trace
their contracts on this board — not just the compile breaks.

## Code audit — bespoke payload correctness and upstream-idiom review

> **ARCHIVAL.** Findings fixed or deferred; kept for rationale.

A full read-only audit (three passes: shared wireless stack, board files, host
tooling/CI) of the ~5,460-line payload we carry. Findings below are **verified by
reading the source**, not inferred. Ordered by severity. Nothing here is fixed
yet unless marked DONE.

### High — memory safety / races

- **`md_send_devinfo()` pushes a frame whose checksum is not last.**
  `keyboards/linker/wireless/module.c:370-384` does
  `md_calc_check_sum(sdata, infolen + 2)` then `smsg_push(sdata, sizeof(sdata))`
  (the full 21 bytes). Every sibling sender (`md_send_manufacturer`/`product`,
  `:395-421`) pushes `len + 3` so the checksum is the final byte, which is where
  the receiver's `md_check_sum` looks. For any device name shorter than
  `MD_SND_CMD_DEVINFO_LEN` (18) the BT-name frame is non-conformant. **Fix:**
  `smsg_push(sdata, infolen + 3)`.
- **Send-buffer overrun.** `md_pkt_payload` is `MD_SEND_PKT_PAYLOAD_MAX` = 36 B
  (`module.c:22,68`), but `md_send_manufacturer`/`md_send_product` can push up to
  `MD_SND_CMD_MANUFACTURER_LEN + 3` = 49 B (`module.h:33-34`), and `smsg_peek`
  (`smsg.c:85-90`) copies `tail - head` with **no capacity argument**. Up to 13
  bytes are written past a static buffer before `uart_transmit` sends them. The
  dongle/name RPCs reach this. **Fix:** size the payload to the true max frame,
  or give `smsg_peek` a capacity and clamp.
- **UART RX framing writes past `md_rev_payload[36]`.**
  `module.c:163-176`: the `MD_REV_CMD_RAW` arm sets `data_remain = data + 1` from
  the **received length byte** with no bound, then `default:` does
  `md_rev_payload[data_count++]` unchecked. A declared length ≥ 33 overruns; a
  length of `0xFF` wraps `uint8_t` and overruns by ~256. The only later guard
  (`len == sizeof(md_raw_payload)`, `:194`) is far too late. **Fix:** reject
  `data > MD_RAW_SIZE` at case 2 and clamp the write.
- **ISR-shared sleep flag is not `volatile`.** `lpwr_wakeupcd` is written from the
  PAL EXTI callback (ISR context, `wireless/lpwr_wb32.c:37-55` →
  `lowpower.c:74-76`) and read in the main loop after `__WFI()`
  (`lowpower.c:241,246`) without `volatile` or a barrier. **Fix:** mark it
  `volatile`; take `osalSysLockFromISR` if a multi-byte update.

### Medium — link integrity and drift

- **`smsg_push` return value discarded everywhere.** All ~12 callers
  (`module.c:322-447`) ignore the `bool`, so a full ring silently drops a report
  (lost key release) or a reset RPC. **Fix:** check it and flag/retry.
- **`md_send_vpid` signed-shift UB.** `module.c:427` `pid << 16` on a `uint16_t`
  promoted to signed `int` is UB for `pid ≥ 0x8000`; the following `memcpy`
  also assumes host endianness. **Fix:** cast to `uint32_t`; encode explicitly.
- **Framing state can desync permanently.** `module.c:122-123` `static
  data_count/data_remain` have no inter-byte timeout, so a stall mid-frame
  mis-parses all subsequent bytes (compounds the RX overrun above). **Fix:** idle
  timeout that resets both counters.
- **`WEAR_LEVELING_BACKING_SIZE` defined in both places, board wins silently.**
  `config.h:104` = 8192 vs `keyboard.json` `eeprom.wear_leveling.backing_size` =
  4096. Board `config.h` is force-included before the generated `info_config.h`
  (whose value is `#ifndef`-wrapped), so the 8192 wins and keyboard.json is
  ignored — the opposite of upstream's "keyboard.json is source of truth".
  Vendor-inherited, but exactly the rebase-drift class. **Fix:** keep the value in
  one place.
- **`rgb_record` duplicate buffer definition.** `rgb_record/rgb_record.c:24` and
  `:44` both define `static uint8_t rgbrec_buffer[...]` (legal tentative
  redefinition; the second is dead). Remove one.

### Low — idiom, dead code, rebase fragility

- **`record_color_hsv` reads `rgb_hsvs` out of bounds** (`rgb_hsvs[RGB_HSV_MAX]`
  and `rgb_hsvs[0xFF]`; array is `[7][2]`, `rgb_record.c:279-304`). **Unreachable
  dead code** — its only caller `record_rgbmatrix_increase` (`:256`) has no
  callers — but it is exported. Fix or delete with the function.
- **Board file occupies the `_user` hook namespace:** `process_record_user`,
  `suspend_wakeup_init_user`, `suspend_power_down_user`, `hs_reset_settings_user`
  are defined in `epomaker_split65.c` (a keyboard file). Works today, but any
  keymap that also defines them will collide. Move bodies to the `_kb` variants
  and call `_user` from there.
- **`rgbrec_set_close_all()` index arithmetic** (`rgb_record.c:181-182`) uses
  `row * MATRIX_COLS * col * 2` instead of `((row * MATRIX_COLS) + col) * 2`.
  Unreachable (no caller) but exported.
- **`bin/compiledb` is silently broken.** It calls the deprecated
  `qmk generate-compilation-database` (now a stub that returns `False` without a
  non-zero exit); `bin/qmk` does not propagate the CLI return value, so `set -e`
  does not trip and a **stale** `compile_commands.json` is reported as success.
  **Fix:** use `qmk compile --compiledb`; make `bin/qmk` `sys.exit(cli())`.
- **`split65.py` `check`/`setup` always exit 0** and `check`'s warning cites a
  `--transport` flag that belongs to `battery_polybar.py`, not `split65.py`.
- **`battery_polybar.py`** can raise an unhandled `HIDException` if the device
  vanishes between `enumerate()` and `open()` (breaks the "exit non-zero, no
  output" contract). Its `interface 2 = dongle` selection assumption is no
  longer unverified — it was **confirmed on hardware 2026-10-09** (interface 2
  carries the raw collection; see defect 3 above).
- **Rebase fragility:** `md_raw.h` remaps `raw_hid_send` by `__LINE__`
  (`_temp_rhs_29`/`_temp_rhs_489`) — any upstream line shift breaks it (the CI
  guard exists precisely for this); `transport.c:49` reaches into the core
  file-local `last_suspend_state` via an inline `extern`.
- **Dead/unused:** `SERIAL_DEBUG` (`config.h:85`, referenced nowhere),
  `test_white_light_flag`, `hs_ct_time`, unused `rgbrec` colour defines, and a
  stray `if (s2m.resp == 0x00);` no-op (semantic: `epomaker_split65.c:142` and
  three more).

### Confirmed clean

- `wls/wls_battery.c` raw-HID receive path: checks length and command byte, only
  touches indices 0-6 of a 32-byte buffer — no OOB.
- All RGB/matrix LED indices used are < `RGB_MATRIX_LED_COUNT` (68); `rgbrec`
  buffer/view dimensions match `MATRIX_ROWS`×`MATRIX_COLS`.
- `rgbrec` EEPROM addressing and region sizes are consistent.
- `halconf.h`/`mcuconf.h` match current WB32 ChibiOS expectations.
- `bin/make`, `bin/qmk` (except return-value propagation), `.gitignore` and the
  userspace `.gitignore` are correct; no tracked build artifacts or secrets.
- All shared-stack and board files carry `SPDX-License-Identifier:
  GPL-2.0-or-later` **except** `rgb_record/rgb_record.h` (legacy prose header).

## Design cleanup — ownership/cadence audit (`docs/AUDIT.md`)

> **Live.** The actionable tracker is `docs/AUDIT.md` (state/effect inventory
> with dispositions, and the "clean = provable" acceptance bar). This section
> records progress only; edit the audit doc for the current list.

A four-pass audit found the defects that surfaced were one shape, not random:
**state-ownership faults** (multiple writers for one state; one function doing
two jobs at different cadences; state derived at the wrong time). Our own
additions are among them. Fixes land as **pure core + test + trivial shell**,
one commit each, ordered by risk × provability.

- **Fix 1 — DONE.** `keycode_shadow` (the long-press re-pair could target the
  wrong profile because the deferred timer captured a *pointer* into shared
  state that every later keypress overwrote). Now a pure
  `hsm_long_press_devs(keycode)` decides the target and the shell passes the
  **value** at arm time; the shared shadow is deleted. Pure-core test
  `TransportLogic.long_press_target_is_a_keycode_table` (7/7 pass). Submodule
  commit recorded in `docs/AUDIT.md`.
- **Fix 2 — DONE.** The BT profile was a second RAM variable (`wls_bt_profile`)
  kept in lockstep with the device index only by convention, so a
  `wireless_devs_change` that bypassed `bluetooth_select_profile` could desync
  it and make `bluetooth_get_profile()` lie in the `0xA4` reply. The variable is
  deleted; the profile is **derived** via pure `hsm_profile_of_devs(devs)`.
  Pure-core test `TransportLogic.bt_profile_is_a_pure_function_of_the_device_index`
  (8/8 pass).
- **Fix 3 — DONE.** `confinfo.devs`/`.last_btdevs` had two writers (the
  `wireless_devs_change_kb` bookkeeping mirror and the `wls_persist_devs` user
  path) in a struct a third field (`KC_FILP`) persists whole — so an internal
  change could commit a transport the user never chose. The board no longer
  overrides the vendor hook (mirror gone); `confinfo.*` is written **only** by
  user intent and read only as the boot seed. Every live "current mode" reader
  now uses `wireless_get_current_devs()` via pure `hsm_mode_seed`/`hsm_seed_btdev`.
  Pure-core tests `mode_seed_is_the_live_device_index` and
  `bt_seed_prefers_live_index_and_clamps_fallback` (10/10 pass).
- **Fix 4 — DONE.** `hs_linker_rgb_timer` (one timestamp read as *both* the 30 s
  reconnect timeout and the 60 s sleep timeout, in a fall-through pass) is split
  into two independent deadlines (`hsm_link_timers_t.reconnect_at`/`.sleep_at`).
  The policy is the pure `hsm_link_watch()` (arm on entry/change, fire the
  state's own deadline, clear the other state's) plus `hsm_link_restart()` for
  activity events; the shell only performs the returned action. The missing
  `break` that caused the fall-through is gone. Pure-core tests
  `link_watch_uses_independent_deadlines` and `link_watch_clears_foreign_deadlines`
  (12/12 pass).
- **Fix 5 — DONE.** The ordered-sleep flag (`lower_sleep`) has one authority:
  it moved into `wls/wls.c` behind `wls_order_sleep(bool)` / `wls_sleep_ordered()`,
  and the `extern bool` is gone. Every reader is a side-effect-free query (the
  wake-clear no longer writes a bare global), and the low-battery decision is the
  pure `hsm_should_order_sleep(level, charging, stop_threshold)`. Pure-core test
  `sleep_order_is_a_pure_function_of_battery_and_charge` (13/13 pass).
- **Fix 6 — DONE.** `md_info.state`/`.indicator` had two writers: the module UART
  decoder *and* the vendor `wireless_devs_change` (which poked the registers on a
  device change). The transition is now expressed once, by the module that owns
  the registers: `md_devs_changed()` (module.c) replaces the two pointer writes,
  so no external writer reaches `md_info`; callers read via the accessors.
- **Fix 7 — DONE.** Dead state deleted (`inqbat_flag`, `test_white_light_flag`,
  `start_hsv`, `temp`, `im_test_rate_flag`, `prev_cable_state`), the no-op
  `hs_transport_arbitrate_cable()` and its two calls removed, and
  `bat_indicator_cnt`'s initializer corrected (`true`→`0`, a valid ms epoch).
  Host tools consolidated: one `REPLY_INDEX` drives `parse_reply`, one
  `CHARGE_NAMES` table feeds both formatters, the dead `None` interface branch is
  gone, and the stale "UNVERIFIED" interface-2 notes are corrected.
- **Fix 8 — DONE.** The `raw_hid_send` line-pinned macro (`md_raw.h`, pinned to
  `__LINE__` 29/489 and force-included into every TU) is **deleted**. Its shim
  `replaced_hid_send()` had become behaviorally identical to upstream
  `raw_hid_send()` (both route to `host_raw_hid_send()` → the active driver's
  `send_raw_hid`), so the alias, the shim, the direct board call, and the
  `-include md_raw.h` in both `.mk` files are all removed. The board calls plain
  `raw_hid_send()`; the receive path (`md_receive_raw_cb` → `raw_hid_receive`)
  stays in `md_raw.c`. A pure deletion (−4 bytes, no new code).
- **Fix 9 — DONE.** `md_receive_msg_task` framed six reply types *and* interpreted
  them, carrying the in-progress frame in two coupled statics (`data_count`,
  `data_remain`). The framing half is now the pure, include-free core
  `keyboards/linker/wireless/md_frame.{c,h}`: state carries the decided grammar
  and the expected length, `md_frame_feed(state, byte)` returns whether a frame
  completed and its length, and the shell (`module.c`) only interprets completed
  frames. It lives in the **shared** tree (not the board `wls/`) because
  `module.c` is shared across ~20 boards and must not include a board header.
  Tested byte-by-byte (`tests/md_frame`, 8/8; `transport_logic` 13/13).
- **Fix 10 — DONE** (`docs/AUDIT.md` Tier 2). Two defects in the STOP entry:
  (a) `lpwr_set_sleep_wakeupcd(LPWR_WAKEUP_NONE)` was an accumulate-only setter
  (`|= 0`), so the wake set was **never cleared** before entering STOP — a stale
  code could survive into the next window. New `lpwr_clear_sleep_wakeupcd()`
  clears under `chSysLock()`/`chSysUnlock()` against the ISR `|=`
  (`lpwr_wb32.c` `palcallback`). (b) `lpwr_is_allow_timeout()` was a *query with
  a side effect*: it consumed the one-shot `manual_timeout` on every path,
  destroying a request made while the decision was false (on USB, or hook-forbidden).
  It is now the pure `lpwr_timeout_allowed_decide()` (`lowpower_logic`), and the
  caller (`lpwr_task`) consumes the override only when the timeout path is taken.
  Tested: `lowpower_logic` 9/9 (new `timeout_is_allowed_only_when_a_stop_can_be_taken`).
- **Tier 3 — ACCEPT + document** (upstream contract: `driver` fallthrough, the
  unconditional `connection_set_host` EEPROM write, the hook-skipped-on-no-op
  gap), plus one genuinely-new incompleteness to fix: `wireless_2p4ghz_init/task`
  mirror the BT contract but `keyboard.c` never calls them.

## Right-half DFU without hardware shorting

Goal: let the right half enter the WB32 DFU bootloader by holding a key, like the
left half, instead of shorting the spacebar switch pins (remove the spacebar,
short the two metal-plated holes where the switch feet insert, plug USB-C).

Rationale / evidence:

- `QK_BOOT` is handled in the application firmware at
  `qmk_firmware/keyboards/epomaker/epomaker_split65/epomaker_split65.c:1071`:
  it calls `eeconfig_disable()` then `bootloader_jump()`. `bootloader_jump()` is
  a **local MCU operation** and the handler is **not** gated on
  `is_keyboard_master()`, so a `QK_BOOT` key pressed on the right half should jump
  *that half* into its own bootloader.
- Both halves run identical firmware, so adding `QK_BOOT` to the keymap adds it
  to both. The `nathan` keymap maps `QK_BOOT` on the **Fn** layer at the right
  half's matrix `[10,4]`; the left half has **no** keymap route into its own
  bootloader (its rows are 1–5, so a left-half key cannot fire `[10,4]`).
- Esc-hold (bootmagic) is **broken on our build on both halves** (it works on
  stock). On the left half it is no longer even the documented route — the
  spacebar-hole short is. That asymmetry is why the physical short is currently
  required for both halves.

Plan:

1. Add a `QK_BOOT` binding to a convenient Fn position in
   `qmk_firmware/keyboards/epomaker/epomaker_split65/keymaps/default/keymap.c`.
2. Rebuild and flash both halves.
3. Verify: with the right half connected over USB, press the key and confirm it
   enumerates as `342d:dfa0` (`wb32-dfu-updater_cli -l`).
4. If it works, document the key-based method as primary in `docs/DEPENDENCIES.md` and
   keep the spacebar-pin short as the hardware fallback.

Caveats to confirm empirically:

- The right half must be connected directly to the host over USB when the key is
  pressed (DFU enumerates on the USB port).
- **Cold-plug requirement:** the WB32 bootloader samples the boot pin only at
  reset, so the jump must land the half in DFU during a fresh enumeration. A
  `QK_BOOT` press on a sleeping slave may not enumerate; if the half does not
  appear as `342d:dfa0`, unplug and replug it (or fall back to the short).
- Untested on this board whether the slave half processes `QK_BOOT` while not
  master; expected to work because the jump is local, but verify before relying
  on it.
- Hardware shorting remains the firmware-independent recovery path and must stay
  documented even if the key-based method works.

## User experience / usability review of the keyboard mappings

The mappings and indicators are inherited from the vendor and were designed for
the stock firmware; they have never been reviewed against how this keyboard is
actually used. Audit and question each of the following, then decide what (if
anything) to change in the `nathan` keymap (userspace repo — see Status) and
whether the vendor defaults deserve an upstream report.

Three of these were pulled forward into **Tier 0, item 2** because they are
cheap and must land in the same flash as other pre-flash decisions: the
`QK_BOOT`/`EE_CLR` placement, the battery-indicator-vs-fill decision, and whether
to trim the compiled-in animation list. The remainder stay here.

- **Charging/battery LED placement.** The only charge renderer is the
  master-only soft indicator at `HS_MATRIX_BAT_SOFT_INDEX 64` (right half, bottom
  row, `[11,5]`, fourth from the right). Question whether that is discoverable at
  all: it sits on the *opposite* half from the battery-bearing half it describes,
  is master-only, and is invisible when RGB brightness is zero. Consider a better
  location or a dedicated indicator, and whether the level colours are
  distinguishable.
- **Default RGB effects.** Partly addressed: the vendor rainbow is gone; the
  default is now solid white at 50%, declared in `keyboard.json`
  (`rgb_matrix.default`) with the keymaps re-applying it persistently in
  `keyboard_post_init_user()`. Open questions remain: the effects are still
  compiled in and reachable via `RGB_MOD`, the stock wave drains battery, and the
  soft battery indicator blends into the fill rather than overriding it. Decide
  whether to review/trim the enabled animation list
  (`keyboard.json` `rgb_matrix.animations`, ~44 entries) and whether the battery
  indicator should override the fill.
- **Battery indicator vs solid fill.** With a uniform white fill, the battery
  indicator is the only thing that breaks it (one LED on the right half shows the
  charge colour). Decide whether that single-LED exception is wanted, and whether
  it should be more prominent given it is the only charge readout.
- **Connection-mode switching.** `KC_BT1`/`KC_BT2`/`KC_BT3`/`KC_2G4` (Fn layer,
  row 1) and the physical mode switch both exist. Question the discoverability of
  the keycodes, whether the currently-selected channel is visible, and whether
  the switch-and-keys interaction is coherent.
- **Keycap legends vs matrix.** Legends do not reliably match matrix positions
  (see `docs/HARDWARE.md`), so any mapping work must identify keys positionally
  ("right half, bottom row, fourth from the right"), never by legend.
- **`QK_BOOT` / `EE_CLR` placement.** `QK_BOOT` sits on the **Fn** layer at the
  Fn-layer top-right corner key (matrix `[10,4]`), **not** on the base layer, and
  `EE_CLR` on the `_RST` layer at the right-half bottom-right corner (matrix
  `[11,7]`). Reaching `QK_BOOT` takes a held spacebar (Fn) plus that key; `EE_CLR`
  takes a held Fn-plus-corner chord plus the opposite half's corner, so no single
  accidental keypress reaches either.
- **Layers and ergonomics.** `_FL` is reached by holding right Spacebar
  (`LT(_FL, KC_SPC)`); `_MBL`/`_MFL` are the Mac variants. Question reachability,
  whether the held-modifier arrangement is comfortable, and whether the Mac/PC
  split is worth the complexity.
- **Battery-related keycodes.** `KC_BATQ` is disabled on USB
  (`confinfo.devs == DEVS_USB`) and only blinks when level <= 15, so it is nearly
  useless as a query key. Question whether it should report a real level instead
  (ties into the `md_info.bat` staleness defect above).

Deliverable: a reviewed mapping with a written rationale for every deviation
from the vendor default. Record findings here and in `docs/FINDINGS.md`.

## Reverse-engineering the board (no OEM schematic exists)

> **ARCHIVAL.** A plan, not yet executed; kept as the probe-runbook.

Epomaker has not published a schematic, and QMK upstream has flagged the lack.
The board is in hand and fully USB-powered, so a reverse-engineered
**interface-level** map is recoverable — enough for a QMK port. What probing can
and cannot establish:

- **Definitive (measured):** pin-to-signal mapping for every GPIO; net
  connectivity (continuity on an unpowered board); power-rail voltages; the WS2812
  daisy-chain order; the module UART and its protocol (with a logic analyzer);
  charging/FULL/CABLE line polarity and behaviour.
- **Inferred, not proven:** component values read in-circuit (parallel paths make
  a meter lie); *why* a net exists; the module's internals (sealed sub-board).
- **Effectively unknowable:** PCB inner-layer routing under a power plane (the
  endpoints are findable, the path is not); laser-etched part numbers; the
  designer's naming and intent. You reconstruct a functionally-equivalent
  schematic, never *the* schematic — label it **reverse-engineered** (measured
  nets = fact; values/intent = inference).

Probe plan (produces an upstream-usable pin/net map):

1. **Cold, unpowered — continuity.** Enumerate the MCU package pins and classify
   each as connected / NC. Map matrix rows and columns (already partly known from
   the firmware: rows 1–5 left, 7–11 right; `MATRIX_COLS 9`). Confirm the LED
   data chain start and order. Identify the module UART, power and control pins,
   and the USB-C CC/ID conditioning. Prefer exposed test pads/probe points; do
   not lift legs.
2. **Powered — voltages.** USB VBUS 5 V, the 3.3 V (or core) regulator output,
   the LED rail, the charger output. Record each under USB power.
3. **Powered — dynamic.** Toggle each firmware-known pin (A5/A8 LED power, A7
   cable detect, A15 FULL, B9 handedness, B7/B6 encoder, C10/C11 module UART,
   A9/A10 split link) and observe the responding net. For firmware-*unknown*
   GPIOs, toggle in a scratch build and watch where the state changes.
4. **Logic capture.** A logic analyzer on the module UART (SD3, C10/C11) and the
   WS2812 data line turns "this is a UART" into the concrete protocol —
   confirming the deobfuscated `module.c`/`smsg.c` or surfacing undocumented
   commands. Highest-value new knowledge.

Caution: continuity on a populated board is the slow/lossy part, not the
electrical part. Record every result as measured vs inferred. Deliverable: a
`docs/` reverse-engineered interface map a QMK reviewer can trust.

## Debugging capability (probe + tooling prerequisites)

Static ELF inspection is available now (lldb 23.1.1 and gdb 18.1 are installed;
`target create --arch armv7m <elf>` + `image lookup -rn` + `disassemble -n`) and
has already paid for itself — it caught the wake-set width-truncation bug in the
sleep-invariant work. What it cannot do is **runtime** truth: no breakpoints, no
watching `lpwr_wakeupcd` live, no single-stepping the STOP entry. That needs a
hardware debug probe, which is absent (`lsusb` shows no ST-Link/J-Link/CMSIS-DAP;
no `/dev/ttyACM*` or `/dev/ttyUSB*`).

**Software (no AUR, installs cleanly):**

- `arm-none-eabi-gdb` (17.2, `extra`) — target debugger; also what QMK's own
  debug docs assume. `gdb` 18.1 is already present and multi-arch-capable, so
  this is a convenience, not a hard requirement.
- `openocd` (1:0.12.0, `extra`) — the probe server. Useless without a probe, but
  install it alongside so the probe is plug-and-play when it arrives.

**Hardware (the actual gate):**

- A **CMSIS-DAP** or **ST-Link** probe (~$10–25; e.g. Raspberry Pi Debug Probe).
  SWO is a bonus for UART/protocol work (favours an ST-Link V3 or J-Link).
- **SWD pads not yet mapped** — the reverse-engineering probe plan above must
  locate them (they are likely among the un-enumerated GPIO/test points). A probe
  is only useful once its SWDIO/SWCLK/GND connections are found.
- Trust implications: a probe on a connected target permits flash, halt, memory
  read/write. Treat it as a hard-to-recover operation and confirm with the user
  before attaching to a powered board.

**Order of value:** (1) the SWD pads must be found (reverse-engineering item 1);
(2) the probe makes runtime debugging possible; (3) `openocd` + `arm-none-eabi-gdb`
drive it. Until (1), installing the software changes nothing.

### Pre-flight rule for any state-persisting path (added 2026-10-09)

A hardware test that exercises a **state-persisting** code path must establish the
**non-flashing recovery** first. `TODO.md` defect 4 is the worked example: `KC_BT1`
was treated as "a pairing gesture" but it persists the host to EEPROM and, at the
next boot, overrides the physical mode switch — stranding the board on a dead
transport with typing silently routed nowhere. The persistence chain was readable
in the source we had already read (`connection_set_host` → `eeconfig_update_connection`;
`connection_host_changed_kb()` → `wireless_devs_change()` → `confinfo.devs`; boot
restores `confinfo.devs`), so this was **anticipatable without a flash**.

Before touching such a path on hardware, answer in writing:

1. **Does it persist?** Grep the keycode/handler for `eeconfig_update*`,
   `connection_set_host`, `*_change(`, `confinfo`. If it writes EEPROM, it survives
   a reboot.
2. **What overrides the persisted value, and is that authority real?** Here the
   switch *looked* authoritative but only acted on an **edge** after boot, so it was
   not an escape hatch.
3. **What is the recovery that needs no flash?** Establish it *before* acting
   (here: `EE_CLR`, hold 3 s → `hs_reset_settings()` → EEPROM wipe → USB default).
   Note that bootmagic is **not** one — it jumps to the bootloader.
4. **What is the observable failure and its detector?** "Enumerated but no keys"
   (HID node present, no events) was the symptom; a one-line `cat
   /dev/input/by-id/...` probe on the live keyboard node shows it immediately.

This is the same discipline as the sleep-test precondition (defect 2's deferred
note): establish reachability and recovery up front so a hardware session cannot
leave the device in a state only a reflash clears.

## Other

- **Wireless while charging (requirement 2)** — now first-class, see `## Priority
  order` item 8 and `docs/FINDINGS.md` "Functional requirements". Verdict to be
  recorded in `docs/HARDWARE.md`.

- Firmware unit tests for the board-local pure helpers (`kb_battery_charge`,
  `kb_battery_transport`, `kb_battery_changed`, `kb_battery_snapshot`) — deferred
  pending the hardware probe. (`kb_battery_percent` no longer exists; the value is
  upstream `battery_get_percent()`.)
- **The sleep decisions are extracted and unit-tested.** The functional core is
  `keyboards/linker/wireless/lowpower_logic.{h,c}`
  (`lpwr_stop_is_allowed_decide`, `lpwr_wakeup_is_real`); `lowpower.c` and the
  board `wls.c` are thin adapters. Tests live in `tests/lowpower_logic/` (modern
  `tests/<name>/` layout; run `make test:lowpower_logic`, 8 tests). Conventions and
  rationale in `docs/FINDINGS.md`. Next candidates in the same style: the
  `md_*` decode helpers and the pad→wake-code classifier (the latter needs the
  pad map as data, and is what would have caught the aliasing bug as a test).
- Bluetooth transport: confirm whether the BT link exposes the raw HID
  collection (`0xFF60`/`0x61`) and whether `*md_getp_bat()` is populated over BT;
  BLE Battery Service `0x180F`/`0x2A19` is the host fallback.
- Re-basing onto current upstream QMK is now **Tier 0 item 1** (see `## Re-base`
  below and `docs/FINDINGS.md` "the vendor fork is shallow").

## Re-base

> **ARCHIVAL.** Landed; kept for rationale. Current commit/gitlink state is in Status.

The move off the vendor's Oct-2024 core onto current `qmk/qmk_firmware` master,
promoted to Tier 0. The spike proved it tractable (see below); the remaining work
is deciding how the spike lands, then doing the Tier 1 hardware verification once
on the final base.

**Why the fork is cheap to leave.** The vendor did **not** patch core. Of the
entire divergence from the upstream base (`92afc8198a`, 2024-10-29), only two
non-board files differ — `.gitignore` (removes `*.a`, so `libmodule.a` can be
tracked) and a stray `.txt` — plus three submodule bumps. Everything else is
additive vendor boards plus the shared wireless stack. WB32 platform support
(`platforms/chibios/boards/GENERIC_WB32_FQ95XX/`, the `wb32_dfu` bootloader) is
**already upstream**, so no platform fork is needed. Our own authored payload is
9 commits, all in the board + wireless stack + a 4-line `math.py` fix.

**Spike result (branch `split65-overlay` — renamed from `split65-rebase-spike`
when it landed; off `qmk/master` `7a1bbf37c5`, 2026-10-02 — 1,695 commits ahead
of base). The root gitlink points at it. The old vendor line is preserved as
`split65-vendor-overlay` (remote and local, `d68e3152c3`); the two lines are not
mergeable — they diverge from the upstream base
`92afc8198a` with 1,695 upstream commits on the new side — so the spike
**replaces** the payload rather than merging with it. Our nine vendor-line
authored commits remain on `split65-vendor-overlay`; their end-state is already
in the landed branch.**

- Two commits: `11d0bc8` (port the 44 board/shared files) and `35de42afe0`
  (the port fixes). Both signed.
- **Both keymaps build green** (`qmk lint` clean — four cosmetic
  `keyboard.json` redundancy nits).
- Six upstream breakages fixed, all mechanical, all confined to the board +
  shared stack: moved `EECONFIG_USER_DATABLOCK` internal header; legacy GPIO API
  → `gpio_*`; removed `keyboard_protocol` global → `usb_device_state_set_protocol()`;
  removed `SD1_*`→`UART_*` alias layer → define `UART_TX/RX_PIN` +
  `UART_TX/RX_PAL_MODE`; renamed RGB keycodes (no compat aliases); keymap-config
  eeconfig now takes a struct pointer.
- **`nathan` (userspace) needed a manifest.** Master's CLI validates a userspace
  dir only if it carries `qmk.json` (`userspace_version`, `qmk.user_repo.v0`).
  Added `keeb-userspace/qmk.json`; the older vendored CLI ignores the extra file,
  so it is backward-compatible. (The `QMK_USERSPACE` forwarding was fine — the
  manifest was the real cause.)

**Open decisions before this lands:**

- **How the spike lands — DECIDED.** It replaces the vendor payload: the branch
  was renamed `split65-overlay` and the root gitlink now points at it (the old
  line is `split65-vendor-overlay`). Not a merge — the lines share only the
  upstream base.
- **`libmodule.a` / legacy `keyboards/wireless/` — RESOLVED (deleted in the
  spike).** The legacy directory was a pre-hoist duplicate of
  `keyboards/linker/wireless/`: no board included its `wireless.mk`, nothing
  referenced it, and no `-lmodule` appeared in any link. It was the only
  carrier of `libmodule.a` — a stale `ar` archive of `module.o`, `smsg.o`,
  `assert.o` compiled from source we already hold. **Not a blocker:** nothing we
  build ever linked it. Commit `f1ee1f3`; both keymaps rebuild byte-identical.
- **Upstream battery + connection APIs — ADOPTED (on the spike branch).**
  Master's `quantum/battery/` + `drivers/battery/` now back the battery value
  via a `custom` driver (`wls/wls_battery_driver.c`), and `quantum/connection/`
  owns the user-facing host selection, bridged to the vendor `DEVS_*` enum by
  `connection_host_changed_kb()`. The `0xA4` responder stays board-local. Builds
  green. See `docs/FINDINGS.md`, "upstream already ships the battery and
  connection APIs".

**Cost note.** A re-base invalidates any hardware verification done on the vendor
tree, which is exactly why it is now first: do the Tier 1 flash and measurements
on the final base, once.

**Upstream-alignment plan (in anticipation of the eventual merge).** Merging the
wireless/tri-mode stack upstream requires conforming to QMK's contributor
conventions (`docs/contributing.md`), not just building. The work is sequenced
cheapest-first, and **all of it happens on the spike branch** — formatting churn
on 44 vendor-derived files would wreck cherry-pickability against the vendor
overlay, and the spike is already a from-scratch replay. Rationale and the
bespoke-vs-superseded audit are in `docs/FINDINGS.md`, "what stays bespoke, and
why it is not superseded".

1. **Formatting + licensing pass (cheap, do first).** Run `qmk format-c` on our
   authored `.c`/`.h`, `qmk format-json -i` on `keyboard.json`, `qmk format-text`
   on `readme.md`. Add GPL-2.0-or-later SPDX headers to every authored source
   file (a common review-blocker; upstream requires them). Turn mechanical review
   into a no-op.
2. **Naming / hook-convention pass (moderate).** Rename the vendor's
   `wls_*`/`kb_*`/`hs_*` prefixes toward upstream idioms; use the `_kb`/`_user`
   hook suffixes and `xxx_init`/`xxx_task` pairs where core calls them. The
   adopted battery driver (`wls_battery_driver.c`) already conforms — that is why
   it dropped in cleanly; treat it as the template.
3. **Layering — CONFORM to the pending upstream shape (no longer our choice).**
   Upstream PRs already propose the exact layering this project derived:
   **26203** (damex, "2.4 GHz wireless dongle api" — stale-bot-closed, not
   rejected) defines a `drivers/wireless/wireless_2p4ghz.{c,h}` dispatcher with
   weak hooks plus a `host_driver_t wireless_2p4ghz_driver` in
   `tmk_core/protocol/host.c` selected when `active_host ==
   CONNECTION_HOST_2P4GHZ`, enabled by `WIRELESS_2P4GHZ_ENABLE` +
   `WIRELESS_2P4GHZ_DRIVER = custom`; **26207** (damex, OPEN) is the same
   category for the Freqchip fr800x chip; **24365** (tzarc, open draft) is the
   maintainer-sanctioned `host_driver_t` swap. So the target is
   `WIRELESS_2P4GHZ_DRIVER = custom`, with our module stack as **one driver
   behind that API**, not a parallel `keyboards/linker/wireless/` layer. Engage
   `damex` before writing more; cite 26203/26207/24365 in the U1 RFC. See
   `docs/FINDINGS.md`, "upstream is already defining the API we would invent".
4. **`libmodule.a` — RESOLVED, not a blocker.** The prebuilt archive lived only
   in the obsolete `keyboards/wireless/` copy, which no board linked; the legacy
   directory is deleted in the spike, so no vendored binary remains. No design
   work is needed; the module protocol was always open source. See the `## Re-base`
   record for the full autopsy.
