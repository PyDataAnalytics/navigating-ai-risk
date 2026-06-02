#!/usr/bin/env python3
"""
runpod_pod.py - RunPod REST v1 control for the weekly discovery job.

Discovery CREATES A FRESH POD each run and TERMINATES it at the end. Creating
(rather than resuming a pinned pod) lets RunPod place the pod on any host with
capacity.

`create` is built to actually land a GPU:
  * Sends a curated list of >=24GB GPU type ids (an 8B model fits on any of them).
  * SELF-CORRECTS: the REST API validates gpuTypeIds against a fixed enum and
    400s the whole request if any id is not in it. On that 400 we parse the
    allowed ids out of the error and retry with the intersection, so a stale or
    mistyped id can never block the run.
  * Tries SECURE then COMMUNITY cloud (capacity escalation).
  * 240s timeout + id-recovery-by-name (a slow create can't duplicate/orphan).

`create` exit codes:
  0  pod created (id on stdout)
  1  request rejected for a non-GPU reason, HTTP 4xx (bad key/body) -> workflow fails
  3  no GPU obtained (capacity / 5xx / timeout)                      -> workflow skips

Commands: create | wait | terminate | cleanup | describe | start | stop
stdlib only. Auth: Bearer ${RUNPOD_API_KEY}.

create env: POD_NAME, GPU_TYPE_IDS (comma list; optional preference/override),
POD_TEMPLATE_ID, POD_IMAGE, POD_CLOUD_TYPE (comma list, default "SECURE,COMMUNITY"),
CONTAINER_DISK_GB, VOLUME_GB, PUBLIC_KEY.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "https://rest.runpod.io/v1"
TIMEOUT = 60.0
CREATE_TIMEOUT = 240.0
USER_AGENT = "ai-risk-discovery/1.0 (+github-actions)"

DEFAULT_IMAGE = "runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04"

# Curated >=24GB GPUs, in rough order of availability/value. These are standard
# RunPod REST gpuTypeIds; if any is stale, the enum self-correction handles it.
DEFAULT_GPU_IDS = [
    "NVIDIA GeForce RTX 4090",
    "NVIDIA L40S",
    "NVIDIA L40",
    "NVIDIA RTX A5000",
    "NVIDIA RTX A6000",
    "NVIDIA A40",
    "NVIDIA GeForce RTX 3090",
    "NVIDIA A100 80GB PCIe",
    "NVIDIA H100 PCIe",
    "NVIDIA H100 80GB HBM3",
]

_LAST_STATUS: int | None = None
_LAST_ERROR: str = ""


def _api(method: str, path: str, body: dict | None = None, timeout: float = TIMEOUT):
    global _LAST_STATUS, _LAST_ERROR
    _LAST_STATUS = None
    _LAST_ERROR = ""
    key = os.environ.get("RUNPOD_API_KEY", "").strip()
    if not key:
        print("RUNPOD_API_KEY is not set", file=sys.stderr)
        sys.exit(2)
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(f"{BASE}{path}", data=data, method=method, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed https host)
            _LAST_STATUS = getattr(r, "status", 200)
            txt = r.read().decode("utf-8")
            return json.loads(txt) if txt.strip() else {}
    except HTTPError as e:
        _LAST_STATUS = e.code
        _LAST_ERROR = e.read().decode("utf-8", "replace")
        print(f"RunPod {method} {path} -> HTTP {e.code}: {_LAST_ERROR[:300]}", file=sys.stderr)
        return None
    except Exception as e:  # noqa: BLE001
        print(f"RunPod {method} {path} -> {type(e).__name__}: {e}", file=sys.stderr)
        return None


def _enum_from_error(text: str) -> list[str]:
    """Extract RunPod's allowed gpuTypeIds from a 400 'value must be one of ...'."""
    if "must be one of" not in text:
        return []
    tail = text.split("must be one of", 1)[1]
    # Stop at the next problem entry if present, then grab all quoted tokens.
    tail = re.split(r'"\s*\]|"\s*,\s*"At ', tail, maxsplit=1)[0]
    return [m for m in re.findall(r"'([^']+)'", tail)]


def _all_pods() -> list[dict]:
    out = _api("GET", "/pods")
    if isinstance(out, list):
        return [p for p in out if isinstance(p, dict)]
    if isinstance(out, dict):
        for key in ("pods", "data", "items"):
            v = out.get(key)
            if isinstance(v, list):
                return [p for p in v if isinstance(p, dict)]
    return []


def _ids_by_name(name: str) -> list[str]:
    return [p["id"] for p in _all_pods() if p.get("name") == name and p.get("id")]


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


