# Boro Vai Downloader API - PRO

## How to Deploy on Render.com (Free)

1. Go to https://render.com -> New Web Service
2. Choose "Public Git Repository" and paste your GitHub repo URL
3. Or upload this folder to GitHub first:
   - Create new repo: boro-vai-downloader-api
   - Upload app.py, requirements.txt, render.yaml
4. Build Command: pip install -r requirements.txt
5. Start Command: gunicorn app:app
6. Deploy!

## How to Deploy on Replit (Easier)

1. Go to replit.com -> Create Repl -> Python
2. Upload app.py and requirements.txt
3. Click Run
4. Copy the URL (e.g., https://your-repl.replit.dev)

## Use with Frontend

In your frontend index.html, set:
const BACKEND_URL = "https://your-api-url.onrender.com";

Then download will work 100%!

Made by Python With Boro Vai
