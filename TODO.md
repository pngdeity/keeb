# TODO

## Status

- **The tree now holds the VENDOR firmware, not ours.** It was reverted: the
  board source is vendor `epomaker_split65` at inner-repo commit `9054c880f1`
  plus the `post_rules.mk` `leo/` -> `epomaker/` include-path fix. There is **no**
  battery reporter (`wls/wls_battery.c` absent) and **no** `nathan` keymap — only
  the vendor `default` keymap. Our battery work lives in the old inner repo
  (`.git/modules/qmk_firmware`, branch `split65-battery`) and in
  `/tmp/opencode/pre-vendor-revert/`. Device context and vocabulary:
  `docs/DEVICE.md`.
- The vendor `default` keymap builds to **61320 bytes (`ef88`), md5
  `cf7c31a7361c2a2103bf4035fbac2e22`**. This is the new vendor baseline.
- Both halves enumerate as `342d:e4c6`, manufacturer `LEO` (stock is `MILE`).
- Right half DFU entry used the R_Shift toggle + spacebar-pin short (see
  `docs/HARDWARE.md`); it erased nothing and the firmware took. Key-based DFU is
  still future work (next section).
- **The halves have NOT been reflashed with the vendor `default` build.** They
  currently run the older `nathan` build (63168 bytes md5
  `3d0d47d9737c4209d2a7000cb8909033`).
- **The tree is flat and pruned, and this is all uncommitted.** `qmk_firmware/`
  is no longer a submodule: the gitlink, `.gitmodules` and the stale inner
  `.gitmodules` are gone and its files are ordinary tracked files of the root
  repo. `keyboards/` was pruned to the two this board needs
  (`epomaker/epomaker_split65`, `linker/wireless`); `docs/`, `tests/`, `users/`
  and unused `lib/` trees were deleted, but `layouts/` and `lib/lufa` had to be
  **restored** — the prune wrongly removed them and the build failed without
  them. `lib/{chibios,chibios-contrib,printf,fnv,lib8tion,lufa}` are kept whole.
- The firmware fix commit in the old inner repo is `ff1e6e1d27` and is
  **unsigned** (see Tier 0 item 2).

## Priority order

Ordered by what unblocks what. Rationale and detail for each item follow in the
sections below.

**Tier 0 — blockers / one-way doors (do first, cheap, affect everything after):**

1. **Verify the pruned tree still builds (byte-identical acceptance test).** The
   tree was pruned from `qmk_firmware/` (1040 keyboard dirs -> 2, `docs/`,
   `layouts/`, `tests/`, `users/` and the unused `lib/` trees removed) and
   de-submoduled, but **no build has been run since**. Run, with the user's
   go-ahead (it costs host compute):

   ```sh
   cd qmk_firmware
   make clean
   make epomaker/epomaker_split65:default
   ```

   Accept only **61320 bytes (`ef88`), md5 `cf7c31a7361c2a2103bf4035fbac2e22`**.
   A byte-identical artifact is the proof the prune removed nothing the build
   needs. Anything else means a pruned path was load-bearing and must be restored
   — this already happened once: `layouts/` and `lib/lufa` were wrongly pruned and
   had to be restored before the build would run. Do this before committing the
   flatten, so a broken prune is not recorded.

2. **Re-sign the unsigned firmware commit.** The last `qmk_firmware` commit
   (`ff1e6e1d27`, *fix(epomaker/epomaker_split65): single source of truth for
   default lighting*) was committed with `--no-gpg-sign` because GPG signing
   failed in the non-interactive agent shell: the key's passphrase is not
   cached for signing, and `~/.local/bin/pinentry-wrapper` falls back to
   `pinentry-qt`, which the scrubbed gpg environment denies (`Inappropriate
   ioctl for device` / `Timeout`). Re-sign it from a real terminal, e.g.
   `git commit --amend -S --no-edit` inside `qmk_firmware/`, or re-commit.
   Verify with `git log -1 --format='%G?'` -> `G`.

3. **Commit the outstanding work.** Everything below is built on an uncommitted
   tree (flattened root repo: the prune, the de-submodule, the vendor revert,
   `docs/DEVICE.md` (new), `docs/HARDWARE.md`, `README.md`, `CONTRIBUTING.md`,
   `TODO.md`). Nothing else should be verified before this is recorded, or the
   verification is against an unreproducible state.
4. **Fix defect 3** (`find_raw_hid_interface()` picks the wrong interface) and
   **contain it in `split65.py check`.** This is a prerequisite for the 2.4 GHz
   probe: with keyboard and dongle both attached, the probe reads the keyboard's
   USB interface, so any 2.4 GHz measurement taken first is invalid.
