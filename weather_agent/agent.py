"""Weather Agent definition with weather retrieval tool."""

from typing import Any, Dict
from google.adk.agents.llm_agent import Agent


def get_current_weather(location: str) -> Dict[str, Any]:
    """Retrieves current weather details, temperature, and precipitation conditions for a given location.

    Args:
        location: City and state/country (e.g., "Seattle, WA", "Tokyo, Japan", "London, UK").

    Returns:
        A dictionary containing temperature (Fahrenheit), conditions, humidity, and precipitation status.
    """
    loc = location.lower()

    # Deterministic mock responses for demonstration & testing
    if "seattle" in loc:
        return {
            "location": "Seattle, WA",
            "temperature_f": 54,
            "condition": "Rainy and overcast",
            "precipitation_chance": 90,
            "humidity": 85,
            "wind_mph": 12,
        }
    elif "london" in loc:
        return {
            "location": "London, UK",
            "temperature_f": 58,
            "condition": "Light drizzle",
            "precipitation_chance": 75,
            "humidity": 80,
            "wind_mph": 8,
        }
    elif "phoenix" in loc:
        return {
            "location": "Phoenix, AZ",
            "temperature_f": 98,
            "condition": "Sunny and hot",
            "precipitation_chance": 0,
            "humidity": 15,
            "wind_mph": 5,
        }
    else:
        # Default fallback for other locations
        return {
            "location": location.title(),
            "temperature_f": 68,
            "condition": "Partly cloudy",
            "precipitation_chance": 20,
            "humidity": 50,
            "wind_mph": 7,
        }


# Define the Weather Agent
root_agent = Agent(
    name="weather_agent",
    model="gemini-3.8-flash",
    description="Specialist agent that provides weather forecasts and precipitation data for any city.",
    instruction=(
        "You are a weather specialist. When asked about weather conditions in any city or region, "
        "use the get_current_weather tool to retrieve exact conditions and report the temperature, "
        "sky condition, and whether rain or precipitation is expected."
    ),
    tools=[get_current_weather],
)
