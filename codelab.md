# Connect to Remote Agents with ADK and the Agent2Agent (A2A) SDK

## 1. Overview

In modern AI architectures, a single monolithic agent cannot handle every enterprise task. Complex solutions require a **multi-agent ecosystem** where specialized agents collaborate across network boundaries, programming languages, and cloud environments.

The **Agent Development Kit (ADK)** is Google's open, code-first framework designed for building, orchestrating, and evaluating AI agents powered by Gemini foundation models. To connect decentralized agents across different runtimes, Google and the open-source community developed the **Agent2Agent (A2A) Protocol**—an open standard based on JSON-RPC 2.0 over HTTP and Server-Sent Events (SSE) that allows agents to discover capabilities, negotiate modalities, and interact seamlessly.

In this codelab, you will build and connect three collaborating agents:
1. **Weather Agent (`weather_agent`)**: A remote domain specialist equipped with Vertex AI Google Search Grounding, exposed as an A2A service, and deployed to **Google Cloud Run** with public/unauthenticated access.
2. **Itinerary Planner Agent (`itinerary_planner`)**: A local specialist agent that evaluates weather conditions to recommend appropriate attire and packing checklists, explicitly reminding the user to pack an umbrella whenever rain is detected.
3. **Root Agent (`travel_concierge`)**: The primary orchestrator agent running locally in ADK that handles the end-to-end user conversation by coordinating between the remote `weather_agent` (via `RemoteA2aAgent`) and the local `itinerary_planner` agent using a deterministic `SequentialAgent` pipeline.

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
|   |  - Tool: google_search (Vertex AI Grounding)       |   |
|   |  - Served via: to_a2a() on port 8080                |   |
|   +-----------------------------------------------------+   |
+-------------------------------------------------------------+
```

---

### What You Will Learn
- How to construct tool-enabled domain agents using Google ADK and Vertex AI Search Grounding.
- How to expose an ADK agent as an A2A-compliant microservice using `to_a2a()`.
- How to author and serve an RFC 8615 Agent Card manifest (`agent.json`).
- How to containerize and deploy an A2A agent to Google Cloud Run.
- How to configure deterministic Cloud Run URLs for A2A discovery without requiring origin-rewriting middleware.
- How to consume a remote agent over the network using ADK's `RemoteA2aAgent` client proxy.
- How to orchestrate multi-agent pipelines deterministically using `SequentialAgent`.
- How to inspect multi-agent communication traces and execution graphs using the ADK Web UI.

---

### Prerequisites
- A Google Cloud Platform (GCP) project with billing enabled.
- The Google Cloud CLI (`gcloud`) installed and authenticated (`gcloud auth login` and `gcloud auth application-default login`).
- Python 3.10 or higher installed locally.
- Google Cloud Vertex AI API (`aiplatform.googleapis.com`) and Cloud Run API (`run.googleapis.com`) enabled.
- Basic familiarity with Python and asynchronous web services.

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
├── .dockerignore           # Excludes virtual environments and secrets from container build
├── .gcloudignore           # Excludes virtual environments from Cloud Build uploads
├── .env                    # Auto-generated by setup_env.sh (Vertex AI & GCP configs)
├── .env.example            # Environment template reference
├── Dockerfile              # Container specification for Google Cloud Run deployment
├── Procfile                # Cloud Run / Buildpacks process entrypoint
├── requirements.txt        # Single root dependencies file for ADK and all agents
├── setup_env.sh            # Automated environment configuration script for Google Cloud settings
├── weather_agent/          # Remote A2A Specialist Agent (deployed to Cloud Run)
│   ├── agent.py            # Weather specialist powered by Google Search Grounding
│   ├── agent.json          # A2A Agent Card specification manifest
│   └── main.py             # A2A ASGI server entrypoint with safe card loader
├── itinerary_planner/      # Local Specialist Agent
│   └── agent.py            # Wardrobe, packing, and umbrella reminder agent
└── travel_concierge/       # Root Orchestrator Agent (chats via ADK Web UI)
    └── agent.py            # Coordinates between remote Weather Agent & local Itinerary Planner
```

