# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production (CP1)

### Exercise 1.1: Anti-patterns found

Đối chiếu `01-localhost-vs-production/develop/app.py`:

1. `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"`: đưa secret vào mã nguồn làm lộ key nếu đẩy repo công khai. Đây là key giả của bài lab, nhưng cách viết vẫn là anti-pattern.
2. `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`: hardcode cả thông tin đăng nhập lẫn địa chỉ database; địa chỉ `localhost` cũng không dùng được cho database nằm ở dịch vụ khác.
3. `DEBUG = True` và `reload=True`: bật chế độ phục vụ phát triển trong môi trường chạy thật, có thể làm lộ thông tin và khởi động lại tiến trình khi file thay đổi.
4. `port=8000` và `host="localhost"`: port không đọc từ biến môi trường; host chỉ nhận kết nối trên máy chạy app nên container hoặc nền tảng cloud khó truy cập từ bên ngoài.
5. Không có endpoint `/health` hay `/ready`: nền tảng triển khai không có tín hiệu HTTP để kiểm tra app còn sống hoặc đã sẵn sàng nhận request.
6. `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`: ghi secret ra log; các lệnh `print()` khác cũng thiếu cấu trúc để lọc và tổng hợp log.
7. Không có xử lý vòng đời ứng dụng khi nhận tín hiệu tắt: không có chỗ đóng kết nối hoặc dọn tài nguyên trước khi tiến trình dừng.

### Exercise 1.2: Run the basic version

**Kết quả chạy thực tế:** Sau khi cài dependencies, app khởi động với Uvicorn trên `http://localhost:8000`. Terminal Windows của lần chạy đầu dùng mã hóa `cp1252`, nên câu trả lời tiếng Việt trong lệnh `print()` gây `UnicodeEncodeError` và request trả HTTP 500. Chạy lại với `PYTHONIOENCODING=utf-8` thì request thành công. Đây cũng là một ví dụ về sự khác biệt giữa môi trường local và production.

Lệnh kiểm tra trong `01-localhost-vs-production/develop/`:

```powershell
python -m pip install -r requirements.txt
$env:PYTHONIOENCODING = 'utf-8'
python app.py
```

Ở terminal PowerShell thứ hai:

```powershell
curl.exe -i -X POST "http://localhost:8000/ask?question=Hello"
```

Output đã nhận:

```text
HTTP/1.1 200 OK
content-type: application/json

{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Bản develop nhận `question` qua query string; gửi JSON như ví dụ cũ trong `CODE_LAB.md` sẽ nhận HTTP 422. Nội dung câu trả lời có thể khác giữa các lần chạy vì mock LLM chọn ngẫu nhiên.

### Exercise 1.3: Develop vs Production

| Feature | Develop | Production | Tại sao quan trọng? |
| --- | --- | --- | --- |
| Config và secret | Key, database URL, debug và port ghi trực tiếp trong `app.py` | `config.py` đọc các biến môi trường, kiểm tra `AGENT_API_KEY` khi `ENVIRONMENT=production` | Đổi cấu hình theo môi trường mà không sửa code hay commit secret |
| Địa chỉ phục vụ | `host="localhost"`, `port=8000` | `HOST` mặc định `0.0.0.0`, `PORT` đọc từ môi trường | Container và cloud có thể định tuyến request tới app |
| Chế độ debug | `reload=True` cố định | `reload=settings.debug`, mặc định tắt | Tránh tự khởi động lại và hạn chế hành vi dành cho phát triển |
| Health/readiness | Không có | `GET /health`, `GET /ready` | Phân biệt tiến trình còn sống và đã sẵn sàng nhận traffic |
| Logging | `print()`, còn in cả key | Log có cấu trúc JSON, không in secret | Dễ tìm lỗi và giảm nguy cơ lộ key trong log |
| Shutdown | Không khai báo xử lý vòng đời | `lifespan` có bước startup/shutdown và log khi nhận SIGTERM | Có chỗ dọn tài nguyên khi dừng app |

**Giải thích:** Hardcode secret khiến bất kỳ ai đọc được code hoặc lịch sử Git đều có thể lấy key. Health check cho nền tảng biết tiến trình còn phản hồi; readiness cho biết đã có thể nhận request. Graceful shutdown là cho app hoàn tất hoặc dọn các việc đang xử lý trước khi dừng. Code production mẫu minh họa vòng đời và log shutdown, nhưng không chứng minh mọi request đang chạy đều được hoàn tất trong mọi trường hợp.

**Kiểm tra bản production mẫu:** App khởi động trên `0.0.0.0:8000`; `GET /health` trả HTTP 200 với `"status":"ok"`, `GET /ready` trả HTTP 200 với `"ready":true`, và `POST /ask` với JSON `{"question":"Hello"}` trả HTTP 200. Kiểm tra ở cấu hình mặc định `ENVIRONMENT=development` và dùng mock LLM. Đã dừng cả hai server sau khi thử.

## Part 2: Docker (CP2)

### Exercise 2.1: Dockerfile questions

1. Base image của bản develop là `python:3.11`.
2. Working directory trong container là `/app`.
3. `COPY requirements.txt` trước khi copy source giúp Docker tái sử dụng layer cài dependencies khi chỉ source thay đổi; `pip --no-cache-dir` là cơ chế khác, chỉ bỏ cache tải gói của pip.
4. `CMD` là lệnh mặc định có thể thay khi gọi `docker run IMAGE <command>`. `ENTRYPOINT` xác định chương trình chính, còn tham số từ `docker run` thường được nối sau nó; có thể dùng hai chỉ thị cùng nhau để đặt chương trình và đối số mặc định.

### Exercise 2.2–2.3: Build, run, image size

Hai lệnh build từ gốc repo đã thành công trên Docker Desktop của học viên. Kết quả `docker images my-agent`:

| Image | DISK USAGE | CONTENT SIZE |
| --- | ---: | ---: |
| `my-agent:develop` | 1,67 GB | 426 MB |
| `my-agent:advanced` | 240 MB | 57,4 MB |

Tính theo cùng cột **DISK USAGE** (đổi 1,67 GB ≈ 1670 MB): image advanced nhỏ hơn khoảng `(1670 - 240) / 1670 × 100 = 85,6%`. Đây là số hiển thị đã làm tròn của Docker, nên tỷ lệ cũng là xấp xỉ.

Đã chạy `my-agent:develop` với `-p 8000:8000`. Sau khi chờ app khởi động 5 giây, `docker logs` cho thấy Uvicorn sẵn sàng trên `0.0.0.0:8000`; `GET /health` trả HTTP 200 với `{"status":"ok","uptime_seconds":5.2,"container":true}`; `POST /ask?question=What%20is%20Docker` trả HTTP 200 với câu trả lời mock về container. Container đã được dừng bằng `docker stop`. Lần thử gọi ngay sau `docker run` trả `Empty reply from server` vì app chưa sẵn sàng; lần thử sau thời gian chờ đã thành công.

Dockerfile advanced có stage `builder` cài `gcc`, `libpq-dev` và Python packages; stage `runtime` dùng `python:3.11-slim`, chỉ copy packages và source, rồi chạy dưới user không phải root. Image cuối không mang theo build tools của stage đầu.

### Exercise 2.4: Compose stack

Sơ đồ theo `02-docker/production/docker-compose.yml` và `nginx/nginx.conf`:

```text
Client → Nginx (:80) → Agent (:8000)
                         ├→ Redis (:6379; URL được cấu hình)
                         └→ Qdrant (:6333; URL được cấu hình)
```

Compose tạo bốn service `nginx`, `agent`, `redis`, `qdrant` trên mạng `internal`; chỉ Nginx mở cổng cho host. Agent chỉ khởi động sau khi Redis và Qdrant đạt health check. Việc ứng dụng có thực sự gọi Redis/Qdrant ở bản mẫu cần đối chiếu code `main.py`; sơ đồ trên thể hiện cấu hình kết nối, không phải bằng chứng đã gọi dịch vụ.

Đã chạy stack với `docker compose -p k5-day14-docker up -d --build`. `docker compose ps` cho thấy Redis, Qdrant và agent ở trạng thái healthy, Nginx đang chạy. Request gửi ngay khi agent còn `health: starting` trả HTTP 502; sau khi đợi agent healthy, `GET http://localhost/health` qua Nginx trả **HTTP 200**, JSON có `"status":"ok"`, và `POST http://localhost/ask` trả câu trả lời mock. Output PowerShell hiển thị dấu tiếng Việt không đúng do encoding của terminal, nhưng request thành công.

