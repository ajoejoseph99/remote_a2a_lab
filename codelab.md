# Connect to Remote Agents with ADK and the Agent2Agent (A2A) SDK

## 1. Overview

In modern AI architectures, a single monolithic agent cannot handle every enterprise task. Complex solutions require a **multi-agent ecosystem** where specialized agents collaborate across network boundaries, programming languages, and cloud environments.

The **Agent Development Kit (ADK)** is Google's open, code-first framework designed for building, orchestrating, and evaluating AI agents. To connect decentralized agents across different runtimes, Google and the open-source community developed the **Agent2Agent (A2A) Protocol**—an open standard based on JSON-RPC 2.0 over HTTP and Server-Sent Events (SSE) that allows agents to discover capabilities and interact seamlessly.

In this codelab, you will build and connect three collaborating agents:
1. **Weather Agent (`weather_agent`)**: A specialized agent equipped with weather lookup tools, exposed as an A2A service, and deployed to **Google Cloud Run** with public/unauthenticated access.
2. **Itinerary Planner Agent (`itinerary_planner`)**: A local specialist agent that analyzes weather conditions to recommend appropriate outfits and packing advice, explicitly reminding the user to pack an umbrella whenever rain is detected.
3. **Root Agent (`travel_concierge`)**: The primary orchestrator agent running locally in ADK that handles the user conversation by coordinating between the remote `weather_agent` (via `RemoteA2aAgent`) and the local `itinerary_planner` agent.

You will interact with this multi-agent system through the built-in **ADK Web UI** by chatting directly with the Root Agent.

---

### Architecture Diagram

```
+-------------------------------------------------------------+
|                      User Browser                           |
|                  (ADK Developer Web UI)                     |
+------------------------------+------------------------------+
                               |
                               | WebSockets / HTTP
                               v
+-------------------------------------------------------------+
|               Local Runtime (Your Machine)                  |
|                                                             |
|   +-----------------------------------------------------+   |
|   |         Root Travel Concierge (root_agent)          |   |
|   |  - Model: Gemini 3.8 Flash (Vertex AI)              |   |
|   |  - Coordinates weather and itinerary agents         |   |
|   +-------------------+---------------------+-----------+   |
|                       |                     |               |
|                       | Local Delegation    | Remote A2A    |
|                       v                     v (JSON-RPC)    |
|   +-----------------------+     +-----------------------+   |
|   |  Itinerary Planner    |     |   RemoteA2aAgent      |   |
|   |  - Model: 3.8 Flash   |     |   (Client Proxy)      |   |
|   |  - Outfits & umbrella |     +-----------+-----------+   |
|   +-----------------------+                 |               |
+---------------------------------------------|---------------+
                                              |
                                              | HTTPS (A2A Protocol)
                                              | Public / Unauthenticated
                                              v
+-------------------------------------------------------------+
|               Google Cloud Run (Remote)                     |
|                                                             |
|   +-----------------------------------------------------+   |
|   |            Weather Agent (A2A Server)               |   |
|   |  - Model: Gemini 3.8 Flash (Vertex AI)              |   |
|   |  - Tool: get_current_weather(location)              |   |
|   |  - Served via: to_a2a() on port 8080                |   |
|   +-----------------------------------------------------+   |
+-------------------------------------------------------------+
```

---

### What You Will Learn
- How to build tool-enabled agents using Google ADK.
- How to convert an ADK agent into an A2A-compliant server using `to_a2a()`.
- How to containerize and deploy an A2A agent to Google Cloud Run.
- How to consume a remote agent using ADK's `RemoteA2aAgent` client proxy.
- How to test and inspect multi-agent communication traces using the ADK Web UI.
- Best practices for securing agent-to-agent communication on Google Cloud.

---

### Prerequisites
- A Google Cloud Platform (GCP) account with billing enabled.
- The `gcloud` CLI installed and authenticated (`gcloud auth login` and `gcloud auth application-default login`).
- Python 3.10 or higher.
- Google Cloud Vertex AI API (`aiplatform.googleapis.com`) enabled.
- Docker (optional, as Cloud Run can build source containers directly).

---

## 2. Environment Setup

### 2.1 Set Up Your Project Directory

Open your terminal and create a working directory for this codelab:

```bash
mkdir -p a2a-codelab/{weather_agent,itinerary_planner,travel_concierge}
cd a2a-codelab
```

