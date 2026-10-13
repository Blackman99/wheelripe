"""A small, dependency-free MCP server (stdio, JSON-RPC 2.0, newline-delimited).

Read-only: it reads local dependency files and queries the package index. It never
installs, edits or uploads anything.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional

from . import __version__, report
from .check import run
from .inputs import InputError, collect, from_spec
from .pypi import PyPI
from .tags import DEFAULT_PLATFORMS, PLATFORM_KEYS, Python, compatible, make_platform, parse_wheel_filename

SUPPORTED = ("2025-06-18", "2025-03-26", "2024-11-05")

_PLAT_SCHEMA = {"type": "array", "items": {"type": "string", "enum": list(PLATFORM_KEYS)},
                "description": f"Target platforms. Default: {', '.join(DEFAULT_PLATFORMS)}"}
_PY_SCHEMA = {"type": "string", "description": "Target CPython, e.g. '3.15' or '3.15t' (free-threaded).",
              "default": "3.15"}

TOOLS = [
    {
        "name": "check_python_upgrade",
        "title": "Check Python upgrade wheel readiness",
        "description": (
            "Before moving a project to a new Python (e.g. 3.15 or free-threaded 3.15t), list every "
            "dependency that has no installable wheel for it on the target platforms, and the smallest "
            "version bump that fixes each one. Reads uv.lock / pylock.toml / poetry.lock / Pipfile.lock / "
            "requirements.txt / pyproject.toml from `path`, or checks explicit `requirements` specs. "
            "Statuses: ready, bump (newer release has a wheel), blocked (no release has one: waiting on "
            "upstream), excluded (requires-python), build (sdist only), skip (marker), missing."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Lockfile, requirements file, pyproject.toml or "
                                                          "project directory. Default: server working dir."},
                "requirements": {"type": "array", "items": {"type": "string"},
                                 "description": "Requirement specs such as 'numpy==1.26.4' (instead of path)."},
                "python": _PY_SCHEMA,
                "platforms": _PLAT_SCHEMA,
                "glibc": {"type": "string", "description": "Oldest glibc for linux-* targets, default 2.34"},
                "macos": {"type": "string", "description": "Oldest macOS for macos-* targets, default 14"},
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True,
                        "openWorldHint": True},
    },
    {
        "name": "explain_wheel",
        "title": "Explain a wheel filename",
        "description": "Say whether a wheel filename (e.g. foo-1.0-cp315-abi3.abi3t-manylinux_2_28_x86_64.whl) "
                       "installs on a target CPython and platforms, using PEP 425/600/656/803 tag rules.",
        "inputSchema": {
            "type": "object",
            "properties": {"filename": {"type": "string"}, "python": _PY_SCHEMA, "platforms": _PLAT_SCHEMA},
            "required": ["filename"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True,
                        "openWorldHint": False},
    },
]


def _plats(args: Dict[str, Any]):
    keys = args.get("platforms") or list(DEFAULT_PLATFORMS)
    return [make_platform(k, glibc=args.get("glibc"), macos=args.get("macos")) for k in keys]


def call_tool(name: str, args: Dict[str, Any], fetch=None) -> Dict[str, Any]:
    target = Python.parse(args.get("python") or "3.15")
    if name == "explain_wheel":
        tags = parse_wheel_filename(args["filename"])
        if not tags:
            raise ValueError("not a wheel filename")
        res = {p.key: compatible(tags, target, p) for p in _plats(args)}
        txt = "\n".join(f"{k}: {'installs' if v else 'does NOT install'} on CPython {target}" for k, v in res.items())
        return {"content": [{"type": "text", "text": txt}],
                "structuredContent": {"filename": args["filename"], "python": str(target), "installs": res}}
    if name == "check_python_upgrade":
        if args.get("requirements"):
            deps = [from_spec(s, "mcp") for s in args["requirements"]]
            sources = ["requirements"]
        else:
            deps, sources = collect([args.get("path") or os.getcwd()])
        rep = run(deps, fetch or PyPI(), target, _plats(args), sources)
        return {"content": [{"type": "text", "text": report.markdown(rep)}],
                "structuredContent": rep.to_dict()}
    raise KeyError(name)


def handle(msg: Dict[str, Any], fetch=None) -> Optional[Dict[str, Any]]:
    mid = msg.get("id")
    method = msg.get("method")
    if mid is None:  # notification
        return None
    try:
        if method == "initialize":
            asked = (msg.get("params") or {}).get("protocolVersion")
            result = {
                "protocolVersion": asked if asked in SUPPORTED else SUPPORTED[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "wheelripe", "title": "wheelripe", "version": __version__},
                "instructions": "Use check_python_upgrade before bumping a project's Python version "
                                "(CI matrix, Docker base image, requires-python).",
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = msg.get("params") or {}
            try:
                result = call_tool(params.get("name", ""), params.get("arguments") or {}, fetch)
            except KeyError:
                return {"jsonrpc": "2.0", "id": mid,
                        "error": {"code": -32602, "message": f"unknown tool {params.get('name')!r}"}}
            except (ValueError, InputError, OSError, RuntimeError) as e:
                result = {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True}
        else:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    except Exception as e:  # pragma: no cover - defensive
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def serve(stdin=None, stdout=None, fetch=None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            resp = handle(msg, fetch)
        if resp is not None:
            stdout.write(json.dumps(resp) + "\n")
            stdout.flush()
    return 0
