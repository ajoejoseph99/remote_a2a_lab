"""Root Travel Concierge Agent coordinating Weather Agent (remote A2A) and Itinerary Planner."""

import os
import subprocess
from dotenv import load_dotenv
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.agents.sequential_agent import SequentialAgent
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

# Ensure Gemini 3.8 Flash uses the global publisher endpoint on Vertex AI
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"


def resolve_weather_agent_url() -> str:
    """Resolves Weather Agent A2A endpoint on Cloud Run via environment variable or live gcloud describe."""
    # 1. Prefer WEATHER_AGENT_URL from environment (.env)
    url = os.environ.get("WEATHER_AGENT_URL")
    if url and url.startswith("http"):
        return url.rstrip("/")

    # 2. Fall back to live Cloud Run service URL directly from gcloud if deployed
    try:
        region = os.environ.get("CLOUD_RUN_REGION")
        if not region:
            region = subprocess.check_output(
                ["gcloud", "config", "get-value", "compute/region"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=3,
            ).strip()
        region = region or "us-central1"
        discovered = subprocess.check_output(
            ["gcloud", "run", "services", "describe", "weather-agent", "--region", region, "--format", "value(status.url)"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
        ).strip()
        if discovered and discovered.startswith("http"):
            return discovered.rstrip("/")
    except Exception:
        pass

    raise RuntimeError(
        "Could not resolve Weather Agent Cloud Run URL. "
        "Please deploy weather-agent to Cloud Run or set WEATHER_AGENT_URL in .env."
    )


CLOUD_RUN_URL = resolve_weather_agent_url()

# 3. Instantiate the Remote A2A Weather Agent Proxy
# The proxy discovers capabilities by fetching /.well-known/agent-card.json from Cloud Run
remote_weather_agent = RemoteA2aAgent(
    name="weather_agent",
    description="Remote specialist agent that retrieves live weather conditions, temperature, and precipitation percentage for any city.",
    agent_card=f"{CLOUD_RUN_URL}/.well-known/agent-card.json",
)

# 4. Define the Root Agent executing sub-agents sequentially: weather_agent first, itinerary_planner second
root_agent = SequentialAgent(
    name="travel_concierge",
    description="Sequential travel concierge that executes weather retrieval via weather_agent followed by attire and packing planning via itinerary_planner.",
    sub_agents=[remote_weather_agent, itinerary_planner],
)