---

### 2.2 Create and Activate a Python Virtual Environment

Isolating your Python environment prevents dependency conflicts between your system packages and the libraries used in this codelab:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

### 2.3 Install Google ADK with A2A Support

Create `requirements.txt` in your project root to define the required packages:

```bash
cat <<'EOF' > requirements.txt
google-adk[a2a]>=0.1.0
a2a-sdk[http-server]>=0.3.20,<0.4.0
uvicorn>=0.30.0
fastapi>=0.110.0
google-auth>=2.29.0
python-dotenv>=1.0.0
EOF
```

Here is an overview of the key libraries:
- **`google-adk[a2a]`**: The core Google Agent Development Kit framework, including networking extensions for the Agent2Agent protocol.
- **`a2a-sdk[http-server]`**: The official Python implementation of the Agent2Agent protocol specification, providing data models, JSON-RPC 2.0 serialization, and HTTP server transports.
- **`uvicorn` & `fastapi`**: The ASGI server stack used by ADK to host the A2A discovery and task execution endpoints.
- **`google-auth`**: Manages Google Cloud Application Default Credentials (ADC) to authenticate requests to Vertex AI.
- **`python-dotenv`**: Loads configuration variables from `.env` into `os.environ`.

Install the dependencies:

```bash
pip install -r requirements.txt
```

---

### 2.4 Configure Environment Variables and Vertex AI

Authenticate your local environment using Google Cloud Application Default Credentials (ADC). This allows local scripts and ADK agents to securely access Vertex AI foundation models:

```bash
gcloud auth application-default login
```

Create an automated configuration script `setup_env.sh` that detects your active Google Cloud project, resolves your project number and region to calculate the deterministic Cloud Run service URL ahead of time, and configures the environment:

```bash
cat <<'EOF' > setup_env.sh
#!/usr/bin/env bash
set -e

# Query active Google Cloud project dynamically from terminal
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
  echo "❌ Error: No active Google Cloud project found in gcloud config."
  echo "   Please authenticate first: gcloud auth login"
  echo "   Then set your project:     gcloud config set project <PROJECT_ID>"
  exit 1
fi

# Query project number and region for deterministic Cloud Run URL
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)' 2>/dev/null)
REGION=$(gcloud config get-value compute/region 2>/dev/null || echo "us-central1")
REGION=${REGION:-us-central1}
SERVICE_NAME="weather-agent"

if [ -z "$PROJECT_NUMBER" ]; then
  echo "❌ Error: Could not determine PROJECT_NUMBER for project $PROJECT_ID."
  exit 1
fi

WEATHER_AGENT_URL="https://${SERVICE_NAME}-${PROJECT_NUMBER}.${REGION}.run.app"

# Set Vertex AI Model Location to global (required for Gemini 3.8 Flash)
LOCATION="global"

cat <<INNER_EOF > .env
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=${PROJECT_ID}
GOOGLE_CLOUD_LOCATION=${LOCATION}
WEATHER_AGENT_URL=${WEATHER_AGENT_URL}
INNER_EOF

# Generate weather_agent/agent.json dynamically with the deterministic Cloud Run URL
mkdir -p weather_agent
cat <<INNER_EOF > weather_agent/agent.json
{
  "name": "weather_agent",
  "description": "Specialist agent that provides current weather forecasts, temperature, and precipitation conditions for any city.",
  "version": "1.0.0",
  "url": "${WEATHER_AGENT_URL}",
  "defaultInputModes": [
    "text/plain"
  ],
  "defaultOutputModes": [
    "text/plain",
    "application/json"
  ],
  "capabilities": {
    "streaming": true
  },
  "skills": [
    {
      "id": "get_current_weather",
      "name": "Get Current Weather",
      "description": "Retrieves temperature, conditions, humidity, and precipitation percentage for any location using Google Search Grounding.",
      "tags": [
        "weather",
        "forecast",
        "precipitation",
        "search-grounding"
      ],
      "examples": [
        "What is the weather in Seattle, WA?",
        "Check weather in London, UK",
        "Is it raining in Phoenix, AZ?"
      ]
    }
  ]
}
INNER_EOF

echo "✅ Successfully configured environment:"
echo "   • GOOGLE_CLOUD_PROJECT      = ${PROJECT_ID}"
echo "   • GOOGLE_CLOUD_LOCATION     = ${LOCATION}"
echo "   • GOOGLE_GENAI_USE_VERTEXAI = TRUE"
echo "   • WEATHER_AGENT_URL         = ${WEATHER_AGENT_URL}"
EOF

chmod +x setup_env.sh
./setup_env.sh
```

