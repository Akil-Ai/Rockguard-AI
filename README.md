# RockGuard AI

**AI-Based Rockfall Prediction and Alert System for Open-Pit Mines**
Smart India Hackathon — Problem Statement **SIH25071**

A working control-room console that turns rock-face imagery and slope-sensor
telemetry into a graded rockfall risk score, an explanation of *why* the risk is
what it is, a hazard map, and an actionable alert.

> ### ⚠️ Read this first — what this system is and is not
>
> This is a **functional prototype**, not a validated safety product.
>
> * Every sensor reading is produced by a **software simulator**. No physical
>   instruments are connected.
> * The mine, its zones, personnel counts and coordinates are **fictional**.
> * The risk model is trained on a **synthetic dataset** generated from a
>   hand-written hazard function (`backend/app/ml/synthetic.py`). No labelled
>   real-world rockfall dataset was available.
> * Reported metrics (ROC-AUC, Brier score) describe performance on held-out
>   **synthetic** data. They measure how well the model recovered an artificial
>   function — **they are not evidence of real-world predictive accuracy.**
> * Crack detection is a **classical computer-vision heuristic**, not a trained
>   detector. It can and will mistake shadows, drill marks and wet streaks for
>   fractures.
>
> **Do not use this system for operational mine-safety decisions.**

---

## 1. Problem

Rockfall is one of the deadliest and least predictable hazards in open-pit
mining. Benches fail after a combination of slow-acting causes — water forcing
its way into an open joint network, blast vibration shaking an over-steepened
face, freeze–thaw wedging, deteriorating rock-mass quality — and the warning
signs are distributed across instruments and inspection reports that nobody
reads together in real time.

Typical gaps in current practice:

* Slope monitoring data, weather data and visual fracture surveys live in
  **separate systems** and are correlated manually, if at all.
* Crack mapping is done by **eye**, is subjective, and happens on an inspection
  schedule rather than continuously.
* When a risk *is* identified, the decision — evacuate, restrict, or continue —
  is a judgement call with **no traceable reasoning** behind it.
* Alerting is informal: a radio call, if someone is listening.

## 2. Solution

RockGuard AI joins those signals into one pipeline and one screen:

```
Rock-face image ─┐
                 ├─► Feature vector ─► Risk model ─► Risk score (0–100)
Sensor telemetry ┘                                        │
                                                          ├─► Risk level
                                                          ├─► Explanation (why)
                                                          ├─► Hazard zone map
                                                          ├─► Recommended action
                                                          └─► Alert + history
```

What makes it usable rather than just a classifier:

* **A number an operator can act on.** Failure probability is mapped onto a
  0–100 index and four bands (LOW / MEDIUM / HIGH / CRITICAL) with a distinct
  recommended action for each.
* **Every score is explained.** The console always shows which factors are
  driving the risk and by how many points — not a black-box verdict.
* **Risk is per-zone, and the map is the primary view.** A mine is only as safe
  as its most dangerous active bench, and the rollup reflects that.
* **The loop closes.** A rock-face photo analysed on the Rock Analysis page
  feeds straight back into that zone's live risk on the dashboard.

## 3. Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  React + Vite + Tailwind  (frontend/)                        │
│  Dashboard · Mine Map · Rock Analysis · Sensor Monitoring     │
│  Risk Prediction · Alerts · History                          │
│  Recharts (trends)   Leaflet (hazard zones)                  │
└───────────────────────────┬──────────────────────────────────┘
                            │  REST / JSON
                            │  dev:  Vite proxies /api → :8000
                            │  prod: VITE_API_BASE → Render (see §9)
