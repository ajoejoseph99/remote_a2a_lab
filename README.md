# Connect to Remote Agents with Google ADK and the Agent2Agent (A2A) SDK

This repository contains the complete code implementation and step-by-step tutorial for the Google Cloud Codelab: **"Connect to Remote Agents with ADK and the Agent2Agent (A2A) SDK"**.

## 📖 Codelab Guide
The full, step-by-step walkthrough is available in [codelab.md](file:///Users/ajoejoseph/Desktop/a2a%20lab/codelab.md).

---

## 🏗️ Architecture
- **`weather_agent`**: Specialist remote ADK agent powered by **Gemini 3.8 Flash** via **Vertex AI** with weather retrieval tools, exposed as an A2A service via `to_a2a()`, and deployed to Google Cloud Run (`--allow-unauthenticated`).
- **`itinerary_planner`**: Specialist local ADK agent (Gemini 3.8 Flash) that suggests clothing and reminds the user to bring an umbrella if rain is forecast.
- **`travel_concierge` (Root Agent)**: The primary orchestrator agent that coordinates between `weather_agent` (via `RemoteA2aAgent`) and `itinerary_planner`.
- **ADK Web UI**: Interactive chat interface to talk directly to `travel_concierge` and visualize multi-agent collaboration and reasoning traces.

---

## 🚀 Quickstart

### 1. Setup Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Authenticate with Google Cloud Vertex AI
gcloud auth application-default login

export PROJECT_ID=$(gcloud config get-value project)
export REGION="us-central1"

# Enable required APIs
gcloud services enable run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    aiplatform.googleapis.com

cp .env.example .env
# Edit .env with your GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION
```

### 2. Deploy Weather Agent to Google Cloud Run (Public/Unauthenticated)
```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/aiplatform.user"

gcloud run deploy weather-agent \
    --source . \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION
```

### 3. Start ADK Web UI
```bash
export WEATHER_AGENT_URL=$(gcloud run services describe weather-agent --region $REGION --format 'value(status.url)')
adk web
```
Navigate to `http://127.0.0.1:8000`, select **`travel_concierge`**, and test:
> *"I'm traveling to Seattle today for an outdoor walking tour. What should I wear?"*
