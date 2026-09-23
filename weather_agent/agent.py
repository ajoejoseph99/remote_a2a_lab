"""Weather Agent definition powered by Gemini with Google Search Grounding."""

from google.adk.agents.llm_agent import Agent
from google.adk.tools import google_search

# Define the Weather Agent with Google Search Grounding
root_agent = Agent(
    name="weather_agent",
    model="gemini-3.8-flash",
    description="Specialist agent that provides live, grounded weather forecasts and precipitation data for any city using Google Search.",
    instruction=(
        "You are a weather specialist. When asked about weather conditions in any city or region, "
        "use the google_search tool to find the current live weather report. "
        "Always extract and clearly state: "
        "1. Current temperature (in Fahrenheit and Celsius). "
        "2. Sky conditions (e.g. sunny, cloudy, rainy, drizzle). "
        "3. Precipitation probability (chance of rain/snow percentage). "
        "4. Humidity and wind speed. "
        "Be concise, factual, and focused strictly on the weather forecast. "
        "Do not provide clothing, packing, or wardrobe suggestions; focus solely on the weather report."
    ),
    tools=[google_search],
)
