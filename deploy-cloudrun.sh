#!/usr/bin/env bash
# ==============================================================================
# Smart Health Sentinel — Automated Cloud Run Deployment Script
# ==============================================================================
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-sentinel-backend}"
REGION="${REGION:-us-central1}"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo '')}"

echo "========================================================================"
echo " Smart Health Sentinel: Deploying to Google Cloud Run"
echo "========================================================================"

if [ -z "${PROJECT_ID}" ]; then
  echo "ERROR: Google Cloud project not detected."
  echo "Please authenticate and select a project:"
  echo "  gcloud auth login"
  echo "  gcloud config set project <YOUR_GCP_PROJECT_ID>"
  exit 1
fi

echo "Project:  ${PROJECT_ID}"
echo "Service:  ${SERVICE_NAME}"
echo "Region:   ${REGION}"
echo ""

# 1. Enable required Google Cloud APIs
echo "--> Enabling required GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  --project="${PROJECT_ID}"

# 2. Build Container Image via Cloud Build
IMAGE_TAG="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:$(git rev-parse --short HEAD 2>/dev/null || echo 'latest')"
echo "--> Building container image: ${IMAGE_TAG}"
gcloud builds submit --tag "${IMAGE_TAG}" .

# 3. Deploy to Cloud Run with Secret Manager Bindings & Health Probe
echo "--> Deploying service to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image="${IMAGE_TAG}" \
  --region="${REGION}" \
  --platform=managed \
  --allow-unauthenticated \
  --port=8080 \
  --set-env-vars="DEBUG=false,APP_NAME=Healthcare Supply Chain API,APP_VERSION=0.1.0,PLANNING_HORIZON_DAYS=30,SAFETY_RESERVE_DAYS=7,CORS_ORIGINS=https://smart-health-gray-theta.vercel.app,https://smarthealth-production.up.railway.app" \
  --set-secrets="DATABASE_URL=sentinel-database-url:latest,JWT_SECRET_KEY=sentinel-jwt-secret-key:latest" \
  --project="${PROJECT_ID}"

# 4. Extract Service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --platform=managed --region="${REGION}" --format='value(status.url)' --project="${PROJECT_ID}")

echo ""
echo "========================================================================"
echo " Cloud Run Deployment Succeeded!"
echo " Service URL: ${SERVICE_URL}"
echo "========================================================================"

# 5. Verification Smoke Tests
echo "--> Verifying /api/v1/health probe..."
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${SERVICE_URL}/api/v1/health" || echo "failed")
if [ "${HEALTH_STATUS}" = "200" ]; then
  echo "✓ Health check passed (HTTP 200)"
else
  echo "⚠ Warning: Health check returned HTTP ${HEALTH_STATUS}"
fi

echo "--> Deployment complete."