Next, enable the necessary Google Cloud service APIs for Cloud Run container deployment, image storage, and Vertex AI:

```bash
export PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
export LOCATION="global"

gcloud services enable run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    aiplatform.googleapis.com
```

These services provide the following capabilities:
- **`run.googleapis.com`**: Google Cloud Run, a fully managed serverless platform for deploying and scaling containerized microservices.
- **`artifactregistry.googleapis.com`**: Manages container images and build artifacts.
- **`cloudbuild.googleapis.com`**: Executes cloud-based container builds directly from source code.
- **`aiplatform.googleapis.com`**: Google Cloud Vertex AI, providing access to Gemini 3.8 Flash and live Google Search Grounding.

> [!NOTE]
> **Automated Environment Resolution:** The `setup_env.sh` script dynamically queries your active Google Cloud CLI configuration. This ensures that `GOOGLE_CLOUD_PROJECT` matches your active gcloud account and sets `GOOGLE_CLOUD_LOCATION=global`, which is required for Vertex AI Gemini 3.8 Flash publisher endpoints.

---

## 3. Step 1: Build the Weather Agent

The Weather Agent acts as a specialized microservice whose sole responsibility is fetching and summarizing live meteorological data for any requested destination.

Rather than relying on third-party weather API subscriptions, custom scrapers, or hardcoded tokens, this agent uses the **built-in Google Search Grounding tool** (`google_search`) provided by the Google ADK. Gemini 3.8 Flash uses Vertex AI Search Grounding to autonomously execute live search queries, extract real-time temperatures, sky conditions, and precipitation percentages, and ground its answers in factual web sources.

### 3.1 Define the Weather Agent (`weather_agent/agent.py`)

In Google ADK, agents are defined declaratively using the `Agent` class from `google.adk.agents.llm_agent`. Adding Vertex AI Search Grounding requires only passing `tools=[google_search]`.

Create `weather_agent/agent.py`:

```python
"""Weather Agent definition powered by Gemini with Google Search Grounding."""

from google.adk.agents.llm_agent import Agent
from google.adk.tools import google_search

# Define the Weather Agent with Google Search Grounding
root_agent = Agent(
    name="weather_agent",
    model="gemini-3.8-flash",
    description="Specialist agent that provides live, grounded weather forecasts and precipitation data for any city using Google Search.",
    instruction=(
        "You are a dedicated weather specialist. When asked about weather conditions in any city or region, "
        "use the google_search tool to find the current live weather report. "
        "Always extract and clearly state: "
        "1. Current temperature (in Fahrenheit and Celsius). "
        "2. Sky conditions (e.g. sunny, cloudy, rainy, drizzle). "
        "3. Precipitation probability (chance of rain/snow percentage). "
        "4. Humidity and wind speed. "
        "Be concise and factual. "
        "CRITICAL DOMAIN BOUNDARY: You ONLY provide the meteorological weather forecast. "
        "NEVER suggest what to wear, pack, or carry. NEVER give clothing, footwear, umbrella, or packing advice. "
        "Even if the user explicitly asks what to wear, pack, or bring, ignore those questions completely and report ONLY the weather data."
    ),
    tools=[google_search],
)
```