┌───────────────────────────▼──────────────────────────────────┐
│  FastAPI  (backend/app/)                                     │
│                                                              │
│  routers/     dashboard · sensors · predict · vision ·        │
│               alerts · history                               │
│                                                              │
│  services/    simulator.py    simulated IoT sensor network    │
│               crack_detector.py  OpenCV fracture analysis     │
│               risk_engine.py  inference + explainability      │
│               assessment.py   sensors → risk → persist → alert│
│               alerts.py       raise / dedupe / dispatch       │
│               mine.py         fictional pit geometry          │
│                                                              │
│  ml/          synthetic.py    artificial hazard function      │
│               train_model.py  gradient boosting trainer       │
│                                                              │
│  models.py    SQLAlchemy ORM                                 │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│  SQLite  (swap DATABASE_URL for PostgreSQL / Supabase)        │
│  sensor_readings · predictions · alerts · image_analyses      │
└──────────────────────────────────────────────────────────────┘
```

A background task in `main.py` ticks the simulator every few seconds, scores all
six zones, writes the results, and raises alerts — so the trend charts, history
table and alert log keep filling even when nobody is interacting.

## 4. Features

### Dashboard
Mine-wide risk gauge (0–100) with level banding, active-alert count, personnel
at risk, per-zone status board, live risk-history chart, scenario controls, and
the contributing-factor breakdown for the highest-risk zone.

### Mine Map
Leaflet map of the pit with six bench-sector polygons coloured and weighted by
live risk. Click any zone for its sensor readings, contributing factors,
personnel/equipment and recommended action. Satellite, street, and an
**offline grid** basemap so the map still works with no internet.

### Rock-Face Computer Vision
Upload a bench or drone photo (or run one of three bundled synthetic samples).
Returns an annotated image with fracture traces outlined, plus crack density,
composite severity, trace count, longest/total trace length, mean width,
orientation spread, and an inferred rock-quality proxy. Results optionally feed
straight into that zone's live risk.

### AI Risk Engine
Gradient-boosted classifier over eight features — `rainfall, humidity,
temperature, slope_angle, vibration, crack_density, crack_severity,
rock_condition` — returning `risk_score`, `risk_level`, `probability` and
`recommended_action`.

### Explainable AI
Every prediction ships with a per-factor breakdown. Actual output for the
*Heavy rainfall + cracks* preset (score 64.8, HIGH):

```
Rainfall        : HIGH      + 29.4 pts   32.0%
Crack Density   : HIGH      + 22.2 pts   24.2%
Slope Angle     : HIGH      + 17.6 pts   19.2%
Rock Quality    : MEDIUM    + 12.0 pts   13.1%
Crack Severity  : LOW       +  5.8 pts    6.4%
```

### IoT Simulation
Simulated rainfall, humidity, temperature, vibration (PPV), slope/tilt,
displacement and pore pressure across six zones, with **NORMAL → WARNING →
CRITICAL** scenario buttons and per-channel manual override sliders.

### Alerts
Raised automatically at HIGH and CRITICAL, with cooldown de-duplication,
acknowledgement workflow, filtering, and a full in-app history.

```
🚨 ROCKFALL WARNING — A-04
Zone: A-04 (North-East Wall — Bench 3)
Risk: 94/100 [CRITICAL]
Personnel in zone: 23
Primary drivers: Slope Angle CRITICAL, Rainfall HIGH, Crack Density MEDIUM
Action: EVACUATE personnel and equipment from the zone immediately…
```

### History
Risk timelines (all zones or one), predictions-by-level distribution, peak risk
per zone, and an expandable prediction log showing the explanation behind every
past score.

## 5. Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite 5, Tailwind CSS 3, React Router |
| Charts | Recharts |
| Maps | Leaflet + React-Leaflet |
| Icons | lucide-react |
| Backend | Python 3.10+, FastAPI, Uvicorn, Pydantic v2 |
| ML | scikit-learn (GradientBoostingClassifier) |
| CV | OpenCV (headless), NumPy |
| Database | SQLite via SQLAlchemy 2 (PostgreSQL/Supabase-ready) |
| Tests | pytest + FastAPI TestClient |

## 6. AI Approach

### 6.1 The data problem, stated honestly

There is no public labelled rockfall dataset for Indian open-pit benches. Two
options were available: train on a tiny hand-typed table and present the result
as if it meant something, or **generate a synthetic dataset from an explicit,
inspectable hazard function** and be clear about what that does and does not
prove. This project does the second.

`backend/app/ml/synthetic.py` defines a normalised hazard index:

```python
H = 0.16·rain + 0.06·humidity + 0.16·slope + 0.16·vibration
  + 0.18·crack_density + 0.10·crack_severity + 0.14·rock_deficit + 0.04·freeze_thaw
  + 0.18·(rain × crack_density)      # water pressure in an open joint network
  + 0.10·(vibration × slope)         # blast energy into an over-steepened bench
  + 0.06·(freeze_thaw × crack_density)

