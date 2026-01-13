# Siloq App - Quick Start Cheat Sheet

## 🚀 30-Second Deploy

1. **Add app.yaml to your repo root**
2. **Push to GitHub:** `git push origin main`
3. **Create app in Digital Ocean:** [cloud.digitalocean.com/apps/new](https://cloud.digitalocean.com/apps/new)
4. **Connect GitHub** → Select `Siloq-seo/siloq-app`
5. **Set Environment Variables** (see below)
6. **Deploy!**

---

## 🔐 Required Environment Variables

```bash
DATABASE_URL=postgresql://user:pass@host:port/db?sslmode=require
REDIS_URL=redis://default:password@host:port
OPENAI_API_KEY=sk-...
SECRET_KEY=$(openssl rand -hex 32)
ENVIRONMENT=production
PORT=8080
```

---

## 🎯 How run.py Works

Your `run.py` should look like this:

```python
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # MUST be 0.0.0.0, not localhost!
        port=port,
        reload=False
    )
```

**Key Points:**
- Uses `0.0.0.0` to accept external connections
- Reads PORT from environment variable
- Starts uvicorn web server
- Loads FastAPI app from `app/main.py`

---

## 💾 Database Setup

### Option 1: Managed PostgreSQL
```bash
# Create in DO Dashboard
Create → Databases → PostgreSQL 16 → Basic $15/month

# Copy connection string and add to env vars
```

### Option 2: Existing Database
```bash
# Just add connection string to DATABASE_URL
```

---

## ⚡ Redis/Valkey Setup

```bash
# We already set this up in previous chat!
# Create → Databases → Valkey → Basic $15/month

# Add connection string to REDIS_URL
```

---

## 🔧 Common Issues & Quick Fixes

### "No components detected"
✅ Add `app.yaml` to repo root and push

### "App crashed"
✅ Check if all env vars are set
✅ Make sure run.py uses `0.0.0.0` not `localhost`

### "Database connection failed"
✅ Add `?sslmode=require` to DATABASE_URL
✅ Check database allows connections from app

### "Build failed"
✅ Check `requirements.txt` is valid
✅ Check build logs for specific error

---

## 📝 After First Deployment

```bash
# Run database migrations
alembic upgrade head

# Or add to run.py:
if os.getenv("ENVIRONMENT") == "production":
    subprocess.run(["alembic", "upgrade", "head"])
```

---

## 💰 Costs

| Service | Cost/Month |
|---------|------------|
| App Platform | $5-12 |
| PostgreSQL | $15-60 |
| Valkey | $15-60 |
| **Total Dev** | **$35** |
| **Total Prod** | **$72-132** |

---

## 🔗 Useful Links

- [Digital Ocean Dashboard](https://cloud.digitalocean.com)
- [App Platform Docs](https://docs.digitalocean.com/products/app-platform/)
- [Previous Valkey Setup Guide](../siloq-valkey-setup-guide.md)

---

## 📞 Support

- **Logs:** App Dashboard → Runtime Logs
- **Docs:** docs.digitalocean.com
- **Support:** 24/7 via dashboard

---

**That's it! You're ready to deploy.** 🎉
