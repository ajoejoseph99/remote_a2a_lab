"""Entrypoint for serving the Weather Agent over the A2A protocol."""

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

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")

# Determine port from Cloud Run environment (defaults to 8080)
port = int(os.environ.get("PORT", "8080"))

# Locate explicit Agent Card (agent.json) if present
agent_card_path = os.path.join(os.path.dirname(__file__), "agent.json")

# Convert the ADK agent to an A2A-compliant ASGI application
app = to_a2a(
    root_agent,
    agent_card=agent_card_path if os.path.exists(agent_card_path) else None,
    port=port,
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)