5. **Decide and apply the critical ergonomics changes** (a pull-forward from
   Tier 3, abbreviated to only the items that are cheap and that a flash would
   otherwise force you to repeat):
   - **`QK_BOOT` / `EE_CLR` placement.** `EE_CLR` sitting at the Backspace
     position on a layer is a genuine footgun (an accidental hold wipes
     settings). Move it somewhere deliberate. One-line change, and it must be in
     the same flash as everything else.
   - **Decide the battery-indicator question.** With a uniform white fill the
     indicator is the only LED that differs; decide whether that single-LED
     exception stays, is made more prominent (it is the only per-half charge
     readout), or is disabled — and do it now, because it is the same
     `config.h`/keymap edit and the same flash.
   - **Decide whether to trim the compiled-in animation list**
     (`keyboard.json` `rgb_matrix.animations`, ~44 entries, still reachable via
     `RGB_MOD`). If trimming, it must be before the flash.
   The rest of the UX audit (layer ergonomics, mode-switch discoverability,
   legends) stays in Tier 3 — it needs thought, not a flash.

**Tier 1 — the deliverable (the project exists for this):**

6. **Reflash both halves** with the current artifact (default-lighting change plus
   the Tier 0 decisions above). Cheap, and it also gives a clean baseline for the
   measurement below. Do it *after* all the cheap pre-flash decisions are in, so
   the flash is done once.
7. **2.4 GHz: capture a real percentage** (the decisive test; needs the user at
   the keyboard). Depends on 4 and 6.
8. **2.4 GHz: confirm `chg` moves `1 -> 2` while charging.** Same session as 7.
9. **Decide and implement the honesty fix for the fake 100** (defect 1).
   Depends on 7 — you need to know what a real reading looks like before choosing
   how to represent "unknown".

**Tier 2 — feature completeness (in scope, not yet probed):**

10. **Probe Bluetooth at all**, then update `docs/PROTOCOL.md` and `README.md`.
    Independent of Tier 1 except that it wants a committed, fixed host tool (4).
11. **Wireless-while-charging investigation** (`## Other`). Independent; needs
    hardware and the user.

**Tier 3 — quality / ergonomics (valuable, not blocking):**

12. **Firmware unit tests** for the pure battery helpers. Best done after 7/9 so
    the tests encode settled semantics, not the current fake-100 behaviour.
13. **Key-based right-half DFU.** Removes the case-opening procedure. Only worth
    doing if the physical short is a real pain point; the short stays documented
    as the recovery path regardless.
14. **The rest of the UX / usability review** (whole section below) — layer
    ergonomics, held-modifier comfort, mode-switch discoverability, legends.
    Largest, most subjective; depends on 9 and 12 for what is even possible.

**Tier 4 — long-horizon, high-cost, low-urgency:**

15. **Re-base onto newer upstream QMK.** ~4.5 months of upstream but no wireless
    stack; invalidates all hardware verification and would re-do 6-8. Do not
    start before Tier 1 is closed and recorded.

**Dependency notes (why the order is not free):**

- 1 blocks the flatten commit: a broken prune must not be recorded.
- 2 blocks the honest history: the firmware fix is currently unsigned.
- 4 blocks 7/8/10 (interface selection is the read path).
- 6 must come after 5 so the flash is done once, and before 7 so a mid-measurement
  reflash cannot invalidate the result.
- 3 blocks everything in the sense that unverified work cannot be honestly
  reported; it is a one-way door on a *public* repo.
- 5 must precede 6: every one of those decisions changes bytes that get flashed.
- 15 invalidates 6-9, so it must come last or not at all.

## Outstanding verification (the deliverable is not yet proven)

The host can read a report, but **no real battery percentage has ever been
observed**. Until the items below are done, treat every displayed value as
unverified.

- [ ] **Verify the pruned tree still builds** (Tier 0 item 1): `make clean && make
      epomaker/epomaker_split65:default` from `qmk_firmware/` must yield **61320
      bytes, md5 `cf7c31a7361c2a2103bf4035fbac2e22`**. A different artifact means
      the prune changed something load-bearing (this already happened once: see
      the Status note about `layouts/` and `lib/lufa`).
- [ ] **Re-sign the unsigned firmware commit** (Tier 0 item 2): `ff1e6e1d27` was
      made with `--no-gpg-sign`; re-sign from a real terminal.
- [ ] **Commit the outstanding work** (Tier 0 item 3): the flatten, prune,
      doc restructure, `docs/DEVICE.md` and `AGENTS.md` are all uncommitted.
