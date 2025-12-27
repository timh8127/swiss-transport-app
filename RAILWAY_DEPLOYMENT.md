# Railway Deployment Guide

## Prerequisites
- GitHub account with repository created
- Railway account (https://railway.app/)
- Swiss OTD API key (https://api-manager.opentransportdata.swiss/)

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
   - `OTD_API_KEY`: Your Swiss OTD API key
   - `CORS_ORIGINS`: `*` (or your frontend URL after deployment)

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
| `OTD_API_KEY` | Swiss OTD API key | Yes |
| `CORS_ORIGINS` | Allowed origins (comma-separated) | No (default: `*`) |
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
- Check `OTD_API_KEY` is set
- View logs in Railway dashboard

### Frontend can't reach backend
- Verify `VITE_API_URL` was set during build
- Check CORS settings on backend
- Ensure backend is running and healthy

### API errors
- Verify your OTD API key is valid
- Check API rate limits (GTFS-RT: 2 requests/min)
