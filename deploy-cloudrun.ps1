# ==============================================================================
# Smart Health Sentinel — Automated Cloud Run Deployment Script (PowerShell)
# ==============================================================================

$ErrorActionPreference = "Stop"

$ServiceName = if ($env:SERVICE_NAME) { $env:SERVICE_NAME } else { "sentinel-backend" }
$Region = if ($env:REGION) { $env:REGION } else { "us-central1" }
$ProjectId = if ($env:PROJECT_ID) { $env:PROJECT_ID } else { (gcloud config get-value project 2>$null) }

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host " Smart Health Sentinel: Deploying to Google Cloud Run" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan

if (-not $ProjectId) {
    Write-Host "ERROR: Google Cloud project not detected." -ForegroundColor Red
    Write-Host "Please authenticate and configure your project:" -ForegroundColor Yellow
    Write-Host "  gcloud auth login" -ForegroundColor Yellow
    Write-Host "  gcloud config set project <YOUR_GCP_PROJECT_ID>" -ForegroundColor Yellow
    exit 1
}

Write-Host "Project:  $ProjectId"
Write-Host "Service:  $ServiceName"
Write-Host "Region:   $Region"
Write-Host ""

# 1. Enable required APIs
Write-Host "--> Enabling required GCP APIs..." -ForegroundColor Green
gcloud services enable `
    run.googleapis.com `
    cloudbuild.googleapis.com `
    secretmanager.googleapis.com `
    artifactregistry.googleapis.com `
    --project=$ProjectId

# 2. Build Container Image via Cloud Build
$GitHash = git rev-parse --short HEAD 2>$null
if (-not $GitHash) { $GitHash = "latest" }
$ImageTag = "gcr.io/$ProjectId/${ServiceName}:$GitHash"

Write-Host "--> Building container image: $ImageTag" -ForegroundColor Green
gcloud builds submit --tag $ImageTag .

# 3. Deploy to Cloud Run
Write-Host "--> Deploying service to Cloud Run..." -ForegroundColor Green
gcloud run deploy $ServiceName `
    --image=$ImageTag `
    --region=$Region `
    --platform=managed `
    --allow-unauthenticated `
    --port=8080 `
    --set-env-vars="DEBUG=false,APP_NAME=Healthcare Supply Chain API,APP_VERSION=0.1.0,PLANNING_HORIZON_DAYS=30,SAFETY_RESERVE_DAYS=7,CORS_ORIGINS=https://smart-health-gray-theta.vercel.app,https://smarthealth-production.up.railway.app" `
    --set-secrets="DATABASE_URL=sentinel-database-url:latest,JWT_SECRET_KEY=sentinel-jwt-secret-key:latest" `
    --project=$ProjectId

# 4. Service URL and Verification
$ServiceUrl = gcloud run services describe $ServiceName --platform=managed --region=$Region --format='value(status.url)' --project=$ProjectId

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host " Cloud Run Deployment Succeeded!" -ForegroundColor Cyan
Write-Host " Service URL: $ServiceUrl" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Cyan

Write-Host "--> Verifying /api/v1/health probe..." -ForegroundColor Green
try {
    $response = Invoke-RestMethod -Uri "$ServiceUrl/api/v1/health" -Method Get
    Write-Host "✓ Health check passed: status=$($response.status)" -ForegroundColor Green
} catch {
    Write-Host "⚠ Warning: Health check query failed: $_" -ForegroundColor Yellow
}
