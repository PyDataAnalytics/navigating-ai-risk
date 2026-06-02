#!/usr/bin/env python3
"""
runpod_pod.py - RunPod REST v1 control for the weekly discovery job.

Discovery CREATES A FRESH POD each run and TERMINATES it at the end. This is
more reliable than resuming a single stopped pod: a stopped pod can fail to
resume when its original host has no free GPU ("not enough free GPUs on the
host machine"). Creating lets RunPod place the pod on any host/datacenter with
capacity, and a permissive GPU list (gpuTypeIds) maximises the odds of getting
one.

Commands:
  create     POST   /v1/pods            create an on-demand pod from a GPU list;
                                         print the new pod id on stdout
  wait       GET    /v1/pods/{id}        poll until RUNNING + public SSH (port 22);
                                         print "<ip> <port>" on stdout
  terminate  DELETE /v1/pods/{id}        delete the pod (best-effort; never wedges
                                         an `if: always()` cleanup step)
  describe   GET    /v1/pods/{id}        dump raw JSON (debugging)
  start/stop POST   /v1/pods/{id}/...    kept for manual use

stdlib only. Auth: Bearer ${RUNPOD_API_KEY}.

`create` reads its config from the environment:
  POD_NAME          pod name (default ai-risk-discovery)
  GPU_TYPE_IDS      comma-separated RunPod GPU type ids to try, any order (required)
  POD_TEMPLATE_ID   create from this template (recommended; overrides POD_IMAGE)
  POD_IMAGE         container image if no template (default: a RunPod pytorch image)
  POD_CLOUD_TYPE    SECURE (default) or COMMUNITY
  CONTAINER_DISK_GB container disk (default 40)
  VOLUME_GB         /workspace volume (default 40)
  PUBLIC_KEY        SSH public key injected into the pod's authorized_keys
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
TIMEOUT = 60.0

DEFAULT_IMAGE = "runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04"


def _api(method: str, path: str, body: dict | None = None) -> dict | list | None:
    key = os.environ.get("RUNPOD_API_KEY", "").strip()
    if not key:
        print("RUNPOD_API_KEY is not set", file=sys.stderr)
        sys.exit(2)
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(f"{BASE}{path}", data=data, method=method, headers=headers)
    try:
        with urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310 (fixed https host)
            txt = r.read().decode("utf-8")
            return json.loads(txt) if txt.strip() else {}
    except HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        print(f"RunPod {method} {path} -> HTTP {e.code}: {detail}", file=sys.stderr)
        return None
    except Exception as e:  # noqa: BLE001 - surface, don't crash the cleanup path
        print(f"RunPod {method} {path} -> {type(e).__name__}: {e}", file=sys.stderr)
        return None


def _ports(pod: dict) -> list[dict]:
    rt = pod.get("runtime") or {}
    for candidate in (rt.get("ports"), pod.get("portMappings"), pod.get("ports")):
        if isinstance(candidate, list) and candidate:
            return candidate
    return []


def _ssh_endpoint(pod: dict) -> tuple[str, int] | None:
    for p in _ports(pod):
        if not isinstance(p, dict):
            continue
        public = p.get("isIpPublic") or p.get("isPublic")
        if public and p.get("privatePort") == 22 and p.get("ip") and p.get("publicPort"):
            return str(p["ip"]), int(p["publicPort"])
    return None


def _is_running(pod: dict) -> bool:
    status = (pod.get("desiredStatus") or pod.get("status") or "").upper()
    return status == "RUNNING" or bool(pod.get("runtime"))


def cmd_create() -> int:
    gpu_ids = [g.strip() for g in os.environ.get("GPU_TYPE_IDS", "").split(",") if g.strip()]
    if not gpu_ids:
        print("GPU_TYPE_IDS not set (comma-separated GPU type ids)", file=sys.stderr)
        return 2
    body: dict = {
        "name": os.environ.get("POD_NAME", "ai-risk-discovery"),
        "computeType": "GPU",
        "cloudType": os.environ.get("POD_CLOUD_TYPE", "SECURE"),
        "gpuCount": 1,
        "gpuTypeIds": gpu_ids,
        "gpuTypePriority": "availability",
        "dataCenterPriority": "availability",
        "containerDiskInGb": int(os.environ.get("CONTAINER_DISK_GB", "40")),
        "volumeInGb": int(os.environ.get("VOLUME_GB", "40")),
        "volumeMountPath": "/workspace",
        "ports": ["8888/http", "22/tcp"],
        "supportPublicIp": True,
        "interruptible": False,
        "env": {"PUBLIC_KEY": os.environ.get("PUBLIC_KEY", "")},
    }
    template_id = os.environ.get("POD_TEMPLATE_ID", "").strip()
    if template_id:
        body["templateId"] = template_id
    else:
        body["imageName"] = os.environ.get("POD_IMAGE", DEFAULT_IMAGE)

    out = _api("POST", "/pods", body)
    if not isinstance(out, dict):
        return 1
    pod_id = out.get("id") or (out.get("pod") or {}).get("id")
    if not pod_id:
        print(f"create: no pod id in response: {json.dumps(out)[:300]}", file=sys.stderr)
        return 1
    print(pod_id)  # stdout: the workflow captures this
    return 0


def cmd_wait(pod_id: str, timeout_s: int, interval_s: int) -> int:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        pod = _api("GET", f"/pods/{pod_id}")
        if isinstance(pod, dict) and _is_running(pod):
            ep = _ssh_endpoint(pod)
            if ep:
                print(f"{ep[0]} {ep[1]}")  # stdout: consumed by the workflow
                return 0
            print("  running, no public SSH (port 22) yet...", file=sys.stderr)
        else:
            print("  pod not running yet...", file=sys.stderr)
        time.sleep(interval_s)
    print(f"timed out after {timeout_s}s waiting for pod {pod_id} SSH", file=sys.stderr)
    return 1


def cmd_terminate(pod_id: str) -> int:
    if not pod_id:
        print("terminate: no pod id - nothing to do")
        return 0
    out = _api("DELETE", f"/pods/{pod_id}")
    print(f"terminate requested for pod {pod_id} (ok={out is not None})")
    return 0  # never fail the cleanup step


def cmd_describe(pod_id: str) -> int:
    out = _api("GET", f"/pods/{pod_id}")
    print(json.dumps(out, indent=2))
    return 0 if out is not None else 1


def cmd_simple(pod_id: str, action: str) -> int:
    out = _api("POST", f"/pods/{pod_id}/{action}")
    print(f"{action} requested for pod {pod_id} (ok={out is not None})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["create", "wait", "terminate", "describe", "start", "stop"])
    ap.add_argument("--pod-id", default=os.environ.get("RP_POD_ID", ""))
    ap.add_argument("--timeout", type=int, default=420, help="wait: seconds before giving up")
    ap.add_argument("--interval", type=int, default=12, help="wait: poll interval seconds")
    a = ap.parse_args()

    if a.command == "create":
        return cmd_create()
    if a.command == "terminate":
        return cmd_terminate(a.pod_id)
    if not a.pod_id:
        print(f"{a.command}: no --pod-id (or RP_POD_ID)", file=sys.stderr)
        return 2
    if a.command == "wait":
        return cmd_wait(a.pod_id, a.timeout, a.interval)
    if a.command == "describe":
        return cmd_describe(a.pod_id)
    return cmd_simple(a.pod_id, a.command)


if __name__ == "__main__":
    raise SystemExit(main())
