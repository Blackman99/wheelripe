# Goal

**Tell you, before you move a project to a new Python (3.15, free-threaded 3.15t, and every release after), which of its dependencies have no installable wheel for that Python on your platforms — and the smallest version bump that fixes each one.**

That is the whole job. A dependency is either ready (a wheel installs), fixed by a bump (a newer release has the wheel), blocked upstream (no release has one yet), excluded by `requires-python`, or sdist-only. wheelripe answers from your lockfile and the package index's own file lists, with the same tag rules pip uses, without installing anything.

In scope: reading uv.lock / pylock.toml / poetry.lock / Pipfile.lock / requirements*.txt / pyproject.toml; CPython target versions including free-threaded builds and the PEP 803 `abi3t` stable ABI; Linux (manylinux/musllinux), macOS and Windows targets; text / JSON / Markdown / GitHub-annotation output; a GitHub Action; a read-only MCP server so coding agents can ask before they bump.

Out of scope: building wheels, editing your lockfile, running your test suite on the new Python, checking source-level compatibility (removed stdlib APIs), conda packages, and PyPy/GraalPy targets. Requests in those directions get a polite close pointing here.
