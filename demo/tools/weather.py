"""Mock weather tool — returns synthetic weather data with realistic delay."""
import time
import random

def get_weather(location: str, units: str = "celsius") -> dict:
    time.sleep(random.uniform(0.1, 0.3))  # simulate API latency
    conditions = random.choice(["sunny", "cloudy", "rainy", "partly cloudy"])
    temp = random.randint(15, 35) if units == "celsius" else random.randint(59, 95)
    return {
        "location": location,
        "temperature": temp,
        "units": units,
        "conditions": conditions,
        "humidity": random.randint(30, 90),
        "wind_speed_kmh": random.randint(5, 40),
    }

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a given location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City and country, e.g. 'Paris, France'"},
                "units": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "celsius"},
            },
            "required": ["location"],
        },
    },
}
