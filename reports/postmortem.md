# Postmortem — DR Drill Lab 23

Theo đúng template §4 "Sau Failover: Blameless Postmortem". Blameless: câu hỏi là
"hệ thống/process nào cho phép chuyện này", không phải "ai làm sai".

## 1. Timeline (mọi dòng phải có evidence path:line)

| ISO time | Sự kiện | Evidence |
|---|---|---|
| 2026-10-09T17:11:17 | outage bắt đầu | `chaos/chaos-events.jsonl:2` |
| 2026-10-09T17:11:17 | user đầu tiên bị ảnh hưởng | `reports/drill-2-withdr.jsonl:20` |
| 2026-10-09T17:11:17 | health check alert | `reports/health-events.jsonl:1` |
| 2026-10-09T17:11:17 | operator confirm cutover | `reports/failover-events.jsonl:1` |
| 2026-10-09T17:11:17 | resolved (request đầu tiên OK từ region phụ) | `reports/drill-2-withdr.jsonl:60` |

## 2. RTO/RPO đo được vs mục tiêu — gap ở bước nào?

- RTO mục tiêu: 300s · đo được: `28.9s` · gap: `0s`
- RPO mục tiêu: 300s · đo được: `12.5s` (`4` doc bị mất) · gap: `0s`
- **Bước tốn nhiều giây nhất:** `Health check` — vì sao? Vi threshold lon

## 3. Root cause (5 whys)

Không phải "vì tôi chạy chaos script". Câu hỏi: *nếu đây là outage thật, bước nào
trong runbook của tôi sẽ thất bại?*
Vi khong thiet ke multi-region hoan hao ngay tu dau.

## 4. Action items (có owner + deadline)

| # | Action | Owner | Deadline | Giảm RTO/RPO bao nhiêu giây |
|---|---|---|---|---|
| 1 | Giam TTL | Dev | 2024 | 5s |
| 2 | Giam Healthcheck interval | Dev | 2024 | 10s |

## 5. Ba câu hỏi bắt buộc trả lời

1. `interval × threshold` của bạn là bao nhiêu giây? Nó chiếm bao nhiêu % RTO?
15s, chiem khoang 50% RTO
2. Nếu hạ interval xuống 1s, RTO giảm mấy giây — và bạn trả giá gì (§4 flapping)?
Giam 12s, de bi flapping.
3. Nếu outage kéo dài 6 giờ và region chính mất dữ liệu vĩnh viễn, `docs_lost` của
   bạn có nghĩa gì với khách hàng?
Mat 4 documents ma khach hang da upload, phai thong bao ho upload lai.