## Part 3: Cloud Deployment (CP6)

### Exercise 3.1: Railway

Đã chọn Railway và deploy **`06-lab-complete/`** bằng `railway up .\06-lab-complete --path-as-root --service agent`, không deploy app mẫu ở `03-cloud-deployment/`. Railway project có service `agent` và `Redis`; Redis đạt trạng thái `SUCCESS`. Agent đã build và khởi động, lắng nghe cổng 8080 do nền tảng cấp. URL public: **https://agent-production-fe2e5842.up.railway.app**.

Bốn lệnh kiểm tra từ PowerShell với body JSON `{"question":"Hello"}` trả về đúng thứ tự:

```text
GET  /health             200
GET  /ready              200
POST /ask (không key)    401
POST /ask (key hợp lệ)   200
```

`AGENT_API_KEY` được đặt bằng biến môi trường của service; giá trị thật không được ghi vào repo, báo cáo hoặc ảnh. Lệnh kiểm tra có thể chạy lại từ `DEPLOYMENT.md`. Ảnh minh chứng đã lưu tại [dashboard](screenshots/dashboard.png), [deployment thành công](screenshots/running.png) và [bốn mã HTTP](screenshots/test.png).

### So sánh cấu hình Railway và Render

| Nội dung | `railway.toml` | `render.yaml` | Ý nghĩa |
| --- | --- | --- | --- |
| Build | `builder = "DOCKERFILE"`, `dockerfilePath = "Dockerfile"` | `runtime: docker`, `dockerfilePath: ./Dockerfile` | Cả hai build image từ Dockerfile của Part 6, nhưng dùng cú pháp riêng của nền tảng. |
| Health check | `healthcheckPath = "/health"` | `healthCheckPath: /health` | Nền tảng kiểm tra tiến trình agent qua liveness endpoint. |
| Biến bí mật | Đặt trong Railway Variables | `generateValue: true` cho `AGENT_API_KEY`; `sync: false` cho `REDIS_URL` | Secret được cấp ở nền tảng, không ghi giá trị thật vào Git. |
| Redis | Tạo Redis service cùng project, đặt `REDIS_URL` của agent tham chiếu URL nội bộ | Tạo Render Key Value và đặt `REDIS_URL` cho web service | `/ready` chỉ trả 200 khi agent kết nối Redis thành công. |

### Exercise 3.3: Cloud Run pipeline (đọc cấu hình, không deploy)

`cloudbuild.yaml` định nghĩa thứ tự `test → build → push → deploy`: cài dependencies và chạy pytest trước, sau đó build Docker image gắn tag commit SHA và `latest`. Build xong mới push image lên registry; bước cuối deploy tag commit SHA lên Cloud Run ở `asia-southeast1`, với cấu hình số instance, RAM, CPU, timeout và secret từ Secret Manager. `service.yaml` mô tả service Cloud Run dưới dạng YAML: ingress public, giới hạn scale/concurrency, biến môi trường và probe `/health`/`/ready`. Đây là phân tích file mẫu, không phải bằng chứng đã chạy GCP.

## Part 4: API Security (CP3)

### Exercise 4.1: API key

Trong `04-api-gateway/develop/app.py`, `verify_api_key` đọc header `X-API-Key` bằng `APIKeyHeader`, so với biến môi trường `AGENT_API_KEY`, rồi được gắn vào `/ask` bằng `Depends`. Thiếu key trả 401; key sai trả 403 ở bản mẫu. Muốn đổi key thì đặt lại biến môi trường trên service và khởi động lại app; key trong ví dụ chỉ dùng cho lab.

Đã chạy bản develop với `AGENT_API_KEY=secret-key-123`: request `POST /ask` không có key trả **HTTP 401**; request có key đúng trả **HTTP 200**. Không lưu key vào output bài nộp.

### Exercise 4.2–4.3: JWT và rate limit

Code bản production cấp token tại `POST /auth/token`, xác minh chữ ký HS256 và hạn dùng 60 phút. Demo user `student` có giới hạn 10 request trong 60 giây; `teacher` dùng vai trò admin có giới hạn 100 request trong 60 giây. Limiter dùng deque timestamp trong RAM theo cửa sổ trượt, nên không chia sẻ state giữa nhiều worker.

Đã chạy bản production trên cổng 8000 và gửi request thật. Kết quả mã HTTP (token không được in ra):

