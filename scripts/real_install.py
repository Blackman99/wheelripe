#!/usr/bin/env python3
"""Run on a *real* target interpreter (e.g. CPython 3.15 / 3.15t in CI).

wheelripe predicts, for this interpreter and this machine's platform, which pinned
packages install from a wheel. We then ask pip on this very interpreter to install
each one with --only-binary=:all: and require the prediction to match.
"""
import json
import platform
import subprocess
import sys
import sysconfig
import tempfile

SPECS = ["numpy==1.26.4", "numpy==2.5.4", "six==1.16.0", "confluent-kafka==2.16.0", "pydantic-core==2.41.5",
         "pydantic-core==2.50.1", "cryptography==46.0.3", "msgpack==1.2.3", "zstandard==0.25.0", "pyyaml==6.0.1",
         "orjson", "lxml", "markupsafe==2.1.5"]

target = sys.argv[1] if len(sys.argv) > 1 else f"{sys.version_info.major}.{sys.version_info.minor}"
ft = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
assert target.endswith("t") == ft, f"interpreter free-threaded={ft} but target {target}"
glibc = platform.libc_ver()[1] or "2.34"
arch = platform.machine()
plat = f"linux-{arch}"
out = subprocess.run([sys.executable, "-m", "wheelripe", *SPECS, "--python", target, "--platform", plat,
                      "--glibc", glibc, "-f", "json", "--fail-on", "never"],
                     capture_output=True, text=True, check=True)
pkgs = json.loads(out.stdout)["packages"]
bad = 0
for p in pkgs:
    spec = f"{p['name']}=={p['version']}"
    predicted = p["platforms"][plat]["status"] == "ready"
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps", "--only-binary=:all:",
                            "--target", tmp, "-q", "--disable-pip-version-check", spec],
                           capture_output=True, text=True)
    actual = r.returncode == 0
    ok = predicted == actual
    bad += not ok
    print(f"{'ok ' if ok else 'MISMATCH'} {spec:28} predicted={p['platforms'][plat]['status']:8} "
          f"pip-on-{sys.version.split()[0]}{'t' if ft else ''}={'installed' if actual else 'no wheel'}")
print(f"glibc {glibc} · {arch} · {len(pkgs) - bad}/{len(pkgs)} match")
sys.exit(1 if bad else 0)
