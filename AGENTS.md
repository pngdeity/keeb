# AGENTS.md

Working rules for this repository. Read this first, then `TODO.md` (the live
record). See `README.md` for the reading order and layout.

## What this project is

Firmware and host tooling for one keyboard: the EPOMAKER Split65 (WB32FQ95,
wb32-dfu bootloader). The firmware adds raw HID battery reporting (`0xA4`) over
USB, the 2.4 GHz dongle and Bluetooth. The deliverable is a `.bin` flashed onto
both halves.

## Environment traps

- **Never run `doas`, `split65.py flash`, or `wb32-dfu-updater_cli`.** `flash`
  calls `doas` and prompts with `input()`; an unanswered `doas` prompt locks the
  user's account. Flashing is a human action — print the command and stop.
- **Never run `sudo`, `su`, `pkexec`.** `doas` is the only elevation tool here and
  it is user-only.
- **Building is expensive.** Do not run `make` (or `make clean`) without the
  user's go-ahead. It is a full cross-compile.
- **Commit signing needs a terminal.** `git commit -S` fails in
  non-interactive shells: the GPG pinentry wrapper falls back to `pinentry-qt`,
  which the scrubbed gpg environment denies. Commits require signing; if signing
  fails, stop and ask the user rather than committing unsigned.
- Tooling: `rg` not `grep`, `fd` not `find`, `bun` not `npm`, `uv` not `pip`,
  `pacman`/`yay` for packages. Temp files go in `/tmp/opencode/`.

## Build, lint, flash

`qmk_firmware/` is a **pinned submodule** (branch `split65-overlay`, rebased onto
`qmk/qmk_firmware` master); the board source inside it carries our authored
changes. The personal `nathan` keymap lives
**outside** the tree, in a sibling userspace repo (`../keeb-userspace/`).

**Use the project-local wrappers — never a bare `make` or `qmk`:**

```sh
./bin/make epomaker/epomaker_split65:default   # stock (vendor) keymap
./bin/make epomaker/epomaker_split65:nathan    # personal keymap (userspace)

./bin/qmk lint -kb epomaker/epomaker_split65 -km default
./bin/qmk hello
```

`bin/make` handles both requirements automatically: it puts `bin/` first on
`PATH` (so the Makefile's `QMK_BIN := qmk` finds the project CLI, not the older
packaged one) and passes `QMK_USERSPACE="../keeb-userspace"` to make. It `cd`s
into `qmk_firmware/` itself, so run it from the project root.

**Why `QMK_USERSPACE` is needed:** the tree's Makefile reads `user.overlay_dir`
from the qmk config but does **not** forward it into the inner
`build_keyboard.mk` submake, and `qmk list-keymaps` / `qmk compile` do not
consult userspace at all. Without the variable, `make ...:nathan` resolves only
`default` and fails with `No rule to make target 'nathan'`. Full detail in
`docs/DEPENDENCIES.md`.

`qmk lint` needs `jsonschema`, `hjson`, `dotty_dict`, `milc` (installed in the
project `.venv`). `qmk format-c` is a wrapper over `clang-format`;
`qmk format-json` is self-contained Python. `qmk format-python` needs `yapf`,
which is **not** installed; `qmk format-text` has no `-n`.

## The qmk CLI and the make wrapper

Use the project-local wrappers (no system install needed):

```sh
./bin/qmk hello
./bin/qmk compile -kb epomaker/epomaker_split65 -km default
./bin/make epomaker/epomaker_split65:nathan
```

- **`bin/qmk`** runs `.venv/bin/python` (project venv, Python 3.12) against the
  submodule's `lib/python/qmk`, with `ORIG_CWD` set and `PYTHONPATH` pointing at
  the tree. It also forces `sys.argv[0] = "qmk"` **before** importing milc —
  milc derives its program name (and therefore its config file
  `~/.config/qmk/qmk.ini`) from `argv[0]`, so without this it would look for
  `-c.ini` and never see `user.overlay_dir`.
- **`bin/make`** is a thin wrapper over the real `make` that exports
  `QMK_USERSPACE` (both as an environment variable and as a make command-line
  variable) and puts `bin/` on `PATH`. It resolves the real `make` path
  *before* modifying `PATH`, so it does not recurse into itself. If the sibling
  userspace directory is absent (e.g. in CI) it blanks `QMK_USERSPACE`, so the
  tree does not try to copy firmware into a missing directory.
- The userspace repo is a **sibling** of this repo (`../keeb-userspace/`), not a
  child; `bin/make` computes it that way.
- Create the venv once with `uv venv` and `uv pip install --python
  .venv/bin/python -r qmk_firmware/requirements.txt`. `.venv/` is gitignored.
- **The system/PyPI `qmk` (1.2.0) is insufficient** — it lacks `compile`, `flash`,
  and the `userspace-*` commands. Upstream's CLI only advanced inside the tree,
  so the tree's copy is the modern one.

Flashing (human only): `./split65.py flash`, or manually
`wb32-dfu-updater_cli -t -s 0x08000000 -D <bin>` then `-R`.

