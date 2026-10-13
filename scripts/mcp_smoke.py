#!/usr/bin/env python3
"""Drive `wheelripe mcp` over stdio like an MCP client would, against the real PyPI."""
import json
import subprocess
import sys

msgs = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "smoke", "version": "0"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "check_python_upgrade", "arguments": {
        "path": "examples/requirements-blocked.txt", "python": "3.15"}}},
    {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "explain_wheel", "arguments": {
        "filename": "msgpack-1.2.3-cp315-cp315t-win_amd64.whl", "python": "3.15t", "platforms": ["windows-amd64"]}}},
]
p = subprocess.run([sys.executable, "-m", "wheelripe", "mcp"], input="\n".join(json.dumps(m) for m in msgs) + "\n",
                   capture_output=True, text=True, timeout=180)
resp = {r["id"]: r for r in map(json.loads, p.stdout.splitlines())}
assert resp[1]["result"]["serverInfo"]["name"] == "wheelripe", resp[1]
assert len(resp[2]["result"]["tools"]) == 2
sc = resp[3]["result"]["structuredContent"]
status = {x["name"].lower().replace("_", "-"): x["status"] for x in sc["packages"]}
print(json.dumps(status))
assert sc["ripe"] is False
assert status["numpy"] == "bump" and status["six"] == "ready", status
assert resp[4]["result"]["structuredContent"]["installs"] == {"windows-amd64": True}
print(resp[3]["result"]["content"][0]["text"])
print("MCP smoke OK")
