"""Read dependency lists from lockfiles, requirements files, pyproject.toml or CLI specs."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib


@dataclass
class Dep:
    name: str
    version: Optional[str] = None  # exact pin, or None
    specifier: str = ""  # used when not pinned
    marker: Optional[str] = None
    origin: str = ""

    @property
    def key(self) -> str:
        return canonicalize_name(self.name)


class InputError(Exception):
    pass


AUTODETECT = ("uv.lock", "pylock.toml", "poetry.lock", "Pipfile.lock", "requirements.txt", "pyproject.toml")


def _pin(req: Requirement) -> Optional[str]:
    specs = list(req.specifier)
    if len(specs) == 1 and specs[0].operator in ("==", "===") and "*" not in specs[0].version:
        return specs[0].version
    return None


def from_spec(text: str, origin: str = "cli") -> Dep:
    try:
        req = Requirement(text)
    except InvalidRequirement as e:
        raise InputError(f"not a file and not a requirement: {text!r} ({e})") from None
    return Dep(req.name, _pin(req), str(req.specifier), str(req.marker) if req.marker else None, origin)


def parse_requirements(path: Path, _seen: Optional[set] = None) -> List[Dep]:
    seen = _seen if _seen is not None else set()
    path = path.resolve()
    if path in seen:
        return []
    seen.add(path)
    deps: List[Dep] = []
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"\\\r?\n", " ", text)  # line continuations
    for raw in text.splitlines():
        line = re.sub(r"(^|\s)#.*$", "", raw).strip()
        if not line:
            continue
        m = re.match(r"^(-r|--requirement)\s*=?\s*(\S+)", line)
        if m:
            deps += parse_requirements(path.parent / m.group(2), seen)
            continue
        if line.startswith("-"):  # -c, -e, --index-url, --hash-only lines ...
            continue
        if re.match(r"^(\w+\+)?(https?|file|git)\S*://", line) or line.startswith((".", "/")):
            continue
        line = re.split(r"\s+--hash", line)[0].strip()
        line = re.split(r"\s+--\w", line)[0].strip()
        try:
            req = Requirement(line)
        except InvalidRequirement:
            continue
        if req.url:
            continue
        deps.append(Dep(req.name, _pin(req), str(req.specifier),
                        str(req.marker) if req.marker else None, path.name))
    return deps


def _load_toml(path: Path) -> dict:
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def parse_uv_lock(path: Path) -> List[Dep]:
    data = _load_toml(path)
    deps = []
    for pkg in data.get("package", []):
        src = pkg.get("source", {})
        if "registry" not in src:
            continue  # editable / virtual / git / path / url
        deps.append(Dep(pkg["name"], pkg.get("version"), origin=path.name))
    return deps


def parse_pylock(path: Path) -> List[Dep]:
    data = _load_toml(path)
    deps = []
    for pkg in data.get("packages", []):
        if any(k in pkg for k in ("vcs", "directory", "archive")):
            continue
        if not pkg.get("version"):
            continue
        deps.append(Dep(pkg["name"], pkg["version"], marker=pkg.get("marker"), origin=path.name))
    return deps


def parse_poetry_lock(path: Path) -> List[Dep]:
    data = _load_toml(path)
    deps = []
    for pkg in data.get("package", []):
        src = pkg.get("source") or {}
        if src.get("type") in ("git", "directory", "file", "url"):
            continue
        deps.append(Dep(pkg["name"], pkg.get("version"), origin=path.name))
    return deps


def parse_pipfile_lock(path: Path) -> List[Dep]:
    data = json.loads(path.read_text(encoding="utf-8"))
    deps = []
    for section in ("default", "develop"):
        for name, meta in (data.get(section) or {}).items():
            ver = meta.get("version", "")
            if not ver.startswith("=="):
                continue
            deps.append(Dep(name, ver[2:], marker=meta.get("markers"), origin=f"{path.name}:{section}"))
    return deps


def parse_pyproject(path: Path) -> List[Dep]:
    data = _load_toml(path)
    project = data.get("project", {})
    reqs = [(r, "dependencies") for r in project.get("dependencies", [])]
    for extra, items in (project.get("optional-dependencies") or {}).items():
        reqs += [(r, f"extra:{extra}") for r in items]
    for group, items in (data.get("dependency-groups") or {}).items():
        reqs += [(r, f"group:{group}") for r in items if isinstance(r, str)]
    deps = []
    for text, where in reqs:
        try:
            req = Requirement(text)
        except InvalidRequirement:
            continue
        if req.url:
            continue
        deps.append(Dep(req.name, _pin(req), str(req.specifier),
                        str(req.marker) if req.marker else None, f"pyproject.toml:{where}"))
    return deps


def parse_file(path: Path) -> List[Dep]:
    name = path.name.lower()
    if name == "uv.lock":
        return parse_uv_lock(path)
    if name == "poetry.lock":
        return parse_poetry_lock(path)
    if name == "pipfile.lock":
        return parse_pipfile_lock(path)
    if name == "pyproject.toml":
        return parse_pyproject(path)
    if name == "pylock.toml" or re.fullmatch(r"pylock\.[^.]+\.toml", name):
        return parse_pylock(path)
    return parse_requirements(path)


def collect(args: List[str]) -> tuple:
    """Turn CLI positionals into (deps, sources). Directory -> autodetect the best file."""
    if not args:
        args = ["."]
    deps: List[Dep] = []
    sources: List[str] = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            for cand in AUTODETECT:
                if (p / cand).is_file():
                    deps += parse_file(p / cand)
                    sources.append(str(p / cand))
                    break
            else:
                raise InputError(f"no {', '.join(AUTODETECT)} found in {p}")
        elif p.is_file():
            deps += parse_file(p)
            sources.append(str(p))
        elif os.sep in a or a.endswith((".txt", ".lock", ".toml")):
            raise InputError(f"file not found: {a}")
        else:
            deps.append(from_spec(a))
            sources.append("cli")
    # de-duplicate by (name, version); keep first origin
    uniq = {}
    for d in deps:
        uniq.setdefault((d.key, d.version, d.specifier), d)
    return list(uniq.values()), sources
