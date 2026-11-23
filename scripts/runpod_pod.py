#!/usr/bin/env python3
"""
runpod_pod.py - RunPod REST v2 control for the weekly discovery job.

Discovery CREATES A FRESH POD each run and TERMINATES it at the end. Creating
(rather than resuming a pinned pod) lets RunPod place the pod on any host with
capacity.

MIGRATED FROM REST v1 (retired 2026-11-15; rest.runpod.io stopped resolving).
Base URL is now https://api.runpod.io/v2. What that changed here:
  * Flat create body -> nested: imageName->image, gpuTypeIds->gpu.id,
    gpuCount->gpu.count, cloudType->cloud, containerDiskInGb->disk,
    dockerStartCmd->entrypoint+cmd. v2 REJECTS UNKNOWN BODY FIELDS WITH 422,
    so interruptible / supportPublicIp / gpuTypePriority / dataCenterPriority /
    volumeInGb / volumeMountPath are all gone.
  * A pod takes ONE GPU type and v2 does not fall back, so the capacity ladder
    is now an explicit loop here: every GPU id x every cloud, in order.
  * No persistent volume. v1's implicit 20GB /workspace is gone; the run clones
    fresh and scp's results back, so the ephemeral container `disk` is enough.
  * GET /pods returns {"pods":[...]} with cursor pagination.
  * desiredStatus -> status, which can now be ERROR (handled in `wait`).
  * SSH comes from pod.ssh.direct{host,port}; there is no public IP field.
  * start/stop go through POST /pods/{id}/action {"action": ...}.

`create` exit codes (unchanged contract):
  0  pod created (id on stdout)
  1  request rejected for a real reason (bad key / bad body) -> workflow fails
  3  no GPU obtained (capacity / 5xx / timeout)              -> workflow skips

Commands: create | wait | terminate | cleanup | describe | start | stop
stdlib only. Auth (unchanged by v2): Bearer ${RUNPOD_API_KEY}.

create env: POD_NAME, GPU_TYPE_IDS (comma list; optional preference/override),
POD_TEMPLATE_ID, POD_IMAGE, POD_CLOUD_TYPE (comma list, default "SECURE,COMMUNITY"),
CONTAINER_DISK_GB, POD_DATACENTER_IDS (comma list; empty = scheduler picks),
PUBLIC_KEY. disk = CONTAINER_DISK_GB + VOLUME_GB (v2 has no implicit volume).
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "https://api.runpod.io/v2"
TIMEOUT = 60.0
CREATE_TIMEOUT = 120.0
# Whole-ladder budget. 13 GPU ids x 2 clouds is 26 candidates; a capacity
# rejection is fast, but this stops a pathological run from eating the job.
CREATE_BUDGET = 900.0

USER_AGENT = "ai-risk-discovery/2.0 (+github-actions)"

DEFAULT_IMAGE = (
    "runpod/pytorch@sha256:2594f25beeef751aeebcc207ba4c45a382ba174655f01e15cbbfad0e2bdb5ef8"
)

# Start command for a bare image: guarantee sshd is up with our key, regardless
# of the image's default behaviour. Runs sshd in the foreground so the pod stays
# alive for us to SSH in. $PUBLIC_KEY is read from the pod's env at runtime.
# v2 carries this as entrypoint=["bash","-lc"] + cmd=[SSHD_BOOTSTRAP]; we never
# set startSsh, because RunPod's own sshd would not have these flags.
SSHD_BOOTSTRAP = (
    "set -e; "
    "mkdir -p /root/.ssh && chmod 700 /root/.ssh; "
    'printf "%s\\n" "$PUBLIC_KEY" >> /root/.ssh/authorized_keys; '
    "chmod 600 /root/.ssh/authorized_keys; "
    "command -v sshd >/dev/null 2>&1 || { apt-get update && "
    "DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends openssh-server; }; "
    "ssh-keygen -A; mkdir -p /run/sshd; "
    "exec /usr/sbin/sshd -D -e "
    "-o PasswordAuthentication=no -o KbdInteractiveAuthentication=no "
    "-o PubkeyAuthentication=yes -o PermitRootLogin=prohibit-password"
)

# Curated >=16GB GPUs, cheap/plentiful only. The pipeline holds llama3.1:8b
# (Q4_K_M, ~5GB) and llama3.2:3b (~2GB) - about 8GB resident - so a 16GB card
# is comfortable. Expensive H100/A100/B200 cards are deliberately excluded.
# v2 places ONE of these per request, so this list is the ladder's order: put
# the cheapest/most plentiful first. An id RunPod does not recognise costs one
# fast rejection and the loop moves on.
DEFAULT_GPU_IDS = [
    "NVIDIA GeForce RTX 4090",
    "NVIDIA L4",
    "NVIDIA RTX A4000",
    "NVIDIA RTX A4500",
    "NVIDIA RTX 4000 Ada Generation",
    "NVIDIA RTX 2000 Ada Generation",
    "NVIDIA GeForce RTX 3090",
    "NVIDIA RTX A5000",
    "NVIDIA A30",
    "NVIDIA A40",
    "NVIDIA L40",
    "NVIDIA L40S",
    "NVIDIA RTX A6000",
]

# How each documented POST /v2/pods status is treated by the ladder:
#   400  placement failed. RunPod documents that capacity exhaustion "currently
#        returns 400 with only a human-readable detail and no machine-readable
#        code" -> a CAPACITY MISS: try the next candidate.
#   401  token missing/invalid                    -> fatal (every candidate fails)
#   402  insufficient balance                     -> fatal
#   403  "lacks access ... such as a restricted pool" -> skip THIS candidate; fatal
#        only if every candidate is forbidden
#   413  body too large                           -> fatal (our body is constant)
#   422  validation failed: on gpu.id -> one stale card name, skip it;
#        on any other field -> fatal (our body is wrong)
#   429  rate limited                             -> back off, treat as transient
#   5xx  transient upstream failure               -> capacity/transient miss
FATAL_STATUSES = (401, 402, 413)
RATE_LIMIT_BACKOFF_S = 30

# Extra phrasing that marks a non-400 4xx as a placement/capacity problem.
_CAPACITY_WORDS = (
    "capacity",
    "could not be placed",
    "no instances",
    "instances available",
    "no longer any",
    "unavailable",
    "no gpu",
    "out of stock",
    "no machines",
)

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
    # noqa justification: BASE is the fixed https RunPod API constant.
    req = Request(f"{BASE}{path}", data=data, method=method, headers=headers)  # noqa: S310
    try:
        with urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed https host)
            _LAST_STATUS = getattr(r, "status", 200)
            txt = r.read().decode("utf-8")
            return json.loads(txt) if txt.strip() else {}
    except HTTPError as e:
        _LAST_STATUS = e.code
        _LAST_ERROR = e.read().decode("utf-8", "replace")
        print(
            f"RunPod {method} {path} -> HTTP {e.code}: {_err_summary(_LAST_ERROR)}", file=sys.stderr
        )
        return None
    except Exception as e:  # noqa: BLE001
        print(f"RunPod {method} {path} -> {type(e).__name__}: {e}", file=sys.stderr)
        return None


def _err_summary(text: str, limit: int = 300) -> str:
    """Condense a v2 RFC 9457 error body ({title, status, detail, errors}) to one line."""
    if not text:
        return ""
    try:
        d = json.loads(text)
    except (ValueError, TypeError):
        return text[:limit].replace("\n", " ")
    if not isinstance(d, dict):
        return text[:limit].replace("\n", " ")
    bits = [str(d[k]) for k in ("title", "detail") if d.get(k)]
    errs = d.get("errors")
    if isinstance(errs, list):
        for e in errs[:3]:
            if isinstance(e, dict):
                bits.append(" ".join(str(e[k]) for k in ("field", "detail", "message") if e.get(k)))
            elif e:
                bits.append(str(e))
    return (" | ".join(b for b in bits if b) or text[:limit]).replace("\n", " ")[:limit]


def _err_fields(text: str) -> list[str]:
    """Field names an RFC 9457 error body blames, e.g. ['gpu.id']."""
    try:
        d = json.loads(text)
    except (ValueError, TypeError):
        return []
    errs = d.get("errors") if isinstance(d, dict) else None
    if not isinstance(errs, list):
        return []
    out: list[str] = []
    for e in errs:
        if isinstance(e, dict):
            for k in ("field", "pointer", "path", "location"):
                if e.get(k):
                    out.append(str(e[k]))
    return out


def _is_gpu_id_rejection(text: str) -> bool:
    """True when RunPod rejected the GPU *name*, not the request shape."""
    fields = [f.lower() for f in _err_fields(text)]
    if fields:
        # Only gpu.id (the card NAME). A 422 on gpu.count etc. is a body bug.
        return all("gpu" in f and f.rstrip("/").endswith("id") for f in fields)
    low = text.lower()
    return "gpu.id" in low or "gpu id" in low or "gpu type" in low


def _looks_like_capacity(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in _CAPACITY_WORDS)


def _all_pods() -> list[dict]:
    """GET /pods, following v2 cursor pagination. v2 wraps the list in {"pods": [...]}."""
    pods: list[dict] = []
    cursor: str | None = None
    for _ in range(20):  # hard page cap; we only ever have a handful of pods
        path = f"/pods?cursor={cursor}" if cursor else "/pods"
        out = _api("GET", path)
        if isinstance(out, list):  # tolerate a bare list
            return [p for p in out if isinstance(p, dict)]
        if not isinstance(out, dict):
            break
        page = out.get("pods")
        if not isinstance(page, list):
            page = next(
                (out[k] for k in ("data", "items") if isinstance(out.get(k), list)),
                [],
            )
        pods += [p for p in page if isinstance(p, dict)]
        pg = out.get("pagination") or {}
        cursor = pg.get("nextCursor")
        if not pg.get("hasNextPage") or not cursor:
            break
    return pods


def _ids_by_name(name: str) -> list[str]:
    return [p["id"] for p in _all_pods() if p.get("name") == name and p.get("id")]


_PRIVATE_IP_PREFIXES = ("10.", "172.16.", "172.17.", "172.18.", "192.168.", "100.64.", "127.")


def _port_dicts(pod: dict) -> list[dict]:
    rt = pod.get("runtime") or {}
    out: list[dict] = []
    for cand in (rt.get("ports"), pod.get("portMappings"), pod.get("ports")):
        if isinstance(cand, list):
            out += [p for p in cand if isinstance(p, dict)]
    return out


def _ssh_endpoint(pod: dict) -> tuple[str, int] | None:
    """Public SSH endpoint, or None.

    v2 exposes pod.ssh = {proxy: {...}, direct: {...}}; `direct` is null until
    22/tcp has a public port assigned. We require `direct`: the proxy path would
    reach RunPod's own sshd, not the hardened one SSHD_BOOTSTRAP starts.
    """
    ssh = pod.get("ssh")
    if isinstance(ssh, dict):
        direct = ssh.get("direct")
        if isinstance(direct, dict):
            host, port = direct.get("host"), direct.get("port")
            if host and port:
                return str(host), int(port)
    # Fallback: runtime.ports[] carries the 22/tcp mapping and its public ip.
    for p in _port_dicts(pod):
        priv = p.get("privatePort") or p.get("PrivatePort")
        pub = p.get("publicPort") or p.get("PublicPort")
        ip = p.get("ip") or p.get("IP")
        flagged_public = p.get("isIpPublic") or p.get("isPublic") or p.get("public")
        if str(priv) != "22" or not pub or not ip:
            continue
        if flagged_public or not str(ip).startswith(_PRIVATE_IP_PREFIXES):
            return str(ip), int(pub)
    return None


def _tcp_open(host: str, port: int, timeout: float = 5.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _pod_status(pod: dict) -> str:
    """v2 reports the ACTUAL state in `status` (v1's desiredStatus is gone)."""
    return str(pod.get("status") or pod.get("desiredStatus") or "").upper()


def _is_running(pod: dict) -> bool:
    return _pod_status(pod) == "RUNNING"


def _post_create(body: dict, name: str) -> tuple[str | None, int | None, str]:
    """POST once. Returns (pod_id, http_status, error_body). v2 create returns 201."""
    out = _api("POST", "/pods", body, timeout=CREATE_TIMEOUT)
    status, err = _LAST_STATUS, _LAST_ERROR
    pod_id = None
    if isinstance(out, dict):
        pod_id = out.get("id") or (out.get("pod") or {}).get("id")
    # Recover an orphan ONLY when the POST outcome was ambiguous (transport
    # error / timeout / 5xx). A definite 4xx created nothing. Kept short (3x5s):
    # at 60s per candidate a RunPod 5xx incident would spend the whole budget
    # on SECURE and never reach COMMUNITY. Anything missed here is still
    # terminated by `cleanup --name` in the workflow's always() step.
    if not pod_id and (status is None or status >= 500):
        for _ in range(3):
            ids = _ids_by_name(name)  # overwrites globals; we saved them above
            if ids:
                pod_id = ids[0]
                print(f"create: recovered pod {pod_id} by name '{name}'", file=sys.stderr)
                break
            time.sleep(5)
    return pod_id, status, err


def _create_body(cloud: str, gpu_id: str, name: str) -> dict:
    """v2 CreatePodRequest. Unknown fields are rejected with 422, so keep this exact."""
    body: dict = {
        "name": name,
        "cloud": cloud,
        "gpu": {"id": gpu_id, "count": 1},
        # v1 gave 40GB container disk + a 40GB /workspace volume. v2 has no
        # implicit volume, and RunPod does not say whether the (large) image
        # counts against `disk`, so keep the same TOTAL rather than halve it.
        "disk": int(os.environ.get("CONTAINER_DISK_GB", "40"))
        + int(os.environ.get("VOLUME_GB", "40")),
        "ports": ["22/tcp"],  # v2 has NO default ports; 22/tcp is what gets us in
        "env": {"PUBLIC_KEY": os.environ.get("PUBLIC_KEY", "")},
    }
    dcs = [d.strip() for d in os.environ.get("POD_DATACENTER_IDS", "").split(",") if d.strip()]
    if dcs:
        body["dataCenterIds"] = dcs
    template_id = os.environ.get("POD_TEMPLATE_ID", "").strip()
    if template_id:
        body["templateId"] = template_id
    else:
        body["image"] = os.environ.get("POD_IMAGE", DEFAULT_IMAGE)
        body["entrypoint"] = ["bash", "-lc"]
        body["cmd"] = [SSHD_BOOTSTRAP]
    return body


def cmd_create() -> int:
    requested = [g.strip() for g in os.environ.get("GPU_TYPE_IDS", "").split(",") if g.strip()]
    gpu_ids = list(dict.fromkeys(requested + DEFAULT_GPU_IDS))  # preference first, then fallbacks
    name = os.environ.get("POD_NAME", "ai-risk-discovery")
    clouds = [
        c.strip().upper()
        for c in os.environ.get("POD_CLOUD_TYPE", "SECURE,COMMUNITY").split(",")
        if c.strip()
    ]

    # Preflight: one cheap call that tells "RunPod is unreachable / key is bad"
    # apart from "no capacity". Without it, a dead host (e.g. a retired API
    # base) has no HTTP status, looks like a capacity miss on every candidate,
    # and ends in a GREEN skip - exactly how the v1 retirement hid for a week.
    _api("GET", "/pods")
    if _LAST_STATUS is None:
        print(
            f"create: cannot reach the RunPod API at {BASE} (DNS/network/TLS). "
            f"This is NOT a capacity problem - check RunPod status and the API base URL.",
            file=sys.stderr,
        )
        return 1
    if _LAST_STATUS in (401, 403):
        print(
            f"create: RunPod rejected the API key (HTTP {_LAST_STATUS}). "
            f"Check the RUNPOD_API_KEY secret.",
            file=sys.stderr,
        )
        return 1

    deadline = time.time() + CREATE_BUDGET
    transport_errors = 0
    unexplained_4xx: int | None = None
    capacity_misses = 0
    forbidden = 0
    last_400 = ""
    stale_ids: list[str] = []
    attempts = 0
    print(
        f"create: v2 ladder over {len(clouds)} cloud(s) x {len(gpu_ids)} GPU id(s)",
        file=sys.stderr,
    )
    for cloud in clouds:
        for gpu_id in gpu_ids:
            if time.time() > deadline:
                print(
                    f"create: {CREATE_BUDGET:.0f}s budget spent after {attempts} attempts; stopping",
                    file=sys.stderr,
                )
                return 3
            attempts += 1
            pod_id, status, err = _post_create(_create_body(cloud, gpu_id, name), name)
            if pod_id:
                print(
                    f"create: landed {gpu_id} in {cloud} after {attempts} attempt(s)",
                    file=sys.stderr,
                )
                print(pod_id)  # stdout: captured by the workflow
                return 0
            print(
                f"create:   {cloud}/{gpu_id} -> {status} {_err_summary(err, 160)}", file=sys.stderr
            )

            if status == 422 and _is_gpu_id_rejection(err):
                # One stale card name - skip it, don't abort the ladder.
                if gpu_id not in stale_ids:
                    stale_ids.append(gpu_id)
                continue
            if status == 422:
                print(
                    "create: request rejected (HTTP 422) - the v2 body failed validation. "
                    "This is a CONFIG error, not capacity; the field is named above.",
                    file=sys.stderr,
                )
                return 1
            if status in FATAL_STATUSES:
                why = {
                    401: "RunPod rejected the API key - check the RUNPOD_API_KEY secret",
                    402: "RunPod account balance is insufficient - top up before re-running",
                    413: "request body too large - the create body itself is wrong",
                }[status]
                print(f"create: HTTP {status}: {why}. CONFIG error, not capacity.", file=sys.stderr)
                return 1
            if status == 403:
                forbidden += 1  # restricted pool for this key; try the next one
                continue
            if status == 429:
                capacity_misses += 1
                print(f"create: rate limited; backing off {RATE_LIMIT_BACKOFF_S}s", file=sys.stderr)
                time.sleep(RATE_LIMIT_BACKOFF_S)
                continue
            if status == 400:
                capacity_misses += 1  # documented: capacity exhaustion returns 400
                last_400 = _err_summary(err, 160)
                continue
            if status is None:
                transport_errors += 1
                if transport_errors >= 3 and transport_errors == attempts:
                    print(
                        "create: RunPod stopped answering mid-ladder (3 transport errors in a "
                        "row, nothing landed) - network, not capacity.",
                        file=sys.stderr,
                    )
                    return 1
                continue
            if status >= 500 or _looks_like_capacity(err):
                capacity_misses += 1
                continue
            if 400 <= status < 500:
                unexplained_4xx = status

    if stale_ids:
        print(
            f"create: RunPod did not recognise {len(stale_ids)} GPU id(s) - prune them "
            f"from DEFAULT_GPU_IDS: {', '.join(stale_ids)}",
            file=sys.stderr,
        )
    if forbidden:
        print(
            f"create: {forbidden} candidate(s) refused with 403 (restricted pool for this key)",
            file=sys.stderr,
        )
    if capacity_misses:
        print(
            f"create: no GPU could be placed ({capacity_misses} capacity miss(es) across "
            f"{attempts} attempts); run will be skipped. RunPod's last 400 said: "
            f"{last_400 or 'n/a'}",
            file=sys.stderr,
        )
        return 3
    if forbidden and forbidden + len(stale_ids) >= attempts:
        print(
            "create: every candidate was forbidden (403) - the API key lacks access to these "
            "GPU pools/clouds. CONFIG error, not capacity.",
            file=sys.stderr,
        )
        return 1
    if unexplained_4xx is not None:
        print(
            f"create: every candidate was rejected (last HTTP {unexplained_4xx}) and none "
            f"looked like capacity - treating as a request problem. Read the per-candidate "
            f"lines above.",
            file=sys.stderr,
        )
        return 1
    if stale_ids and len(stale_ids) == len(gpu_ids):
        print(
            "create: EVERY GPU id was rejected as unknown - the list is stale. Failing "
            "loudly rather than guessing at a (possibly expensive) substitute.",
            file=sys.stderr,
        )
        return 1
    print(
        f"create: no GPU available in any cloud right now ({attempts} candidates tried); "
        f"run will be skipped",
        file=sys.stderr,
    )
    return 3


def _redacted(pod: dict) -> dict:
    """Pod object with the env block removed (it carries PUBLIC_KEY)."""
    safe = {k: v for k, v in pod.items() if k != "env"}
    if "env" in pod:
        safe["env"] = "[redacted]"
    return safe


def cmd_wait(pod_id: str, timeout_s: int, interval_s: int) -> int:
    deadline = time.time() + timeout_s
    announced = False
    warned_proxy_only = False
    last_pod: dict | None = None
    while time.time() < deadline:
        pod = _api("GET", f"/pods/{pod_id}")
        if isinstance(pod, dict):
            last_pod = pod
            st = _pod_status(pod)
            # v2 added ERROR; without this we would poll a dead pod to timeout.
            if st in ("ERROR", "TERMINATED", "EXITED", "STOPPED"):
                print(f"pod {pod_id} reached terminal status {st}", file=sys.stderr)
                print("  last pod state (env redacted):", file=sys.stderr)
                print(json.dumps(_redacted(pod), indent=2)[:4000], file=sys.stderr)
                return 1
            # Don't hinge on the exact status string: the real readiness test is a
            # published endpoint that accepts TCP. Status only short-circuits ERROR.
            if _is_running(pod) and not announced:
                print("  pod running; waiting for its public SSH endpoint...", file=sys.stderr)
                announced = True
            ep = _ssh_endpoint(pod)
            if ep and _tcp_open(ep[0], ep[1]):
                print(f"{ep[0]} {ep[1]}")
                return 0
            if not ep and not warned_proxy_only:
                ssh = pod.get("ssh") if isinstance(pod.get("ssh"), dict) else {}
                if ssh.get("proxy") and not ssh.get("direct"):
                    print(
                        "  pod has only RunPod's SSH proxy, no direct 22/tcp mapping; "
                        "waiting (the proxy would bypass our hardened sshd)",
                        file=sys.stderr,
                    )
                    warned_proxy_only = True
        time.sleep(interval_s)
    print(f"timed out after {timeout_s}s waiting for public SSH on pod {pod_id}", file=sys.stderr)
    if last_pod is not None:
        # Only on failure, and with env (PUBLIC_KEY) stripped out.
        print("  last pod state (env redacted):", file=sys.stderr)
        print(json.dumps(_redacted(last_pod), indent=2)[:4000], file=sys.stderr)
    return 1


def cmd_terminate(pod_id: str) -> int:
    if not pod_id:
        print("terminate: no pod id - nothing to do")
        return 0
    out = _api("DELETE", f"/pods/{pod_id}")  # v2: 204 No Content
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
    """v2 consolidates lifecycle onto POST /pods/{id}/action."""
    out = _api("POST", f"/pods/{pod_id}/action", {"action": action})
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
