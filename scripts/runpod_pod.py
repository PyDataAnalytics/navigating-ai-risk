#!/usr/bin/env python3
"""
runpod_pod.py — minimal RunPod REST v1 control plane for the weekly discovery job.

Drives the lifecycle of an existing GPU pod from CI:

  start     POST /v1/pods/{id}/start         resume the (stopped) pod
  wait      GET  /v1/pods/{id} (polled)      block until it's RUNNING and SSH-ready,
                                             then print "<ip> <port>" on stdout
  stop      POST /v1/pods/{id}/stop          stop it (preserves the /workspace volume)
  describe  GET  /v1/pods/{id}               dump raw JSON (for debugging field shapes)

stdlib only. Auth: Bearer ${RUNPOD_API_KEY}. The pod id comes from --pod-id or
${RUNPOD_POD_ID}. SSH details are read from the pod's runtime port list — the entry
with privatePort 22 and a public IP gives the host + mapped external port.

Refs: https://docs.runpod.io/api-reference/pods  (start/stop/get)
      Pod must expose TCP port 22 on a public IP for "SSH over exposed TCP".
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "https://rest.runpod.io/v1"
TIMEOUT = 30.0


def _api(method: str, path: str) -> dict | list | None:
    key = os.environ.get("RUNPOD_API_KEY", "").strip()
    if not key:
        print("RUNPOD_API_KEY is not set", file=sys.stderr)
        sys.exit(2)
    req = Request(
        f"{BASE}{path}",
        method=method,
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310 (fixed https host)
            body = r.read().decode("utf-8")
            return json.loads(body) if body.strip() else {}
    except HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        print(f"RunPod API {method} {path} -> HTTP {e.code}: {detail}", file=sys.stderr)
        return None
    except Exception as e:  # noqa: BLE001
        print(f"RunPod API {method} {path} -> {type(e).__name__}: {e}", file=sys.stderr)
        return None


def _ports(pod: dict) -> list[dict]:
    """Return the runtime port list across the shapes RunPod has used."""
    rt = pod.get("runtime") or {}
    for candidate in (rt.get("ports"), pod.get("portMappings"), pod.get("ports")):
        if isinstance(candidate, list) and candidate:
            return candidate
    return []


def _ssh_endpoint(pod: dict) -> tuple[str, int] | None:
    for p in _ports(pod):
        if not isinstance(p, dict):
            continue
        is_public = p.get("isIpPublic") or p.get("isPublic")
        if is_public and p.get("privatePort") == 22 and p.get("ip") and p.get("publicPort"):
            return str(p["ip"]), int(p["publicPort"])
    return None


def _is_running(pod: dict) -> bool:
    status = (pod.get("desiredStatus") or pod.get("status") or "").upper()
    return status == "RUNNING" or bool(pod.get("runtime"))


def cmd_start(pod_id: str) -> int:
    out = _api("POST", f"/pods/{pod_id}/start")
    if out is None:
        return 1
    print(f"start requested for pod {pod_id}")
    return 0


def cmd_stop(pod_id: str) -> int:
    out = _api("POST", f"/pods/{pod_id}/stop")
    # Treat "already stopped" / transient errors as non-fatal: stopping is a
    # best-effort safety net and must never wedge the workflow.
    print(f"stop requested for pod {pod_id} (ok={out is not None})")
    return 0


def cmd_describe(pod_id: str) -> int:
    out = _api("GET", f"/pods/{pod_id}")
    print(json.dumps(out, indent=2))
    return 0 if out is not None else 1


def cmd_wait(pod_id: str, timeout_s: int, interval_s: int) -> int:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        pod = _api("GET", f"/pods/{pod_id}")
        if isinstance(pod, dict) and _is_running(pod):
            ep = _ssh_endpoint(pod)
            if ep:
                print(f"{ep[0]} {ep[1]}")  # stdout: consumed by the workflow
                return 0
            print("  running but no public SSH (port 22) endpoint yet...", file=sys.stderr)
        else:
            print("  pod not running yet...", file=sys.stderr)
        time.sleep(interval_s)
    print(f"timed out after {timeout_s}s waiting for pod {pod_id} SSH", file=sys.stderr)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["start", "wait", "stop", "describe"])
    ap.add_argument("--pod-id", default=os.environ.get("RUNPOD_POD_ID", ""))
    ap.add_argument("--timeout", type=int, default=300, help="wait: seconds before giving up")
    ap.add_argument("--interval", type=int, default=10, help="wait: poll interval seconds")
    a = ap.parse_args()
    if not a.pod_id:
        print("no pod id (pass --pod-id or set RUNPOD_POD_ID)", file=sys.stderr)
        return 2
    return {
        "start": lambda: cmd_start(a.pod_id),
        "stop": lambda: cmd_stop(a.pod_id),
        "describe": lambda: cmd_describe(a.pod_id),
        "wait": lambda: cmd_wait(a.pod_id, a.timeout, a.interval),
    }[a.command]()


if __name__ == "__main__":
    raise SystemExit(main())
