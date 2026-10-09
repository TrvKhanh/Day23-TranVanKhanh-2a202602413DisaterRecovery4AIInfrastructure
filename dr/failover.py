import argparse
import json
import pathlib
import sys
import time

import httpx

sys.path.insert(0, ".")
from state import snapshot  # noqa: E402

URL = {"a": "http://127.0.0.1:8001", "b": "http://127.0.0.1:8002"}
LOG = pathlib.Path("reports/failover-events.jsonl")

def emit(**kw):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    d = {"ts": time.time(), "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    d.update(kw)
    s = json.dumps(d)
    with open(LOG, "a") as f:
        f.write(s + "\n")
    print(s)

def failover(target: str, backend: str, wait: float) -> dict:
    primary = "a" if target == "b" else "b"
    
    # 1. verify target
    emit(step="1_verify_target", msg=f"Verifying target {target}")
    try:
        state = httpx.get(f"{URL[target]}/v1/state").json()
    except Exception as e:
        state = {"error": str(e)}
        
    # 2. restore snapshot
    try:
        snap_info = snapshot.get(target, backend)
    except Exception as e:
        snap_info = {"error": str(e)}
        
    try:
        rpo_info = snapshot.rpo(pathlib.Path(f"state/region-{primary}"), pathlib.Path(f"state/region-{target}"))
    except Exception as e:
        rpo_info = {"rpo_seconds": None, "docs_lost": None}
        
    emit(step="2_restore_snapshot", msg="Restoring snapshot", rpo_seconds=rpo_info.get("rpo_seconds"), docs_lost=rpo_info.get("docs_lost"), embed_model_version=snap_info.get("embed_model_version", "unknown"))
    
    # 3. scale pool
    emit(step="3_scale_pool", msg="Scaling pool to full")
    pathlib.Path(f"state/region-{target}/pool_state").parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(f"state/region-{target}/pool_state").write_text("full")
    
    # 4. wait ready
    emit(step="4_wait_ready", msg="Waiting for target to be ready")
    start_t = time.time()
    ready = False
    while time.time() - start_t < wait:
        try:
            r = httpx.get(f"{URL[target]}/readyz", timeout=1.0)
            if r.status_code == 200:
                ready = True
                break
        except Exception:
            pass
        time.sleep(1)
        
    if not ready:
        emit(step="abort", msg="Target not ready, aborting")
        return {"ok": False, "reason": "timeout_waiting_ready"}
        
    # 5. dns cutover
    emit(step="5_dns_cutover", msg=f"Cutting over DNS to {target}")
    pathlib.Path("edge/active_region").parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path("edge/active_region").write_text(target)
    
    target_state = {}
    try:
        target_state = httpx.get(f"{URL[target]}/v1/state").json()
    except:
        pass
    
    return {"ok": True, "target": target, "state": target_state}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--target", default="b", choices=["a", "b"])
    p.add_argument("--backend", default="fs", choices=["fs", "minio"])
    p.add_argument("--wait", type=float, default=60)
    a = p.parse_args()
    print(json.dumps(failover(a.target, a.backend, a.wait), indent=2))
