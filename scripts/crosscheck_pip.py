#!/usr/bin/env python3
"""Ground-truth check: wheelripe's per-platform verdict must agree with pip's own resolver.

For every (pinned package, platform) pair we ask pip, with --only-binary=:all: and an
explicit --python-version/--platform/--abi, whether it can find a wheel. pip's tag logic
is the reference implementation; wheelripe must say READY exactly when pip succeeds.
Hits the real PyPI. Run: python scripts/crosscheck_pip.py
"""
import json
import subprocess
import sys
import tempfile
import urllib.request

PKGS = [
    "numpy==1.26.4", "numpy@latest", "cchardet==2.1.7", "pydantic-core==2.41.5", "pydantic-core@latest",
    "confluent-kafka==2.16.0", "onnxruntime@latest", "six==1.16.0", "pywin32@latest", "orjson@latest",
    "lxml@latest", "psycopg-binary@latest", "pyyaml==6.0.1", "pyyaml@latest", "cryptography@latest",
    "cffi==1.17.1", "regex==2024.11.6", "pillow@latest", "pandas==2.2.3", "pandas@latest", "scipy@latest",
    "torch@latest", "markupsafe==2.1.5", "msgpack@latest", "zstandard@latest", "llvmlite==0.44.0",
]
# pip only expands the legacy manylinux aliases for --platform, so spell out every
# glibc level up to the 2.34 default (what a real glibc-2.34 pip would accept).
def _manylinux(arch):
    return [f"manylinux_2_{m}_{arch}" for m in range(34, 4, -1)] + [
        f"manylinux2014_{arch}", f"manylinux2010_{arch}", f"manylinux1_{arch}"]


PLATFORMS = {
    "linux-x86_64": _manylinux("x86_64"),
    "linux-aarch64": _manylinux("aarch64"),
    "musllinux-x86_64": ["musllinux_1_2_x86_64", "musllinux_1_1_x86_64", "musllinux_1_0_x86_64"],
    "macos-arm64": ["macosx_14_0_arm64"],
    "macos-x86_64": ["macosx_14_0_x86_64"],
    "windows-amd64": ["win_amd64"],
    "windows-arm64": ["win_arm64"],
}
PY = sys.argv[1] if len(sys.argv) > 1 else "3.15"


def latest(name):
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json", timeout=30) as r:
        return json.load(r)["info"]["version"]


def pip_ok(spec, plats, py):
    nodot = py.replace(".", "").rstrip("t")
    abi = f"cp{nodot}t" if py.endswith("t") else f"cp{nodot}"
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [sys.executable, "-m", "pip", "install", "--dry-run", "--no-deps", "--ignore-installed",
               "--only-binary=:all:", "--target", tmp, "--python-version", py.rstrip("t"),
               "--implementation", "cp", "--abi", abi, "-q", "--disable-pip-version-check"]
        for p in plats:
            cmd += ["--platform", p]
        cmd.append(spec)
        return subprocess.run(cmd, capture_output=True, text=True).returncode == 0


def main():
    specs = []
    for p in PKGS:
        name, _, ver = p.partition("==") if "==" in p else (p.split("@")[0], "", latest(p.split("@")[0]))
        specs.append(f"{name}=={ver}")
    out = subprocess.run([sys.executable, "-m", "wheelripe", *specs, "--python", PY, "-f", "json",
                          "--fail-on", "never", "--platform", ",".join(PLATFORMS)],
                         capture_output=True, text=True, check=True)
    rep = {(p["name"].lower().replace("_", "-"), p["version"]): p for p in json.loads(out.stdout)["packages"]}
    bad = 0
    rows = 0
    for spec in specs:
        name, ver = spec.split("==")
        res = rep[(name.lower(), ver)]
        for key, plats in PLATFORMS.items():
            mine = res["platforms"][key]["status"] == "ready"
            theirs = pip_ok(spec, plats, PY)
            rows += 1
            flag = "ok " if mine == theirs else "MISMATCH"
            if mine != theirs:
                bad += 1
            print(f"{flag} {spec:32} {key:18} wheelripe={'ready' if mine else res['platforms'][key]['status']:8} "
                  f"pip={'wheel' if theirs else 'none'}")
    print(f"\n{rows - bad}/{rows} agree with pip ({PY})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
