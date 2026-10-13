#!/usr/bin/env python3
"""Build site/data.json: real wheelripe verdicts (live PyPI) for the landing-page cheese."""
import datetime
import json
import sys

from wheelripe.check import run
from wheelripe.inputs import from_spec
from wheelripe.pypi import PyPI
from wheelripe.tags import Python, make_platform

DEMO = ["numpy==2.2.6", "pandas==2.2.3", "pydantic-core==2.41.5", "orjson==3.10.18", "lxml==5.4.0",
        "psycopg-binary==3.2.9", "cryptography==45.0.4", "pyyaml==6.0.2", "confluent-kafka==2.16.0",
        "onnxruntime==1.31.0", "msgpack==1.1.0", "zstandard==0.25.0", "six==1.16.0", "requests==2.32.4",
        "markupsafe==3.0.2", "regex==2024.11.6"]
TARGETS = ["3.13", "3.14", "3.15", "3.15t"]
PLATS = ["linux-x86_64", "macos-arm64", "windows-amd64"]

pypi = PyPI()
deps = [from_spec(s) for s in DEMO]
out = {"generated": datetime.date.today().isoformat(), "packages": [d.name for d in deps], "pins": {}, "v": {}}
for d in deps:
    out["pins"][d.name] = d.version
for t in TARGETS:
    rep = run(deps, pypi, Python.parse(t), [make_platform(p) for p in PLATS])
    by = {r.name.lower().replace("_", "-"): r for r in rep.results}
    out["v"][t] = {}
    for p in PLATS:
        out["v"][t][p] = {}
        for d in deps:
            r = by[d.name.lower()]
            pr = r.platforms[p]
            out["v"][t][p][d.name] = [pr.status] + ([pr.fix] if pr.fix else [])
json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "site/data.json", "w"), separators=(",", ":"))
print(json.dumps({t: {p: sum(1 for v in out["v"][t][p].values() if v[0] != "ready") for p in PLATS} for t in TARGETS}))
