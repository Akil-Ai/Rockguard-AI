# Container image for the RockGuard AI backend.
#
# render.yaml uses Render's native Python runtime (faster builds), so this file
# is not needed for the default deployment. It exists so the same backend can run
# on any container host — Railway, Fly.io, Hugging Face Spaces, Cloud Run — or
# locally with `docker run`.
#
#   docker build -t rockguard-api ./backend
#   docker run -p 8000:8000 -e PORT=8000 rockguard-api

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# opencv-python-headless still links against glib even without the GUI modules,
# and libgomp is required by scikit-learn's OpenMP-backed estimators.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first so the (slow) dependency layer is cached across
# source-only rebuilds.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Train at build time: the artifact is gitignored, and baking it into the image
# means the container starts serving immediately instead of training on boot.
RUN python -m app.ml.train_model

EXPOSE 8000
ENV PORT=8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/api/health" || exit 1

# Shell form so ${PORT} is expanded by the host at runtime.
CMD python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
