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
└── .env
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
pip install --upgrade "google-adk[a2a]" uvicorn fastapi
```

---

### 2.4 Configure Environment Variables & Vertex AI

Authenticate your local environment with Google Cloud Application Default Credentials (ADC):

```bash
gcloud auth application-default login
```

Configure your Google Cloud project and region:

```bash
export PROJECT_ID=$(gcloud config get-value project)
export REGION="us-central1"

# Enable required Google Cloud services including Vertex AI
gcloud services enable run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    aiplatform.googleapis.com
```

Create a root `.env` file configured to use **Vertex AI**:

```bash
cat <<EOF > .env
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=${PROJECT_ID}
GOOGLE_CLOUD_LOCATION=${REGION}
EOF
```

> **Vertex AI Advantage:** Using Vertex AI allows your agents to authenticate via Google Cloud IAM and Application Default Credentials (ADC) without requiring static API keys.

---

## 3. Step 1: Build the Weather Agent

The Weather Agent is a domain-specific agent whose responsibility is fetching and summarizing weather forecasts for any requested location.

### 3.1 Define the Weather Tool and Agent (`weather_agent/agent.py`)

In ADK, tools are native Python functions with type annotations and informative docstrings. Gemini uses the docstrings to determine when and how to call the tool.

Create `weather_agent/agent.py`:

```python
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

Once the deployment completes, `gcloud` will output the Service URL:

```bash
export WEATHER_AGENT_URL=$(gcloud run services describe weather-agent \
    --region $REGION \
    --format 'value(status.url)')

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

Create `travel_concierge/agent.py`:

```python
"""Root Travel Concierge Agent coordinating Weather Agent (remote A2A) and Itinerary Planner."""

import os
from google.adk.agents.llm_agent import Agent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from itinerary_planner.agent import itinerary_planner

# Retrieve remote Cloud Run A2A URL from environment variable or fallback to localhost
CLOUD_RUN_URL = os.environ.get("WEATHER_AGENT_URL", "http://localhost:8080")

# 1. Instantiate the Remote A2A Weather Agent Proxy
# The proxy discovers capabilities by fetching /.well-known/agent-card.json from Cloud Run
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

Export your `WEATHER_AGENT_URL` and run `adk web` from your project root:

```bash
export WEATHER_AGENT_URL=$(gcloud run services describe weather-agent \
    --region $REGION \
    --format 'value(status.url)')

# Launch the developer UI
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
