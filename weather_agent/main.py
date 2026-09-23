"""Entrypoint for serving the Weather Agent over the A2A protocol."""

import json
import os
import subprocess
from dotenv import load_dotenv
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from weather_agent.agent import root_agent

# 1. Automatically load .env if present
load_dotenv()

# 2. Automatically discover GOOGLE_CLOUD_PROJECT from terminal/gcloud or ADC if missing
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

# Determine port from Cloud Run environment (defaults to 8080)
port = int(os.environ.get("PORT", "8080"))

# Locate explicit Agent Card (agent.json) and ensure required schema fields exist
agent_card_path = os.path.join(os.path.dirname(__file__), "agent.json")


def _load_agent_card():
    """Safely loads agent.json ensuring all A2A specification required fields exist."""
    if not os.path.exists(agent_card_path):
        return None
    try:
        from a2a.types import AgentCard

        with open(agent_card_path, "r") as f:
            card_data = json.load(f)
        # Ensure mandatory A2A schema fields are present
        card_data.setdefault("url", f"http://localhost:{port}")
        card_data.setdefault("defaultInputModes", ["text/plain"])
        card_data.setdefault("defaultOutputModes", ["text/plain", "application/json"])
        card_data.setdefault("capabilities", {"streaming": True})
        if "skills" in card_data and isinstance(card_data["skills"], list):
            for skill in card_data["skills"]:
                if isinstance(skill, dict):
                    skill.setdefault("tags", ["weather", "search-grounding"])
        return AgentCard(**card_data)
    except Exception:
        # Fall back to automatic generation by ADK
        return None


# Convert the ADK agent to an A2A-compliant ASGI application
app = to_a2a(
    root_agent,
    agent_card=_load_agent_card(),
    port=port,
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
