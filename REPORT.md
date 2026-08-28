# Báo cáo Lab Day 26 — MCP Tools Integration

**Học viên:** Bùi Xuân Tùng — 01828
**Ngày:** 29/08/2026

---

## 1. Mục tiêu

Phân biệt **Function Calling** và **MCP (Model Context Protocol)**, sau đó xây dựng một agent hoàn chỉnh dùng cả hai: agent ADK đóng vai MCP Client, kết nối tới MCP Server độc lập qua Streamable HTTP.

## 2. Kết luận cốt lõi

| | Function Calling | MCP |
|---|---|---|
| Bản chất | Khả năng của **model** | **Giao thức** client–server |
| Ai định nghĩa tool | App hard-code | Server tự công bố (`list_tools`) |
| Nơi thực thi | Ngay trong app | MCP Server riêng |
| Tái sử dụng | Copy code sang app khác | Cắm thêm client, không sửa server |

**MCP không thay thế Function Calling — MCP dùng Function Calling bên dưới.** Model vẫn là thứ quyết định gọi tool nào; MCP chỉ chuẩn hoá cách client nói chuyện với server chứa tool đó.

```
User hỏi → LLM (function calling: chọn tool) → MCP Client
                                                    │ giao thức MCP
                                                    ▼
                                              MCP Server (thực thi)
                                                    │
User ← LLM tổng hợp ←────────────────── kết quả ────┘
```

## 3. Các phần đã thực hiện

| Phần | Nội dung | Trạng thái |
|---|---|---|
| `01-function-calling` | Function calling thuần với Gemini SDK — schema viết tay, app tự chạy tool | Đọc hiểu, giữ nguyên |
| `02-mcp-basics` | MCP server + client qua stdio, tool tự sinh schema từ type hints | Chạy OK |
| `03-production` | Auth (bearer token), Tool Registry, Versioning | Chạy OK sau khi sửa 2 lỗi |
| `04-lab` | ADK Agent + MCP Server + OpenAI — **phần chính** | Hoàn thành, chạy end-to-end |

## 4. Kiến trúc Lab 04

```
┌─────────────────┐  Streamable HTTP  ┌─────────────────┐    REST     ┌──────────────┐
│   ADK Agent     │ ───────────────── │   MCP Server    │ ─────────── │ WeatherAPI   │
│ gpt-4o-mini     │  localhost:8085   │  3 weather tool │             │ (hoặc MOCK)  │
│ (MCP Client)    │       /mcp        │                 │             │              │
└─────────────────┘                   └─────────────────┘             └──────────────┘
```

**ADK làm 5 việc:** kết nối MCP server → tự `list_tools()` → đưa schema cho LLM → điều phối vòng lặp function calling → cung cấp web UI. So với bài 02 (viết `ClientSession` thủ công), ADK bỏ hẳn phần vòng lặp viết tay.

**3 tool server công bố:** `get_current_weather(city)`, `get_forecast(city, days)`, `health_check()`.

## 5. Lỗi đã tìm và sửa

### 5.1. `04-lab/mcp-server/weather.py` không chạy được — MCP SDK đổi API

Code dùng `from mcp.server.fastmcp import FastMCP`, nhưng `mcp[cli]>=1.2.0` giải ra **mcp 2.x**, nơi `FastMCP` đã đổi tên thành `MCPServer`:

```
ModuleNotFoundError: No module named 'mcp.server.fastmcp'. This is mcp 2.x,
where FastMCP was renamed to MCPServer...
```

Hai bản còn khác nhau ở chỗ nhận `host`/`port`: mcp 1.x đặt ở constructor, mcp 2.x đặt ở `run()`. Đã viết shim xử lý cả hai và **test thực tế trên cả hai phiên bản** (2.1.1 và 1.28.1).

### 5.2. `03-production/registry_client.py` — nhánh HTTP crash

```python
async with streamable_http_client(...) as (read, write, _):   # sai: mcp 2.x chỉ trả 2
```

Lỗi này **ẩn**, vì demo mặc định chỉ đi nhánh stdio. Đã sửa thành truy cập theo index (chạy được cả 2-tuple lẫn 3-tuple) và test lại nhánh HTTP kèm bearer auth — thành công.

### 5.3. Biến môi trường cũ che key trong `.env` ⭐

Lỗi khó chịu nhất. `load_dotenv()` **không ghi đè** biến môi trường đã tồn tại. Máy có sẵn một `OPENAI_API_KEY` cũ đã hết hạn → key đúng trong `.env` bị che → API trả 401 dù key hoàn toàn hợp lệ.