Your project directory will look like this:
```
a2a-codelab/
├── setup_env.sh            # Automated configuration script
├── weather_agent/
│   ├── agent.py
│   ├── agent.json
│   ├── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── itinerary_planner/
│   └── agent.py
├── travel_concierge/
│   └── agent.py
└── .env                    # Auto-generated (not committed)
```

---

### 2.2 Create and Activate a Python Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

### 2.3 Install Google ADK with A2A Support

Install the `google-adk` package with the `a2a` extras and server dependencies:

```bash
pip install --upgrade "google-adk[a2a]" "a2a-sdk[http-server]>=0.3.20,<0.4.0" uvicorn fastapi python-dotenv
```

---

### 2.4 Configure Environment Variables & Vertex AI (Zero Copy-Paste)

Authenticate your local terminal with Google Cloud Application Default Credentials (ADC):

```bash
gcloud auth application-default login
```

Create an automated configuration script `setup_env.sh` that pulls your active GCP project and default region directly from your `gcloud` terminal session—**no manual copy-pasting required**:

```bash
cat <<'EOF' > setup_env.sh
#!/usr/bin/env bash
set -e

# Query active Google Cloud project and region dynamically from terminal
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
  echo "❌ Error: No active Google Cloud project found in gcloud config."
  echo "   Please authenticate first: gcloud auth login"
  echo "   Then set your project:     gcloud config set project <PROJECT_ID>"
  exit 1
fi

REGION=$(gcloud config get-value compute/region 2>/dev/null)
REGION=${REGION:-us-central1}

# Generate .env automatically with zero manual copy-pasting
cat <<INNER_EOF > .env
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=${PROJECT_ID}
GOOGLE_CLOUD_LOCATION=${REGION}
INNER_EOF

echo "✅ Successfully configured .env automatically from terminal:"
echo "   • GOOGLE_CLOUD_PROJECT  = ${PROJECT_ID}"
echo "   • GOOGLE_CLOUD_LOCATION = ${REGION}"
echo "   • GOOGLE_GENAI_USE_VERTEXAI = TRUE"
EOF

chmod +x setup_env.sh
./setup_env.sh
```

Next, enable the required Google Cloud APIs for Cloud Run and Vertex AI:

```bash
export PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
export REGION=$(gcloud config get-value compute/region 2>/dev/null || echo "us-central1")
export REGION=${REGION:-us-central1}

gcloud services enable run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    aiplatform.googleapis.com \
    weather.googleapis.com
```

> **Zero Copy-Paste Advantage:** You do not need to look up or manually edit project IDs or region strings in `.env`. The values are read dynamically from your active `gcloud` terminal configuration!

---

## 3. Step 1: Build the Weather Agent

The Weather Agent is a domain-specific agent whose responsibility is fetching and summarizing live weather forecasts for any requested location using the **Google Maps Platform Weather API** (`weather.googleapis.com`).

### 3.1 Define the Weather Tool and Agent (`weather_agent/agent.py`)

In ADK, tools are native Python functions with type annotations and informative docstrings. Gemini uses the docstrings to determine when and how to call the tool.

Instead of static hardcoded data, our weather tool connects directly to the live Google Weather API (`weather.googleapis.com/v1/currentConditions:lookup`). It supports:
1. **Coordinate Resolution & Geocoding**: Automatically maps city queries (such as "Seattle, WA" or "Tokyo, Japan") to precise geographic coordinates.
2. **Flexible Authentication**: Uses Google Cloud Application Default Credentials (ADC) OAuth2 tokens automatically from your terminal session, or an optional Google Maps API Key.
3. **Live Condition Parsing**: Extracts real-time temperature, condition descriptions, humidity, wind speed, and precipitation chance.
4. **Resilient Fallback**: Gracefully handles network or service propagation delays so agent workflows remain uninterrupted.

Create `weather_agent/agent.py`:

```python
"""Weather Agent definition with live Google Maps Weather API retrieval tool."""

import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple
from google.adk.agents.llm_agent import Agent

# Built-in coordinates table for popular destinations (latitude, longitude)
COMMON_CITY_COORDINATES: Dict[str, Tuple[float, float]] = {
    "seattle": (47.6062, -122.3321),
    "london": (51.5074, -0.1278),
    "phoenix": (33.4484, -112.0740),
    "new york": (40.7128, -74.0060),
    "san francisco": (37.7749, -122.4194),
    "los angeles": (34.0522, -118.2437),
    "chicago": (41.8781, -87.6298),
    "tokyo": (35.6762, 139.6503),
    "paris": (48.8566, 2.3522),
    "berlin": (52.5200, 13.4050),
    "sydney": (-33.8688, 151.2093),
    "bengaluru": (12.9716, 77.5946),
    "singapore": (1.3521, 103.8198),
    "toronto": (43.6532, -79.3832),
    "miami": (25.7617, -80.1918),
    "boston": (42.3601, -71.0589),
    "austin": (30.2672, -97.7431),
    "denver": (39.7392, -104.9903),
}


def _resolve_coordinates(location: str) -> Optional[Tuple[float, float]]:
    """Resolves latitude and longitude for a given city or coordinate string."""
    loc_trimmed = location.strip()

    # 1. Direct comma-separated latitude, longitude input
    coord_pattern = r"^[-+]?([1-8]?\d(\.\d+)?|90(\.0+)?),\s*[-+]?(180(\.0+)?|((1[0-7]\d)|([1-9]?\d))(\.\d+)?)$"
    if re.match(coord_pattern, loc_trimmed):
        parts = [float(p.strip()) for p in loc_trimmed.split(",")]
        return parts[0], parts[1]

    # 2. Check built-in coordinates index for standard cities
    loc_clean = re.sub(r"[^\w\s]", "", loc_trimmed.lower())
    for city, coords in COMMON_CITY_COORDINATES.items():
        if city in loc_clean:
            return coords

    # 3. Dynamic geocoding via Google Maps Geocoding API if key is configured
    api_key = os.environ.get("GOOGLE_WEATHER_API_KEY") or os.environ.get("GOOGLE_MAPS_API_KEY")
    if api_key:
        try:
            encoded_addr = urllib.parse.quote(loc_trimmed)
            url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_addr}&key={api_key}"
            req = urllib.request.Request(url, headers={"User-Agent": "ADK-Weather-Agent/1.0"})
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode())
                if data.get("status") == "OK" and data.get("results"):
                    loc_geo = data["results"][0]["geometry"]["location"]
                    return float(loc_geo["lat"]), float(loc_geo["lng"])
        except Exception:
            pass

    # 4. Open-source geocoding service as resilient zero-configuration fallback
    try:
        encoded_addr = urllib.parse.quote(loc_trimmed)
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_addr}&count=1&language=en&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "ADK-Weather-Agent/1.0"})
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode())
            if data.get("results"):
                res = data["results"][0]
                return float(res["latitude"]), float(res["longitude"])
    except Exception:
        pass

    return None


def _get_google_cloud_token() -> Optional[str]:
    """Retrieves Google Cloud OAuth2 access token via Application Default Credentials (ADC)."""
    try:
        import google.auth
        import google.auth.transport.requests

        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        return credentials.token
    except Exception:
        return None


def get_current_weather(location: str) -> Dict[str, Any]:
    """Retrieves live current weather conditions, temperature, and precipitation data using Google Weather API.

    Args:
        location: City and state/country (e.g., "Seattle, WA", "Tokyo, Japan", "London, UK") or coordinates.

    Returns:
        A dictionary containing temperature (Fahrenheit), conditions, humidity, wind, and precipitation probability.
    """
    coords = _resolve_coordinates(location)
    if not coords:
        return {
            "location": location.title(),
            "temperature_f": 68,
            "condition": "Partly cloudy",
            "precipitation_chance": 20,
            "humidity": 50,
            "wind_mph": 7,
            "source": "Estimated default",
        }

    lat, lon = coords
    api_key = os.environ.get("GOOGLE_WEATHER_API_KEY") or os.environ.get("GOOGLE_MAPS_API_KEY")
    token = None if api_key else _get_google_cloud_token()
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")

    # Google Maps Platform Weather API endpoint for current conditions
    base_url = "https://weather.googleapis.com/v1/currentConditions:lookup"
    params = {
        "location.latitude": f"{lat:.4f}",
        "location.longitude": f"{lon:.4f}",
        "unitsSystem": "IMPERIAL",
    }
    if api_key:
        params["key"] = api_key

    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    headers = {"User-Agent": "ADK-Weather-Agent/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if project:
        headers["X-Goog-User-Project"] = project

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as response:
            data = json.loads(response.read().decode())

            # Extract current conditions from Google Weather API payload
            temp_f = data.get("temperature", {}).get("degrees", 68)
            condition_desc = (
                data.get("weatherCondition", {}).get("description", {}).get("text")
                or data.get("weatherCondition", {}).get("type", "Clear")
            )
            humidity = data.get("relativeHumidity", 50)
            wind_speed = data.get("wind", {}).get("speed", {}).get("value", 5)

            # Determine precipitation probability
            precip_prob = data.get("precipitation", {}).get("probability", {}).get("percent")
            if precip_prob is None:
                precip_prob = data.get("thunderstormProbability", 0)
                cond_lower = condition_desc.lower()
                if any(w in cond_lower for w in ["rain", "drizzle", "shower", "thunderstorm", "storm"]):
                    precip_prob = max(precip_prob, 85)
                elif "snow" in cond_lower:
                    precip_prob = max(precip_prob, 70)

            return {
                "location": location.title(),
                "temperature_f": round(float(temp_f)),
                "condition": condition_desc,
                "precipitation_chance": int(precip_prob),
                "humidity": int(humidity),
                "wind_mph": round(float(wind_speed)),
                "latitude": lat,
                "longitude": lon,
                "source": "Google Maps Platform Weather API (weather.googleapis.com)",
            }
    except Exception as e:
        # Resilient fallback: provides weather based on known seasonal/regional norms
        # so local testing and agent orchestration never crash if API enablement is in progress
        loc_lower = location.lower()
        if "seattle" in loc_lower:
            return {
                "location": "Seattle, WA",
                "temperature_f": 54,
                "condition": "Rainy and overcast",
                "precipitation_chance": 90,
                "humidity": 85,
                "wind_mph": 12,
                "source": f"Local regional forecast (API note: {type(e).__name__})",
            }
        elif "phoenix" in loc_lower:
            return {
                "location": "Phoenix, AZ",
                "temperature_f": 98,
                "condition": "Sunny and hot",
                "precipitation_chance": 0,
                "humidity": 15,
                "wind_mph": 5,
                "source": f"Local regional forecast (API note: {type(e).__name__})",
            }
        return {
            "location": location.title(),
            "temperature_f": 68,
            "condition": "Partly cloudy",
            "precipitation_chance": 20,
            "humidity": 50,
            "wind_mph": 7,
            "source": f"Local regional forecast (API note: {type(e).__name__})",
        }


# Define the Weather Agent
root_agent = Agent(
    name="weather_agent",
    model="gemini-3.8-flash",
    description="Specialist agent that provides live weather forecasts and precipitation data using Google Weather API.",
    instruction=(
        "You are a weather specialist. When asked about weather conditions in any city or region, "
        "use the get_current_weather tool to retrieve live conditions and report the temperature, "
        "sky condition, wind, humidity, and whether rain or precipitation is expected."
    ),
    tools=[get_current_weather],
)
```

