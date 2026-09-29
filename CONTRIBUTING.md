# Contributing

## Layout

Firmware lives in the vendored QMK tree under
`qmk_firmware/keyboards/epomaker/epomaker_split65/`. Host tooling lives in
`host/` and `split65.py`. Documentation lives at the repository root.

## Before committing

1. Lint the firmware and build every keymap:

   ```bash
   cd qmk_firmware
   qmk lint -kb epomaker/epomaker_split65 -km default
   qmk lint -kb epomaker/epomaker_split65 -km nathan
   make epomaker/epomaker_split65:default epomaker/epomaker_split65:nathan
   ```

2. Optionally format C to QMK style (vendor code is intentionally left as-is;
   only run this on files you changed):

   ```bash
   qmk format-c -n <files>          # -n: check only
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

## Tests

Firmware unit tests use QMK's GoogleTest harness under `qmk_firmware/tests/`
and run with `make test:<group>`. Host-side changes should be exercised against
`host/battery_polybar.py`'s pure functions before committing.