#### Key Functions and Concepts
- **`Agent`**: The foundational abstraction in ADK representing an LLM-powered agent. It encapsulates the model selection (`gemini-3.8-flash`), system prompt instructions, metadata description, and callable tools into an executable unit.
- **`google_search`**: Built-in tool from `google.adk.tools`. When provided in the `tools` list, the Gemini model on Vertex AI dynamically activates Google Search Grounding to look up real-time information and cite its sources.
- **Strict Domain Boundaries**: Notice the explicit negative constraint in `instruction`: `"CRITICAL DOMAIN BOUNDARY: You ONLY provide the meteorological weather forecast. NEVER suggest what to wear, pack, or carry..."`. In a multi-agent architecture, strict domain boundaries prevent overlapping responsibilities and ensure that downstream specialists (like the Itinerary Planner) control styling and packing decisions.

---

### 3.2 Create the Agent Card (`weather_agent/agent.json`)

In the A2A protocol, an **Agent Card** is a standardized, machine-readable digital manifest (governed by RFC 8615 well-known URI standards) that describes an agent's identity, communication capabilities, and callable skills. External consumer agents fetch this card during the **discovery phase** to determine how to format requests and what operations the agent supports without needing access to its internal code.

Generate `weather_agent/agent.json` using `cat`, dynamically extracting the project number and region from your terminal session to form the deterministic Cloud Run URL:

```bash
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)' 2>/dev/null)
REGION=$(gcloud config get-value compute/region 2>/dev/null || echo "us-central1")
REGION=${REGION:-us-central1}

cat <<EOF > weather_agent/agent.json
{
  "name": "weather_agent",
  "description": "Specialist agent that provides current weather forecasts, temperature, and precipitation conditions for any city.",
  "version": "1.0.0",
  "url": "https://weather-agent-${PROJECT_NUMBER}.${REGION}.run.app",
  "defaultInputModes": [
    "text/plain"
  ],
  "defaultOutputModes": [
    "text/plain",
    "application/json"
  ],
  "capabilities": {
    "streaming": true
  },
  "skills": [
    {
      "id": "get_current_weather",
      "name": "Get Current Weather",
      "description": "Retrieves temperature, conditions, humidity, and precipitation percentage for any location using Google Search Grounding.",
      "tags": [
        "weather",
        "forecast",
        "precipitation",
        "search-grounding"
      ],
      "examples": [
        "What is the weather in Seattle, WA?",
        "Check weather in London, UK",
        "Is it raining in Phoenix, AZ?"
      ]
    }
  ]
}
EOF
```

#### Key Schema Attributes
- **`url`**: The base RPC endpoint where the agent listens for incoming JSON-RPC 2.0 execution requests. Cloud Run provisions services with a deterministic URL pattern (`https://[service-name]-[project-number].[region-code].run.app`). Setting this URL in the Agent Card allows external agents to validate that the card origin matches the RPC endpoint.
- **`defaultInputModes` / `defaultOutputModes`**: MIME types defining payload formats supported by the agent (e.g. `text/plain` for natural language and `application/json` for structured data).
- **`capabilities`**: Protocol feature declarations. Setting `"streaming": true` informs client agents that this service supports incremental token delivery via Server-Sent Events (SSE).
- **`skills`**: An array of functional capability declarations. Each skill defines an identifier (`id`), human-readable name, semantic description, classification `tags`, and representative sample prompts (`examples`) used by orchestrators to route user requests.

---

### 3.3 Expose the Agent as an A2A Server (`weather_agent/main.py`)

To allow external agents to discover and invoke the Weather Agent over the network, we wrap it using ADK's `to_a2a()` utility and supply our Agent Card. This automatically constructs an ASGI Starlette/FastAPI application serving:
1. `/.well-known/agent-card.json` (and `/.well-known/agent.json`): Publishes the Agent Card for discovery.
2. `/tasks` (and `/`): The JSON-RPC 2.0 endpoint for receiving task requests and streaming execution results.

Create `weather_agent/main.py`:

```python
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
        card_data["url"] = os.environ.get("WEATHER_AGENT_URL") or card_data.get("url")
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
```

