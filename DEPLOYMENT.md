# RockGuard AI — Deployment Guide

Complete walkthrough for putting RockGuard AI online: **backend on Render**,
**frontend on Vercel**, both on free tiers.

Total time: ~20 minutes, most of it waiting for the first backend build.

> You must be signed in to Render and Vercel yourself — account creation and
> authorisation cannot be automated. Both accept "Sign in with GitHub" and
> neither requires a credit card for the tiers used here.

---

## Contents

1. [Before you start](#1-before-you-start)
2. [How the deployment is split](#2-how-the-deployment-is-split)
3. [Part A — Backend on Render](#3-part-a--backend-on-render)
4. [Part B — Frontend on Vercel](#4-part-b--frontend-on-vercel)
5. [Part C — Wire the two together](#5-part-c--wire-the-two-together)
6. [Verification checklist](#6-verification-checklist)
7. [Troubleshooting](#7-troubleshooting)
8. [Pre-demo checklist](#8-pre-demo-checklist)
9. [Offline fallback — running locally](#9-offline-fallback--running-locally)
10. [Optional extras](#10-optional-extras)

---

## 1. Before you start

**Accounts** — [render.com](https://render.com) and [vercel.com](https://vercel.com).
Sign in to both with GitHub so they can see your repository.

**Code pushed to GitHub.** Both hosts build from the repo, not from your laptop.

```bash
git status
```

```bash
git push origin main
```

Confirm `render.yaml`, `frontend/vercel.json` and `backend/Dockerfile` are all
present on GitHub before continuing — if they're missing, the hosts have nothing
to read.

---

## 2. How the deployment is split

```
        Vercel  (static site)                    Render  (web service)
   ┌──────────────────────────┐             ┌────────────────────────────┐
   │  frontend/  →  dist/     │  ── HTTPS ─►│  backend/   FastAPI        │
   │  React SPA, Leaflet,     │             │  + background sim loop     │
   │  Recharts                │◄─── JSON ───│  + SQLite (ephemeral)      │
   │                          │             │  + trained model           │
   │  VITE_API_BASE ──────────┼─────────────►  CORS_ORIGINS ─────────────┤
   └──────────────────────────┘             └────────────────────────────┘
        always instant                       sleeps after ~15 min idle
```

**Why the backend is not also on Vercel.** OpenCV, scikit-learn and SciPy total
about **370 MB** installed — well past Vercel's 250 MB serverless bundle limit.
The simulation loop also needs a long-lived process, which serverless functions
don't provide. Render runs it as an ordinary always-on web service.

The two settings that connect the halves are `VITE_API_BASE` (frontend → backend)
and `CORS_ORIGINS` (backend → allows frontend). Getting one of them wrong is the
single most common deployment failure; [Part C](#5-part-c--wire-the-two-together)
covers both.

**Deploy the backend first** — you need its URL before you can configure the
frontend.

---

## 3. Part A — Backend on Render

### 3.1 Create the service

The repo contains `render.yaml`, so Render can provision everything itself.

1. Go to **[dashboard.render.com/blueprints](https://dashboard.render.com/blueprints)**
2. Click **New Blueprint Instance**
3. Select the repository **`Akil-Ai/Rockguard-AI`**
   *(if it isn't listed, click **Configure account** and grant Render access)*
4. Render reads `render.yaml` and shows a service named **`rockguard-api`**
5. Click **Apply** / **Create Resources**

### 3.2 What Render does now

The first build takes **5–10 minutes**. Watch the **Logs** tab. It runs:

```bash
pip install --upgrade pip && pip install -r requirements.txt && python -m app.ml.train_model
```

then starts:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

The training step matters. `risk_model.joblib` is a build output and is
gitignored, so it does not exist in the repo. Without this step the API still
runs but silently falls back to the analytical hazard function instead of the
trained gradient-boosting model.

Look for these lines near the end of the log:

```
Saved model -> .../app/ml/artifacts/risk_model.joblib
ROC-AUC (synthetic hold-out): 0.85...
...
Risk engine: gradient_boosting (loaded)
Simulation loop started (5s interval).
Uvicorn running on http://0.0.0.0:10000
```

### 3.3 Confirm it works

Copy your service URL from the top of the Render dashboard — it looks like
`https://rockguard-api.onrender.com`. Open:

```
https://<your-service>.onrender.com/api/health
```

You want `"status": "ok"` and, importantly, `"engine": {"loaded": true, ...}`.
If `loaded` is `false`, the training step didn't run — see
[Troubleshooting](#7-troubleshooting).

The interactive API docs are at `https://<your-service>.onrender.com/docs`.

> **Note the URL down.** You need it in Part B.

---

## 4. Part B — Frontend on Vercel

### 4.1 Import the project

1. Go to **[vercel.com/new](https://vercel.com/new)**
2. Import the repository **`Akil-Ai/Rockguard-AI`**
3. **Set Root Directory to `frontend`** ← easy to miss, and it fails without it

   Click **Edit** next to Root Directory and select the `frontend` folder.
   Vercel then reads `frontend/vercel.json` and detects Vite automatically.

### 4.2 Add the environment variable

Before clicking Deploy, expand **Environment Variables** and add:

| Name | Value |
|---|---|
| `VITE_API_BASE` | `https://<your-service>.onrender.com` |

Use your real Render URL. **No trailing slash.** It must be `https://`.

### 4.3 Deploy

Click **Deploy** and wait ~1 minute. Vercel gives you a URL such as
`https://rockguard-ai.vercel.app`.

---

## 5. Part C — Wire the two together

Two settings must agree, or the console will load but never show data.

### 5.1 Tell the backend to trust the frontend

1. Render dashboard → **rockguard-api** → **Environment**
2. Set **`CORS_ORIGINS`** to your actual Vercel URL:

   ```
   https://rockguard-ai.vercel.app
   ```

3. **Save Changes** — Render redeploys automatically (~2 min)

Preview deployments are already handled: `backend/app/config.py` carries a
`cors_origin_regex` that matches this project's own Vercel preview hostnames
(`rockguard-ai-git-<branch>-<user>.vercel.app`) without opening the API to all
of `*.vercel.app`.

### 5.2 Understand the Vite build-time trap

**Vite inlines environment variables at build time, not at run time.**

Changing `VITE_API_BASE` in the Vercel dashboard does *nothing* to an already-built
site. You must redeploy after changing it:

> Vercel → **Deployments** → latest → **⋯** → **Redeploy**

If your console shows "Waking the RockGuard server" forever while the Render
health endpoint clearly works, this is almost always the cause.

---

## 6. Verification checklist

Work through these in order on the live site.

| # | Check | Expected |
|---|---|---|
| 1 | `https://<render>/api/health` | `"status": "ok"`, `"engine": {"loaded": true}` |
| 2 | Open the Vercel URL | Dashboard renders; top-right badge reads **Live** (green) |
| 3 | Browser DevTools → Console | No CORS errors |
| 4 | DevTools → Network | `/api/dashboard` returns **200**, repeating every ~4 s |
| 5 | Press **CRITICAL** on the dashboard | Risk climbs to ~86, several zones turn red/orange, alerts appear |
| 6 | Open **Mine Map** | Leaflet tiles load, six zone polygons coloured by risk |
| 7 | **Rock Analysis** → sample *Fractured* | Annotated image returns with traces outlined, severity ≈ 92 |
| 8 | **Risk Prediction** → *Blasting + severe cracks* | Score 98 CRITICAL with factor breakdown |
| 9 | **Alerts** | Alert log populated, acknowledge works |
| 10 | Press **NORMAL**, wait ~10 s | Risk falls back to ~27 LOW |

If 1 and 2 pass but 4 fails with a CORS error, revisit [5.1](#51-tell-the-backend-to-trust-the-frontend).

---

## 7. Troubleshooting

### Console stuck on "Waking the RockGuard server"

This screen is *normal for the first 30–60 s* after idle. If it persists beyond
~2 minutes:

1. Open `https://<render>/api/health` directly. If it fails, the backend is the
   problem — check Render logs.
2. If health works, `VITE_API_BASE` is wrong or was set after the build.
   Verify in DevTools → Network: the requests should go to your Render domain,
   **not** to the Vercel domain. If they're hitting `vercel.app/api/...`, the
   variable was never applied → set it and **redeploy** ([5.2](#52-understand-the-vite-build-time-trap)).

### CORS error in the browser console

```
Access to fetch at 'https://...onrender.com/api/dashboard' from origin
'https://....vercel.app' has been blocked by CORS policy
```

`CORS_ORIGINS` on Render doesn't match your Vercel URL. It must be the exact
origin — scheme + host, no path, no trailing slash. Update it and let Render
redeploy.

### Badge says "Offline" (red) rather than "Waking"

The API was reached but returned an error, rather than being unreachable. Check
the Render logs for a traceback. A 500 means the backend answered and something
is genuinely broken.

### `/api/health` shows `"engine": {"loaded": false}`

The model artifact is missing — the build's training step failed or was skipped.
Check the Render build log for `Saved model ->`. Confirm the build command
includes `python -m app.ml.train_model`. The API still works in this state (it
falls back to the analytical hazard function), but it is not running the trained
model.

### Render build fails

- **`ModuleNotFoundError` / wheel build errors** → confirm `PYTHON_VERSION` is
  `3.11.9` in the service Environment tab.
- **Out of memory during build** → retry; free-tier builders are occasionally
  starved. The runtime itself needs only ~90–250 MB, well inside the 512 MB limit.
- **`could not find requirements.txt`** → Root Directory isn't set to `backend`.

### Vercel build fails

- **`vite: command not found` / no `package.json`** → Root Directory isn't set
  to `frontend`.
- **Blank white page** → check DevTools console; usually a failed asset path.
  Confirm Output Directory is `dist`.

### Map tiles don't load

The satellite basemap needs internet access to Esri's tile servers. Some venue
networks block them. Switch the basemap dropdown to **Offline grid** — zone
geometry and risk colouring remain fully functional without any tiles.

### Data disappeared after a redeploy

Expected. Render's free filesystem is ephemeral, so the SQLite database resets on
every restart. The simulator refills the charts within seconds. See
[10.2](#102-persistent-database) to make it durable.

---

## 8. Pre-demo checklist

Run through this **15 minutes before** presenting.

- [ ] Open `https://<render>/api/health` to **wake the backend** — this is the
      single most important step. A cold instance takes 30–60 s, and you do not
      want that happening while a judge watches.
- [ ] Open the Vercel URL, confirm the badge reads **Live**.
- [ ] Press **NORMAL** so you start the demo from a clean LOW baseline.
- [ ] Optionally clear accumulated history so the charts are readable:
      Render → **Shell** tab → `python -m scripts.reset_demo`
- [ ] Have the local fallback ready ([section 9](#9-offline-fallback--running-locally))
      in case venue wifi fails.
- [ ] Keep both URLs open in separate browser tabs.

> The backend goes back to sleep after ~15 minutes of inactivity. If there's a
> long gap before your slot, wake it again.

---

## 9. Offline fallback — running locally

Venue wifi fails often. Have this ready as a backup; it needs no internet at all
once installed (switch the map to **Offline grid**).

```bash
start.bat
```

On macOS/Linux/Git Bash:

```bash
bash start.sh
```

This trains the model if needed, installs frontend packages if needed, and starts
both servers. Console at `http://localhost:5173`, API docs at
`http://127.0.0.1:8000/docs`.

Manual equivalent, if the script misbehaves:

```bash
cd backend && pip install -r requirements.txt && python -m app.ml.train_model && python -m uvicorn app.main:app --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

---

## 10. Optional extras

### 10.1 Real SMS alerts

Alerts are **simulated** by default — recorded in the database and shown in the
UI, stamped `IN_APP / SIMULATED`. No credentials are hard-coded anywhere.

To send real SMS, add these in Render → Environment (never commit them):

| Variable | Example |
|---|---|
| `TWILIO_ACCOUNT_SID` | `AC...` |
| `TWILIO_AUTH_TOKEN` | your token |
| `TWILIO_FROM_NUMBER` | `+1...` |
| `ALERT_RECIPIENTS` | `+9198...,+9199...` |

You must also add `twilio` to `backend/requirements.txt`. With all four set, the
Alerts page dispatch mode changes to `SMS (Twilio configured)` and HIGH/CRITICAL
alerts are additionally sent as real messages.

### 10.2 Persistent database

To survive restarts, create a **PostgreSQL** instance (Render's free Postgres, or
Supabase), then set on the backend service:

```
DATABASE_URL=postgresql+psycopg://user:password@host:5432/rockguard
```

Add `psycopg[binary]` to `backend/requirements.txt`. No code changes are needed —
SQLAlchemy handles the rest, and tables are created on startup.

### 10.3 Other container hosts

`backend/Dockerfile` builds the same service for Railway, Fly.io, Hugging Face
Spaces or Cloud Run:

```bash
docker build -t rockguard-api ./backend
```

```bash
docker run -p 8000:8000 rockguard-api
```

Railway and Fly.io have no cold-start sleep, which is more reliable for a live
demo, but both eventually require payment.

### 10.4 Tuning the deployment

Set these on the Render service to change behaviour without code edits:

| Variable | Default | Effect |
|---|---|---|
| `SENSOR_TICK_SECONDS` | `5` | How often the simulator advances |
| `THRESHOLD_MEDIUM` | `35` | LOW → MEDIUM boundary |
| `THRESHOLD_HIGH` | `60` | MEDIUM → HIGH boundary |
| `THRESHOLD_CRITICAL` | `80` | HIGH → CRITICAL boundary |
| `ALERT_COOLDOWN_MINUTES` | `2` | Repeat-alert suppression window |

---

## Reference — what lives where

| File | Purpose |
|---|---|
| `render.yaml` | Render blueprint: build/start commands, env vars, health check |
| `backend/Dockerfile` | Container build for any other host |
| `backend/.dockerignore` | Keeps `.env`, the local DB and caches out of images |
| `frontend/vercel.json` | Vite framework detection + asset caching |
| `backend/.env.example` | Every backend setting, documented |
| `frontend/.env.example` | `VITE_API_BASE` and the build-time caveat |

---

*RockGuard AI — SIH25071. Demo system: simulated sensor data, synthetic training
data, fictional mine. Not validated for operational mine safety.*