## CI

`.github/workflows/build.yml` builds `epomaker/epomaker_split65:all` on every
push to `main`, every PR, and on demand, so a broken board source is caught
without a human build. It uses QMK's official image
(`ghcr.io/qmk/qmk_cli:latest`), checks out this repo **with submodules**,
installs the tree's `requirements.txt`, runs `./bin/make`, and also enforces
`git diff --check` and canonical `qmk format-json` output.

**Toolchain note:** the container ships its own `arm-none-eabi-gcc` (currently
15.2.0), which can differ from the host's (16.2.0). A different compiler version
produces a **different `.bin` size and md5 for identical source**, so the CI
artifact is not byte-comparable to a local build. CI's job is "does it build",
not "is it byte-identical to the host".

## Software traps in this tree

The tree holds the vendor board **plus our battery changes**, committed inside
the `qmk_firmware` submodule (branch `split65-overlay`). The personal `nathan`
keymap is **not** in the tree — it lives in the sibling userspace repo
(`../keeb-userspace/`).

- **`keyboard.json` is the source of truth for defaults**, not `config.h`.
  Defining e.g. `RGB_MATRIX_DEFAULT_*` in `config.h` when `keyboard.json` already
  sets the same key makes `qmk lint` warn on the duplicate. Edit `keyboard.json`
  and run `qmk format-json -i` on it.
- **`ENCODER_MAP_ENABLE` is not set**, so the `encoder_map` array in the keymap
  is compiled out (dead code). Enabling the feature is a one-line change, but
  nothing currently uses it.
- **`RGB_MATRIX_DEFAULT_*` in `config.h` only applies to a blank EEPROM.** The
  halves carry saved RGB state, so defaults must be re-applied at
  `keyboard_post_init_user()` to take effect.
- **hidapi writes to the raw HID interface must be 33 bytes** (leading Report ID
  `0x00` + the 32-byte report). A bare 32-byte write is accepted and silently
  never answered.
- **`qmk_firmware/` is a submodule**, pinned to `pngdeity/cleave-keeb` branch
  `split65-overlay`. Board edits are commits inside it; the root repo pins the
  result by gitlink, so a board change needs a matching root bump.
- **Editing `keyboard.json` with a text tool reflows the whole file.** The `edit`
  tool rewrites every `rgb_matrix.layout` and `rotary` entry (hundreds of lines
  of churn for a one-value change). Use `qmk format-json -i` for structural edits
  and a line-targeted edit (e.g. `perl -i -pe`) for single values.

## Where to write what

- What the device is, and how to name its parts -> `docs/DEVICE.md`
- Measured hardware facts -> `docs/HARDWARE.md`
- Wire format -> `docs/PROTOCOL.md`
- Toolchain, flashing, host deps -> `docs/DEPENDENCIES.md`
- Why the design is as it is -> `docs/FINDINGS.md`
- Work, defects, status -> `TODO.md` (the live record)

## Code intelligence

OpenCode V2 has no built-in LSP. Use the `serena` MCP server for symbol
navigation, refactoring and per-file diagnostics; `cclsp` is the fallback for
file types Serena cannot serve. After editing source, run diagnostics and fix
reported errors. Do not guess with grep/read when a symbol tool applies.

**C/C++ (the firmware tree) needs a compile database.** Without one, clangd
reports bogus errors on every C file (`unknown type name 'bool'`, undeclared
`MATRIX_*` macros). Generate it with the project wrapper:

```sh
./bin/compiledb nathan     # or: ./bin/compiledb default
```

This emits `qmk_firmware/compile_commands.json` (and a copy at the userspace
root), then does a real build so the *generated* headers (`info_config.h`)
exist at rest — QMK's own `generate-compilation-database` does a `make clean`
first, which removes them and defeats clangd. Both the DB and clangd's cache
are gitignored; re-run after a clean checkout or a build-config change.

Which tool serves what here:

- **Serena** (`cpp` language server, bundled clangd 19) is rooted at this repo
  and serves the **in-tree firmware** under `qmk_firmware/`. It is the tool for
  symbol navigation there — `get_symbols_overview`, `find_symbol`,
  `find_referencing_symbols` all work on the C tree.
- **cclsp** (system clangd 23) serves C **and** the userspace keymap under
  `../keeb-userspace/`, which is *outside* Serena's workspace (a sibling repo,
  not a child). Prefer cclsp for the `nathan` keymap; prefer Serena for the
  firmware.
- `~/.config/clangd/config.yaml` force-includes a tiny `bool`/`true`/`false`
  shim so clangd parses ChibiOS's `chtime.h`. This is user-level and touches no
  repo file.

**Known cclsp limitation:** `find_workspace_symbols` queries only the *first*
running language server regardless of the query's language, so it returns
nothing in a multi-language project. Use Serena's `find_symbol` or cclsp's
per-file tools (`get_diagnostics`, `find_definition`) instead. cclsp's `hover`
also times out (>30 s) on cold firmware files; Serena's symbol tools do not.
