# Benchmark & Observability Report — Day 14

> Mọi con số phải lấy từ report JSON / CSV / screenshot thật, không ước lượng.

**Họ tên:** Nguyễn Nho Trọng
**Ngày chạy:** 25/11/2026
**Môi trường:** Windows PowerShell, Python 3.12.10 trong `.venv`; hai agent local trên cổng 8001 (v1) và 8002 (v2), dùng mock LLM. Mỗi lần load test gửi 300 request.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Ngưỡng mặc định của `load_test.py`; kiểm tra trải nghiệm của phần lớn request thay vì chỉ nhìn trung bình. |
| Error rate `/ask` | ≤ 2% | Ngưỡng mặc định của `load_test.py`; mock LLM có lỗi ngẫu nhiên nên cần đo tỉ lệ thực tế. |
| Accuracy trên golden dataset | ≥ 100% sau khi sửa KB | Mục tiêu quality gate cuối của CP7 là đúng đủ 23/23 câu và không regression. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.12 | 202.1 | 235.5 | 1701.9 | 1.00% | PASS |
| 10 | 39.33 | 191.7 | 237.0 | 1664.5 | 0.33% | PASS |
| 50 | 101.07 | 203.9 | 502.5 | 531.2 | 1.00% | FAIL (p95) |
| 100 | 62.55 | 587.5 | 2860.1 | 3549.7 | 0.33% | FAIL (p95) |

**Nhận xét:** RPS tăng từ 4.12 lên 101.07 khi concurrency tăng từ 1 lên 50, nhưng giảm còn 62.55 ở mức 100. Tăng tải không tạo tăng thông lượng tuyến tính: ở mức 100, thời gian chờ/điều phối request tăng mạnh (p50 587.5 ms, p95 2860.1 ms). Các lần chạy là mẫu ngắn 300 request và mock có độ trễ ngẫu nhiên, nên chỉ kết luận cho các phép đo này; cần lặp lại nếu muốn xác định năng lực ổn định của máy.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 204.7 | 450.2 | 512.3 |
| 0.03 (mặc định) | 251.4 | 461.7 | 1718.2 |
| 0.1 | 381.1 | 1697.1 | 1725.6 |

**Nhận xét:** Khi slow rate tăng từ 0 lên 0.03, p99 tăng từ 512.3 lên 1718.2 ms, trong khi p95 chỉ tăng 11.5 ms; p99 nhạy với một nhóm nhỏ request rất chậm. Ở mức 0.1, p95 tăng lên 1697.1 ms và SLO p95 ≤ 500 ms bị vi phạm, dù average chỉ 381.1 ms. Average che khuất trải nghiệm của nhóm request chậm; p95/p99 cho thấy phần đuôi phân phối. Cả ba lần chạy dùng concurrency 20 và 300 request; SLO tải lần lượt PASS, PASS, FAIL.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.35% (1/23) | 91.30% (21/23) | 100% (23/23) |
| Avg tokens / câu | 56.2 | 108.8 | 111.7 |
| Tổng cost (USD) | 0.000392 | 0.000758 | 0.000773 |
| Cost / câu đúng (USD) | 0.00039195 | 0.00003607 | 0.00003361 |
| Quality gate | FAIL (ngưỡng 80%) | PASS (ngưỡng 80%, không regression) | PASS (ngưỡng 100%, không regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry `jwt`/`api key` giải thích JWT là token có chữ ký và thời gian hết hạn. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry `kubernetes hpa`/`hpa` nêu ba loại metric để scale. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:** v2 thêm retrieval nên accuracy tăng từ 1/23 lên 21/23 trước sửa KB, rồi 23/23 sau sửa. Avg tokens tăng từ 56.2 lên 108.8 (111.7 sau sửa), tổng cost tăng từ $0.000392 lên $0.000758 ($0.000773 sau sửa), nhưng cost/câu đúng giảm từ $0.00039195 xuống $0.00003607 ($0.00003361 sau sửa). Độ trễ eval chỉ có 23 mẫu và chứa request chậm ngẫu nhiên; dùng bảng load test 300 request ở trên để đánh giá latency.

**Quality gate trong CI:** chạy `python eval/run_eval.py --url http://localhost:8001 --baseline reports/eval_v2.json --min-accuracy 0.8 --out reports/eval_v1_regression.json` sau khi khởi động agent v1. Lệnh thực tế trả exit code **1**: accuracy 1/23 và 20 câu từng đúng ở baseline v2 bị regression. Trong GitHub Actions, đặt lệnh eval thành một bước `run` sau bước khởi động agent và trước bước build/deploy; exit code khác 0 khiến job thất bại và có thể chặn merge khi job là required status check. Lần chạy v2 sau sửa KB với `--min-accuracy 1.0 --baseline reports/eval_v2.json` trả exit code **0**.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] [Dashboard Grafana khi đang có tải](screenshots/grafana-dashboard.png) — 30 Locust users, error rate khoảng 21% và p95 khoảng 1.9 giây.
- [x] [Trace chậm trong Jaeger](screenshots/jaeger-slow-trace.png) — `chat mock-llm-small` chiếm phần lớn thời gian.
- [x] [Trace lỗi trong Jaeger](screenshots/jaeger-error-trace.png) — HTTP 503; [JSON trace](06-lab-complete/benchmark-observability/production/benchmark-results/jaeger-error-trace.json) chứa event `exception` ở span `chat mock-llm-small`.
- [x] [Trang Alerts của Prometheus](screenshots/prometheus-alert-firing.png) — **cả hai alert** `AgentHighErrorRate` và `AgentHighLatencyP95` cùng firing.

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | 134.3 giây | Error rate `/ask` (đỏ, khoảng 21%) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | 195.1 giây | p95 latency `/ask` (đỏ, khoảng 1.9 giây) |
| C | `LLM_MODEL=mock-llm-large` | Chưa chạy | — | — |
| D | `docker pause` 1 instance | Chưa chạy | — | — |
| E | `AGENT_VERSION=v1` | Chưa chạy trong stack production; eval local ở CP7 đã phát hiện giảm chất lượng | — | — |