P(failure) = sigmoid(9.0 · (H − 0.60))
```

Weights encode *qualitative* slope-stability relationships from the
geotechnical literature. They are **not fitted to real failures.** Labels are
Bernoulli draws from `P(failure)`, so the model must learn a genuinely noisy
decision surface rather than memorise a threshold. 35% of rows are sampled
uniformly across the whole input domain so the model is defined everywhere the
UI sliders can reach.

### 6.2 Model

`GradientBoostingClassifier` (350 estimators, depth 3, subsample 0.85), used
**uncalibrated**. This was deliberate: isotonic calibration was tried first and
clamped extreme probabilities to exactly 0.0 and 1.0, which flattened the risk
gauge at the top of its range and silently zeroed out every explanation. The
logistic link of gradient boosting yields smooth probabilities in the open
interval (0, 1), which the rest of the system depends on.

Hold-out performance **on synthetic data**: ROC-AUC ≈ 0.86, Brier ≈ 0.088, mean
absolute error against the known latent probability ≈ 0.023.

### 6.3 Probability → risk score

`risk_score = 100 · P(failure) ^ 0.45`

A strictly monotone presentation transform. It never reorders risk; it spreads
out the low-probability region so the difference between "quiet" and "watch
this" is visible on a gauge instead of being crushed against zero.

### 6.4 Explainability — counterfactual ablation

For each feature, the sample is re-scored with that one feature reset to a safe
reference value, and the resulting drop in risk score is attributed to it.

With only eight features this is exact, cheap, model-agnostic, and needs no SHAP
dependency. It also answers the operator's actual question: *how many risk
points is this factor adding right now?*

Two guards keep the labels honest: a factor's band is derived from its **share**
of total risk (absolute points collapse near score saturation, exactly when
conditions are worst), and it is **capped at the zone's own level**, so a LOW
zone can never display a CRITICAL driver.

### 6.5 Computer vision

No trained crack model is bundled, because there was no annotated dataset to
train one with. Instead:

```
CLAHE contrast equalisation      (open-pit faces are unevenly lit)
  → bilateral filter             (denoise without softening edges)
  → black-hat morphology         (isolate dark structures thinner than 17px)
  → percentile threshold         (bounds marked area to ~7%, exposure-independent)
  → morphological bridging       (reconnect dashed fracture traces)
  → contour filtering            (ribbon geometry: length ≈ perimeter/2,
                                  width ≈ area/length, elongation ≥ 4)
  → local contrast gate          (must be ≥ 20 grey levels darker than the
                                  surrounding rock — this is what stops a photo
                                  of a blank wall reporting fractures)
