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

# Automatically query or default compute region
REGION=$(gcloud config get-value compute/region 2>/dev/null)
REGION=${REGION:-us-central1}

# Generate .env automatically with zero manual copy-pasting
cat <<EOF > .env
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=${PROJECT_ID}
GOOGLE_CLOUD_LOCATION=${REGION}
EOF

echo "✅ Successfully configured .env automatically from terminal:"
echo "   • GOOGLE_CLOUD_PROJECT      = ${PROJECT_ID}"
echo "   • GOOGLE_CLOUD_LOCATION     = ${REGION}"
echo "   • GOOGLE_GENAI_USE_VERTEXAI = TRUE"