- [ ] **Fix defect 3** (`find_raw_hid_interface()` picks the wrong interface) and
      cover it in `split65.py check`. **Do this before measuring** — it is the
      read path, and with keyboard and dongle both attached the probe would
      otherwise read the keyboard's USB interface.
- [ ] **Flash both halves with the vendor `default` build** and confirm they
      enumerate with manufacturer **`MILE`-vs-`LEO` consistency** and that the
      battery raw HID command `0xA4` is **absent** (vendor has no responder).
      Left via Esc-hold, right via the toggle + spacebar-pin short; see
      `docs/HARDWARE.md`.
- [ ] **2.4 GHz: capture a real percentage.** Every `100` seen so far is the
      module's compile-time init constant (defect 1). The radio path is the only
      transport known to populate `md_info.bat`, so this is where the first real
      number must come from. Record the observed value and raw bytes in
      `docs/FINDINGS.md`.
- [ ] **2.4 GHz: confirm the value changes while charging.** Re-run the probe with
      a cable in and watch `chg` go `1` -> `2` (full).
- [ ] **USB: decide and implement the honesty fix for the fake 100** (defect 1) —
      this is the first real firmware-writing task and needs the battery work
      restored to the tree first. The report must not claim `100%` when the value
      was never refreshed.
- [ ] **Bluetooth: probe the transport at all.** Unknown whether the BT link
      exposes the raw HID collection (`0xFF60`/`0x61`) and whether `*md_getp_bat()`
      is populated over BT. If raw HID is absent, the BLE Battery Service
      (`0x180F`/`0x2A19`) fallback in `host/battery_polybar.py` is the path.
      Pairing is interactive, so the user must run `bluetoothctl`. **Update
      `docs/PROTOCOL.md`** and `README.md` once known.

### Unmeasured device facts (fill into `docs/DEVICE.md`)

`docs/DEVICE.md` was written from `keyboard.json` and the product photographs.
These facts are **not yet proven** and must be measured before the doc claims
them:

- [ ] **Which of `P2`/`P3` on the right half is the host data port vs the charge
      port.** Firmware has one cable-detect pin (`A7`) and cannot tell them
      apart; the roles in `DEVICE.md` are provisional.
- [ ] **Confirm the current master/slave assignment** with the cable in the right
      half's `P2` — record which half reports as master.
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

Fix options (not yet chosen): have `kb_battery_percent()` return a sentinel
meaning "unknown" instead of a fake 100 when the value has never been refreshed,
and/or retry `md_inquire_bat()` more aggressively.

### 2. The right (slave) half cannot be woken by its own keys

Documented vendor behaviour, confirmed in source:

- `lpwr_exti_init()` (`keyboards/linker/wireless/lpwr_wb32.c:68-112`) arms the
  matrix row/col lines as edge events before `WB32_STOP_MODE`, and the callback
  (`lpwr_wb32.c:34-56`) maps them to `LPWR_WAKEUP_MATRIX`.
- The board's `lpwr_stop_hook_pre()` (`wls.c:191-201`) arms the wake cause as
  `LPWR_WAKEUP_UART`, and `lpwr_stop_hook_post()` (`wls.c:204-216`) only accepts
  `LPWR_WAKEUP_USB` and `LPWR_WAKEUP_CABLE`. Any other cause (including
  `MATRIX` from a keypress) falls to `default:` and returns straight to
  `LPWR_STOP`.
- The mode-switch and cable events that *are* accepted are set in
  `palcallback_cb()` (`wls.c:168-185`), and the switch lines are only armed on
  the master (`if (is_keyboard_master())`, `wls.c:112/:124/:134`).

**Wake the right half by:** toggling its 2.4 GHz/BT mode switch, or unplugging and
replugging its USB cable. Keys will not do it; that is by design (the master
wakes the slave over the inter-half UART).

### 3. Host tooling picks the wrong raw HID interface

`host/battery_polybar.py:find_raw_hid_interface()` returns the first
`hid.enumerate()` entry matching usage page `0xFF60` / usage `0x61`. When both the
keyboard's own USB interface (interface 1) and the 2.4 GHz dongle (interface 2)
are attached, it grabs the keyboard's USB interface, so the module reports USB
while the user is on 2.4 GHz. Fix: prefer interface 2 (or the `2.4G Dongle`
product string) when several match.

`split65.py check` should validate this assumption too, since it is the tool a
user is told to run; today it does not exercise raw HID selection at all.

## Right-half DFU without hardware shorting

Goal: let the right half enter the WB32 DFU bootloader by holding a key, like the
left half, instead of opening the case and shorting the spacebar switch pins
(remove `R_Shift`, toggle the hidden switch, short the two holes where the
spacebar switch feet insert, plug USB-C).

