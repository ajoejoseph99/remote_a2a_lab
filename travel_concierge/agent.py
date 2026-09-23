"""Root Travel Concierge Agent coordinating Weather Agent (remote A2A) and Itinerary Planner."""

import os
import subprocess
from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from itinerary_planner.agent import itinerary_planner

# 1. Automatically load .env if present
load_dotenv()

# 2. Automatically resolve GOOGLE_CLOUD_PROJECT from terminal/gcloud or ADC if missing
if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
    try:
        import google.auth
        _, project = google.auth.default()
        if project:
            os.environ["GOOGLE_CLOUD_PROJECT"] = project
    except Exception:
        pass
    if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
        try:
            proj = subprocess.check_output(
                ["gcloud", "config", "get-value", "project"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=2,
            ).strip()
            if proj:
                os.environ["GOOGLE_CLOUD_PROJECT"] = proj
        except Exception:
            pass

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")


def resolve_weather_agent_url() -> str:
    """Resolves Weather Agent A2A endpoint: env var -> gcloud describe -> localhost."""
    url = os.environ.get("WEATHER_AGENT_URL")
    if url:
        return url.rstrip("/")
    # Automatically query gcloud from the terminal environment if deployed
    try:
        region = os.environ.get("CLOUD_RUN_REGION")
        if not region:
            region = subprocess.check_output(
                ["gcloud", "config", "get-value", "compute/region"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=2,
            ).strip()
        region = region or "us-central1"
        discovered = subprocess.check_output(
            ["gcloud", "run", "services", "describe", "weather-agent", "--region", region, "--format", "value(status.url)"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()
        if discovered:
            return discovered.rstrip("/")
    except Exception:
        pass
    return "http://localhost:8080"


CLOUD_RUN_URL = resolve_weather_agent_url()

# 3. Instantiate the Remote A2A Weather Agent Proxy
# The proxy discovers capabilities by fetching /.well-known/agent-card.json from Cloud Run
remote_weather_agent = RemoteA2aAgent(
    name="weather_agent",
    description="Remote specialist agent that retrieves live weather conditions, temperature, and precipitation percentage for any city.",
    agent_card=f"{CLOUD_RUN_URL}/.well-known/agent-card.json",
)

# 4. Define Root Orchestrator Instructions
ROOT_INSTRUCTIONS = """
You are the Root Travel Concierge. You assist travelers by coordinating their trip preparations end-to-end.

When a user asks about traveling to a city, planning a day out, or what they should wear/pack:
1. First, delegate to your remote 'weather_agent' sub-agent to fetch the current weather and precipitation forecast for the destination.
2. Second, pass the retrieved weather details to your 'itinerary_planner' sub-agent to generate clothing suggestions, footwear recommendations, and umbrella alerts.
3. Finally, combine the findings into a clear, friendly, and complete travel summary for the user.
"""

# 5. Define the Root Agent coordinating both sub-agents
root_agent = Agent(
    name="travel_concierge",
    model="gemini-3.8-flash",
    description="Root travel orchestrator that coordinates weather forecasting and attire planning across specialized agents.",
    instruction=ROOT_INSTRUCTIONS,
    sub_agents=[remote_weather_agent, itinerary_planner],
)