Đã sửa bằng `load_dotenv(..., override=True)` ở cả `agent.py` và `verify_setup.py`.

### 5.4. Cổng 8000 bị chiếm

Một process khác đang giữ `127.0.0.1:8000`, khiến `auth_client.py` báo `MCPError: Not Found` — thông báo không hề gợi ý nguyên nhân thật. Đã cho phép đổi cổng qua `MCP_AUTH_PORT`.

### 5.5. Tiếng Việt lỗi trên Windows

Console Windows dùng codepage cp1252 → `UnicodeEncodeError: 'charmap' codec can't encode character 'ấ'`. Cách xử lý: đặt `PYTHONUTF8=1`. Đã ghi vào README.

## 6. Thay đổi thiết kế

**Dùng OpenAI thay Gemini.** Bài gốc viết cho `gemini-2.5-flash`; đã chuyển sang OpenAI qua `LiteLlm` wrapper của ADK (`openai/gpt-4o-mini`), giữ nguyên kiến trúc ADK + MCP. Agent tự fallback sang Gemini nếu chỉ có `GOOGLE_API_KEY`.

**Thêm mock fallback cho MCP server.** Không có `WEATHERAPI_KEY` thì server trả dữ liệu mô phỏng thay vì báo lỗi, nên vẫn demo được trọn vẹn luồng ADK + MCP. Output luôn ghi rõ `[source: MOCK DATA]`, và agent được yêu cầu cảnh báo người dùng.

**Bỏ "fallback agent không có tool".** Code gốc bắt exception khi MCP hỏng rồi tạo agent *không có tool nào*. Với bài lab thời tiết, điều này nguy hiểm: agent sẽ **tự bịa số liệu** thay vì báo lỗi, và người học tưởng MCP đang chạy. Giờ agent fail rõ ràng.

## 7. Kết quả chạy thật

`verify_setup.py` — pass 5/5:

```
1. [OK] OPENAI_API_KEY — agent sẽ dùng OpenAI
2. [OK] google-adk, litellm, mcp, python-dotenv, httpx
3. [OK] weather_agent/agent.py, __init__.py
4. [OK] Server trả về 3 tool: get_current_weather, get_forecast, health_check
5. [OK] Agent 'weather_agent' — model: openai/gpt-4o-mini
```

ADK kết nối MCP server, negotiate protocol version `2025-11-25`, tự khám phá đủ 3 tool.

Chạy `test_agent.py` — model chọn đúng tool, đúng tham số:

```
User: Thời tiết Hà Nội hôm nay thế nào?
  [LLM gọi tool]   get_current_weather({'city': 'Hanoi'})
  [MCP trả về]     Current Weather for Hanoi, Vietnam...
Agent: Thời tiết Hà Nội hôm nay khoảng 29°C, có mưa nhẹ 🌧️, độ ẩm 82%,
       gió Đông Nam 12 km/h. Hãy mang theo ô khi ra ngoài nhé!
       ⚠️ (Dữ liệu mô phỏng — chưa cấu hình WEATHERAPI_KEY)

User: Cho tôi dự báo 2 ngày tới ở Đà Nẵng.
  [LLM gọi tool]   get_forecast({'city': 'Danang', 'days': 2})   ← truyền đúng days=2
```

Cả 3 tool đều đã verify hoạt động end-to-end.

## 8. Bài học rút ra

1. **Version drift là rủi ro thật.** `mcp[cli]>=1.2.0` kéo về bản 2.x đổi tên class — code viết cho 1.x chết ngay. Trong production nên pin version chặt.
2. **MCP tách bạch được vòng đời tool và app.** Sửa server không cần đụng agent; ADK khám phá tool lúc runtime.
3. **Lỗi cấu hình thường ngụy trang thành lỗi khác.** 401 hoá ra do biến môi trường cũ che key; `Not Found` hoá ra do đụng cổng. Cả hai đều không liên quan tới thông báo lỗi hiển thị.
4. **Fallback im lặng nguy hiểm hơn crash.** Agent không tool vẫn trả lời trôi chảy bằng số liệu bịa — sai mà trông như đúng.

## 9. Cách chạy lại

```bash
# Terminal 1 — MCP server
cd 04-lab/mcp-server && uv sync
export WEATHERAPI_KEY="..."     # tuỳ chọn, không có thì dùng MOCK
uv run python weather.py

# Terminal 2 — ADK agent
cd 04-lab/mcp-client && uv sync
cp .env.example .env            # điền OPENAI_API_KEY=sk-...
uv run python verify_setup.py
uv run python test_agent.py     # hoặc: uv run adk web
```

> Windows: đặt `PYTHONUTF8=1` trước khi chạy.
