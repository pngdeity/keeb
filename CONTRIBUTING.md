# Contributing

## Layout

Firmware lives in the `qmk_firmware/` submodule under
`qmk_firmware/keyboards/epomaker/epomaker_split65/` (with the wireless stack at
`qmk_firmware/keyboards/linker/wireless/`). Host tooling lives in `host/` and
`split65.py`; build wrappers in `bin/`. Documentation lives in `docs/`, except
`README.md`, `TODO.md`, `CHANGELOG.md`, `AGENTS.md` and this file at the root.

## Where to write what

- **`docs/DEVICE.md`** — what the device is: physical layout, ports, modes of
  operation, accessories, host machine, and the nomenclature for naming parts.
  Read this before referring to a half, a port, or a key.
- **`docs/HARDWARE.md`** — immutable physical/electrical facts learned by
  measuring the keyboard (USB IDs, interfaces, DFU entry, sleep/wake, link
  power). Record anything you discover by trial and error here, not in source
  comments.
- **`docs/PROTOCOL.md`** — the wire format of the `0xA4` battery command.
- **`docs/FINDINGS.md`** — research narrative, design decisions and their
  rationale.
- **`TODO.md`** — outstanding work and known defects. **This is the live record**;
  read it first and update it rather than scattering status elsewhere.
- **`docs/DEPENDENCIES.md`** — toolchain, flashing procedure and host
  dependencies.

## Before committing

1. Lint the firmware and build all keymaps (from the repo root):

   ```bash
   ./bin/qmk lint -kb epomaker/epomaker_split65 -km default
   ./bin/make epomaker/epomaker_split65:all
   ```

   The submodule holds the vendor `default` keymap plus our board source; the
   `nathan` keymap is in the sibling userspace repo (`../keeb-userspace/`) and
   `bin/make` supplies the `QMK_USERSPACE` it needs.

2. Optionally format C to QMK style (vendor code is intentionally left as-is;
   only run this on files you changed):

   ```bash
   ./bin/qmk format-c -n <files>     # -n: check only
   ```

   `qmk format-python` requires `yapf`, which is not installed here; `qmk
   format-text` has no `-n` (check-only) flag. Do not reformat vendored QMK code
   wholesale — it predates this formatter and such a change would desync us from
   upstream.

3. Check for stray whitespace: `git diff --check`.

4. Confirm no build artifacts are staged (`*.bin`, `.build/`).

## Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>[optional scope]: <description>

[optional body]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`,
`ci`, `build`, `revert`. Subject ≤72 characters; wrap the body at 72. Breaking
changes: append `!` after the type/scope and add a `BREAKING CHANGE:` footer.

Commits must be signed (`git commit -S`), and `git diff --check` must be clean.

## Code style

- **C**: QMK conventions — 4-space indent, modified One True Brace Style,
  always include optional braces, `#pragma once` in headers, license header on
  every source file. Run `qmk format-c`.
- **Python**: QMK/PEP 8 — 4-space indent, docstrings on all functions,
  printf-style format strings, no type annotations. Formatter is `yapf` via
  `qmk format-python` (see the caveat above — `yapf` is not installed here).
- **Headers**: every source file starts with two lines:

  ```
  // Copyright <year>
  // SPDX-License-Identifier: <SPDX-ID>
  ```

  Firmware files derived from QMK use `GPL-2.0-or-later`. Project-authored
  scripts and docs use `Apache-2.0`. See `LICENSE`.

## Inline annotations

Tag annotations in comments; `FIXME`, `BUG`, and `HACK` must not be merged.

| Tag | Use |
|-----|-----|
| `TODO` | Planned work |
| `FIXME` | Broken behavior |
| `HACK` | Fragile workaround |
| `BUG` | Active defect |
| `NOTE` | Informational, no action |

Format: `// TODO: imperative description`.

## Traps in this tree

Verified gotchas that cost time if rediscovered. Check here before debugging.

- **`ENCODER_MAP_ENABLE` is not set.** The keymap ships an `encoder_map[]`, but
  the macro is never defined, so it is dead code and never linked. Enabling the
  encoder map means adding `ENCODER_MAP_ENABLE = yes` to the keymap's
  `rules.mk`.
- **`RGB_MATRIX_DEFAULT_*` does not apply to a used keyboard.** It is only
  consumed when the RGB EEPROM is blank. Both halves carry vendor-persisted RGB
  state, so the defaults are inert unless the keymap also calls
  `rgb_matrix_mode()` / `rgb_matrix_sethsv()` at init. The board
  `keymaps/default/keymap.c` does; the `nathan` keymap uses the `*_noeeprom()`
  variants instead (a boot-time override, not a stored value).
- **A raw HID write through hidapi must be 33 bytes** (Report ID `0x00` + the
  32-byte report). A bare 32-byte write is accepted and silently never answered.
  See `docs/HARDWARE.md`.
- **`keyboard.json` is formatted by `qmk format-json`**, not by hand. Hand
  editing drifts from QMK's canonical `InfoJSONEncoder` output and creates a noisy
  diff.
- **`qmk format-python` needs `yapf`, which is not installed here**, and
  `qmk format-text` has no `-n` check flag.
- **Do not run `doas` from an agent context.** An unanswered prompt locks the
  account; `split65.py flash` therefore requires a human.

## Tests

Firmware unit tests use QMK's GoogleTest harness under `qmk_firmware/tests/` and
run with `./bin/make test:<group>`. **This does not work in the current
submodule**: `lib/googletest` is deliberately not initialized (the submodule is
kept thin and upstream-dependent), so `make test` cannot compile. Initialize it
with `git -C qmk_firmware submodule update --init lib/googletest` before relying
on the harness. Host-side changes should be exercised against
`host/battery_polybar.py`'s pure functions before committing.