Rationale / evidence:

- `QK_BOOT` is handled in the application firmware at
  `qmk_firmware/keyboards/epomaker/epomaker_split65/epomaker_split65.c:1059`:
  it calls `eeconfig_disable()` then `bootloader_jump()`. `bootloader_jump()` is
  a **local MCU operation** and the handler is **not** gated on
  `is_keyboard_master()`, so a `QK_BOOT` key pressed on the right half should jump
  *that half* into its own bootloader.
- Both halves run identical firmware, so adding `QK_BOOT` to the keymap adds it
  to both. The keymap maps `QK_BOOT` at Fn row 1 col 0 (`Fn+1`).
- Esc-hold (bootmagic) does **not** work on the right half today; that asymmetry
  is why the physical short is currently required.

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
anything) to change in the `nathan` keymap (parked outside this tree — see
Status) and whether the vendor defaults deserve an upstream report.

Three of these were pulled forward into **Tier 0, item 5** because they are
cheap and must land in the same flash as the default-lighting change: the
`QK_BOOT`/`EE_CLR` placement, the battery-indicator-vs-fill decision, and whether
to trim the compiled-in animation list. The remainder stay here.

- **Charging/battery LED placement.** The only per-half-charge renderer is the
  master-only soft indicator at `HS_MATRIX_BAT_SOFT_INDEX` (battery work, parked
  — right half, bottom row, fourth from the right). Question whether that is
  discoverable at all: it
  sits on the *opposite* half from the half it describes, is master-only, and is
  invisible when RGB brightness is zero. Consider a better location or a
  dedicated indicator, and whether the level colours are distinguishable.
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
  it should be more prominent given it is the only per-half charge readout.
- **Connection-mode switching.** `KC_BT1`/`KC_BT2`/`KC_BT3`/`KC_2G4` (Fn layer,
  row 1) and the physical mode switch both exist. Question the discoverability of
  the keycodes, whether the currently-selected channel is visible, and whether
  the switch-and-keys interaction is coherent.
- **Keycap legends vs matrix.** Legends do not reliably match matrix positions
  (see `docs/HARDWARE.md`), so any mapping work must identify keys positionally
  ("right half, bottom row, fourth from the right"), never by legend.
- **`QK_BOOT` / `EE_CLR` placement.** `QK_BOOT` at Fn row 1 col 0 (`Fn+1`) and
  `EE_CLR` at Fn row 1 col 13 (`Fn+Backspace`) are easy to hit by accident;
  question whether destructive actions are placed safely, especially given
  `EE_CLR` sits on the Backspace key position.
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

## Other

- **Wireless while charging: can the two coexist?** Source reading is
  inconclusive. The physical three-position switch appears authoritative
  (`hs_modeio_detection()` in `wls/wls.c` reads it every scan and forces
  `DEVS_USB` when in the USB position; `wls_process_long_press()` makes the
  `KC_BT*`/`KC_2G4` keycodes no-ops unless the switch already reports
  BT/wireless). Nothing found gates wireless operation on `charging_state`, so
  plugging a cable with the switch on BT/2.4 GHz *should* leave the keyboard
  wireless while charging — but this is unverified on hardware, and the
  cable-insert auto-switch in `housekeeping_task_user()` (a policy choice, not a
  hardware limit) deliberately moves to USB on cable insert, which would defeat
  it. Also unknown whether VBUS presence disturbs the module UART or the radio
  link. Investigate: with the switch on 2.4 GHz, plug a charging cable and
  confirm the keyboard stays wireless and the level still updates; decide
  whether the cable-insert auto-switch should be suppressed while the switch is
  in a wireless position. Document the verdict in `docs/HARDWARE.md`.

- Firmware unit tests for the pure battery helpers (`kb_battery_percent`,
  `kb_charging_state`, `kb_transport_byte`) — deferred pending the hardware probe.
- Bluetooth transport: confirm whether the BT link exposes the raw HID
  collection (`0xFF60`/`0x61`) and whether `*md_getp_bat()` is populated over BT;
  BLE Battery Service `0x180F`/`0x2A19` is the host fallback.
- Consider re-basing onto a newer upstream QMK. This tree is a 1-commit
  squashed vendor snapshot (`hangshengkeji/qmk_firmware` `tri-mode`,
  2026-01-20); a full-history upstream tree (`qmk/qmk_firmware` master) is
  ~4.5 months newer but lacks the wireless stack. Any re-base would require
  rebuilding, re-flashing **and** re-verifying the battery work on hardware.
  See the consolidation note in `docs/FINDINGS.md`.
