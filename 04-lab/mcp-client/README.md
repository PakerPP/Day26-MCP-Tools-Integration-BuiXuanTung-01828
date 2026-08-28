# Weather Agent - Google ADK with MCP Server

AI agent built with **Google Agent Development Kit (ADK)** that uses tools from a local **MCP server** via Streamable HTTP transport.

Model: **OpenAI** (`openai/gpt-4o-mini`) thông qua LiteLLM wrapper của ADK.

## Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────────┐
│   User Browser  │ ───> │  ADK Web UI      │ ───> │  Weather Agent      │
│   localhost:8000│      │  (Google ADK)    │      │  (Agent with MCP)   │
└─────────────────┘      └──────────────────┘      └─────────────────────┘
                                                             │
                                                             │ Streamable HTTP
                                                             ▼
                                                   ┌─────────────────────┐
                                                   │  MCP Server         │
                                                   │  localhost:8085/mcp │
                                                   │  FastMCP + Tools    │
                                                   └─────────────────────┘
                                                             │
                                                             ▼
                                                   ┌─────────────────────┐
                                                   │  WeatherAPI.com     │
                                                   └─────────────────────┘
```

## Features

- **Remote MCP Tools**: Connects to MCP server via Streamable HTTP
- **3 Weather Tools**:
  - `get_current_weather(city)` - Real-time weather conditions
  - `get_forecast(city, days)` - Weather forecast up to 3 days
  - `health_check()` - Server health verification
- **Web Interface**: UI via ADK web
- **Streaming Responses**: Real-time AI responses

## Quick Start

### 1. Start the MCP Server

```bash
cd ../mcp-server
export WEATHERAPI_KEY="your_weatherapi_key"   # tuỳ chọn — không có thì dùng MOCK
uv run python weather.py
```

### 2. Setup Environment

```bash
cd mcp-client

# Copy mẫu rồi điền OPENAI_API_KEY
cp .env.example .env
```

### 3. Install Dependencies

```bash
uv sync
```

### 4. Kiểm tra & chạy

```bash
uv run python verify_setup.py    # kiểm tra key, deps, MCP server
uv run python test_agent.py      # chạy nhanh ở dòng lệnh
uv run adk web                   # hoặc giao diện web
```

### 5. Use the Agent

1. Open browser: http://localhost:8000
2. Select `weather_agent` from dropdown
3. Ask questions like:
   - "Thời tiết Hà Nội hôm nay thế nào?"
   - "Cho tôi dự báo 3 ngày ở Đà Nẵng"
   - "Hải Phòng có mưa không?"

## Project Structure

```
mcp-client/
├── weather_agent/
│   ├── agent.py           # Agent + kết nối MCP
│   └── __init__.py
├── test_agent.py          # Chạy thử ở dòng lệnh
├── verify_setup.py        # Kiểm tra môi trường
├── .env.example           # Mẫu cấu hình
├── .env                   # Key thật (tự tạo, đã gitignore)
├── pyproject.toml
└── README.md
```

## Configuration

### Agent Configuration

In `weather_agent/agent.py`:

```python
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8085/mcp")

weather_tools = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=MCP_SERVER_URL,
        timeout=30.0,
    ),
)

root_agent = Agent(
    name="weather_agent",
    model=LiteLlm("openai/gpt-4o-mini"),   # OpenAI qua LiteLLM
    instruction=INSTRUCTION,
    tools=[weather_tools],
)
```

## Troubleshooting

### Agent won't connect to MCP server

1. **404 errors**: MCP server is not running or wrong port
   - Ensure the MCP server is running on port 8085
   - Check `MCP_SERVER_URL` in `agent.py`

2. **405 errors**: Port conflict with another application
   - Check what's running on the port: `lsof -i :8085`
   - Change port in both server and client if needed

3. **Timeout errors**: Server not started
   - Start the MCP server first, then the ADK client

### Lỗi tiếng Việt trên Windows

Console Windows dùng cp1252 → `UnicodeEncodeError`. Đặt `PYTHONUTF8=1` trước khi chạy.

## Environment Variables

Tạo file `.env` (xem `.env.example`):
```bash
OPENAI_API_KEY=sk-...
# OPENAI_MODEL=openai/gpt-4o-mini      # tuỳ chọn
# GOOGLE_API_KEY=...                   # tuỳ chọn, dùng Gemini thay OpenAI
# MCP_SERVER_URL=http://localhost:8085/mcp
```

## Resources

- [Google ADK Documentation](https://google.github.io/adk-docs/)
- [MCP Specification](https://modelcontextprotocol.io/)
- [FastMCP GitHub](https://github.com/jlowin/fastmcp)
- [WeatherAPI](https://www.weatherapi.com/)
