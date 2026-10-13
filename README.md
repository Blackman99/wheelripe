<p align="center"><img src="site/logo.svg" width="96" alt="wheelripe logo: a cheese wedge with one open hole"></p>

# wheelripe

**Before you move to a new Python, find every dependency that has no wheel for it yet — and the version bump that fixes each one.**

Python 3.15 shipped on 2026-10-09. Moving a project means finding out, package by package, whether each locked dependency has a `cp315` (or `abi3`, or free-threaded `cp315t`/`abi3t`) wheel for *your* platforms. Today that means upgrading, watching `pip`/`uv` fall back to an sdist and fail on a missing compiler or header, fixing one, and repeating — or hand-checking the PyPI JSON API like [harlequin#1119](https://github.com/tconbeer/harlequin/issues/1119) and [dynamic-des#40](https://github.com/jaehyeon-kim/dynamic-des/issues/40) do. `pip install --only-binary=:all: --python-version 3.15` stops at the first failure and never tells you which newer release would work.

wheelripe reads your lockfile, asks the index for every release's file list, and applies the same tag rules pip does (PEP 425/600/656/803 — CI cross-checks every verdict against pip on the real PyPI) for every target platform at once.

![wheelripe checking a requirements file for CPython 3.15](site/demo.gif)

## Install

```bash
uvx --from git+https://github.com/Blackman99/wheelripe wheelripe          # one-off
pipx install git+https://github.com/Blackman99/wheelripe                   # or keep it
```

Not on PyPI yet; the [release](https://github.com/Blackman99/wheelripe/releases/latest) has a wheel you can `pip install` directly.

## Use

```bash
wheelripe                               # auto-detects uv.lock / pylock.toml / poetry.lock / requirements.txt / pyproject.toml
wheelripe uv.lock --python 3.15t        # free-threaded
wheelripe requirements.txt --platform linux-aarch64,musllinux-x86_64 --glibc 2.28
```

```
BLOCKED  confluent-kafka 2.16.0          no cp315 wheel for any target platform (ships cp38–cp314)
BUMP     numpy 1.26.4 → 2.5.2            no cp315 wheel in 1.26.4 (ships cp39–cp312); 2.5.2 is the first release with one
BUMP     pydantic_core 2.41.5 → 2.48.0   no cp315 wheel in 2.41.5 (ships cp39–cp314); 2.48.0 is the first release with one
READY    1 package (0 with binary wheels · 1 pure Python)

NOT RIPE for CPython 3.15: 1 blocked upstream · 2 need a version bump
```

Exit code is 1 when anything needs a bump or is blocked (`--fail-on blocked|build|never` to change). Also: `-f json|markdown|github`, a [GitHub Action](https://blackman99.github.io/wheelripe/docs/usage.html#github-action) (`uses: Blackman99/wheelripe@v0.1.0`), and an [MCP server](https://blackman99.github.io/wheelripe/docs/usage.html#mcp) (`wheelripe mcp`) so coding agents check before they bump.

Docs: https://blackman99.github.io/wheelripe/docs/ · [GOAL.md](GOAL.md) · [ROADMAP.md](ROADMAP.md) · MIT
