# AnyStreamPro API Backend

FastAPI backend for video downloading with **FFmpeg merge support**.

## Features

- ✅ Extract video formats from any URL
- ✅ Merge video + audio with FFmpeg
- ✅ Stream merged file to user with proper filename
- ✅ Auto-cleanup temp files

## Local Development

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Make sure FFmpeg is installed
# Windows: choco install ffmpeg
# Mac: brew install ffmpeg
# Ubuntu: apt install ffmpeg

# Run server
python main.py
```

## API Endpoints

| Method | Endpoint        | Description                 |
| ------ | --------------- | --------------------------- |
| GET    | `/`             | API info                    |
| GET    | `/health`       | Health + FFmpeg status      |
| POST   | `/api/formats`  | Get video formats           |
| POST   | `/api/download` | Download merged video+audio |

## Deploy to Render (Free Tier)

### Step 1: Push to GitHub

```bash
cd backend
git init
git add .
git commit -m "AnyStreamPro API"
git remote add origin https://github.com/YOUR_USERNAME/anystreampro-api.git
git push -u origin main
```

### Step 2: Deploy on Render

1. Go to [render.com](https://render.com) and sign up
2. Click **"New +" → "Web Service"**
3. Connect your GitHub repo
4. Configure:
   - **Name**: `anystreampro-api`
   - **Runtime**: `Docker`
   - **Plan**: `Free`
   - **Health Check Path**: `/health`
5. Click **"Deploy Web Service"**

### Step 3: Get Your API URL

After deployment, you'll get a URL like:

```
https://anystreampro-api.onrender.com
```

Use this in your frontend's `.env` file:

```
VITE_API_URL=https://anystreampro-api.onrender.com
```

## Files

| File               | Description               |
| ------------------ | ------------------------- |
| `main.py`          | FastAPI application       |
| `requirements.txt` | Python dependencies       |
| `Dockerfile`       | Docker config with FFmpeg |
| `render.yaml`      | Render deployment config  |

## Free Tier Limits

- **Render Free**: 750 hours/month, 100GB bandwidth
- Spins down after 15 min inactivity (cold start ~30s)

## Estimated Costs (After Free Tier)

| Video Length | Size   | Bandwidth Cost |
| ------------ | ------ | -------------- |
| 10 min 1080p | ~500MB | ~$0.05         |
| 1 hour 1080p | ~3GB   | ~$0.30         |
| 1 hour 4K    | ~10GB  | ~$1.00         |