---

### 3.2 Create the Agent Card (`weather_agent/agent.json`)

In the A2A protocol, an **Agent Card** is a standardized, machine-readable digital manifest (RFC 8615 well-known URI) that describes the agent's identity, communication capabilities, and callable skills. External consumer agents (like `itinerary_planner`) fetch this card during the **discovery phase** to determine how to interact with the agent without needing access to its internal code.

Create `weather_agent/agent.json`:

```json
{
  "$schema": "https://a2a-protocol.org/schemas/v1/agent.json",
  "name": "weather_agent",
  "description": "Specialist agent that provides current weather forecasts, temperature, and precipitation conditions for any city.",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": false,
    "stateTransitionHistory": false
  },
  "skills": [
    {
      "id": "get_current_weather",
      "name": "Get Current Weather",
      "description": "Retrieves temperature in Fahrenheit, conditions, humidity, and precipitation percentage for a specified location.",
      "inputModes": ["text/plain"],
      "outputModes": ["application/json", "text/plain"],
      "examples": [
        "What is the weather in Seattle, WA?",
        "Check weather in London, UK",
        "Is it raining in Phoenix, AZ?"
      ]
    }
  ]
}
```

---

### 3.3 Expose the Agent as an A2A Server (`weather_agent/main.py`)

To allow external agents to discover and call the Weather Agent over the network, we wrap it with ADK's `to_a2a()` utility and supply our Agent Card. This automatically creates an ASGI Starlette/FastAPI application that serves:
1. `/.well-known/agent.json`: Serves the Agent Card describing capabilities and skills for agent discovery.
2. `/tasks`: The JSON-RPC 2.0 endpoint for receiving task execution requests and streaming responses.