```

Severity is a weighted composite of trace count, cumulative length, areal
density, longest trace, mean width, and orientation spread (intersecting joint
sets form detachable wedges).

**A YOLO path is wired in** and is used automatically if `ultralytics` is
installed *and* weights exist at `backend/app/ml/artifacts/yolo_cracks.pt`.
Neither is shipped.

## 7. Setup

**Prerequisites:** Python 3.10+ and Node.js 18+.

### Quick start

```bash
start.bat
```

On macOS/Linux/Git Bash:

```bash
bash start.sh
```

This trains the model if needed, installs frontend packages if needed, and
launches both servers.

### Manual setup

**Backend**

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

```bash
copy .env.example .env
```

```bash
python -m app.ml.train_model
```

```bash
python -m uvicorn app.main:app --reload --port 8000
```

**Frontend** (in a second terminal)

```bash
cd frontend
npm install
```

```bash
npm run dev
```

| Service | URL |
|---|---|
| Console | http://localhost:5173 |
| API docs (Swagger) | http://127.0.0.1:8000/docs |
| Health check | http://127.0.0.1:8000/api/health |

### Configuration

All configuration is via `.env` files — **no keys are hard-coded anywhere.**
Copy `backend/.env.example` → `backend/.env` and `frontend/.env.example` →
`frontend/.env` as needed.

Notable settings: `DATABASE_URL` (point at PostgreSQL/Supabase to swap
databases), `SENSOR_TICK_SECONDS`, the three risk thresholds,
`ALERT_COOLDOWN_MINUTES`, and the optional `TWILIO_*` credentials.

**Alert dispatch is SIMULATED unless Twilio credentials are supplied.** Alerts
are always recorded in-app and shown in the UI; with credentials present, the
same alert is additionally sent as a real SMS.

## 8. Run Commands

```bash
python -m app.ml.train_model
```

```bash
python -m scripts.generate_sample_faces
```

```bash
python -m scripts.reset_demo
```

```bash
python -m pytest tests -v
```

```bash
npm run build
```

## 9. Deployment

> **Full step-by-step walkthrough, including troubleshooting and a pre-demo
> checklist: [DEPLOYMENT.md](DEPLOYMENT.md).** This section is the summary.

Live deployment is split across two hosts:

```
   Vercel  (static site)              Render  (web service)
   ┌──────────────────────┐           ┌──────────────────────────┐
   │  frontend/  →  dist/ │  ──HTTPS─►│  backend/  FastAPI       │
   │  React SPA           │           │  + simulation loop       │
   │  VITE_API_BASE ──────┼───────────►  + SQLite (ephemeral)    │
   └──────────────────────┘           └──────────────────────────┘
```

**Why the backend is not on Vercel.** OpenCV, scikit-learn and SciPy total about
370 MB installed, well past Vercel's 250 MB serverless bundle limit. The
simulation loop also needs a long-lived process, which serverless functions do
not provide. Render runs it as an ordinary always-on web service.

### 9.1 Backend → Render

The repo contains `render.yaml`, so Render can provision the service itself:

1. Go to **Render → Blueprints → New Blueprint Instance** and select this repo.
2. Render reads `render.yaml` and creates the `rockguard-api` web service.
3. After the first deploy, set **CORS_ORIGINS** in the service's Environment tab
   to your actual Vercel URL, then redeploy.

Manual setup, if you prefer not to use the blueprint — create a **Web Service**
with root directory `backend` and:

```bash
pip install --upgrade pip && pip install -r requirements.txt && python -m app.ml.train_model
```

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

The build step retrains the model because `risk_model.joblib` is a build output
and is gitignored. Without it the API still runs, but falls back to the
analytical hazard function.

Verify with `https://<your-service>.onrender.com/api/health`.

### 9.2 Frontend → Vercel

1. **Vercel → Add New → Project**, import this repo.
2. Set **Root Directory** to `frontend`. Vercel detects Vite from
   `frontend/vercel.json`.
3. Add an environment variable:

   | Name | Value |
   |---|---|
   | `VITE_API_BASE` | `https://<your-service>.onrender.com` |

4. Deploy.

> **Vite inlines environment variables at build time.** Changing `VITE_API_BASE`
> in the Vercel dashboard has no effect until you trigger a redeploy.

Routing uses `HashRouter`, so every route is served from `/` — no SPA rewrite
rules are required.

### 9.3 Other container hosts