def _post_create(body: dict, name: str) -> tuple[str | None, int | None, str]:
    """POST once + recover by name. Returns (pod_id, http_status, error_body)."""
    out = _api("POST", "/pods", body, timeout=CREATE_TIMEOUT)
    status, err = _LAST_STATUS, _LAST_ERROR
    pod_id = None
    if isinstance(out, dict):
        pod_id = out.get("id") or (out.get("pod") or {}).get("id")
    if not pod_id:
        for _ in range(6):
            ids = _ids_by_name(name)  # overwrites globals; that's fine, we saved them
            if ids:
                pod_id = ids[0]
                print(f"create: recovered pod {pod_id} by name '{name}'", file=sys.stderr)
                break
            time.sleep(10)
    return pod_id, status, err


def _create_in_cloud(
    base_body: dict, gpu_ids: list[str], name: str
) -> tuple[str | None, int | None]:
    """Create in one cloud, self-correcting the GPU list against RunPod's enum."""
    body = dict(base_body)
    body["gpuTypeIds"] = gpu_ids
    pod_id, status, err = _post_create(body, name)
    if pod_id:
        return pod_id, status

    # Enum rejection -> learn the allowed ids and retry with the intersection.
    if status == 400 and "gpuTypeIds" in err:
        allowed = _enum_from_error(err)
        if allowed:
            fixed = [g for g in gpu_ids if g in allowed] or allowed
            if fixed and fixed != gpu_ids:
                print(
                    f"create: retrying with RunPod-accepted GPU ids "
                    f"({len(fixed)} of {len(allowed)} allowed)",
                    file=sys.stderr,
                )
                body["gpuTypeIds"] = fixed
                pod_id, status, _ = _post_create(body, name)
                if pod_id:
                    return pod_id, status
    return None, status


def cmd_create() -> int:
    requested = [g.strip() for g in os.environ.get("GPU_TYPE_IDS", "").split(",") if g.strip()]
    gpu_ids = list(dict.fromkeys(requested + DEFAULT_GPU_IDS))  # preference first, then fallbacks
    name = os.environ.get("POD_NAME", "ai-risk-discovery")
    clouds = [
        c.strip().upper()
        for c in os.environ.get("POD_CLOUD_TYPE", "SECURE,COMMUNITY").split(",")
        if c.strip()
    ]
    template_id = os.environ.get("POD_TEMPLATE_ID", "").strip()
    base_body: dict = {
        "name": name,
        "computeType": "GPU",
        "gpuCount": 1,
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
    if template_id:
        base_body["templateId"] = template_id
    else:
        base_body["imageName"] = os.environ.get("POD_IMAGE", DEFAULT_IMAGE)

    worst_status: int | None = None
    for cloud in clouds:
        print(f"create: trying {cloud} cloud ({len(gpu_ids)} GPU ids)", file=sys.stderr)
        body = dict(base_body)
        body["cloudType"] = cloud
        pod_id, status = _create_in_cloud(body, gpu_ids, name)
        if pod_id:
            print(pod_id)  # stdout: captured by the workflow
            return 0
        if status is not None:
            worst_status = status
        print(f"create: {cloud} cloud yielded no pod; trying next option", file=sys.stderr)

    # 4xx that is NOT the (self-corrected) gpu enum means a real problem to fix.
    if worst_status is not None and 400 <= worst_status < 500:
        print(
            f"create: request rejected (HTTP {worst_status}); check API key / body",
            file=sys.stderr,
        )
        return 1
    print("create: no GPU available in any cloud right now; run will be skipped", file=sys.stderr)
    return 3


def cmd_wait(pod_id: str, timeout_s: int, interval_s: int) -> int:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        pod = _api("GET", f"/pods/{pod_id}")
        if isinstance(pod, dict) and _is_running(pod):
            ep = _ssh_endpoint(pod)
            if ep:
                print(f"{ep[0]} {ep[1]}")
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
    return 0


def cmd_cleanup(name: str) -> int:
    if not name:
        print("cleanup: no --name - nothing to do")
        return 0
    ids = _ids_by_name(name)
    if not ids:
        print(f"cleanup: no pods named '{name}'")
        return 0
    for pid in ids:
        _api("DELETE", f"/pods/{pid}")
        print(f"cleanup: terminated {pid} (name '{name}')")
    return 0


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
    ap.add_argument(
        "command",
        choices=["create", "wait", "terminate", "cleanup", "describe", "start", "stop"],
    )
    ap.add_argument("--pod-id", default=os.environ.get("RP_POD_ID", ""))
    ap.add_argument("--name", default=os.environ.get("POD_NAME", ""))
    ap.add_argument("--timeout", type=int, default=420, help="wait: seconds before giving up")
    ap.add_argument("--interval", type=int, default=12, help="wait: poll interval seconds")
    a = ap.parse_args()

    if a.command == "create":
        return cmd_create()
    if a.command == "cleanup":
        return cmd_cleanup(a.name)
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