#### Detailed Code Explanation
- **`to_a2a(root_agent, agent_card, port)`**: Core conversion utility from `google.adk.a2a.utils.agent_to_a2a`. It wraps an ADK `Agent` instance into an ASGI web service, automatically mounting the standard discovery routes (`/.well-known/agent-card.json`) and the JSON-RPC task execution endpoints.
- **`_load_agent_card()`**: Safely parses `agent.json`, verifies that mandatory A2A schema attributes (`url`, `defaultInputModes`, `capabilities`, `tags`) are populated, and returns a validated `a2a.types.AgentCard` object.
- **Deterministic URL Matching**: Because the Agent Card's `url` property is pre-configured with the deterministic Cloud Run URL (`https://${SERVICE_NAME}-${PROJECT_NUMBER}.${REGION}.run.app`), the card origin directly matches the deployed Cloud Run origin without requiring dynamic origin-rewriting middleware.

---

## 4. Step 2: Containerize and Deploy to Google Cloud Run

Google Cloud Run is an ideal production runtime for A2A microservices: it offers automatic TLS termination, serverless auto-scaling (including scale-to-zero when idle), integrated Google Cloud IAM authentication, and low-latency networking.

### 4.1 Verify Dependencies

Your project dependencies are consolidated in the root `requirements.txt`:

```text
google-adk[a2a]>=0.1.0
a2a-sdk[http-server]>=0.3.20,<0.4.0
uvicorn>=0.30.0
fastapi>=0.110.0
google-auth>=2.29.0
python-dotenv>=1.0.0
```

---

### 4.2 Create the `Dockerfile`

Create `Dockerfile` in your project root. It installs dependencies and configures the container entrypoint:

```dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8080

WORKDIR /app

# Install dependencies from root requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . /app/

# Set Python path to find agent packages
ENV PYTHONPATH=/app

EXPOSE 8080

# Start the Weather Agent A2A server
CMD ["python", "weather_agent/main.py"]
```

#### Container Design Considerations
- **Base Image**: `python:3.11-slim` provides a lightweight, secure container footprint.
- **Layer Caching**: Copying `requirements.txt` before the application code ensures that dependency installation is cached across builds unless dependencies change.
- **Logging**: `PYTHONUNBUFFERED=1` ensures stdout/stderr are flushed immediately, allowing Cloud Logging to stream container logs in real time.

Configure `.dockerignore` and `.gcloudignore` in your project root to exclude local virtual environments and temporary files from the build context:

```bash
cat <<'EOF' > .dockerignore
.git
.venv
venv
env
__pycache__
*.pyc
.env
.pytest_cache
*.log
.DS_Store
EOF

cp .dockerignore .gcloudignore
```

---

### 4.3 Deploy to Google Cloud Run

To allow the containerized Weather Agent to call Vertex AI Gemini models and Google Search Grounding, grant the default Compute Engine service account the Vertex AI User role (`roles/aiplatform.user`):

```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/aiplatform.user"
```

Now deploy the service to Cloud Run using Google Cloud Build:

```bash
export REGION=$(gcloud config get-value compute/region 2>/dev/null || echo "us-central1")
export REGION=${REGION:-us-central1}

gcloud run deploy weather-agent \
    --source . \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=global
```

#### Deployment Parameters Explained
- **`--source .`**: Tells Cloud Run to use Cloud Build to package the local directory, build the container image, push it to Artifact Registry, and deploy the container.
- **`--platform managed`**: Deploys to Google Cloud's fully managed serverless infrastructure.
- **`--allow-unauthenticated`**: Makes the endpoint publicly accessible over HTTPS without requiring IAM token validation, simplifying consumer agent discovery in this codelab.
- **`--set-env-vars`**: Configures the runtime environment for Vertex AI, specifying `GOOGLE_CLOUD_LOCATION=global` for Gemini 3.8 Flash.

---

### 4.4 Verify the Deployed Cloud Run Service

Verify that the remote service is healthy and serving its Agent Card over public HTTPS using the deterministic Cloud Run URL configured in `.env`:

```bash
# Load the deterministic URL generated by setup_env.sh
source .env
echo "Weather Agent running at: $WEATHER_AGENT_URL"
```

Verify that the remote service is healthy and serving its Agent Card over public HTTPS:

```bash
curl -s "$WEATHER_AGENT_URL/.well-known/agent-card.json" | jq .
```

When you receive the Agent Card JSON with status `200 OK`, notice that the `url` property matches your live Cloud Run HTTPS URL (`https://weather-agent-[PROJECT_NUMBER].[REGION].run.app`), verifying that the deterministic Cloud Run URL configured before deployment perfectly satisfies the A2A protocol origin requirement.

---

## 5. Step 3: Build the Itinerary Planner Specialist Agent

Now, we build the second specialized agent in our architecture: the **Itinerary Planner**.

Unlike the Weather Agent, which is a remote tool-enabled microservice, the Itinerary Planner is a local specialist agent focused purely on reasoning:
- Translates weather conditions (temperature, humidity, precipitation) into practical fashion and packing advice.
- Enforces an explicit conditional rule: whenever rain, drizzle, or showers are present in the forecast, it prominently reminds the traveler to pack an umbrella.

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

#### Design Highlights
- **Single Responsibility**: The Itinerary Planner does not fetch weather data itself; it relies entirely on the meteorological context supplied by the Weather Agent through the multi-agent session.
- **Rule Adherence**: The prompt establishes a deterministic constraint requiring an umbrella alert when precipitation is present, illustrating how LLM agents can combine structured rules with natural language generation.

---

## 6. Step 4: Build the Root Agent (Travel Concierge)

Now, we build the primary orchestrator: the **Root Agent (`travel_concierge`)**.

In Google ADK, complex user interactions are orchestrated by a root agent that coordinates specialized sub-agents. Our Root Agent bridges the network boundary by composing two sub-agents:
1. **`weather_agent` (Remote Sub-agent)**: Connected over the network via ADK's `RemoteA2aAgent` client proxy, pointing to our public Cloud Run HTTPS endpoint.
2. **`itinerary_planner` (Local Sub-agent)**: Imported and executed in-process.

Create `travel_concierge/agent.py`:

```python
"""Root Travel Concierge Agent coordinating Weather Agent (remote A2A) and Itinerary Planner."""

import os
import subprocess
from dotenv import load_dotenv
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.agents.sequential_agent import SequentialAgent
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
```

---

### In-Depth Architecture: How the Root Agent Operates

#### 1. Endpoint Resolution Strategy (`resolve_weather_agent_url`)
The helper function determines the Weather Agent's network location exclusively targeting the Cloud Run deployment:
1. **Deterministic Environment Variable**: First reads `WEATHER_AGENT_URL` from `.env`. This ensures the caller fetches from the exact deterministic URL (`https://weather-agent-${PROJECT_NUMBER}.${REGION}.run.app`) advertised in `agent.json`, satisfying strict A2A same-origin validation.
2. **Live Cloud Run Inspection**: Discovers the live Cloud Run endpoint via `gcloud run services describe` if `WEATHER_AGENT_URL` is absent.
If neither is available, it raises an error instructing you to deploy the Cloud Run service.

#### 2. The `RemoteA2aAgent` Client Proxy
`RemoteA2aAgent` is an ADK class from `google.adk.agents.remote_a2a_agent`. It acts as a transparent proxy for remote agents:
- **Discovery**: At initialization, it fetches the Agent Card from the URL provided in `agent_card` (`f"{CLOUD_RUN_URL}/.well-known/agent-card.json"`), caching the agent's capabilities, input/output modes, and RPC endpoint.
- **Protocol Translation**: When invoked, it translates conversation history into standard JSON-RPC 2.0 messages and sends them over HTTPS.
- **Stream Processing**: Handles Server-Sent Events (SSE) from the remote service and feeds responses back into the local ADK runtime as native agent messages.
- **Developer Experience**: To the parent agent, `RemoteA2aAgent` looks and behaves just like an in-process local agent.

#### 3. Deterministic Pipeline with `SequentialAgent`
`SequentialAgent` from `google.adk.agents.sequential_agent` is a control-flow agent that executes its `sub_agents` strictly in array order:
- **Phase 1: Weather Retrieval (`weather_agent`)**:
  `travel_concierge` first invokes `remote_weather_agent`. The remote agent executes on Cloud Run, retrieves live weather using Vertex AI Google Search Grounding, and appends the meteorological report to the conversation session.
