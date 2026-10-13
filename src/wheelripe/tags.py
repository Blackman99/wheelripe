"""Wheel tag compatibility for a *target* interpreter and platform.

This deliberately does not use ``packaging.tags.sys_tags()``: that describes the
interpreter running wheelripe, while we need to answer for an interpreter you do
not have yet (CPython 3.15, 3.15t, ...) on platforms you are not on.

Rules follow PEP 425 / PEP 600 / PEP 656 / PEP 703 and PEP 803 (abi3t).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import FrozenSet, Iterable, Optional, Tuple

# ---------------------------------------------------------------------------
# targets


@dataclass(frozen=True)
class Python:
    major: int
    minor: int
    freethreaded: bool = False

    @classmethod
    def parse(cls, text: str) -> "Python":
        m = re.fullmatch(r"\s*(?:cp|py|python)?(\d)\.?(\d{1,2})(t?)\s*", text.lower())
        if not m:
            raise ValueError(f"cannot parse Python version {text!r} (try 3.15 or 3.15t)")
        return cls(int(m.group(1)), int(m.group(2)), bool(m.group(3)))

    @property
    def nodot(self) -> str:
        return f"{self.major}{self.minor}"

    @property
    def full(self) -> str:
        """Version string used for requires-python and markers."""
        return f"{self.major}.{self.minor}.0"

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}{'t' if self.freethreaded else ''}"


@dataclass(frozen=True)
class Platform:
    key: str
    os: str  # linux | musllinux | macos | windows
    arch: str
    libc: Tuple[int, int] = (0, 0)  # glibc / musl version, or macOS version
    markers: Tuple[Tuple[str, str], ...] = field(default=())

    def marker_env(self, py: Python) -> dict:
        env = {
            "implementation_name": "cpython",
            "platform_python_implementation": "CPython",
            "python_version": f"{py.major}.{py.minor}",
            "python_full_version": py.full,
            "implementation_version": py.full,
            "extra": "",
        }
        env.update(dict(self.markers))
        return env


DEFAULT_GLIBC = (2, 34)
DEFAULT_MUSL = (1, 2)
DEFAULT_MACOS = (14, 0)

_LINUX_MARK = (("sys_platform", "linux"), ("os_name", "posix"), ("platform_system", "Linux"))
_MAC_MARK = (("sys_platform", "darwin"), ("os_name", "posix"), ("platform_system", "Darwin"))
_WIN_MARK = (("sys_platform", "win32"), ("os_name", "nt"), ("platform_system", "Windows"))

PLATFORM_KEYS = (
    "linux-x86_64",
    "linux-aarch64",
    "musllinux-x86_64",
    "musllinux-aarch64",
    "macos-arm64",
    "macos-x86_64",
    "windows-amd64",
    "windows-arm64",
    "windows-x86",
)
DEFAULT_PLATFORMS = ("linux-x86_64", "macos-arm64", "windows-amd64")


def _ver(text: Optional[str], default: Tuple[int, int]) -> Tuple[int, int]:
    if not text:
        return default
    parts = [int(p) for p in text.split(".")[:2]]
    return (parts[0], parts[1] if len(parts) > 1 else 0)


def make_platform(key: str, glibc: Optional[str] = None, musl: Optional[str] = None,
                  macos: Optional[str] = None) -> Platform:
    key = key.strip().lower()
    aliases = {
        "linux": "linux-x86_64", "manylinux": "linux-x86_64", "linux-amd64": "linux-x86_64",
        "linux-arm64": "linux-aarch64", "musllinux": "musllinux-x86_64", "alpine": "musllinux-x86_64",
        "macos": "macos-arm64", "mac": "macos-arm64", "darwin": "macos-arm64",
        "macos-intel": "macos-x86_64", "windows": "windows-amd64", "win": "windows-amd64",
        "windows-x86_64": "windows-amd64", "windows-32": "windows-x86", "win32": "windows-x86",
    }
    key = aliases.get(key, key)
    if key not in PLATFORM_KEYS:
        raise ValueError(f"unknown platform {key!r}; choose from: {', '.join(PLATFORM_KEYS)}")
    osname, arch = key.split("-", 1)
    if osname == "linux":
        return Platform(key, "linux", arch, _ver(glibc, DEFAULT_GLIBC),
                        _LINUX_MARK + (("platform_machine", arch),))
    if osname == "musllinux":
        return Platform(key, "musllinux", arch, _ver(musl, DEFAULT_MUSL),
                        _LINUX_MARK + (("platform_machine", arch),))
    if osname == "macos":
        return Platform(key, "macos", arch, _ver(macos, DEFAULT_MACOS),
                        _MAC_MARK + (("platform_machine", arch),))
    machine = {"amd64": "AMD64", "arm64": "ARM64", "x86": "x86"}[arch]
    return Platform(key, "windows", arch, (0, 0), _WIN_MARK + (("platform_machine", machine),))


# ---------------------------------------------------------------------------
# wheel filenames


@dataclass(frozen=True)
class WheelTags:
    pythons: FrozenSet[str]
    abis: FrozenSet[str]
    platforms: FrozenSet[str]

    @property
    def is_pure(self) -> bool:
        return self.abis == frozenset({"none"}) and self.platforms == frozenset({"any"})


def parse_wheel_filename(filename: str) -> Optional[WheelTags]:
    """Return the expanded tag sets of a wheel filename, or None if it is not a wheel."""
    name = filename.rsplit("/", 1)[-1]
    if not name.endswith(".whl"):
        return None
    parts = name[:-4].split("-")
    if len(parts) < 5:
        return None
    py, abi, plat = parts[-3:]
    return WheelTags(frozenset(py.lower().split(".")), frozenset(abi.lower().split(".")),
                     frozenset(plat.lower().split(".")))


# ---------------------------------------------------------------------------
# interpreter + ABI


def _cp_minor(tag: str, major: int) -> Optional[int]:
    m = re.fullmatch(rf"cp{major}(\d+)", tag)
    return int(m.group(1)) if m else None


def _interp_abi_ok(py_tag: str, abi: str, target: Python) -> bool:
    maj = target.major
    if abi == "none":
        if py_tag == f"py{maj}" or py_tag == f"cp{target.nodot}":
            return True
        m = re.fullmatch(rf"py{maj}(\d+)", py_tag)
        return bool(m) and int(m.group(1)) <= target.minor
    cp = _cp_minor(py_tag, maj)
    if cp is None:
        return False
    if abi == f"cp{target.nodot}t":
        return target.freethreaded and cp == target.minor
    if abi == f"cp{target.nodot}":
        return (not target.freethreaded) and cp == target.minor
    if abi == "abi3":
        # PEP 384: cp3X-abi3 runs on GIL-enabled 3.X and later; never on free-threaded.
        return (not target.freethreaded) and 2 <= cp <= target.minor
    if abi == "abi3t":
        # PEP 803: abi3t runs on free-threaded builds whose version >= the tag's (table starts at 3.14).
        return target.freethreaded and 14 <= cp <= target.minor
    return False


# ---------------------------------------------------------------------------
# platform

_LEGACY_MANYLINUX = {"manylinux1": (2, 5), "manylinux2010": (2, 12), "manylinux2014": (2, 17)}
_MAC_ARCHES = {
    "arm64": {"arm64", "universal2"},
    "x86_64": {"x86_64", "intel", "fat64", "fat3", "universal", "universal2"},
}
_WIN = {"amd64": "win_amd64", "arm64": "win_arm64", "x86": "win32"}


def platform_ok(tag: str, plat: Platform) -> bool:
    if tag == "any":
        return True
    if plat.os in ("linux", "musllinux"):
        if tag == f"linux_{plat.arch}":
            return True
        if plat.os == "linux":
            m = re.fullmatch(r"manylinux_(\d+)_(\d+)_(\w+)", tag)
            if m:
                return m.group(3) == plat.arch and (int(m.group(1)), int(m.group(2))) <= plat.libc
            m = re.fullmatch(r"(manylinux1|manylinux2010|manylinux2014)_(\w+)", tag)
            if m:
                return m.group(2) == plat.arch and _LEGACY_MANYLINUX[m.group(1)] <= plat.libc
            return False
        m = re.fullmatch(r"musllinux_(\d+)_(\d+)_(\w+)", tag)
        return bool(m) and m.group(3) == plat.arch and (int(m.group(1)), int(m.group(2))) <= plat.libc
    if plat.os == "macos":
        m = re.fullmatch(r"macosx_(\d+)_(\d+)_(\w+)", tag)
        if not m:
            return False
        major, minor, arch = int(m.group(1)), int(m.group(2)), m.group(3)
        if arch not in _MAC_ARCHES[plat.arch]:
            return False
        if plat.arch == "arm64" and arch == "arm64" and major < 11:
            return False
        if major >= 11:
            return major <= plat.libc[0]
        return True  # every 10.x tag is older than any supported target
    if plat.os == "windows":
        return tag == _WIN[plat.arch]
    return False


def compatible(tags: WheelTags, target: Python, plat: Platform) -> bool:
    if not any(platform_ok(p, plat) for p in tags.platforms):
        return False
    return any(_interp_abi_ok(py, abi, target) for py in tags.pythons for abi in tags.abis)


def kind(tags: WheelTags, target: Python) -> str:
    """Short label for *why* a compatible wheel matched."""
    if tags.is_pure:
        return "pure"
    if "abi3t" in tags.abis and target.freethreaded:
        return "abi3t"
    if "abi3" in tags.abis and not target.freethreaded:
        return "abi3"
    if "none" in tags.abis:
        return "py-none"
    return f"cp{target.nodot}{'t' if target.freethreaded else ''}"


def binary_pythons(all_tags: Iterable[WheelTags]) -> list:
    """CPython versions a release ships version-specific wheels for, e.g. ['cp312', 'cp313t']."""
    seen = set()
    for t in all_tags:
        for abi in t.abis:
            if re.fullmatch(r"cp\d+t?", abi):
                seen.add(abi)
    def key(s: str):
        return (int(s[3:].rstrip("t")), s.endswith("t"))
    return sorted(seen, key=key)


def _fmt(v: Tuple[int, int]) -> str:
    return f"{v[0]}.{v[1]}"


def why_not_platform(tags: WheelTags, plat: Platform) -> str:
    """One-line reason none of the wheel's platform tags fit (assumes they don't)."""
    floors = []
    for tag in tags.platforms:
        m = re.fullmatch(r"manylinux_(\d+)_(\d+)_(\w+)", tag)
        if m and plat.os == "linux" and m.group(3) == plat.arch:
            floors.append(f"needs glibc {m.group(1)}.{m.group(2)}, your floor is {_fmt(plat.libc)}")
        m = re.fullmatch(r"musllinux_(\d+)_(\d+)_(\w+)", tag)
        if m and plat.os == "musllinux" and m.group(3) == plat.arch:
            floors.append(f"needs musl {m.group(1)}.{m.group(2)}, your floor is {_fmt(plat.libc)}")
        m = re.fullmatch(r"macosx_(\d+)_(\d+)_(\w+)", tag)
        if m and plat.os == "macos" and m.group(3) in _MAC_ARCHES[plat.arch] and int(m.group(1)) >= 11:
            floors.append(f"needs macOS {m.group(1)}, your floor is {plat.libc[0]}")
    if floors:
        return floors[0]
    return f"built for {', '.join(sorted(tags.platforms))}, not {plat.key}"


def why_not_python(tags: WheelTags, target: Python) -> str:
    """One-line reason no interpreter/ABI pair fits (assumes none does)."""
    abis = tags.abis
    if target.freethreaded:
        if "abi3" in abis and "abi3t" not in abis:
            return "abi3 (stable ABI) wheels never load on free-threaded builds; needs abi3t or cp%st" % target.nodot
        if f"cp{target.nodot}" in abis:
            return f"built for the GIL build cp{target.nodot}, not free-threaded cp{target.nodot}t"
    else:
        if f"cp{target.nodot}t" in abis or "abi3t" in abis and "abi3" not in abis:
            return f"built for free-threaded builds only, not GIL-enabled CPython {target}"
    cps = sorted({m for m in (_cp_minor(p, target.major) for p in tags.pythons) if m is not None})
    if "abi3" in abis or "abi3t" in abis:
        if cps and min(cps) > target.minor:
            return f"stable-ABI wheel needs CPython {target.major}.{min(cps)} or newer"
    if cps:
        return f"built for {', '.join(sorted(tags.pythons))}, not cp{target.nodot}{'t' if target.freethreaded else ''}"
    return f"interpreter tag {', '.join(sorted(tags.pythons))} does not match CPython {target}"


def explain_one(tags: WheelTags, target: Python, plat: Platform) -> Tuple[bool, str]:
    """(installs?, short reason) for one wheel on one target."""
    py_ok = any(_interp_abi_ok(py, abi, target) for py in tags.pythons for abi in tags.abis)
    plat_ok = any(platform_ok(p, plat) for p in tags.platforms)
    if py_ok and plat_ok:
        return True, f"installs ({kind(tags, target)})"
    reasons = []
    if not py_ok:
        reasons.append(why_not_python(tags, target))
    if not plat_ok:
        reasons.append(why_not_platform(tags, plat))
    return False, "; ".join(reasons)
