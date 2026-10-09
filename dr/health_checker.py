import argparse
import json
import pathlib
import time

import httpx

URL = {"a": "http://127.0.0.1:8001", "b": "http://127.0.0.1:8002"}

def probe(region: str, timeout: float) -> tuple[bool, str]:
    try:
        r = httpx.get(f"{URL[region]}/readyz", timeout=timeout)
        if r.status_code == 200:
            return True, "ready"
        else:
            return False, f"status {r.status_code}"
    except Exception as e:
        return False, str(e)

def run(interval: float, timeout: float, threshold: int, duration: float, out: pathlib.Path):
    start_t = time.time()
    state = {"a": "HEALTHY", "b": "HEALTHY"}
    consecutive_fails = {"a": 0, "b": 0}
    out.parent.mkdir(parents=True, exist_ok=True)
    
    with open(out, "a") as f:
        while time.time() - start_t < duration:
            for region in ["a", "b"]:
                is_ready, reason = probe(region, timeout)
                
                if is_ready:
                    consecutive_fails[region] = 0
                    if state[region] == "UNHEALTHY":
                        state[region] = "HEALTHY"
                        ev = {
                            "ts": time.time(),
                            "event": "state_change",
                            "region": region,
                            "to": "HEALTHY",
                            "reason": reason,
                            "interval_s": interval,
                            "threshold": threshold,
                            "consecutive_fails": consecutive_fails[region]
                        }
                        f.write(json.dumps(ev) + "\n")
                        f.flush()
                else:
                    consecutive_fails[region] += 1
                    if consecutive_fails[region] >= threshold and state[region] == "HEALTHY":
                        state[region] = "UNHEALTHY"
                        ev = {
                            "ts": time.time(),
                            "event": "state_change",
                            "region": region,
                            "to": "UNHEALTHY",
                            "reason": reason,
                            "interval_s": interval,
                            "threshold": threshold,
                            "consecutive_fails": consecutive_fails[region]
                        }
                        f.write(json.dumps(ev) + "\n")
                        f.flush()
            time.sleep(interval)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--interval", type=float, default=5.0)
    p.add_argument("--timeout", type=float, default=2.0)
    p.add_argument("--threshold", type=int, default=3)
    p.add_argument("--duration", type=float, default=300)
    p.add_argument("--out", default="reports/health-events.jsonl")
    a = p.parse_args()
    run(a.interval, a.timeout, a.threshold, a.duration, pathlib.Path(a.out))
