# Runbook 1 trang — Region chính down

Runbook phải chạy được lúc 3h sáng bởi người KHÔNG viết nó. Mỗi bước: lệnh copy-paste
được + cách biết bước đó xong.

| # | Bước | Lệnh | Biết là xong khi | Ai làm |
|---|---|---|---|---|
| 1 | Xác nhận outage | `python chaos/kill_region.py status` | `a.alive=false` 3 lần liên tiếp | on-call |
| 2 | Mở incident + bấm giờ RTO | `python dr/runbook.py` | ts ghi vào `reports/runbook-run.jsonl` | on-call |
| 3 | Restore state ở region phụ | `python state/snapshot.py get --region b --backend fs` | thay output co rpo_seconds | on-call |
| 4 | Scale pool warm→full | `echo full > state/region-b/pool_state` | `/readyz` của b trả 200 | on-call |
| 5 | DNS/LB cutover | `echo b > edge/active_region` | `curl localhost:8080/edge/state` cho `active_region=b` | on-call |
| 6 | Verify golden signals | `curl ...` | p95 < 100ms, error rate < 1% | on-call |
| 7 | Đo RTO + postmortem | `python tools/measure_rto.py --loadgen reports/drill-2-withdr.jsonl` | `rto_verdict` != null | on-call |

**Rollback (failover ngược):** điều kiện nào thì trả traffic về region A? Ai quyết định?
Khi region A on dinh tro lai tren 1h. Do Manager quyet dinh.