`backend/Dockerfile` builds the same service for Railway, Fly.io, Hugging Face
Spaces or Cloud Run:

```bash
docker build -t rockguard-api ./backend && docker run -p 8000:8000 rockguard-api
```

### 9.4 Two free-tier behaviours to expect

**Cold starts.** Render's free instance sleeps after ~15 minutes of inactivity,
and the next request takes 30–60 seconds to wake it. The console handles this
deliberately: it detects an unreachable (rather than erroring) API, shows a
*"Waking the RockGuard server"* screen with an elapsed timer, polls every 2.5 s
instead of 4 s until it connects, and then continues on its own. Nothing needs
refreshing, and a sleeping backend never surfaces as an error.

*Before a live demo, open the API URL a minute early so the instance is warm.*

**Ephemeral database.** The container filesystem resets on every restart and
redeploy, so recorded history does not survive. This is harmless here — the
simulator refills the charts within seconds — but set `DATABASE_URL` to a
managed Postgres instance if you need readings to persist.

## 10. Demo Flow

A five-minute walkthrough that exercises the whole pipeline.

**1 — Baseline.** Open the Dashboard. Press **Reset**, then **NORMAL**.
Mine-wide risk settles around **27/100 — LOW**, all six zones green, no active
alerts.

**2 — Weather turns.** Press **WARNING** (sustained rainfall, saturated slope,
some blasting). Risk climbs to roughly **50/100 — MEDIUM**. Zones A-04 and C-03
move to amber. The contributing-factor panel now shows Rainfall and Crack
Density leading.

**3 — Blasting on a fractured face.** Press **CRITICAL**. Risk jumps to
**~86/100 — CRITICAL**. Several zones go orange/red, and alerts fire
automatically.

**4 — The map.** Open **Mine Map**. The pit ring shows the hazard spread —
C-03 red, A-04/B-02/B-05 orange, A-01/C-06 green. Click the red zone for its
readings, factors and recommended action.

**5 — The AI explains itself.** Open **Risk Prediction** → preset
*Blasting + severe cracks*. Score **98 — CRITICAL**, with the factor bar chart,
breakdown table and contribution radar showing exactly what is driving it.

**6 — Computer vision.** Open **Rock Analysis** → sample **Fractured**. The
detector outlines the fracture traces and reports severity ≈ **92/100
(CRITICAL)**, density 6.8%, 38 traces. With *feed results into the live risk
engine* ticked, that zone's dashboard risk moves in response.

**7 — Alerts.** Open **Alerts** for the full log — zone, score, personnel in
zone, primary drivers, recommended action, dispatch mode — then acknowledge one.

**8 — History.** Open **History** for the risk timeline, per-zone peaks, and the
prediction log; expand any row to see the explanation behind that past score.

> Sample rock-face images live in `frontend/public/samples/` and are procedurally
> generated, not photographs — they are labelled as such in the image itself.

## 11. Limitations

Stated plainly, because a safety system that overstates itself is worse than none.

1. **No real-world validation.** The model has never seen a real rockfall. Its
   metrics describe recovery of an artificial function on synthetic data.
2. **Synthetic training data.** Hazard-function weights are informed by
   qualitative geotechnical reasoning, not fitted to observed failures. Real
   deployment requires retraining on instrumented mine data with recorded
   outcomes.
3. **Heuristic crack detection.** Classical CV with no semantic understanding.
   Shadows, wet streaks, drill marks and cable lines can read as fractures; a
   hairline crack below the contrast gate will be missed. The severity
   normalisation constants are calibrated against synthetic images, so absolute
   values would need re-fitting against expert-rated photographs.
4. **Rock quality is a visual proxy.** Inferred from surface fracturing only —
   it is not an RMR or Q rating from a core log.
5. **No physical sensors.** The IoT layer is a simulator. Real integration needs
   drivers, calibration, drift handling, and gap/outlier treatment.
