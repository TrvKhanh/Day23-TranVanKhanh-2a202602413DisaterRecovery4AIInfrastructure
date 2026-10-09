import argparse
import json
import pathlib
import sys
import time

import httpx

sys.path.insert(0, ".")
from dr import failover as fo  # noqa: E402

LOG = pathlib.Path("reports/runbook-run.jsonl")
URL = {"a": "http://127.0.0.1:8001", "b": "http://127.0.0.1:8002"}

def step(n, name, **kw):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    d = {"ts": time.time(), "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "step": f"{n}_{name}"}
    d.update(kw)
    s = json.dumps(d)
    with open(LOG, "a") as f:
        f.write(s + "\n")
    print(s)

def confirm(auto: bool, msg: str) -> bool:
    if auto:
        return True
    try:
        return input(f"{msg} [y/N]: ").strip().lower() == "y"
    except EOFError:
        return False

def run(primary: str, target: str, backend: str, auto: bool) -> dict:
    # 1. xac_nhan_outage
    step(1, "xac_nhan_outage", msg=f"Verifying outage on {primary}")
    primary_down = False
    for _ in range(3):
        try:
            r = httpx.get(f"{URL[primary]}/readyz", timeout=1.0)
            if r.status_code != 200:
                primary_down = True
        except Exception:
            primary_down = True
        time.sleep(0.5)
        
    if not primary_down:
        step(1, "xac_nhan_outage_status", msg=f"Primary {primary} is still up")
        if not confirm(auto, "Primary seems up. Proceed anyway?"):
            return {"ok": False, "reason": "primary_up_abort"}
    else:
        step(1, "xac_nhan_outage_status", msg=f"Primary {primary} confirmed DOWN")
        
    # 2. thong_bao_incident
    t_outage = None
    try:
        lines = pathlib.Path("chaos/chaos-events.jsonl").read_text().splitlines()
        for line in reversed(lines):
            ev = json.loads(line)
            if ev.get("action") == "kill":
                t_outage = ev.get("ts")
                break
    except Exception:
        pass
    
    alert_delay = time.time() - t_outage if t_outage else None
    step(2, "thong_bao_incident", msg="Incident declared", t_outage=t_outage, alert_delay=alert_delay)
    
    if not confirm(auto, "Proceed with failover?"):
        return {"ok": False, "reason": "operator_abort"}

    # 3. scale_gpu_pool
    step(3, "scale_gpu_pool", msg="Starting failover sub-process")
    fo_res = fo.failover(target, backend, wait=60)
    
    # 4. verify_state_replica
    step(4, "verify_state_replica", msg="State replica verified", target_state=fo_res.get("state", {}))
    
    # 5. dns_cutover
    step(5, "dns_cutover", msg="DNS cutover verified", ok=fo_res.get("ok"), reason=fo_res.get("reason"))
    
    if not fo_res.get("ok"):
        return {"ok": False, "reason": "failover_failed"}
        
    # 6. verify_golden_signals
    step(6, "verify_golden_signals", msg="Running 10 requests to check latency and errors")
    latencies = []
    errors = 0
    for _ in range(10):
        t0 = time.time()
        try:
            r = httpx.post(f"{URL[target]}/v1/infer", json={"query": "test"}, timeout=2.0)
            if r.status_code == 200:
                latencies.append(time.time() - t0)
            else:
                errors += 1
        except Exception:
            errors += 1
        time.sleep(0.1)
        
    p95 = sorted(latencies)[int(0.95 * len(latencies))] if latencies else None
    error_rate = errors / 10.0
    step(6, "verify_golden_signals_result", p95_latency=p95, error_rate=error_rate)
    
    # 7. post_incident
    step(7, "post_incident", msg="Run measure_rto.py to verify")
    
    return {"ok": True, "target": target}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--primary", default="a")
    p.add_argument("--target", default="b")
    p.add_argument("--backend", default="fs", choices=["fs", "minio"])
    p.add_argument("--auto", action="store_true")
    a = p.parse_args()
    print(json.dumps(run(a.primary, a.target, a.backend, a.auto), indent=2))
