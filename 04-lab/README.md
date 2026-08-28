# Lab 04 — Weather Agent with Remote MCP Server

Agent thời tiết xây bằng Google ADK, kết nối tới MCP server qua Streamable HTTP transport.

## Architecture

```
┌─────────────────┐   Streamable HTTP    ┌─────────────────┐      REST       ┌─────────────────┐
│   ADK Agent     │ ──────────────────── │   MCP Server    │ ─────────────── │  WeatherAPI.com │
│  (mcp-client)   │   localhost:8085/mcp │  (mcp-server)   │                 │  (hoặc MOCK)    │
│  model: OpenAI  │                      │                 │                 │                 │
└─────────────────┘                      └─────────────────┘                 └─────────────────┘
```

## Tools

| Tool | Description |
|------|-------------|
| `get_current_weather(city)` | Thời tiết hiện tại của một thành phố |
| `get_forecast(city, days)` | Dự báo thời tiết (1–3 ngày) |
| `health_check()` | Kiểm tra server đang chạy + nguồn dữ liệu |

## ADK làm gì trong Lab này?

ADK (Agent Development Kit) đóng vai trò **MCP Client**:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  1. KẾT NỐI tới MCP Server qua Streamable HTTP                  │
│     StreamableHTTPConnectionParams(url="localhost:8085/mcp")    │
│                                                                 │
│  2. KHÁM PHÁ tools tự động (list_tools)                         │
│     McpToolset → tự hỏi server "anh có tool gì?"                │
│     → nhận về: get_current_weather, get_forecast, health_check  │
│                                                                 │
│  3. TRUYỀN tools cho LLM (OpenAI qua LiteLLM)                   │
│     Agent(model=LiteLlm("openai/gpt-4o-mini"), tools=[...])     │
│     → model biết nó có thể gọi 3 tools trên                     │
│                                                                 │
│  4. ĐIỀU PHỐI vòng lặp Function Calling                         │
│     User hỏi → model chọn tool → ADK gọi MCP Server             │
│     → nhận kết quả → đưa lại cho model tổng hợp                 │
│                                                                 │
│  5. CUNG CẤP giao diện web (adk web)                            │
│     → http://localhost:8000 để chat với agent                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

So với bài 02 (viết client thủ công bằng `mcp.ClientSession`), ADK giúp bạn **không phải viết vòng lặp function calling thủ công** nữa. Toàn bộ luồng list_tools → model quyết định → call_tool → model tổng hợp được ADK xử lý tự động.

## Setup

Cần **2 terminal**: một chạy MCP server, một chạy ADK agent.

### Terminal 1 — MCP Server

```bash
cd mcp-server
uv sync

# TUỲ CHỌN: dùng dữ liệu thật (đăng ký free tại https://weatherapi.com)
export WEATHERAPI_KEY="your_weatherapi_key"
# Không đặt key → server tự dùng dữ liệu MOCK, lab vẫn chạy đầy đủ

uv run python weather.py
```

Server chạy tại `http://localhost:8085/mcp`.

### Terminal 2 — ADK Agent (Client)

```bash
cd mcp-client
uv sync

# Tạo .env chứa OpenAI key
cp .env.example .env       # rồi sửa OPENAI_API_KEY=sk-...

# Kiểm tra mọi thứ đã sẵn sàng
uv run python verify_setup.py

# Cách A — chạy nhanh ở dòng lệnh
uv run python test_agent.py

# Cách B — giao diện web
uv run adk web
```

Với `adk web`: mở http://localhost:8000, chọn `weather_agent`, rồi hỏi về thời tiết.

## Configuration

| Variable | Where | Description |
|----------|-------|-------------|
| `OPENAI_API_KEY` | mcp-client/.env | **Bắt buộc** — key OpenAI |
| `OPENAI_MODEL` | mcp-client/.env | Model OpenAI (mặc định `openai/gpt-4o-mini`) |
| `GOOGLE_API_KEY` | mcp-client/.env | Tuỳ chọn — dùng Gemini thay OpenAI |
| `MCP_SERVER_URL` | mcp-client/.env | Địa chỉ MCP server (mặc định `http://localhost:8085/mcp`) |
| `WEATHERAPI_KEY` | mcp-server (env) | Tuỳ chọn — không có thì dùng MOCK |
| `PORT` | mcp-server (env) | Đổi cổng server (mặc định 8085) |

### Đổi model

Agent tự chọn model theo key có sẵn: có `OPENAI_API_KEY` → dùng OpenAI; nếu không, có `GOOGLE_API_KEY` → dùng Gemini. Đổi model OpenAI cụ thể trong `.env`:

```bash
OPENAI_MODEL=openai/gpt-4o        # hoặc openai/gpt-4.1-mini, ...
```

## Ghi chú cho Windows

Console Windows mặc định dùng codepage cp1252 nên **in tiếng Việt sẽ lỗi `UnicodeEncodeError`**. Đặt biến này trước khi chạy:

```powershell
$env:PYTHONUTF8 = "1"
```

```bash
# Git Bash
export PYTHONUTF8=1
```

## Troubleshooting

| Triệu chứng | Nguyên nhân & cách xử lý |
|---|---|
| `UnicodeEncodeError: 'charmap' codec` | Đặt `PYTHONUTF8=1` (xem mục trên) |
| Agent không gọi tool, tự bịa số liệu | MCP server chưa chạy → mở Terminal 1 trước |
| `error while attempting to bind ... 10048` | Cổng đã bị chiếm. Đổi cổng: `PORT=8090` (server) + `MCP_SERVER_URL` (client) |
| `ModuleNotFoundError: mcp.server.fastmcp` | Bạn đang dùng mcp 2.x — `weather.py` đã xử lý tương thích, chạy lại `uv sync` |
| Tool trả `[source: MOCK DATA]` | Chưa đặt `WEATHERAPI_KEY` — bình thường, lab vẫn chạy đủ luồng |
| OpenAI trả 401 | Key sai/hết hạn — kiểm tra `OPENAI_API_KEY` trong `.env` |

## Luồng bạn sẽ thấy khi chạy `test_agent.py`

```
User: Thời tiết Hà Nội hôm nay thế nào?
  [LLM gọi tool]   get_current_weather({'city': 'Hanoi'})
  [MCP trả về]     Current Weather for Hanoi, Vietnam...
Agent: 🌧️ Hà Nội hiện 29°C, mưa nhẹ, độ ẩm 82%... nhớ mang ô nhé!
```

Đó chính là **MCP dùng Function Calling bên dưới**: model quyết định gọi tool (function calling), còn MCP là giao thức để ADK nói chuyện với server thật.