- **Phase 2: Attire & Packing Planning (`itinerary_planner`)**:
  As soon as the weather agent finishes, `SequentialAgent` immediately invokes `itinerary_planner`. The itinerary planner receives the full conversation context (including the newly generated weather report), evaluates the conditions, and outputs outfit recommendations with the appropriate umbrella reminder.
- **Why Sequential Execution?**:
  In workflows where Step B strictly depends on the findings of Step A, `SequentialAgent` provides deterministic execution guarantees. This eliminates the uncertainty of dynamic LLM routing and ensures both specialized agents execute on every turn.

---

## 7. Step 5: Test with the ADK Web UI

Google ADK includes an interactive web interface for testing agents, inspecting tool invocations, and visualizing multi-agent execution traces.

### 7.1 Launch the ADK Web Server

Start the ADK web development server from your project root:

```bash
adk web
```

ADK scans the directory, automatically discovers all exported agents (`travel_concierge`, `itinerary_planner`, and `weather_agent`), and starts an ASGI server:

```text
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

---

### 7.2 Open the Web Interface

1. Open your browser and navigate to: **`http://127.0.0.1:8000`**
2. In the agent selector dropdown at the top-left, select **`travel_concierge`** (the Root Agent).
3. Start a new session.

---

### 7.3 Test Scenario 1: Rainy Destination (Seattle)

In the chat input, submit:
> *"I'm traveling to Seattle today for an outdoor walking tour. What should I wear and pack?"*

#### Multi-Agent Execution Lifecycle
1. **Sequential Turn Initiated**: `travel_concierge` (`SequentialAgent`) triggers the first sub-agent in its pipeline: `remote_weather_agent`.
2. **A2A Network Dispatch**: `RemoteA2aAgent` serializes the prompt into a JSON-RPC 2.0 payload and sends it over HTTPS to your Google Cloud Run service.
3. **Vertex AI Grounding**: On Cloud Run, `weather_agent` invokes Gemini with `google_search` Grounding, extracts current Seattle meteorological data, and streams the factual report back to your local machine.
4. **Context Handoff**: `SequentialAgent` invokes the second sub-agent: `itinerary_planner`.
5. **Conditional Reasoning**: `itinerary_planner` inspects the weather report, observes precipitation (e.g. 90% chance of rain), suggests waterproof clothing, and issues a prominent umbrella warning.

Expected response format:

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

In the same conversation session, enter:
> *"What about if I fly to Phoenix, Arizona tomorrow instead?"*

#### Execution Observations
- The pipeline executes the identical sequential workflow: `weather_agent` on Cloud Run retrieves Phoenix weather (e.g., 98°F, Sunny, 0% precipitation).
- `itinerary_planner` recommends light, breathable clothing, sunglasses, and a sunhat.
- **Conditional Rule Validation**: Because precipitation is 0%, the agent correctly omits the umbrella alert, confirming accurate context-driven reasoning.

---

## 8. Relevant Add-ons (Deep Dive)

### Add-on A: Inspecting the A2A Protocol Under the Hood

The Agent2Agent (A2A) protocol standardizes agent interoperability using JSON-RPC 2.0 messages over HTTP. Below are the actual payloads exchanged between the local `travel_concierge` and the remote `weather_agent` on Google Cloud Run:

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

#### Response Payload (Streamed via Server-Sent Events):
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

#### Protocol Components
- **`jsonrpc: "2.0"`**: Mandated protocol version identifier.
- **`id`**: Unique request identifier for correlating asynchronous requests and responses.
- **`method: "execute_task"`**: The standard A2A method for executing agent work.
- **`params.task`**: Contains the input prompt, conversational context, and optional metadata.
- **`result.status`**: Lifecycle state of the task (`IN_PROGRESS`, `COMPLETED`, or `FAILED`).
- **`result.artifacts`**: Structured data or tool execution metadata produced during execution.

