# Siloq App - Digital Ocean Deployment Guide

## 📋 Table of Contents
1. [Understanding run.py](#understanding-runpy)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Step-by-Step Deployment](#step-by-step-deployment)
4. [Environment Variables Setup](#environment-variables-setup)
5. [Database Setup](#database-setup)
6. [Post-Deployment](#post-deployment)
7. [Troubleshooting](#troubleshooting)

---

## 🚀 Understanding run.py

Your `run.py` file is the entry point for your FastAPI application. It typically does one of these:

### Common Pattern 1: Uvicorn Server
```python
import uvicorn
from app.main import app

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=False  # Don't use reload in production
    )
```

### Common Pattern 2: Simple Import
```python
from app.main import app

# The app is already configured in app/main.py
# run.py just makes it executable
```

### How Digital Ocean Runs It:
Digital Ocean will execute: `python run.py`

This starts your FastAPI server and makes it available on the specified port (8080).

---

## ✅ Pre-Deployment Checklist

Before deploying to Digital Ocean, ensure you have:

- [ ] GitHub repository is public or DO has access
- [ ] `requirements.txt` is up to date
- [ ] Database connection strings ready
- [ ] API keys ready (OpenAI, etc.)
- [ ] Secret key generated for sessions
- [ ] `app.yaml` file added to your repo (provided below)

---

## 📦 Step-by-Step Deployment

### Step 1: Add app.yaml to Your Repository

1. Download the `app.yaml` file provided
2. Place it in the **root** of your repository
3. Commit and push to GitHub:

```bash
git add app.yaml
git commit -m "Add Digital Ocean app.yaml configuration"
git push origin main
```

### Step 2: Create App in Digital Ocean

1. **Go to Digital Ocean Dashboard**
   - Navigate to [cloud.digitalocean.com](https://cloud.digitalocean.com)
   - Click "Create" → "Apps"

2. **Connect GitHub**
   - Select "GitHub" as source
   - Authorize Digital Ocean if needed
   - Select repository: `Siloq-seo/siloq-app`
   - Select branch: `main`

3. **Configure Using app.yaml**
   - Digital Ocean should detect your `app.yaml`
   - If not, click "Edit Plan" and select "Use app.yaml"
   - Review the configuration

4. **Click "Next"** → **Review** → **Create Resources**

### Step 3: Wait for Initial Build

- First build takes 5-10 minutes
- You'll see build logs in real-time
- Don't worry if it fails initially - you need to add environment variables

---

## 🔐 Environment Variables Setup

After creating the app, you **MUST** set these environment variables:

### Go to App Settings → Environment Variables

Add these variables (one by one):

#### Required Variables:

| Variable | Value | Type | Where to Get It |
|----------|-------|------|----------------|
| `DATABASE_URL` | `postgresql://user:pass@host:port/db` | SECRET | From DO Managed Database or external DB |
| `REDIS_URL` | `redis://user:pass@host:port` | SECRET | From DO Managed Valkey (we set this up before) |
| `OPENAI_API_KEY` | `sk-...` | SECRET | From OpenAI dashboard |
| `SECRET_KEY` | Generate a random string | SECRET | Use: `openssl rand -hex 32` |
| `ENVIRONMENT` | `production` | PLAIN | Set to production |
| `PORT` | `8080` | PLAIN | Must match http_port in app.yaml |

#### Optional Variables (add if needed):

| Variable | Description |
|----------|-------------|
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) |
| `MAX_WORKERS` | Number of worker processes |
| `LOG_LEVEL` | Logging level (INFO, DEBUG, etc.) |

### How to Generate SECRET_KEY:

```bash
# On Mac/Linux:
openssl rand -hex 32

# Or in Python:
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 🗄️ Database Setup

You have two options for the database:

### Option A: Digital Ocean Managed PostgreSQL (Recommended)

1. **Create Database:**
   - Go to Digital Ocean Dashboard
   - Click "Create" → "Databases"
   - Select "PostgreSQL 16"
   - Choose plan: **Basic ($15/month for dev)**
   - Region: Same as your app (e.g., NYC)
   - Create database cluster

2. **Get Connection String:**
   - Click on your database cluster
   - Go to "Connection Details"
   - Copy the connection string
   - Format: `postgresql://username:password@host:port/database?sslmode=require`

3. **Add to App:**
   - Go to your App Settings → Environment Variables
   - Add `DATABASE_URL` with the connection string

4. **Trust App in Database:**
   - In database settings → "Trusted Sources"
   - Add your app name

### Option B: External Database

If you have an existing database:
- Get the connection string
- Add it as `DATABASE_URL` in environment variables

---

## 🎯 Post-Deployment

### 1. Run Database Migrations

After first deployment, you need to run migrations:

```bash
# Digital Ocean Console (or SSH into app)
python -m alembic upgrade head
```

Or add to your `run.py`:
```python
import subprocess
import os

if os.getenv("ENVIRONMENT") == "production":
    # Run migrations on startup
    subprocess.run(["alembic", "upgrade", "head"])
```

### 2. Verify Deployment

1. **Check App URL:**
   - Go to your app in DO dashboard
   - Click on the URL (e.g., `siloq-app-xxxxx.ondigitalocean.app`)

2. **Check Health:**
   - Visit: `https://your-app-url.ondigitalocean.app/health`
   - Should return 200 OK

3. **Check Logs:**
   - In DO dashboard → App → Runtime Logs
   - Look for any errors

### 3. Set Up Custom Domain (Optional)

1. **Add Domain in DO:**
   - App Settings → Domains
   - Add your domain (e.g., `api.siloq.com`)

2. **Configure DNS:**
   - Add CNAME record in your DNS provider
   - Point to the DO app URL

---

## 🔧 Troubleshooting

### Issue: "No components detected"

**Solution:**
1. Make sure `app.yaml` is in the root of your repo
2. Commit and push to GitHub
3. Trigger a new deployment

### Issue: "Build failed - pip install error"

**Solution:**
1. Check your `requirements.txt` is valid
2. Make sure all packages are available on PyPI
3. Check build logs for specific error

### Issue: "App crashed after deployment"

**Solutions:**
1. **Check environment variables are set**
   - Missing DATABASE_URL or REDIS_URL?

2. **Check your run.py**
   - Does it bind to `0.0.0.0` instead of `localhost`?
   - Does it use the PORT environment variable?

3. **Check logs:**
   ```bash
   # In DO dashboard → Runtime Logs
   ```

4. **Common fixes in run.py:**
   ```python
   import os
   import uvicorn
   
   if __name__ == "__main__":
       port = int(os.getenv("PORT", 8080))
       uvicorn.run(
           "app.main:app",
           host="0.0.0.0",  # Important! Not localhost
           port=port,
           reload=False
       )
   ```

### Issue: "Database connection failed"

**Solutions:**
1. Check DATABASE_URL format is correct
2. Make sure database allows connections from your app
3. Add `?sslmode=require` to connection string if using managed DB

### Issue: "Redis/Valkey connection failed"

**Solutions:**
1. Check REDIS_URL format: `redis://default:password@host:port`
2. Make sure Valkey cluster allows connections from your app
3. Check if using TLS: `rediss://` (note the double 's')

---

## 🎨 Updating Your App

### To deploy changes:

1. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "Your changes"
   git push origin main
   ```

2. **Auto-deployment:**
   - Digital Ocean will automatically detect the push
   - Build and deploy the new version
   - Zero-downtime deployment

### To manually trigger deployment:

1. Go to DO dashboard → Your App
2. Click "Actions" → "Force Rebuild and Deploy"

---

## 📊 Monitoring & Scaling

### View Metrics:
- CPU usage
- Memory usage
- Request count
- Response times

### Scaling Options:

**Vertical Scaling:**
- Upgrade instance size in app settings
- `basic-xxs` ($5) → `basic-xs` ($12) → `basic-s` ($24)

**Horizontal Scaling:**
- Increase instance count in `app.yaml`
- Load balanced automatically

---

## 💰 Estimated Costs

| Service | Plan | Monthly Cost |
|---------|------|--------------|
| App Platform | Basic (512MB) | $5 |
| PostgreSQL | Basic (1GB) | $15 |
| Valkey/Redis | Basic (1GB) | $15 |
| **Total** | **Development** | **$35/month** |

For production, upgrade to:
- App: $12 (1GB RAM)
- Database: $30-60 (2-4GB)
- Redis: $30-60 (2GB HA)
- **Total: $72-132/month**

---

## 🆘 Need Help?

1. **Check Digital Ocean Docs:** [docs.digitalocean.com/products/app-platform](https://docs.digitalocean.com/products/app-platform/)
2. **Check Logs:** Always start with runtime logs
3. **Community:** [DigitalOcean Community](https://www.digitalocean.com/community)
4. **Support:** Available 24/7 via dashboard

---

## ✅ Quick Checklist

Before going live:

- [ ] app.yaml committed to repo
- [ ] All environment variables set
- [ ] Database created and connected
- [ ] Redis/Valkey created and connected
- [ ] Database migrations run
- [ ] Health check endpoint working
- [ ] Custom domain configured (if applicable)
- [ ] Monitoring set up
- [ ] Backup strategy in place

---

**You're ready to deploy!** 🚀

If you encounter any issues, refer to the Troubleshooting section or check the Digital Ocean dashboard logs for specific error messages.