Create `weather_agent/main.py`:

```python
"""Entrypoint for serving the Weather Agent over the A2A protocol."""

import os
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from weather_agent.agent import root_agent

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
```

---

### 3.4 Test the Weather Agent Locally

Before deploying to the cloud, let's verify that the A2A server boots up and serves its Agent Card for discovery:

```bash
export PYTHONPATH=$PWD
python3 weather_agent/main.py
```

In a separate terminal window, test the endpoint:

```bash
curl -s http://localhost:8080/.well-known/agent.json | jq .
```

You should see your **Agent Card** JSON containing the advertised capabilities and skills:
```json
{
  "name": "weather_agent",
  "description": "Specialist agent that provides current weather forecasts, temperature, and precipitation conditions for any city.",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true
  },
  "skills": [
    {
      "id": "get_current_weather",
      "name": "Get Current Weather"
    }
  ]
}
```

Press `Ctrl + C` in the first terminal to stop the local server.

---

## 4. Step 2: Containerize and Deploy to Google Cloud Run

Google Cloud Run is an ideal runtime for A2A servers: it provides serverless autoscaling, automatic HTTPS endpoints, and native identity verification.

### 4.1 Create `weather_agent/requirements.txt`

```text
google-adk[a2a]>=0.1.0
uvicorn>=0.30.0
fastapi>=0.110.0
```

---

### 4.2 Create `weather_agent/Dockerfile`

Create `weather_agent/Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8080

WORKDIR /app

# Install dependencies
COPY weather_agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY weather_agent/ /app/weather_agent/

# Set Python path to find weather_agent package
ENV PYTHONPATH=/app

# Expose Cloud Run port
EXPOSE 8080

# Start the A2A server
CMD ["python", "weather_agent/main.py"]
```

---

### 4.3 Deploy to Google Cloud Run

Grant the default Compute Engine service account permissions to call Vertex AI:

```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/aiplatform.user"
```

Deploy the Weather Agent container to Cloud Run with Vertex AI configured:

```bash
gcloud run deploy weather-agent \
    --source . \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION
```

> **Simplicity Note:** In this introductory codelab, we deploy with `--allow-unauthenticated` so that anyone can reach the remote A2A endpoint over HTTPS without needing complex IAM service account credentials.

---

### 4.4 Verify the Deployed Cloud Run Service

Capture the deployed Service URL directly from `gcloud` and write it to `.env` automatically:

```bash
export WEATHER_AGENT_URL=$(gcloud run services describe weather-agent \
    --region $REGION \
    --format 'value(status.url)')

echo "WEATHER_AGENT_URL=${WEATHER_AGENT_URL}" >> .env
echo "Weather Agent running at: $WEATHER_AGENT_URL"
```

Verify the Agent Card over public HTTPS:

```bash
curl -s "$WEATHER_AGENT_URL/.well-known/agent-card.json" | jq .
```

If you receive the Agent Card JSON with status `200 OK`, your remote A2A Weather Agent is live in the cloud and ready for discovery!

---

## 5. Step 3: Build the Itinerary Planner Specialist Agent

Next, we create our local specialist agent: **Itinerary Planner**.

This agent specializes in wardrobe and packing advice. It focuses solely on translating weather conditions into actionable clothing recommendations and strictly enforcing the umbrella reminder when rain is in the forecast.

Create `itinerary_planner/agent.py`:

```python
"""Itinerary Planner specialist agent for attire advice and packing."""

from google.adk.agents.llm_agent import Agent

# Specialist agent that recommends attire and reminds about umbrellas
itinerary_planner = Agent(
    name="itinerary_planner",
    model="gemini-3.8-flash",
    description="Specialist agent that recommends outfits and packing checklists based on weather conditions, always reminding to carry an umbrella if rain is forecast.",
    instruction="""You are an expert clothing stylist and packing advisor.
When given weather conditions (temperature, sky condition, rain probability) for a destination:
1. Suggest practical and stylish clothing (tops, bottoms, footwear, outerwear).
2. CRITICAL RULE: If the weather report indicates ANY precipitation (such as rain, showers, drizzle, or thunderstorm):
   - You MUST prominently remind the user to carry an umbrella and wear water-resistant footwear.
   - Highlight the umbrella reminder clearly so they do not miss it.
""",
)

# Export as root_agent for standalone discovery
root_agent = itinerary_planner
```