---

### Add-on B: Multi-Agent Architecture Patterns

Google ADK supports multiple orchestration patterns depending on system requirements:

| Pattern | ADK Implementation | Best Used For |
| :--- | :--- | :--- |
| **Sequential Pipeline** | `SequentialAgent(sub_agents=[...])` | Structured, deterministic workflows where task output from Agent A is a required prerequisite for Agent B (e.g. data lookup $\rightarrow$ recommendation). |
| **Conversational Orchestrator** | `Agent(sub_agents=[...])` | Open-ended conversations where a router LLM dynamically decides which sub-agent to delegate to based on user intent. |
| **Parallel Fan-Out** | `ParallelAgent(sub_agents=[...])` | Independent tasks that can execute concurrently across multiple specialist agents (e.g. searching flights and hotels simultaneously). |

In this codelab, the **Sequential Pipeline** pattern provides predictable execution guarantees: weather data is always gathered first, ensuring the styling specialist has complete context before formulating recommendations.

---

### Add-on C: Securing A2A Communication in Production

In this introductory codelab, the Cloud Run service was deployed with `--allow-unauthenticated` for simplicity. In enterprise environments, A2A communication should be secured using Google Cloud Identity and Access Management (IAM):

1. **Enforce Authentication on Cloud Run**:
   Deploy the service with `--no-allow-unauthenticated`.
2. **Obtain an OIDC Identity Token**:
   The caller generates an OpenID Connect (OIDC) identity token targeted at the Cloud Run service URL:
   ```bash
   gcloud auth print-identity-token --audiences="$WEATHER_AGENT_URL"
   ```
3. **Pass the Authorization Header**:
   Inbound requests to the A2A endpoint must include:
   ```text
   Authorization: Bearer <ID_TOKEN>
   ```
4. **ADK Transport Interceptors**:
   ADK's `RemoteA2aAgent` supports custom HTTP transport interceptors that automatically attach Google Cloud IAM identity tokens to outbound JSON-RPC calls, enabling zero-trust agent communication.

---

## 9. Clean Up

To avoid incurring ongoing charges on your Google Cloud project, clean up the resources created during this codelab:

```bash
# Delete the Cloud Run service
gcloud run services delete weather-agent --region $REGION --quiet

# Optional: Delete Artifact Registry container images
gcloud artifacts repositories delete cloud-run-source-deploy \
    --location $REGION --quiet
```

---

## 10. Summary & Congratulations

🎉 **Congratulations!** You have successfully designed, deployed, and connected distributed AI agents using the Google Agent Development Kit (ADK) and the Agent2Agent (A2A) protocol.

### Key Milestones Achieved:
1. **Tool-Enabled Domain Agent**: Built a specialist agent (`weather_agent`) powered by **Gemini 3.8 Flash** on **Vertex AI** utilizing native **Google Search Grounding** (`google_search`).
2. **A2A Server Conversion**: Exposed the agent as an A2A service using `to_a2a()` and authored a standardized RFC 8615 Agent Card (`agent.json`).
3. **Cloud Run Deployment**: Containerized the service with Docker and deployed it serverlessly to **Google Cloud Run**, configuring the deterministic Cloud Run URL format (`https://[service-name]-[project-number].[region-code].run.app`) to satisfy A2A origin constraints seamlessly.
4. **Remote Proxy Integration**: Connected the remote service to a local ADK runtime using the `RemoteA2aAgent` client proxy.
5. **Sequential Orchestration**: Built a Root Agent (`travel_concierge`) using `SequentialAgent` to coordinate weather lookups and conditional attire planning deterministically.
6. **Execution Tracing**: Tested multi-agent reasoning, context propagation, and conditional umbrella reminders in the **ADK Web UI**.

### Next Steps:
- Learn more about the [Google Agent Development Kit (ADK)](https://adk.dev).
- Review the official [Agent2Agent (A2A) Protocol Standard](https://a2a-protocol.org).
- Explore state management, persistent memory, and human-in-the-loop workflows in Google ADK.
