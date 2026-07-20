# ── Stage 1: build the Astro frontend (single-origin: relative API base) ──────
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install
COPY frontend/ ./
# Empty PUBLIC_API_BASE → the built client calls /api/* relative to its origin.
ENV PUBLIC_API_BASE=""
RUN npm run build

# ── Stage 2: FastAPI runtime that serves the API + the built frontend ─────────
FROM python:3.12-slim AS runtime
WORKDIR /app/backend

# Backend deps
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend source + built frontend (main.py mounts ../frontend/dist when present)
COPY backend/ ./
COPY --from=frontend /app/frontend/dist /app/frontend/dist

ENV PORT=8642
EXPOSE 8642

CMD ["python", "main.py"]
