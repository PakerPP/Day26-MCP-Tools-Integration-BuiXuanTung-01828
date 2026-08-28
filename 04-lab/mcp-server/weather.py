"""Weather MCP Server — công bố 3 tool thời tiết qua Streamable HTTP.

Server này là "nguồn tool" trong kiến trúc MCP: nó tự khai báo có tool gì,
bất kỳ MCP client nào (ADK agent, Claude Code, Cursor...) cắm vào cũng dùng
được mà không cần biết code bên trong.

Nguồn dữ liệu:
  - Có WEATHERAPI_KEY  → gọi API thật của weatherapi.com
  - Không có key       → tự động dùng dữ liệu MOCK để bạn vẫn chạy được lab

Cách chạy:
    uv sync
    export WEATHERAPI_KEY="..."      # tuỳ chọn — không có thì chạy mock
    uv run python weather.py
    # Server lắng nghe tại http://localhost:8085/mcp
"""

from __future__ import annotations

import os
import sys
from typing import Any

import httpx

# MCP SDK 2.x đổi tên FastMCP → MCPServer, và chuyển host/port từ constructor
# sang run(). Import + khởi tạo tương thích cả hai để lab chạy được dù bạn cài
# mcp 1.x hay 2.x.
try:
    from mcp.server.mcpserver import MCPServer  # mcp >= 2.0

    IS_MCP_V2 = True
except ModuleNotFoundError:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP as MCPServer  # mcp 1.x

    IS_MCP_V2 = False

PORT = int(os.getenv("PORT", "8085"))

WEATHERAPI_BASE = "https://api.weatherapi.com/v1"
USER_AGENT = "weather-mcp-lab/1.0"
API_KEY = os.getenv("WEATHERAPI_KEY")

if IS_MCP_V2:
    mcp = MCPServer("weather")
else:
    # mcp 1.x: host/port phải khai báo ngay ở constructor
    mcp = MCPServer("weather", host="0.0.0.0", port=PORT)

# ── Dữ liệu mock — dùng khi không có WEATHERAPI_KEY ───────────────────
_MOCK_DB: dict[str, dict[str, Any]] = {
    "hanoi": {
        "name": "Hanoi", "country": "Vietnam",
        "temp_c": 29.0, "condition": "Light rain", "humidity": 82,
        "wind_kph": 12.0, "wind_dir": "SE", "pressure_mb": 1006.0, "uv": 6.0, "vis_km": 8.0,
        "forecast": [
            {"date": "N+1", "max_c": 31.0, "min_c": 25.0, "condition": "Patchy rain", "rain": 68, "wind_kph": 15.0, "uv": 6.0},
            {"date": "N+2", "max_c": 33.0, "min_c": 26.0, "condition": "Sunny", "rain": 10, "wind_kph": 11.0, "uv": 8.0},
            {"date": "N+3", "max_c": 30.0, "min_c": 24.0, "condition": "Cloudy", "rain": 35, "wind_kph": 13.0, "uv": 5.0},
        ],
    },
    "haiphong": {
        "name": "Haiphong", "country": "Vietnam",
        "temp_c": 33.0, "condition": "Rain shower", "humidity": 75,
        "wind_kph": 15.0, "wind_dir": "SW", "pressure_mb": 1004.0, "uv": 7.0, "vis_km": 9.0,
        "forecast": [
            {"date": "N+1", "max_c": 34.0, "min_c": 27.0, "condition": "Rain shower", "rain": 72, "wind_kph": 17.0, "uv": 7.0},
            {"date": "N+2", "max_c": 32.0, "min_c": 26.0, "condition": "Cloudy", "rain": 40, "wind_kph": 14.0, "uv": 6.0},
            {"date": "N+3", "max_c": 33.0, "min_c": 26.0, "condition": "Sunny", "rain": 15, "wind_kph": 12.0, "uv": 8.0},
        ],
    },
    "danang": {
        "name": "Da Nang", "country": "Vietnam",
        "temp_c": 30.0, "condition": "Partly cloudy", "humidity": 78,
        "wind_kph": 10.0, "wind_dir": "E", "pressure_mb": 1008.0, "uv": 7.0, "vis_km": 10.0,
        "forecast": [
            {"date": "N+1", "max_c": 32.0, "min_c": 25.0, "condition": "Sunny", "rain": 12, "wind_kph": 11.0, "uv": 9.0},
            {"date": "N+2", "max_c": 31.0, "min_c": 25.0, "condition": "Patchy rain", "rain": 55, "wind_kph": 13.0, "uv": 6.0},
            {"date": "N+3", "max_c": 30.0, "min_c": 24.0, "condition": "Cloudy", "rain": 30, "wind_kph": 12.0, "uv": 6.0},
        ],
    },
}

_DEFAULT_MOCK: dict[str, Any] = {
    "name": "", "country": "(mock)",
    "temp_c": 28.0, "condition": "Partly cloudy", "humidity": 70,
    "wind_kph": 10.0, "wind_dir": "N", "pressure_mb": 1010.0, "uv": 5.0, "vis_km": 10.0,
    "forecast": [
        {"date": "N+1", "max_c": 30.0, "min_c": 24.0, "condition": "Partly cloudy", "rain": 30, "wind_kph": 11.0, "uv": 5.0},
        {"date": "N+2", "max_c": 31.0, "min_c": 24.0, "condition": "Sunny", "rain": 15, "wind_kph": 10.0, "uv": 7.0},
        {"date": "N+3", "max_c": 29.0, "min_c": 23.0, "condition": "Cloudy", "rain": 40, "wind_kph": 12.0, "uv": 4.0},
    ],
}