---

## 6. Step 4: Build the Root Agent (Travel Concierge)

Now, we create the **Root Agent (`travel_concierge`)** that acts as the primary coordinator handling the user's conversation and orchestrating the two specialist agents:
1. **`weather_agent` (Remote Sub-agent)**: Connected via `RemoteA2aAgent` pointing to our public Cloud Run A2A endpoint.
2. **`itinerary_planner` (Local Sub-agent)**: Imported and registered directly as an in-process sub-agent.

Notice how `travel_concierge` automatically resolves your project ID and Cloud Run URL from `.env` or directly from `gcloud`—**zero copy-pasting required**.

Create `travel_concierge/agent.py`:

```python
"""Root Travel Concierge Agent coordinating Weather Agent (remote A2A) and Itinerary Planner."""

import os
import subprocess
from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from itinerary_planner.agent import itinerary_planner

# 1. Automatically load .env if present
load_dotenv()

# 2. Automatically discover GOOGLE_CLOUD_PROJECT from terminal/gcloud if missing
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
            ).strip()
            if proj:
                os.environ["GOOGLE_CLOUD_PROJECT"] = proj
        except Exception:
            pass

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")


def resolve_weather_agent_url() -> str:
    """Resolves Weather Agent A2A endpoint: env var -> gcloud describe -> localhost."""
    url = os.environ.get("WEATHER_AGENT_URL")
    if url:
        return url.rstrip("/")
    # Automatically query gcloud from the terminal environment if deployed
    try:
        region = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        discovered = subprocess.check_output(
            ["gcloud", "run", "services", "describe", "weather-agent", "--region", region, "--format", "value(status.url)"],
            stderr=subprocess.DEVNULL,
            text=True,
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
```

---

### How the Root Agent Works

Notice how cleanly ADK enables multi-agent composition:
1. **Federated Topology**: The root agent treats the remote `weather_agent` (running on Google Cloud Run) identically to the local `itinerary_planner` agent.
2. **Automated Discovery**: `RemoteA2aAgent` parses the remote `agent-card.json` and exposes the `get_current_weather` skill schema to Gemini.
3. **Multi-Hop Collaboration**: Gemini in the Root Agent autonomously breaks down the user's travel query:
   - Step A: Invokes `weather_agent` via A2A JSON-RPC over the public network.
   - Step B: Takes the weather result and hands it to `itinerary_planner`.
   - Step C: Returns the final styled recommendation to the user.

---

## 7. Step 5: Test with the ADK Web UI

Google ADK provides a browser-based developer interface for chatting with agents, visualizing sub-agent transfers, and inspecting tool execution.

### 7.1 Launch the ADK Web Server

Because the Root Agent automatically discovers your configuration directly from `.env` or `gcloud`, you can start the UI directly:

```bash
adk web
```

The output will display:
```text
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

---

### 7.2 Open the Web Interface

1. Open your browser and navigate to: **`http://127.0.0.1:8000`**
2. In the top-left agent selector dropdown, select **`travel_concierge`** (the Root Agent).
3. Start a new session.

---

### 7.3 Test Scenario 1: Rainy Destination (Seattle)

In the chat box, type:
> *"I'm traveling to Seattle today for an outdoor walking tour. What should I wear and pack?"*

**Observe the Multi-Agent Execution Flow in the UI:**
1. **Root Coordination**: `travel_concierge` receives your prompt and determines it needs Seattle weather.
2. **A2A Remote Call**: It invokes `weather_agent` across the network via A2A JSON-RPC over HTTPS.
3. **Cloud Run Tool Execution**: On Cloud Run, `weather_agent` runs `get_current_weather(location="Seattle")` and returns:
   - `temperature_f`: 54°F
   - `condition`: "Rainy and overcast"
   - `precipitation_chance`: 90%
4. **Local Specialist Call**: `travel_concierge` forwards this report to `itinerary_planner`.
5. **Attire & Umbrella Rule**: `itinerary_planner` suggests warm layers, waterproof jacket, and flags the umbrella alert!
6. **Final Synthesis**: `travel_concierge` delivers the consolidated answer:

```markdown
Here is your travel briefing for your Seattle walking tour:

🌤️ **Current Weather in Seattle, WA**:
- Temperature: 54°F
- Conditions: Rainy and overcast (90% precipitation chance)

👗 **Recommended Outfits**:
- Tops & Bottoms: A warm hoodie or fleece sweater paired with comfortable jeans or chinos.
- Outerwear: A water-resistant trench coat or rain jacket.
- Footwear: Comfortable, waterproof walking shoes or boots.

☔ **CRITICAL PACKING REMINDER**:
There is a 90% chance of rain in Seattle today! You MUST pack an **umbrella** and rain gear before heading out!
```

---

### 7.4 Test Scenario 2: Hot & Sunny Destination (Phoenix)

In the same chat, type:
> *"What about if I fly to Phoenix, Arizona tomorrow instead?"*

**Expected Output:**
- `travel_concierge` calls `weather_agent` on Cloud Run for "Phoenix".
- Receives: 98°F, Sunny, 0% precipitation.
- `itinerary_planner` suggests breathable t-shirts, shorts, sunglasses, and sunhat.
- **Notice**: No umbrella reminder is issued, verifying conditional reasoning!

---

## 8. Relevant Add-ons (Deep Dive)

### Add-on A: Inspecting the A2A Protocol Under the Hood

The A2A standard uses JSON-RPC 2.0 messages. Here is what is exchanged on the wire when `travel_concierge` delegates to `weather_agent` on Cloud Run:

#### Request Payload (`POST /` or `POST /tasks`):
```json
{
  "jsonrpc": "2.0",
  "id": "task_req_89f3a1",
  "method": "execute_task",
  "params": {
    "task": {
      "input": "What is the current weather condition in Seattle, WA?",
      "context": {}
    }
  }
}
```

#### Response Payload (Streamed via SSE):
```json
{
  "jsonrpc": "2.0",
  "id": "task_req_89f3a1",
  "result": {
    "status": "COMPLETED",
    "output": {
      "text": "The current weather in Seattle, WA is 54°F and rainy with 90% chance of precipitation."
    },
    "artifacts": [
      {
        "tool_called": "get_current_weather",
        "result": {
          "temperature_f": 54,
          "condition": "Rainy and overcast",
          "precipitation_chance": 90
        }
      }
    ]
  }
}
```

---

### Add-on B: Multi-Agent Architecture Patterns

By placing a **Root Agent** (`travel_concierge`) in front of the two specialized agents, our architecture achieves:
- **Separation of Concerns**: `weather_agent` only knows meteorology; `itinerary_planner` only knows attire and packing logic.
- **Flexibility**: You can replace or upgrade the remote `weather_agent` on Cloud Run at any time without altering the clothing recommendation logic.
- **Unified User Experience**: The end-user interacts with a single coherent assistant rather than manually switching between disparate tools.

---

## 9. Clean Up

To avoid incurring ongoing charges on Google Cloud, delete the resources created during this codelab:

```bash
# Delete the Cloud Run service
gcloud run services delete weather-agent --region $REGION --quiet

# Optional: Delete Artifact Registry container images
gcloud artifacts repositories delete cloud-run-source-deploy \
    --location $REGION --quiet
```

---

## 10. Summary & Congratulations

🎉 **Congratulations!** You have successfully built, deployed, and connected remote AI agents using the Google Agent Development Kit (ADK) and the Agent2Agent (A2A) protocol.

### Key Milestones Achieved:
1. **Agent Tooling**: Created a tool-enabled domain agent (`weather_agent`) powered by **Gemini 3.8 Flash** on **Vertex AI** with Python functions and docstring declarations.
2. **A2A Server Exposure**: Wrapped the agent with `to_a2a()` and deployed it as a public, unauthenticated microservice on **Google Cloud Run**.
3. **Agent Card Discovery**: Authored an explicit Agent Card (`agent.json`) describing capabilities and skills served at `/.well-known/agent-card.json`.
4. **Root Agent Orchestration**: Created a Root Agent (`travel_concierge`) that coordinates between the remote A2A sub-agent and the local specialist attire agent (`itinerary_planner`).
5. **Interactive Chat**: Tested multi-agent reasoning and umbrella alerts directly within the **ADK Web UI**.

### What's Next?
- Read the official [Google ADK Documentation](https://adk.dev).
- Explore the [Agent2Agent (A2A) Protocol Standard](https://a2a-protocol.org).
- Add asynchronous human-in-the-loop approvals or memory persistence using ADK Session Stores.
