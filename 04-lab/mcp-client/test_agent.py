"""Chạy thử agent ở chế độ dòng lệnh — không cần mở `adk web`.

Script này minh hoạ đúng vòng lặp mà ADK điều phối:
    câu hỏi → LLM chọn tool → ADK gọi MCP server → LLM tổng hợp trả lời

Yêu cầu:
  1. MCP server đang chạy:  cd ../mcp-server && uv run python weather.py
  2. Có mcp-client/.env chứa OPENAI_API_KEY

Cách chạy:
    uv run python test_agent.py
    uv run python test_agent.py "Cuối tuần này Đà Nẵng có mưa không?"
"""

from __future__ import annotations

import asyncio
import sys

from google.adk.runners import InMemoryRunner
from google.genai import types

from weather_agent import root_agent

QUESTIONS = [
    "Thời tiết Hà Nội hôm nay thế nào?",
    "Cho tôi dự báo 2 ngày tới ở Đà Nẵng.",
]


async def ask(runner: InMemoryRunner, user_id: str, session_id: str, question: str) -> None:
    print(f"\n{'=' * 70}\nUser: {question}\n{'-' * 70}")

    content = types.Content(role="user", parts=[types.Part(text=question)])

    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=content
    ):
        # In ra tool nào được model gọi — đây chính là function calling
        for call in event.get_function_calls() or []:
            print(f"  [LLM gọi tool]   {call.name}({call.args})")
        for resp in event.get_function_responses() or []:
            preview = str(resp.response).replace("\n", " ")[:110]
            print(f"  [MCP trả về]     {preview}...")

        if event.is_final_response() and event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts).strip()
            if text:
                print(f"\nAgent: {text}")


async def main() -> None:
    questions = sys.argv[1:] or QUESTIONS

    runner = InMemoryRunner(agent=root_agent, app_name="weather_agent")
    session = await runner.session_service.create_session(
        app_name="weather_agent", user_id="demo_user"
    )

    for q in questions:
        await ask(runner, "demo_user", session.id, q)

    print(f"\n{'=' * 70}\nXong.")


if __name__ == "__main__":
    asyncio.run(main())
