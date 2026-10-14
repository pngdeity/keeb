# The `0xA4` golden vector

The `0xA4` raw-HID report is written by the firmware (C) and read by the host
tool (`host/battery_polybar.py`, Python). Nothing links the two, so the byte
layout is a **contract by convention**: if an index moves on one side, the other
keeps parsing without error and silently reports the wrong field. This is the
cross-language instance of the drift class recorded as F7 in
`docs/AUDIT-fcis.md` (two statements of one fact, with nothing that fails when
they diverge).

The fix is one checked-in vector asserted by both sides. There is no shared
header to generate from, and a generated header would add a build step for a
23-byte layout; a fixture both sides assert is smaller and just as binding.

## The vector

23 bytes, printed in `host/battery_polybar.py` as `GOLDEN_VECTOR`:

| Idx | Value | Field |
| --- | --- | --- |
| 0 | `0xA4` | `KB_BATTERY_CMD_GET` — the reply echoes the command |
| 1 | `0x51` | level 81% |
| 2–3 | `0x00` | reserved |
| 4 | `0x01` | charge = charging |
| 5 | `0x02` | transport = bluetooth |
| 6 | `0x07` | model id |
| 7 | `0x04` | host = `BLUETOOTH` |
| 8 | `0x03` | BT sub-index 3 (`BT4`) |
| 9 | `0x12` | module firmware version |
| 10 | `0x02` | module state = `CONNECTED` |
| 11–20 | — | the `wls_diag_t` block (see below) |
| 21 | `0x07` | boot code amber = 7 (stage `RSTCAUSE`) |
| 22 | `0x05` | boot code white = 5 (bit 4 = `PORRSTF`) |

The diag block (bytes 11–20) is `{0x02, 0x04, 0x04, 0x03, 0x01, 0x02, 0x01,
0x00, 0x01, 0x10}` — switch `BT`, devs `DEVS_BT4`, host bluetooth, boot count 3,
USB line up, link connected, pins `C14=1 C15=0 B9=1`, reset cause bit 4.

**Bytes 23–34 — the jump journal (`wls_jump_journal`, `KB_BATTERY_IDX_JUMP 23`).**
The evidence a boot leaves behind so a later read can tell whether *our* `QK_BOOT`
path ran (the magic word itself is cleared before our code runs; see
`docs/AUDIT-fcis.md` "Stage 4"). Encoded by `jump_journal_logic`:

| Idx | Field | Vector | Meaning |
| --- | --- | --- | --- |
| 23 | presence | `0x01` | `WLS_JUMP_JOURNAL_MAGIC` held (`"JMPR"`) |
| 24 | version | `0x01` | `WLS_JUMP_JOURNAL_VERSION` |
| 25 | generation | `0x09` | jumps performed since power-on |
| 26 | stage | `0x00` | `wls_boot_code_t.stage` at the jump |
| 27 | code | `0x00` | `wls_boot_code_t.code` at the jump |
| 28–31 | reset_cause | `0x10 00 00 00` | `RSTSTAT` bits at the jump (LE) |
| 32–34 | uptime_ms | `0xD2 0xB4 0x00` | `timer_read32()` at the jump (LE; 0x00B4D2) |

A presence byte of `0x00` means no jump has been recorded since power-on — the
case that exonerates the keymap path when a `dfa0` window is seen.

The values are chosen to be non-trivial (no field equals its index, several are
zero) so a moved index changes the decode.

## Where each side asserts it

- **Firmware:** `qmk_firmware/tests/wls_diag/wls_diag_tests.cpp` —
  `golden_vector_diag_block_matches_the_host_fixture` decodes bytes 11–20 and
  re-encodes them, so a moved index in `wls_diag_encode`/`_decode` fails. The
  boot pair (21–22) is asserted in
  `qmk_firmware/tests/boot_code_logic/boot_code_logic_tests.cpp` as
  `golden_vector_boot_code_pair_matches_the_host_fixture`, because
  `tests/wls_diag/test.mk` compiles only `diag_logic.c`. The jump journal
  (23–34) is asserted in
  `qmk_firmware/tests/wls_jump_journal/wls_jump_journal_tests.cpp` as
  `golden_vector_journal_block_matches_the_host_fixture`.
- **Host:** `python3 host/battery_polybar.py --self-check` decodes the vector and
  compares every field to `GOLDEN_EXPECTED`; it needs no hardware. Wired into CI
  (`.github/workflows/build.yml`, "Check the 0xA4 golden vector (host side)").

## Maintaining it

The vector is a fixture, not a source of truth: the source is
`wls/wls.h` (`KB_BATTERY_IDX_*`), `wls/diag_logic.h` (the diag field order),
`wls/boot_code_logic.h` (the boot pair), and `wls/jump_journal_logic.h` (the
journal block). When the layout changes on purpose, update the vector in all the
places in the same commit. A change to only one side is exactly the defect this
exists to catch.

**A real drift this found:** `BOOT_STAGE_NAMES` in `host/battery_polybar.py` held
six stages against the firmware's eight (`BOOTCOUNT` and `RSTCAUSE` were missing),
so the host would print `stage=?` for precisely the readings the boot instrument
exists to produce. Completed to all eight when the vector was added.
