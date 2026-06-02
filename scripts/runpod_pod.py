#!/usr/bin/env python3
"""
runpod_pod.py - RunPod REST v1 control for the weekly discovery job.

Discovery CREATES A FRESH POD each run and TERMINATES it at the end. Creating
(rather than resuming a pinned pod) lets RunPod place the pod on any host with
capacity.

`create` is built to maximise the odds of actually getting a GPU:
  * It pulls RunPod's live GPU catalog (GraphQL) and selects every GPU with
    >= MIN_VRAM_GB of memory - an 8B model fits on any 24GB card - so it never
    depends on a hand-typed GPU-name string being exactly right. A provided
    GPU_TYPE_IDS list is treated as a *preference order*, not a hard constraint.
  * It tries SECURE then COMMUNITY cloud, so a capacity miss in one tier
    escalates to the other.
  * A slow create can time out AFTER the pod was made; the unique per-run pod
    name lets us recover the id instead of failing or duplicating.

`create` exit codes (so the workflow reacts sensibly):
  0  pod created (id on stdout)
  1  request rejected, HTTP 4xx (bad API key / bad body)      -> workflow fails
  2  could not determine any eligible GPU at all              -> workflow fails
  3  no GPU obtained anywhere (capacity / 5xx / timeout)       -> workflow skips

Commands: create | wait | terminate | cleanup | describe | start | stop
stdlib only. Auth: Bearer ${RUNPOD_API_KEY}.

create env: POD_NAME, GPU_TYPE_IDS (comma list, optional preference),
POD_TEMPLATE_ID, POD_IMAGE, POD_CLOUD_TYPE (comma list, default "SECURE,COMMUNITY"),
CONTAINER_DISK_GB, VOLUME_GB, PUBLIC_KEY, MIN_VRAM_GB (default 24).
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
GRAPHQL = "https://api.runpod.io/graphql"
TIMEOUT = 60.0
CREATE_TIMEOUT = 240.0
USER_AGENT = "ai-risk-discovery/1.0 (+github-actions)"

DEFAULT_IMAGE = "runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04"
MIN_VRAM_GB = int(os.environ.get("MIN_VRAM_GB", "24"))

_LAST_STATUS: int | None = None


def _api(method: str, path: str, body: dict | None = None, timeout: float = TIMEOUT):
    global _LAST_STATUS
    _LAST_STATUS = None
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
        detail = e.read().decode("utf-8", "replace")[:400]
        print(f"RunPod {method} {path} -> HTTP {e.code}: {detail}", file=sys.stderr)
        return None
    except Exception as e:  # noqa: BLE001
        print(f"RunPod {method} {path} -> {type(e).__name__}: {e}", file=sys.stderr)
        return None


def _gpu_catalog() -> list[dict]:
    """Live GPU catalog via GraphQL. Best-effort: returns [] on any failure."""
    key = os.environ.get("RUNPOD_API_KEY", "").strip()
    if not key:
        return []
    query = {"query": "query { gpuTypes { id memoryInGb secureCloud communityCloud } }"}
    req = Request(
        f"{GRAPHQL}?api_key={key}",
        data=json.dumps(query).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310
            payload = json.loads(r.read().decode("utf-8"))
        types = (payload.get("data") or {}).get("gpuTypes") or []
        return [t for t in types if isinstance(t, dict) and t.get("id")]
    except Exception as e:  # noqa: BLE001
        print(
            f"gpu catalog lookup failed ({type(e).__name__}); using requested list",
            file=sys.stderr,
        )
        return []


def _resolve_gpu_ids(requested: list[str], cloud: str) -> list[str]:
    """Eligible GPU ids for this cloud (>= MIN_VRAM_GB), requested ones first.

    Falls back to the requested list verbatim if the catalog can't be fetched.
    """
    catalog = _gpu_catalog()
    if not catalog:
        return list(dict.fromkeys(requested))
    want_secure = cloud.upper() == "SECURE"
    eligible = [
        t["id"]
        for t in catalog
        if (t.get("memoryInGb") or 0) >= MIN_VRAM_GB
        and (t.get("secureCloud") if want_secure else t.get("communityCloud"))
    ]
    valid_req = [r for r in requested if r in eligible]
    return list(dict.fromkeys(valid_req + eligible))


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


def _try_create(body: dict, name: str) -> tuple[str | None, int | None]:
    """One create attempt + name-based recovery. Returns (pod_id, http_status)."""
    out = _api("POST", "/pods", body, timeout=CREATE_TIMEOUT)
    status = _LAST_STATUS
    pod_id = None
    if isinstance(out, dict):
        pod_id = out.get("id") or (out.get("pod") or {}).get("id")
    if not pod_id:
        # The POST may have made the pod even though the response was lost.
        for _ in range(6):
            ids = _ids_by_name(name)
            if ids:
                pod_id = ids[0]
                print(f"create: recovered pod {pod_id} by name '{name}'", file=sys.stderr)
                break
            time.sleep(10)
    return pod_id, status


def cmd_create() -> int:
    requested = [g.strip() for g in os.environ.get("GPU_TYPE_IDS", "").split(",") if g.strip()]
    name = os.environ.get("POD_NAME", "ai-risk-discovery")
    clouds = [
        c.strip().upper()
        for c in os.environ.get("POD_CLOUD_TYPE", "SECURE,COMMUNITY").split(",")
        if c.strip()
    ]
    template_id = os.environ.get("POD_TEMPLATE_ID", "").strip()
    image = os.environ.get("POD_IMAGE", DEFAULT_IMAGE)
    public_key = os.environ.get("PUBLIC_KEY", "")
    disk = int(os.environ.get("CONTAINER_DISK_GB", "40"))
    vol = int(os.environ.get("VOLUME_GB", "40"))

    had_any_gpu_list = False
    worst_status: int | None = None

    for cloud in clouds:
        gpu_ids = _resolve_gpu_ids(requested, cloud)
        if not gpu_ids:
            print(f"create: no eligible >={MIN_VRAM_GB}GB GPUs for {cloud} cloud", file=sys.stderr)
            continue
        had_any_gpu_list = True
        print(
            f"create: trying {cloud} cloud with {len(gpu_ids)} candidate GPU type(s)",
            file=sys.stderr,
        )
        body: dict = {
            "name": name,
            "computeType": "GPU",
            "cloudType": cloud,
            "gpuCount": 1,
            "gpuTypeIds": gpu_ids,
            "gpuTypePriority": "availability",
            "dataCenterPriority": "availability",
            "containerDiskInGb": disk,
            "volumeInGb": vol,
            "volumeMountPath": "/workspace",
            "ports": ["8888/http", "22/tcp"],
            "supportPublicIp": True,
            "interruptible": False,
            "env": {"PUBLIC_KEY": public_key},
        }
        if template_id:
            body["templateId"] = template_id
        else:
            body["imageName"] = image

        pod_id, status = _try_create(body, name)
        if pod_id:
            print(pod_id)  # stdout: captured by the workflow
            return 0
        if status is not None:
            worst_status = status
        print(f"create: {cloud} cloud yielded no pod; trying next option", file=sys.stderr)

    if not had_any_gpu_list:
        print(
            "create: could not determine any eligible GPU (catalog lookup failed "
            "and no valid GPU_TYPE_IDS provided)",
            file=sys.stderr,
        )
        return 2
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
