"""Get current weather conditions and forecast."""
import logging
import os
import urllib.request
import urllib.parse
import json
from typing import Any, Dict

from reachy_mini_conversation_app.tools.core_tools import Tool, ToolDependencies

logger = logging.getLogger(__name__)

CONFIG_FILE = "/etc/reachy-companion/companion.env"


def _cfg(key: str, default: str = "") -> str:
    """Read a setting from the environment, then from the companion config file."""
    value = os.environ.get(key)
    if value:
        return value
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip().strip("\"'") or default
    except OSError:
        pass
    return default


def _float(value: str, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


DEFAULT_LAT = _float(_cfg("WEATHER_LATITUDE"), 0.0)
DEFAULT_LON = _float(_cfg("WEATHER_LONGITUDE"), 0.0)
DEFAULT_NAME = _cfg("WEATHER_LOCATION_NAME", "home")
UNITS = _cfg("WEATHER_UNITS", "fahrenheit").lower()
METRIC = UNITS.startswith("c")

WEATHER_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "depositing rime fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    61: "light rain", 63: "moderate rain", 65: "heavy rain",
    66: "light freezing rain", 67: "heavy freezing rain",
    71: "light snow", 73: "moderate snow", 75: "heavy snow",
    77: "snow grains",
    80: "light rain showers", 81: "moderate rain showers", 82: "violent rain showers",
    85: "light snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with light hail", 99: "thunderstorm with heavy hail",
}


def _geocode(location_name):
    url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode({
        "name": location_name, "count": 1, "language": "en", "format": "json",
    })
    with urllib.request.urlopen(url, timeout=5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data.get("results"):
        return None
    r = data["results"][0]
    return r["latitude"], r["longitude"], f"{r['name']}, {r.get('admin1', r.get('country', ''))}"


def _fetch_weather(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "temperature_unit": "celsius" if METRIC else "fahrenheit",
        "wind_speed_unit": "kmh" if METRIC else "mph",
        "precipitation_unit": "mm" if METRIC else "inch",
        "timezone": "auto",
        "forecast_days": 2,
    })
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


class Weather(Tool):
    name = "weather"
    description = (
        "Get current weather conditions and a short forecast. "
        "Use this when the user asks about the weather, temperature, rain, or outdoor conditions. "
        "Defaults to the user's home location if no location is provided."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "Optional city name. If omitted, uses home location.",
            },
        },
        "required": [],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        location_name = kwargs.get("location")
        try:
            if location_name:
                geo = _geocode(location_name)
                if geo is None:
                    return {"error": f"Could not find location: {location_name}"}
                lat, lon, resolved_name = geo
            else:
                if DEFAULT_LAT == 0.0 and DEFAULT_LON == 0.0:
                    return {"error": "No home location is set. Add WEATHER_LATITUDE and WEATHER_LONGITUDE to companion.env, or name a city."}
                lat, lon, resolved_name = DEFAULT_LAT, DEFAULT_LON, DEFAULT_NAME
            data = _fetch_weather(lat, lon)
            current = data.get("current", {})
            daily = data.get("daily", {})
            condition = WEATHER_CODES.get(current.get("weather_code"), "unknown")
            result = {
                "location": resolved_name,
                "units": "celsius, km/h" if METRIC else "fahrenheit, mph",
                "current": {
                    "condition": condition,
                    "temperature": current.get("temperature_2m"),
                    "feels_like": current.get("apparent_temperature"),
                    "humidity_pct": current.get("relative_humidity_2m"),
                    "wind_speed": current.get("wind_speed_10m"),
                },
                "today": {
                    "high": daily.get("temperature_2m_max", [None])[0],
                    "low": daily.get("temperature_2m_min", [None])[0],
                    "precipitation_chance_pct": daily.get("precipitation_probability_max", [None])[0],
                },
                "tomorrow": {
                    "condition": WEATHER_CODES.get(daily.get("weather_code", [None, None])[1], "unknown"),
                    "high": daily.get("temperature_2m_max", [None, None])[1],
                    "low": daily.get("temperature_2m_min", [None, None])[1],
                },
            }
            logger.info(f"Tool call: weather location={resolved_name} condition={condition}")
            return result
        except Exception as e:
            logger.error(f"Weather fetch failed: {e}")
            return {"error": f"Could not fetch weather: {e}"}
