"""Weather Agent — ADK agent đóng vai trò MCP CLIENT.

ADK làm 5 việc trong lab này:
  1. KẾT NỐI tới MCP Server qua Streamable HTTP
  2. KHÁM PHÁ tools tự động (list_tools) — không hard-code tool nào
  3. TRUYỀN tools cho LLM dưới dạng function declarations
  4. ĐIỀU PHỐI vòng lặp function calling (model chọn tool → gọi server → tổng hợp)
  5. CUNG CẤP giao diện web qua `adk web`

Model: dùng OpenAI (qua LiteLLM wrapper của ADK). Chỉ cần OPENAI_API_KEY.
Nếu không có OPENAI_API_KEY nhưng có GOOGLE_API_KEY, agent tự chuyển sang Gemini.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool.mcp_toolset import (
    McpToolset,
    StreamableHTTPConnectionParams,
)

# Nạp .env nằm cạnh thư mục agent (mcp-client/.env).
# override=True: giá trị trong .env THẮNG biến môi trường sẵn có — nếu không,
# một OPENAI_API_KEY cũ còn sót trong shell sẽ âm thầm che key trong .env
# và bạn nhận lỗi 401 rất khó đoán.
load_dotenv(os.path.join(os.path.dirname(__file__), os.pardir, ".env"), override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8085/mcp")

# Model — mặc định OpenAI; đổi bằng biến môi trường OPENAI_MODEL nếu muốn
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

INSTRUCTION = (
    "Bạn là trợ lý thời tiết thân thiện. Khi người dùng hỏi về thời tiết, "
    "HÃY GỌI TOOL để lấy dữ liệu thật — tuyệt đối không tự bịa số liệu.\n"
    "- Thời tiết hiện tại  → get_current_weather(city)\n"
    "- Dự báo nhiều ngày   → get_forecast(city, days)\n"
    "- Kiểm tra server     → health_check()\n"
    "Trả lời bằng tiếng Việt, ngắn gọn, dùng emoji phù hợp (🌧️ 🌤️ 💨 💧), "
    "và thêm một lời khuyên thực tế (mang ô, mặc áo mỏng...).\n"
    "QUAN TRỌNG: nếu kết quả tool có chứa 'MOCK DATA', BẮT BUỘC kết thúc câu "
    "trả lời bằng đúng một dòng: '⚠️ (Dữ liệu mô phỏng — chưa cấu hình "
    "WEATHERAPI_KEY)'. Không được bỏ qua dòng này."
)


def _build_model() -> LiteLlm | str:
    """Chọn model theo API key có sẵn: ưu tiên OpenAI, fallback Gemini."""
    if os.getenv("OPENAI_API_KEY"):
        logger.info("Model: %s (OpenAI qua LiteLLM)", OPENAI_MODEL)
        return LiteLlm(model=OPENAI_MODEL)

    if os.getenv("GOOGLE_API_KEY"):
        logger.info("Model: %s (Gemini)", GEMINI_MODEL)
        return GEMINI_MODEL

    raise RuntimeError(
        "Chưa có API key. Tạo file mcp-client/.env với một trong hai dòng:\n"
        "  OPENAI_API_KEY=sk-...        (khuyến nghị)\n"
        "  GOOGLE_API_KEY=...           (nếu dùng Gemini)"
    )


logger.info("Khởi tạo weather agent — MCP server: %s", MCP_SERVER_URL)

# ── ADK bước 1+2: kết nối MCP server và tự khám phá tools ─────────────
# McpToolset gọi list_tools() khi agent chạy — không hard-code tool nào ở đây.
weather_tools = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=MCP_SERVER_URL,
        timeout=30.0,
    ),
)

# ── ADK bước 3+4: đưa tools cho LLM và điều phối function calling ─────
root_agent = Agent(
    name="weather_agent",
    model=_build_model(),
    instruction=INSTRUCTION,
    tools=[weather_tools],
)

logger.info("Agent sẵn sàng. Tools sẽ được khám phá từ MCP server lúc chạy.")
