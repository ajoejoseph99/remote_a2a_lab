# Connect to Remote Agents with Google ADK and the Agent2Agent (A2A) SDK

This repository contains the complete code implementation and step-by-step tutorial for the Google Cloud Codelab: **"Connect to Remote Agents with ADK and the Agent2Agent (A2A) SDK"**.

## 📖 Codelab Guide
The full, step-by-step walkthrough is available in [codelab.md](file:///Users/ajoejoseph/Desktop/a2a%20lab/codelab.md).

> [!NOTE]
> **Starter Codelab Branch (`codelab`)**: This branch is the interactive starter template for following the [codelab guide](file:///Users/ajoejoseph/Desktop/a2a%20lab/codelab.md). You will populate the empty agent files and execute setup commands in Cloud Shell as you progress through each step.
> For the complete pre-built reference solution, see the [`main`](https://github.com/ajoejoseph99/remote_a2a_lab/tree/main) branch.

---

## 🏗️ Architecture
- **`weather_agent`**: Specialist remote ADK agent powered by **Gemini 3.8 Flash** via **Vertex AI** with live Google Search Grounding (`google_search`), exposed as an A2A service via `to_a2a()`, and deployed to Google Cloud Run (`--allow-unauthenticated`).
- **`itinerary_planner`**: Specialist local ADK agent (Gemini 3.8 Flash) that suggests clothing and reminds the user to bring an umbrella if rain is forecast.
- **`travel_concierge` (Root Agent)**: The primary orchestrator agent that coordinates between `weather_agent` (via `RemoteA2aAgent`) and `itinerary_planner`.
- **ADK Web UI**: Interactive chat interface to talk directly to `travel_concierge` and visualize multi-agent collaboration and reasoning traces.

---

## 🚀 Quickstart (Zero Copy-Paste Setup)

### 1. Setup Environment
All project and region configs are pulled directly from your terminal (`gcloud config`):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Authenticate with Google Cloud Vertex AI
gcloud auth application-default login

# Automatically configure .env directly from your terminal session
./setup_env.sh

# Enable required Google Cloud services
export PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
export LOCATION="global"

gcloud services enable run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    aiplatform.googleapis.com
```

### 2. Deploy Weather Agent to Google Cloud Run (Public/Unauthenticated)
```bash
# Automatically bind Vertex AI permissions to the compute service account
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/aiplatform.user"

# Deploy to Cloud Run using terminal variables directly
export REGION=$(gcloud config get-value compute/region 2>/dev/null || echo "us-central1")
export REGION=${REGION:-us-central1}

gcloud run deploy weather-agent \
    --source . \
    --region "$REGION" \
    --allow-unauthenticated \
    --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT="$PROJECT_ID",GOOGLE_CLOUD_LOCATION=global

# Verify the deployed service serves its Agent Card over public HTTPS
source .env
curl -s "$WEATHER_AGENT_URL/.well-known/agent-card.json" | jq .
```

### 3. Start ADK Web UI
The Root Agent (`travel_concierge`) automatically discovers the deployed Cloud Run service URL and project configuration directly from the terminal/environment:

```bash
adk web
```
Navigate to `http://127.0.0.1:8000`, select **`travel_concierge`**, and test:
> *"I'm traveling to Seattle today for an outdoor walking tour. What should I wear and pack?"*