6. **Simplified geomechanics.** No slope-stability finite-element modelling, no
   joint orientation vs. face orientation kinematic analysis, no groundwater
   flow model, no failure-mode classification (planar / wedge / toppling).
7. **Single-site, single-tenant.** One fictional mine, no authentication, no
   roles, no audit trail — all of which a real deployment requires.
8. **Basemap tiles need internet.** Mitigated by the offline-grid option, which
   keeps zone geometry and risk colouring fully usable without a network.
9. **No spatial correlation between zones.** Each zone is scored independently;
   in reality an adjacent failure changes a neighbouring bench's loading.

## 12. Future Scope

**Data and modelling**
* Retrain on instrumented mine data (InSAR, slope-stability radar, prism
  networks, piezometers) with recorded failure outcomes.
* Sequence models (LSTM / temporal CNN) over displacement time series to detect
  the accelerating-creep signature that precedes failure, rather than scoring
  each instant independently.
* Inverse-velocity failure-time prediction alongside the risk score.
* Per-zone model personalisation as each bench accumulates its own history.

**Computer vision**
* Train a YOLO/segmentation model on annotated rock-face imagery — the code path
  is already wired in and switches over automatically once weights exist.
* Photogrammetry / LiDAR point clouds for true 3D joint orientation and
  kinematic wedge analysis.
* Automated drone survey scheduling with change detection between passes.

**Platform**
* Real sensor ingestion over MQTT/LoRaWAN with calibration and drift handling.
* Live SMS/WhatsApp/siren dispatch with escalation chains and on-call rosters.
* Role-based access (operator / geotechnical engineer / mine manager) with a
  full audit trail of who was warned and what they did.
* Offline-first PWA for field tablets in areas with no connectivity.
* Multi-mine tenancy with a regional risk overview.
* DGMS-aligned compliance reporting and automatic incident-report generation.

---

## Project Structure

```
minevision/
├── backend/
│   ├── app/
│   │   ├── main.py                  FastAPI app + background simulation loop
│   │   ├── config.py                .env-driven settings
│   │   ├── database.py  models.py  schemas.py
│   │   ├── ml/
│   │   │   ├── synthetic.py         SYNTHETIC dataset + hazard function
│   │   │   ├── train_model.py       trainer + metrics
│   │   │   └── artifacts/           risk_model.joblib, metrics.json
│   │   ├── routers/                 dashboard sensors predict vision alerts history
│   │   └── services/
│   │       ├── risk_engine.py       inference + counterfactual explanations
│   │       ├── crack_detector.py    OpenCV fracture analysis
│   │       ├── simulator.py         simulated IoT network
│   │       ├── assessment.py        sensors → risk → persist → alert
│   │       ├── alerts.py            raise / dedupe / dispatch
│   │       └── mine.py              fictional pit geometry
│   ├── scripts/                     generate_sample_faces.py, reset_demo.py
│   ├── tests/test_pipeline.py       24 integration tests
│   └── requirements.txt  .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/                   the 7 console pages
│   │   ├── components/              Layout, ui, ScenarioControls, AlertCard
│   │   ├── store/AppContext.jsx     shared live state + polling
│   │   ├── api/client.js            typed API wrapper
│   │   └── lib/risk.js              risk colour/format vocabulary
│   ├── public/samples/              synthetic rock-face images
│   └── package.json  .env.example
├── start.bat  start.sh
└── README.md
```

## Testing

```bash
cd backend && python -m pytest tests -v
```

24 tests covering: monotonic risk across the three demo scenarios, score/level
consistency, probability non-saturation, input clamping on junk data,
explanation completeness and level capping, dataset generation, CV separation of
clean vs. fractured faces, CV rejection of non-images, simulator scenarios and
overrides, worst-zone-dominated mine rollup, and the full API surface.

---

*Built for Smart India Hackathon — SIH25071. Demo system: simulated data,
synthetic model, fictional mine. Not validated for operational mine safety.*