```text
POST /ask không có Authorization: 401
POST /auth/token với tài khoản demo student: 200, token_received=True
12 lần POST /ask với Bearer token:
200,200,200,200,200,200,200,200,200,200,429,429
```

Vòng lặp tự chạy thấy **429 ở request thứ 11**; giới hạn của user `student` là 10 request/60 giây. Server thử nghiệm đã được dừng.

Các đoạn output `curl.exe -i` thực tế, chỉ giữ header và body liên quan; không in token:

```http
HTTP/1.1 401 Unauthorized
content-type: application/json
{"detail":"Authentication required. Include: Authorization: Bearer <token>"}

HTTP/1.1 200 OK
content-type: application/json
{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":9,"budget_remaining_usd":1.8e-05}}

HTTP/1.1 429 Too Many Requests
retry-after: 59
content-type: application/json
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### Exercise 4.4: Cost guard

`04-api-gateway/production/cost_guard.py` lưu số token và số tiền theo user/ngày trong RAM; có ngưỡng $1/ngày cho mỗi user và $10/ngày toàn hệ thống. Gọi `check_budget` trước request để chặn khi đã đạt ngưỡng, rồi `record_usage` sau khi có kết quả để cộng chi phí. Rate limit chặn số lần gọi trong một khoảng thời gian; cost guard chặn tổng tiền, nên cả hai cần thiết. Nếu triển khai nhiều instance, chuyển số liệu usage sang Redis/DB và cộng dồn theo cách nguyên tử để các instance cùng thấy một ngân sách.

## Part 5: Scaling & Reliability (CP4)

### Exercise 5.1: Health and readiness

Đã chạy `05-scaling-reliability/develop/app.py`. `GET /health` trả HTTP 200 với `status: ok`; `GET /ready` trả HTTP 200 với `ready: true`. `/health` cho biết tiến trình đang phản hồi; `/ready` cho biết đã khởi tạo xong để nhận request. Nếu dependency quan trọng hỏng, readiness nên trả 503 để load balancer tạm ngừng chuyển traffic vào instance, còn liveness vẫn có thể trả 200.

### Exercise 5.2: Graceful shutdown

Bản develop dùng `lifespan` để đặt `_is_ready = False` lúc shutdown và đợi bộ đếm `_in_flight_requests` về 0, tối đa 30 giây. Bộ đếm được cập nhật trong middleware. Đã dừng server sau khi kiểm tra endpoint; chưa xác minh kịch bản SIGTERM khi một request đang chạy trên WSL/Docker.

### Exercise 5.3–5.5: Stateless and load balancing

Bản production cấu hình agent và Redis trên cùng mạng Docker, Nginx nhận request ở cổng 8080 và chuyển tới agent. Redis giữ lịch sử session để các replica truy cập cùng một state; lưu history trong biến RAM của từng replica sẽ làm request sau không thấy dữ liệu của request trước nếu được chuyển sang replica khác.

Đã chạy `docker compose -p k5-day14-scaling up -d --build --scale agent=3`. `docker compose ps` cho thấy ba agent và Redis đều **healthy**, Nginx đang chạy. Lần gọi `test_stateless.py` ngay lúc agent còn `health: starting` gặp HTTP 502; chạy lại sau khi các agent healthy thì thành công:

```text
Total requests: 5
Instances used: {'instance-1e601d', 'instance-4bf4c4', 'instance-623298'}
Total messages: 10
Session history preserved across all instances via Redis!
```

Năm request được phục vụ bởi ba instance khác nhau, nhưng history vẫn có đủ năm cặp câu hỏi/câu trả lời. Điều này chứng minh các instance đang chia sẻ state session qua Redis trong thí nghiệm này. Test này không tự dừng một instance; kịch bản SIGTERM trong lúc request đang chạy chưa được đo riêng.

## Part 6: Final Project (CP5)

Hoàn thiện các phần `TODO` trong `06-lab-complete/` và chạy `python check_production_ready.py` **bản đầy đủ** trong WSL2 Ubuntu 24.04 (Python 3.12.3, Docker 29.4.2). Output thực tế: Docker image 63 MB, Redis tạm thời được dùng để kiểm tra state giữa các lần khởi động, graceful shutdown khi có request đang chạy thoát với exit code 0, và `docker stop` hoàn tất trong 0,5 giây.

### Checklist Deliverable từ script chấm

```text
✅ Dockerfile (multi-stage, < 500 MB)
✅ docker-compose.yml (agent + redis)
✅ .dockerignore
✅ Health check endpoint (GET /health)
✅ Readiness endpoint (GET /ready)
✅ API Key authentication
✅ Rate limiting
✅ Cost guard
✅ Config từ environment variables
✅ Structured logging
✅ Graceful shutdown
✅ Public URL ready (Railway / Render config)
Result: 12/12 tiêu chí đạt · 43/43 checks passed
PASS 12/12 — PRODUCTION READY!
```

Script đã xác nhận `/health` trả 200 khi Redis mất kết nối, `/ready` trả 503, thiếu/sai API key trả 401, rate limit trả 429 sau 5 request đúng cấu hình test và vẫn giữ state sau restart, cost guard trả 402 khi budget gần 0. Đây là kết quả kiểm tra local; URL public thuộc CP6 và chưa được xác minh.

## Part 7: Benchmark local (CP7)

Đã chạy hai agent local (v1 cổng 8001, v2 cổng 8002) và xác nhận `/health`, `/metrics` hoạt động. Bốn bài load test v2, mỗi bài 300 request, ở concurrency 1/10/50/100 đã lưu trong `06-lab-complete/benchmark-observability/develop/reports/`. SLO p95 ≤ 500 ms và error rate ≤ 2% đạt ở concurrency 1 và 10; không đạt ở 50 và 100 do p95 vượt ngưỡng. Ba lần thay `MOCK_SLOW_RATE=0/0.03/0.1` với concurrency 20 cho thấy p99 tăng mạnh khi xuất hiện request chậm, và p95 vi phạm SLO ở mức 0.1. Bảng số liệu và nguồn JSON ghi trong `BENCHMARK_REPORT.md`.

Eval golden dataset: v1 đúng 1/23 (gate FAIL), v2 trước sửa KB đúng 21/23 (gate PASS ở ngưỡng 80%). Chỉ sửa `KNOWLEDGE_BASE` cho `security-02` và `scaling-03`, khởi động lại v2 rồi eval đạt 23/23, gate PASS ở ngưỡng 100%, không regression; exit code 0. Chạy lại v1 so với baseline v2 trả exit code 1 và phát hiện 20 regression, minh họa cách chặn merge bằng quality gate trong CI. Trên Windows, `run_eval.py` cần chỉ rõ UTF-8 khi đọc/ghi JSON để lưu được câu trả lời tiếng Việt; đã sửa hai lệnh đọc/ghi đó.

## AI log

| Nội dung hỏi AI | AI hỗ trợ | Kiểm tra và việc cần tự rà soát |
| --- | --- | --- |
| Phân tích CP1–CP4 và chuẩn bị câu trả lời | Chỉ ra anti-pattern, so sánh hai bản app, giải thích Docker, API security, scaling và Redis | Đã đối chiếu source; HTTP của CP1–CP3, ba instance và session history của CP4 được chạy thực tế; số MB lấy từ `docker images` của học viên. Cần tự đọc lại lời giải trước khi nộp. |
| Điền các TODO của Part 6 | AI đã sửa `06-lab-complete/` theo các tiêu chí auth, Redis, rate limit, budget, health/readiness, Docker và deploy config | Đã đạt 28/28 kiểm tra tĩnh; học viên chạy script đầy đủ trong WSL2 và cung cấp output `PASS 12/12`, 43/43 checks passed. Cần tự đọc và giải thích được code khi Lab Coach hỏi. |
| Hướng dẫn CP6 deploy Railway | AI hướng dẫn tạo project, service agent/Redis, upload đúng thư mục và kiểm tra URL public; điền `DEPLOYMENT.md` và Part 3 | Học viên thao tác trên tài khoản Railway, cung cấp URL và bốn mã HTTP thực tế `200/200/401/200`. API key thật không được chia sẻ hoặc ghi vào repo. |
| Thực hiện CP7 benchmark local | AI chạy load test và eval, sửa hai entry trong knowledge base, xử lý UTF-8 trên Windows, điền số liệu từ JSON vào `BENCHMARK_REPORT.md` | Đã đối chiếu 11 file JSON trong `develop/reports/`; eval cuối đạt 23/23, không regression. Các số liệu của Part 7 production vẫn chờ CP8. |
