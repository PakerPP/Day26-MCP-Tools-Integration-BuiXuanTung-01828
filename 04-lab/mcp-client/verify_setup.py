#!/usr/bin/env python3
"""Kiểm tra môi trường trước khi chạy agent.

    uv run python verify_setup.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8085/mcp")


def check_environment() -> bool:
    """.env tồn tại và có OPENAI_API_KEY (hoặc GOOGLE_API_KEY)."""
    print("1. Kiểm tra API key...")

    from dotenv import load_dotenv

    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        # override=True để .env thắng biến môi trường cũ còn sót trong shell
        load_dotenv(env_file, override=True)
    else:
        print("   [!] Chưa có file .env (vẫn chạy được nếu key nằm trong biến môi trường)")

    openai_key = os.getenv("OPENAI_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")

    if openai_key:
        print(f"   [OK] OPENAI_API_KEY ({openai_key[:7]}...) — agent sẽ dùng OpenAI")
        return True
    if google_key:
        print(f"   [OK] GOOGLE_API_KEY ({google_key[:7]}...) — agent sẽ dùng Gemini")
        return True

    print("   [X] Chưa có OPENAI_API_KEY hoặc GOOGLE_API_KEY")
    print("       Tạo file mcp-client/.env với nội dung:  OPENAI_API_KEY=sk-...")
    return False


def check_dependencies() -> bool:
    """Các package bắt buộc đã cài chưa."""
    print("\n2. Kiểm tra dependencies...")

    required = [
        ("google.adk", "google-adk"),
        ("litellm", "litellm"),
        ("mcp", "mcp"),
        ("dotenv", "python-dotenv"),
        ("httpx", "httpx"),
    ]

    ok = True
    for module, name in required:
        try:
            __import__(module)
            print(f"   [OK] {name}")
        except ImportError:
            print(f"   [X] {name} chưa cài")
            ok = False

    if not ok:
        print("       Chạy: uv sync")
    return ok


def check_agent_structure() -> bool:
    """Cấu trúc thư mục agent đúng chuẩn ADK."""
    print("\n3. Kiểm tra cấu trúc agent...")

    base = Path(__file__).parent
    ok = True
    for rel in ("weather_agent/agent.py", "weather_agent/__init__.py"):
        if (base / rel).exists():
            print(f"   [OK] {rel}")
        else:
            print(f"   [X] Thiếu {rel}")
            ok = False
    return ok


def check_mcp_server() -> bool:
    """MCP server đang chạy và công bố đủ 3 tool."""
    print(f"\n4. Kiểm tra MCP server ({MCP_SERVER_URL})...")

    async def probe() -> list[str]:
        import mcp.client.streamable_http as sh
        from mcp import ClientSession

        # mcp 1.x: streamablehttp_client yield 3 phần tử (read, write, get_session_id)
        # mcp 2.x: streamable_http_client yield 2 phần tử (read, write)
        connect = getattr(sh, "streamablehttp_client", None) or sh.streamable_http_client

        async with connect(MCP_SERVER_URL) as streams:
            read, write = streams[0], streams[1]
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                return [t.name for t in result.tools]

    try:
        names = asyncio.run(probe())
    except Exception as e:  # noqa: BLE001
        print(f"   [X] Không kết nối được: {type(e).__name__}")
        print("       Khởi động server trước:")
        print("       cd ../mcp-server && uv run python weather.py")
        return False

    print(f"   [OK] Server trả về {len(names)} tool: {', '.join(names)}")

    expected = {"get_current_weather", "get_forecast", "health_check"}
    missing = expected - set(names)
    if missing:
        print(f"   [X] Thiếu tool: {', '.join(sorted(missing))}")
        return False
    return True


def check_agent_import() -> bool:
    """Import được agent (đã bao gồm việc chọn model)."""
    print("\n5. Kiểm tra import agent...")

    try:
        from weather_agent import root_agent

        model = root_agent.model
        name = model if isinstance(model, str) else getattr(model, "model", model)
        print(f"   [OK] Agent '{root_agent.name}' — model: {name}")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"   [X] Lỗi import: {e}")
        return False


def main() -> int:
    print("=" * 62)
    print("Weather Agent — kiểm tra môi trường")
    print("=" * 62)

    results = [
        check_environment(),
        check_dependencies(),
        check_agent_structure(),
        check_mcp_server(),
        check_agent_import(),
    ]

    print("\n" + "=" * 62)
    if all(results):
        print("Tất cả đều OK. Chạy agent bằng:")
        print("   uv run python test_agent.py     (dòng lệnh)")
        print("   uv run adk web                  (giao diện web :8000)")
        return 0

    print(f"Còn {results.count(False)} mục chưa đạt — xem hướng dẫn ở trên.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
