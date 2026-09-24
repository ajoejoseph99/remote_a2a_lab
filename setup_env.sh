#!/usr/bin/env bash
set -e

# Automatically query active Google Cloud project from gcloud
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

if [ -n "$PROJECT_NUMBER" ] && [ -n "$REGION" ]; then
  WEATHER_AGENT_URL="https://${SERVICE_NAME}-${PROJECT_NUMBER}.${REGION}.run.app"
else
  WEATHER_AGENT_URL="http://localhost:8080"
fi

# Set Vertex AI Model Location to global (required for Gemini 3.8 Flash)
LOCATION="global"

cat <<EOF > .env
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=${PROJECT_ID}
GOOGLE_CLOUD_LOCATION=${LOCATION}
WEATHER_AGENT_URL=${WEATHER_AGENT_URL}
EOF

# Update weather_agent/agent.json with the deterministic Cloud Run URL
if [ -f "weather_agent/agent.json" ]; then
  python3 -c "
import json
with open('weather_agent/agent.json', 'r') as f:
    data = json.load(f)
data['url'] = '${WEATHER_AGENT_URL}'
with open('weather_agent/agent.json', 'w') as f:
    json.dump(data, f, indent=2)
"
fi

echo "✅ Successfully configured environment:"
echo "   • GOOGLE_CLOUD_PROJECT      = ${PROJECT_ID}"
echo "   • GOOGLE_CLOUD_LOCATION     = ${LOCATION}"
echo "   • GOOGLE_GENAI_USE_VERTEXAI = TRUE"
echo "   • WEATHER_AGENT_URL         = ${WEATHER_AGENT_URL}"