def _mock_for(city: str) -> dict[str, Any]:
    """Lấy bản ghi mock cho *city* (không phân biệt hoa thường / dấu cách)."""
    key = city.strip().lower().replace(" ", "").replace("-", "")
    data = _MOCK_DB.get(key)
    if data is not None:
        return data
    fallback = dict(_DEFAULT_MOCK)
    fallback["name"] = city.strip().title()
    return fallback


def _c_to_f(celsius: float) -> float:
    return round(celsius * 9 / 5 + 32, 1)


async def make_weather_request(endpoint: str, params: dict[str, str]) -> dict[str, Any] | None:
    """Gọi WeatherAPI với xử lý lỗi. Trả None nếu thất bại hoặc chưa có key."""
    if not API_KEY:
        return None

    params = {**params, "key": API_KEY}
    url = f"{WEATHERAPI_BASE}/{endpoint}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                url, headers={"User-Agent": USER_AGENT}, params=params, timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP Error {e.response.status_code}: {e.response.text}", file=sys.stderr)
            return None
        except httpx.RequestError as e:
            print(f"Request Error: {e}", file=sys.stderr)
            return None
        except Exception as e:  # noqa: BLE001
            print(f"Unexpected error: {e}", file=sys.stderr)
            return None


@mcp.tool()
async def get_current_weather(city: str) -> str:
    """Get current weather conditions for a city.

    Args:
        city: City name (e.g., "Hanoi", "Haiphong", "Danang", "Tokyo", "Sydney")
    """
    data = await make_weather_request("current.json", {"q": city, "aqi": "no"})

    if data:
        current, location = data["current"], data["location"]
        source = "WeatherAPI.com (live)"
        parts = [location["name"], location.get("region") or "", location["country"]]
        name = ", ".join(p for p in parts if p)
        temp_c, temp_f = current["temp_c"], current["temp_f"]
        feels_c, feels_f = current["feelslike_c"], current["feelslike_f"]
        condition = current["condition"]["text"]
        humidity, wind_kph = current["humidity"], current["wind_kph"]
        wind_dir, pressure = current["wind_dir"], current["pressure_mb"]
        uv, vis = current["uv"], current["vis_km"]
        updated = current["last_updated"]
    else:
        m = _mock_for(city)
        source = "MOCK DATA (chưa cấu hình WEATHERAPI_KEY)"
        name = f"{m['name']}, {m['country']}"
        temp_c, temp_f = m["temp_c"], _c_to_f(m["temp_c"])
        feels_c, feels_f = temp_c, temp_f
        condition = m["condition"]
        humidity, wind_kph = m["humidity"], m["wind_kph"]
        wind_dir, pressure = m["wind_dir"], m["pressure_mb"]
        uv, vis = m["uv"], m["vis_km"]
        updated = "n/a"

    return f"""Current Weather for {name}:
[source: {source}]

Temperature: {temp_c}°C ({temp_f}°F)
Feels like: {feels_c}°C ({feels_f}°F)
Condition: {condition}
Humidity: {humidity}%
Wind: {wind_kph} km/h {wind_dir}
Pressure: {pressure} mb
UV Index: {uv}
Visibility: {vis} km

Last updated: {updated}"""


@mcp.tool()
async def get_forecast(city: str, days: int = 3) -> str:
    """Get weather forecast for a city.

    Args:
        city: City name (e.g., "Hanoi", "Haiphong", "Danang", "Tokyo", "Sydney")
        days: Number of days to forecast (1-3 on the free tier)
    """
    days = max(1, min(days, 3))

    data = await make_weather_request(
        "forecast.json", {"q": city, "days": str(days), "aqi": "no", "alerts": "no"}
    )

    if data:
        location = data["location"]
        source = "WeatherAPI.com (live)"
        parts = [location["name"], location.get("region") or "", location["country"]]
        name = ", ".join(p for p in parts if p)
        rows = [
            {
                "date": d["date"],
                "max_c": d["day"]["maxtemp_c"], "min_c": d["day"]["mintemp_c"],
                "condition": d["day"]["condition"]["text"],
                "rain": d["day"]["daily_chance_of_rain"],
                "wind_kph": d["day"]["maxwind_kph"], "uv": d["day"]["uv"],
            }
            for d in data["forecast"]["forecastday"]
        ]
    else:
        m = _mock_for(city)
        source = "MOCK DATA (chưa cấu hình WEATHERAPI_KEY)"
        name = f"{m['name']}, {m['country']}"
        rows = m["forecast"][:days]

    blocks = [f"Weather Forecast for {name}:\n[source: {source}]"]
    for r in rows:
        blocks.append(
            f"""{r['date']}:
High: {r['max_c']}°C ({_c_to_f(r['max_c'])}°F)
Low: {r['min_c']}°C ({_c_to_f(r['min_c'])}°F)
Condition: {r['condition']}
Chance of Rain: {r['rain']}%
Max Wind: {r['wind_kph']} km/h
UV Index: {r['uv']}"""
        )

    return "\n---\n".join(blocks)


@mcp.tool()
async def health_check() -> str:
    """Health check endpoint for deployment verification."""
    mode = "live WeatherAPI" if API_KEY else "MOCK data (chưa có WEATHERAPI_KEY)"
    return f"Weather MCP Server is running. Data source: {mode}."


if __name__ == "__main__":
    mode = "live WeatherAPI.com" if API_KEY else "MOCK (đặt WEATHERAPI_KEY để dùng dữ liệu thật)"
    print(f"Data source : {mode}", file=sys.stderr)
    print("Tools       : get_current_weather, get_forecast, health_check", file=sys.stderr)
    print(f"Starting MCP server on http://0.0.0.0:{PORT}/mcp", file=sys.stderr)

    if IS_MCP_V2:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=PORT)
    else:
        # mcp 1.x đã nhận host/port từ constructor
        mcp.run(transport="streamable-http")
