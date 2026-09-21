"""Root Travel Concierge Agent coordinating Weather Agent (remote A2A) and Itinerary Planner."""

import os
from google.adk.agents.llm_agent import Agent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from itinerary_planner.agent import itinerary_planner

# Retrieve remote Cloud Run A2A URL from environment variable or fallback to localhost
CLOUD_RUN_URL = os.environ.get("WEATHER_AGENT_URL", "http://localhost:8080")

# 1. Instantiate the Remote A2A Weather Agent Proxy
remote_weather_agent = RemoteA2aAgent(
    name="weather_agent",
    description="Remote specialist agent that retrieves live weather conditions, temperature, and precipitation percentage for any city.",
    agent_card=f"{CLOUD_RUN_URL}/.well-known/agent-card.json",
)

# 2. Define Root Orchestrator Instructions
ROOT_INSTRUCTIONS = """
You are the Root Travel Concierge. You assist travelers by coordinating their trip preparations end-to-end.

When a user asks about traveling to a city, planning a day out, or what they should wear/pack:
1. First, delegate to your remote 'weather_agent' sub-agent to fetch the current weather and precipitation forecast for the destination.
2. Second, pass the retrieved weather details to your 'itinerary_planner' sub-agent to generate clothing suggestions, footwear recommendations, and umbrella alerts.
3. Finally, combine the findings into a clear, friendly, and complete travel summary for the user.
"""

# 3. Define the Root Agent coordinating both sub-agents
root_agent = Agent(
    name="travel_concierge",
    model="gemini-3.8-flash",
    description="Root travel orchestrator that coordinates weather forecasting and attire planning across specialized agents.",
    instruction=ROOT_INSTRUCTIONS,
    sub_agents=[remote_weather_agent, itinerary_planner],
)
