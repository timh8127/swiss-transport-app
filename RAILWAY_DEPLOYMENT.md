# Railway Deployment Guide

## Prerequisites
- GitHub account with repository created
- Railway account (https://railway.app/)
- Swiss OTD API keys (https://api-manager.opentransportdata.swiss/)
  - You may need separate API keys for each service (OJP, GTFS-RT, SIRI-SX, DATEX II, OCIT-C)

## Step 1: Create GitHub Repository

```bash
# In the swiss-transport-app directory
git init
git add .
git commit -m "Initial commit: Swiss Transport Planner"

# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/swiss-transport-app.git
git branch -M main
git push -u origin main
```

## Step 2: Deploy Backend on Railway

1. Go to https://railway.app/new
2. Select "Deploy from GitHub repo"
3. Connect your GitHub account and select the repository
4. Configure the service:
   - **Root Directory**: `backend`
   - **Builder**: Dockerfile (auto-detected)

5. Add Environment Variables:
   - `OTD_OJP_API_KEY`: API key for OJP (route planning)
   - `OTD_GTFSRT_API_KEY`: API key for GTFS-RT (delay data)
   - `OTD_SIRI_SX_API_KEY`: API key for SIRI-SX (disruptions)
   - `OTD_TRAFFIC_SITUATIONS_API_KEY`: API key for DATEX II (traffic situations)
   - `OTD_TRAFFIC_LIGHTS_API_KEY`: API key for OCIT-C (traffic lights)
   - `CORS_ORIGINS`: `*` (or your frontend URL after deployment)
   - `TIMEZONE`: `Europe/Zurich` (default)

6. Railway will automatically deploy. Note the public URL (e.g., `https://swiss-transport-backend-production.up.railway.app`)

## Step 3: Deploy Frontend on Railway

1. In the same Railway project, click "New Service"
2. Select "GitHub Repo" again
3. Configure the service:
   - **Root Directory**: `frontend`
   - **Builder**: Dockerfile (auto-detected)

4. Add Build Arguments (in Settings > Build):
   - `VITE_API_URL`: Your backend URL from Step 2

5. Add Environment Variables:
   - `BACKEND_URL`: Your backend URL (for nginx proxy)

6. Railway will deploy. Note the public URL.

## Step 4: Update CORS (Optional)

If you want to restrict CORS:
1. Go to backend service settings
2. Update `CORS_ORIGINS` to include your frontend URL

## Alternative: Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Create project
railway init

# Link to backend directory and deploy
cd backend
railway up

# Link to frontend directory and deploy
cd ../frontend
railway up
```

## Environment Variables Summary

### Backend
| Variable | Description | Required |
|----------|-------------|----------|
| `OTD_OJP_API_KEY` | API key for OJP route planning | Yes |
| `OTD_GTFSRT_API_KEY` | API key for GTFS-RT delay data | Yes |
| `OTD_SIRI_SX_API_KEY` | API key for SIRI-SX disruptions | Yes |
| `OTD_TRAFFIC_SITUATIONS_API_KEY` | API key for DATEX II traffic | Optional |
| `OTD_TRAFFIC_LIGHTS_API_KEY` | API key for OCIT-C traffic lights | Optional |
| `CORS_ORIGINS` | Allowed origins (comma-separated) | No (default: `*`) |
| `TIMEZONE` | Server timezone | No (default: `Europe/Zurich`) |
| `DEBUG` | Enable debug mode | No (default: `false`) |

### Frontend
| Variable | Description | Required |
|----------|-------------|----------|
| `VITE_API_URL` | Backend API URL (build-time) | Yes |
| `BACKEND_URL` | Backend URL for nginx proxy | Yes |

## Health Checks

- Backend: `GET /health`
- Frontend: Nginx serves static files

## Troubleshooting

### Backend not starting
- Check `OTD_OJP_API_KEY` is set (minimum required)
- View logs in Railway dashboard
- Verify PORT is being used correctly (Railway sets it automatically)

### Frontend can't reach backend
- Verify `VITE_API_URL` was set during build
- Check CORS settings on backend
- Ensure backend is running and healthy

### API errors
- Verify your OTD API keys are valid
- Check API rate limits (GTFS-RT: 2 requests/min)
- Check `/health` endpoint for data availability status

### "Live data unavailable" warnings
- Some features work with reduced functionality when API keys are missing
- Traffic prediction requires `OTD_TRAFFIC_SITUATIONS_API_KEY` and `OTD_TRAFFIC_LIGHTS_API_KEY`
- Disruptions require `OTD_SIRI_SX_API_KEY`