Hai thay đổi A và B được bật **cùng lúc**; ba agent được tạo lại từ 21:10:46 (+07:00), Locust web chạy 30 users liên tục. Prometheus ghi `activeAt=21:11:57` cho cả hai điều kiện; quan sát lần đầu `AgentHighErrorRate` firing lúc 21:13:00 và `AgentHighLatencyP95` firing lúc 21:14:01. Thời gian trong bảng tính từ thời điểm bắt đầu áp dụng cấu hình lúc 21:10:46, có gồm thời gian tạo lại agent và khởi động tải. [Timeline](06-lab-complete/benchmark-observability/production/benchmark-results/alert_timeline.csv) và [snapshot API](06-lab-complete/benchmark-observability/production/benchmark-results/prometheus_alerts_firing.json) lưu trạng thái thật; các thời điểm được poll mỗi 5 giây nên sai số quan sát tối đa khoảng 5 giây.

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Chạy eval định kỳ trên golden dataset và đặt quality gate trong CI trước khi deploy; theo dõi accuracy theo phiên bản agent. Metric hạ tầng như error rate hoặc p95 vẫn có thể bình thường khi agent v1 trả lời sai nội dung. Bài eval local ở CP7 cho thấy v1 chỉ đúng 1/23, còn v2 sau sửa KB đúng 23/23.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: `425e8fffa4fa08356c9327a544e01de6`
- Tổng thời gian: 1718.7 ms
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (1691.3 ms, 98.4%)
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts":"2026-11-25T14:15:08.837238+00:00","level":"INFO","service":"observable-agent","instance":"d67abb3b7132","event":"http_request","trace_id":"425e8fffa4fa08356c9327a544e01de6","span_id":"dfca8351d5708620","request_id":"ae2944da1357","method":"POST","route":"/ask","status":200,"ms":1718.2}
```

Trace lỗi: `5f1962fda46352913c9999af4b533d3c` trả HTTP 503. Span `chat mock-llm-small` có event `exception`, type `utils.mock_llm.LLMError` và message `Upstream LLM error: 503 Service Unavailable (mock)`.

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 61.75 | 190 | 230 | 1700 | 70/7162 (0.98%) |
| 3 | 61.83 | 190 | 220 | 1700 | 73/7168 (1.02%) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

Với cùng 100 Locust users, tăng từ 1 lên 3 instance làm RPS `/ask` đổi từ 61.75 lên 61.83 (chênh 0.08 req/s), p95 từ 230 xuống 220 ms. Chênh lệch rất nhỏ, chưa cho thấy cải thiện đáng kể; p99 ở cả hai lượt là 1700 ms do mock LLM có request chậm. Agent dùng `asyncio.sleep` để mô phỏng LLM, còn Locust giới hạn 100 users và thời gian chờ 0.5–2 giây giữa các request, nên tăng replica không tự tạo thêm tải hay giảm độ trễ upstream. Số liệu chỉ phản ánh hai lượt chạy 2 phút này, chưa xác định ngưỡng chịu tải tối đa.

---

## 6. Kết luận

- 3 điều rút ra từ các phép đo:
  1. Ở mức slow rate 0.03, p99 tăng mạnh trước p95; average có thể che khuất request chậm. Khi slow rate 0.1, p95 vượt SLO dù average vẫn dưới 500 ms.
  2. Retrieval giúp eval tăng từ 1/23 lên 23/23 sau sửa KB; tổng token và cost tăng, nhưng cost trên mỗi câu đúng giảm.
  3. Tăng từ 1 lên 3 agent với cùng 100 Locust users không tăng RPS đáng kể. Trace cho thấy mock LLM chiếm phần lớn thời gian của request chậm; cần đo thêm ở tải cao hơn trước khi kết luận về giới hạn hạ tầng.
- Nếu đưa lên production thật, nên thêm metric và alert cho **HTTP 5xx/504 tại Nginx** cùng một synthetic check gọi `/ask` từ bên ngoài. Lỗi ở load balancer có thể không xuất hiện trong counter của agent. Thêm quality gate eval sau mỗi thay đổi prompt/model/KB để phát hiện lỗi nội dung mà metric hạ tầng không thấy.
